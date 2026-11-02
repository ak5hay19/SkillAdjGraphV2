"""P3.2 component evaluators (ARCHITECTURE §11.2–§11.3; TASKS P3.2). Synthetic fixtures only: TEST/… codes, no registry,
no file, no real data.

Where the architecture is silent the test says so and names the assumption (A-1 … A-5 in TASKS.md P3.2).
"""

import ast
import itertools
from pathlib import Path

import pytest
from model_factory import ev
from pydantic import ValidationError

from skillgraph.eligibility.components import (
    ComponentError,
    ComponentInputs,
    ComponentOutcome,
    Condition,
    ConditionKind,
    HeldQualification,
    component_id,
    evaluate_component,
)
from skillgraph.model.eligibility import Component, ComponentType, UnknownReasonCode, Verdict

N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
R = UnknownReasonCode
TARGET = "TEST/Q9001"
CID = f"rule:{TARGET}/E1#c1"
EV = ev(7)


def comp(type_: str, params: dict | None = None, *, safe: bool = True, reason: str | None = None, **kw) -> Component:
    return Component.model_validate({"type": type_, "params": params or {}, "evidence_id": EV, "safe": safe,
                                     "unknown_reason": reason, **kw})


def inputs(**kw) -> ComponentInputs:
    return ComponentInputs(target_code=TARGET, **kw)


def held(*pairs) -> tuple[HeldQualification, ...]:
    return tuple(HeldQualification(ref=r, nsqf_level=lv) for r, lv in pairs)


def run(c: Component, i: ComponentInputs | None = None, match=None) -> ComponentOutcome:
    return evaluate_component(c, component_id=CID, inputs=i or inputs(), nsqf_level_match=match)


def code(o: ComponentOutcome):
    return o.unknown_reason.code if o.unknown_reason else None


# ---- AGE_MIN -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("min_age", "age", "verdict"), [
    (18, 18, M), (18, 19, M), (18, 80, M), (18, 17, N), (18, 0, N), (0, 0, M), (16, 15, N), (16, 16, M),
])
def test_age_min_met_and_not_met_with_boundaries(min_age, age, verdict):
    o = run(comp("AGE_MIN", {"min_age": min_age}), inputs(age_years=age))
    assert o.verdict is verdict and o.unknown_reason is None and not o.conditions
    assert [(u.field, u.value, u.evidence_class.value) for u in o.inputs_used] == [("profile.age_years", age, "DECLARED")]


def test_age_min_undeclared_is_unknown_never_a_pass_or_a_failure():
    o = run(comp("AGE_MIN", {"min_age": 18}), inputs())
    assert o.verdict is U and code(o) is R.INPUT_NOT_DECLARED and o.inputs_used == ()
    assert o.unknown_reason.ref == CID and o.unknown_reason.resolvable_by == "PROFILE"
    assert o.unknown_reason.text == "Not declared: profile.age_years."


# ---- SCHOOL_GRADE_MIN --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("grade", "declared", "verdict"), [
    (9, 9, M), (9, 12, M), (9, 8, N), (9, 0, N), (0, 0, M), (12, 12, M), (12, 11, N),
])
def test_school_grade_is_at_least_per_as5(grade, declared, verdict):
    o = run(comp("SCHOOL_GRADE_MIN", {"grade": grade}), inputs(school_grade_passed=declared))
    assert o.verdict is verdict and o.unknown_reason is None


def test_school_grade_undeclared_is_unknown():
    o = run(comp("SCHOOL_GRADE_MIN", {"grade": 9}), inputs())
    assert o.verdict is U and code(o) is R.INPUT_NOT_DECLARED


@pytest.mark.parametrize(("declared", "verdict", "reason"), [
    (9, M, None), (12, M, None), (8, U, R.REVIEW_FLAG), (0, U, R.REVIEW_FLAG), (None, U, R.INPUT_NOT_DECLARED),
])
def test_below_required_verdict_unknown_replaces_not_met_only_below_the_threshold(declared, verdict, reason):
    # D5. The reason code for the below-threshold case is not specified by the architecture (A-2).
    o = run(comp("SCHOOL_GRADE_MIN", {"grade": 9, "below_required_verdict": "UNKNOWN"}), inputs(school_grade_passed=declared))
    assert o.verdict is verdict and code(o) is reason


