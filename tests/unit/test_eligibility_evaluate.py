"""P3.3 qualification-level evaluator (ARCHITECTURE §11.1-§11.3; API_SPEC §2.4; TASKS P3.3). Synthetic fixtures only:
TEST/… codes, a registry assembled with ``Registry.from_records``, no file, no real data.

Expected values are derived from the documented contract (the verdict lattice, the §11.2 table, the API_SPEC §2.4 result
rules), not copied from the evaluator's output. The choices the specification leaves open are D-1 … D-6 in
``skillgraph.eligibility.evaluate``; a test that depends on one says so. Tests marked PROVISIONAL-Q-B depend on the open
Q-B decision (docs/decisions/P3_2_AUDIT.md) and are written so that BOTH readings are asserted.
"""

import ast
import itertools
from pathlib import Path

import pytest
from model_factory import CODE, age_rule, component, curated, ev, official, row
from pydantic import ValidationError

from skillgraph.eligibility.components import ConditionKind
from skillgraph.eligibility.evaluate import (
    EligibilityError,
    EligibilityResult,
    EngineConfig,
    ExternalQualification,
    PostSchoolCredential,
    ProfileState,
    TargetDeclaration,
    UndecidedLevelUse,
    evaluate,
)
from skillgraph.model.eligibility import UnknownReasonCode as R
from skillgraph.model.eligibility import Verdict
from skillgraph.model.qualification import Qualification
from skillgraph.registry import Registry, UnknownEntityError

N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
HELD1, HELD2 = "TEST/Q9002", "TEST/Q9003"
DECL_EXP = f"declarations[{CODE}].relevant_experience_years"
DECL_PRIOR = f"declarations[{CODE}].relevant_prior_qualifications"


# ---- fixtures ---------------------------------------------------------------------------------------------------------


def comp(kind: str):
    """A component whose verdict does not depend on anything but the declared experience (2 years) and the safe flag."""
    if kind == "M":  # zero years required: nothing to declare
        return component("EXPERIENCE_MIN_YEARS", params={"years": 0.0})
    if kind == "C":  # 2 years required, 2 declared: CONDITIONAL on relevance
        return component("EXPERIENCE_MIN_YEARS", params={"years": 2.0}, requires_relevance=True)
    if kind == "N":  # 5 years required, 2 declared
        return component("EXPERIENCE_MIN_YEARS", params={"years": 5.0}, requires_relevance=True)
    if kind == "U":
        return component("UNMODELLED", params={}, safe=False, unknown_reason="REVIEW_FLAG")
    raise AssertionError(kind)


