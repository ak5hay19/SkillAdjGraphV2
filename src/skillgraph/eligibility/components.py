"""Component evaluators (ARCHITECTURE §11.2–§11.4; API_SPEC §2.4; TASKS P3.2).

``evaluate_component`` evaluates ONE stored ``Component`` against the already-resolved inputs of ONE target and returns
a ``ComponentOutcome``: the verdict, the inputs used, the evidence ids, the conditions a ``CONDITIONAL`` rests on and the
reason an ``UNKNOWN`` is unknown. It aggregates nothing: combining components into rows, rows into a target, resolving a
profile against the registry and projecting ``ComponentResult`` belong to P3.3.

Rules, in the order they apply:

1. The stored component is re-validated (``model_construct`` skips validators) and its shape is checked. A malformed
   component, input or identifier raises (``ComponentError`` or pydantic ``ValidationError``); it is never guessed at.
2. An ``UNMODELLED`` component, or any component with ``safe = False``, is ``UNKNOWN`` with its *stored* reason
   (``UNCERTAIN_EXTRACTION``, ``OVERLAY_NOT_APPROVED``, ``ENGINE_USE_UNDECIDED``, ``SOURCE_CONFLICT``, ``REVIEW_FLAG``,
   ``*_NOT_MODELLED``), whatever the profile says (§11.3 items 1, 2 and 6). Nothing in the profile can lift it.
3. Otherwise the §11.2 rule of its type applies. A missing input is ``UNKNOWN`` and never ``MET`` or ``NOT_MET``.

Nothing here reads a registry, a similarity, a shared NOS unit, an occupation, a progression claim, a credit value or any
labour-market figure, and there is no probabilistic or LLM judgement. Credits do not exist in this module's inputs.

Choices where the architecture is silent are numbered A-1 … A-6 in ``TASKS.md`` P3.2 and marked ``(A-n)`` below.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from skillgraph.model.base import NsqfLevel, Number, SchemaModel
from skillgraph.model.eligibility import Component, ComponentType, UnknownReasonCode, Verdict
from skillgraph.model.evidence import EvidenceClass
from skillgraph.model.ids import KEY_PATTERNS, QUAL_CODE, EvidenceId, IdKind, QualificationCode

__all__ = [
    "Condition",
    "ConditionKind",
    "ComponentError",
    "ComponentInputs",
    "ComponentOutcome",
    "HeldQualification",
    "InputUsed",
    "NsqfLevelMatch",
    "PostSchoolCredentialType",
    "UnknownReason",
    "component_id",
    "evaluate_component",
]

NsqfLevelMatch = Literal["exact", "at_least"]
PostSchoolCredentialType = Literal["UG_CERTIFICATE", "UG_DIPLOMA", "OTHER"]  # API_SPEC §2.1
Resolvable = Literal["PROFILE", "CONFIG", "SOURCE_REVIEW", "NOT_RESOLVABLE_FROM_CURRENT_SOURCES"]
Years = Annotated[Number, Field(ge=0)]
Value = StrictStr | StrictInt | float | tuple[StrictStr, ...]

_CREDENTIALS = ("UG_CERTIFICATE", "UG_DIPLOMA")  # the values params.credential may take (API_SPEC §2.4)
_COMPONENT_ID = re.compile(rf"^rule:{KEY_PATTERNS[IdKind.RULE]}#c[1-9]\d*$")
_EXTERNAL_REF = re.compile(r"^ext-[a-z0-9-]{1,20}$")  # API_SPEC §2.3
_REGISTRY_REF = re.compile(rf"^{QUAL_CODE}$")
_LEVEL_CAPS = frozenset({
    UnknownReasonCode.UNCERTAIN_EXTRACTION, UnknownReasonCode.SOURCE_CONFLICT, UnknownReasonCode.OVERLAY_NOT_APPROVED,
    UnknownReasonCode.ENGINE_USE_UNDECIDED,
})


class ComponentError(ValueError):
    """The component, its inputs or its identifier are malformed. Distinct from UNKNOWN, which is a valid verdict."""


class ConditionKind(StrEnum):
    DECLARATION = "DECLARATION"
    CONFIG = "CONFIG"
    HYPOTHETICAL = "HYPOTHETICAL"


# --------------------------------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------------------------------


class HeldQualification(SchemaModel):
    """A prior qualification the profile holds, with its NSQF level already resolved by the caller (P3.3).

    ``ref`` is a registry code (its level is OFFICIAL, taken from the registry) or an ``ext-…`` reference to an
    external qualification (its level is DECLARED by the profile). The two are told apart by the form of ``ref``.

    ``level_cap`` carries the state of an OFFICIAL level that ARCHITECTURE §11.3 items 1, 2 and 6 say must not be
    computed with: ``UNCERTAIN_EXTRACTION`` (uncertain value), ``SOURCE_CONFLICT`` (open conflict),
    ``OVERLAY_NOT_APPROVED`` (pending proposal) or ``ENGINE_USE_UNDECIDED`` (no computing use). The caller (P3.3) sets it
    from the level's provenance (``value_status``, ``conflict_id``, ``engine_use``); ``None`` means the level may be
    compared. Which provenance states cap a level is a policy question for P3.3 (see ``docs/decisions/P3_2_AUDIT.md``);
    this class only makes the capped state representable, so that it cannot be silently turned into a comparison.

    ``origin`` says how the holding came to be held: ``DECLARED`` (the default, every holding of a profile) or
    ``HYPOTHETICAL`` (a qualification that a path step is assumed to complete, ARCHITECTURE §13.1; P3.6a, API_SPEC §4
    amendment A-2). Only a registry holding can be hypothetical. The relevance of a hypothetical holding cannot be declared
    by a profile (API_SPEC §2.3), so it never counts as declared relevant here (PROVISIONAL, TASKS P3.6 O-4).
    """

    ref: StrictStr
    nsqf_level: NsqfLevel
    level_cap: UnknownReasonCode | None = None
    origin: Literal[EvidenceClass.DECLARED, EvidenceClass.HYPOTHETICAL] = EvidenceClass.DECLARED

    @field_validator("ref")
    @classmethod
    def _form(cls, v: str) -> str:
        if not (_REGISTRY_REF.fullmatch(v) or _EXTERNAL_REF.fullmatch(v)):
            raise ValueError("ref must be a qualification code or an ext-… reference")
        return v

    @model_validator(mode="after")
    def _cap(self) -> HeldQualification:
        if self.level_cap is not None:
            if self.level_cap not in _LEVEL_CAPS:
                raise ValueError(f"level_cap must be one of {sorted(c.value for c in _LEVEL_CAPS)}")
            if self.is_external:
                raise ValueError("an external qualification's level is the profile's own declaration and has no cap")
        if self.is_external and self.origin is not EvidenceClass.DECLARED:
            raise ValueError("an external qualification is always DECLARED; only a registry holding can be hypothetical")
        return self

    @property
    def is_external(self) -> bool:
        return self.ref.startswith("ext-")

    @property
    def is_hypothetical(self) -> bool:
        return self.origin is EvidenceClass.HYPOTHETICAL


class ComponentInputs(SchemaModel):
    """Everything a component may read about one target. ``None`` always means "not declared", never "none".

    Mirrors ``HypotheticalProfile`` and ``TargetDeclaration`` (API_SPEC §2.3) after the caller resolved holdings against
    the registry. ``held_qualifications`` is ``None`` only if the profile declared neither registry holdings nor
    external ones; ``()`` means the declared lists together hold none.

    The profile has two independent nullable lists (``held_qualification_codes``, ``external_qualifications``).
    ``holdings_complete`` is true only if BOTH were declared (API_SPEC §2.3). It defaults to false (fail closed): with
    one list undeclared, a person may hold qualifications that are not listed, so "no listed holding satisfies the level"
    is not a definite failure and the component is ``UNKNOWN(INPUT_NOT_DECLARED)``, not ``NOT_MET`` (§11.1: ``NOT_MET``
    needs a definitively failed rule). A listed holding that does satisfy the level still counts either way.
    """

    target_code: QualificationCode
    age_years: Annotated[StrictInt, Field(ge=0)] | None = None
    school_grade_passed: Annotated[StrictInt, Field(ge=0, le=12)] | None = None
    post_school_credentials: tuple[PostSchoolCredentialType, ...] | None = None
    held_qualifications: tuple[HeldQualification, ...] | None = None
    holdings_complete: StrictBool = False
    relevant_prior_qualifications: tuple[StrictStr, ...] | None = None
    relevant_experience_years: Years | None = None

    @model_validator(mode="after")
    def _check(self) -> ComponentInputs:
        if self.holdings_complete and self.held_qualifications is None:
            raise ValueError("holdings_complete requires declared held_qualifications")
        refs = [h.ref for h in self.held_qualifications or ()]
        if len(set(refs)) != len(refs):
            raise ValueError("held_qualifications must be unique by ref")
        rel = self.relevant_prior_qualifications
        if rel is not None:
            if len(set(rel)) != len(rel):
                raise ValueError("relevant_prior_qualifications must be unique")
            if self.held_qualifications is None or not set(rel) <= set(refs):
                raise ValueError("relevant_prior_qualifications must refer to declared holdings")
        return self


# --------------------------------------------------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------------------------------------------------


class InputUsed(SchemaModel):
    field: StrictStr
    value: Value | None
    evidence_class: Literal[EvidenceClass.DECLARED, EvidenceClass.CONFIG, EvidenceClass.OFFICIAL,
                            EvidenceClass.HYPOTHETICAL]  # HYPOTHETICAL is listed in API_SPEC §2.4 (P3.6a)


class Condition(SchemaModel):
    """A CONDITIONAL verdict holds only if this does (ARCHITECTURE §11.3 item 3)."""

    kind: ConditionKind
    key: StrictStr
    value: Value | None
    evidence_class: Literal[EvidenceClass.DECLARED, EvidenceClass.CONFIG]
    text: StrictStr


class UnknownReason(SchemaModel):
    code: UnknownReasonCode
    ref: StrictStr  # the component id
    text: StrictStr
    resolvable_by: Resolvable


class ComponentOutcome(SchemaModel):
    """The result of one component. ``UNKNOWN`` has exactly one reason; ``CONDITIONAL`` has at least one condition."""

    component_id: StrictStr
    type: ComponentType
    verdict: Verdict
    inputs_used: tuple[InputUsed, ...] = ()
    evidence_ids: tuple[EvidenceId, ...]
    conditions: tuple[Condition, ...] = ()
    unknown_reason: UnknownReason | None = None

    @property
    def condition(self) -> Condition | None:
        """The declaration condition, the single ``ComponentResult.condition`` of API_SPEC §2.4 (the CONFIG condition,
        if any, is in ``conditions`` and reaches the target-level list). (A-1)"""
        return next((c for c in self.conditions if c.kind is ConditionKind.DECLARATION), None)

    @model_validator(mode="after")
    def _check(self) -> ComponentOutcome:
        if (self.verdict is Verdict.UNKNOWN) != (self.unknown_reason is not None):
            raise ValueError("an UNKNOWN outcome has exactly one reason, and no other outcome has one")
        if (self.verdict is Verdict.CONDITIONAL) != bool(self.conditions):
            raise ValueError("a CONDITIONAL outcome has at least one condition, and no other outcome has any")
        # ComponentResult.condition is singular (API_SPEC §2.4). Projecting it must lose no material condition, so an
        # outcome has at most one DECLARATION condition and every other kind is also visible in inputs_used.
        if sum(c.kind is ConditionKind.DECLARATION for c in self.conditions) > 1:
            raise ValueError("an outcome has at most one DECLARATION condition")
        used = {u.field for u in self.inputs_used}
        missing = [c.key for c in self.conditions if c.kind is not ConditionKind.DECLARATION and c.key not in used]
        if missing:
            raise ValueError(f"conditions {missing} must also appear in inputs_used")
        return self


def component_id(rule_id: str, n: int) -> str:
    """``rule:AMH/Q2301/E9`` and 1 -> ``rule:AMH/Q2301/E9#c1`` (API_SPEC §2.4); n counts from 1."""
    cid = f"{rule_id}#c{n}"
    if isinstance(n, bool) or not isinstance(n, int) or not _COMPONENT_ID.fullmatch(cid):
        raise ComponentError(f"not a component id: {cid!r}")
    return cid


