"""Validation of an installed curated build (TASKS P1.6; ARCHITECTURE sections 8.6, 9.3 and 18).

``validate(build_dir)`` re-reads the curated JSON and the extraction tables, recomputes counts and cross-document checks
independently of the builder, and compares every discrepancy it finds with the known-deviations register
(``config/known_deviations.yaml``). Nothing is waived: a registered discrepancy is an unresolved data issue reported
beside the check results, and the register must match the observations exactly. The report has no timestamp, so the same
build and inputs give byte-identical output.

It never writes into ``data/raw``, ``data/processed`` or the config; ``write_report`` only adds ``validation_report.json``
to the build directory it was given.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from skillgraph.model.conflict import Conflict
from skillgraph.model.eligibility import EligibilitySourceRow
from skillgraph.model.evidence import Evidence
from skillgraph.model.occupation import Occupation
from skillgraph.model.qualification import NosUnit, Qualification
from skillgraph.model.source import SourceDocument
from skillgraph.provenance.manifest import OVERLAY_NAME
from skillgraph.settings import Settings

from .build import CATALOGUE_NAME, MANIFEST_OUT, OUTPUT_FILES, TABLES, check_references
from .errors import BuildError
from .inputs import canonical_json

DEVIATIONS_PATH = Path("config/known_deviations.yaml")
FINDINGS_PATH = Path("config/known_findings.yaml")
REPORT_NAME = "validation_report.json"
BASELINE_DOC = "docs/baselines/legacy_tests_2026-10-31.md"
LEGACY_BASELINE_TEXT = "23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)"
VANISHED_MESSAGE = "resolution review required: follow the baseline document section 5"
SCHEMA_VERSION = 1
RESOLVED_WORDS = frozenset({"RESOLVED", "ACCEPTED", "WAIVED", "APPROVED", "PASSED", "OK", "CLOSED", "FIXED"})


class ValidationConfigError(BuildError):
    """A register file is malformed. Validation cannot run against an unreadable register."""


# --------------------------------------------------------------------------------------------------------------------
# Discrepancies and the register
# --------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Discrepancy:
    """A source discrepancy found by a check."""

    check: str
    subject: str
    observed: dict[str, Any]

    @property
    def key(self) -> tuple[str, str]:
        return (self.check, self.subject)


@dataclass(frozen=True)
class Deviation:
    """A registered (known, unresolved) discrepancy."""

    id: str
    finding: str
    check: str
    subject: str
    observed: dict[str, Any]
    evidence: dict[str, Any]
    status: str
    resolution_criteria: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.check, self.subject)


@dataclass(frozen=True)
class Problem:
    kind: str  # UNREGISTERED | CHANGED_VALUES | VANISHED
    check: str
    subject: str
    message: str
    deviation_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "check": self.check, "subject": self.subject, "message": self.message,
                "deviation_id": self.deviation_id}


def _same(a: Any, b: Any) -> bool:
    """Exact equality; numbers compare by value (12 == 12.0) and bool is never a number."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return a == b


def compare_deviations(found: list[Discrepancy], registered: list[Deviation]) -> list[Problem]:
    """The known-deviations rule: an unregistered discrepancy fails; a registered one with different values fails; a
    registered one that no longer occurs fails ("resolution review required"). No tolerance, no xfail."""
    problems: list[Problem] = []
    by_key: dict[tuple[str, str], Deviation] = {}
    for d in registered:
        if d.key in by_key:
            raise ValidationConfigError(f"the register has two entries for {d.check} / {d.subject}")
        by_key[d.key] = d
    seen: set[tuple[str, str]] = set()
    for f in found:
        if f.key in seen:
            raise ValidationConfigError(f"a check reported {f.check} / {f.subject} twice")
        seen.add(f.key)
        reg = by_key.get(f.key)
        if reg is None:
            problems.append(Problem("UNREGISTERED", f.check, f.subject,
                                    f"unregistered discrepancy {json.dumps(f.observed, sort_keys=True)}"))
        elif not _same(f.observed, reg.observed):
            problems.append(Problem(
                "CHANGED_VALUES", f.check, f.subject,
                f"{reg.id}: observed {json.dumps(f.observed, sort_keys=True)} but registered "
                f"{json.dumps(reg.observed, sort_keys=True)}", reg.id))
    for key, reg in by_key.items():
        if key not in seen:
            problems.append(Problem("VANISHED", reg.check, reg.subject, f"{reg.id}: {VANISHED_MESSAGE}", reg.id))
    return sorted(problems, key=lambda p: (p.check, p.subject, p.kind))