def mkrow(s_no: int, first: str, second: str = "M", **kw) -> dict:
    return row(s_no, raw_text=f"cell one of {s_no} || cell two of {s_no}", components=[comp(first), comp(second)],
               engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE", overlay_ids=[], **kw)


def held_qual(n: int, level: float = 2.5, *, engine_use="SAFE_HARD_RULE", status="TRANSCRIBED", claims=(), **extra) -> dict:
    code = f"TEST/Q900{n}"
    return curated(id=f"qual:{code}", code=code, slug=f"TEST.Q900{n}", titles={"qf": f"Held Qualification {n}"},
                   nsqf_level=official(level, 10 + n, engine_use=engine_use, status=status, **extra),
                   nos_memberships=[], modules=[], eligibility=None,
                   progression_claims=[{"id": f"claim:{code}/P{i}", "qualification_id": f"qual:{code}",
                                        "text_verbatim": text, "direction_label": "Vertical", "evidence_id": ev(30 + i)}
                                       for i, text in enumerate(claims, start=1)])


def make(rows=None, age=None, *holdings: dict, credits=4.0) -> tuple[Registry, Qualification]:
    spec = {"age_rule": age or age_rule(), "rows": rows if rows is not None else [mkrow(1, "M")]}
    target = curated(eligibility=spec, credits=official(credits, 1, engine_use="NOT_USED"), nos_memberships=[], modules=[])
    reg = Registry.from_records(qualifications=[Qualification.model_validate(d) for d in (target, *holdings)])
    return reg, reg.qualification_by_code(CODE)


def run(reg, q, state=None, match=None, **kw) -> EligibilityResult:
    declared = profile()
    return evaluate(q.eligibility, state or declared, EngineConfig(nsqf_level_match=match), reg, **kw)


def profile(**kw) -> ProfileState:
    kw.setdefault("age_years", 30)
    kw.setdefault("declarations", (TargetDeclaration(target_code=CODE, relevant_experience_years=2),))
    return ProfileState(**kw)


# ---- AND(age, OR(rows)) -----------------------------------------------------------------------------------------------

# (age declared?, age in years, verdict of each row's first component, expected target verdict). The second component of
# every row is MET, so a row's verdict is its first component's. Written out by hand from ARCHITECTURE §11.1.
TARGET_CASES = [
    (30, "M", M), (30, "C", C), (30, "U", U), (30, "N", N),                       # one row
    (30, "MCUN", M), (30, "CUN", C), (30, "UN", U), (30, "NN", N),                 # OR = the best row
    (17, "M", N), (17, "C", N), (17, "U", N), (17, "N", N),                        # age fails: a definite failure wins
    (None, "M", U), (None, "C", U), (None, "U", U), (None, "N", N),                # age unknown never lets a row pass
    (17, "MCUN", N), (None, "MCUN", U), (18, "M", M), (18, "NU", U),
]


@pytest.mark.parametrize(("age", "rows", "expected"), TARGET_CASES)
def test_the_target_verdict_is_and_of_age_with_or_of_rows(age, rows, expected):
    reg, q = make([mkrow(i, k) for i, k in enumerate(rows, start=1)])
    res = run(reg, q, profile(age_years=age))
    assert res.verdict is expected
    assert [r.verdict.value for r in res.rows] == [{"M": "MET", "C": "CONDITIONAL", "U": "UNKNOWN", "N": "NOT_MET"}[k] for k in rows]


@pytest.mark.parametrize(("first", "second", "expected"), [
    ("M", "N", N), ("N", "M", N), ("U", "N", N), ("N", "U", N),   # one definite failure fails the conjunction
    ("U", "M", U), ("M", "U", U), ("C", "U", U),                   # an unknown never becomes a pass
    ("C", "M", C), ("M", "C", C), ("C", "C", C), ("M", "M", M),
])
def test_a_row_is_the_and_of_its_components(first, second, expected):
    reg, q = make([mkrow(1, first, second)])
    assert run(reg, q).rows[0].verdict is expected


def test_decisive_rows_are_the_rows_that_attain_the_target_verdict():
    reg, q = make([mkrow(1, "N"), mkrow(2, "C"), mkrow(3, "U"), mkrow(4, "C")])
    res = run(reg, q)
    assert res.verdict is C
    assert res.decisive_rule_ids == (f"rule:{CODE}/E2", f"rule:{CODE}/E4")


def test_every_row_is_decisive_when_the_target_is_not_met():
    reg, q = make([mkrow(1, "N"), mkrow(2, "N")])
    res = run(reg, q)
    assert res.verdict is N and res.decisive_rule_ids == (f"rule:{CODE}/E1", f"rule:{CODE}/E2")
    assert res.unknown_reasons == ()


def test_d2_when_only_the_age_limits_the_target_no_row_attains_the_verdict():
    reg, q = make([mkrow(1, "C")])
    res = run(reg, q, profile(age_years=None))  # age unknown, the row is CONDITIONAL: AND = UNKNOWN
    assert res.verdict is U and res.decisive_rule_ids == ()
    assert [u.code for u in res.unknown_reasons] == [R.INPUT_NOT_DECLARED]
    assert res.unknown_reasons[0].ref == f"rule:{CODE}/AGE#c1" and res.age.verdict is U


def test_d4_an_unknown_target_lists_the_age_reason_then_each_unknown_component_of_the_decisive_rows():
    reg, q = make([mkrow(1, "U", "U"), mkrow(2, "C"), mkrow(3, "U")])
    res = run(reg, q, profile(age_years=None))
    assert res.verdict is U and res.decisive_rule_ids == (f"rule:{CODE}/E1", f"rule:{CODE}/E3")
    assert [u.ref for u in res.unknown_reasons] == [f"rule:{CODE}/AGE#c1", f"rule:{CODE}/E1#c1", f"rule:{CODE}/E1#c2",
                                                    f"rule:{CODE}/E3#c1"]
    assert all(u.code is R.REVIEW_FLAG for u in res.unknown_reasons[1:])


def test_only_an_unknown_target_carries_target_level_unknown_reasons():
    reg, q = make([mkrow(1, "U"), mkrow(2, "C")])
    res = run(reg, q)  # CONDITIONAL beats UNKNOWN; the unknown row is not decisive
    assert res.verdict is C and res.unknown_reasons == ()
    assert res.rows[0].components[0].unknown_reason.code is R.REVIEW_FLAG  # still visible on the row


def test_a_specification_without_rows_is_refused_not_guessed_d1():
    reg, q = make([])
    with pytest.raises(EligibilityError, match="without rows"):
        run(reg, q)


def test_missing_age_and_missing_declarations_are_unknown_never_pass_or_fail():
    reg, q = make([mkrow(1, "C")])
    res = evaluate(q.eligibility, ProfileState(), EngineConfig(), reg)
    assert res.age.verdict is U and res.age.unknown_reason.code is R.INPUT_NOT_DECLARED
    assert res.rows[0].components[0].verdict is U  # experience not declared
    assert res.verdict is U


# ---- conditions (D-3) -------------------------------------------------------------------------------------------------


def test_target_conditions_are_the_union_over_decisive_rows_deduplicated_and_sorted_by_key():
    reg, q = make([mkrow(1, "C", "C"), mkrow(2, "C"), mkrow(3, "N")])
    res = run(reg, q)
    assert res.verdict is C
    assert [(c.kind, c.key, c.value) for c in res.conditions] == [(ConditionKind.DECLARATION, DECL_EXP, 2.0)]  # 3 sources, 1 entry
    keys = [c.key for c in res.conditions]
    assert keys == sorted(keys)
    assert res.quality_flags[0].code.value == "DEPENDS_ON_DECLARATION"


def prior_row(s_no, level):
    return row(s_no, raw_text=f"prior level {level} || {s_no} years", engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG",
               overlay_ids=[], components=[component("PRIOR_NSQF_LEVEL", params={"level": level}, requires_relevance=True),
                                           comp("M")])


def test_the_config_condition_reaches_the_target_list_though_the_component_result_carries_one_condition():
    # P3.2 audit A-1 / P3.3 obligation: the target list is built from ComponentOutcome.conditions, not .condition
    reg, q = make([prior_row(1, 2.5)], None, held_qual(2, 2.5))
    res = run(reg, q, profile(held_qualification_codes=(HELD1,), external_qualifications=(),
                              declarations=(TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1,)),)),
              match="exact")
    assert res.verdict is C
    component_result = res.rows[0].components[0]
    assert component_result.condition.kind is ConditionKind.DECLARATION  # the single API condition
    assert {(c.kind, c.key, c.value) for c in res.conditions} == {
        (ConditionKind.CONFIG, "config.nsqf_level_match", "exact"),
        (ConditionKind.DECLARATION, DECL_PRIOR, (HELD1,)),
    }
    assert [c.key for c in res.conditions] == ["config.nsqf_level_match", DECL_PRIOR]  # sorted by key
    assert {f.code.value for f in res.quality_flags} == {"DEPENDS_ON_DECLARATION", "DEPENDS_ON_CONFIG"}
    assert any(u.field == "config.nsqf_level_match" for u in component_result.inputs_used)