@pytest.mark.parametrize(("declared", "verdict", "reason"), [
    (12, M, None), (11, U, R.EQUIVALENCE_UNDEFINED), (0, U, R.EQUIVALENCE_UNDEFINED), (None, U, R.INPUT_NOT_DECLARED),
])
def test_or_equivalent_grade_below_threshold_is_unknown_not_not_met(declared, verdict, reason):
    o = run(comp("SCHOOL_GRADE_MIN", {"grade": 12}, or_equivalent=True), inputs(school_grade_passed=declared))
    assert o.verdict is verdict and code(o) is reason
    if reason is R.EQUIVALENCE_UNDEFINED:
        assert o.unknown_reason.resolvable_by == "NOT_RESOLVABLE_FROM_CURRENT_SOURCES"


def test_a_declared_grade_is_never_mapped_to_an_equivalent():
    # no equivalence mechanism exists: neither a higher nor a lower grade, nor credentials, satisfy "12th or equivalent"
    o = run(comp("SCHOOL_GRADE_MIN", {"grade": 12}, or_equivalent=True),
            inputs(school_grade_passed=10, post_school_credentials=("UG_DIPLOMA",)))
    assert o.verdict is U and code(o) is R.EQUIVALENCE_UNDEFINED


# ---- NAMED_CREDENTIAL --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("creds", "or_eq", "verdict", "reason"), [
    (("UG_CERTIFICATE",), False, M, None),
    (("UG_DIPLOMA", "UG_CERTIFICATE"), False, M, None),
    ((), False, N, None),
    (("UG_DIPLOMA",), False, U, R.CREDENTIAL_ORDER_UNDEFINED),
    (("OTHER",), False, U, R.CREDENTIAL_ORDER_UNDEFINED),
    ((), True, U, R.EQUIVALENCE_UNDEFINED),
    (("UG_DIPLOMA",), True, U, R.EQUIVALENCE_UNDEFINED),  # the or_equivalent branch is checked first (§11.2)
    (("UG_CERTIFICATE",), True, M, None),
    (None, False, U, R.INPUT_NOT_DECLARED),
    (None, True, U, R.INPUT_NOT_DECLARED),
])
def test_named_credential_table(creds, or_eq, verdict, reason):
    o = run(comp("NAMED_CREDENTIAL", {"credential": "UG_CERTIFICATE"}, or_equivalent=or_eq),
            inputs(post_school_credentials=creds))
    assert o.verdict is verdict and code(o) is reason


# ---- PRIOR_NSQF_LEVEL --------------------------------------------------------------------------------------------------

PRIOR = comp("PRIOR_NSQF_LEVEL", {"level": 2.5}, requires_relevance=True)
Q_A, Q_B, EXT = "TEST/Q9101", "TEST/Q9102", "ext-cert"


def prior(**kw):
    """Both holdings lists declared (the P3.2 baseline); partial declaration has its own tests below."""
    return inputs(holdings_complete=kw.get("held_qualifications") is not None, **kw)


def test_prior_level_holdings_undeclared_is_unknown_even_with_config_unset():
    o = run(PRIOR, prior(), match=None)
    assert o.verdict is U and code(o) is R.INPUT_NOT_DECLARED  # step (1) precedes step (3)


@pytest.mark.parametrize("match", [None, "exact", "at_least"])
def test_prior_level_declared_none_is_not_met_under_any_config(match):
    o = run(PRIOR, prior(held_qualifications=()), match=match)
    assert o.verdict is N and o.unknown_reason is None  # step (2): no interpretation question arises


def test_prior_level_config_unset_is_unknown_even_where_both_interpretations_agree():
    for lv in (2.5, 1.0, 4.0):
        o = run(PRIOR, prior(held_qualifications=held((Q_A, lv)), relevant_prior_qualifications=(Q_A,)), match=None)
        assert o.verdict is U and code(o) is R.CONFIG_UNSET and o.unknown_reason.resolvable_by == "CONFIG"


@pytest.mark.parametrize(("lv", "match", "satisfies"), [
    (2.5, "exact", True), (3.0, "exact", False), (2.0, "exact", False),
    (2.5, "at_least", True), (3.0, "at_least", True), (2.0, "at_least", False),
])
def test_prior_level_exact_and_at_least(lv, match, satisfies):
    o = run(PRIOR, prior(held_qualifications=held((Q_A, lv)), relevant_prior_qualifications=(Q_A,)), match=match)
    assert o.verdict is (C if satisfies else N)