# --------------------------------------------------------------------------------------------------------------------
# Unknown reasons
# --------------------------------------------------------------------------------------------------------------------

# Causes that exist only per evaluation. They are never stored (API_SPEC §2.4), so a stored component carrying one is
# malformed.
_DYNAMIC = frozenset({
    UnknownReasonCode.INPUT_NOT_DECLARED, UnknownReasonCode.RELEVANCE_NOT_DECLARED, UnknownReasonCode.CONFIG_UNSET,
    UnknownReasonCode.EQUIVALENCE_UNDEFINED, UnknownReasonCode.CREDENTIAL_ORDER_UNDEFINED,
})
_R = UnknownReasonCode
# Fixed wording for the stored (static) causes. Tests pin it, so a change is deliberate.
_STATIC_TEXT = {
    _R.ENROLMENT_NOT_MODELLED: "Pursuing schooling is not modelled in profiles.",
    _R.LITERACY_NOT_MODELLED: "'Ability to read and write' is not modelled in profiles.",
    _R.NTC_NAC_CITS_NOT_MODELLED: "NTC/NAC/CITS routes are not modelled in profiles.",
    _R.DIPLOMA_YEAR_NOT_MODELLED: "Diploma-year routes are not modelled in profiles.",
    _R.REVIEW_FLAG: "The audit flagged this requirement's verbatim text for review; it is not evaluated.",
    _R.UNCERTAIN_EXTRACTION: "The source value is an uncertain extraction and has not been substantiated.",
    _R.SOURCE_CONFLICT: "The value this requirement depends on has an open source conflict.",
    _R.OVERLAY_NOT_APPROVED: "The value exists only as a pending overlay proposal that has not been approved.",
    _R.ENGINE_USE_UNDECIDED: "The audit has assigned this requirement no safe use; it needs a new audit decision.",
}
_RESOLVABLE_BY: dict[UnknownReasonCode, Resolvable] = {
    _R.INPUT_NOT_DECLARED: "PROFILE", _R.RELEVANCE_NOT_DECLARED: "PROFILE", _R.CONFIG_UNSET: "CONFIG",
    _R.EQUIVALENCE_UNDEFINED: "NOT_RESOLVABLE_FROM_CURRENT_SOURCES",
    _R.CREDENTIAL_ORDER_UNDEFINED: "NOT_RESOLVABLE_FROM_CURRENT_SOURCES",
    **dict.fromkeys(_STATIC_TEXT, "SOURCE_REVIEW"),
}
assert set(_RESOLVABLE_BY) == set(UnknownReasonCode)  # a new code must be given a resolution here


