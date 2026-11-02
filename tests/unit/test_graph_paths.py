"""P3.6a path enumeration core (ARCHITECTURE §13.1; API_SPEC §4, E09; TASKS P3.6). Synthetic fixtures only: TEST/… codes.

Expected values are derived by hand from the documented rules and from the approved decisions:

* O-1 / O-2 (TASKS P3.6, approved 2026-11-02): the guard is ``n ** max_steps`` with ``n`` the ``CURATED`` qualifications not
  held, refused only when strictly greater than ``max_expansions``; argument types and ranges are checked first.
* P-1 to P-5 are explicit IMPLEMENTATION decisions of 2026-11-02, not contract text (prefixes are paths, depth-first
  pre-order, held target gives ``[]``, a ``CATALOGUE_ONLY`` target is refused, a ``CURATED`` record without rules raises,
  ``from_state`` is the declared holdings sorted then the earlier targets). The tests that pin them say so.
* The hypothetical-relevance outcome is PROVISIONAL (TASKS P3.6 A-3 / O-4); non-default scenarios are rejected by an internal
  limitation of P3.6a whose departure from E09 is UNRESOLVED (O-8).
"""

import ast
import inspect
from itertools import permutations
from pathlib import Path

import pytest
from model_factory import age_rule, catalogue_only, component, curated, ev, row
from pydantic import ValidationError

import skillgraph.graph.paths as paths_module
from skillgraph.eligibility.evaluate import EligibilityError, EngineConfig, ProfileState, TargetDeclaration
from skillgraph.graph import (
    IncrementalHoursPolicy,
    LimitExceededError,
    RawPath,
    RawStep,
    Scenario,
    ScenarioNotSupportedError,
    TargetNotEvaluableError,
    build_inference_edges,
    build_static_edges,
    enumerate_paths,
)
from skillgraph.graph.edges import GraphError
from skillgraph.model.eligibility import UnknownReasonCode as R
from skillgraph.model.eligibility import Verdict
from skillgraph.model.evidence import Evidence
from skillgraph.model.occupation import Occupation
from skillgraph.model.qualification import Qualification
from skillgraph.registry import Registry, UnknownEntityError

N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
SRC = Path(__file__).resolve().parents[2] / "src" / "skillgraph"
LIMITS = {"max_expansions": 10_000, "max_steps_limit": 4}  # the Settings.paths values, supplied by the caller
ORDER = {N: 0, U: 1, C: 2, M: 3}  # the verdict lattice of API_SPEC §2.1, written out independently of the code


def code(n: int) -> str:
    return f"TEST/Q900{n}"


def comp(kind: str):
    """Experience-only components, so a row's verdict depends only on the kind letter (declared experience is 2 years)."""
    if kind == "M":
        return component("EXPERIENCE_MIN_YEARS", params={"years": 0.0})
    if kind == "C":
        return component("EXPERIENCE_MIN_YEARS", params={"years": 2.0}, requires_relevance=True)
    if kind == "N":
        return component("EXPERIENCE_MIN_YEARS", params={"years": 5.0}, requires_relevance=True)
    if kind == "U":
        return component("UNMODELLED", params={}, safe=False, unknown_reason="REVIEW_FLAG")
    raise AssertionError(kind)


