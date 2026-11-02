"""Qualifications, NOS units, memberships, modules, hours and progression claims (ARCHITECTURE §9.2, §12).

Hours are the official notional training hours of a full qualification (QF item 13). Credits are a different
quantity: ``CreditValue`` is the only credit type, it is always ``NOT_USED``, and no hours field accepts it.
There is deliberately no field for incremental or reduced retraining hours: no source defines one (§12).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import Hours, MinAge, NsqfLevel, SchemaModel, SNo
from .eligibility import EligibilitySpec
from .evidence import CreditValue, DisplayValued, EngineUse, EvidenceClass, OfficialValued, QualityFlag
from .ids import (
    ClaimId,
    EvidenceId,
    IdKind,
    ModuleId,
    NcoCode,
    NosCode,
    NosId,
    OverlayId,
    QualificationCode,
    QualificationId,
    make_id,
    slug_of,
    split_id,
)

Text = Annotated[str, StringConstraints(min_length=1)]


class Coverage(StrEnum):
    CURATED = "CURATED"
    CATALOGUE_ONLY = "CATALOGUE_ONLY"


class CoreOrNonCore(StrEnum):
    CORE = "Core"
    NON_CORE = "Non-Core"


class HoursBreakdown(SchemaModel):
    """Official notional hours. ``total`` is always present; the parts are null where a source gives only a total."""

    theory: OfficialValued[Hours] | None = None
    practical: OfficialValued[Hours] | None = None
    ojt_mandatory: OfficialValued[Hours] | None = None
    ojt_recommended: OfficialValued[Hours] | None = None
    total: OfficialValued[Hours]

    @property
    def is_complete(self) -> bool:
        return None not in (self.theory, self.practical, self.ojt_mandatory, self.ojt_recommended)

    @model_validator(mode="after")
    def _hours_are_not_credits(self) -> HoursBreakdown:
        for name in ("theory", "practical", "ojt_mandatory", "ojt_recommended", "total"):
            v = getattr(self, name)
            if v is not None and v.engine_use is EngineUse.NOT_USED:
                raise ValueError(f"{name}: hours are never NOT_USED (that is the credit treatment)")
        return self


class Titles(SchemaModel):
    """Titles as printed by each source. Differences are kept, never merged (DQ-05)."""

    qf: Text | None = None
    qp: Text | None = None
    catalogue: Text | None = None


class NosUnit(SchemaModel):
    """A NOS unit. Its level is per membership, so it has none here."""

    id: NosId
    code: NosCode
    titles_by_source: Annotated[dict[QualificationId, Text], Field(min_length=1)]

    @model_validator(mode="after")
    def _check(self) -> NosUnit:
        if split_id(self.id) != (IdKind.NOS, self.code):
            raise ValueError("id must be nos:<code>")
        return self


class Module(SchemaModel):
    """A non-NOS row of the NOS table, e.g. the bridge module (``mod:<QP code>/S<s_no>``)."""

    id: ModuleId
    qualification_id: QualificationId
    s_no: SNo
    title: Text
    is_bridge: bool

    @model_validator(mode="after")
    def _check(self) -> Module:
        code, tail = split_id(self.id)[1].rsplit("/", 1)
        if make_id(IdKind.QUAL, code) != self.qualification_id or tail != f"S{self.s_no}":
            raise ValueError("id must be mod:<qualification code>/S<s_no>")
        return self


class NosMembership(SchemaModel):
    qualification_id: QualificationId
    nos_id: NosId | None = None
    module_id: ModuleId | None = None
    s_no: SNo
    core_or_noncore: CoreOrNonCore
    nsqf_level: OfficialValued[NsqfLevel]
    version: DisplayValued[str] | None = None  # null where the source prints none (bridge rows)
    hours: HoursBreakdown
    credits: CreditValue
    is_bridge: bool

    @model_validator(mode="after")
    def _check(self) -> NosMembership:
        if (self.nos_id is None) == (self.module_id is None):
            raise ValueError("exactly one of nos_id and module_id")
        if self.is_bridge and self.module_id is None:
            raise ValueError("a bridge row is a module (mod: id), not a NOS unit")
        if not self.hours.is_complete:
            raise ValueError("a membership states all five hours values")
        return self


class CreditGroup(SchemaModel):
    """One printed credit value that covers several NOS-table rows (merged cell; OV-034/035, DQ-12).

    A representation only: the members keep their own credit values exactly as extracted, and nothing is copied from
    one row to another. It is recorded only for an approved ``PROPOSED_REPRESENTATION``. Credits stay ``NOT_USED``.
    """

    member_s_nos: Annotated[list[SNo], Field(min_length=2)]  # ascending, unique; each is a membership s_no
    credits: CreditValue  # the single printed value; evidence_id cites the overlay's geometry evidence
    overlay_ids: Annotated[list[OverlayId], Field(min_length=1)]

    @model_validator(mode="after")
    def _check(self) -> CreditGroup:
        if self.member_s_nos != sorted(set(self.member_s_nos)):
            raise ValueError("member_s_nos must be ascending and unique")
        return self


class ResolvedTarget(SchemaModel):
    """A name-based link from a claim to a catalogue qualification. Always INFERENCE, never an official edge (DQ-15)."""

    qualification_id: QualificationId
    evidence_class: Literal[EvidenceClass.INFERENCE] = EvidenceClass.INFERENCE
    evidence_id: EvidenceId


class ProgressionClaim(SchemaModel):
    id: ClaimId
    qualification_id: QualificationId
    text_verbatim: Text
    direction_label: Text  # as extracted: Horizontal, Vertical or UNLABELLED
    resolved_target: ResolvedTarget | None = None
    engine_use: Literal[EngineUse.DISPLAY_ONLY] = EngineUse.DISPLAY_ONLY
    evidence_id: EvidenceId

    @model_validator(mode="after")
    def _check(self) -> ProgressionClaim:
        code = split_id(self.id)[1].rsplit("/", 1)[0]
        if make_id(IdKind.QUAL, code) != self.qualification_id:
            raise ValueError("claim id must belong to its qualification")
        return self


class Qualification(SchemaModel):
    id: QualificationId
    code: QualificationCode
    slug: str
    coverage: Coverage
    nqr_code: Text
    titles: Titles
    awarding_body: Text | None = None
    sector: Text | None = None
    nsqf_level: OfficialValued[NsqfLevel]
    min_age: OfficialValued[MinAge] | None = None
    hours: HoursBreakdown
    credits: CreditValue
    nco_codes: list[OfficialValued[NcoCode]] = []
    version_info: dict[Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$")], DisplayValued[str]] = {}
    nos_memberships: list[NosMembership] = []
    modules: list[Module] = []
    credit_groups: list[CreditGroup] = []
    # Structured rules arrive with P1.5; until then a CURATED record may omit them (no placeholder is invented).
    eligibility: EligibilitySpec | None = None
    progression_claims: list[ProgressionClaim] = []
    quality_flags: list[QualityFlag] = []

    @model_validator(mode="after")
    def _check(self) -> Qualification:
        if self.id != make_id(IdKind.QUAL, self.code) or self.slug != slug_of(self.id):
            raise ValueError("id and slug must be derived from code")
        if self.coverage is Coverage.CURATED:
            self._check_curated()
        else:
            self._check_catalogue_only()
        return self

    def _check_curated(self) -> None:
        if self.titles.qf is None:
            raise ValueError("a CURATED qualification requires the QF title")
        if self.min_age is None:
            raise ValueError("a CURATED qualification requires min_age")
        if not self.hours.is_complete:
            raise ValueError("a CURATED qualification states all five hours values")
        if self.eligibility is not None and self.eligibility.age_rule.qualification_code != self.code:
            raise ValueError("eligibility rules belong to another qualification")
        module_ids = {m.id for m in self.modules}
        if len(module_ids) != len(self.modules):
            raise ValueError("duplicate module")
        if any(m.qualification_id != self.id for m in self.modules):
            raise ValueError("a module belongs to another qualification")
        for m in self.nos_memberships:
            if m.qualification_id != self.id:
                raise ValueError("a membership belongs to another qualification")
            if m.module_id is not None and m.module_id not in module_ids:
                raise ValueError(f"membership refers to unknown module {m.module_id}")
        by_module = {m.id: m for m in self.modules}
        if any(m.is_bridge != by_module[m.module_id].is_bridge for m in self.nos_memberships if m.module_id):
            raise ValueError("membership is_bridge differs from its module")
        numbers = [m.s_no for m in self.nos_memberships]
        if len(set(numbers)) != len(numbers):
            raise ValueError("duplicate S.No. among NOS memberships")
        for g in self.credit_groups:
            if not set(g.member_s_nos) <= set(numbers):
                raise ValueError("a credit group refers to an S.No. that is not a NOS membership")
        claim_ids = [c.id for c in self.progression_claims]
        if len(set(claim_ids)) != len(claim_ids) or any(c.qualification_id != self.id for c in self.progression_claims):
            raise ValueError("progression claims must be unique and belong to this qualification")

    def _check_catalogue_only(self) -> None:
        # Catalogue row only (ARCHITECTURE §10.2): level, notional hours and credits, no QF evidence.
        if self.titles.catalogue is None:
            raise ValueError("a CATALOGUE_ONLY qualification requires the catalogue title")
        if (
            self.nos_memberships
            or self.modules
            or self.progression_claims
            or self.credit_groups
            or self.eligibility is not None
        ):
            raise ValueError("a CATALOGUE_ONLY qualification has no NOS, module, claim or eligibility data")
        if self.min_age is not None:
            raise ValueError("the catalogue does not state a minimum age")