def test_prior_level_not_satisfied_is_not_met_even_if_relevance_is_undeclared():
    o = run(PRIOR, prior(held_qualifications=held((Q_A, 2.0))), match="exact")
    assert o.verdict is N


def test_prior_level_relevance_undeclared_is_unknown():
    o = run(PRIOR, prior(held_qualifications=held((Q_A, 2.5))), match="exact")
    assert o.verdict is U and code(o) is R.RELEVANCE_NOT_DECLARED and o.unknown_reason.resolvable_by == "PROFILE"
    assert TARGET in o.unknown_reason.text


@pytest.mark.parametrize("rel", [(), (Q_B,)])
def test_prior_level_relevance_declared_false_is_not_met(rel):
    o = run(PRIOR, prior(held_qualifications=held((Q_A, 2.5), (Q_B, 2.0)), relevant_prior_qualifications=rel), match="exact")
    assert o.verdict is N and not o.conditions  # the satisfying one is declared not relevant; the relevant one does not satisfy


def test_prior_level_relevant_and_satisfying_is_conditional_with_both_conditions():
    o = run(PRIOR, prior(held_qualifications=held((Q_A, 2.5), (Q_B, 2.0)), relevant_prior_qualifications=(Q_A, Q_B)),
            match="exact")
    assert o.verdict is C and o.unknown_reason is None
    d, cfg = o.conditions
    assert (d.kind, d.key, d.value, d.evidence_class.value) == (
        ConditionKind.DECLARATION, f"declarations[{TARGET}].relevant_prior_qualifications", (Q_A,), "DECLARED")
    assert (cfg.kind, cfg.key, cfg.value, cfg.evidence_class.value) == (
        ConditionKind.CONFIG, "config.nsqf_level_match", "exact", "CONFIG")
    assert o.condition == d  # the single ComponentResult.condition is the declaration (A-1)


def test_prior_level_external_qualification_uses_its_declared_level():
    o = run(PRIOR, prior(held_qualifications=held((EXT, 3.0)), relevant_prior_qualifications=(EXT,)), match="at_least")
    assert o.verdict is C
    fields = {u.field: u.evidence_class.value for u in o.inputs_used}
    assert fields["profile.external_qualifications"] == "DECLARED"
    assert fields[f"profile.external_qualifications[{EXT}].nsqf_level"] == "DECLARED"


def test_prior_level_registry_qualification_level_is_recorded_as_official():
    o = run(PRIOR, prior(held_qualifications=held((Q_A, 2.5)), relevant_prior_qualifications=(Q_A,)), match="exact")
    fields = {u.field: (u.value, u.evidence_class.value) for u in o.inputs_used}
    assert fields[f"qual:{Q_A}.nsqf_level"] == (2.5, "OFFICIAL")
    assert fields["profile.held_qualification_codes"] == ((Q_A,), "DECLARED")
    assert fields["config.nsqf_level_match"] == ("exact", "CONFIG")


def test_prior_level_shared_nos_or_similarity_is_not_an_input():
    assert not {"shared_nos", "similarity", "occupation", "credits", "title"} & set(ComponentInputs.model_fields)


# ---- audit corrections (docs/decisions/P3_2_AUDIT.md): partial holdings and capped official levels ------------------------


def one_list(**kw):
    """Only one of held_qualification_codes / external_qualifications was declared (holdings_complete stays False)."""
    return inputs(**kw)


def test_holdings_complete_defaults_to_false_so_that_an_omission_cannot_become_a_failure():
    assert ComponentInputs(target_code=TARGET).holdings_complete is False
    o = run(PRIOR, one_list(held_qualifications=()), match="exact")
    assert o.verdict is U and code(o) is R.INPUT_NOT_DECLARED and o.unknown_reason.resolvable_by == "PROFILE"


@pytest.mark.parametrize("match", ["exact", "at_least"])
def test_one_list_declared_and_nothing_satisfies_is_unknown_not_not_met(match):
    # e.g. external_qualifications declared, held_qualification_codes null: registry holdings may exist unlisted
    o = run(PRIOR, one_list(held_qualifications=held((EXT, 2.0))), match=match)
    assert o.verdict is U and code(o) is R.INPUT_NOT_DECLARED and "profile.external_qualifications" in o.unknown_reason.text