def test_two_conditions_with_one_key_and_different_values_are_both_kept():
    reg, q = make([prior_row(1, 3.0), prior_row(2, 2.5)], None, held_qual(2, 2.5), held_qual(3, 3.0))
    both = TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1, HELD2))
    res = run(reg, q, profile(held_qualification_codes=(HELD1, HELD2), external_qualifications=(), declarations=(both,)),
              match="at_least")
    values = [c.value for c in res.conditions if c.key == DECL_PRIOR]
    assert sorted(values) == [(HELD1, HELD2), (HELD2,)]  # level 3: only Q9003; level 2.5: both


def test_conditions_do_not_depend_on_row_or_profile_order():
    reg, q = make([prior_row(1, 2.5), mkrow(2, "C")], None, held_qual(2, 2.5), held_qual(3, 3.0))
    outputs = set()
    for codes in itertools.permutations((HELD1, HELD2)):
        d = TargetDeclaration(target_code=CODE, relevant_experience_years=2, relevant_prior_qualifications=codes)
        res = run(reg, q, profile(held_qualification_codes=codes, external_qualifications=(), declarations=(d,)), match="at_least")
        outputs.add(res.model_dump_json())
    assert len(outputs) == 1


# ---- holdings: complete only when BOTH lists are declared -------------------------------------------------------------


