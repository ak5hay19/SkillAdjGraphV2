"""Qualification-level eligibility evaluator (ARCHITECTURE §11.1–§11.3; API_SPEC §2.3, §2.4; TASKS P3.3).

``evaluate(spec, state, config, registry)`` resolves a hypothetical profile against the registry into the inputs of ONE
target, evaluates every component of the target's rules with ``evaluate_component`` (P3.2; no component logic lives here),
and aggregates with the P3.2 lattice:

    row verdict    = and_(component verdicts)
    target verdict = and_(age, or_(row verdicts))             (ARCHITECTURE §11.1)

Nothing here decides a verdict except those two folds. It reads no credit, NOS membership, occupation, title similarity,
progression claim or labour-market figure when deciding, and there is no probabilistic or LLM judgement. Progression claims
are *displayed* (``supporting_evidence``) and never feed a verdict. A pending, unapproved overlay proposal is never applied:
the curated components built from one are not safe and stay ``UNKNOWN`` whatever the profile says (P3.2).

Result shapes mirror API_SPEC §2.4 exactly (no field is added). The only deliberate departures are listed in the notes
below. Choices where the specification is silent are numbered D-1 … D-6 and recorded in ``TASKS.md`` (P3.3).

D-1  A specification with no rows raises ``EligibilityError``. ``or_()`` of nothing is undefined (P3.2), ``NOT_MET`` would
     claim a definite failure and ``UNKNOWN`` has no fitting reason code, so the data defect is surfaced, not guessed at.
D-2  ``decisive_rule_ids`` are row ids only, as written in API_SPEC §2.4: the rows whose verdict equals the target verdict,
     or every row when the target is ``NOT_MET``. When the age rule alone limits the target (for example age ``UNKNOWN``
     with a ``CONDITIONAL`` row) no row attains the target verdict and the list is empty; the age component, which is
     always returned, carries the reason.
D-3  Target-level ``conditions`` are the union of ``ComponentOutcome.conditions`` (not of the singular ``.condition``) over
     every component of every decisive row, with exact duplicates removed and sorted by ``(key, kind, value, text)``
     (API_SPEC §2.4: "de-duplicated, sorted by key"). Two conditions with the same key and different values are both kept.
     A consumer reads the verdict first: conditions on a ``NOT_MET`` or ``UNKNOWN`` target describe the decisive rows
     only and are not a claim that the target is conditional.
D-4  Target-level ``unknown_reasons`` are filled only when the target is ``UNKNOWN`` (ARCHITECTURE §11.3 item 4): the age
     reason if the age is unknown, then the reason of every ``UNKNOWN`` component of the decisive rows, in printed order.
D-5  ``supporting_evidence``: the verbatim progression claims of each registry qualification the profile holds AND declares
     relevant to the target, shown as "lists X as a progression". No claim is linked to the target by name: a claim-to-
     target link is an inference (ARCHITECTURE §10.3, P3.5) and none is made here. ``explanation`` is empty (P3.8).
D-6  Q-B (``docs/decisions/P3_2_AUDIT.md``). A held registry qualification's own ``nsqf_level`` is compared only if its
     provenance allows it: an open conflict caps it ``SOURCE_CONFLICT``, an uncertain or null value ``UNCERTAIN_EXTRACTION``
     (§11.3 items 1, 2); ``DISPLAY_ONLY``, ``NOT_USED`` and ``SAFE_HOURS`` caps it ``ENGINE_USE_UNDECIDED`` (§11.4 "shown,
     never computed"). The one undecided case is ``engine_use`` ``UNKNOWN`` (every curated qualification-level NSQF value
     of the real build): ``undecided_level_use`` selects ``COMPARE`` (default; the reading that TASKS P3.3 criteria 1-2,
     ARCHITECTURE §11.5 and the E07 example rely on) or ``CAP`` (the strict reading of §11.4). Results that depend on this
     choice are PROVISIONAL until Q-B is decided; the choice is an explicit argument, never implicit.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Collection

from pydantic import Field, StrictInt, StrictStr, StringConstraints, model_validator

from skillgraph.eligibility.components import (
    Condition,
    ConditionKind,
    ComponentInputs,
    ComponentOutcome,
    HeldQualification,
    InputUsed,
    NsqfLevelMatch,
    PostSchoolCredentialType,
    UnknownReason,
    component_id,
    evaluate_component,
)
from skillgraph.eligibility.logic import and_, or_
from skillgraph.model.base import NsqfLevel, Number, SchemaModel
from skillgraph.model.eligibility import (
    AgeRule,
    ComponentType,
    EligibilityRow,
    EligibilitySpec,
    ParamValue,
    UnknownReasonCode,
    Verdict,
)
from skillgraph.model.evidence import EngineUse, EvidenceClass, QualityFlag, QualityFlagCode, Severity, ValueStatus
from skillgraph.model.ids import EvidenceId, QualificationCode
from skillgraph.model.qualification import Qualification
from skillgraph.registry import Registry

__all__ = [
    "ComponentResult",
    "EligibilityError",
    "EligibilityResult",
    "EngineConfig",
    "ExplanationItem",
    "ExternalQualification",
    "PostSchoolCredential",
    "ProfileState",
    "QualificationRef",
    "RowResult",
    "TargetDeclaration",
    "UndecidedLevelUse",
    "evaluate",
    "identity_profile_digest",
]

DELIMITER = " || "  # a space, two vertical bars, a space (ARCHITECTURE §9.2, cell mapping)
Years = Annotated[Number, Field(ge=0)]


class EligibilityError(ValueError):
    """The specification, profile or registry cannot be evaluated (malformed or incomplete data). Not a verdict."""


class UndecidedLevelUse(StrEnum):
    """Q-B: what to do with a held registry qualification's NSQF level whose ``engine_use`` is ``UNKNOWN``."""

    COMPARE = "COMPARE"  # compare it (TASKS P3.3 criteria 1-2; ARCHITECTURE §11.5; E07 example)
    CAP = "CAP"  # do not compare it: ENGINE_USE_UNDECIDED (strict reading of ARCHITECTURE §11.4)


