"""Eligibility rule structure (ARCHITECTURE §9.2, §11).

These are the *stored* rule shapes. Evaluating them against a profile is the engine's job (Phase 3). The component
types deliberately include nothing for equivalence, exemption, RPL or reduced hours: no source defines them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, StringConstraints, model_validator

from .base import SNo, SchemaModel
from .evidence import EngineUse, QualityFlag
from .ids import EvidenceId, OverlayId, RuleId, split_id


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