def _load_yaml(path: Path) -> dict:
    try:
        text = path.read_bytes().decode("utf-8")
        data = yaml.safe_load(text)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValidationConfigError(f"{path}: cannot read: {' '.join(str(exc).split())}") from None
    if not isinstance(data, dict):
        raise ValidationConfigError(f"{path}: must be a mapping")
    return data


def load_deviations(path: Path = DEVIATIONS_PATH) -> list[Deviation]:
    data = _load_yaml(path)
    unknown = set(data) - {"deviations"}
    if unknown:
        raise ValidationConfigError(f"{path}: unknown key(s) {sorted(unknown)}")
    out: list[Deviation] = []
    need = {"id", "finding", "check", "subject", "observed", "evidence", "status", "resolution_criteria"}
    for i, e in enumerate(data.get("deviations") or []):
        if not isinstance(e, dict) or set(e) != need:
            raise ValidationConfigError(f"{path}: entry {i} must have exactly the keys {sorted(need)}")
        if e["status"] != "UNRESOLVED":
            raise ValidationConfigError(f"{path}: {e['id']}: status must be UNRESOLVED (nothing is accepted or waived)")
        if not isinstance(e["observed"], dict) or not e["observed"]:
            raise ValidationConfigError(f"{path}: {e['id']}: observed must be a non-empty mapping")
        if not all(isinstance(e[k], str) and e[k].strip() for k in ("id", "finding", "check", "subject", "resolution_criteria")):
            raise ValidationConfigError(f"{path}: {e.get('id')}: id, finding, check, subject, resolution_criteria must be text")
        out.append(Deviation(**e))
    if len({d.id for d in out}) != len(out):
        raise ValidationConfigError(f"{path}: duplicate deviation id")
    return out


@dataclass(frozen=True)
class FindingSpec:
    id: str
    status: str
    check: str
    title: str
    refs: tuple[str, ...]
    extra: dict[str, Any] = field(default_factory=dict)


def load_findings(path: Path = FINDINGS_PATH) -> tuple[list[FindingSpec], dict[str, tuple[int, int]]]:
    data = _load_yaml(path)
    if set(data) != {"findings", "audit_status_counts"}:
        raise ValidationConfigError(f"{path}: expected exactly the keys findings and audit_status_counts")
    specs: list[FindingSpec] = []
    for e in data["findings"]:
        base = {"id", "status", "check", "title", "refs"}
        if not isinstance(e, dict) or not base <= set(e):
            raise ValidationConfigError(f"{path}: malformed finding {e!r}")
        if not isinstance(e["status"], str) or not e["status"] or e["status"] in RESOLVED_WORDS:
            raise ValidationConfigError(f"{path}: {e['id']}: a finding status may not claim resolution or acceptance")
        specs.append(FindingSpec(e["id"], e["status"], e["check"], e["title"], tuple(e["refs"]),
                                 {k: v for k, v in e.items() if k not in base}))
    ids = [s.id for s in specs]
    if ids != [f"DQ-{i:02d}" for i in range(1, 16)]:
        raise ValidationConfigError(f"{path}: findings must be exactly DQ-01..DQ-15 in order, got {ids}")
    counts: dict[str, tuple[int, int]] = {}
    for qp, v in data["audit_status_counts"].items():
        if not (isinstance(v, list) and len(v) == 2 and all(isinstance(n, int) and not isinstance(n, bool) for n in v)):
            raise ValidationConfigError(f"{path}: audit_status_counts[{qp}] must be [transcribed, parsed_uncertain]")
        counts[qp] = (v[0], v[1])
    return specs, counts


# --------------------------------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------------------------------

_MODELS: dict[str, Callable[[dict], Any]] = {
    "qualifications.json": Qualification.model_validate,
    "nos_units.json": NosUnit.model_validate,
    "occupations.json": Occupation.model_validate,
    "sources.json": SourceDocument.model_validate,
    "evidence.json": Evidence.model_validate,
    "conflicts.json": Conflict.model_validate,
    "eligibility_source_rows.json": EligibilitySourceRow.model_validate,
}


