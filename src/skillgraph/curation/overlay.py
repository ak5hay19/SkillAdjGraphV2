"""P1.3 overlay approval mechanism (ARCHITECTURE §3 principle 2, §7, §11.4; Q-2).

The audit overlay proposes; only the user's explicit approval applies a proposal. This module reads the overlay and
``config/overlay_approvals.yaml`` and classifies every overlay row as APPLY, INTERPRET, DISPLAY, PENDING or IGNORE.
It never writes, and never modifies a source value: a resolved field keeps the extraction's ``source_value`` and
carries any applied overlay value beside it.

Classification depends on the overlay ``status`` and, for the two PROPOSED_* statuses only, on the approval:

=============================  ==========================  =====================================================
status                         without approval            with approval
=============================  ==========================  =====================================================
PROPOSED_CORRECTION            PENDING                     APPLY (the value is replaced, source value kept)
PROPOSED_REPRESENTATION        PENDING                     APPLY (a structure is recorded; no value replaced)
INTERPRETATION_DECIDED,        INTERPRET                   approval is refused: not a proposal
UNRESOLVED, REVIEW_FLAG,
CONFIRMED_BY_GEOMETRY,
CORROBORATED
SUPPORTING_EVIDENCE_ONLY,      DISPLAY                     approval is refused: not a proposal
PARSED_UNCERTAIN_RETAINED,
SOURCE_NUMBERING_GAP,
UNRESOLVED_SOURCE_CONFLICT
NO_OFFICIAL_RELATIONSHIP       IGNORE                      approval is refused: not a proposal
=============================  ==========================  =====================================================

An unknown status is an error, never a guess. The mapping of the non-proposal statuses is this module's reading of
AUDIT_NOTE §4 (they change no value); the engine behaviour stays with ``engine_use`` (ARCHITECTURE §11.4).
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
from collections import Counter
from collections.abc import Iterable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from skillgraph.model.evidence import EngineUse, QualityFlagCode, ValueStatus
from skillgraph.model.ids import OverlayId

APPROVALS_PATH = Path("config/overlay_approvals.yaml")

OVERLAY_COLUMNS = (
    "overlay_id",
    "category",
    "qp_code",
    "target_file",
    "target_row_key",
    "target_field",
    "source_value",
    "overlay_value",
    "status",
    "engine_use",
)
_NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OverlayError(Exception):
    """The overlay or the approvals file is malformed, or an approval is invalid. The build must stop."""


class OverlayStatus(StrEnum):
    """The twelve statuses of AUDIT_NOTE §4."""

    PROPOSED_CORRECTION = "PROPOSED_CORRECTION"
    PROPOSED_REPRESENTATION = "PROPOSED_REPRESENTATION"
    CONFIRMED_BY_GEOMETRY = "CONFIRMED_BY_GEOMETRY"
    INTERPRETATION_DECIDED = "INTERPRETATION_DECIDED"
    UNRESOLVED = "UNRESOLVED"
    UNRESOLVED_SOURCE_CONFLICT = "UNRESOLVED_SOURCE_CONFLICT"
    REVIEW_FLAG = "REVIEW_FLAG"
    SOURCE_NUMBERING_GAP = "SOURCE_NUMBERING_GAP"
    PARSED_UNCERTAIN_RETAINED = "PARSED_UNCERTAIN_RETAINED"
    CORROBORATED = "CORROBORATED"
    SUPPORTING_EVIDENCE_ONLY = "SUPPORTING_EVIDENCE_ONLY"
    NO_OFFICIAL_RELATIONSHIP = "NO_OFFICIAL_RELATIONSHIP"


class OverlayClass(StrEnum):
    APPLY = "APPLY"
    INTERPRET = "INTERPRET"
    DISPLAY = "DISPLAY"
    PENDING = "PENDING"
    IGNORE = "IGNORE"


PROPOSALS = frozenset({OverlayStatus.PROPOSED_CORRECTION, OverlayStatus.PROPOSED_REPRESENTATION})
_UNAPPROVED_CLASS: dict[OverlayStatus, OverlayClass] = {
    OverlayStatus.PROPOSED_CORRECTION: OverlayClass.PENDING,
    OverlayStatus.PROPOSED_REPRESENTATION: OverlayClass.PENDING,
    OverlayStatus.INTERPRETATION_DECIDED: OverlayClass.INTERPRET,
    OverlayStatus.UNRESOLVED: OverlayClass.INTERPRET,
    OverlayStatus.REVIEW_FLAG: OverlayClass.INTERPRET,
    OverlayStatus.CONFIRMED_BY_GEOMETRY: OverlayClass.INTERPRET,
    OverlayStatus.CORROBORATED: OverlayClass.INTERPRET,
    OverlayStatus.SUPPORTING_EVIDENCE_ONLY: OverlayClass.DISPLAY,
    OverlayStatus.PARSED_UNCERTAIN_RETAINED: OverlayClass.DISPLAY,
    OverlayStatus.SOURCE_NUMBERING_GAP: OverlayClass.DISPLAY,
    OverlayStatus.UNRESOLVED_SOURCE_CONFLICT: OverlayClass.DISPLAY,
    OverlayStatus.NO_OFFICIAL_RELATIONSHIP: OverlayClass.IGNORE,
}
assert set(_UNAPPROVED_CLASS) == set(OverlayStatus)  # a new status must be classified deliberately


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OverlayRow(_Frozen):
    """The columns of ``corrections_overlay.csv`` that classification and application need."""

    overlay_id: OverlayId
    category: _NonEmpty
    qp_code: str
    target_file: _NonEmpty
    target_row_key: _NonEmpty
    target_field: _NonEmpty
    source_value: str
    overlay_value: str
    status: OverlayStatus
    engine_use: EngineUse


class Approval(_Frozen):
    overlay_id: OverlayId
    approved_by: _NonEmpty
    approved_on: dt.date
    note: str = ""


class ApprovalsFile(_Frozen):
    approved: tuple[Approval, ...]


class ClassifiedRow(_Frozen):
    row: OverlayRow
    classification: OverlayClass
    approval: Approval | None = None


class OverlayPlan(_Frozen):
    rows: tuple[ClassifiedRow, ...]
    approvals_digest: str  # "sha256:<hex>" of the approvals file bytes, or of the empty input if none was read

    def ids(self, classification: OverlayClass) -> list[str]:
        return [c.row.overlay_id for c in self.rows if c.classification is classification]

    def counts(self) -> dict[str, int]:
        n = Counter(c.classification.value for c in self.rows)
        return {k.value: n.get(k.value, 0) for k in OverlayClass}

    def get(self, overlay_id: str) -> ClassifiedRow:
        for c in self.rows:
            if c.row.overlay_id == overlay_id:
                return c
        raise KeyError(overlay_id)


class ResolvedField(_Frozen):
    """One curated field: the untouched source value plus any applied overlay value (ARCHITECTURE §3 principle 2)."""

    target_file: str
    target_row_key: str
    target_field: str
    source_value: str
    value: str
    value_status: ValueStatus | None  # the source status, or CORRECTION_APPLIED when an approved correction applies
    overlay_ids: tuple[str, ...]
    pending_overlay_ids: tuple[str, ...]
    quality_flags: tuple[QualityFlagCode, ...]


# ---- loading ---------------------------------------------------------------------------------------------------


def load_overlay(path: Path) -> list[OverlayRow]:
    """Parse the overlay CSV read-only. A missing file or column, a malformed row, an unknown status or ``engine_use``
    value, or a duplicate overlay_id raises ``OverlayError``."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in OVERLAY_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise OverlayError(f"{path.name}: missing column(s) {', '.join(missing)}")
            raw = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise OverlayError(f"cannot read overlay {path}: {exc}") from None
    if not raw:
        raise OverlayError(f"{path.name}: no overlay rows")
    rows: list[OverlayRow] = []
    for line, rec in enumerate(raw, start=2):
        # A short row leaves None values; that is malformed, not an empty string.
        if any(rec.get(c) is None for c in OVERLAY_COLUMNS) or None in rec:
            raise OverlayError(f"{path.name} line {line}: wrong number of columns")
        try:
            rows.append(OverlayRow(**{c: rec[c] for c in OVERLAY_COLUMNS}))
        except ValidationError as exc:
            raise OverlayError(f"{path.name} line {line}: {_errors(exc)}") from None
    dupes = sorted(k for k, n in Counter(r.overlay_id for r in rows).items() if n > 1)
    if dupes:
        raise OverlayError(f"{path.name}: duplicate overlay_id(s): {', '.join(dupes)}")
    return rows