def _reason(code: UnknownReasonCode, cid: str, text: str | None = None) -> UnknownReason:
    return UnknownReason(code=code, ref=cid, text=text if text is not None else _STATIC_TEXT[code],
                         resolvable_by=_RESOLVABLE_BY[code])


# --------------------------------------------------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------------------------------------------------

_Result = tuple[Verdict, tuple[InputUsed, ...], tuple[Condition, ...], UnknownReason | None]
_D, _C, _O = EvidenceClass.DECLARED, EvidenceClass.CONFIG, EvidenceClass.OFFICIAL


def _unknown(code: UnknownReasonCode, cid: str, text: str, used: tuple[InputUsed, ...] = ()) -> _Result:
    return Verdict.UNKNOWN, used, (), _reason(code, cid, text)


def _not_declared(cid: str, field: str, used: tuple[InputUsed, ...] = ()) -> _Result:
    return _unknown(_R.INPUT_NOT_DECLARED, cid, f"Not declared: {field}.", used)


def _age(c: Component, cid: str, i: ComponentInputs, _: NsqfLevelMatch | None) -> _Result:
    if i.age_years is None:
        return _not_declared(cid, "profile.age_years")
    used = (InputUsed(field="profile.age_years", value=i.age_years, evidence_class=_D),)
    return (Verdict.MET if i.age_years >= c.params["min_age"] else Verdict.NOT_MET), used, (), None