def level_target():
    return make([prior_row(1, 4.0)], None, held_qual(2, 2.5))


@pytest.mark.parametrize(("codes", "ext", "verdict", "reason"), [
    ((), (), N, None),                          # both declared, none held: a definite failure
    (None, None, U, R.INPUT_NOT_DECLARED),      # neither declared
    ((), None, U, R.INPUT_NOT_DECLARED),        # an undeclared external list may hold a qualifying qualification
    (None, (), U, R.INPUT_NOT_DECLARED),
    ((HELD1,), None, U, R.INPUT_NOT_DECLARED),  # holds a lower level; the other list is undeclared
    ((HELD1,), (), N, None),                    # both declared, nothing reaches level 4
])
@pytest.mark.parametrize("match", ["exact", "at_least"])
def test_holdings_are_complete_only_if_both_profile_lists_are_declared(codes, ext, verdict, reason, match):
    reg, q = level_target()
    res = run(reg, q, profile(held_qualification_codes=codes, external_qualifications=ext), match=match)
    c = res.rows[0].components[0]
    assert c.verdict is verdict and (c.unknown_reason.code if c.unknown_reason else None) is reason


def test_a_listed_holding_that_satisfies_the_level_counts_even_when_the_other_list_is_undeclared():
    reg, q = make([prior_row(1, 2.5)], None, held_qual(2, 2.5))
    d = TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1,))
    res = run(reg, q, profile(held_qualification_codes=(HELD1,), external_qualifications=None, declarations=(d,)), match="exact")
    assert res.rows[0].components[0].verdict is C


def test_holdings_declared_as_none_are_not_met_even_when_the_config_is_unset():
    reg, q = level_target()
    res = run(reg, q, profile(held_qualification_codes=(), external_qualifications=()), match=None)
    assert res.rows[0].components[0].verdict is N  # ARCHITECTURE §11.2 step 2 precedes step 3


def test_a_declared_holding_with_the_config_unset_is_unknown_config_unset_even_when_both_readings_agree():
    reg, q = level_target()  # held 2.5 against level 4: exact and at_least both say "not satisfied"
    res = run(reg, q, profile(held_qualification_codes=(HELD1,), external_qualifications=()), match=None)
    c = res.rows[0].components[0]
    assert c.verdict is U and c.unknown_reason.code is R.CONFIG_UNSET and c.unknown_reason.resolvable_by == "CONFIG"
    assert res.verdict is U


def test_external_qualifications_carry_their_declared_level_and_class():
    reg, q = make([prior_row(1, 3.0)])
    ext = (ExternalQualification(ref="ext-abc", label="Course", nsqf_level=3.0),)
    d = TargetDeclaration(target_code=CODE, relevant_prior_qualifications=("ext-abc",))
    res = run(reg, q, profile(held_qualification_codes=(), external_qualifications=ext, declarations=(d,)), match="exact")
    used = {u.field: u.evidence_class.value for u in res.rows[0].components[0].inputs_used}
    assert used["profile.external_qualifications[ext-abc].nsqf_level"] == "DECLARED"
    assert res.rows[0].components[0].verdict is C


# ---- Q-B: the NSQF level of a held registry qualification -------------------------------------------------------------


def q_b(level_held: float, level_required: float, match: str, **held_kw):
    reg, q = make([prior_row(1, level_required)], None, held_qual(2, level_held, **held_kw))
    d = TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1,))
    state = profile(held_qualification_codes=(HELD1,), external_qualifications=(), declarations=(d,))
    return {pol: run(reg, q, state, match, undecided_level_use=pol).rows[0].components[0] for pol in UndecidedLevelUse}


@pytest.mark.parametrize("engine_use", ["SAFE_HARD_RULE", "SAFE_WITH_CONSTRAINT", "CONDITIONAL_ON_DECLARED_RELEVANCE"])
def test_q_b_case_1_a_level_with_a_computing_engine_use_is_compared_under_both_policies(engine_use):
    for level, required, expected in [(2.5, 2.5, C), (3.5, 2.5, N), (2.5, 4.0, N)]:  # exact: only equality satisfies
        out = q_b(level, required, "exact", engine_use=engine_use)
        assert {c.verdict for c in out.values()} == {expected}, (level, required)
    assert {c.verdict for c in q_b(3.5, 2.5, "at_least", engine_use=engine_use).values()} == {C}


