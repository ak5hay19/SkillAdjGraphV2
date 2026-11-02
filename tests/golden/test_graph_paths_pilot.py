"""P3.6a golden tests: path enumeration over the four curated pilot qualifications of the REAL curated build (skipped when absent).

Every test loads the real build through the ``reg`` fixture, which asserts ``BuildInfo.validation == "PASSED"``. All profiles are
synthetic ("a person who ..."); no result is a claim about a real person.

Expected values are derived by hand from the printed rules and the documented contract, not copied from the enumerator:

* The pilots in ascending ``qualification_id`` order are AMH/Q0103 (IC), AMH/Q0301 (SMO), AMH/Q2101 (PS), AMH/Q2301 (SSMO).
* Nothing can be ``NOT_MET`` for a profile that declares nothing (every input is then undeclared), so all four are steps and
  the number of paths of up to three steps is 4 + 4*3 + 4*3*2 = 40, all ``UNKNOWN`` because the age is undeclared.
* Age 17 is below every printed minimum (18, 18, 18, 20), so every pilot is ``NOT_MET`` as a first step and there is no path.

PROVISIONAL markers: Q-B (``undecided_level_use = COMPARE``, the ``evaluate`` default, which the E07 profile result relies on;
see ``docs/decisions/P3_2_AUDIT.md``) and the hypothetical-relevance rule (TASKS P3.6 A-3 / O-4). P-1 to P-5 are implementation
decisions of 2026-11-02, not contract text. The caller supplies ``profile_digest`` (P3.6b, A-6). Nothing here claims the P3.6 inference invariant; the path-identity
invariants are in tests/unit/test_path_identity.py and tests/golden/test_path_identity_pilot.py.
"""

import itertools

import pytest

from skillgraph.eligibility.evaluate import (
    EngineConfig,
    ExternalQualification,
    PostSchoolCredential,
    ProfileState,
    TargetDeclaration,
    UndecidedLevelUse,
    evaluate,
    identity_profile_digest,
)
from skillgraph.graph import (
    LimitExceededError,
    Scenario,
    ScenarioNotSupportedError,
    TargetNotEvaluableError,
    build_inference_edges,
    build_static_edges,
    enumerate_paths,
)
from skillgraph.model.eligibility import UnknownReasonCode as R
from skillgraph.model.eligibility import Verdict
from skillgraph.registry import Registry, UnknownEntityError, load

N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
IC, SMO, PS, SSMO = "AMH/Q0103", "AMH/Q0301", "AMH/Q2101", "AMH/Q2301"  # ascending qualification_id
PILOTS = (IC, SMO, PS, SSMO)
RANK = {N: 0, U: 1, C: 2, M: 3}


@pytest.fixture(scope="session")
def _registry(build_dir) -> Registry:
    return load(build_dir)


@pytest.fixture
def reg(_registry) -> Registry:
    assert _registry.build is not None and _registry.build.validation == "PASSED"
    return _registry


@pytest.fixture(scope="session")
def limits(settings) -> dict:
    """What the caller (a future façade) supplies: the validated Settings.paths values, unchanged."""
    return {"max_expansions": settings.paths.max_expansions, "max_steps_limit": settings.paths.max_steps_limit}


def P(*, age=30, grade=None, creds=None, held=None, ext=None, decl=()) -> ProfileState:
    return ProfileState(
        age_years=age, school_grade_passed=grade,
        post_school_credentials=None if creds is None else tuple(PostSchoolCredential(type=t) for t in creds),
        held_qualification_codes=held, external_qualifications=ext, declarations=tuple(decl))


def D(code, years=None, rel=None) -> TargetDeclaration:
    return TargetDeclaration(target_code=code, relevant_experience_years=years, relevant_prior_qualifications=rel)


def paths(reg, limits, state, *, max_steps=3, target=None, match="exact", scenario=None):
    return enumerate_paths(state, reg, EngineConfig(nsqf_level_match=match), scenario or Scenario(), max_steps, target,
                           profile_digest=identity_profile_digest(state), **limits)


