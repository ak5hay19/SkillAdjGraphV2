"""P3.6a: holding origin and hypothetical holdings in the eligibility evaluator (TASKS P3.6 A-2, A-3, O-7).

Synthetic fixtures only (TEST/… codes). The rule under test is PROVISIONAL (TASKS P3.6 O-4): a hypothetically completed
qualification's relevance cannot be declared by a profile, so where it is what satisfies a prior-level component the result is
``UNKNOWN(RELEVANCE_NOT_DECLARED)``, never ``NOT_MET``. These tests pin that provisional behaviour and the unchanged
behaviour of every call that passes no hypothetical holding.
"""

import pytest
from model_factory import CODE, age_rule, component, curated, ev, official, row
from pydantic import ValidationError

from skillgraph.eligibility.components import ComponentInputs, HeldQualification, evaluate_component
from skillgraph.eligibility.evaluate import (
    EligibilityError,
    EngineConfig,
    ExternalQualification,
    ProfileState,
    TargetDeclaration,
    evaluate,
)
from skillgraph.model.eligibility import Component
from skillgraph.model.eligibility import UnknownReasonCode as R
from skillgraph.model.eligibility import Verdict
from skillgraph.model.evidence import EvidenceClass
from skillgraph.model.qualification import Qualification
from skillgraph.registry import Registry, UnknownEntityError

N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
TARGET = CODE  # TEST/Q9001: needs a prior qualification at level 2.5, "relevant"
HELD_A, HELD_B, LOW = "TEST/Q9002", "TEST/Q9003", "TEST/Q9004"
DECL_PRIOR = f"declarations[{TARGET}].relevant_prior_qualifications"
HYP = EvidenceClass.HYPOTHETICAL


def holder(code: str, level: float):
    n = int(code[-1])
    return curated(id=f"qual:{code}", code=code, slug=f"TEST.Q900{n}", titles={"qf": f"Holder {n}"},
                   nsqf_level=official(level, 10 + n, engine_use="SAFE_HARD_RULE"), nos_memberships=[], modules=[],
                   eligibility=None, progression_claims=[])


