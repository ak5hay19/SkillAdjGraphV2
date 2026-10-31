"""Evidence classes, value statuses, ``Valued`` and ``Evidence`` (ARCHITECTURE §9.2 and §10.1, API_SPEC §2).

The provenance rules live here, so that no model can hold a factual value that hides where it came from.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import model_validator

from .base import Credits, SchemaModel
from .ids import ConflictId, DecisionRef, EvidenceId, OverlayId, Sha256Hex, SourceId


class EvidenceClass(StrEnum):
    OFFICIAL = "OFFICIAL"
    RULE_DERIVED = "RULE_DERIVED"
    DECLARED = "DECLARED"
    INFERENCE = "INFERENCE"
    HYPOTHETICAL = "HYPOTHETICAL"
    CONFIG = "CONFIG"


class ValueStatus(StrEnum):
    TRANSCRIBED = "TRANSCRIBED"
    PARSED_UNCERTAIN = "PARSED_UNCERTAIN"
    UNRESOLVED = "UNRESOLVED"
    CORROBORATED = "CORROBORATED"
    CONFIRMED_BY_GEOMETRY = "CONFIRMED_BY_GEOMETRY"
    CORRECTION_APPLIED = "CORRECTION_APPLIED"


class EngineUse(StrEnum):
    SAFE_HARD_RULE = "SAFE_HARD_RULE"
    SAFE_WITH_CONSTRAINT = "SAFE_WITH_CONSTRAINT"
    SAFE_HOURS = "SAFE_HOURS"
    CONDITIONAL_ON_DECLARED_RELEVANCE = "CONDITIONAL_ON_DECLARED_RELEVANCE"
    CONDITIONAL_ON_DECLARED_RELEVANCE_LEVEL_CONFIG = "CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG"
    UNKNOWN = "UNKNOWN"
    DISPLAY_ONLY = "DISPLAY_ONLY"
    NOT_USED = "NOT_USED"


class QualityFlagCode(StrEnum):
    UNCERTAIN_EXTRACTION = "UNCERTAIN_EXTRACTION"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    NCO_TITLE_NOT_FOUND = "NCO_TITLE_NOT_FOUND"
    TITLE_VARIANT = "TITLE_VARIANT"
    SECONDARY_COPY_BINARY_DIFFERS = "SECONDARY_COPY_BINARY_DIFFERS"
    OVERLAY_PENDING_APPROVAL = "OVERLAY_PENDING_APPROVAL"
    NUMBERING_GAP = "NUMBERING_GAP"
    SEMANTIC_AMBIGUITY = "SEMANTIC_AMBIGUITY"
    INFERENCE_EXPERIMENTAL = "INFERENCE_EXPERIMENTAL"
    HYPOTHETICAL_SCENARIO = "HYPOTHETICAL_SCENARIO"
    LICENCE_UNCONFIRMED = "LICENCE_UNCONFIRMED"
    NO_OFFICIAL_REDUCTION_SOURCE = "NO_OFFICIAL_REDUCTION_SOURCE"
    DEPENDS_ON_DECLARATION = "DEPENDS_ON_DECLARATION"
    DEPENDS_ON_CONFIG = "DEPENDS_ON_CONFIG"
    SMALL_SAMPLE = "SMALL_SAMPLE"
    UNCERTAINTY_NOT_ESTIMABLE = "UNCERTAINTY_NOT_ESTIMABLE"
    AGGREGATION_CONTEXT_ONLY = "AGGREGATION_CONTEXT_ONLY"


class Severity(StrEnum):
    INFO = "INFO"
    CAUTION = "CAUTION"
    WARNING = "WARNING"


class QualityFlag(SchemaModel):
    code: QualityFlagCode
    severity: Severity
    message: str
    refs: list[str] = []  # conflict, overlay or evidence ids


# Classes whose values come from a stored evidence record. DECLARED / CONFIG / HYPOTHETICAL are request-scoped.
STORED_CLASSES = frozenset({EvidenceClass.OFFICIAL, EvidenceClass.RULE_DERIVED, EvidenceClass.INFERENCE})
# A value with an open source conflict may not be used by the engine as a safe input (ARCHITECTURE §11.3, §11.4).
SAFE_USES = frozenset(
    {
        EngineUse.SAFE_HARD_RULE,
        EngineUse.SAFE_WITH_CONSTRAINT,
        EngineUse.SAFE_HOURS,
        EngineUse.CONDITIONAL_ON_DECLARED_RELEVANCE,
        EngineUse.CONDITIONAL_ON_DECLARED_RELEVANCE_LEVEL_CONFIG,
    }
)


class Evidence(SchemaModel):
    """Where a value or a rule row comes from. The meaning of each field depends on ``evidence_class``."""

    id: EvidenceId
    evidence_class: EvidenceClass
    source_id: SourceId | None = None  # OFFICIAL only
    source_sha256: Sha256Hex | None = None  # OFFICIAL only; must equal the SourceDocument hash (checked by the build)
    page: str | None = None  # as printed in the extraction, e.g. "3-4"
    location: str | None = None  # e.g. "QF item 13"
    method: str | None = None
    value_status: ValueStatus | None = None
    overlay_ids: list[OverlayId] = []
    decision_refs: list[DecisionRef] = []
    derived_from: list[EvidenceId] = []  # RULE_DERIVED / INFERENCE only
    declared_field: str | None = None  # DECLARED only
    config_key: str | None = None  # CONFIG only
    note: str | None = None

    @model_validator(mode="after")
    def _check_class_fields(self) -> Evidence:
        cls = self.evidence_class
        official = cls is EvidenceClass.OFFICIAL
        derives = cls in (EvidenceClass.RULE_DERIVED, EvidenceClass.INFERENCE)
        if official:
            if self.source_id is None or self.source_sha256 is None:
                raise ValueError("OFFICIAL evidence requires source_id and source_sha256")
            if not (self.page or self.location):
                raise ValueError("OFFICIAL evidence requires a page or a location")
        elif self.source_id or self.source_sha256 or self.page:
            raise ValueError(f"{cls.value} evidence must not carry source_id, source_sha256 or page")
        if derives:
            if not self.derived_from:
                raise ValueError(f"{cls.value} evidence requires derived_from")
            if self.id in self.derived_from or len(set(self.derived_from)) != len(self.derived_from):
                raise ValueError("derived_from must list distinct evidence ids other than this record")
        elif self.derived_from:
            raise ValueError("derived_from is only for RULE_DERIVED and INFERENCE evidence")
        if cls is EvidenceClass.DECLARED:
            if not self.declared_field:
                raise ValueError("DECLARED evidence requires declared_field")
        elif self.declared_field:
            raise ValueError("declared_field is only for DECLARED evidence")
        if cls is EvidenceClass.CONFIG:
            if not self.config_key:
                raise ValueError("CONFIG evidence requires config_key")
        elif self.config_key:
            raise ValueError("config_key is only for CONFIG evidence")
        return self


T = TypeVar("T")


class Valued(SchemaModel, Generic[T]):
    """A factual value together with its provenance (API_SPEC §2.2).

    ``value`` is required but may be null (the source printed nothing); it is never silently defaulted.
    """

    value: T | None
    evidence_class: EvidenceClass
    evidence_id: EvidenceId | None = None
    value_status: ValueStatus | None = None
    engine_use: EngineUse | None = None
    conflict_id: ConflictId | None = None
    # Only for CORRECTION_APPLIED (ARCHITECTURE §7 principle 2): the extraction value that the applied overlay value
    # replaced, and the evidence for it. ``source_value = ""`` (the source printed nothing) differs from None (absent).
    source_value: str | None = None
    source_evidence_id: EvidenceId | None = None

    @model_validator(mode="after")
    def _check_provenance(self) -> Valued[T]:
        corrected = self.value_status is ValueStatus.CORRECTION_APPLIED
        has_source = self.source_value is not None or self.source_evidence_id is not None
        if has_source and not corrected:
            raise ValueError("source_value and source_evidence_id are only for value_status CORRECTION_APPLIED")
        if corrected and (self.source_value is None or self.source_evidence_id is None):
            raise ValueError("a CORRECTION_APPLIED value requires source_value and source_evidence_id")
        if corrected and self.source_evidence_id == self.evidence_id:
            raise ValueError("source_evidence_id must differ from evidence_id")
        if self.evidence_class in STORED_CLASSES and self.evidence_id is None:
            raise ValueError(f"a {self.evidence_class.value} value requires evidence_id")
        if self.evidence_class is EvidenceClass.OFFICIAL and self.value_status is None:
            raise ValueError("an OFFICIAL value requires value_status")
        if self.conflict_id is not None and self.engine_use in SAFE_USES:
            raise ValueError("a value with an open conflict cannot have a safe engine_use")
        return self


class OfficialValued(Valued[T], Generic[T]):
    """A stored source-of-truth fact: it must be OFFICIAL, i.e. copied from a source and cited.

    Qualification hours, levels, ages, credits, NCO codes and NOS-membership values are all of this kind. The
    specifications give no stored qualification fact of any other class: RULE_DERIVED totals are computed per path
    (ARCHITECTURE §12), DECLARED / CONFIG / HYPOTHETICAL values are request-scoped, and INFERENCE is never a fact.
    A new class for any of these fields needs a deliberate, documented decision. The general ``Valued`` stays
    open to every class for the contexts that need it.
    """

    @model_validator(mode="after")
    def _official_only(self) -> OfficialValued[T]:
        if self.evidence_class is not EvidenceClass.OFFICIAL:
            raise ValueError(f"a stored source fact must be OFFICIAL, not {self.evidence_class.value}")
        return self


class DisplayValued(OfficialValued[T], Generic[T]):
    """An official value that is shown but never computed with (versions: ARCHITECTURE §9.2 'display only')."""

    @model_validator(mode="after")
    def _display_only(self) -> DisplayValued[T]:
        if self.engine_use is not EngineUse.DISPLAY_ONLY:
            raise ValueError("engine_use must be DISPLAY_ONLY")
        return self


class CreditValue(OfficialValued[Credits]):
    """NSQF credits. They are displayed only: ``engine_use`` is always NOT_USED and they are never hours (decision D1)."""

    @model_validator(mode="after")
    def _credits_not_used(self) -> CreditValue:
        if self.engine_use is not EngineUse.NOT_USED:
            raise ValueError("credits must have engine_use NOT_USED")
        return self