@pytest.mark.parametrize("level_held", [2.5, 3.5, 1.0])
def test_q_b_case_2_unknown_engine_use_is_compared_only_when_the_policy_says_so_provisional(level_held):
    # PROVISIONAL-Q-B: COMPARE reproduces TASKS P3.3 criteria 1-2 and the E07 example; CAP is the strict §11.4 reading.
    out = q_b(level_held, 2.5, "at_least", engine_use="UNKNOWN")
    assert out[UndecidedLevelUse.COMPARE].verdict is (C if level_held >= 2.5 else N)
    capped = out[UndecidedLevelUse.CAP]
    assert capped.verdict is U and capped.unknown_reason.code is R.ENGINE_USE_UNDECIDED
    assert capped.unknown_reason.resolvable_by == "SOURCE_REVIEW"
    assert not any(u.field == f"qual:{HELD1}.nsqf_level" for u in capped.inputs_used)  # a capped level is not an input used


def test_q_b_an_absent_engine_use_is_treated_like_unknown():
    out = q_b(2.5, 2.5, "exact", engine_use=None)
    assert out[UndecidedLevelUse.COMPARE].verdict is C and out[UndecidedLevelUse.CAP].verdict is U


@pytest.mark.parametrize("engine_use", ["DISPLAY_ONLY", "NOT_USED", "SAFE_HOURS"])
@pytest.mark.parametrize(("level_held", "match"), [(2.5, "exact"), (4.0, "at_least"), (1.0, "exact")])
def test_q_b_a_display_only_level_never_gains_authority_from_having_a_number(engine_use, level_held, match):
    # §11.4: DISPLAY_ONLY is "shown, never computed" - under either policy, whether the number would satisfy the rule or not
    for c in q_b(level_held, 2.5, match, engine_use=engine_use).values():
        assert c.verdict is U and c.unknown_reason.code is R.ENGINE_USE_UNDECIDED


@pytest.mark.parametrize(("status", "extra", "reason"), [
    ("PARSED_UNCERTAIN", {}, R.UNCERTAIN_EXTRACTION),
    ("UNRESOLVED", {}, R.UNCERTAIN_EXTRACTION),
    ("TRANSCRIBED", {"conflict_id": "conflict:OV-777"}, R.SOURCE_CONFLICT),
    ("PARSED_UNCERTAIN", {"conflict_id": "conflict:OV-777"}, R.SOURCE_CONFLICT),  # a conflict outranks uncertainty
])
def test_a_level_that_is_uncertain_or_conflicted_is_capped_whatever_its_engine_use(status, extra, reason):
    for c in q_b(2.5, 2.5, "exact", engine_use="UNKNOWN", status=status, **extra).values():  # also under COMPARE
        assert c.verdict is U and c.unknown_reason.code is reason


@pytest.mark.parametrize("status", ["CORROBORATED", "CONFIRMED_BY_GEOMETRY"])
def test_a_substantiated_level_is_not_capped_for_uncertainty(status):
    assert q_b(2.5, 2.5, "exact", engine_use="SAFE_HARD_RULE", status=status)[UndecidedLevelUse.CAP].verdict is C


def test_a_null_level_is_capped_and_its_placeholder_is_never_compared():
    reg, q = make([prior_row(1, 1.0)], None, held_qual(2, 2.5))
    null_level = Qualification.model_validate(held_qual(2, 2.5) | {
        "nsqf_level": official(None, 12, engine_use="UNKNOWN", status="UNRESOLVED")})
    reg = Registry.from_records(qualifications=[reg.qualification_by_code(CODE), null_level])
    d = TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1,))
    res = run(reg, q, profile(held_qualification_codes=(HELD1,), external_qualifications=(), declarations=(d,)), "at_least")
    c = res.rows[0].components[0]  # the placeholder 1.0 would satisfy "level 1.0"; it must not be used
    assert c.verdict is U and c.unknown_reason.code is R.UNCERTAIN_EXTRACTION