def test_one_list_declared_and_a_listed_holding_satisfies_still_counts():
    o = run(PRIOR, one_list(held_qualifications=held((EXT, 2.5)), relevant_prior_qualifications=(EXT,)), match="exact")
    assert o.verdict is C
    o = run(PRIOR, one_list(held_qualifications=held((EXT, 2.5))), match="exact")
    assert o.verdict is U and code(o) is R.RELEVANCE_NOT_DECLARED


def test_both_lists_declared_and_nothing_satisfies_is_a_definite_failure():
    o = run(PRIOR, inputs(held_qualifications=held((EXT, 2.0)), holdings_complete=True), match="exact")
    assert o.verdict is N


def test_config_unset_still_precedes_the_holdings_completeness_question():
    o = run(PRIOR, one_list(held_qualifications=held((EXT, 2.0))), match=None)
    assert o.verdict is U and code(o) is R.CONFIG_UNSET


def test_holdings_complete_without_declared_holdings_is_malformed():
    with pytest.raises(ValidationError):
        inputs(holdings_complete=True)


CAPS = [R.UNCERTAIN_EXTRACTION, R.SOURCE_CONFLICT, R.OVERLAY_NOT_APPROVED, R.ENGINE_USE_UNDECIDED]


def capped(ref, lv, cap):
    return HeldQualification(ref=ref, nsqf_level=lv, level_cap=cap)


@pytest.mark.parametrize("cap", CAPS)
@pytest.mark.parametrize("lv", [2.5, 1.0, 4.0])
def test_a_capped_level_is_never_compared_so_it_gives_neither_a_pass_nor_a_failure(cap, lv):
    # whether its number would satisfy or not, the result is the cap's UNKNOWN (§11.3 items 1, 2, 6)
    h = (capped(Q_A, lv, cap),)
    o = run(PRIOR, inputs(held_qualifications=h, holdings_complete=True, relevant_prior_qualifications=(Q_A,)), "exact")
    assert o.verdict is U and code(o) is cap and Q_A in o.unknown_reason.text and o.unknown_reason.resolvable_by == "SOURCE_REVIEW"
    assert not any(u.field == f"qual:{Q_A}.nsqf_level" for u in o.inputs_used)  # a capped level is not an input used


def test_a_capped_holding_beside_a_usable_non_satisfying_one_is_unknown_not_not_met():
    h = (capped(Q_A, 2.5, R.ENGINE_USE_UNDECIDED), HeldQualification(ref=Q_B, nsqf_level=1.0))
    o = run(PRIOR, inputs(held_qualifications=h, holdings_complete=True), "exact")
    assert o.verdict is U and code(o) is R.ENGINE_USE_UNDECIDED


def test_a_usable_satisfying_holding_wins_over_a_capped_one():
    h = (capped(Q_A, 2.5, R.SOURCE_CONFLICT), HeldQualification(ref=Q_B, nsqf_level=2.5))
    o = run(PRIOR, inputs(held_qualifications=h, holdings_complete=True, relevant_prior_qualifications=(Q_A, Q_B)), "exact")
    assert o.verdict is C and o.condition.value == (Q_B,)  # the capped holding is not named as the basis


def test_config_unset_precedes_a_capped_level():
    h = (capped(Q_A, 2.5, R.ENGINE_USE_UNDECIDED),)
    assert code(run(PRIOR, inputs(held_qualifications=h, holdings_complete=True), None)) is R.CONFIG_UNSET


def test_with_several_capped_holdings_the_reason_is_the_first_by_ref():
    h = (capped(Q_B, 2.5, R.SOURCE_CONFLICT), capped(Q_A, 2.5, R.UNCERTAIN_EXTRACTION))
    assert code(run(PRIOR, inputs(held_qualifications=h, holdings_complete=True), "exact")) is R.UNCERTAIN_EXTRACTION


@pytest.mark.parametrize("bad", [R.INPUT_NOT_DECLARED, R.CONFIG_UNSET, R.REVIEW_FLAG, R.EQUIVALENCE_UNDEFINED])
def test_only_input_state_reasons_are_valid_level_caps(bad):
    with pytest.raises(ValidationError):
        capped(Q_A, 2.5, bad)


def test_an_external_level_cannot_be_capped():
    with pytest.raises(ValidationError):
        capped(EXT, 2.5, R.UNCERTAIN_EXTRACTION)