def _grade(c: Component, cid: str, i: ComponentInputs, _: NsqfLevelMatch | None) -> _Result:
    if i.school_grade_passed is None:
        return _not_declared(cid, "profile.school_grade_passed")
    g = i.school_grade_passed
    used = (InputUsed(field="profile.school_grade_passed", value=g, evidence_class=_D),)
    if g >= c.params["grade"]:  # "at least" is rule-derived per AS-5 / Q-9
        return Verdict.MET, used, (), None
    if c.or_equivalent:  # Q-3 default: a lower grade is not NOT_MET where "or equivalent" is printed
        return _unknown(_R.EQUIVALENCE_UNDEFINED, cid, "The requirement allows an equivalent, and no equivalence rule "
                        "is defined; the declared grade is below the threshold.", used)
    if c.params.get("below_required_verdict") == "UNKNOWN":  # decision D5; the code to use is not specified (A-2)
        return _unknown(_R.REVIEW_FLAG, cid, "The requirement's wording ('Grade' without 'pass') is kept verbatim and "
                        "is not resolved for a lower declared grade (audit decision D5).", used)
    return Verdict.NOT_MET, used, (), None


def _credential(c: Component, cid: str, i: ComponentInputs, _: NsqfLevelMatch | None) -> _Result:
    held = i.post_school_credentials
    if held is None:
        return _not_declared(cid, "profile.post_school_credentials")
    used = (InputUsed(field="profile.post_school_credentials", value=tuple(sorted(held)), evidence_class=_D),)
    if c.params["credential"] in held:
        return Verdict.MET, used, (), None
    if c.or_equivalent:
        return _unknown(_R.EQUIVALENCE_UNDEFINED, cid, "The requirement allows an equivalent, and no equivalence "
                        "rule is defined; the named credential is not held.", used)
    if held:  # other post-school credentials are held and no order between credentials is defined
        return _unknown(_R.CREDENTIAL_ORDER_UNDEFINED, cid, "Other post-school credentials are declared, and no order "
                        "between credentials is defined.", used)
    return Verdict.NOT_MET, used, (), None