def e07_state() -> ProfileState:
    return P(age=24, grade=10, creds=[], held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])])


# ---- the real build -----------------------------------------------------------------------------------------------------


def test_the_pilots_are_the_four_curated_qualifications_in_ascending_id_order(reg):
    curated = sorted(q.id for q in reg.qualifications() if q.coverage.value == "CURATED")
    assert curated == [f"qual:{c}" for c in PILOTS]
    assert all(q.eligibility is not None for q in reg.qualifications() if q.coverage.value == "CURATED")


def test_the_settings_limits_are_the_provisional_documented_values(limits):
    assert limits == {"max_expansions": 10000, "max_steps_limit": 4}  # config/default.yaml, PROVISIONAL


# ---- an empty profile: nothing can be NOT_MET ---------------------------------------------------------------------------------


def test_an_empty_profile_enters_every_pilot_and_gives_forty_unknown_paths_in_pre_order(reg, limits):
    got = paths(reg, limits, ProfileState(), max_steps=3, match=None)
    assert len(got) == 4 + 12 + 24 == 40
    assert got[0].target_codes == (IC,) and got[1].target_codes == (IC, SMO) and got[2].target_codes == (IC, SMO, PS)
    assert got[-1].target_codes == (SSMO, PS, SMO)
    assert [p.target_codes for p in got] == sorted(p.target_codes for p in got)
    assert {p.verdict for p in got} == {U}  # the age is undeclared in every step
    assert all(len(set(p.target_codes)) == len(p.steps) for p in got)


@pytest.mark.parametrize(("k", "count"), [(1, 4), (2, 16), (3, 40), (4, 64)])
def test_the_number_of_paths_follows_the_number_of_simple_prefixes(reg, limits, k, count):
    assert len(paths(reg, limits, ProfileState(), max_steps=k, match=None)) == count  # 4, 4+12, +24, +24


def test_the_empty_profile_unknown_steps_carry_a_reason_never_not_met(reg, limits):
    for p in paths(reg, limits, ProfileState(), max_steps=2, match=None):
        for s in p.steps:
            assert s.eligibility.verdict is U and s.eligibility.unknown_reasons


# ---- age 17, held pilots, targets ----------------------------------------------------------------------------------------------


def test_age_17_is_not_met_for_every_pilot_so_there_is_no_path(reg, limits):
    state = P(age=17, grade=12, creds=["UG_DIPLOMA"], held=[], ext=(), decl=[D(c, 30, []) for c in PILOTS])
    assert paths(reg, limits, state, max_steps=4) == []
    assert paths(reg, limits, state, max_steps=3, target=SSMO) == []


def test_a_pilot_below_the_printed_minimum_age_is_not_a_step_and_not_extended(reg, limits):
    # PS prints "Age: 20 years", the others 18: at age 19 PS is NOT_MET for a first step and is never a hypothetical holding
    state = P(age=19, grade=12, held=[], ext=(), decl=[D(c, 30, []) for c in PILOTS])
    got = paths(reg, limits, state, max_steps=3)
    assert got and all(PS not in p.target_codes for p in got)


def test_holding_every_pilot_leaves_nothing_to_enter(reg, limits):
    assert paths(reg, limits, P(held=list(PILOTS), ext=()), max_steps=4) == []


def test_p2_a_held_target_gives_an_empty_list(reg, limits):
    assert paths(reg, limits, e07_state(), target=SMO) == []


def test_p3_a_catalogue_only_target_is_refused_and_an_unknown_one_is_an_unknown_entity(reg, limits):
    catalogue = next(q.code for q in reg.qualifications() if q.coverage.value == "CATALOGUE_ONLY")
    with pytest.raises(TargetNotEvaluableError):
        paths(reg, limits, e07_state(), target=catalogue)
    with pytest.raises(UnknownEntityError):
        paths(reg, limits, e07_state(), target="AMH/Q9999")