def test_a_level_cap_does_not_touch_other_component_types():
    h = (capped(Q_A, 2.5, R.SOURCE_CONFLICT),)
    o = run(comp("AGE_MIN", {"min_age": 18}), inputs(age_years=20, held_qualifications=h))
    assert o.verdict is M


# ---- A-1: a singular ComponentResult.condition must lose no material condition ------------------------------------------


def test_the_config_condition_is_always_visible_in_inputs_used_beside_the_declaration_condition():
    o = run(PRIOR, FULL, "at_least")
    assert o.verdict is C and {c.kind for c in o.conditions} == {ConditionKind.DECLARATION, ConditionKind.CONFIG}
    used = {u.field: (u.value, u.evidence_class.value) for u in o.inputs_used}
    assert used["config.nsqf_level_match"] == ("at_least", "CONFIG")  # nothing is lost if only .condition is projected
    assert o.condition.kind is ConditionKind.DECLARATION


def test_an_outcome_with_two_declaration_conditions_or_a_hidden_config_condition_is_rejected():
    d1 = Condition(kind=ConditionKind.DECLARATION, key="a", value=1.0, evidence_class="DECLARED", text="t")
    d2 = Condition(kind=ConditionKind.DECLARATION, key="b", value=2.0, evidence_class="DECLARED", text="t")
    cfg = Condition(kind=ConditionKind.CONFIG, key="config.nsqf_level_match", value="exact", evidence_class="CONFIG", text="t")
    base = {"component_id": CID, "type": "PRIOR_NSQF_LEVEL", "verdict": C, "evidence_ids": (EV,)}
    with pytest.raises(ValidationError, match="at most one DECLARATION"):
        ComponentOutcome(**base, conditions=(d1, d2))
    with pytest.raises(ValidationError, match="inputs_used"):
        ComponentOutcome(**base, conditions=(d1, cfg))  # CONFIG condition without the config input
    ok = ComponentOutcome(**base, conditions=(d1, cfg), inputs_used=(
        {"field": "config.nsqf_level_match", "value": "exact", "evidence_class": "CONFIG"},))
    assert ok.condition == d1


# ---- EXPERIENCE_MIN_YEARS ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("years", "declared", "verdict"), [
    (3.0, 3.0, C), (3.0, 10.0, C), (3.0, 2.5, N), (3.0, 0.0, N), (0.5, 0.5, C), (0.5, 0.4, N),
])
def test_experience_declared_against_required(years, declared, verdict):
    o = run(comp("EXPERIENCE_MIN_YEARS", {"years": years}, requires_relevance=True), inputs(relevant_experience_years=declared))
    assert o.verdict is verdict
    if verdict is C:
        (cond,) = o.conditions
        assert cond.kind is ConditionKind.DECLARATION and cond.key == f"declarations[{TARGET}].relevant_experience_years"
        assert cond.value == declared and o.condition == cond


def test_experience_undeclared_is_unknown():
    o = run(comp("EXPERIENCE_MIN_YEARS", {"years": 3.0}, requires_relevance=True), inputs())
    assert o.verdict is U and code(o) is R.INPUT_NOT_DECLARED
    assert "relevant_experience_years" in o.unknown_reason.text


@pytest.mark.parametrize("declared", [None, 0.0, 12.0])
@pytest.mark.parametrize("relevance", [True, False])
def test_zero_years_required_is_met_whatever_is_declared(declared, relevance):
    o = run(comp("EXPERIENCE_MIN_YEARS", {"years": 0.0}, requires_relevance=relevance), inputs(relevant_experience_years=declared))
    assert o.verdict is M and not o.conditions and o.unknown_reason is None


def test_experience_without_requires_relevance_is_still_conditional_when_years_are_required():
    # The architecture's table does not branch on requires_relevance; the flag is not used to grant MET (A-3).
    o = run(comp("EXPERIENCE_MIN_YEARS", {"years": 2.0}, requires_relevance=False), inputs(relevant_experience_years=5.0))
    assert o.verdict is C


# ---- UNMODELLED and stored (static) unknowns ----------------------------------------------------------------------------

UNMODELLED_REASONS = [R.ENROLMENT_NOT_MODELLED, R.LITERACY_NOT_MODELLED, R.NTC_NAC_CITS_NOT_MODELLED,
                      R.DIPLOMA_YEAR_NOT_MODELLED, R.REVIEW_FLAG, R.OVERLAY_NOT_APPROVED]