# --------------------------------------------------------------------------------------------------------------------
# Inputs (API_SPEC §2.3)
# --------------------------------------------------------------------------------------------------------------------


class EngineConfig(SchemaModel):
    """``nsqf_level_match`` is ``None`` when unset; that makes every ``PRIOR_NSQF_LEVEL`` component ``UNKNOWN``."""

    nsqf_level_match: NsqfLevelMatch | None = None


class PostSchoolCredential(SchemaModel):
    type: PostSchoolCredentialType
    label: StrictStr | None = None


class ExternalQualification(SchemaModel):
    ref: Annotated[StrictStr, StringConstraints(pattern=r"^ext-[a-z0-9-]{1,20}$")]
    label: Annotated[StrictStr, StringConstraints(min_length=1)]
    nsqf_level: NsqfLevel


class TargetDeclaration(SchemaModel):
    target_code: QualificationCode
    relevant_experience_years: Years | None = None
    relevant_prior_qualifications: tuple[StrictStr, ...] | None = None


class ProfileState(SchemaModel):
    """The engine view of ``HypotheticalProfile`` (API_SPEC §2.3). ``None`` is "not declared"; an empty tuple is "none".

    ``label`` is request metadata and is not an engine input. The two holding lists are independently nullable: the
    evaluator treats the holdings as complete only if both are declared."""

    age_years: Annotated[StrictInt, Field(ge=14, le=80)] | None = None
    school_grade_passed: Annotated[StrictInt, Field(ge=0, le=12)] | None = None
    post_school_credentials: tuple[PostSchoolCredential, ...] | None = None
    held_qualification_codes: tuple[QualificationCode, ...] | None = None
    external_qualifications: tuple[ExternalQualification, ...] | None = None
    declarations: tuple[TargetDeclaration, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> ProfileState:
        codes, ext = self.held_qualification_codes, self.external_qualifications
        if codes is not None and len(set(codes)) != len(codes):
            raise ValueError("held_qualification_codes must be unique")
        if ext is not None and len({e.ref for e in ext}) != len(ext):
            raise ValueError("external_qualifications must have unique refs")
        refs = set(codes or ()) | {e.ref for e in ext or ()}
        targets = [d.target_code for d in self.declarations]
        if len(set(targets)) != len(targets):
            raise ValueError("declarations[].target_code must be unique")
        for d in self.declarations:
            rel = d.relevant_prior_qualifications
            if rel is None:
                continue
            if len(set(rel)) != len(rel):
                raise ValueError("relevant_prior_qualifications must be unique")
            if (codes is None and ext is None) or not set(rel) <= refs:
                raise ValueError("relevant_prior_qualifications must refer to declared holdings")
        return self


def identity_profile_digest(state: ProfileState) -> str:
    """The identity of a validated profile, for path identity (API_SPEC §4 amendment A-6; TASKS P3.6).

    ``"sha256:"`` plus the lowercase hex SHA-256 of the UTF-8 bytes of ``json.dumps(projection, sort_keys=True,
    separators=(",", ":"), ensure_ascii=False)``, the models serialised with ``model_dump(mode="json")``. It is NOT
    ``logging_setup.profile_digest`` (a digest of the raw mapping, for logs), which is unchanged.

    Projection: ``age_years``; ``school_grade_passed``; ``post_school_credentials`` (the ``type`` of each credential, sorted,
    duplicates KEPT: ``inputs_used`` echoes the declared credentials, so a duplicate changes the serialised result);
    ``held_qualification_codes`` (sorted); ``external_qualifications`` (``{ref, nsqf_level}`` sorted by ``ref``);
    ``declarations`` (sorted by ``target_code``, each ``{target_code, relevant_experience_years,
    relevant_prior_qualifications}`` with the last sorted). Only these set-like collections are put in order. ``None`` (not
    declared) and ``[]`` (declared none) stay distinct for every nullable field. The three display labels (the request
    ``label``, ``PostSchoolCredential.label`` and ``ExternalQualification.label``) are excluded: nothing
    in the engine reads them, so they cannot reach a verdict, a condition or an ``inputs_used`` entry."""
    if not isinstance(state, ProfileState):
        raise TypeError(f"state must be a ProfileState, got {type(state).__name__}")
    d = state.model_dump(mode="json")

    def ordered(values: list | None) -> list | None:
        return None if values is None else sorted(values)

    ext = d["external_qualifications"]
    projection = {
        "age_years": d["age_years"],
        "school_grade_passed": d["school_grade_passed"],
        "post_school_credentials": (None if d["post_school_credentials"] is None
                                    else sorted(c["type"] for c in d["post_school_credentials"])),
        "held_qualification_codes": ordered(d["held_qualification_codes"]),
        "external_qualifications": (None if ext is None else
                                    sorted(({"ref": e["ref"], "nsqf_level": e["nsqf_level"]} for e in ext),
                                           key=lambda e: e["ref"])),
        "declarations": sorted(({"target_code": x["target_code"],
                                 "relevant_experience_years": x["relevant_experience_years"],
                                 "relevant_prior_qualifications": ordered(x["relevant_prior_qualifications"])}
                                for x in d["declarations"]), key=lambda x: x["target_code"]),
    }
    canonical = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------------------------------
# Outputs (API_SPEC §2.2, §2.4)
# --------------------------------------------------------------------------------------------------------------------


class ComponentResult(SchemaModel):
    component_id: StrictStr
    type: ComponentType
    requirement_text: StrictStr
    params: dict[str, ParamValue]
    verdict: Verdict
    inputs_used: tuple[InputUsed, ...]
    evidence_ids: tuple[EvidenceId, ...]
    condition: Condition | None = None
    unknown_reason: UnknownReason | None = None


class RowResult(SchemaModel):
    rule_id: StrictStr
    s_no: StrictInt
    raw_text: StrictStr
    engine_use: EngineUse
    overlay_ids: tuple[StrictStr, ...]
    verdict: Verdict
    components: tuple[ComponentResult, ...]
    flags: tuple[QualityFlag, ...]


class QualificationRef(SchemaModel):
    id: StrictStr
    code: StrictStr
    slug: StrictStr
    title: StrictStr
    nsqf_level: float | None  # display only; never an input to a verdict


class ExplanationItem(SchemaModel):
    kind: StrictStr
    text: StrictStr
    evidence_class: EvidenceClass
    evidence_ids: tuple[EvidenceId, ...] = ()
    flags: tuple[QualityFlagCode, ...] = ()


class EligibilityResult(SchemaModel):
    target: QualificationRef
    verdict: Verdict
    age: ComponentResult
    rows: tuple[RowResult, ...]
    decisive_rule_ids: tuple[StrictStr, ...]
    conditions: tuple[Condition, ...]
    unknown_reasons: tuple[UnknownReason, ...]
    supporting_evidence: tuple[ExplanationItem, ...]
    explanation: tuple[ExplanationItem, ...] = ()
    quality_flags: tuple[QualityFlag, ...]

    @model_validator(mode="after")
    def _check(self) -> EligibilityResult:  # the P3.3 invariants (TASKS criterion 8) hold for every result by construction
        every = [self.age, *(c for r in self.rows for c in r.components)]
        for c in every:
            if (c.verdict is Verdict.CONDITIONAL) != (c.condition is not None):
                raise ValueError(f"{c.component_id}: a CONDITIONAL component has a condition, and no other has one")
            if (c.verdict is Verdict.UNKNOWN) != (c.unknown_reason is not None):
                raise ValueError(f"{c.component_id}: an UNKNOWN component has a reason, and no other has one")
        if self.verdict is Verdict.UNKNOWN and not self.unknown_reasons:
            raise ValueError("an UNKNOWN target carries at least one unknown reason")
        if self.verdict is not Verdict.UNKNOWN and self.unknown_reasons:
            raise ValueError("only an UNKNOWN target carries target-level unknown reasons")
        return self


# --------------------------------------------------------------------------------------------------------------------
# Resolution of the profile against the registry
# --------------------------------------------------------------------------------------------------------------------

_USABLE_LEVEL_USES = frozenset({
    EngineUse.SAFE_HARD_RULE, EngineUse.SAFE_WITH_CONSTRAINT, EngineUse.CONDITIONAL_ON_DECLARED_RELEVANCE,
    EngineUse.CONDITIONAL_ON_DECLARED_RELEVANCE_LEVEL_CONFIG,
})
_UNCERTAIN = frozenset({ValueStatus.PARSED_UNCERTAIN, ValueStatus.UNRESOLVED})
_R = UnknownReasonCode


def _title(q: Qualification) -> str:
    return q.titles.qf or q.titles.qp or q.titles.catalogue or q.code


def _held_from_registry(q: Qualification, undecided: UndecidedLevelUse,
                        origin: EvidenceClass = EvidenceClass.DECLARED) -> HeldQualification:
    """A registry holding with its level and, if the level may not be compared, the reason (D-6)."""
    v = q.nsqf_level
    if v.conflict_id is not None:  # §11.3 item 2
        cap: UnknownReasonCode | None = _R.SOURCE_CONFLICT
    elif v.value is None or v.value_status in _UNCERTAIN:  # §11.3 item 1: not confirmed, corroborated or corrected
        cap = _R.UNCERTAIN_EXTRACTION
    elif v.engine_use in _USABLE_LEVEL_USES:
        cap = None
    elif v.engine_use is EngineUse.UNKNOWN or v.engine_use is None:  # Q-B: the audit assigned the value no use
        cap = None if undecided is UndecidedLevelUse.COMPARE else _R.ENGINE_USE_UNDECIDED
    else:  # DISPLAY_ONLY, NOT_USED, SAFE_HOURS: §11.4 "shown, never computed"
        cap = _R.ENGINE_USE_UNDECIDED
    # A capped level is never compared. 1.0 is a placeholder required by the field's type when the source level is null.
    return HeldQualification(ref=q.code, nsqf_level=v.value if v.value is not None else 1.0, level_cap=cap, origin=origin)


def _checked_hypothetical(hypothetical_codes: Collection[str], state: ProfileState, target_code: str,
                          registry: Registry) -> tuple[str, ...]:
    """The hypothetically completed codes, de-duplicated and sorted (P3.6a, TASKS P3.6 O-7).

    They must be registry codes (``UnknownEntityError`` otherwise), must not already be declared holdings and must not be
    the target itself (``EligibilityError``). They are only ever *added* to the resolved holdings; ``state`` is not changed."""
    if isinstance(hypothetical_codes, str | bytes) or not isinstance(hypothetical_codes, Collection):
        raise TypeError("hypothetical_codes must be a collection of qualification codes, not a single string")
    if not all(isinstance(c, str) for c in hypothetical_codes):
        raise TypeError("hypothetical_codes must contain only strings")
    codes = tuple(sorted(set(hypothetical_codes)))
    for code in codes:
        registry.qualification_by_code(code)  # UnknownEntityError
    declared = set(state.held_qualification_codes or ())
    if overlap := declared & set(codes):
        raise EligibilityError(f"hypothetical_codes must not repeat declared holdings: {sorted(overlap)}")
    if target_code in codes:
        raise EligibilityError(f"{target_code}: the target cannot be one of the hypothetically completed qualifications")
    return codes


def _resolve_inputs(state: ProfileState, target_code: str, registry: Registry, undecided: UndecidedLevelUse,
                    hypothetical: tuple[str, ...] = ()) -> tuple[ComponentInputs, dict[str, Qualification]]:
    codes, ext = state.held_qualification_codes, state.external_qualifications
    registry_held = {code: registry.qualification_by_code(code) for code in codes or ()}  # unknown code: UnknownEntityError
    held: tuple[HeldQualification, ...] | None = None
    if codes is not None or ext is not None or hypothetical:
        items = [_held_from_registry(q, undecided) for q in registry_held.values()]
        items += [_held_from_registry(registry.qualification_by_code(c), undecided, EvidenceClass.HYPOTHETICAL)
                  for c in hypothetical]
        items += [HeldQualification(ref=e.ref, nsqf_level=e.nsqf_level) for e in ext or ()]
        held = tuple(sorted(items, key=lambda h: h.ref))
    decl = next((d for d in state.declarations if d.target_code == target_code), None)
    inputs = ComponentInputs(
        target_code=target_code,
        age_years=state.age_years,
        school_grade_passed=state.school_grade_passed,
        post_school_credentials=(None if state.post_school_credentials is None
                                 else tuple(c.type for c in state.post_school_credentials)),
        held_qualifications=held,
        # true only if BOTH profile lists were declared; hypothetical holdings never complete an undeclared list (A-2)
        holdings_complete=codes is not None and ext is not None,
        relevant_prior_qualifications=None if decl is None else decl.relevant_prior_qualifications,
        relevant_experience_years=None if decl is None else decl.relevant_experience_years,
    )
    return inputs, registry_held


# --------------------------------------------------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------------------------------------------------


def _texts(rule: AgeRule | EligibilityRow) -> list[str]:
    """The verbatim text of each component's own cell: the age rule's whole text, or the row split once on the delimiter."""
    if isinstance(rule, AgeRule):
        texts = [rule.raw_text]
    else:
        head, sep, tail = rule.raw_text.partition(DELIMITER)
        if not sep:
            raise EligibilityError(f"{rule.id}: raw_text has no {DELIMITER!r} delimiter")
        texts = [head, tail]
    if len(texts) != len(rule.components):
        raise EligibilityError(f"{rule.id}: {len(rule.components)} components for {len(texts)} printed cells")
    return texts


def _run_rule(rule: AgeRule | EligibilityRow, inputs: ComponentInputs,
              match: NsqfLevelMatch | None) -> list[tuple[ComponentResult, ComponentOutcome]]:
    out = []
    for n, (comp, text) in enumerate(zip(rule.components, _texts(rule), strict=True), start=1):
        o = evaluate_component(comp, component_id=component_id(rule.id, n), inputs=inputs, nsqf_level_match=match)
        params = dict(comp.params)
        if comp.requires_relevance:  # the API projection (API_SPEC §2.4)
            params["requires_relevance"] = True
        out.append((ComponentResult(
            component_id=o.component_id, type=o.type, requirement_text=text, params=params, verdict=o.verdict,
            inputs_used=o.inputs_used, evidence_ids=o.evidence_ids, condition=o.condition, unknown_reason=o.unknown_reason,
        ), o))
    return out


def _condition_sort_key(c: Condition) -> tuple[str, str, str, str]:
    return c.key, c.kind.value, json.dumps(c.value, sort_keys=True), c.text


def _flag_sort_key(f: QualityFlag) -> tuple[str, str, tuple[str, ...], str]:
    return f.code.value, f.severity.value, tuple(f.refs), f.message


def _supporting_evidence(relevant_held: list[Qualification]) -> tuple[ExplanationItem, ...]:
    items = []
    for q in sorted(relevant_held, key=lambda x: x.code):
        for claim in sorted(q.progression_claims, key=lambda c: c.id):
            items.append(ExplanationItem(
                kind="PROGRESSION_CLAIM",
                text=(f"The {_title(q)} QF lists '{claim.text_verbatim}' as a progression. Supporting evidence only; "
                      "it does not change the verdict."),
                evidence_class=EvidenceClass.OFFICIAL, evidence_ids=(claim.evidence_id,)))
    return tuple(items)


def evaluate(
    spec: EligibilitySpec,
    state: ProfileState,
    config: EngineConfig,
    registry: Registry,
    *,
    undecided_level_use: UndecidedLevelUse = UndecidedLevelUse.COMPARE,
    hypothetical_codes: Collection[str] = (),
) -> EligibilityResult:
    """Evaluate one target's rules for a hypothetical profile; pure, deterministic, no I/O.

    ``spec`` belongs to the target qualification, which must exist in ``registry`` (it supplies the target reference and
    the held qualifications' levels and claims). ``undecided_level_use`` is the Q-B switch described in the module notes.
    ``hypothetical_codes`` (P3.6a; TASKS P3.6 O-7) are registry qualifications that a path is assumed to have completed:
    they are held with origin ``HYPOTHETICAL``, are never written into ``state`` and never make an undeclared holdings list
    "complete". Their relevance cannot be declared, so a hypothetical holding that satisfies a prior-level component gives
    ``UNKNOWN(RELEVANCE_NOT_DECLARED)``, not ``NOT_MET`` (PROVISIONAL; ARCHITECTURE §13.1).
    Raises ``EligibilityError`` for a specification that cannot be evaluated, ``UnknownEntityError`` for a held code that
    is not in the registry, and the P3.2 errors for a malformed component. A valid but incomplete profile never raises:
    it gives ``UNKNOWN``.
    """
    for obj, cls, name in ((spec, EligibilitySpec, "spec"), (state, ProfileState, "state"),
                           (config, EngineConfig, "config"), (registry, Registry, "registry")):
        if not isinstance(obj, cls):
            raise TypeError(f"{name} must be a {cls.__name__}, got {type(obj).__name__}")
    undecided = UndecidedLevelUse(undecided_level_use)
    spec = EligibilitySpec.model_validate(spec.model_dump())  # model_construct / model_copy skip the validators
    if not spec.rows:
        raise EligibilityError(f"{spec.age_rule.id}: a specification without rows has no defined verdict (D-1)")
    target_code = spec.age_rule.qualification_code
    target = registry.qualification_by_code(target_code)
    hypothetical = _checked_hypothetical(hypothetical_codes, state, target_code, registry)
    inputs, registry_held = _resolve_inputs(state, target_code, registry, undecided, hypothetical)
    match = config.nsqf_level_match

    age_pairs = _run_rule(spec.age_rule, inputs, match)
    age, _ = age_pairs[0]  # an age rule has exactly one component (model-enforced)
    row_pairs = [(row, _run_rule(row, inputs, match)) for row in spec.rows]
    row_verdicts = [and_(*(res.verdict for res, _ in pairs)) for _, pairs in row_pairs]

    verdict = and_(age.verdict, or_(*row_verdicts))
    rows = tuple(
        RowResult(rule_id=row.id, s_no=row.s_no, raw_text=row.raw_text, engine_use=row.engine_use,
                  overlay_ids=tuple(row.overlay_ids), verdict=rv, components=tuple(res for res, _ in pairs),
                  flags=tuple(f.model_copy(deep=True) for f in row.flags))
        for (row, pairs), rv in zip(row_pairs, row_verdicts, strict=True))
    decisive = [(row, pairs) for (row, pairs), rv in zip(row_pairs, row_verdicts, strict=True)
                if verdict is Verdict.NOT_MET or rv is verdict]  # D-2

    unique = {_condition_sort_key(c): c for _, pairs in decisive for _, o in pairs for c in o.conditions}  # D-3
    conditions = tuple(unique[k] for k in sorted(unique))

    reasons: list[UnknownReason] = []  # D-4
    if verdict is Verdict.UNKNOWN:
        if age.unknown_reason is not None:
            reasons.append(age.unknown_reason)
        reasons += [o.unknown_reason for _, pairs in decisive for _, o in pairs if o.unknown_reason is not None]

    flags: dict[tuple, QualityFlag] = {}
    if any(c.kind is ConditionKind.DECLARATION for c in conditions):
        f = QualityFlag(code=QualityFlagCode.DEPENDS_ON_DECLARATION, severity=Severity.CAUTION,
                        message="Relevance is self-declared and unverified.")
        flags[_flag_sort_key(f)] = f
    if any(c.kind is ConditionKind.CONFIG for c in conditions):
        f = QualityFlag(code=QualityFlagCode.DEPENDS_ON_CONFIG, severity=Severity.CAUTION,
                        message="The result depends on the configured NSQF level interpretation.")
        flags[_flag_sort_key(f)] = f
    for row, _ in decisive:  # the stored flags of the decisive rows (UNCERTAIN_EXTRACTION, OVERLAY_PENDING_APPROVAL, …)
        for f in row.flags:
            flags.setdefault(_flag_sort_key(f), f.model_copy(deep=True))

    rel = inputs.relevant_prior_qualifications or ()
    relevant_held = [q for code, q in registry_held.items() if code in rel]  # D-5

    return EligibilityResult(
        target=QualificationRef(id=target.id, code=target.code, slug=target.slug, title=_title(target),
                                nsqf_level=target.nsqf_level.value),
        verdict=verdict, age=age, rows=rows, decisive_rule_ids=tuple(row.id for row, _ in decisive),
        conditions=conditions, unknown_reasons=tuple(reasons), supporting_evidence=_supporting_evidence(relevant_held),
        quality_flags=tuple(flags[k] for k in sorted(flags)),
    )