def test_a_usable_satisfying_holding_wins_over_a_capped_one_and_a_capped_one_blocks_a_definite_failure():
    reg, q = make([prior_row(1, 3.0)], None, held_qual(2, 4.0, engine_use="DISPLAY_ONLY"), held_qual(3, 3.0))
    d = TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD2,))
    both = profile(held_qualification_codes=(HELD1, HELD2), external_qualifications=(), declarations=(d,))
    assert run(reg, q, both, "exact").rows[0].components[0].verdict is C
    only_capped = profile(held_qualification_codes=(HELD1,), external_qualifications=(), declarations=(
        TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1,)),))
    assert run(reg, q, only_capped, "exact").rows[0].components[0].verdict is U  # not NOT_MET


def test_the_policy_must_be_a_known_value():
    reg, q = make()
    with pytest.raises(ValueError):
        run(reg, q, undecided_level_use="MAYBE")


# ---- progression claims, credits and overlays never change a verdict --------------------------------------------------


def claims_registry(claims):
    return make([prior_row(1, 2.5), mkrow(2, "C")], None, held_qual(2, 2.5, claims=claims), held_qual(3, 3.0, claims=["Other (Vertical)"]))


def claims_state(relevant):
    d = TargetDeclaration(target_code=CODE, relevant_experience_years=2, relevant_prior_qualifications=relevant)
    return profile(held_qualification_codes=(HELD1, HELD2), external_qualifications=(), declarations=(d,))


def test_progression_claims_are_supporting_evidence_only_and_removing_them_changes_nothing_else():
    with_claims = run(*claims_registry(["Target (Vertical)", "Another (Horizontal)"]), claims_state((HELD1,)), "exact")
    without = run(*claims_registry([]), claims_state((HELD1,)), "exact")
    assert [e.kind for e in with_claims.supporting_evidence] == ["PROGRESSION_CLAIM", "PROGRESSION_CLAIM"]
    assert all(e.evidence_class.value == "OFFICIAL" and len(e.evidence_ids) == 1 for e in with_claims.supporting_evidence)
    assert "Supporting evidence only; it does not change the verdict." in with_claims.supporting_evidence[0].text
    assert without.supporting_evidence == ()
    strip = {"supporting_evidence"}
    assert with_claims.model_dump(exclude=strip) == without.model_dump(exclude=strip)


def test_a_claim_is_shown_only_for_a_held_qualification_the_profile_declares_relevant():
    reg_q = claims_registry(["Target (Vertical)"])
    shown = run(*reg_q, claims_state((HELD1,)), "exact").supporting_evidence
    assert [e.evidence_ids for e in shown] == [(ev(31),)] and "Held Qualification 2" in shown[0].text
    assert run(*reg_q, claims_state(()), "exact").supporting_evidence == ()  # held, declared not relevant
    assert run(*reg_q, claims_state(None), "exact").supporting_evidence == ()  # relevance not declared


def test_supporting_evidence_is_never_linked_to_the_target_by_name_d5():
    # the claim text names nothing resolvable; no claim-to-target link is asserted (that is an inference, P3.5)
    res = run(*claims_registry(["Synthetic Qualification (Vertical)"]), claims_state((HELD1,)), "exact")
    assert all(CODE not in e.text for e in res.supporting_evidence)


def test_credits_and_other_display_values_never_change_a_result():
    base = run(*make([mkrow(1, "C")], credits=4.0), profile())
    for credits in (0.0, 4.0, 99.5):
        assert run(*make([mkrow(1, "C")], credits=credits), profile()).model_dump() == base.model_dump()
    assert "credit" not in base.model_dump_json().lower()


def test_an_unapproved_overlay_proposal_cannot_lift_a_component_whatever_the_profile_says():
    pending = row(2, raw_text="Diploma year || ", engine_use="UNKNOWN", overlay_ids=[],
                  components=[component("UNMODELLED", params={}, safe=False, unknown_reason="DIPLOMA_YEAR_NOT_MODELLED"),
                              component("UNMODELLED", params={}, safe=False, unknown_reason="OVERLAY_NOT_APPROVED")],
                  flags=[{"code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "Proposed value (OV-002) is not applied.",
                          "refs": ["OV-002"]}])
    reg, q = make([pending])
    full = ProfileState(age_years=40, school_grade_passed=12, post_school_credentials=(), held_qualification_codes=(),
                        external_qualifications=(), declarations=(TargetDeclaration(target_code=CODE, relevant_experience_years=20),))
    res = evaluate(q.eligibility, full, EngineConfig(nsqf_level_match="at_least"), reg)
    assert res.verdict is U and res.rows[0].verdict is U
    assert [c.unknown_reason.code for c in res.rows[0].components] == [R.DIPLOMA_YEAR_NOT_MODELLED, R.OVERLAY_NOT_APPROVED]
    assert [f.code.value for f in res.rows[0].flags] == ["OVERLAY_PENDING_APPROVAL"]
    assert "OVERLAY_PENDING_APPROVAL" in [f.code.value for f in res.quality_flags]  # surfaced, as a warning
    assert [u.code for u in res.unknown_reasons] == [R.DIPLOMA_YEAR_NOT_MODELLED, R.OVERLAY_NOT_APPROVED]