def world() -> tuple[Registry, Qualification]:
    prior = component("PRIOR_NSQF_LEVEL", params={"level": 2.5}, requires_relevance=True)
    zero = component("EXPERIENCE_MIN_YEARS", params={"years": 0.0})
    spec = {"age_rule": age_rule(), "rows": [row(1, raw_text="level cell || nothing else", components=[prior, zero],
                                                  engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE", overlay_ids=[])]}
    target = curated(eligibility=spec, nos_memberships=[], modules=[])
    quals = [Qualification.model_validate(d) for d in (target, holder(HELD_A, 2.5), holder(HELD_B, 2.5), holder(LOW, 1.0))]
    reg = Registry.from_records(qualifications=quals)
    return reg, reg.qualification_by_code(TARGET)


def profile(held=(), ext=(), rel=None, **kw) -> ProfileState:
    return ProfileState(age_years=30, held_qualification_codes=held, external_qualifications=ext,
                        declarations=(TargetDeclaration(target_code=TARGET, relevant_prior_qualifications=rel),), **kw)


def run(state, hyp=(), match="exact", **kw):
    reg, q = world()
    return evaluate(q.eligibility, state, EngineConfig(nsqf_level_match=match), reg, hypothetical_codes=hyp, **kw)


def prior_component(res):
    return res.rows[0].components[0]


def reason(res):
    c = prior_component(res)
    return c.unknown_reason.code if c.unknown_reason else None


# ---- the origin field (A-2) ----------------------------------------------------------------------------------------------


def test_origin_defaults_to_declared_and_accepts_only_declared_or_hypothetical():
    assert HeldQualification(ref=HELD_A, nsqf_level=2.5).origin is EvidenceClass.DECLARED
    assert HeldQualification(ref=HELD_A, nsqf_level=2.5, origin=HYP).is_hypothetical
    for bad in (EvidenceClass.OFFICIAL, EvidenceClass.CONFIG, EvidenceClass.INFERENCE, EvidenceClass.RULE_DERIVED, "X", None):
        with pytest.raises(ValidationError):
            HeldQualification(ref=HELD_A, nsqf_level=2.5, origin=bad)


def test_an_external_qualification_can_never_be_hypothetical():
    with pytest.raises(ValidationError, match="only a registry holding"):
        HeldQualification(ref="ext-x", nsqf_level=2.5, origin=HYP)
    assert HeldQualification(ref="ext-x", nsqf_level=2.5).origin is EvidenceClass.DECLARED


# ---- the provisional relevance rule (A-3) --------------------------------------------------------------------------------


def test_a_satisfying_hypothetical_holding_with_undeclared_relevance_is_unknown_never_not_met():
    # holdings declared complete (none held) and an empty relevant list declared: before P3.6a this satisfying holding
    # would have been "declared not relevant" and NOT_MET
    res = run(profile(held=(), ext=(), rel=()), hyp=[HELD_A])
    assert res.verdict is U and prior_component(res).verdict is U and reason(res) is R.RELEVANCE_NOT_DECLARED
    assert res.unknown_reasons[0].code is R.RELEVANCE_NOT_DECLARED and res.unknown_reasons[0].resolvable_by == "PROFILE"
    assert HELD_A in res.unknown_reasons[0].text and "hypothetically" in res.unknown_reasons[0].text


def test_the_same_holding_declared_instead_is_conditional_when_declared_relevant_and_not_met_when_not():
    assert run(profile(held=(HELD_A,), ext=(), rel=(HELD_A,))).verdict is C
    assert run(profile(held=(HELD_A,), ext=(), rel=())).verdict is N  # existing behaviour, unchanged


def test_a_declared_not_relevant_list_does_not_turn_a_hypothetical_holding_into_not_met():
    # HELD_A is declared and declared NOT relevant; HELD_B is hypothetical and satisfies the level: relevance undeclared
    res = run(profile(held=(HELD_A,), ext=(), rel=()), hyp=[HELD_B])
    assert res.verdict is U and reason(res) is R.RELEVANCE_NOT_DECLARED


def test_a_declared_relevant_satisfying_holding_still_wins_over_a_hypothetical_one():
    res = run(profile(held=(HELD_A,), ext=(), rel=(HELD_A,)), hyp=[HELD_B])
    assert res.verdict is C
    cond = [c for c in res.conditions if c.key == DECL_PRIOR]
    assert [c.value for c in cond] == [(HELD_A,)]  # the condition names the declared holding only


def test_undeclared_relevance_list_stays_unknown_with_or_without_hypothetical_holdings():
    assert reason(run(profile(held=(HELD_A,), ext=(), rel=None))) is R.RELEVANCE_NOT_DECLARED
    assert reason(run(profile(held=(), ext=(), rel=None), hyp=[HELD_A])) is R.RELEVANCE_NOT_DECLARED


def test_a_hypothetical_holding_that_does_not_satisfy_the_level_still_gives_a_definite_failure_when_complete():
    assert run(profile(held=(), ext=()), hyp=[LOW]).verdict is N


def test_precedence_of_the_other_steps_is_unchanged():
    assert reason(run(profile(held=(), ext=()), hyp=[HELD_A], match=None)) is R.CONFIG_UNSET  # step (3) before step (5)
    capped = run(profile(held=(), ext=()), hyp=[HELD_A], match="exact", undecided_level_use="CAP")
    assert capped.verdict is U  # the level of a registry qualification is capped or compared exactly as for a declared one


def test_a_hypothetical_holding_never_makes_an_undeclared_holdings_list_complete():
    # only external qualifications were declared; the registry list is undeclared, so the person may hold more
    res = run(profile(held=None, ext=()), hyp=[LOW])
    assert res.verdict is U and reason(res) is R.INPUT_NOT_DECLARED
    assert run(profile(held=(), ext=()), hyp=[LOW]).verdict is N  # both declared: a definite failure


def test_a_hypothetical_holding_alone_counts_as_a_declared_holdings_list_only_for_the_relevance_question():
    res = run(profile(held=None, ext=None), hyp=[HELD_A])
    assert res.verdict is U and reason(res) is R.RELEVANCE_NOT_DECLARED


def test_a_hypothetical_ref_listed_as_relevant_is_still_not_counted_at_component_level():
    # P3.6a: a hypothetical holding never counts as declared relevant (a profile cannot name it; PROVISIONAL)
    c = Component.model_validate({"type": "PRIOR_NSQF_LEVEL", "params": {"level": 2.5}, "evidence_id": ev(7), "safe": True,
                                  "unknown_reason": None, "requires_relevance": True})
    inp = ComponentInputs(target_code=TARGET, holdings_complete=True,
                          held_qualifications=(HeldQualification(ref=HELD_A, nsqf_level=2.5, origin=HYP),),
                          relevant_prior_qualifications=(HELD_A,))
    out = evaluate_component(c, component_id=f"rule:{TARGET}/E1#c1", inputs=inp, nsqf_level_match="exact")
    assert out.verdict is U and out.unknown_reason.code is R.RELEVANCE_NOT_DECLARED


# ---- evidence class of the inputs ---------------------------------------------------------------------------------------


def test_inputs_used_label_a_hypothetical_holding_hypothetical_and_keep_it_out_of_the_profile_field():
    res = run(profile(held=(HELD_B,), ext=(), rel=(HELD_B,)), hyp=[HELD_A])
    used = {(u.field, u.evidence_class): u.value for u in prior_component(res).inputs_used}
    assert used[("profile.held_qualification_codes", EvidenceClass.DECLARED)] == (HELD_B,)
    assert used[("path.hypothetically_completed_qualifications", HYP)] == (HELD_A,)
    assert used[(f"qual:{HELD_A}.nsqf_level", HYP)] == 2.5
    assert used[(f"qual:{HELD_B}.nsqf_level", EvidenceClass.OFFICIAL)] == 2.5


def test_inputs_without_hypothetical_holdings_are_unchanged():
    res = run(profile(held=(HELD_A,), ext=(), rel=(HELD_A,)))
    assert {u.evidence_class for u in prior_component(res).inputs_used} <= {
        EvidenceClass.DECLARED, EvidenceClass.OFFICIAL, EvidenceClass.CONFIG}
    assert "path.hypothetically_completed_qualifications" not in {u.field for u in prior_component(res).inputs_used}


# ---- the keyword (O-7) -----------------------------------------------------------------------------------------------------


def test_the_default_is_no_hypothetical_holding_and_changes_nothing():
    state = profile(held=(HELD_A,), ext=(), rel=(HELD_A,))
    assert run(state) == run(state, hyp=()) == run(state, hyp=[]) == run(state, hyp=frozenset())


def test_the_keyword_is_keyword_only():
    reg, q = world()
    with pytest.raises(TypeError):
        evaluate(q.eligibility, profile(), EngineConfig(), reg, "exact", ["TEST/Q9002"])  # type: ignore[misc]


def test_duplicates_and_order_do_not_matter():
    state = profile(held=(), ext=())
    assert run(state, hyp=[HELD_B, HELD_A, HELD_A]) == run(state, hyp=(HELD_A, HELD_B))


def test_hypothetical_codes_must_be_registry_codes():
    with pytest.raises(UnknownEntityError):
        run(profile(held=(), ext=()), hyp=["TEST/Q9099"])


def test_hypothetical_codes_must_not_repeat_declared_holdings_or_be_the_target():
    with pytest.raises(EligibilityError, match="declared holdings"):
        run(profile(held=(HELD_A,), ext=()), hyp=[HELD_A])
    with pytest.raises(EligibilityError, match="the target cannot be"):
        run(profile(held=(), ext=()), hyp=[TARGET])


@pytest.mark.parametrize("bad", ["TEST/Q9002", b"TEST/Q9002", 5, None, [5], [None], [("a",)]])
def test_hypothetical_codes_must_be_a_collection_of_strings(bad):
    with pytest.raises(TypeError):
        run(profile(held=(), ext=()), hyp=bad)


def test_the_profile_and_the_registry_are_not_changed():
    reg, q = world()
    state = profile(held=(HELD_B,), ext=(ExternalQualification(ref="ext-x", label="X", nsqf_level=4.0),), rel=(HELD_B,))
    before_state, before_reg = state.model_dump(), [r.model_dump() for r in reg.qualifications()]
    evaluate(q.eligibility, state, EngineConfig(nsqf_level_match="exact"), reg, hypothetical_codes=[HELD_A])
    assert state.model_dump() == before_state
    assert [r.model_dump() for r in reg.qualifications()] == before_reg
    assert state.held_qualification_codes == (HELD_B,)