def _csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _num(text: str) -> float:
    """A blank cell is 0, as in the legacy suite; a non-numeric cell raises (a corrupt table is not a discrepancy)."""
    text = (text or "").strip()
    if text == "":
        return 0.0
    v = float(text)
    if not math.isfinite(v):
        raise ValueError(f"non-finite number {text!r}")
    return v


@dataclass
class Inputs:
    curated: dict[str, list[dict]]
    build_manifest: dict
    tables: dict[str, list[dict[str, str]]]
    catalogue: list[dict[str, str]]
    overlay: list[dict[str, str]]


def load_inputs(build_dir: Path, settings: Settings) -> Inputs:
    manifest_path = build_dir / MANIFEST_OUT
    if not manifest_path.is_file():
        raise ValidationConfigError(f"{build_dir} is not a complete build ({MANIFEST_OUT} missing)")
    curated = {n: json.loads((build_dir / n).read_text(encoding="utf-8")) for n in OUTPUT_FILES}
    extracted = settings.data_path("extracted_dir")
    tables = {t: _csv(extracted / f"{t}.csv") for t in TABLES}
    return Inputs(curated, json.loads(manifest_path.read_text(encoding="utf-8")), tables,
                  _csv(settings.data_path("acquisition_dir") / CATALOGUE_NAME),
                  _csv(settings.data_path("audit_dir") / OVERLAY_NAME))


# --------------------------------------------------------------------------------------------------------------------
# Cross-document checks (recomputed from the extraction tables, independent of the builder)
# --------------------------------------------------------------------------------------------------------------------

CROSS_CHECKS = (
    "qf_nos_credit_sum_vs_item10", "nos_credits_qf_vs_qp", "nos_level_qf_vs_qp", "qf_nos_hours_sum_vs_item13",
    "item10_credits_vs_catalogue", "nos_code_set_qf_vs_qp", "rows_have_sha_and_page",
)


def _qualifications(inp: Inputs) -> list[str]:
    return sorted(r["qp_code"] for r in inp.tables["qualifications"] if r["doc_type"] == "QF")


def cross_document_discrepancies(inp: Inputs) -> list[Discrepancy]:
    t = inp.tables
    qf_nos = [r for r in t["qf_nos"] if r["doc_type"] == "QF"]
    qf_q = {r["qp_code"]: r for r in t["qualifications"] if r["doc_type"] == "QF"}
    cat = {r["qp_code"].strip(): r for r in inp.catalogue}
    out: list[Discrepancy] = []

    # NOS-level QF vs QP disagreements (credits and level), per qualification and NOS code.
    qp_by = {(r["qp_code"], r["nos_code"]): r for r in t["qp_nos_headers"] if r["nos_code"]}
    nos_credit_diff: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    for r in sorted(qf_nos, key=lambda r: (r["qp_code"], r["nos_code"])):
        if not r["nos_code"]:
            continue
        p = qp_by.get((r["qp_code"], r["nos_code"]))
        if p is None:
            continue
        subject = f"{r['qp_code']} {r['nos_code']}"
        a, b = _num(r["credits"]), _num(p["credits"])
        if a != b:
            nos_credit_diff[r["qp_code"]].append((r["nos_code"], a, b))
            out.append(Discrepancy("nos_credits_qf_vs_qp", subject, {"qf": a, "qp": b}))
        la, lb = _num(r["nsqf_level"]), _num(p["nsqf_level"])
        if la != lb:
            out.append(Discrepancy("nos_level_qf_vs_qp", subject, {"qf": la, "qp": lb}))

    totals = {o["qp_code"]: _num(o["source_value"]) for o in inp.overlay
              if o["target_row_key"].endswith("|QF|nos_table_total_credits")}
    for qp in _qualifications(inp):
        rows = [r for r in qf_nos if r["qp_code"] == qp]
        item10, item13 = qf_q[qp]["credits"], qf_q[qp]["hours_total"]
        if item10 == "" or item13 == "":
            raise ValidationConfigError(f"{qp}: QF item 10 or item 13 was not extracted")
        row_sum = sum(_num(r["credits"]) for r in rows)
        if row_sum != _num(item10):
            obs: dict[str, Any] = {"row_sum": row_sum, "item10": _num(item10)}
            if qp in totals:
                obs["totals_row"] = totals[qp]
            for code, a, b in nos_credit_diff.get(qp, []):  # context: the NOS values behind the disagreement
                obs[f"qf_{code.rsplit('/', 1)[-1]}"], obs[f"qp_{code.rsplit('/', 1)[-1]}"] = a, b
            out.append(Discrepancy("qf_nos_credit_sum_vs_item10", qp, obs))
        hours = sum(_num(r["total_hours"]) for r in rows)
        if hours != _num(item13):
            out.append(Discrepancy("qf_nos_hours_sum_vs_item13", qp, {"row_sum": hours, "item13": _num(item13)}))
        if qp not in cat:
            out.append(Discrepancy("item10_credits_vs_catalogue", qp, {"item10": _num(item10), "catalogue": None}))
        elif _num(item10) != _num(cat[qp]["credits"]):
            out.append(Discrepancy("item10_credits_vs_catalogue", qp, {"item10": _num(item10), "catalogue": _num(cat[qp]["credits"])}))
        qf_codes = {r["nos_code"] for r in rows if r["nos_code"]}
        qp_codes = {r["nos_code"] for r in t["qp_nos_headers"] if r["qp_code"] == qp and r["nos_code"]}
        if not qf_codes or qf_codes != qp_codes:
            out.append(Discrepancy("nos_code_set_qf_vs_qp", qp, {"only_qf": sorted(qf_codes - qp_codes),
                                                                  "only_qp": sorted(qp_codes - qf_codes)}))
    for name in TABLES:
        bad = [i for i, r in enumerate(t[name], start=2)
               if r["extraction_status"] != "UNRESOLVED"
               and not (len(r["source_sha256"]) == 64 and set(r["source_sha256"]) <= set("0123456789abcdef") and r["page"].strip())]
        if bad:
            out.append(Discrepancy("rows_have_sha_and_page", name, {"csv_lines": bad}))
    return sorted(out, key=lambda d: d.key)