def _level_ok(held_level: float, required: float, match: NsqfLevelMatch) -> bool:
    return held_level == required if match == "exact" else held_level >= required


def _held_used(held: tuple[HeldQualification, ...]) -> tuple[InputUsed, ...]:
    ordered = sorted(held, key=lambda h: h.ref)
    codes = tuple(h.ref for h in ordered if not h.is_external and not h.is_hypothetical)
    hypothetical = tuple(h.ref for h in ordered if h.is_hypothetical)
    externals = tuple(h.ref for h in ordered if h.is_external)
    used = []
    if codes or not held:
        used.append(InputUsed(field="profile.held_qualification_codes", value=codes, evidence_class=_D))
    if externals:
        used.append(InputUsed(field="profile.external_qualifications", value=externals, evidence_class=_D))
    if hypothetical:  # not a profile field: the qualifications a path is assumed to have completed (ARCHITECTURE §13.1)
        used.append(InputUsed(field="path.hypothetically_completed_qualifications", value=hypothetical,
                              evidence_class=EvidenceClass.HYPOTHETICAL))
    for h in ordered:  # a registry level is OFFICIAL; an external level is the profile's own declaration
        if h.level_cap is not None:  # a capped level is not computed with, so it is not an input used
            continue
        used.append(InputUsed(
            field=(f"profile.external_qualifications[{h.ref}].nsqf_level" if h.is_external
                   else f"qual:{h.ref}.nsqf_level"),
            value=h.nsqf_level,
            evidence_class=(_D if h.is_external else EvidenceClass.HYPOTHETICAL if h.is_hypothetical else _O)))
    return tuple(used)