FULL = inputs(age_years=40, school_grade_passed=12, post_school_credentials=("UG_CERTIFICATE", "UG_DIPLOMA"),
              held_qualifications=held((Q_A, 2.5)), holdings_complete=True, relevant_prior_qualifications=(Q_A,), relevant_experience_years=20.0)


@pytest.mark.parametrize("reason", UNMODELLED_REASONS)
@pytest.mark.parametrize("profile", [inputs(), FULL], ids=["nothing declared", "everything declared"])
@pytest.mark.parametrize("match", [None, "exact", "at_least"])
def test_unmodelled_is_always_unknown_with_its_stored_reason(reason, profile, match):
    o = run(comp("UNMODELLED", safe=False, reason=reason.value), profile, match)
    assert o.verdict is U and code(o) is reason and o.inputs_used == () and not o.conditions
    assert o.unknown_reason.ref == CID and o.unknown_reason.resolvable_by == "SOURCE_REVIEW"


def test_unmodelled_or_equivalent_has_no_effect():
    a = run(comp("UNMODELLED", safe=False, reason="LITERACY_NOT_MODELLED"), FULL)
    b = run(comp("UNMODELLED", safe=False, reason="LITERACY_NOT_MODELLED", or_equivalent=True), FULL)
    assert a == b


STATIC = [R.UNCERTAIN_EXTRACTION, R.OVERLAY_NOT_APPROVED, R.ENGINE_USE_UNDECIDED, R.SOURCE_CONFLICT, R.REVIEW_FLAG]
TYPED = {
    "AGE_MIN": {"min_age": 18}, "SCHOOL_GRADE_MIN": {"grade": 9}, "NAMED_CREDENTIAL": {"credential": "UG_DIPLOMA"},
    "PRIOR_NSQF_LEVEL": {"level": 2.5}, "EXPERIENCE_MIN_YEARS": {"years": 3.0},
}


@pytest.mark.parametrize(("type_", "reason"), list(itertools.product(TYPED, STATIC)))
def test_an_unsafe_component_is_unknown_with_its_stored_reason_whatever_the_profile_says(type_, reason):
    # §11.3 items 1, 2, 6: uncertain, pending-overlay, undecided and conflicted inputs cap the result.
    c = comp(type_, TYPED[type_], safe=False, reason=reason.value)
    for profile, match in ((inputs(), None), (FULL, "exact"), (FULL, "at_least")):
        o = run(c, profile, match)
        assert o.verdict is U and code(o) is reason and o.inputs_used == ()


def test_stored_reason_wording_and_resolution_are_stable():
    o = run(comp("UNMODELLED", safe=False, reason="DIPLOMA_YEAR_NOT_MODELLED"))
    assert o.unknown_reason.model_dump(mode="json") == {
        "code": "DIPLOMA_YEAR_NOT_MODELLED", "ref": CID, "text": "Diploma-year routes are not modelled in profiles.",
        "resolvable_by": "SOURCE_REVIEW"}  # the wording of API_SPEC §3 E07's example


def test_every_unknown_reason_code_has_a_resolution():
    from skillgraph.eligibility import components as mod

    assert set(mod._RESOLVABLE_BY) == set(UnknownReasonCode)
    assert set(mod._STATIC_TEXT) == set(UnknownReasonCode) - mod._DYNAMIC


# ---- evidence references, determinism, purity --------------------------------------------------------------------------

CASES = [
    (comp("AGE_MIN", {"min_age": 18}), inputs(age_years=20), None),
    (comp("AGE_MIN", {"min_age": 18}), inputs(), None),
    (comp("SCHOOL_GRADE_MIN", {"grade": 9}), inputs(school_grade_passed=5), None),
    (comp("NAMED_CREDENTIAL", {"credential": "UG_DIPLOMA"}), inputs(post_school_credentials=("UG_DIPLOMA",)), None),
    (PRIOR, FULL, "exact"), (PRIOR, FULL, None), (PRIOR, inputs(held_qualifications=()), "exact"),
    (comp("EXPERIENCE_MIN_YEARS", {"years": 3.0}), inputs(relevant_experience_years=4.0), None),
    (comp("UNMODELLED", safe=False, reason="REVIEW_FLAG"), FULL, "exact"),
    (comp("AGE_MIN", {"min_age": 18}, safe=False, reason="UNCERTAIN_EXTRACTION"), FULL, "exact"),
]