def status_counts(inp: Inputs) -> dict[str, tuple[int, int]]:
    """TRANSCRIBED / PARSED_UNCERTAIN per qualification across the six extraction tables, secondary copy excluded."""
    c: dict[str, Counter] = defaultdict(Counter)
    for name in TABLES:
        for r in inp.tables[name]:
            if r["doc_type"] != "QF_SECONDARY":
                c[r["qp_code"]][r["extraction_status"]] += 1
    return {qp: (v["TRANSCRIBED"], v["PARSED_UNCERTAIN"]) for qp, v in sorted(c.items())}


# --------------------------------------------------------------------------------------------------------------------
# Known findings: is each one still present in the curated build?
# --------------------------------------------------------------------------------------------------------------------


def _finding_present(spec: FindingSpec, inp: Inputs) -> tuple[bool | None, str]:
    cur, man = inp.curated, inp.build_manifest
    quals = {q["id"]: q for q in cur["qualifications.json"]}
    flags = lambda q, code: [f for f in quals.get(q, {}).get("quality_flags", []) if f["code"] == code]  # noqa: E731
    kind = spec.check
    if kind == "none":
        return None, ("no curated record to test (NOT_MACHINE_CHECKED); " + str(spec.extra.get("note", "")).strip()).strip()
    if kind == "conflicts":
        have = {c["id"]: c["status"] for c in cur["conflicts.json"]}
        missing = [r for r in spec.refs if have.get(r) != "UNRESOLVED_SOURCE_CONFLICT"]
        return not missing, f"missing or not unresolved: {missing}" if missing else "registered and unresolved"
    if kind == "open_lead":
        lead = [x for x in man["open_leads"] if x["id"] == spec.id and x["status"] == spec.status]
        unavailable = {x["manifest_item_id"] for x in man["sources_unavailable"]}
        ok = bool(lead) and "C3" in unavailable and bool(flags("qual:AMH/Q2301", "SOURCE_UNAVAILABLE"))
        return ok, "open lead, SOURCE_UNAVAILABLE flag and unavailable source C3" if ok else "lead, flag or unavailable source missing"
    if kind == "nco_title":
        occ = [o for o in cur["occupations.json"] if o["nco_code"] == "3122.3551"]
        ok = bool(occ) and occ[0]["title_verification"] == "NOT_FOUND"
        return ok, "title_verification NOT_FOUND" if ok else "3122.3551 missing or its title is now verified"
    if kind == "title_variant":
        q = quals.get("qual:AMH/Q0103", {})
        t = q.get("titles", {})
        ok = bool(t.get("qp")) and t["qp"] != t.get("qf") and bool(flags("qual:AMH/Q0103", "TITLE_VARIANT"))
        return ok, "QP title differs from the QF title and carries TITLE_VARIANT" if ok else "titles no longer differ"
    if kind == "secondary_copy":
        by = {s["manifest_item_id"]: s for s in cur["sources.json"]}
        ok = (by.get("B2b", {}).get("role") == "SECONDARY" and by.get("B2", {}).get("role") == "PRIMARY"
              and by["B2"]["sha256"] != by["B2b"]["sha256"] and bool(flags("qual:AMH/Q0103", "SECONDARY_COPY_BINARY_DIFFERS")))
        return ok, "B2 primary, B2b secondary, hashes differ, flag present" if ok else "copies no longer differ"
    if kind == "pending_overlays":
        want = set(spec.extra["overlays"])
        missing = sorted(want - set(man["overlays"]["pending"]))
        applied = sorted(want & set(man["overlays"]["applied"]))
        return not missing and not applied, f"not pending: {missing}; applied: {applied}" if missing or applied else "still pending, none applied"
    if kind == "numbering_gap":
        ok = bool(flags("qual:AMH/Q2301", "NUMBERING_GAP"))
        return ok, "NUMBERING_GAP flag present" if ok else "NUMBERING_GAP flag missing"
    if kind == "row_unknown":
        row = [r for r in cur["eligibility_source_rows.json"] if r["id"] == spec.extra["row"]]
        ok = bool(row) and row[0]["engine_use"] == "UNKNOWN"
        return ok, "row present and engine_use UNKNOWN" if ok else "row missing or no longer UNKNOWN"
    if kind == "recount":
        return True, "counts are recomputed by the counts_recomputed and audit_status_counts checks"
    if kind == "unavailable":
        have = {x["manifest_item_id"] for x in man["sources_unavailable"]}
        missing = [s for s in spec.extra["sources"] if s not in have]
        return not missing, f"not unavailable: {missing}" if missing else "sources unavailable"
    if kind == "claims_unresolved":
        claims = [c for q in quals.values() for c in q["progression_claims"]]
        ok = bool(claims) and all(c["resolved_target"] is None and c["engine_use"] == "DISPLAY_ONLY" for c in claims)
        return ok, f"{len(claims)} claims, all unresolved and DISPLAY_ONLY" if ok else "a claim is resolved or not DISPLAY_ONLY"
    raise ValidationConfigError(f"{spec.id}: unknown finding check {kind!r}")