def _prior_level(c: Component, cid: str, i: ComponentInputs, match: NsqfLevelMatch | None) -> _Result:
    held = i.held_qualifications
    if held is None:  # (1)
        return _not_declared(cid, "profile.held_qualification_codes / profile.external_qualifications")
    used = _held_used(held)
    partial = _unknown(_R.INPUT_NOT_DECLARED, cid, "Not declared: one of profile.held_qualification_codes and "
                       "profile.external_qualifications, so the qualifications held are not fully known.", used)
    if not held:  # (2) no interpretation question arises
        return (Verdict.NOT_MET, used, (), None) if i.holdings_complete else partial
    if match is None:  # (3) even where both interpretations would agree (decision D3)
        return _unknown(_R.CONFIG_UNSET, cid, "config.nsqf_level_match is not set, so a stated NSQF level cannot be "
                        "compared.", used)
    used += (InputUsed(field="config.nsqf_level_match", value=match, evidence_class=_C),)
    level = c.params["level"]
    satisfying = [h for h in held if h.level_cap is None and _level_ok(h.nsqf_level, level, match)]
    if not satisfying:  # (4) a failure is definite only if every held level was compared and the holdings are complete
        capped = sorted((h for h in held if h.level_cap is not None), key=lambda h: h.ref)
        if capped:
            h = capped[0]
            return _unknown(h.level_cap, cid, f"The NSQF level of {h.ref} cannot be used: {_STATIC_TEXT[h.level_cap]}", used)
        return (Verdict.NOT_MET, used, (), None) if i.holdings_complete else partial
    rel = i.relevant_prior_qualifications  # (5) relevance is declared per target and is never verified
    key = f"declarations[{i.target_code}].relevant_prior_qualifications"
    if rel is None:
        return _unknown(_R.RELEVANCE_NOT_DECLARED, cid, f"Not declared: {key}.", used)
    used += (InputUsed(field=key, value=tuple(sorted(rel)), evidence_class=_D),)
    # A hypothetical holding never counts as declared relevant: a profile cannot declare it (API_SPEC §2.3; PROVISIONAL).
    relevant = tuple(sorted(h.ref for h in satisfying if h.ref in rel and not h.is_hypothetical))
    if not relevant:
        undeclared = sorted(h.ref for h in satisfying if h.is_hypothetical)
        if undeclared:  # "relevance undeclared" (§11.2 step 5), not "declared not relevant": never NOT_MET (TASKS P3.6 A-3)
            return _unknown(_R.RELEVANCE_NOT_DECLARED, cid,
                            f"Not declared: whether the hypothetically completed {', '.join(undeclared)} is relevant to "
                            "this qualification (a profile cannot declare it).", used)
        return Verdict.NOT_MET, used, (), None  # declared not relevant (or declared none relevant)
    conditions = (
        Condition(kind=ConditionKind.DECLARATION, key=key, value=relevant, evidence_class=_D,
                  text=f"Holds only if {', '.join(relevant)} is relevant to this qualification (your declaration; "
                       "not verified)."),
        Condition(kind=ConditionKind.CONFIG, key="config.nsqf_level_match", value=match, evidence_class=_C,
                  text=("Uses the interpretation that a stated NSQF level means exactly that level." if match == "exact"
                        else "Uses the interpretation that a stated NSQF level means that level or higher.")),
    )
    return Verdict.CONDITIONAL, used, conditions, None