@pytest.mark.parametrize(("c", "i", "match"), CASES)
def test_the_component_evidence_id_is_preserved_for_every_verdict(c, i, match):
    assert run(c, i, match).evidence_ids == (EV,)


@pytest.mark.parametrize(("c", "i", "match"), CASES)
def test_repeated_evaluation_gives_identical_results(c, i, match):
    before = (c.model_dump(), i.model_dump())
    results = [run(c, i, match) for _ in range(3)]
    assert results[0] == results[1] == results[2]
    assert results[0].model_dump_json() == results[1].model_dump_json()
    assert (c.model_dump(), i.model_dump()) == before  # the inputs are not modified


def test_holdings_order_does_not_change_the_result():
    pairs = ((Q_A, 2.5), (Q_B, 3.0), (EXT, 2.5))
    outs = {
        run(PRIOR, inputs(held_qualifications=held(*p), relevant_prior_qualifications=(Q_B, EXT, Q_A)), "at_least").model_dump_json()
        for p in itertools.permutations(pairs)
    }
    assert len(outs) == 1


def test_every_outcome_obeys_the_invariants_of_the_contract():
    for c, i, match in CASES:
        o = run(c, i, match)
        assert (o.verdict is U) == (o.unknown_reason is not None)  # every UNKNOWN explains itself
        assert (o.verdict is C) == bool(o.conditions)  # every CONDITIONAL names what it rests on
        assert o.component_id == CID and o.type is c.type


def test_outcome_model_rejects_inconsistent_shapes():
    base = {"component_id": CID, "type": "AGE_MIN", "evidence_ids": (EV,)}
    with pytest.raises(ValidationError):
        ComponentOutcome(**base, verdict=U)  # UNKNOWN without a reason
    with pytest.raises(ValidationError):
        ComponentOutcome(**base, verdict=C)  # CONDITIONAL without a condition
    cond = Condition(kind=ConditionKind.CONFIG, key="k", value=None, evidence_class="CONFIG", text="t")
    with pytest.raises(ValidationError):
        ComponentOutcome(**base, verdict=M, conditions=(cond,))