# --------------------------------------------------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------------------------------------------------


def _legacy_baseline(root: Path, rerun: bool) -> dict[str, Any]:
    """The legacy suite is never described as passing. By default the documented baseline is quoted; ``rerun`` executes
    tools/check_legacy_baseline.py (which runs the frozen suite unmodified and demands an exact match)."""
    res: dict[str, Any] = {"baseline_doc": BASELINE_DOC, "result": LEGACY_BASELINE_TEXT, "is_passing_suite": False,
                           "rerun": rerun, "rerun_exit_code": None}
    if rerun:
        proc = subprocess.run([sys.executable, "-B", str(root / "tools" / "check_legacy_baseline.py")],
                              capture_output=True, text=True, timeout=900, cwd=root)
        res["rerun_exit_code"] = proc.returncode
        res["rerun_verdict"] = "MATCH" if proc.returncode == 0 and "MATCH" in proc.stdout else "DEVIATION_OR_ERROR"
    return res


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}


def validate(build_dir: Path, settings: Settings | None = None, **kwargs: Any) -> dict[str, Any]:
    """Validate an installed curated build and return the report (also see ``write_report``).

    A missing, malformed or inconsistent input (a manifest without a key, a non-numeric cell, a wrong type) raises
    ``ValidationConfigError`` instead of a bare KeyError/ValueError, so the command fails closed and says so."""
    try:
        return _validate(build_dir, settings, **kwargs)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        raise ValidationConfigError(f"malformed or inconsistent validation input: {type(exc).__name__}: {exc}") from None


