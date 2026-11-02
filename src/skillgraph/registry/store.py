"""Immutable, indexed in-memory registry loaded from a curated build (TASKS P3.1; ARCHITECTURE §6.2, §9.1, §17).

``load(build_dir)`` reads one installed ``data/curated/<build_id>/`` directory and returns a ``Registry``. It never
substitutes another build: a missing build raises ``BuildNotFoundError`` (``build_status == "NOT_BUILT"``) and a build
that fails any check raises ``BuildInvalidError`` (``build_status == "INVALID"``); the API later maps both to
``503 DATA_NOT_BUILT``. A build is accepted only if, in this order:

1. ``build_manifest.json`` exists, parses, has ``status == "READY"`` and a ``data_build_id`` equal to the directory name;
2. its ``curation_code_version`` is the running code's (an older-code build is stale, as ``validate`` also treats it);
3. each of the seven output files exists and re-hashes to the SHA-256 in the manifest;
4. a ``validation_report.json``, if present, belongs to this build and records no failed check (an absent report is
   allowed and is reported as ``validation == "NOT_RUN"``);
5. every record validates against the source-of-truth schemas in ``skillgraph.model``;
6. the dumped collections pass the builder's own reference check (``curation.build.check_references``);
7. ids are unique, slugs do not collide, cross-references resolve and the manifest counts equal what was loaded.

The registry does not evaluate eligibility, build edges or rank anything, and it contains no network or LLM code.

Immutability. ``Registry`` has no public mutator and rejects attribute assignment. Its indexes are private tuples and
read-only mappings. The model classes are frozen but still contain lists and dicts, so every accessor returns a deep
copy: changing a returned record never changes the registry or any later result. Records handed to ``from_records`` are
copied in for the same reason.

Identifier contract (as the data defines it, nothing invented): a qualification has an ``id`` (``qual:<code>``), a
``code`` and a ``slug`` (``/`` replaced by ``.``); a NOS unit has ``nos:<code>``, a code and a slug; an occupation has
``nco:<code>`` and its NCO code. Lookups are exact and case-sensitive, with no normalisation. A NOS code is *not* tied
to one qualification: ``qualifications_with_nos`` returns every qualification whose NOS table lists the unit. Duplicate
ids, duplicate codes and slug collisions make the build INVALID; they are never resolved by picking one.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from skillgraph.curation.build import MANIFEST_OUT, OUTPUT_FILES, check_references
from skillgraph.curation.config import CURATION_CODE_VERSION
from skillgraph.curation.errors import BuildError
from skillgraph.model.conflict import Conflict
from skillgraph.model.eligibility import EligibilitySourceRow, SourceRowKind
from skillgraph.model.evidence import Evidence
from skillgraph.model.ids import IdError, IdKind, SlugIndex, slug_of, split_id
from skillgraph.model.occupation import Occupation
from skillgraph.model.qualification import Coverage, NosUnit, Qualification
from skillgraph.model.source import SourceDocument

REPORT_NAME = "validation_report.json"
READY = "READY"
MAX_PROBLEMS_SHOWN = 8

# One model per builder output file. The builder owns the file list; a new output file must be given a model here.
MODELS: Mapping[str, type[BaseModel]] = MappingProxyType({
    "qualifications.json": Qualification,
    "nos_units.json": NosUnit,
    "occupations.json": Occupation,
    "sources.json": SourceDocument,
    "evidence.json": Evidence,
    "conflicts.json": Conflict,
    "eligibility_source_rows.json": EligibilitySourceRow,
})
if set(MODELS) != set(OUTPUT_FILES):  # pragma: no cover - guards against builder/registry drift at import time
    raise RuntimeError(f"registry models {sorted(MODELS)} do not match the builder's output files {sorted(OUTPUT_FILES)}")

M = TypeVar("M", bound=BaseModel)


# --------------------------------------------------------------------------------------------------------------------
# Typed errors
# --------------------------------------------------------------------------------------------------------------------


class RegistryError(Exception):
    """Base of every registry failure. ``build_status`` is the API ``BuildStatus`` the failure corresponds to."""

    build_status: str = "INVALID"


class BuildNotFoundError(RegistryError):
    """There is no complete build at the requested location (missing directory or missing ``build_manifest.json``)."""

    build_status = "NOT_BUILT"

    def __init__(self, build_dir: Path, reason: str) -> None:
        super().__init__(f"no curated build at {build_dir}: {reason}")
        self.build_dir = build_dir
        self.reason = reason


class BuildInvalidError(RegistryError):
    """The build exists but failed a check; ``problems`` lists up to the first ones found, in the order checked."""

    build_status = "INVALID"

    def __init__(self, problems: Iterable[str], build_dir: Path | None = None) -> None:
        self.problems: tuple[str, ...] = tuple(problems)
        self.build_dir = build_dir
        shown = "; ".join(self.problems[:MAX_PROBLEMS_SHOWN])
        more = len(self.problems) - MAX_PROBLEMS_SHOWN
        where = f" {build_dir}" if build_dir is not None else ""
        super().__init__(f"invalid curated build{where}: {shown}" + (f" (+{more} more)" if more > 0 else ""))


class UnknownEntityError(RegistryError, LookupError):
    """A lookup key matched nothing. The API maps this to ``404 NOT_FOUND`` (or an ``UNKNOWN_*`` code)."""

    build_status = "READY"

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"unknown {kind}: {key!r}")
        self.kind = kind
        self.key = key


# --------------------------------------------------------------------------------------------------------------------
# Build information
# --------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildInfo:
    """What the registry knows about the build it came from (a read-only summary of ``build_manifest.json``)."""

    data_build_id: str
    status: str
    built_at: str
    curation_code_version: str
    config_digest: str
    validation: str  # "PASSED" (validation_report.json present, no failed check) or "NOT_RUN" (no report)
    counts: Mapping[str, int]


def _frozen_counts(counts: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted(counts.items())))


def _copy(record: M) -> M:
    return record.model_copy(deep=True)


# --------------------------------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------------------------------


class Registry:
    """Read-only, indexed access to one curated build. Construct it with ``load`` or ``Registry.from_records``."""

    __slots__ = ("_build", "_manifest", "_qual", "_qual_code", "_qual_slug", "_nos", "_nos_code", "_nos_slug", "_occ",
                 "_occ_code", "_src", "_ev", "_conflict", "_elig", "_nos_users")

    def __init__(self) -> None:
        raise TypeError("use skillgraph.registry.load(build_dir) or Registry.from_records(...)")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Registry is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Registry is immutable")

    def __repr__(self) -> str:
        bid = self._build.data_build_id if self._build else "in-memory"
        return f"<Registry {bid}: {len(self._qual)} qualifications, {len(self._nos)} NOS units>"

    # ---- construction ---------------------------------------------------------------------------------------------

    @classmethod
    def from_records(
        cls,
        *,
        qualifications: Iterable[Qualification] = (),
        nos_units: Iterable[NosUnit] = (),
        occupations: Iterable[Occupation] = (),
        sources: Iterable[SourceDocument] = (),
        evidence: Iterable[Evidence] = (),
        conflicts: Iterable[Conflict] = (),
        eligibility_source_rows: Iterable[EligibilitySourceRow] = (),
        build: BuildInfo | None = None,
        manifest: Mapping[str, Any] | None = None,
    ) -> Registry:
        """Index already-validated model records (copied in). Raises ``BuildInvalidError`` on a duplicate id or code, a
        slug collision, or a cross-reference that does not resolve. Input order does not affect any result.

        Evidence-reference integrity is checked by ``load`` (on the dumped build); here only the typed references
        between qualifications, NOS units, conflicts and eligibility rows are checked."""
        return _assemble(
            cls,
            {
                "qualifications.json": list(qualifications),
                "nos_units.json": list(nos_units),
                "occupations.json": list(occupations),
                "sources.json": list(sources),
                "evidence.json": list(evidence),
                "conflicts.json": list(conflicts),
                "eligibility_source_rows.json": list(eligibility_source_rows),
            },
            build,
            manifest,
            None,
        )

    # ---- build information ----------------------------------------------------------------------------------------

    @property
    def build(self) -> BuildInfo | None:
        """The build this registry was loaded from, or ``None`` if it was assembled by ``from_records`` without one."""
        return self._build

    def manifest(self) -> dict[str, Any]:
        """A deep copy of the parsed ``build_manifest.json`` (empty for an in-memory registry)."""
        return json.loads(json.dumps(self._manifest))

    # ---- qualifications -------------------------------------------------------------------------------------------

    def qualifications(self) -> tuple[Qualification, ...]:
        """Every qualification, ascending by id."""
        return tuple(_copy(q) for q in self._qual.values())

    def qualification_ids(self) -> tuple[str, ...]:
        return tuple(self._qual)

    def qualification_by_id(self, qualification_id: str) -> Qualification:
        return _copy(_get(self._qual, qualification_id, "qualification id"))

    def qualification_by_code(self, code: str) -> Qualification:
        return self.qualification_by_id(_get(self._qual_code, code, "qualification code"))

    def qualification_by_slug(self, slug: str) -> Qualification:
        return self.qualification_by_id(_get(self._qual_slug, slug, "qualification slug"))

    # ---- NOS units ------------------------------------------------------------------------------------------------

    def nos_units(self) -> tuple[NosUnit, ...]:
        """Every NOS unit, ascending by id."""
        return tuple(_copy(n) for n in self._nos.values())

    def nos_by_id(self, nos_id: str) -> NosUnit:
        return _copy(_get(self._nos, nos_id, "NOS id"))

    def nos_by_code(self, code: str) -> NosUnit:
        return self.nos_by_id(_get(self._nos_code, code, "NOS code"))

    def nos_by_slug(self, slug: str) -> NosUnit:
        return self.nos_by_id(_get(self._nos_slug, slug, "NOS slug"))

    def qualification_ids_with_nos(self, nos_id: str) -> tuple[str, ...]:
        """Ids of every qualification whose NOS table lists this unit, ascending. A shared unit returns several; a
        unit that exists but is listed by no qualification returns ``()``; an unknown id raises."""
        _get(self._nos, nos_id, "NOS id")
        return self._nos_users.get(nos_id, ())

    def qualifications_with_nos(self, nos_id: str) -> tuple[Qualification, ...]:
        return tuple(self.qualification_by_id(q) for q in self.qualification_ids_with_nos(nos_id))

    # ---- occupations ----------------------------------------------------------------------------------------------

    def occupations(self) -> tuple[Occupation, ...]:
        """Every occupation, ascending by id."""
        return tuple(_copy(o) for o in self._occ.values())

    def occupation_by_id(self, occupation_id: str) -> Occupation:
        return _copy(_get(self._occ, occupation_id, "occupation id"))

    def occupation_by_nco_code(self, nco_code: str) -> Occupation:
        return self.occupation_by_id(_get(self._occ_code, nco_code, "NCO code"))

    # ---- provenance, conflicts and source rows --------------------------------------------------------------------

    def evidence_by_id(self, evidence_id: str) -> Evidence:
        return _copy(_get(self._ev, evidence_id, "evidence id"))

    def sources(self) -> tuple[SourceDocument, ...]:
        return tuple(_copy(s) for s in self._src.values())

    def source_by_id(self, source_id: str) -> SourceDocument:
        return _copy(_get(self._src, source_id, "source id"))

    def conflicts(self) -> tuple[Conflict, ...]:
        return tuple(_copy(c) for c in self._conflict.values())

    def conflict_by_id(self, conflict_id: str) -> Conflict:
        return _copy(_get(self._conflict, conflict_id, "conflict id"))

    def eligibility_source_rows(self, qualification_id: str) -> tuple[EligibilitySourceRow, ...]:
        """The extracted eligibility/age source rows of one qualification, ascending by row id. A qualification that
        exists but has none (every ``CATALOGUE_ONLY`` one) returns ``()``; an unknown id raises."""
        _get(self._qual, qualification_id, "qualification id")
        return tuple(_copy(r) for r in self._elig.get(qualification_id, ()))


def _get(index: Mapping[str, M], key: str, kind: str) -> M:
    try:
        return index[key]
    except (KeyError, TypeError):  # TypeError: an unhashable key can never match
        raise UnknownEntityError(kind, str(key)) from None


# --------------------------------------------------------------------------------------------------------------------
# Assembly (shared by load and from_records)
# --------------------------------------------------------------------------------------------------------------------


def _readonly(d: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(d))


def _unique(records: Iterable[M], key: str, label: str, problems: list[str]) -> dict[str, M]:
    """Index by ``key`` attribute, ascending; a repeated id is a problem and keeps the first only to continue checking."""
    out: dict[str, M] = {}
    for r in records:
        k = getattr(r, key)
        if k in out:
            problems.append(f"duplicate {label}: {k}")
        else:
            out[k] = r
    return dict(sorted(out.items()))


def _assemble(
    cls: type[Registry],
    collections: Mapping[str, list[Any]],
    build: BuildInfo | None,
    manifest: Mapping[str, Any] | None,
    build_dir: Path | None,
) -> Registry:
    problems: list[str] = []
    for name, model in MODELS.items():
        wrong = [type(r).__name__ for r in collections[name] if not isinstance(r, model)]
        if wrong:
            raise TypeError(f"{name}: expected {model.__name__} records, got {sorted(set(wrong))}")
    copied = {name: [_copy(r) for r in recs] for name, recs in collections.items()}

    quals = _unique(copied["qualifications.json"], "id", "qualification id", problems)
    nos = _unique(copied["nos_units.json"], "id", "NOS id", problems)
    occs = _unique(copied["occupations.json"], "id", "occupation id", problems)
    srcs = _unique(copied["sources.json"], "id", "source id", problems)
    evs = _unique(copied["evidence.json"], "id", "evidence id", problems)
    confs = _unique(copied["conflicts.json"], "id", "conflict id", problems)
    rows = _unique(copied["eligibility_source_rows.json"], "id", "eligibility row id", problems)

    def by_attr(index: Mapping[str, M], attr: str, label: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for rid, rec in index.items():
            v = getattr(rec, attr)
            if v in out:
                problems.append(f"duplicate {label}: {v} ({out[v]} and {rid})")
            else:
                out[v] = rid
        return dict(sorted(out.items()))

    qual_code = by_attr(quals, "code", "qualification code")
    nos_code = by_attr(nos, "code", "NOS code")
    occ_code = by_attr(occs, "nco_code", "NCO code")

    def slugs(index: Mapping[str, M], slug_of_record: Any, label: str) -> dict[str, str]:
        si = SlugIndex()
        out: dict[str, str] = {}
        for rid, rec in index.items():
            try:
                out[si.add(rid, slug_of_record(rec))] = rid
            except IdError as exc:
                problems.append(f"{label} slug: {exc}")
        return dict(sorted(out.items()))

    qual_slug = slugs(quals, lambda q: q.slug, "qualification")
    nos_slug = slugs(nos, lambda n: slug_of(n.id), "NOS")

    users: dict[str, set[str]] = defaultdict(set)
    for qid, q in quals.items():
        for m in q.nos_memberships:
            if m.nos_id is None:
                continue
            if m.nos_id not in nos:
                problems.append(f"{qid}: NOS table lists unknown {m.nos_id}")
            else:
                users[m.nos_id].add(qid)
    for rid, r in rows.items():
        if r.qualification_id not in quals:
            problems.append(f"{rid}: unknown qualification {r.qualification_id}")
    for cid, c in confs.items():
        kind, _ = split_id(c.subject.entity_id)
        known = quals if kind is IdKind.QUAL else nos if kind is IdKind.NOS else None
        if known is not None and c.subject.entity_id not in known:
            problems.append(f"{cid}: unknown subject {c.subject.entity_id}")

    if problems:
        raise BuildInvalidError(problems, build_dir)

    by_qual: dict[str, list[EligibilitySourceRow]] = defaultdict(list)
    for r in rows.values():
        by_qual[r.qualification_id].append(r)

    reg = object.__new__(cls)
    state = {
        "_build": build,
        "_manifest": json.loads(json.dumps(manifest)) if manifest is not None else {},
        "_qual": _readonly(quals), "_qual_code": _readonly(qual_code), "_qual_slug": _readonly(qual_slug),
        "_nos": _readonly(nos), "_nos_code": _readonly(nos_code), "_nos_slug": _readonly(nos_slug),
        "_occ": _readonly(occs), "_occ_code": _readonly(occ_code),
        "_src": _readonly(srcs), "_ev": _readonly(evs), "_conflict": _readonly(confs),
        "_elig": _readonly({k: tuple(v) for k, v in by_qual.items()}),
        "_nos_users": _readonly({k: tuple(sorted(v)) for k, v in users.items()}),
    }
    for name, value in state.items():
        object.__setattr__(reg, name, value)
    return reg


# --------------------------------------------------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------------------------------------------------


def _problem_text(exc: ValidationError) -> str:
    e = exc.errors()[0]
    where = ".".join(str(p) for p in e["loc"])
    extra = f" (+{len(exc.errors()) - 1} more)" if len(exc.errors()) > 1 else ""
    return f"{where}: {e['msg']}{extra}"


def _read_json(path: Path, problems: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # ValueError covers JSONDecodeError and UnicodeDecodeError
        problems.append(f"{path.name}: unreadable ({type(exc).__name__})")
        return None


def _check_manifest(build_dir: Path, manifest: Any, problems: list[str]) -> None:
    if not isinstance(manifest, dict):
        problems.append(f"{MANIFEST_OUT}: not a JSON object")
        return
    if manifest.get("status") != READY:
        problems.append(f"{MANIFEST_OUT}: status is {manifest.get('status')!r}, not {READY!r}")
    declared = manifest.get("data_build_id")
    try:
        ok = split_id(declared)[0] is IdKind.CB if isinstance(declared, str) else False
    except IdError:
        ok = False
    if not ok:
        problems.append(f"{MANIFEST_OUT}: data_build_id {declared!r} is not a build id")
    elif declared != build_dir.resolve().name:
        problems.append(f"{MANIFEST_OUT}: data_build_id {declared} does not match the directory {build_dir.resolve().name}")
    if manifest.get("curation_code_version") != CURATION_CODE_VERSION:
        problems.append(f"{MANIFEST_OUT}: built by curation code {manifest.get('curation_code_version')!r}, "
                        f"current is {CURATION_CODE_VERSION!r}; rebuild")
    if not isinstance(manifest.get("output_files"), dict):
        problems.append(f"{MANIFEST_OUT}: output_files missing")
    if not isinstance(manifest.get("counts"), dict):
        problems.append(f"{MANIFEST_OUT}: counts missing")


def _validation_state(build_dir: Path, build_id: str, problems: list[str]) -> str:
    path = build_dir / REPORT_NAME
    if not path.is_file():
        return "NOT_RUN"
    report = _read_json(path, problems)
    if report is None:
        return "NOT_RUN"
    if not isinstance(report, dict) or report.get("data_build_id") != build_id:
        problems.append(f"{REPORT_NAME}: missing or belongs to another build")
        return "NOT_RUN"
    failed = report.get("checks_failed")
    if not isinstance(failed, int) or isinstance(failed, bool):
        problems.append(f"{REPORT_NAME}: checks_failed is not a number")
        return "NOT_RUN"
    if failed:
        problems.append(f"{REPORT_NAME}: records {failed} failed check(s)")
    return "PASSED" if not failed else "NOT_RUN"


def _loaded_counts(c: Mapping[str, list[Any]]) -> dict[str, int]:
    quals, rows = c["qualifications.json"], c["eligibility_source_rows.json"]
    return {
        "qualifications_curated": sum(q.coverage is Coverage.CURATED for q in quals),
        "qualifications_catalogue_only": sum(q.coverage is Coverage.CATALOGUE_ONLY for q in quals),
        "nos_units": len(c["nos_units.json"]),
        "occupations": len(c["occupations.json"]),
        "eligibility_rows": sum(r.kind is SourceRowKind.ELIGIBILITY_ROW for r in rows),
        "age_rows": sum(r.kind is SourceRowKind.AGE_9C for r in rows),
        "conflicts_open": len(c["conflicts.json"]),
    }


def load(build_dir: Path | str) -> Registry:
    """Load and verify one installed curated build. Raises ``BuildNotFoundError`` or ``BuildInvalidError``; never falls
    back to another build."""
    build_dir = Path(build_dir)
    if not build_dir.is_dir():
        raise BuildNotFoundError(build_dir, "directory does not exist")
    manifest_path = build_dir / MANIFEST_OUT
    if not manifest_path.is_file():
        raise BuildNotFoundError(build_dir, f"{MANIFEST_OUT} is missing (an incomplete or wrong directory)")

    problems: list[str] = []
    manifest = _read_json(manifest_path, problems)
    if manifest is None:
        raise BuildInvalidError(problems, build_dir)
    _check_manifest(build_dir, manifest, problems)
    if problems:
        raise BuildInvalidError(problems, build_dir)

    # Read each output file once: the bytes that were hashed are the bytes that are parsed.
    raw: dict[str, list[dict]] = {}
    for name in OUTPUT_FILES:
        expected = manifest["output_files"].get(name)
        try:
            blob = (build_dir / name).read_bytes()
        except OSError:
            problems.append(f"{name}: missing or unreadable")
            continue
        if hashlib.sha256(blob).hexdigest() != expected:
            problems.append(f"{name}: SHA-256 differs from {MANIFEST_OUT}")
            continue
        try:
            data = json.loads(blob.decode("utf-8"))
        except ValueError:
            problems.append(f"{name}: not valid JSON")
            continue
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            problems.append(f"{name}: expected a JSON list of objects")
            continue
        raw[name] = data
    validation = _validation_state(build_dir, manifest["data_build_id"], problems)
    if problems:
        raise BuildInvalidError(problems, build_dir)

    models: dict[str, list[Any]] = {}
    for name, model in MODELS.items():
        models[name] = []
        for i, rec in enumerate(raw[name]):
            try:
                models[name].append(model.model_validate(rec))
            except ValidationError as exc:
                problems.append(f"{name}[{i}]: {_problem_text(exc)}")
                break  # one example per file is enough to refuse it
    if problems:
        raise BuildInvalidError(problems, build_dir)

    try:
        check_references(raw)
    except BuildError as exc:
        raise BuildInvalidError([str(exc)], build_dir) from None

    counts = _loaded_counts(models)
    for key, value in counts.items():
        if manifest["counts"].get(key) != value:
            problems.append(f"{MANIFEST_OUT}: counts.{key} is {manifest['counts'].get(key)!r}, loaded {value}")
    if problems:
        raise BuildInvalidError(problems, build_dir)

    info = BuildInfo(
        data_build_id=manifest["data_build_id"], status=manifest["status"], built_at=str(manifest.get("built_at", "")),
        curation_code_version=manifest["curation_code_version"], config_digest=str(manifest.get("config_digest", "")),
        validation=validation, counts=_frozen_counts(counts),
    )
    return _assemble(Registry, models, info, manifest, build_dir)