def qual(n: int, kind: str = "M", *, eligibility="rows", **kw) -> dict:
    spec = {"age_rule": {**age_rule(), "id": f"rule:{code(n)}/AGE"},
            "rows": [row(1, id=f"rule:{code(n)}/E1", raw_text="cell one || cell two", components=[comp(kind), comp("M")],
                         engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE", overlay_ids=[])]}
    return curated(id=f"qual:{code(n)}", code=code(n), slug=f"TEST.Q900{n}", nos_memberships=[], modules=[],
                   eligibility=spec if eligibility == "rows" else eligibility, **kw)


def cat(n: int = 99) -> dict:
    """A CATALOGUE_ONLY record with a code that no curated test record uses."""
    return catalogue_only(id=f"qual:TEST/Q90{n}", code=f"TEST/Q90{n}", slug=f"TEST.Q90{n}")


def occupations() -> list[Occupation]:
    return [Occupation.model_validate({"id": "nco:8153.0101", "nco_code": "8153.0101", "title_verification": "NOT_CHECKED"})]


EVIDENCE = [Evidence.model_validate({"id": ev(n), "evidence_class": "OFFICIAL", "source_id": "src:T1", "source_sha256": "0" * 64,
                                     "location": "QF item 13"}) for n in range(1, 21)]


def make(records: list[dict]) -> Registry:
    """Every synthetic curated record states the NCO code 8153.0101, so inference edges exist for the invariance test."""
    return Registry.from_records(qualifications=[Qualification.model_validate(d) for d in records],
                                 occupations=occupations(), evidence=EVIDENCE)


def world(kinds: dict[int, str], extra: list[dict] | None = None, *, order=None) -> Registry:
    ns = list(kinds) if order is None else list(order)
    return make([qual(n, kinds[n]) for n in ns] + (extra or []))


def profile(*, held=(), age=30, ns=range(1, 8), **kw) -> ProfileState:
    return ProfileState(age_years=age, held_qualification_codes=held, external_qualifications=(),
                        declarations=tuple(TargetDeclaration(target_code=code(n), relevant_experience_years=2) for n in ns),
                        **kw)


def enum(reg, *, state=None, max_steps=3, target=None, scenario=None, match="exact", **limits):
    kw = {**LIMITS, **limits}
    return enumerate_paths(state or profile(), reg, EngineConfig(nsqf_level_match=match), scenario or Scenario(), max_steps,
                           target, **kw)


def seqs(paths) -> list[tuple[str, ...]]:
    return [p.target_codes for p in paths]


def digits(paths) -> list[tuple[int, ...]]:
    return [tuple(int(c[-1]) for c in p.target_codes) for p in paths]


@pytest.fixture
def spy(monkeypatch):
    """Records every eligibility evaluation as the tuple of hypothetically completed codes it was given."""
    calls = []
    real = paths_module.evaluate

    def wrapped(spec, state, config, registry, **kw):
        calls.append(tuple(kw.get("hypothetical_codes", ())))
        return real(spec, state, config, registry, **kw)

    monkeypatch.setattr(paths_module, "evaluate", wrapped)
    return calls


# ---- the amended signature ---------------------------------------------------------------------------------------------


def test_the_signature_is_the_documented_one_with_required_keyword_only_limits():
    params = inspect.signature(enumerate_paths).parameters
    assert list(params) == ["state", "registry", "config", "scenario", "max_steps", "target_code",
                            "max_expansions", "max_steps_limit"]
    for name in ("state", "registry", "config", "scenario", "max_steps", "target_code"):
        assert params[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD and params[name].default is inspect.Parameter.empty
    for name in ("max_expansions", "max_steps_limit"):  # A-1: keyword-only, no default
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY and params[name].default is inspect.Parameter.empty


def test_the_limits_cannot_be_omitted_or_passed_positionally():
    reg = world({1: "M"})
    args = (profile(), reg, EngineConfig(), Scenario(), 1, None)
    with pytest.raises(TypeError):
        enumerate_paths(*args)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        enumerate_paths(*args, max_expansions=10)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        enumerate_paths(*args, 10, 4)  # type: ignore[call-arg]


# ---- enumeration, order, determinism -----------------------------------------------------------------------------------


def test_p1_every_prefix_is_a_path_in_depth_first_pre_order_with_ascending_expansion():
    got = digits(enum(world({1: "M", 2: "M", 3: "M"}), max_steps=2))
    assert got == [(1,), (1, 2), (1, 3), (2,), (2, 1), (2, 3), (3,), (3, 1), (3, 2)]  # written out by hand


def test_p1_depth_three_over_three_qualifications():
    got = digits(enum(world({1: "M", 2: "M", 3: "M"}), max_steps=3))
    assert len(got) == 3 + 6 + 6 and got[:3] == [(1,), (1, 2), (1, 2, 3)] and got[-1] == (3, 2, 1)
    assert got == sorted(got)  # pre-order over ascending candidates is lexicographic order


def test_max_steps_is_respected_and_one_step_gives_only_single_steps():
    reg = world({1: "M", 2: "M", 3: "M"})
    assert digits(enum(reg, max_steps=1)) == [(1,), (2,), (3,)]
    assert max(len(p.steps) for p in enum(reg, max_steps=2)) == 2


def test_no_qualification_is_repeated_and_held_ones_are_never_steps():
    reg = world({1: "M", 2: "M", 3: "M", 4: "M"})
    for p in enum(reg, state=profile(held=(code(2),)), max_steps=3):
        assert len(set(p.target_codes)) == len(p.steps) and code(2) not in p.target_codes


def test_expansion_order_does_not_depend_on_registry_construction_order():
    base = digits(enum(world({1: "M", 2: "M", 3: "M"}), max_steps=3))
    for order in permutations([1, 2, 3]):
        assert digits(enum(world({1: "M", 2: "M", 3: "M"}, order=order), max_steps=3)) == base


def test_two_runs_give_identical_serialised_output():
    reg = world({1: "M", 2: "C", 3: "U", 4: "N"})
    a = [p.model_dump_json() for p in enum(reg)]
    b = [p.model_dump_json() for p in enum(reg)]
    assert a == b and a  # byte-identical, non-empty


def test_only_curated_qualifications_are_steps():
    reg = world({1: "M", 2: "M"}, extra=[cat()])
    assert {c for p in enum(reg) for c in p.target_codes} == {code(1), code(2)}  # TEST/Q9099 is CATALOGUE_ONLY


# ---- NOT_MET steps ------------------------------------------------------------------------------------------------------


def test_a_not_met_step_is_neither_emitted_nor_extended(spy):
    reg = world({1: "M", 2: "N", 3: "M"})
    got = digits(enum(reg, max_steps=3))
    assert got == [(1,), (1, 3), (3,), (3, 1)]
    assert all(2 not in g for g in got)
    # never extended: no evaluation ever assumed the NOT_MET qualification completed
    assert all(code(2) not in assumed for assumed in spy)


def test_a_qualification_not_met_at_the_start_can_be_reached_after_an_earlier_step():
    # TEST/Q9002 requires a prior level; with both holding lists declared empty it is NOT_MET as a first step, but a
    # hypothetically completed TEST/Q9001 satisfies the level, so (1, 2) is a path (PROVISIONAL relevance: UNKNOWN).
    prior = component("PRIOR_NSQF_LEVEL", params={"level": 2.5}, requires_relevance=True)
    d2 = qual(2)
    d2["eligibility"]["rows"][0]["components"] = [prior, comp("M")]
    reg = make([qual(1), d2])
    got = enum(reg, max_steps=2, match="exact")
    assert digits(got) == [(1,), (1, 2)]  # (2,) alone is NOT_MET and absent
    last = got[1].steps[1].eligibility
    assert last.verdict is U and last.rows[0].components[0].unknown_reason.code is R.RELEVANCE_NOT_DECLARED
    assert got[1].verdict is U  # the path inherits its weakest step; never NOT_MET


# ---- the path verdict --------------------------------------------------------------------------------------------------


def test_the_path_verdict_is_the_and_of_its_step_verdicts():
    reg = world({1: "M", 2: "C", 3: "U", 4: "M"})
    got = enum(reg, max_steps=3)
    assert got
    seen = set()
    for p in got:
        steps = [s.eligibility.verdict for s in p.steps]
        assert p.verdict is min(steps, key=ORDER.__getitem__)  # independent recomputation: the weakest step
        assert N not in steps
        seen.add(p.verdict)
    assert seen == {M, C, U}


def test_hand_written_verdict_examples():
    reg = world({1: "M", 2: "C", 3: "U"})
    by = {digits([p])[0]: p.verdict for p in enum(reg, max_steps=2)}
    assert by[(1,)] is M and by[(2,)] is C and by[(3,)] is U
    assert by[(1, 2)] is C and by[(2, 1)] is C and by[(1, 3)] is U and by[(2, 3)] is U and by[(3, 2)] is U


def test_raw_models_enforce_their_invariants():
    reg = world({1: "M", 2: "M"})
    p = enum(reg, max_steps=2)[1]  # (1, 2)
    s1, s2 = p.steps
    with pytest.raises(ValidationError, match="AND of its step verdicts"):
        RawPath(steps=p.steps, verdict=U)
    with pytest.raises(ValidationError, match="never repeated"):
        RawPath(steps=(s1, s1.model_copy(update={"index": 2})), verdict=M)
    with pytest.raises(ValidationError, match="indexes"):
        RawPath(steps=(s2,), verdict=M)
    with pytest.raises(ValidationError):
        RawPath(steps=(), verdict=M)
    with pytest.raises(ValidationError, match="already held"):
        RawStep(index=1, from_state=(code(1),), target_code=code(1), eligibility=s1.eligibility)
    with pytest.raises(ValidationError, match="another qualification"):
        RawStep(index=1, from_state=(), target_code=code(2), eligibility=s1.eligibility)
    not_met = world({1: "N"})
    from skillgraph.eligibility.evaluate import evaluate  # the evaluator, to obtain a genuine NOT_MET result
    res = evaluate(not_met.qualification_by_code(code(1)).eligibility, profile(), EngineConfig(), not_met)
    assert res.verdict is N
    with pytest.raises(ValidationError, match="NOT_MET step"):
        RawStep(index=1, from_state=(), target_code=code(1), eligibility=res)
    assert RawPath.model_validate_json(p.model_dump_json()) == p  # serialisable and round-trips


def test_extra_fields_are_refused_so_later_stage_fields_cannot_creep_in():
    p = enum(world({1: "M"}), max_steps=1)[0]
    assert set(RawPath.model_fields) == {"steps", "verdict"}
    assert set(RawStep.model_fields) == {"index", "from_state", "target_code", "eligibility"}
    with pytest.raises(ValidationError):
        RawPath(steps=p.steps, verdict=p.verdict, path_id="p-3c9e0a1b2d4f")  # type: ignore[call-arg]


# ---- the guard ---------------------------------------------------------------------------------------------------------


def test_the_guard_accepts_equality_and_refuses_budget_plus_one_before_any_evaluation(spy):
    reg = world({1: "M", 2: "M", 3: "M"})  # n = 3, k = 3: estimate 27
    assert len(enum(reg, max_steps=3, max_expansions=27)) == 15
    spy.clear()
    with pytest.raises(LimitExceededError, match="27"):
        enum(reg, max_steps=3, max_expansions=26)
    assert spy == []  # the guard runs before any eligibility evaluation


@pytest.mark.parametrize(("n", "k"), [(2, 1), (2, 2), (3, 1), (3, 2), (4, 3), (4, 4), (5, 2)])
def test_the_estimate_is_n_to_the_k_with_n_the_curated_qualifications_not_held(n, k, spy):
    reg = world({i: "M" for i in range(1, n + 1)}, extra=[cat()])  # a CATALOGUE_ONLY record is not counted
    enum(reg, max_steps=k, max_steps_limit=4, max_expansions=n**k)
    spy.clear()
    with pytest.raises(LimitExceededError):
        enum(reg, max_steps=k, max_steps_limit=4, max_expansions=n**k - 1)
    assert spy == []


def test_held_qualifications_reduce_n(spy):
    reg = world({1: "M", 2: "M", 3: "M", 4: "M"})
    state = profile(held=(code(1),))
    enum(reg, state=state, max_steps=3, max_expansions=27)  # n = 3, not 4 (64)
    with pytest.raises(LimitExceededError):
        enum(reg, state=state, max_steps=3, max_expansions=26)
    with pytest.raises(LimitExceededError):
        enum(reg, max_steps=3, max_expansions=63)  # nothing held: n = 4, 4**3 = 64


def test_the_estimate_is_a_conservative_bound_on_the_evaluations_actually_made(spy):
    for n, k in ((1, 3), (2, 3), (3, 3), (4, 2), (4, 4)):
        spy.clear()
        enum(world({i: "M" for i in range(1, n + 1)}), max_steps=k, max_expansions=n**k)
        assert len(spy) <= n**k


def test_a_controlled_limit_is_really_exceeded_on_a_larger_registry():
    reg = world({i: "M" for i in range(1, 7)})  # n = 6
    with pytest.raises(LimitExceededError):
        enum(reg, max_steps=4, max_expansions=1_295)  # 6**4 = 1296
    assert len(enum(reg, max_steps=4, max_expansions=1_296)) == 6 + 30 + 120 + 360


def test_the_guard_does_not_depend_on_the_target_or_on_eligibility_outcomes(spy):
    reg = world({1: "N", 2: "N", 3: "N"})  # every qualification is NOT_MET: still 3**3 = 27 estimated
    with pytest.raises(LimitExceededError):
        enum(reg, max_steps=3, max_expansions=26, target=code(1))
    assert enum(reg, max_steps=3, max_expansions=27) == []


# ---- argument validation -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [True, False, 3.0, "3", None, 2.5])
def test_max_steps_must_be_an_int_and_not_a_bool(bad, spy):
    with pytest.raises(TypeError, match="max_steps"):
        enum(world({1: "M"}), max_steps=bad)
    assert spy == []


@pytest.mark.parametrize("bad", [0, -1, -10])
def test_max_steps_below_one_is_a_value_error(bad, spy):
    with pytest.raises(ValueError, match="max_steps must be at least 1"):
        enum(world({1: "M"}), max_steps=bad)
    assert spy == []


def test_max_steps_above_the_hard_limit_is_a_limit_error_and_the_boundary_is_allowed(spy):
    reg = world({1: "M", 2: "M"})
    assert enum(reg, max_steps=4, max_steps_limit=4)  # equal to the limit is allowed
    with pytest.raises(LimitExceededError, match="hard limit 4"):
        enum(reg, max_steps=5, max_steps_limit=4)
    assert enum(reg, max_steps=1, max_steps_limit=1)
    with pytest.raises(LimitExceededError):
        enum(reg, max_steps=2, max_steps_limit=1)


@pytest.mark.parametrize("name", ["max_expansions", "max_steps_limit"])
@pytest.mark.parametrize("bad", [True, 4.0, "4", None])
def test_the_limits_must_be_ints_and_not_bools(name, bad, spy):
    with pytest.raises(TypeError, match=name):
        enum(world({1: "M"}), max_steps=1, **{name: bad})
    assert spy == []


@pytest.mark.parametrize("name", ["max_expansions", "max_steps_limit"])
@pytest.mark.parametrize("bad", [0, -1])
def test_the_limits_must_be_positive(name, bad, spy):
    with pytest.raises(ValueError, match=f"{name} must be at least 1"):
        enum(world({1: "M"}), max_steps=1, **{name: bad})
    assert spy == []


def test_arguments_are_validated_before_the_registry_is_consulted(spy):
    reg = world({1: "M"})
    with pytest.raises(ValueError):  # not UnknownEntityError for the target
        enum(reg, max_steps=0, target="TEST/Q9099")
    with pytest.raises(TypeError):
        enum(reg, max_steps=True, scenario=Scenario(assume_intermediate_relevance=True))  # not ScenarioNotSupportedError
    with pytest.raises(LimitExceededError):
        enum(reg, max_steps=9, target="TEST/Q9099")
    assert spy == []


@pytest.mark.parametrize(("name", "bad"), [("state", None), ("registry", None), ("config", None), ("scenario", None),
                                           ("scenario", {}), ("state", {})])
def test_wrong_object_types_are_type_errors(name, bad, spy):
    args = {"state": profile(), "registry": world({1: "M"}), "config": EngineConfig(), "scenario": Scenario()}
    args[name] = bad
    with pytest.raises(TypeError, match=name):
        enumerate_paths(args["state"], args["registry"], args["config"], args["scenario"], 1, None, **LIMITS)
    assert spy == []


def test_target_code_must_be_a_string_or_none():
    with pytest.raises(TypeError, match="target_code"):
        enum(world({1: "M"}), max_steps=1, target=5)


# ---- the target (P-1 .. P-4) --------------------------------------------------------------------------------------------


def test_p1_with_a_target_only_paths_ending_at_it_are_returned_and_stopping_changes_nothing():
    reg = world({1: "M", 2: "M", 3: "M", 4: "M"})
    everything = enum(reg, max_steps=3)
    for t in (1, 2, 4):
        expected = [p for p in everything if p.target_codes[-1] == code(t)]  # filtering the full result
        got = enum(reg, max_steps=3, target=code(t))
        assert got == expected and got  # identical paths, identical order
        assert all(p.target_codes[-1] == code(t) and p.target_codes.count(code(t)) == 1 for p in got)


def test_p1_a_target_path_of_every_length_up_to_max_steps_is_returned():
    got = digits(enum(world({1: "M", 2: "M", 3: "M"}), max_steps=3, target=code(3)))
    assert got == [(1, 2, 3), (1, 3), (2, 1, 3), (2, 3), (3,)]


def test_a_not_met_target_gives_no_path():
    assert enum(world({1: "M", 2: "N"}), max_steps=2, target=code(2)) == []


def test_p2_a_held_target_gives_an_empty_list_without_evaluating(spy):
    reg = world({1: "M", 2: "M"})
    assert enum(reg, state=profile(held=(code(1),)), target=code(1)) == []
    assert spy == []


def test_p3_an_unknown_target_raises_unknown_entity_error(spy):
    with pytest.raises(UnknownEntityError):
        enum(world({1: "M"}), target="TEST/Q9099")
    assert spy == []


def test_p3_a_catalogue_only_target_is_refused_before_any_evaluation(spy):
    reg = world({1: "M"}, extra=[cat()])
    with pytest.raises(TargetNotEvaluableError, match="TEST/Q9099"):
        enum(reg, target="TEST/Q9099")
    assert spy == [] and issubclass(TargetNotEvaluableError, GraphError)


def test_p4_a_curated_qualification_without_rules_raises_and_is_never_skipped(spy):
    d3 = qual(3)
    d3["eligibility"] = None
    reg = make([qual(1), qual(2), d3])
    with pytest.raises(EligibilityError, match="TEST/Q9003"):
        enum(reg)
    assert spy == []
    # held, it is not a candidate and does not matter
    assert enum(reg, state=profile(held=(code(3),)), max_steps=1)


def test_an_unknown_held_code_raises_unknown_entity_error():
    with pytest.raises(UnknownEntityError):
        enum(world({1: "M"}), state=profile(held=("TEST/Q9099",)))


# ---- from_state (P-5) and the immutability of the inputs ---------------------------------------------------------------


def test_p5_from_state_is_the_declared_holdings_sorted_then_the_earlier_targets_in_step_order():
    reg = world({1: "M", 2: "M", 3: "M", 4: "M", 5: "M"})
    state = profile(held=(code(4), code(1)))  # declared in descending order on purpose
    got = [p for p in enum(reg, state=state, max_steps=3) if p.target_codes == (code(5), code(3), code(2))]
    assert len(got) == 1
    assert [s.from_state for s in got[0].steps] == [
        (code(1), code(4)), (code(1), code(4), code(5)), (code(1), code(4), code(5), code(3))]
    assert [s.index for s in got[0].steps] == [1, 2, 3]


def test_the_profile_and_the_registry_records_are_not_changed_and_hypothetical_holdings_stay_out_of_the_profile():
    reg = world({1: "M", 2: "C", 3: "U"})
    state = profile(held=(code(3),))
    before_state, before_reg = state.model_dump(), [q.model_dump() for q in reg.qualifications()]
    enum(reg, state=state, max_steps=3)
    assert state.model_dump() == before_state and state.held_qualification_codes == (code(3),)
    assert [q.model_dump() for q in reg.qualifications()] == before_reg


# ---- hypothetical relevance on paths (PROVISIONAL, O-4) -----------------------------------------------------------------


def test_a_later_step_that_needs_the_earlier_one_is_unknown_not_not_met_even_when_a_declared_list_excludes_it():
    prior = component("PRIOR_NSQF_LEVEL", params={"level": 2.5}, requires_relevance=True)
    d2 = qual(2)
    d2["eligibility"]["rows"][0]["components"] = [prior, comp("M")]
    reg = make([qual(1), d2, qual(3)])
    state = ProfileState(age_years=30, held_qualification_codes=(code(3),), external_qualifications=(),
                         declarations=(TargetDeclaration(target_code=code(2), relevant_prior_qualifications=()),))
    # TEST/Q9003 is held, satisfies level 2.5 and is declared NOT relevant (an empty list) for TEST/Q9002
    got = {digits([p])[0]: p for p in enum(reg, state=state, max_steps=2, match="exact")}
    assert (2,) not in got  # as a first step it is NOT_MET: the only satisfying holding is declared not relevant
    assert (1, 2) in got and got[(1, 2)].verdict is U  # after TEST/Q9001 the hypothetical holding's relevance is undeclared


# ---- scenario ----------------------------------------------------------------------------------------------------------


def test_the_default_scenario_is_the_schema_default():
    s = Scenario()
    assert (s.assume_intermediate_relevance, s.assumed_experience_gain_years_per_step, s.incremental_hours_policy) == (
        False, 0, IncrementalHoursPolicy.NONE)
    assert enum(world({1: "M"}), max_steps=1, scenario=Scenario(assumed_experience_gain_years_per_step=0.0))


@pytest.mark.parametrize(("scenario", "field"), [
    (Scenario(assume_intermediate_relevance=True), "assume_intermediate_relevance"),
    (Scenario(assumed_experience_gain_years_per_step=0.5), "assumed_experience_gain_years_per_step"),
    (Scenario(assumed_experience_gain_years_per_step=5), "assumed_experience_gain_years_per_step"),
    (Scenario(incremental_hours_policy="EXCLUDE_SHARED_NOS_CODE"), "incremental_hours_policy"),
    (Scenario(incremental_hours_policy=IncrementalHoursPolicy.EXCLUDE_SHARED_NOS_CODE_AND_VERSION), "incremental_hours_policy"),
])
def test_a_non_default_scenario_is_rejected_explicitly_and_never_ignored(scenario, field, spy):
    with pytest.raises(ScenarioNotSupportedError, match=field):
        enum(world({1: "M"}), max_steps=1, scenario=scenario)
    assert spy == [] and issubclass(ScenarioNotSupportedError, GraphError)


def test_the_scenario_schema_follows_api_spec_2_3():
    for bad in (-0.1, 5.1, True, "2"):
        with pytest.raises(ValidationError):
            Scenario(assumed_experience_gain_years_per_step=bad)
    for bad in ("yes", 1, None):
        with pytest.raises(ValidationError):
            Scenario(assume_intermediate_relevance=bad)
    with pytest.raises(ValidationError):
        Scenario(incremental_hours_policy="SOMETHING")
    with pytest.raises(ValidationError):
        Scenario(unknown_field=1)  # type: ignore[call-arg]
    assert {m.value for m in IncrementalHoursPolicy} == {"NONE", "EXCLUDE_SHARED_NOS_CODE", "EXCLUDE_SHARED_NOS_CODE_AND_VERSION"}


# ---- inference cannot influence paths; boundaries ---------------------------------------------------------------------


def test_building_edges_and_inference_edges_changes_neither_the_registry_nor_the_paths():
    reg = world({1: "M", 2: "C", 3: "U", 4: "M"})
    before_paths = [p.model_dump_json() for p in enum(reg, max_steps=3)]
    before_reg = [q.model_dump() for q in reg.qualifications()]
    static = build_static_edges(reg)
    inferred = build_inference_edges(reg)  # every synthetic record states the same NCO code: inference edges exist
    assert inferred, "the fixture must actually produce inference edges for this test to mean anything"
    assert [p.model_dump_json() for p in enum(reg, max_steps=3)] == before_paths
    assert [q.model_dump() for q in reg.qualifications()] == before_reg
    assert static is not None and len(static) == len(build_static_edges(reg))  # static edges are unaffected too


def test_the_enumerator_has_no_inference_input_and_reads_no_edge_module_symbol():
    assert not [p for p in inspect.signature(enumerate_paths).parameters if "inference" in p or "edge" in p]
    tree = ast.parse((SRC / "graph" / "paths.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree)
                                                                        if isinstance(n, ast.Attribute)}
    assert not names & {"build_inference_edges", "build_static_edges", "inference_legend", "static_legend", "GraphEdge",
                        "EdgeType", "INFERENCE_EDGE_TYPES", "STATIC_EDGE_TYPES", "claim_title_candidates"}


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            found |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            found.add(n.module)
        elif isinstance(n, ast.ImportFrom) and n.level:
            found.add("." * n.level + (n.module or ""))
    return found


def test_paths_py_imports_only_model_registry_eligibility_and_the_graph_error_base():
    imported = _imports(SRC / "graph" / "paths.py")
    internal = {m for m in imported if m.startswith("skillgraph") or m.startswith(".")}
    allowed = ("skillgraph.model", "skillgraph.registry", "skillgraph.eligibility", "skillgraph.graph.edges")
    assert internal and all(any(m == a or m.startswith(a + ".") for a in allowed) for m in internal), internal
    forbidden = ("skillgraph.settings", "skillgraph.curation", "skillgraph.api", "skillgraph.labour", "skillgraph.services",
                 "skillgraph.cli", "skillgraph.graph.inference", "skillgraph.graph.claim_candidates", "anthropic", "openai",
                 "requests", "httpx", "urllib", "socket", "random", "yaml", "os", "pathlib")
    assert not [m for m in imported if m == "settings" or m.startswith(forbidden)], imported
    from_edges = [n for n in ast.walk(ast.parse((SRC / "graph" / "paths.py").read_text(encoding="utf-8")))
                  if isinstance(n, ast.ImportFrom) and n.module == "skillgraph.graph.edges"]
    assert [a.name for n in from_edges for a in n.names] == ["GraphError"]


@pytest.mark.parametrize("name", ["edges.py", "inference.py", "claim_candidates.py"])
def test_no_other_graph_module_imports_eligibility(name):
    assert not [m for m in _imports(SRC / "graph" / name) if m.startswith("skillgraph.eligibility")]


def test_eligibility_modules_still_do_not_import_the_graph():
    for path in (SRC / "eligibility").glob("*.py"):
        assert not [m for m in _imports(path) if m.startswith("skillgraph.graph")], path.name


def test_the_module_has_no_default_for_the_limits_and_no_settings_value():
    src = (SRC / "graph" / "paths.py").read_text(encoding="utf-8")
    assert "10000" not in src and "10_000" not in src and "max_steps_default" not in src