def test_the_modules_import_only_the_model_package_and_the_standard_library():
    root = Path(__file__).resolve().parents[2] / "src" / "skillgraph" / "eligibility"
    allowed = ("skillgraph.model", "pydantic", "__future__", "re", "enum", "typing")
    for name in ("logic.py", "components.py"):
        mods = []
        for node in ast.walk(ast.parse((root / name).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods.append(node.module or "")
        assert mods
        for m in mods:  # whole dotted prefix, so skillgraph.registry / .api / .labour / .curation are all refused
            assert any(m == a or m.startswith(a + ".") for a in allowed), (name, m)


# ---- malformed input is rejected, not guessed at ------------------------------------------------------------------------


@pytest.mark.parametrize("kw", [
    {"age_years": True}, {"age_years": "18"}, {"age_years": -1}, {"age_years": 17.5},
    {"school_grade_passed": 13}, {"school_grade_passed": -1}, {"school_grade_passed": False},
    {"post_school_credentials": ("PHD",)}, {"post_school_credentials": "UG_DIPLOMA"},
    {"relevant_experience_years": -1.0}, {"relevant_experience_years": "3"}, {"relevant_experience_years": True},
    {"held_qualifications": held((Q_A, 2.5), (Q_A, 3.0))},
    {"held_qualifications": None, "relevant_prior_qualifications": (Q_A,)},
    {"held_qualifications": held((Q_A, 2.5)), "relevant_prior_qualifications": (Q_B,)},
    {"held_qualifications": held((Q_A, 2.5)), "relevant_prior_qualifications": (Q_A, Q_A)},
    {"surprise": 1}, {"credits": 4.0},
])
def test_malformed_inputs_are_rejected(kw):
    with pytest.raises(ValidationError):
        inputs(**kw)


@pytest.mark.parametrize(("ref", "level"), [("TEST/Q91", 2.5), ("ext-UPPER", 2.5), ("ext-", 2.5), (Q_A, 0.5), (Q_A, 11.0),
                                            (Q_A, 2.25), (Q_A, "2.5"), (Q_A, True)])
def test_malformed_holdings_are_rejected(ref, level):
    with pytest.raises(ValidationError):
        HeldQualification(ref=ref, nsqf_level=level)


def test_a_bad_target_code_is_rejected():
    with pytest.raises(ValidationError):
        ComponentInputs(target_code="not-a-code")


@pytest.mark.parametrize("bad", ["", "rule:TEST/Q9001/E1", "rule:TEST/Q9001/E1#c0", "rule:TEST/Q9001/E1#c", "x#c1", None, 7])
def test_malformed_component_ids_are_rejected(bad):
    with pytest.raises(ComponentError):
        evaluate_component(comp("AGE_MIN", {"min_age": 18}), component_id=bad, inputs=inputs(age_years=20))


def test_component_id_helper():
    assert component_id("rule:TEST/Q9001/E9", 2) == "rule:TEST/Q9001/E9#c2"
    assert component_id("rule:TEST/Q9001/AGE", 1) == "rule:TEST/Q9001/AGE#c1"
    for rid, n in (("rule:TEST/Q9001/E1", 0), ("rule:TEST/Q9001/E1", True), ("qual:TEST/Q9001", 1)):
        with pytest.raises(ComponentError):
            component_id(rid, n)


@pytest.mark.parametrize("match", ["Exact", "", "greater", 2.5, True])
def test_an_unknown_level_interpretation_is_rejected(match):
    with pytest.raises(ComponentError):
        run(PRIOR, FULL, match)


def test_wrong_argument_types_are_rejected():
    with pytest.raises(TypeError):
        evaluate_component({"type": "AGE_MIN"}, component_id=CID, inputs=inputs())
    with pytest.raises(TypeError):
        evaluate_component(comp("AGE_MIN", {"min_age": 18}), component_id=CID, inputs={"age_years": 20})


@pytest.mark.parametrize(("type_", "params"), [
    ("SCHOOL_GRADE_MIN", {"grade": 13}), ("SCHOOL_GRADE_MIN", {"grade": -1}), ("SCHOOL_GRADE_MIN", {"grade": 9.5}),
    ("SCHOOL_GRADE_MIN", {"grade": True}), ("SCHOOL_GRADE_MIN", {}), ("SCHOOL_GRADE_MIN", {"grade": 9, "below_required_verdict": "NOT_MET"}),
    ("NAMED_CREDENTIAL", {}), ("NAMED_CREDENTIAL", {"credential": "PHD"}), ("NAMED_CREDENTIAL", {"credential": "OTHER"}),
    ("EXPERIENCE_MIN_YEARS", {"years": -1.0}),
])
def test_malformed_stored_params_are_rejected(type_, params):
    with pytest.raises((ComponentError, ValidationError)):
        run(comp(type_, params), FULL)


def test_a_component_built_with_model_construct_is_revalidated():
    bad = Component.model_construct(type=ComponentType.AGE_MIN, params={}, requires_relevance=False, or_equivalent=False,
                                    evidence_id=EV, safe=True, unknown_reason=None)
    with pytest.raises(ValidationError):
        run(bad, FULL)


@pytest.mark.parametrize("dynamic", [R.INPUT_NOT_DECLARED, R.RELEVANCE_NOT_DECLARED, R.CONFIG_UNSET,
                                     R.EQUIVALENCE_UNDEFINED, R.CREDENTIAL_ORDER_UNDEFINED])
def test_a_stored_per_evaluation_reason_is_malformed(dynamic):
    with pytest.raises(ComponentError, match="never stored"):
        run(comp("AGE_MIN", {"min_age": 18}, safe=False, reason=dynamic.value), FULL)


def test_a_safe_component_with_a_reason_or_an_unsafe_one_without_is_malformed():
    with pytest.raises(ComponentError):
        run(comp("AGE_MIN", {"min_age": 18}, safe=True, reason="REVIEW_FLAG"), FULL)
    with pytest.raises(ComponentError):
        run(comp("AGE_MIN", {"min_age": 18}, safe=False, reason=None), FULL)


def test_evaluation_never_raises_on_valid_but_incomplete_inputs():
    for type_, params in TYPED.items():
        for match in (None, "exact", "at_least"):
            o = run(comp(type_, params), inputs(), match)
            assert o.verdict in (U, M, N)  # 0-year experience is MET; everything else needs a declaration
            assert o.verdict is not M or type_ == "EXPERIENCE_MIN_YEARS" and params["years"] == 0
