"""P1.4 curated build (ARCHITECTURE §7, §9; TASKS P1.4).

``build`` reads the verified extraction CSVs, the audit overlay and the approvals, and writes one deterministic,
evidence-linked dataset to ``<curated_dir>/<data_build_id>/``. It is fail-closed:

1. every input is hashed, then ``verify_sources`` runs before any data is consumed;
2. ``load_plan`` classifies the overlay (a nonexistent or non-proposal approval raises) and every one of the 52
   ``target_row_key`` values must resolve exactly (``targets.py``) and match the extraction;
3. everything is built in memory with the strict P1.2 models, then written to a staging directory, validated,
   and installed with one directory rename after the inputs have been re-hashed.

An overlay classification is not an effect. ``APPLY`` (an approved ``PROPOSED_*`` row) is the only class that changes a
value or records a structure; the others attach provenance, upgrade one field's status (geometry/corroboration), set
flags or register conflicts. ``engine_use`` is copied from the overlay row (or from the documented default table) and is
never raised by a classification or an approval.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from skillgraph.model.conflict import Conflict, ConflictStatus
from skillgraph.model.eligibility import AuditHint, EligibilitySourceRow, SourceRowKind
from skillgraph.model.evidence import (
    EngineUse,
    QualityFlag,
    QualityFlagCode,
    Severity,
    ValueStatus,
)
from skillgraph.model.ids import IdKind, SlugIndex, make_id, slug_of
from skillgraph.model.occupation import Occupation, TitleVerification
from skillgraph.model.qualification import CreditGroup, Module, NosUnit, Qualification
from skillgraph.provenance.manifest import MANIFEST_NAME, OVERLAY_NAME, verify_sources
from skillgraph.settings import Settings

from .config import CURATION_CODE_VERSION, DEFAULTS_PATH, CurationConfig, load_config
from .errors import BuildError, EvidenceError
from .catalogue_source import verify_catalogue
from .evidence_book import EvidenceBook, SourceRegistry, page_numbers
from .inputs import LINE, Row, canonical_json, diff_snapshots, read_csv, read_json, sha256_file, snapshot
from .overlay import (
    APPROVALS_PATH,
    PROPOSALS,
    ClassifiedRow,
    OverlayClass,
    OverlayStatus,
    load_plan,
    resolve_field,
)
from .targets import Target, TargetKind, check_source_value, resolve_target

TABLES = ("qualifications", "facts", "qf_nos", "qp_nos_headers", "eligibility_rows", "progression_claims")
CATALOGUE_NAME = "approved_qualifications_parsed.csv"
VALIDATION_NAME = "VALIDATION.json"
OUTPUT_FILES = (
    "qualifications.json",
    "nos_units.json",
    "occupations.json",
    "sources.json",
    "evidence.json",
    "conflicts.json",
    "eligibility_source_rows.json",
)
MANIFEST_OUT = "build_manifest.json"
_UNCERTAIN = ValueStatus.PARSED_UNCERTAIN
_UPGRADES = {OverlayStatus.CONFIRMED_BY_GEOMETRY, OverlayStatus.CORROBORATED}

Hook = Callable[[str], None]


@dataclass(frozen=True)
class BuildResult:
    data_build_id: str
    path: Path
    manifest: dict
    reused: bool = False


@dataclass
class Cell:
    raw: str
    value: str
    status: ValueStatus
    evidence_id: str
    engine_use: EngineUse
    overlay_ids: tuple[str, ...] = ()
    pending_ids: tuple[str, ...] = ()
    source_value: str | None = None
    source_evidence_id: str | None = None
    conflict_id: str | None = None


def _num(text: str, what: str) -> float | None:
    if text.strip() == "":
        return None
    try:
        return float(text)
    except ValueError:
        raise BuildError(f"{what}: {text!r} is not a number") from None


def _int(text: str, what: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise BuildError(f"{what}: {text!r} is not an integer") from None


def row_key(file: str, r: Row) -> str:
    qp, doc = r["qp_code"], r["doc_type"]
    if file == "eligibility_rows.csv":
        tail = "age_9c" if r["row_type"] == "age_9c" else f"eligibility_row|{r['s_no']}"
    elif file == "qf_nos.csv":
        tail = r["nos_code"] or f"bridge(s_no {r['s_no']})"
    elif file == "qp_nos_headers.csv":
        tail = r["nos_code"]
    elif file == "facts.csv":
        tail = r["field"]
    elif file == "progression_claims.csv":
        tail = f"claim {r['claim_no']}"
    elif file == "qualifications.csv":
        tail = "qualification"
    else:
        raise BuildError(f"no row key for {file}")
    return f"{qp}|{doc}|{tail}"


class Builder:
    """One build, in memory. Nothing here touches the disk except reading inputs."""

    def __init__(self, *, cfg: CurationConfig, plan, tables: dict[str, list[Row]], manifest: list[Row],
                 validation: dict, catalogue: list[Row], raw_root: Path) -> None:
        self.cfg, self.plan, self.tables = cfg, plan, tables
        self.validation, self.catalogue = validation, catalogue
        secondary = {r["source_sha256"] for r in tables["qualifications.csv"] if r["doc_type"] == "QF_SECONDARY"}
        self.sources = SourceRegistry(manifest, raw_root, secondary)
        self.book = EvidenceBook(self.sources)
        self.effects: dict[str, str] = {}
        self.flags_by_qp: dict[str, list[QualityFlag]] = defaultdict(list)
        self.credit_cells: dict[str, list[tuple[str, float | None, str]]] = defaultdict(list)
        self.attached: set[str] = set()
        self.conflict_attach: dict[str, str] = {
            a: f"conflict:{g.id}" for g in cfg.conflict_groups for a in g.attach
        }
        self._resolve_targets()

    # ---- targets and overlay index -------------------------------------------------------------------------

    def _resolve_targets(self) -> None:
        self.targets: dict[str, Target] = {}
        self.cell_index: dict[tuple[str, str, str], list[ClassifiedRow]] = defaultdict(list)
        self.row_index: dict[tuple[str, str], list[ClassifiedRow]] = defaultdict(list)
        for c in self.plan.rows:
            t = resolve_target(c.row, self.tables)
            check_source_value(c.row, t)
            self.targets[c.row.overlay_id] = t
            if t.kind is TargetKind.CELL:
                self.cell_index[(t.file, t.row[LINE], t.field)].append(c)
                self.row_index[(t.file, t.row[LINE])].append(c)
            elif t.kind is TargetKind.COMPOSITE:
                for r in t.rows:
                    self.row_index[(t.file, r[LINE])].append(c)

    def _attach(self, key: str) -> str | None:
        cid = self.conflict_attach.get(key)
        if cid:
            self.attached.add(key)
        return cid

    def _effect(self, oid: str, effect: str) -> None:
        old = self.effects.get(oid)
        if old and old != effect and not (old in ("EVIDENCE_ATTACHED", "INTERPRETATION_ATTACHED")):
            raise BuildError(f"{oid}: two different effects ({old}, {effect})")
        self.effects[oid] = effect

    # ---- cells ---------------------------------------------------------------------------------------------

    @staticmethod
    def field_status(file: str, r: Row, fld: str) -> ValueStatus:
        status = r.get("extraction_status", "TRANSCRIBED")
        if status == "UNRESOLVED":
            raise BuildError(f"{file} line {r[LINE]}: an UNRESOLVED row cannot be curated")
        try:
            st = ValueStatus(status)
        except ValueError:
            raise BuildError(f"{file} line {r[LINE]}: unknown extraction_status {status!r}") from None
        cells = [x.strip() for x in r.get("uncertain_cells", "").split(",") if x.strip()]
        if file == "qf_nos.csv" and st is _UNCERTAIN and cells:
            return _UNCERTAIN if fld in cells else ValueStatus.TRANSCRIBED
        return st

    def cell(self, file: str, r: Row, fld: str, *, disc: str | None = None, conflict_id: str | None = None) -> Cell:
        key = row_key(file, r)
        cls = self.cell_index.get((file, r[LINE], fld), [])
        raw = r[fld]
        orig = self.field_status(file, r, fld)
        value, status, pending = raw, orig, ()
        if cls:
            if len({c.row.target_row_key for c in cls}) != 1:
                raise BuildError(f"{file} line {r[LINE]} {fld}: overlay rows name one cell with different keys")
            res = resolve_field(self.plan, file, cls[0].row.target_row_key, fld, raw, orig)
            value, status, pending = res.value, (res.value_status or orig), res.pending_overlay_ids
        up_rows = [c for c in cls if c.classification is OverlayClass.INTERPRET and c.row.status in _UPGRADES]
        upgrade = None
        if up_rows and status is not ValueStatus.CORRECTION_APPLIED:
            if len(up_rows) > 1:
                raise BuildError(f"{file} line {r[LINE]} {fld}: more than one status upgrade "
                                 f"({', '.join(sorted(c.row.overlay_id for c in up_rows))})")
            upgrade = up_rows[0].row
            status = ValueStatus(upgrade.status.value)
        # A proposal's engine_use (pending or approved) never reaches the output: only decided rows state a use. A
        # corrected cell with no decided row is UNKNOWN, so approving a correction cannot make a value safe.
        uses = {c.row.engine_use for c in cls if c.row.status not in PROPOSALS}
        if len(uses) > 1:
            raise BuildError(f"{file} line {r[LINE]} {fld}: overlay rows disagree on engine_use {sorted(uses)}")
        if uses:
            engine = next(iter(uses))
        elif status is ValueStatus.CORRECTION_APPLIED:
            engine = EngineUse.UNKNOWN
        else:
            engine = self.cfg.default_engine_use(file, fld, disc)
        touching = [c for c in cls if c.classification is not OverlayClass.PENDING]
        ids = tuple(sorted(c.row.overlay_id for c in touching))
        refs = tuple(sorted({d for c in touching for d in c.row.decision_refs}))
        rkey = f"{file}:{key}"
        common = dict(source_file=r["source_file"], sha256=r["source_sha256"], page=r["page"], record_key=rkey,
                      field=fld, method=r.get("method"), note=f"extraction {file} {key} / {fld}")
        src_val = src_ev = None
        if status is ValueStatus.CORRECTION_APPLIED:
            (applied,) = [c for c in cls if c.classification is OverlayClass.APPLY]
            src_ev = self.book.official(value_status=orig, **common)
            ev = self._correction_evidence(applied.row, file, r, fld, ids, refs)
            src_val = raw
        elif upgrade is not None:
            ev = self._upgrade_evidence(upgrade, file, r, fld, ids, refs)
        else:
            ev = self.book.official(value_status=status, overlay_ids=ids, decision_refs=refs, **common)
        for c in cls:
            self._cell_effect(c, orig, status)
        return Cell(raw, value, status, ev, engine, ids, tuple(pending), src_val, src_ev, conflict_id)

    def _cell_effect(self, c: ClassifiedRow, orig: ValueStatus, final: ValueStatus) -> None:
        oid, k = c.row.overlay_id, c.classification
        if k is OverlayClass.PENDING:
            self._effect(oid, "PENDING_FLAGGED")
        elif k is OverlayClass.APPLY:
            if c.row.status is not OverlayStatus.PROPOSED_CORRECTION:
                raise BuildError(f"{oid}: an approved {c.row.status.value} on a single cell has no defined effect")
            self._effect(oid, "VALUE_REPLACED")
        elif k is OverlayClass.IGNORE:
            self._effect(oid, "NO_RELATIONSHIP_ASSERTED")
        elif k is OverlayClass.DISPLAY:
            if c.row.status is OverlayStatus.SOURCE_NUMBERING_GAP:
                self._effect(oid, "FLAG_ATTACHED")
            elif c.row.status is not OverlayStatus.UNRESOLVED_SOURCE_CONFLICT:
                self._effect(oid, "EVIDENCE_ATTACHED")
        else:
            changed = c.row.status in _UPGRADES and final is not orig
            self._effect(oid, "STATUS_UPGRADED" if changed else "INTERPRETATION_ATTACHED")

    # ---- applied-overlay evidence --------------------------------------------------------------------------

    def _overlay_source(self, ov, row: Row) -> None:
        for name in ("evidence_source_file", "evidence_sha256", "evidence_page", "evidence_location", "method"):
            if not getattr(ov, name).strip():
                raise EvidenceError(f"{ov.overlay_id}: an applied overlay row needs {name}")
        ev_src = self.sources.source_for(ov.evidence_source_file, ov.evidence_sha256)
        row_src = self.sources.source_for(row["source_file"], row["source_sha256"])
        if ev_src.id != row_src.id:
            raise EvidenceError(f"{ov.overlay_id}: cites {ev_src.id} but the target row comes from {row_src.id}")
        if not page_numbers(ov.evidence_page) <= page_numbers(row["page"]):
            raise EvidenceError(f"{ov.overlay_id}: cited page {ov.evidence_page} is not on the row's page {row['page']}")

    def _upgrade_evidence(self, ov, file: str, r: Row, fld: str, ids: tuple[str, ...], refs: tuple[str, ...]) -> str:
        """Evidence for a CONFIRMED_BY_GEOMETRY / CORROBORATED upgrade: the overlay's own confirmation (its method,
        location and page), validated like an applied overlay. The extraction method is not the confirmation method."""
        self._overlay_source(ov, r)  # same source as the row, page within the row's page, location and method present
        if ov.source_value != r[fld]:
            raise EvidenceError(f"{ov.overlay_id}: source_value {ov.source_value!r} differs from the extracted "
                                f"{r[fld]!r}, so it cannot confirm it")
        return self.book.official(
            source_file=ov.evidence_source_file, sha256=ov.evidence_sha256, page=ov.evidence_page,
            record_key=f"{file}:{ov.target_row_key}#{ov.overlay_id}", field=fld,
            value_status=ValueStatus(ov.status.value), method=ov.method, location=ov.evidence_location,
            overlay_ids=ids, decision_refs=tuple(sorted(set(refs) | set(ov.decision_refs))),
            note=f"{ov.overlay_id}: {ov.status.value} for the extraction of {file} {row_key(file, r)} / {fld} "
                 f"(extracted by {r.get('method') or 'unknown'}, confirmed by {ov.method})")

    def _correction_evidence(self, ov, file: str, r: Row, fld: str, ids: tuple[str, ...], refs: tuple[str, ...]) -> str:
        self._overlay_source(ov, r)
        # The corrected value must be printed in the same source and page, as the extraction itself shows in another
        # row (a merged cell is printed once). Otherwise the evidence cannot substantiate it: fail closed.
        # ... and as one merged cell: the printing row is above this one, with only empty cells in between.
        pages = page_numbers(r["page"])
        line = int(r[LINE])
        above = sorted((o for o in self.tables[file] if o["qp_code"] == r["qp_code"] and o["doc_type"] == r["doc_type"]
                        and o["source_sha256"] == r["source_sha256"] and page_numbers(o["page"]) & pages
                        and int(o[LINE]) < line), key=lambda o: -int(o[LINE]))
        printed = []
        for o in above:  # nearest first
            if o.get(fld, "") == ov.overlay_value:
                printed.append(o)
                break
            if o.get(fld, "") != "":
                break
        if not printed:
            raise EvidenceError(
                f"{ov.overlay_id}: the value {ov.overlay_value!r} is not printed on the cited source page, so the "
                "cited evidence cannot substantiate the correction"
            )
        return self.book.official(
            source_file=ov.evidence_source_file, sha256=ov.evidence_sha256, page=ov.evidence_page,
            record_key=f"{file}:{ov.target_row_key}#{ov.overlay_id}", field=fld,
            value_status=ValueStatus.CORRECTION_APPLIED, method=ov.method, location=ov.evidence_location,
            overlay_ids=ids, decision_refs=tuple(sorted(set(refs) | set(ov.decision_refs))),
            note=f"approved {ov.overlay_id}: value printed once, in row line {printed[0][LINE]}, of the same merged cell",
        )

    # ---- Valued dicts --------------------------------------------------------------------------------------

    @staticmethod
    def vd(c: Cell, value) -> dict:
        d = {"value": value, "evidence_class": "OFFICIAL", "evidence_id": c.evidence_id,
             "value_status": c.status.value, "engine_use": c.engine_use.value}
        if c.conflict_id:
            d["conflict_id"] = c.conflict_id
        if c.status is ValueStatus.CORRECTION_APPLIED:
            d["source_value"], d["source_evidence_id"] = c.source_value, c.source_evidence_id
        return d

    def _flag(self, qp: str, code: QualityFlagCode, severity: Severity, message: str, refs: list[str]) -> None:
        self.flags_by_qp[qp].append(QualityFlag(code=code, severity=severity, message=message, refs=sorted(set(refs))))

    # ---- eligibility source rows ---------------------------------------------------------------------------

    @staticmethod
    def _source_row(qp: str, r: Row, data: dict) -> EligibilitySourceRow:
        try:
            return EligibilitySourceRow(**data)
        except ValidationError as exc:
            raise BuildError(f"{qp} {row_key('eligibility_rows.csv', r)}: eligibility row refused: "
                             f"{' '.join(str(exc).split())}") from None

    def eligibility_rows(self, qp: str, qid: str) -> tuple[list[EligibilitySourceRow], dict[str, Cell]]:
        out: list[EligibilitySourceRow] = []
        age_cells: dict[str, Cell] = {}
        f = "eligibility_rows.csv"
        rows = [r for r in self.tables[f] if r["qp_code"] == qp and r["doc_type"] == "QF"]
        for r in sorted(rows, key=lambda x: (x["row_type"] != "age_9c", int(x["s_no"] or 0))):
            row_cls = self.row_index.get((f, r[LINE]), [])
            age = r["row_type"] == "age_9c"
            own = "min_age" if age else "raw_row_text"
            # Effective row-level use = the use of the row's own row-level component, never another field's overlay.
            cells = {fld: self.cell(f, r, fld) for fld in (
                ("min_age",) if age else ("raw_academic_or_skill", "raw_required_experience", "raw_row_text"))}
            row_use = cells[own].engine_use
            # The audit's wording for the row-level decision, verbatim (never interpreted, never raising row_use).
            wording = {c.row.engine_constraint for c in row_cls
                       if c.row.status not in PROPOSALS and c.row.target_field == own and c.row.engine_constraint.strip()}
            if len(wording) > 1:
                raise BuildError(f"{qp} {row_key(f, r)}: overlay rows give different engine_constraint texts")
            constraint = next(iter(wording)) if wording else None
            hints = [AuditHint(overlay_id=c.row.overlay_id, field=c.row.target_field, engine_use=c.row.engine_use,
                               engine_constraint=c.row.engine_constraint or None)
                     for c in sorted(row_cls, key=lambda c: c.row.overlay_id)
                     if c.row.status not in PROPOSALS and c.row.target_field != own]
            rstatus = self.field_status(f, r, "min_age" if r["row_type"] == "age_9c" else "raw_row_text")
            ids = sorted({c.row.overlay_id for c in row_cls if c.classification is not OverlayClass.PENDING})
            pend = sorted({c.row.overlay_id for c in row_cls if c.classification is OverlayClass.PENDING})
            flags: list[QualityFlag] = []
            if pend:
                flags.append(QualityFlag(code=QualityFlagCode.OVERLAY_PENDING_APPROVAL, severity=Severity.INFO,
                                         message=f"Proposed overlay value(s) {', '.join(pend)} not applied (no approval).",
                                         refs=pend))
            if rstatus is _UNCERTAIN:
                flags.append(QualityFlag(code=QualityFlagCode.UNCERTAIN_EXTRACTION, severity=Severity.CAUTION,
                                         message="Extraction status PARSED_UNCERTAIN for this row; not cleared by any "
                                                 "field-level overlay.", refs=ids))
            if age:
                cell = cells["min_age"]
                age_cells[qp] = cell
                out.append(self._source_row(qp, r, dict(
                    id=make_id(IdKind.RULE, f"{qp}/AGE"), qualification_id=qid, kind=SourceRowKind.AGE_9C,
                    min_age=self.vd(cell, _int(cell.value, f"{qp} age")), extraction_status=rstatus,
                    engine_use=row_use, engine_constraint=constraint, overlay_ids=ids,
                    pending_overlay_ids=pend, audit_hints=hints, flags=flags, note=r["note"])))
                continue
            fields = {fld: self.vd(c, c.value) for fld, c in cells.items()}
            out.append(self._source_row(qp, r, dict(
                id=make_id(IdKind.RULE, f"{qp}/E{r['s_no']}"), qualification_id=qid, kind=SourceRowKind.ELIGIBILITY_ROW,
                s_no=_int(r["s_no"], "s_no"), extraction_status=rstatus, engine_use=row_use, engine_constraint=constraint,
                overlay_ids=ids, pending_overlay_ids=pend, audit_hints=hints, flags=flags, note=r["note"], **fields)))
        return out, age_cells

    # ---- qualifications ------------------------------------------------------------------------------------

    def pilot(self, qrow: Row, catalogue_title: str | None) -> tuple[Qualification, list[EligibilitySourceRow], list[dict], list]:
        qp = qrow["qp_code"]
        qid = make_id(IdKind.QUAL, qp)
        f = "qualifications.csv"
        self._check_secondary(qrow)
        src_rows, age_cells = self.eligibility_rows(qp, qid)
        age = age_cells.get(qp)
        if age is None:
            raise BuildError(f"{qp}: no age row")
        if _int(age.value, "age") != _int(qrow["min_age"], f"{qp} qualifications min_age"):
            raise BuildError(f"{qp}: age row {age.value} differs from the qualification record {qrow['min_age']}")
        cq = lambda fld, **kw: self.cell(f, qrow, fld, **kw)  # noqa: E731
        lvl = cq("nsqf_level")
        hrs = {k: cq(c) for k, c in (("theory", "hours_theory"), ("practical", "hours_practical"),
                                       ("ojt_mandatory", "hours_ojt_mandatory"),
                                       ("ojt_recommended", "hours_ojt_recommended"), ("total", "hours_total"))}
        cred = cq("credits", conflict_id=self._attach(f"qualification_credits:{qp}"))
        nco = cq("nco_2015_code")
        mem, mods, groups, units = self.memberships(qp, qid)
        titles = {"qf": qrow["qualification_name"], "catalogue": catalogue_title}
        alias = next((a for a in self.cfg.title_aliases if a.qualification == qp), None)
        if alias:
            titles["qp"] = self.title_alias(alias)
        pend = sorted({c.row.overlay_id for c in self.plan.rows
                       if c.classification is OverlayClass.PENDING and c.row.qp_code == qp})
        if pend:
            self._flag(qp, QualityFlagCode.OVERLAY_PENDING_APPROVAL, Severity.INFO,
                       f"Proposed overlay value(s) {', '.join(pend)} are pending approval and not applied.", pend)
        self._flag(qp, QualityFlagCode.LICENCE_UNCONFIRMED, Severity.INFO, "Source reuse permissions are unconfirmed.", [])
        data = {
            "id": qid, "code": qp, "slug": slug_of(qid), "coverage": "CURATED", "nqr_code": qrow["nqr_code"],
            "titles": titles, "nsqf_level": self.vd(lvl, _num(lvl.value, f"{qp} level")),
            "min_age": self.vd(age, _int(age.value, "age")),
            "hours": {k: self.vd(c, _num(c.value, f"{qp} hours {k}")) for k, c in hrs.items()},
            "credits": self.vd(cred, _num(cred.value, f"{qp} credits")),
            "nco_codes": [self.vd(nco, nco.value)],
            "nos_memberships": mem, "modules": mods, "credit_groups": groups,
            "progression_claims": self.claims(qp, qid), "quality_flags": [],
        }
        item5 = next((r for r in self.tables["facts.csv"] if r["qp_code"] == qp and r["doc_type"] == "QF"
                      and r["field"] == "item5_version"), None)
        if item5:
            c = self.cell("facts.csv", item5, "value", disc="item5_version")
            data["version_info"] = {"item5_version": self.vd(c, c.value)}
        return data, src_rows, units, [nco.value, qp]

    def _check_secondary(self, qrow: Row) -> None:
        """DQ-06: the second copy is corroboration only; it must agree on every curated value."""
        qp = qrow["qp_code"]
        sec = [r for r in self.tables["qualifications.csv"] if r["qp_code"] == qp and r["doc_type"] == "QF_SECONDARY"]
        for s in sec:
            for fld in ("qualification_name", "nsqf_level", "min_age", "credits", "hours_theory", "hours_practical",
                        "hours_ojt_mandatory", "hours_ojt_recommended", "hours_total", "nco_2015_code", "nqr_code"):
                if s[fld] != qrow[fld]:
                    raise BuildError(f"{qp}: the secondary QF copy disagrees on {fld} ({s[fld]!r} vs {qrow[fld]!r})")
            if s["source_sha256"] != qrow["source_sha256"]:
                a, b = (self.sources.source_for(x["source_file"], x["source_sha256"]).id for x in (qrow, s))
                self._flag(qp, QualityFlagCode.SECONDARY_COPY_BINARY_DIFFERS, Severity.INFO,
                           f"The second QF copy ({b}) has a different SHA-256 but identical extracted values; {a} is primary.",
                           [a, b])

    def memberships(self, qp: str, qid: str):
        f = "qf_nos.csv"
        rows = sorted((r for r in self.tables[f] if r["qp_code"] == qp and r["doc_type"] == "QF"),
                      key=lambda r: int(r["s_no"]))
        mem, mods, units = [], [], []
        for r in rows:
            bridge = r["is_bridge"] == "true"
            code = r["nos_code"]
            s_no = _int(r["s_no"], "s_no")
            conf_c = self._attach(f"membership_credits:{qp}:{code}")
            conf_l = self._attach(f"membership_level:{qp}:{code}")
            lvl = self.cell(f, r, "nsqf_level", conflict_id=conf_l)
            cred = self.cell(f, r, "credits", conflict_id=conf_c)
            hrs = {k: self.cell(f, r, c) for k, c in (("theory", "theory"), ("practical", "practical"),
                                                       ("ojt_mandatory", "ojt_mandatory"),
                                                       ("ojt_recommended", "ojt_recommended"), ("total", "total_hours"))}
            ver = None if bridge else self.cell(f, r, "nos_version")
            if bridge and r["nos_version"]:
                raise BuildError(f"{qp} S.No. {s_no}: a bridge row states a version")
            m = {"qualification_id": qid, "s_no": s_no, "core_or_noncore": r["core_or_noncore"],
                 "nsqf_level": self.vd(lvl, _num(lvl.value, "level")),
                 "version": None if bridge else self.vd(ver, ver.value),
                 "hours": {k: self.vd(c, _num(c.value, f"hours {k}")) for k, c in hrs.items()},
                 "credits": self.vd(cred, _num(cred.value, "credits")), "is_bridge": bridge}
            if r["extraction_status"] == "PARSED_UNCERTAIN":  # the row-level flag survives every field-level overlay
                cells = {"nsqf_level": lvl, "credits": cred, "total_hours": hrs["total"],
                         **({"nos_version": ver} if ver else {}), **{k: v for k, v in hrs.items()}}
                named = [x.strip() for x in r["uncertain_cells"].split(",") if x.strip()]
                self._flag(qp, QualityFlagCode.UNCERTAIN_EXTRACTION, Severity.CAUTION,
                           f"S.No. {s_no} {code or 'bridge'}: uncertain cell(s) {', '.join(named) or 'unspecified'}; "
                           f"extraction note: {r['note']}", [cells[n].evidence_id for n in named if n in cells])
            cval = _num(cred.value, "credits")
            self.credit_cells[qp].append((code or f"S{s_no}", cval, cred.evidence_id))
            if bridge:
                mid = make_id(IdKind.MOD, f"{qp}/S{s_no}")
                mods.append({"id": mid, "qualification_id": qid, "s_no": s_no, "title": r["nos_module_name"],
                             "is_bridge": True})
                m["module_id"] = mid
            else:
                nid = make_id(IdKind.NOS, code)
                m["nos_id"] = nid
                units.append({"id": nid, "code": code, "qualification_id": qid, "title": r["nos_module_name"]})
            mem.append(m)
        groups = self.credit_groups(qp, rows)
        return mem, mods, groups, units

    def credit_groups(self, qp: str, rows: list[Row]) -> list[dict]:
        f = "qf_nos.csv"
        out = []
        for c in self.plan.rows:
            t = self.targets[c.row.overlay_id]
            if t.kind is not TargetKind.COMPOSITE or c.row.qp_code != qp:
                continue
            oid = c.row.overlay_id
            if c.classification is OverlayClass.PENDING:
                self._effect(oid, "PENDING_FLAGGED")
                continue
            if c.classification is not OverlayClass.APPLY or c.row.status is not OverlayStatus.PROPOSED_REPRESENTATION:
                raise BuildError(f"{oid}: a composite credit group is only expected as an approved representation")
            bridge, nos = t.rows
            if bridge[t.field] != "" or nos[t.field] == "":
                raise EvidenceError(f"{oid}: the grouping premise (bridge cell empty, NOS cell filled) does not hold")
            expected = f"credit_group: one value '{nos[t.field]}' for bridge + {nos['nos_code']} combined"
            if c.row.overlay_value != expected:
                raise EvidenceError(f"{oid}: overlay_value {c.row.overlay_value!r} does not describe the extracted cells")
            self._overlay_source(c.row, nos)
            self._overlay_source(c.row, bridge)
            status = self.field_status(f, nos, t.field)
            ev = self.book.official(
                source_file=c.row.evidence_source_file, sha256=c.row.evidence_sha256, page=c.row.evidence_page,
                record_key=f"{f}:{c.row.target_row_key}#{oid}", field=t.field, value_status=status,
                method=c.row.method, location=c.row.evidence_location, overlay_ids=(oid,),
                decision_refs=tuple(c.row.decision_refs))
            group = CreditGroup.model_validate({
                "member_s_nos": [_int(bridge["s_no"], "s_no"), _int(nos["s_no"], "s_no")],
                "credits": {"value": float(nos[t.field]), "evidence_class": "OFFICIAL", "evidence_id": ev,
                            "value_status": status.value, "engine_use": EngineUse.NOT_USED.value},
                "overlay_ids": [oid]})
            out.append(group.model_dump(mode="json"))
            self._effect(oid, "GROUP_RECORDED")
        return out

    def claims(self, qp: str, qid: str) -> list[dict]:
        f = "progression_claims.csv"
        out = []
        for r in sorted((r for r in self.tables[f] if r["qp_code"] == qp and r["doc_type"] == "QF"),
                        key=lambda r: int(r["claim_no"])):
            c = self.cell(f, r, "claim_text_verbatim")
            out.append({"id": make_id(IdKind.CLAIM, f"{qp}/P{r['claim_no']}"), "qualification_id": qid,
                        "text_verbatim": c.value, "direction_label": r["direction_label"] or "UNLABELLED",
                        "resolved_target": None, "engine_use": "DISPLAY_ONLY", "evidence_id": c.evidence_id})
        return out

    def verify_catalogue_source(self) -> None:
        src = self.sources.available(self.cfg.catalogue_source_item)
        content = (self.sources.raw_root / self.sources.rel_path[src.id]).read_bytes()
        if hashlib.sha256(content).hexdigest() != src.sha256:
            raise BuildError(f"{src.id}: the file changed after integrity verification")
        verify_catalogue(self.catalogue, content)

    def title_alias(self, a) -> str:
        item = self.validation.get("items", {}).get(a.validation_item, {})
        text = " ".join(str(s) for s in item.get("snippets") or [])
        if a.title not in text:
            raise EvidenceError(f"{a.qualification}: alias {a.title!r} is not in VALIDATION.json items.{a.validation_item}")
        src = self.sources.available(a.source_item)
        if item.get("transport", {}).get("sha256") != src.sha256:
            raise EvidenceError(f"{a.qualification}: VALIDATION.json items.{a.validation_item} describes a different "
                                f"file than {src.id}")
        # The build cannot read the QP PDF (no PDF reader is a project dependency), so this title is NOT confirmed
        # against the document: no OFFICIAL evidence is created for it. It is kept with a flag that says so.
        self._flag(a.qualification, QualityFlagCode.TITLE_VARIANT, Severity.CAUTION,
                   f"VALIDATION.json reports the QP titled {a.title!r} (cover text of {src.id}, same file hash); "
                   "the QF and the catalogue use another title. Both are kept. This build does not read the PDF, so "
                   "the QP title is not independently verified and carries no evidence record.", [src.id])
        return a.title

    # ---- occupations ---------------------------------------------------------------------------------------

    def occupation(self, code: str) -> dict:
        oid = make_id(IdKind.NCO, code)
        entry = self.validation.get("nco", {}).get(code)
        if entry is None:
            return Occupation(id=oid, nco_code=code, title_verification=TitleVerification.NOT_CHECKED).model_dump(mode="json")
        if entry.get("outcome") == "NOT_FOUND" or "title" not in entry:
            return Occupation(id=oid, nco_code=code, title_verification=TitleVerification.NOT_FOUND).model_dump(mode="json")
        src = self.sources.available(f"{entry['source']}-p{entry['page']}")
        text = (self.sources.raw_root / self.sources.rel_path[src.id]).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"views-field-title[^>]*>\s*([^<]*?)\s*</td>\s*<td[^>]*field-nco-2015[^>]*>\s*"
                      + re.escape(code) + r"\s*</td>", text, re.S)
        vm = re.match(r"^\d+\s+(.*?)\s+" + re.escape(code), " ".join(str(entry["title"]).split()))
        if not (m and vm):
            raise EvidenceError(f"{code}: VALIDATION.json reports a title but {src.id} does not show it")
        title = " ".join(html.unescape(m[1]).split())
        if title != vm[1]:
            raise EvidenceError(f"{code}: title {title!r} in {src.id} differs from VALIDATION.json {vm[1]!r}")
        ev = self.book.official(source_file=self.sources.rel_path[src.id], sha256=src.sha256 or "",
                                page=str(entry["page"]), record_key=f"nco:{code}", field="title",
                                value_status=ValueStatus.TRANSCRIBED, method="dge_table_html",
                                location=f"DGE NCO-2015 table row {code}")
        return Occupation(id=oid, nco_code=code, title=title, title_verification=TitleVerification.VERIFIED_IN_SOURCE,
                          evidence_id=ev).model_dump(mode="json")

    # ---- conflicts -----------------------------------------------------------------------------------------

    def conflicts(self) -> list[Conflict]:
        out, in_group = [], set()
        for g in self.cfg.conflict_groups:
            vals: list[tuple[float | str, str]] = []
            for oid in g.overlays:
                c = self.plan.get(oid)
                if c.row.status is not OverlayStatus.UNRESOLVED_SOURCE_CONFLICT:
                    raise BuildError(f"conflict:{g.id}: {oid} is {c.row.status.value}, not an unresolved source conflict")
                if c.row.engine_use is not g.engine_effect:
                    raise BuildError(f"conflict:{g.id}: {oid} engine_use {c.row.engine_use.value} != {g.engine_effect.value}")
                in_group.add(oid)
            for v in g.values:
                if v.overlay:
                    t = self.targets[v.overlay]
                    if t.kind is not TargetKind.CELL:
                        raise BuildError(f"conflict:{g.id}: {v.overlay} is not a single cell")
                    cell = self.cell(t.file, t.row, t.field, disc=t.row.get("field"))
                    vals.append((self._val(t.cell), cell.evidence_id))
                    self._effect(v.overlay, "CONFLICT_REGISTERED")
                elif v.qp_row:
                    q = v.qp_row
                    rows = [r for r in self.tables["qp_nos_headers.csv"] if r["qp_code"] == q["qualification"]
                            and r["doc_type"] == "QP" and r["nos_code"] == q["nos_code"]]
                    if len(rows) != 1:
                        raise BuildError(f"conflict:{g.id}: QP row {q} matched {len(rows)} rows")
                    cell = self.cell("qp_nos_headers.csv", rows[0], q["field"])
                    vals.append((self._val(rows[0][q["field"]]), cell.evidence_id))
                else:
                    cells = [x for x in self.credit_cells[v.qualification] if x[1] is not None]
                    total = float(sum(x[1] for x in cells))
                    ev = self.book.derived(f"conflict:{g.id}:sum_qf_nos_credits",
                                           [x[2] for x in cells],
                                           f"sum of the QF NOS-table credit cells of {v.qualification}")
                    vals.append((total, ev))
            if len({v for v, _ in vals}) < 2:
                raise BuildError(f"conflict:{g.id}: the registered values no longer differ; the finding needs review")
            try:
                out.append(Conflict(
                    id=f"conflict:{g.id}", subject={"entity_id": g.subject.entity_id, "field": g.subject.field},
                    values=[{"value": v, "evidence_id": e} for v, e in vals],
                    status=ConflictStatus.UNRESOLVED_SOURCE_CONFLICT, overlay_ids=list(g.overlays),
                    decision_ref=g.decision_ref, engine_effect=g.engine_effect))
            except ValidationError as exc:
                raise BuildError(f"conflict:{g.id}: {exc}") from None
        unregistered = [c.row.overlay_id for c in self.plan.rows
                        if c.row.status is OverlayStatus.UNRESOLVED_SOURCE_CONFLICT and c.row.overlay_id not in in_group]
        if unregistered:
            raise BuildError(f"unresolved source conflict(s) without a conflict group: {', '.join(unregistered)}")
        return sorted(out, key=lambda c: c.id)

    @staticmethod
    def _val(text: str) -> float | str:
        try:
            return float(text)
        except ValueError:
            return text

    # ---- catalogue -----------------------------------------------------------------------------------------

    def catalogue_only(self, pilot: set[str], source_item: str) -> list[dict]:
        src = self.sources.available(source_item)
        out, seen = [], set()
        for r in self.catalogue:
            qp = r["qp_code"].strip()
            if qp in pilot:
                continue
            if qp in seen:
                raise BuildError(f"catalogue lists {qp} twice")
            seen.add(qp)
            qid = make_id(IdKind.QUAL, qp)

            def cv(fld: str, status: ValueStatus = ValueStatus.TRANSCRIBED) -> dict:
                ev = self.book.official(source_file=self.sources.rel_path[src.id], sha256=src.sha256 or "", page="",
                                        record_key=f"catalogue|{r['sno']}|{qp}", field=fld, value_status=status,
                                        method="html_table_parse_verified", location=f"AMHSSC approved-qualifications table, S.No. {r['sno']}")
                use = self.cfg.default_engine_use(CATALOGUE_NAME, fld).value
                return {"value": _num(r[fld], f"catalogue {qp} {fld}"), "evidence_class": "OFFICIAL", "evidence_id": ev,
                        "value_status": status.value, "engine_use": use}

            data = {"id": qid, "code": qp, "slug": slug_of(qid), "coverage": "CATALOGUE_ONLY", "nqr_code": r["nqr_code"],
                    "titles": {"catalogue": r["qp_name"]}, "nsqf_level": cv("nsqf_level"),
                    "hours": {"total": cv("notional_hours")}, "credits": cv("credits"), "quality_flags": [
                        QualityFlag(code=QualityFlagCode.LICENCE_UNCONFIRMED, severity=Severity.INFO,
                                    message="Source reuse permissions are unconfirmed.", refs=[]).model_dump(mode="json")]}
            odd = sorted({f"U+{ord(ch):04X}" for ch in r["qp_name"] if ord(ch) > 127})
            if odd:  # non-ASCII title (S.No. 27, an en dash in A1 itself): preserved verbatim and flagged
                data["quality_flags"].append(QualityFlag(
                    code=QualityFlagCode.UNCERTAIN_EXTRACTION, severity=Severity.CAUTION,
                    message=f"The catalogue title contains non-ASCII character(s) {', '.join(odd)}, as printed in A1; "
                            "kept verbatim and not normalised, so a plain-ASCII search for this title may not match.",
                    refs=[]).model_dump(mode="json"))
            out.append(data)
        if len(out) != self.cfg.expected_catalogue_only:
            raise BuildError(f"catalogue-only records: {len(out)}, expected {self.cfg.expected_catalogue_only}")
        return out


# ---- orchestration -----------------------------------------------------------------------------------------------


def _inside(a: Path, b: Path) -> bool:
    a, b = a.resolve(), b.resolve()
    return a == b or b in a.parents


def build(
    settings: Settings,
    *,
    approvals_path: Path | None = None,
    config_path: Path | None = None,
    out_root: Path | None = None,
    now: datetime | None = None,
    hook: Hook | None = None,
) -> BuildResult:
    """Build and install the curated dataset; raises (and installs nothing) on any failure."""
    hook = hook or (lambda _stage: None)
    approvals_path = approvals_path or APPROVALS_PATH
    config_path = config_path or DEFAULTS_PATH
    raw_root = settings.data_path("raw_dir")
    extracted = settings.data_path("extracted_dir")
    audit = settings.data_path("audit_dir")
    acquisition = settings.data_path("acquisition_dir")
    out_root = out_root or settings.data_path("curated_dir")
    for name, d in (("raw", raw_root), ("extracted", extracted), ("audit", audit), ("acquisition", acquisition),
                    ("data root raw", settings.data_root / "raw"), ("data root processed", settings.data_root / "processed")):
        if _inside(out_root, d) or _inside(d, out_root):
            raise BuildError(f"the output directory {out_root} overlaps the {name} input directory {d}")
    overlay_csv, catalogue_csv = audit / OVERLAY_NAME, acquisition / CATALOGUE_NAME
    manifest_csv, validation_json = raw_root / MANIFEST_NAME, raw_root / VALIDATION_NAME

    cfg, cfg_digest = load_config(config_path)
    guard_roots = [settings.data_root / "raw", settings.data_root / "processed", raw_root, extracted, audit, acquisition]
    guard_files = [approvals_path, config_path]
    before = snapshot(guard_roots, guard_files)

    report = verify_sources(manifest_csv, raw_root, extracted, overlay_csv)  # raises SourceIntegrityError
    hook("verified")
    plan = load_plan(overlay_csv, approvals_path)  # raises OverlayError (missing approved id, non-proposal, ...)

    tables = {f"{n}.csv": read_csv(extracted / f"{n}.csv") for n in TABLES}
    manifest = read_csv(manifest_csv, ("item_id", "validation_status", "local_relative_path", "sha256"))
    validation = read_json(validation_json)
    catalogue = read_csv(catalogue_csv, ("sno", "qp_name", "qp_code", "nqr_code", "qp_version", "nsqf_level",
                                         "notional_hours", "credits", "ccn"))

    b = Builder(cfg=cfg, plan=plan, tables=tables, manifest=manifest, validation=validation, catalogue=catalogue,
                raw_root=raw_root)
    b.verify_catalogue_source()  # the CSV is derived: it must equal the A1 table it cites (BuildError otherwise)
    primary = [r for r in tables["qualifications.csv"] if r["doc_type"] == "QF"]
    if sorted(r["qp_code"] for r in primary) != sorted(cfg.pilot_qualifications):
        raise BuildError("the extracted qualifications differ from the configured pilot set")
    cat_title = {r["qp_code"].strip(): r["qp_name"] for r in catalogue}
    missing = [q for q in cfg.pilot_qualifications if q not in cat_title]
    if missing:
        raise BuildError(f"pilot qualification(s) missing from the catalogue: {', '.join(missing)}")

    ids = [c.row.overlay_id for c in plan.rows]
    if sorted(ids) != [f"OV-{i:03d}" for i in range(1, len(ids) + 1)]:
        raise BuildError(f"the overlay is incomplete or has gaps: expected the contiguous OV-001..OV-{len(ids):03d}")
    if cfg.expected_overlay_rows is not None and len(ids) != cfg.expected_overlay_rows:
        raise BuildError(f"the overlay has {len(ids)} rows, expected {cfg.expected_overlay_rows}")
    for g in cfg.conflict_groups:
        for oid in g.overlays:
            if oid not in ids:
                raise BuildError(f"conflict:{g.id}: overlay row {oid} does not exist")
    quals: dict[str, dict] = {}
    elig: list[EligibilitySourceRow] = []
    units: dict[str, dict] = {}
    nco_codes: set[str] = set()
    for qrow in sorted(primary, key=lambda r: r["qp_code"]):
        data, rows, us, (nco, qp) = b.pilot(qrow, cat_title[qrow["qp_code"]])
        quals[qp] = data
        elig += rows
        nco_codes.add(nco)
        for u in us:
            e = units.setdefault(u["id"], {"id": u["id"], "code": u["code"], "titles_by_source": {}})
            e["titles_by_source"][u["qualification_id"]] = u["title"]
    occupations = [b.occupation(c) for c in sorted(nco_codes)]
    unused = sorted(set(b.conflict_attach) - b.attached)
    if unused:
        raise BuildError("conflict attach target(s) matched no curated value: " + ", ".join(unused))
    conflicts = b.conflicts()

    # Overlay rows not consumed by a curated field still get their provenance and effect recorded.
    for c in plan.rows:
        oid = c.row.overlay_id
        if oid in b.effects:
            continue
        t = b.targets[oid]
        if t.kind is TargetKind.CELL:
            if c.classification is OverlayClass.APPLY:
                raise BuildError(f"{oid}: an approved correction targets a cell that no curated record carries")
            b.cell(t.file, t.row, t.field, disc=t.row.get("field"))
            b.effects[oid] = "EVIDENCE_ONLY_NOT_IN_CURATED_RECORD"
        elif t.kind is TargetKind.RANGE and c.classification is OverlayClass.IGNORE:
            b._effect(oid, "NO_RELATIONSHIP_ASSERTED")
        elif t.kind is TargetKind.SEQUENCE and c.row.status is OverlayStatus.SOURCE_NUMBERING_GAP:
            b._effect(oid, "FLAG_ATTACHED")
            b._flag(c.row.qp_code, QualityFlagCode.NUMBERING_GAP, Severity.INFO,
                    f"The printed S.No. sequence is {c.row.source_value} (a gap, no row missing).", [oid])
        else:
            raise BuildError(f"{oid}: not consumed by the build")
    # IGNORE (NO_OFFICIAL_RELATIONSHIP, OV-033) is recorded only: the build never creates a claim target, so every
    # generated claim has resolved_target = null and is DISPLAY_ONLY (ARCHITECTURE sections 9.2 and 11). The overlay's
    # own NOT_USED describes the absent relationship, not the text of the claims it points at.

    # Conflict / lead / NCO flags
    for g in cfg.conflict_groups:
        qp = plan.get(g.overlays[0]).row.qp_code
        b._flag(qp, QualityFlagCode.SOURCE_CONFLICT, Severity.WARNING,
                f"Unresolved source conflict ({g.subject.field}); no value is selected.", [f"conflict:{g.id}"])
    leads = []
    mrow = {r["item_id"]: r for r in manifest}
    for lead in cfg.open_leads:
        src = b.sources.docs.get(make_id(IdKind.SRC, lead.source_item))
        if src is None or src.has_local_file:
            raise BuildError(f"{lead.id}: source {lead.source_item} is now available; the lead needs a decision")
        b._flag(lead.qualification, QualityFlagCode.SOURCE_UNAVAILABLE, Severity.CAUTION,
                f"{lead.subject}: the comparison source {lead.source_item} is unavailable ({src.validation_status.value}); "
                "the QF hours are used and the lead stays open.", [src.id])
        leads.append({"id": lead.id, "status": lead.status, "qualification": make_id(IdKind.QUAL, lead.qualification),
                      "subject": lead.subject, "source": src.id, "manifest_status": src.validation_status.value,
                      "reference": lead.reference})
    for o in occupations:
        if o["title_verification"] == "NOT_FOUND":
            for qp, q in quals.items():
                if q["nco_codes"][0]["value"] == o["nco_code"]:
                    b._flag(qp, QualityFlagCode.NCO_TITLE_NOT_FOUND, Severity.CAUTION,
                            f"NCO title for {o['nco_code']} was not found in the searched sources; none is shown.", [o["id"]])

    qual_models: list[Qualification] = []
    try:
        for qp, data in quals.items():
            data["quality_flags"] = [f.model_dump(mode="json") for f in b.flags_by_qp[qp]]
            qual_models.append(Qualification.model_validate(data))
        for data in b.catalogue_only(set(cfg.pilot_qualifications), cfg.catalogue_source_item):
            qual_models.append(Qualification.model_validate(data))
        nos_models = [NosUnit.model_validate(u) for u in units.values()]
    except ValidationError as exc:
        raise BuildError(f"model validation failed: {' '.join(str(exc).split())}") from None

    index = SlugIndex()
    for ident in [q.id for q in qual_models] + [n.id for n in nos_models] + [o["id"] for o in occupations] + \
            list(b.sources.docs) + list(b.book.items):
        index.add(ident)  # a slug collision raises SlugCollisionError

    outputs = {
        "qualifications.json": sorted((q.model_dump(mode="json") for q in qual_models), key=lambda x: x["id"]),
        "nos_units.json": sorted((n.model_dump(mode="json") for n in nos_models), key=lambda x: x["id"]),
        "occupations.json": sorted(occupations, key=lambda x: x["id"]),
        "sources.json": [b.sources.docs[k].model_dump(mode="json") for k in sorted(b.sources.docs)],
        "evidence.json": [b.book.items[k].model_dump(mode="json") for k in sorted(b.book.items)],
        "conflicts.json": [c.model_dump(mode="json") for c in conflicts],
        "eligibility_source_rows.json": sorted((e.model_dump(mode="json") for e in elig), key=lambda x: x["id"]),
    }
    check_references(outputs)
    hook("validated")

    # ---- identity ----
    data_root = settings.data_root.resolve()

    def rel(p: Path) -> str:
        try:
            return p.resolve().relative_to(data_root).as_posix()
        except ValueError:
            return p.resolve().as_posix()

    consumed = [manifest_csv, validation_json, overlay_csv, catalogue_csv] + [extracted / f"{n}.csv" for n in TABLES]
    input_files = {rel(p): sha256_file(p) for p in consumed}
    sources_sha = {f.item_id: f.expected_sha256 for f in report.files if f.status == "MATCH"}
    approvals_digest = plan.approvals_digest
    ident = {"input_files": input_files, "source_files": sources_sha, "approvals_digest": approvals_digest,
             "curation_code_version": CURATION_CODE_VERSION, "config_digest": cfg_digest}
    build_id = "cb-" + hashlib.sha256(canonical_json(ident)).hexdigest()[:12]
    make_id(IdKind.CB, build_id[3:])

    effects = {c.row.overlay_id: {"classification": c.classification.value, "effect": b.effects[c.row.overlay_id]}
               for c in plan.rows}
    counts = plan.counts()
    manifest_out = {
        "status": "READY", "data_build_id": build_id,
        "built_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "curation_code_version": CURATION_CODE_VERSION, "config_digest": cfg_digest,
        "inputs": {"raw_run_id": raw_root.name, "extraction_run_id": extracted.name, "overlay_audit_id": audit.name,
                   "approvals_digest": approvals_digest},
        "input_files": input_files, "source_files": sources_sha,
        "unverified_inputs": [rel(validation_json)],
        "verified_derived_inputs": [rel(catalogue_csv)],
        "overlays": {"applied": plan.ids(OverlayClass.APPLY), "pending": plan.ids(OverlayClass.PENDING),
                     "display_only": counts["DISPLAY"]},
        "overlay_classification_counts": counts,
        "overlay_engine_use_counts": dict(sorted(Counter(c.row.engine_use.value for c in plan.rows).items())),
        "overlay_effects": effects,
        "overlay_definitions": {
            "applied": "rows classified APPLY: an approved PROPOSED_* row whose effect was written to a curated record",
            "pending": "rows classified PENDING: unapproved PROPOSED_* rows; no value changed",
            "display_only": "rows classified DISPLAY (by overlay status). This is NOT the number of rows whose "
                            "engine_use is DISPLAY_ONLY; see overlay_engine_use_counts",
        },
        "counts": {"qualifications_curated": sum(q.coverage.value == "CURATED" for q in qual_models),
                   "qualifications_catalogue_only": sum(q.coverage.value == "CATALOGUE_ONLY" for q in qual_models),
                   "nos_units": len(nos_models), "occupations": len(occupations),
                   "eligibility_rows": sum(e.kind is SourceRowKind.ELIGIBILITY_ROW for e in elig),
                   "age_rows": sum(e.kind is SourceRowKind.AGE_9C for e in elig), "conflicts_open": len(conflicts)},
        "open_leads": leads,
        "sources_unavailable": [
            {"manifest_item_id": d.manifest_item_id, "title": d.title,
             "reason": " ".join(x for x in (mrow[d.manifest_item_id].get("http_status", ""),
                                            d.validation_status.value) if x)}
            for d in b.sources.docs.values() if not d.has_local_file and d.manifest_item_id in mrow
            and d.validation_status.value in ("FAIL_HTTP", "NOT_FOUND")],
        "integrity": {"local_files_matched": report.local_files_matched, "no_local_file": report.no_local_file},
    }

    # ---- stage, re-hash, install ----
    out_root.mkdir(parents=True, exist_ok=True)
    stage = out_root / f".staging-{build_id}-{os.getpid()}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    try:
        blobs = {name: canonical_json(outputs[name]) for name in OUTPUT_FILES}
        for name, blob in blobs.items():
            (stage / name).write_bytes(blob)
        manifest_out["output_files"] = {n: hashlib.sha256(bl).hexdigest() for n, bl in sorted(blobs.items())}
        hook("staged")
        check_references({n: json.loads((stage / n).read_text(encoding="utf-8")) for n in OUTPUT_FILES})
        changed = diff_snapshots(before, snapshot(guard_roots, guard_files))
        if changed:
            raise BuildError("inputs changed during the build: " + "; ".join(changed[:5]))
        (stage / MANIFEST_OUT).write_bytes(canonical_json(manifest_out))  # last: its presence marks a complete build
        final = out_root / build_id
        hook("installing")
        if final.exists():
            if not (final / MANIFEST_OUT).is_file():
                raise BuildError(f"{final} exists but is not a complete build; remove it manually")
            same = all((final / n).read_bytes() == blobs[n] for n in OUTPUT_FILES)
            if not same:
                raise BuildError(f"{final} exists with different content for the same data_build_id")
            shutil.rmtree(stage)
            existing = json.loads((final / MANIFEST_OUT).read_text(encoding="utf-8"))
            return BuildResult(build_id, final, existing, reused=True)
        os.replace(stage, final)
        return BuildResult(build_id, final, manifest_out)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def check_references(outputs: dict[str, list]) -> None:
    """Referential integrity of the dumped collections (model validation covers format and local consistency)."""
    ev = {e["id"]: e for e in outputs.get("evidence.json", [])}
    src = {s["id"]: s for s in outputs.get("sources.json", [])}
    conf = {c["id"] for c in outputs.get("conflicts.json", [])}
    quals = {q["id"] for q in outputs.get("qualifications.json", [])}
    nos = {n["id"] for n in outputs.get("nos_units.json", [])}
    bad: list[str] = []

    def walk(node, where: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("evidence_id", "source_evidence_id") and v is not None and v not in ev:
                    bad.append(f"{where}: unknown {k} {v}")
                if k == "conflict_id" and v is not None and v not in conf:
                    bad.append(f"{where}: unknown conflict_id {v}")
                if k == "derived_from":
                    bad.extend(f"{where}: unknown derived_from {x}" for x in v if x not in ev)
                walk(v, where)
        elif isinstance(node, list):
            for x in node:
                walk(x, where)

    for name, data in outputs.items():
        walk(data, name)
    for e in ev.values():
        if e["evidence_class"] == "OFFICIAL":
            s = src.get(e["source_id"])
            if s is None or s["sha256"] != e["source_sha256"]:
                bad.append(f"{e['id']}: source {e['source_id']} unknown or hash differs from the SourceDocument")
    for q in outputs.get("qualifications.json", []):
        for m in q["nos_memberships"]:
            if m["nos_id"] and m["nos_id"] not in nos:
                bad.append(f"{q['id']}: unknown {m['nos_id']}")
    for c in outputs.get("conflicts.json", []):
        if c["subject"]["entity_id"].startswith("qual:") and c["subject"]["entity_id"] not in quals:
            bad.append(f"{c['id']}: unknown subject {c['subject']['entity_id']}")
    for r in outputs.get("eligibility_source_rows.json", []):
        if r["qualification_id"] not in quals:
            bad.append(f"{r['id']}: unknown qualification")
    if bad:
        raise BuildError("reference check failed: " + "; ".join(bad[:8]))
