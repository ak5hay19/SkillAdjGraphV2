"""Eligibility rule structure (ARCHITECTURE §9.2, §11).

These are the *stored* rule shapes. Evaluating them against a profile is the engine's job (Phase 3). The component
types deliberately include nothing for equivalence, exemption, RPL or reduced hours: no source defines them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, StringConstraints, model_validator

from .base import MinAge, SchemaModel, SNo
from .evidence import SAFE_USES, EngineUse, OfficialValued, QualityFlag, ValueStatus
from .ids import EvidenceId, IdKind, OverlayId, QualificationId, RuleId, make_id, split_id


class Verdict(StrEnum):
    """Listed in the order of API_SPEC §2.1; the lattice order is ``rank`` (NOT_MET < UNKNOWN < CONDITIONAL < MET)."""

    MET = "MET"
    NOT_MET = "NOT_MET"
    UNKNOWN = "UNKNOWN"
    CONDITIONAL = "CONDITIONAL"

    @property
    def rank(self) -> int:
        return _VERDICT_RANK[self]


_VERDICT_RANK = {Verdict.NOT_MET: 0, Verdict.UNKNOWN: 1, Verdict.CONDITIONAL: 2, Verdict.MET: 3}


class ComponentType(StrEnum):
    AGE_MIN = "AGE_MIN"
    SCHOOL_GRADE_MIN = "SCHOOL_GRADE_MIN"
    NAMED_CREDENTIAL = "NAMED_CREDENTIAL"
    PRIOR_NSQF_LEVEL = "PRIOR_NSQF_LEVEL"
    EXPERIENCE_MIN_YEARS = "EXPERIENCE_MIN_YEARS"
    UNMODELLED = "UNMODELLED"


class UnknownReasonCode(StrEnum):
    INPUT_NOT_DECLARED = "INPUT_NOT_DECLARED"
    RELEVANCE_NOT_DECLARED = "RELEVANCE_NOT_DECLARED"
    CONFIG_UNSET = "CONFIG_UNSET"
    EQUIVALENCE_UNDEFINED = "EQUIVALENCE_UNDEFINED"
    CREDENTIAL_ORDER_UNDEFINED = "CREDENTIAL_ORDER_UNDEFINED"
    ENROLMENT_NOT_MODELLED = "ENROLMENT_NOT_MODELLED"
    LITERACY_NOT_MODELLED = "LITERACY_NOT_MODELLED"
    NTC_NAC_CITS_NOT_MODELLED = "NTC_NAC_CITS_NOT_MODELLED"
    DIPLOMA_YEAR_NOT_MODELLED = "DIPLOMA_YEAR_NOT_MODELLED"
    REVIEW_FLAG = "REVIEW_FLAG"
    UNCERTAIN_EXTRACTION = "UNCERTAIN_EXTRACTION"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    OVERLAY_NOT_APPROVED = "OVERLAY_NOT_APPROVED"
    # A parsed requirement (the cell is not uncertain) whose engine_use is UNKNOWN: the audit has assigned it no
    # safe use and nothing else substantiates evaluating it. Resolved only by a new audit decision on that cell.
    ENGINE_USE_UNDECIDED = "ENGINE_USE_UNDECIDED"


# Parameters that ARCHITECTURE §11.2 and API_SPEC name for a component type. Other keys are not restricted here.
_REQUIRED_PARAMS = {
    ComponentType.AGE_MIN: "min_age",
    ComponentType.PRIOR_NSQF_LEVEL: "level",
    ComponentType.EXPERIENCE_MIN_YEARS: "years",
}
_RELEVANCE_TYPES = {ComponentType.PRIOR_NSQF_LEVEL, ComponentType.EXPERIENCE_MIN_YEARS}
ParamValue = StrictStr | StrictBool | StrictInt | StrictFloat | None


class Component(SchemaModel):
    type: ComponentType
    params: dict[str, ParamValue] = {}
    requires_relevance: StrictBool = False
    or_equivalent: StrictBool = False
    evidence_id: EvidenceId
    safe: StrictBool
    unknown_reason: UnknownReasonCode | None = None

    @model_validator(mode="after")
    def _check(self) -> Component:
        key = _REQUIRED_PARAMS.get(self.type)
        if key is not None:
            value = self.params.get(key)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{self.type.value} requires a numeric params[{key!r}]")
        if self.requires_relevance and self.type not in _RELEVANCE_TYPES:
            raise ValueError("requires_relevance applies only to PRIOR_NSQF_LEVEL and EXPERIENCE_MIN_YEARS")
        if self.type is ComponentType.UNMODELLED:
            if self.safe:
                raise ValueError("an UNMODELLED component is never safe")
            if self.unknown_reason is None:
                raise ValueError("an UNMODELLED component requires unknown_reason")
        return self


class _Rule(SchemaModel):
    id: RuleId
    raw_text: Annotated[str, StringConstraints(min_length=1)]  # verbatim from the source, quirks included
    evidence_id: EvidenceId  # evidence for raw_text
    components: Annotated[list[Component], Field(min_length=1)]
    engine_use: EngineUse
    overlay_ids: list[OverlayId] = []
    flags: list[QualityFlag] = []

    @property
    def qualification_code(self) -> str:
        return split_id(self.id)[1].rsplit("/", 1)[0]


class AgeRule(_Rule):
    @model_validator(mode="after")
    def _check(self) -> AgeRule:
        if not self.id.endswith("/AGE"):
            raise ValueError("an age rule id must end in /AGE")
        if [c.type for c in self.components] != [ComponentType.AGE_MIN]:
            raise ValueError("an age rule has exactly one AGE_MIN component")
        return self


class EligibilityRow(_Rule):
    s_no: SNo  # the printed S.No.

    @model_validator(mode="after")
    def _check(self) -> EligibilityRow:
        if split_id(self.id)[1].rsplit("/", 1)[1] != f"E{self.s_no}":
            raise ValueError("a row id must be rule:<code>/E<s_no>")
        return self


class EligibilitySpec(SchemaModel):
    """Semantics: AND(age, OR(rows))."""

    age_rule: AgeRule
    rows: list[EligibilityRow]  # strictly ascending s_no

    @model_validator(mode="after")
    def _check(self) -> EligibilitySpec:
        codes = {self.age_rule.qualification_code, *(r.qualification_code for r in self.rows)}
        if len(codes) != 1:
            raise ValueError("all rules of one specification belong to one qualification")
        numbers = [r.s_no for r in self.rows]
        if numbers != sorted(set(numbers)):
            raise ValueError("rows must have distinct, ascending s_no")
        return self


class SourceRowKind(StrEnum):
    ELIGIBILITY_ROW = "ELIGIBILITY_ROW"
    AGE_9C = "AGE_9C"


# A text value in one of these states is not substantiated; only these statuses lift an uncertain extraction.
_UNCERTAIN = frozenset({ValueStatus.PARSED_UNCERTAIN, ValueStatus.UNRESOLVED})
_SUBSTANTIATED = frozenset({ValueStatus.CONFIRMED_BY_GEOMETRY, ValueStatus.CORROBORATED, ValueStatus.CORRECTION_APPLIED})


class AuditHint(SchemaModel):
    """An overlay row that states an ``engine_use`` for a *different* field than the row's own row-level component.

    It is audit metadata only: it never sets or raises the effective ``engine_use`` of the row or of any field.
    """

    overlay_id: OverlayId
    field: StrictStr
    engine_use: EngineUse
    engine_constraint: StrictStr | None = None


class EligibilitySourceRow(SchemaModel):
    """An eligibility row as extracted, with overlay-resolved fields, before P1.5 structures it into components.

    It is the pre-structuring record of ARCHITECTURE §9.2's ``EligibilityRow``: the same ``rule:`` id, the verbatim
    text and the provenance, but no components (none are invented). Each text field keeps the extraction value (a
    corrected field carries ``source_value``) and its own ``value_status`` and ``engine_use``: a correction of one
    field never changes the status or safety of another.

    ``engine_use`` is the effective row-level use and is never safer than the row's own row-level component
    (``raw_row_text`` of an eligibility row, ``min_age`` of the age row): a safe use is allowed only if that component
    carries the same use. A decision the overlay states about another field (for example the experience cell of
    Q2301 row 1) is kept in ``audit_hints`` and authorizes nothing.

    A computing (safe or conditional) row-level use also requires substantiation: no required text value may be
    ``PARSED_UNCERTAIN`` or ``UNRESOLVED``, and if the extraction status of the row is uncertain, the row-level
    component must have been confirmed by geometry, corroborated or corrected. ``audit_hints`` are never evidence.

    ``engine_constraint`` is the audit's wording for the row-level decision, kept verbatim and separate from evidence
    and classification. It is documentation for P1.5, not executable logic, and its presence never changes
    ``engine_use``; ``SAFE_WITH_CONSTRAINT`` requires it because that use is valid only within the constraint.
    """

    id: RuleId
    qualification_id: QualificationId
    kind: SourceRowKind
    s_no: SNo | None = None
    raw_academic_or_skill: OfficialValued[str] | None = None
    raw_required_experience: OfficialValued[str] | None = None
    raw_row_text: OfficialValued[str] | None = None
    min_age: OfficialValued[MinAge] | None = None
    extraction_status: ValueStatus  # the extraction's row status, never cleared by a field-level overlay
    engine_use: EngineUse
    engine_constraint: Annotated[str, StringConstraints(min_length=1)] | None = None
    overlay_ids: list[OverlayId] = []
    pending_overlay_ids: list[OverlayId] = []
    audit_hints: list[AuditHint] = []
    flags: list[QualityFlag] = []
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> EligibilitySourceRow:
        code, tail = split_id(self.id)[1].rsplit("/", 1)
        if make_id(IdKind.QUAL, code) != self.qualification_id:
            raise ValueError("id must belong to the qualification")
        if self.kind is SourceRowKind.AGE_9C:
            if tail != "AGE" or self.s_no is not None or self.min_age is None:
                raise ValueError("an AGE_9C row has id rule:<code>/AGE, no S.No. and a min_age")
        else:
            if self.s_no is None or tail != f"E{self.s_no}" or self.min_age is not None:
                raise ValueError("an eligibility row has id rule:<code>/E<s_no>, an S.No. and no min_age")
            if self.raw_row_text is None:
                raise ValueError("an eligibility row requires raw_row_text")
        component = self.min_age if self.kind is SourceRowKind.AGE_9C else self.raw_row_text
        if self.engine_use in SAFE_USES and component.engine_use is not self.engine_use:
            raise ValueError("a row-level engine_use cannot be safer than the row's own row-level component")
        if self.engine_use in SAFE_USES:
            if self.extraction_status in _UNCERTAIN and component.value_status not in _SUBSTANTIATED:
                raise ValueError(
                    "a computing row-level engine_use requires a substantiated row: the extraction status is "
                    f"{self.extraction_status.value} and the row-level component is only {component.value_status.value}"
                )
            for name in ("raw_academic_or_skill", "raw_required_experience", "raw_row_text", "min_age"):
                cell = getattr(self, name)
                if cell is not None and cell.value_status in _UNCERTAIN:
                    raise ValueError(f"a computing row-level engine_use is refused while {name} is {cell.value_status.value}")
        if self.engine_use is EngineUse.SAFE_WITH_CONSTRAINT and not self.engine_constraint:
            raise ValueError("SAFE_WITH_CONSTRAINT requires the engine_constraint it is valid within")
        return self