def test_only_the_four_curated_pilots_ever_appear(reg, limits):
    seen = {c for p in paths(reg, limits, ProfileState(), max_steps=4, match=None) for c in p.target_codes}
    assert seen == set(PILOTS)


# ---- the E07 example profile (PROVISIONAL on Q-B) ------------------------------------------------------------------------------


def test_the_e07_profile_enters_ssmo_conditionally_exactly_as_the_evaluator_reports_it_provisional_q_b(reg, limits):
    got = {p.target_codes: p for p in paths(reg, limits, e07_state(), max_steps=3)}
    first = got[(SSMO,)]
    assert first.verdict is C  # ARCHITECTURE §11.5 / the E07 example, under COMPARE (PROVISIONAL)
    expected = evaluate(reg.qualification_by_code(SSMO).eligibility, e07_state(), EngineConfig(nsqf_level_match="exact"), reg,
                        undecided_level_use=UndecidedLevelUse.COMPARE)
    assert first.steps[0].eligibility == expected
    assert first.steps[0].from_state == (SMO,) and first.steps[0].index == 1
    assert all(SMO not in p.target_codes for p in got.values())  # held, so never a step
    assert len(got) == 3 + 6 + 6  # three candidates (IC, PS, SSMO), none NOT_MET for this profile


def test_every_step_equals_a_direct_evaluation_against_the_profile_plus_the_earlier_targets(reg, limits):
    state = e07_state()
    for p in paths(reg, limits, state, max_steps=3):
        for i, s in enumerate(p.steps):
            direct = evaluate(reg.qualification_by_code(s.target_code).eligibility, state, EngineConfig(nsqf_level_match="exact"),
                              reg, hypothetical_codes=p.target_codes[:i])
            assert s.eligibility == direct and s.eligibility.verdict is not N
            assert s.from_state == (SMO, *p.target_codes[:i])
        assert p.verdict is min((s.eligibility.verdict for s in p.steps), key=RANK.__getitem__)


def test_p1_the_target_result_is_the_filtered_full_result(reg, limits):
    everything = paths(reg, limits, e07_state(), max_steps=3)
    for t in (IC, PS, SSMO):
        assert paths(reg, limits, e07_state(), max_steps=3, target=t) == [p for p in everything if p.target_codes[-1] == t]


# ---- hypothetical relevance on the real rules (PROVISIONAL, TASKS P3.6 A-3 / O-4) ----------------------------------------------


def hypo_state() -> ProfileState:
    # both lists declared empty, so a first-step row 9 of SSMO ("Previous relevant Qualification of NSQF Level 2.5 || 3 year
    # relevant experience") fails definitely; the profile declares an EMPTY relevant list for SSMO
    return P(age=24, grade=10, creds=[], held=[], ext=(), decl=[D(SSMO, 3, [])])


def test_a_hypothetically_completed_smo_leaves_ssmo_row_9_unknown_not_not_met(reg, limits):
    got = {p.target_codes: p for p in paths(reg, limits, hypo_state(), max_steps=2)}
    alone = got[(SSMO,)].steps[0].eligibility
    after = got[(SMO, SSMO)].steps[1].eligibility

    def row9(res):
        return next(r for r in res.rows if r.s_no == 9)

    assert row9(alone).components[0].verdict is N  # nothing held: a definite failure of the level component
    c = row9(after).components[0]  # SMO (level 2.5) is hypothetically completed; its relevance cannot be declared
    assert c.verdict is U and c.unknown_reason.code is R.RELEVANCE_NOT_DECLARED
    assert ("path.hypothetically_completed_qualifications", (SMO,), "HYPOTHETICAL") in [
        (u.field, u.value, u.evidence_class.value) for u in c.inputs_used]
    assert ("qual:AMH/Q0301.nsqf_level", 2.5, "HYPOTHETICAL") in [(u.field, u.value, u.evidence_class.value) for u in c.inputs_used]
    # the profile is untouched: the same call with the profile alone reports no hypothetical input
    assert not [u for u in alone.rows[0].components[0].inputs_used if u.evidence_class.value == "HYPOTHETICAL"]