def _validate(build_dir: Path, settings: Settings | None = None, *, deviations_path: Path | None = None,
              findings_path: Path | None = None, rerun_legacy: bool = False, repo_root: Path | None = None,
              inputs: Inputs | None = None) -> dict[str, Any]:
    from skillgraph.settings import load_settings

    root = repo_root or Path.cwd()
    st = settings or load_settings()
    inp = inputs or load_inputs(build_dir, st)
    registered = load_deviations(deviations_path or DEVIATIONS_PATH)
    specs, audit_counts = load_findings(findings_path or FINDINGS_PATH)
    man = inp.build_manifest
    checks: list[dict[str, Any]] = []

    checks.append(_check("build_complete", man.get("status") == "READY" and build_dir.name == man.get("data_build_id"),
                         f"{build_dir.name}: status {man.get('status')}, data_build_id {man.get('data_build_id')}"))
    mismatched = [n for n in OUTPUT_FILES
                  if hashlib.sha256((build_dir / n).read_bytes()).hexdigest() != man.get("output_files", {}).get(n)]
    checks.append(_check("output_hashes", not mismatched, f"files differing from the manifest: {mismatched}" if mismatched
                         else f"{len(OUTPUT_FILES)} output files match build_manifest.json"))

    # A build is stale when an input it was built from has changed since: re-hash every recorded input file.
    root_data = st.data_root.resolve()
    stale = []
    for rel, digest in sorted(man["input_files"].items()):
        f = Path(rel) if Path(rel).is_absolute() else root_data / rel
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            stale.append(rel)
    checks.append(_check("inputs_match_build", not stale and bool(man["input_files"]),
                         f"input file(s) missing or changed since the build: {stale}; rebuild" if stale or not man["input_files"]
                         else f"{len(man['input_files'])} recorded input files still hash to the values in build_manifest.json"))

    bad_models: list[str] = []
    for name, model in _MODELS.items():
        for i, rec in enumerate(inp.curated[name]):
            try:
                model(rec)
            except ValidationError as exc:
                bad_models.append(f"{name}[{i}]: {' '.join(str(exc).split())[:160]}")
    checks.append(_check("schema", not bad_models, "; ".join(bad_models[:5]) or "every record validates against its model"))

    try:
        check_references(inp.curated)
        refs_ok, refs_detail = True, "evidence, conflict, source, NOS and qualification references resolve"
    except BuildError as exc:
        refs_ok, refs_detail = False, str(exc)
    checks.append(_check("referential_integrity", refs_ok, refs_detail))

    # Counts recomputed from the extraction tables (DQ-11), compared with the builder's manifest and the curated files.
    t = inp.tables
    cat_codes = {r["qp_code"].strip() for r in inp.catalogue}
    pilot = set(_qualifications(inp))
    recount = {
        "qualifications_curated": len(pilot),
        "qualifications_catalogue_only": len(cat_codes - pilot),
        "nos_units": len({r["nos_code"] for r in t["qf_nos"] if r["doc_type"] == "QF" and r["nos_code"]}),
        "eligibility_rows": sum(r["doc_type"] == "QF" and r["row_type"] == "eligibility_row" for r in t["eligibility_rows"]),
        "age_rows": sum(r["doc_type"] == "QF" and r["row_type"] == "age_9c" for r in t["eligibility_rows"]),
    }
    cur = inp.curated
    in_curated = {
        "qualifications_curated": sum(q["coverage"] == "CURATED" for q in cur["qualifications.json"]),
        "qualifications_catalogue_only": sum(q["coverage"] == "CATALOGUE_ONLY" for q in cur["qualifications.json"]),
        "nos_units": len(cur["nos_units.json"]),
        "eligibility_rows": sum(r["kind"] == "ELIGIBILITY_ROW" for r in cur["eligibility_source_rows.json"]),
        "age_rows": sum(r["kind"] == "AGE_9C" for r in cur["eligibility_source_rows.json"]),
    }
    in_manifest = {k: man["counts"].get(k) for k in recount}
    diffs = {k: {"recomputed": recount[k], "curated": in_curated[k], "manifest": in_manifest[k]} for k in recount
             if not (recount[k] == in_curated[k] == in_manifest[k])}
    checks.append(_check("counts_recomputed", not diffs, f"differences: {diffs}" if diffs else
                         "extraction tables, curated files and build manifest agree: " + json.dumps(recount, sort_keys=True)))
    rules_total = sum(len(q["eligibility"]["rows"]) + 1 for q in cur["qualifications.json"] if q.get("eligibility"))
    checks.append(_check("eligibility_rules_complete", rules_total == recount["eligibility_rows"] + recount["age_rows"],
                         f"{rules_total} structured rules for {recount['eligibility_rows']} eligibility rows and {recount['age_rows']} age rows"))

    got = status_counts(inp)
    expected = {k: tuple(v) for k, v in audit_counts.items()}
    checks.append(_check("audit_status_counts", got == expected,
                         "TRANSCRIBED/PARSED_UNCERTAIN match the audit: " + json.dumps({k: list(v) for k, v in got.items()})
                         if got == expected else f"recomputed {got} but the audit says {expected}; investigate, do not force"))

    # Cross-document checks, each judged against the known-deviations register.
    found = cross_document_discrepancies(inp)
    problems = compare_deviations(found, registered)
    bad_checks = {p.check for p in problems}
    reg_keys = {d.key for d in registered}
    for name in CROSS_CHECKS:
        mine = [f for f in found if f.check == name]
        known = [f for f in mine if f.key in reg_keys and name not in bad_checks]
        problem_text = "; ".join(f"{p.subject}: {p.message}" for p in problems if p.check == name)
        detail = problem_text or ("no discrepancy" if not mine else
                                  f"{len(known)} registered unresolved discrepancy(ies): " + ", ".join(f.subject for f in known))
        checks.append(_check(name, name not in bad_checks, detail))
    unknown_checks = sorted({d.check for d in registered} - set(CROSS_CHECKS))
    checks.append(_check("register_checks_exist", not unknown_checks,
                         f"register entries name unknown check(s): {unknown_checks}" if unknown_checks else "every registered check exists"))

    findings: list[dict[str, Any]] = []
    for s in specs:
        present, detail = _finding_present(s, inp)
        verification = "NOT_MACHINE_CHECKED" if present is None else ("PRESENT" if present else "NOT_PRESENT")
        findings.append({"id": s.id, "title": s.title, "status": s.status, "refs": list(s.refs),
                         "verification": verification, "detail": detail})
        if present is False:
            checks.append(_check(f"finding_{s.id}_present", False, f"{detail}: {VANISHED_MESSAGE}"))
    if all(f["verification"] != "NOT_PRESENT" for f in findings):
        n = sum(f["verification"] == "PRESENT" for f in findings)
        checks.append(_check("known_findings_present", True,
                             f"{n} of {len(findings)} findings confirmed in the curated build; "
                             f"{len(findings) - n} have no curated record (NOT_MACHINE_CHECKED)"))

    unavailable = [{"manifest_item_id": x["manifest_item_id"], "title": x["title"], "reason": x["reason"]}
                   for x in man["sources_unavailable"]]
    checks.append(_check("sources_unavailable", {u["manifest_item_id"] for u in unavailable} >= {"C3", "C4", "D1"},
                         "unavailable: " + ", ".join(u["manifest_item_id"] for u in unavailable)))

    passed = sum(c["status"] == "PASS" for c in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "data_build_id": man["data_build_id"],
        "curation_code_version": man["curation_code_version"],
        "checks_passed": passed,
        "checks_failed": len(checks) - passed,
        "checks": checks,
        "independent_counts": {"recomputed": recount, "audit_status_counts": {k: list(v) for k, v in got.items()}},
        "known_deviations": [
            {"id": d.id, "finding": d.finding, "check": d.check, "subject": d.subject, "observed": d.observed,
             "status": d.status, "resolution_criteria": d.resolution_criteria,
             "matches_observation": not any(p.deviation_id == d.id for p in problems)} for d in registered],
        "deviation_problems": [p.as_dict() for p in problems],
        "known_findings": findings,
        "sources_unavailable": unavailable,
        "legacy_baseline": _legacy_baseline(root, rerun_legacy),
        "overlays": {"applied": man["overlays"]["applied"], "pending": man["overlays"]["pending"]},
    }


def write_report(build_dir: Path, report: dict[str, Any]) -> Path:
    """Write ``validation_report.json`` (canonical JSON) into the build directory and return its path."""
    path = build_dir / REPORT_NAME
    tmp = build_dir / (REPORT_NAME + ".tmp")
    tmp.write_bytes(canonical_json(report))
    tmp.replace(path)  # atomic: a reader never sees a partial report
    return path