def load_approvals(path: Path) -> tuple[list[Approval], str]:
    """Parse the approvals YAML read-only; returns the approvals and the digest of the file bytes.

    The file must be a mapping with exactly the key ``approved``, a list (``[]`` when nothing is approved). A missing
    file is an error: an absent approvals file must not be mistaken for "nothing approved" by a silent default.
    """
    try:
        data = path.read_bytes()
        parsed = yaml.safe_load(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise OverlayError(f"cannot read approvals file {path}: {exc}") from None
    except yaml.YAMLError as exc:
        raise OverlayError(f"approvals file is not valid YAML: {path}: {' '.join(str(exc).split())}") from None
    if not isinstance(parsed, dict):
        raise OverlayError(f"approvals file must contain a mapping with an 'approved' list: {path}")
    if not isinstance(parsed.get("approved"), list):
        raise OverlayError(f"approvals file must contain 'approved' as a list (use [] for none): {path}")
    try:
        approved = ApprovalsFile.model_validate(parsed).approved
    except ValidationError as exc:
        raise OverlayError(f"{path.name}: {_errors(exc)}") from None
    dupes = sorted(k for k, n in Counter(a.overlay_id for a in approved).items() if n > 1)
    if dupes:
        raise OverlayError(f"{path.name}: overlay_id approved more than once: {', '.join(dupes)}")
    return list(approved), "sha256:" + hashlib.sha256(data).hexdigest()


def _errors(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())


# ---- classification --------------------------------------------------------------------------------------------


def classify(
    rows: Sequence[OverlayRow], approvals: Iterable[Approval], approvals_digest: str = ""
) -> OverlayPlan:
    """Classify every row. An approval that names a missing overlay_id, or a row that is not a proposal, raises
    ``OverlayError`` (the build fails): approving something that cannot be approved is a mistake to surface."""
    by_id = {r.overlay_id: r for r in rows}
    approved: dict[str, Approval] = {}
    problems: list[str] = []
    for a in approvals:
        if a.overlay_id in approved:
            problems.append(f"{a.overlay_id} is approved more than once")
        elif a.overlay_id not in by_id:
            problems.append(f"{a.overlay_id} does not exist in the overlay")
        elif by_id[a.overlay_id].status not in PROPOSALS:
            problems.append(
                f"{a.overlay_id} has status {by_id[a.overlay_id].status.value}, which is not a proposal awaiting approval"
            )
        else:
            approved[a.overlay_id] = a
    if problems:
        raise OverlayError("invalid overlay approval(s): " + "; ".join(problems))
    out = []
    for r in rows:
        if r.overlay_id in approved:
            out.append(ClassifiedRow(row=r, classification=OverlayClass.APPLY, approval=approved[r.overlay_id]))
        else:
            out.append(ClassifiedRow(row=r, classification=_UNAPPROVED_CLASS[r.status]))
    return OverlayPlan(rows=tuple(out), approvals_digest=approvals_digest)


def load_plan(overlay_csv: Path, approvals_yaml: Path) -> OverlayPlan:
    """Read the overlay and the approvals and classify. Writes nothing."""
    rows = load_overlay(overlay_csv)
    approvals, digest = load_approvals(approvals_yaml)
    return classify(rows, approvals, digest)


# ---- application -----------------------------------------------------------------------------------------------


def resolve_field(
    plan: OverlayPlan,
    target_file: str,
    target_row_key: str,
    target_field: str,
    source_value: str,
    source_status: ValueStatus | None,
) -> ResolvedField:
    """The curated value of one extraction field.

    ``source_value`` is the extraction CSV's value and is always returned unchanged. Only an APPROVED
    PROPOSED_CORRECTION replaces ``value`` (status ``CORRECTION_APPLIED``). A pending proposal changes nothing and is
    reported in ``pending_overlay_ids`` with the ``OVERLAY_PENDING_APPROVAL`` flag. A representation (credit group)
    never replaces a value. If the overlay recorded a different ``source_value`` than the extraction holds, the overlay
    is stale for this data and ``OverlayError`` is raised.
    """
    value = source_value
    status = source_status
    applied: list[str] = []
    pending: list[str] = []
    for c in plan.rows:
        r = c.row
        if (r.target_file, r.target_row_key, r.target_field) != (target_file, target_row_key, target_field):
            continue
        if c.classification is OverlayClass.PENDING:
            pending.append(r.overlay_id)
        elif c.classification is not OverlayClass.APPLY:
            continue
        elif r.status is OverlayStatus.PROPOSED_CORRECTION:
            if r.source_value != source_value:
                raise OverlayError(
                    f"{r.overlay_id}: overlay source_value {r.source_value!r} differs from the extraction value "
                    f"{source_value!r} for {target_row_key} {target_field}; the overlay is stale"
                )
            if not r.overlay_value.strip():
                raise OverlayError(f"{r.overlay_id}: an approved correction has an empty overlay_value")
            if applied:
                raise OverlayError(
                    f"{r.overlay_id}: more than one approved correction targets {target_row_key} {target_field}"
                )
            value, status = r.overlay_value, ValueStatus.CORRECTION_APPLIED
            applied.append(r.overlay_id)
        else:  # approved PROPOSED_REPRESENTATION: recorded, never a value replacement
            applied.append(r.overlay_id)
    flags = (QualityFlagCode.OVERLAY_PENDING_APPROVAL,) if pending else ()
    return ResolvedField(
        target_file=target_file,
        target_row_key=target_row_key,
        target_field=target_field,
        source_value=source_value,
        value=value,
        value_status=status,
        overlay_ids=tuple(applied),
        pending_overlay_ids=tuple(pending),
        quality_flags=flags,
    )