# ---- determinism and contract shape -----------------------------------------------------------------------------------


def test_repeated_evaluation_is_identical_and_independent_of_declaration_order():
    reg, q = make([prior_row(1, 2.5), mkrow(2, "C"), mkrow(3, "U")], None, held_qual(2, 2.5), held_qual(3, 3.0))
    outputs = set()
    ext = (ExternalQualification(ref="ext-b", label="B", nsqf_level=4.0), ExternalQualification(ref="ext-a", label="A", nsqf_level=2.0))
    for codes, externals in itertools.product(itertools.permutations((HELD1, HELD2)), itertools.permutations(ext)):
        d = TargetDeclaration(target_code=CODE, relevant_experience_years=2, relevant_prior_qualifications=codes)
        state = profile(held_qualification_codes=codes, external_qualifications=externals, declarations=(d,),
                        post_school_credentials=(PostSchoolCredential(type="UG_DIPLOMA"),))
        for _ in range(2):
            outputs.add(run(reg, q, state, "at_least").model_dump_json())
    assert len(outputs) == 1


def test_the_result_projects_to_the_api_shape():
    reg, q = make([prior_row(1, 2.5), mkrow(2, "C")], None, held_qual(2, 2.5))
    d = TargetDeclaration(target_code=CODE, relevant_experience_years=2, relevant_prior_qualifications=(HELD1,))
    res = run(reg, q, profile(held_qualification_codes=(HELD1,), external_qualifications=(), declarations=(d,)), "exact")
    assert res.target.model_dump() == {"id": f"qual:{CODE}", "code": CODE, "slug": "TEST.Q9001", "title": "Synthetic Qualification",
                                       "nsqf_level": 2.5}
    assert res.age.component_id == f"rule:{CODE}/AGE#c1" and res.age.requirement_text == "Age: 18 years"
    assert res.age.params == {"min_age": 18} and res.age.condition is None
    r1 = res.rows[0]
    assert (r1.rule_id, r1.s_no, r1.raw_text) == (f"rule:{CODE}/E1", 1, "prior level 2.5 || 1 years")
    assert [c.component_id for c in r1.components] == [f"rule:{CODE}/E1#c1", f"rule:{CODE}/E1#c2"]
    assert [c.requirement_text for c in r1.components] == ["prior level 2.5", "1 years"]  # verbatim cell text
    assert r1.components[0].params == {"level": 2.5, "requires_relevance": True}
    assert r1.components[1].params == {"years": 0.0}  # requires_relevance omitted when false
    assert all(c.evidence_ids == (ev(2),) for c in r1.components)
    assert res.explanation == ()


def test_an_empty_second_cell_is_kept_verbatim():
    reg, q = make([row(1, raw_text="Some text || ", components=[comp("M"), comp("M")], overlay_ids=[])])
    assert run(reg, q).rows[0].components[1].requirement_text == ""


def test_a_row_whose_cells_do_not_match_its_components_is_malformed():
    reg, q = make([row(1, raw_text="no delimiter here", components=[comp("M"), comp("M")], overlay_ids=[])])
    with pytest.raises(EligibilityError, match="delimiter"):
        run(reg, q)


def test_the_result_model_rejects_a_result_that_breaks_the_unknown_and_condition_invariants():
    reg, q = make([mkrow(1, "U")])
    data = run(reg, q).model_dump()
    assert EligibilityResult.model_validate(data).verdict is U
    for mutate in (lambda d: d.update(unknown_reasons=[]),
                   lambda d: d["rows"][0]["components"][0].update(unknown_reason=None)):
        broken = EligibilityResult.model_validate(data).model_dump()
        mutate(broken)
        with pytest.raises(ValidationError):
            EligibilityResult.model_validate(broken)