def _experience(c: Component, cid: str, i: ComponentInputs, _: NsqfLevelMatch | None) -> _Result:
    required = c.params["years"]
    if required == 0:  # nothing is required, so nothing needs declaring
        return Verdict.MET, (), (), None
    key = f"declarations[{i.target_code}].relevant_experience_years"
    declared = i.relevant_experience_years
    if declared is None:
        return _not_declared(cid, key)
    used = (InputUsed(field=key, value=declared, evidence_class=_D),)
    if declared < required:
        return Verdict.NOT_MET, used, (), None
    cond = Condition(kind=ConditionKind.DECLARATION, key=key, value=declared, evidence_class=_D,
                     text=f"Holds only if your {declared:g} years of experience are relevant (your declaration; "
                          "not verified).")
    return Verdict.CONDITIONAL, used, (cond,), None


_EVALUATORS = {
    ComponentType.AGE_MIN: _age,
    ComponentType.SCHOOL_GRADE_MIN: _grade,
    ComponentType.NAMED_CREDENTIAL: _credential,
    ComponentType.PRIOR_NSQF_LEVEL: _prior_level,
    ComponentType.EXPERIENCE_MIN_YEARS: _experience,
}


def _checked_component(component: object) -> Component:
    """Re-validate the stored component and check what the model leaves open; raise on anything malformed."""
    if not isinstance(component, Component):
        raise TypeError(f"expected a Component, got {type(component).__name__}")
    c = Component.model_validate(component.model_dump())  # model_construct / model_copy skip the validators
    p = c.params
    if c.type is ComponentType.SCHOOL_GRADE_MIN:
        g = p.get("grade")
        if isinstance(g, bool) or not isinstance(g, int) or not 0 <= g <= 12:
            raise ComponentError("SCHOOL_GRADE_MIN requires an integer params['grade'] from 0 to 12")
        if p.get("below_required_verdict", "UNKNOWN") != "UNKNOWN":
            raise ComponentError("params['below_required_verdict'] may only be 'UNKNOWN'")
    elif c.type is ComponentType.NAMED_CREDENTIAL:
        if p.get("credential") not in _CREDENTIALS:
            raise ComponentError(f"NAMED_CREDENTIAL requires params['credential'] in {_CREDENTIALS}")
    elif c.type is ComponentType.EXPERIENCE_MIN_YEARS and p["years"] < 0:
        raise ComponentError("EXPERIENCE_MIN_YEARS requires params['years'] >= 0")
    if c.safe == (c.unknown_reason is not None):
        raise ComponentError("a safe component carries no unknown_reason and an unsafe one carries exactly one")
    if c.unknown_reason in _DYNAMIC:
        raise ComponentError(f"{c.unknown_reason.value} is a per-evaluation cause and is never stored")
    return c


def evaluate_component(
    component: Component,
    *,
    component_id: str,
    inputs: ComponentInputs,
    nsqf_level_match: NsqfLevelMatch | None = None,
) -> ComponentOutcome:
    """Evaluate one stored component; pure and deterministic. ``nsqf_level_match`` is ``EngineConfig.nsqf_level_match``
    (``None`` = unset, which makes every ``PRIOR_NSQF_LEVEL`` component ``UNKNOWN``)."""
    c = _checked_component(component)
    if not isinstance(component_id, str) or not _COMPONENT_ID.fullmatch(component_id):
        raise ComponentError(f"not a component id: {component_id!r}")
    if not isinstance(inputs, ComponentInputs):
        raise TypeError(f"expected ComponentInputs, got {type(inputs).__name__}")
    if nsqf_level_match not in (None, "exact", "at_least"):
        raise ComponentError(f"nsqf_level_match must be 'exact', 'at_least' or None, got {nsqf_level_match!r}")

    if not c.safe:  # includes every UNMODELLED component: the stored cause stands, whatever the profile says
        used: tuple[InputUsed, ...] = ()
        verdict, conditions, reason = Verdict.UNKNOWN, (), _reason(c.unknown_reason, component_id)
    else:
        verdict, used, conditions, reason = _EVALUATORS[c.type](c, component_id, inputs, nsqf_level_match)
    return ComponentOutcome(component_id=component_id, type=c.type, verdict=verdict, inputs_used=used,
                            evidence_ids=(c.evidence_id,), conditions=conditions, unknown_reason=reason)