# ---- guard, validation and scenario with the real Settings values ------------------------------------------------------------


def test_the_real_guard_estimate_is_n_to_the_k_over_the_curated_not_held(reg):
    state = e07_state()  # SMO held: n = 3
    args = (state, reg, EngineConfig(nsqf_level_match="exact"), Scenario(), 3, None)
    digest = identity_profile_digest(state)
    assert enumerate_paths(*args, max_expansions=27, max_steps_limit=4, profile_digest=digest)
    with pytest.raises(LimitExceededError):
        enumerate_paths(*args, max_expansions=26, max_steps_limit=4, profile_digest=digest)


def test_max_steps_above_the_settings_hard_limit_is_refused(reg, limits):
    with pytest.raises(LimitExceededError):
        paths(reg, limits, e07_state(), max_steps=limits["max_steps_limit"] + 1)
    assert paths(reg, limits, e07_state(), max_steps=limits["max_steps_limit"])


def test_a_non_default_scenario_is_rejected_not_ignored(reg, limits):
    with pytest.raises(ScenarioNotSupportedError):
        paths(reg, limits, e07_state(), scenario=Scenario(assume_intermediate_relevance=True))


# ---- determinism, immutability, inference -------------------------------------------------------------------------------------


def test_repeated_and_reloaded_enumeration_is_byte_identical(reg, limits, build_dir):
    state = e07_state()
    a = [p.model_dump_json() for p in paths(reg, limits, state)]
    b = [p.model_dump_json() for p in paths(reg, limits, state)]
    c = [p.model_dump_json() for p in paths(load(build_dir), limits, state)]
    assert a == b == c and a


def test_enumeration_changes_neither_the_registry_nor_the_profile(reg, limits):
    state = e07_state()
    before_reg = [q.model_dump() for q in reg.qualifications()]
    before_state = state.model_dump()
    paths(reg, limits, state)
    paths(reg, limits, hypo_state())
    assert [q.model_dump() for q in reg.qualifications()] == before_reg
    assert state.model_dump() == before_state and state.held_qualification_codes == (SMO,)


@pytest.mark.parametrize("state", [ProfileState(), e07_state(), hypo_state()])
def test_building_the_static_and_inference_edges_changes_no_path_and_no_record(reg, limits, state):
    # Not the P3.6 inference invariant (there is no path_id yet): it shows that the edges, including the SMO-SSMO
    # NCO_GROUP_PROXIMITY inference edge of the real build, cannot create, remove or reorder paths or alter a record.
    before_paths = [p.model_dump_json() for p in paths(reg, limits, state, match=None if state == ProfileState() else "exact")]
    before_reg = [q.model_dump() for q in reg.qualifications()]
    static, inferred = build_static_edges(reg), build_inference_edges(reg)
    assert inferred and any({SMO, SSMO} <= {e.source.removeprefix("qual:"), e.target.removeprefix("qual:")} for e in inferred)
    after = [p.model_dump_json() for p in paths(reg, limits, state, match=None if state == ProfileState() else "exact")]
    assert after == before_paths and [q.model_dump() for q in reg.qualifications()] == before_reg
    assert static


def test_paths_do_not_depend_on_the_progression_claims_or_credits(reg, limits):
    # the evaluator never reads either (P3.3), and paths.py reads no registry field except coverage, code, id and rules
    rich = P(age=40, grade=12, creds=["UG_CERTIFICATE"], held=[SMO], ext=(ExternalQualification(ref="ext-x", label="X", nsqf_level=4.0),),
             decl=[D(c, 5, [SMO, "ext-x"]) for c in (IC, PS, SSMO)])
    got = paths(reg, limits, rich)
    assert got and all(p.target_codes == tuple(dict.fromkeys(p.target_codes)) for p in got)
    assert list(itertools.chain.from_iterable(p.target_codes for p in got)).count(SMO) == 0