@pytest.mark.parametrize("rows", [["M"], ["C"], ["U"], ["N"], ["C", "U", "N"], ["U", "U"]])
@pytest.mark.parametrize("age", [None, 17, 30])
def test_every_conditional_has_a_condition_and_every_unknown_a_reason(rows, age):
    reg, q = make([mkrow(i, k, "C") for i, k in enumerate(rows, start=1)])
    res = run(reg, q, profile(age_years=age))
    for c in [res.age, *(c for r in res.rows for c in r.components)]:
        assert (c.verdict is C) == (c.condition is not None)
        assert (c.verdict is U) == (c.unknown_reason is not None)
    if res.verdict is C:
        assert res.conditions
    if res.verdict is U:
        assert res.unknown_reasons


# ---- profile and call validation --------------------------------------------------------------------------------------


@pytest.mark.parametrize("kw", [
    {"age_years": 13}, {"age_years": 81}, {"age_years": 30.5}, {"school_grade_passed": 13}, {"school_grade_passed": -1},
    {"held_qualification_codes": (HELD1, HELD1)},
    {"external_qualifications": (ExternalQualification(ref="ext-a", label="A", nsqf_level=2.0),) * 2},
    {"declarations": (TargetDeclaration(target_code=CODE), TargetDeclaration(target_code=CODE))},
    {"declarations": (TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1,)),)},  # no holdings declared
    {"held_qualification_codes": (HELD2,),
     "declarations": (TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1,)),)},   # not a declared holding
    {"held_qualification_codes": (HELD1,),
     "declarations": (TargetDeclaration(target_code=CODE, relevant_prior_qualifications=(HELD1, HELD1)),)},
])
def test_an_invalid_profile_is_refused(kw):
    with pytest.raises((ValidationError, ValueError)):
        ProfileState(**kw)


def test_external_reference_and_level_are_validated():
    with pytest.raises(ValidationError):
        ExternalQualification(ref="abc", label="A", nsqf_level=2.0)
    with pytest.raises(ValidationError):
        ExternalQualification(ref="ext-a", label="A", nsqf_level=2.25)


def test_an_unknown_held_code_raises_the_registry_error_not_a_verdict():
    reg, q = make()
    with pytest.raises(UnknownEntityError):
        run(reg, q, profile(held_qualification_codes=("TEST/Q9999",), external_qualifications=()))


def test_a_target_that_is_not_in_the_registry_raises():
    reg, q = make()
    other = Registry.from_records(qualifications=[Qualification.model_validate(held_qual(2))])
    with pytest.raises(UnknownEntityError):
        evaluate(q.eligibility, ProfileState(), EngineConfig(), other)


def test_wrong_argument_types_are_refused():
    reg, q = make()
    for args in ((None, ProfileState(), EngineConfig(), reg), (q.eligibility, {}, EngineConfig(), reg),
                 (q.eligibility, ProfileState(), None, reg), (q.eligibility, ProfileState(), EngineConfig(), None)):
        with pytest.raises(TypeError):
            evaluate(*args)


def test_the_config_accepts_only_the_documented_interpretations():
    assert EngineConfig().nsqf_level_match is None
    with pytest.raises(ValidationError):
        EngineConfig(nsqf_level_match="roughly")


# ---- boundaries -------------------------------------------------------------------------------------------------------


def test_evaluate_imports_only_model_registry_and_eligibility_modules():
    src = Path(__file__).resolve().parents[2] / "src" / "skillgraph" / "eligibility" / "evaluate.py"
    allowed = ("skillgraph.model", "skillgraph.registry", "skillgraph.eligibility")
    stdlib = {"json", "enum", "typing", "__future__"}
    bad = []
    for node in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
        for name in names:
            if name.split(".")[0] in stdlib | {"pydantic"}:
                continue
            if not any(name == p or name.startswith(p + ".") for p in allowed):
                bad.append(name)
    assert bad == []


def test_evaluate_does_not_reimplement_component_logic():
    src = (Path(__file__).resolve().parents[2] / "src" / "skillgraph" / "eligibility" / "evaluate.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"evaluate_component", "and_", "or_"} <= called
    assert "min_age" not in src and '"grade"' not in src  # no component parameter is read here
