"""P3.3 golden tests: the four curated pilot qualifications on the REAL curated build (skipped when it is absent).

Every test loads the real build through the ``reg`` fixture, which asserts ``BuildInfo.validation == "PASSED"`` for each
test. All profiles are synthetic and hypothetical ("a person who ..."); no result is a claim about a real person.

Expected values are derived by hand from (a) the printed rule text of the pilot qualifications, (b) ARCHITECTURE §11.1-§11.3
and API_SPEC §2.4, and (c) the TASKS P3.3 acceptance criteria - not copied from the evaluator's output.

PROVISIONAL markers (see ``docs/decisions/P3_2_AUDIT.md`` and ``TASKS.md`` P3.3):

* PROVISIONAL-Q-B: the qualification-level NSQF value of each curated pilot has ``engine_use = UNKNOWN`` (the catalogue-only
  ones ``DISPLAY_ONLY``). TASKS criteria 1-2 and the E07 example compare it (``undecided_level_use = COMPARE``, the default);
  the strict reading of ARCHITECTURE §11.4 would cap it (``CAP``). Each result that depends on it also asserts the ``CAP``
  outcome, so a decision either way is a one-line change. ``DISPLAY_ONLY`` values are never compared under either policy.
* PROVISIONAL-Q-A: the reason code ``REVIEW_FLAG`` for the D5 below-threshold "Grade 9" case.
"""

import itertools
from pathlib import Path

import pytest
import yaml

from skillgraph.curation.eligibility_rules import project_spec
from skillgraph.eligibility.evaluate import (
    EligibilityResult,
    EngineConfig,
    ExternalQualification,
    PostSchoolCredential,
    ProfileState,
    TargetDeclaration,
    UndecidedLevelUse,
    evaluate,
)
from skillgraph.model.eligibility import ComponentType
from skillgraph.model.eligibility import UnknownReasonCode as R
from skillgraph.model.eligibility import Verdict
from skillgraph.model.qualification import Qualification
from skillgraph.registry import Registry, load

N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
SMO, SSMO, IC, PS = "AMH/Q0301", "AMH/Q2301", "AMH/Q0103", "AMH/Q2101"  # the four curated pilots
PILOTS = (SMO, SSMO, IC, PS)
MATCHES = ("exact", "at_least")
COMPARE, CAP = UndecidedLevelUse.COMPARE, UndecidedLevelUse.CAP
REPO = Path(__file__).resolve().parents[2]


# ---- fixtures and helpers ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _registry(build_dir) -> Registry:
    return load(build_dir)


@pytest.fixture
def reg(_registry) -> Registry:
    assert _registry.build is not None and _registry.build.validation == "PASSED"  # asserted for every golden test
    return _registry


def P(*, age=30, grade=None, creds=None, held=None, ext=None, decl=()) -> ProfileState:
    return ProfileState(
        age_years=age, school_grade_passed=grade,
        post_school_credentials=None if creds is None else tuple(PostSchoolCredential(type=t) for t in creds),
        held_qualification_codes=held, external_qualifications=ext, declarations=tuple(decl))


def D(code, years=None, rel=None) -> TargetDeclaration:
    return TargetDeclaration(target_code=code, relevant_experience_years=years, relevant_prior_qualifications=rel)


def ev(reg, code, state, match=None, **kw) -> EligibilityResult:
    return evaluate(reg.qualification_by_code(code).eligibility, state, EngineConfig(nsqf_level_match=match), reg, **kw)


def row(res: EligibilityResult, s_no: int):
    return next(r for r in res.rows if r.s_no == s_no)


def comp(res: EligibilityResult, s_no: int, n: int):
    return row(res, s_no).components[n - 1]


def reason(c):
    return c.unknown_reason.code if c.unknown_reason else None


def prior_components(reg, code):
    spec = reg.qualification_by_code(code).eligibility
    return [(r.s_no, n) for r in spec.rows for n, c in enumerate(r.components, 1) if c.type is ComponentType.PRIOR_NSQF_LEVEL]


def all_profiles():
    """A spread of synthetic profiles, including incomplete, partial and rich ones."""
    ext = (ExternalQualification(ref="ext-x", label="X", nsqf_level=4.0),)
    return [
        ProfileState(),
        P(age=17, grade=12, creds=["UG_DIPLOMA"], held=[SMO, SSMO, IC], ext=(), decl=[D(c, 20, [SMO, SSMO, IC]) for c in PILOTS]),
        P(age=18, grade=8, creds=[], held=[], ext=(), decl=[D(c, 0, []) for c in PILOTS]),
        P(age=24, grade=10, creds=[], held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])]),
        P(age=40, grade=12, creds=["UG_CERTIFICATE", "OTHER"], held=[SMO, SSMO], ext=ext,
          decl=[D(c, 5, [SMO, "ext-x"]) for c in PILOTS]),
        P(age=21, held=[SMO], ext=None, decl=[D(IC, 3, [SMO])]),
        P(age=21, held=None, ext=(), decl=[D(PS, 2)]),
    ]


# ---- the build ------------------------------------------------------------------------------------------------------------


def test_the_real_build_is_the_validated_current_build(reg):
    assert reg.build.validation == "PASSED" and reg.build.status == "READY"
    assert {q.code for q in reg.qualifications() if q.coverage.value == "CURATED"} == set(PILOTS)
    assert yaml.safe_load((REPO / "config" / "overlay_approvals.yaml").read_text(encoding="utf-8"))["approved"] == []


def test_the_result_projects_the_stored_rules_exactly_as_the_static_projection_does(reg):
    # component ids, verbatim requirement text, params (+requires_relevance) and evidence ids agree with curation.project_spec
    for code in PILOTS:
        q = reg.qualification_by_code(code)
        res = ev(reg, code, ProfileState())
        proj = project_spec(q.eligibility)
        assert [c.model_dump(mode="json", include={"component_id", "type", "requirement_text", "params"}) | {"evidence_ids": list(c.evidence_ids)}
                for c in [res.age, *(c for r in res.rows for c in r.components)]] == [
            {k: v for k, v in c.items()} for c in [*proj["age"]["components"], *(c for r in proj["rows"] for c in r["components"])]]
        assert [(r.rule_id, r.s_no, r.raw_text, r.engine_use.value, list(r.overlay_ids)) for r in res.rows] == [
            (r["rule_id"], r["s_no"], r["raw_text"], r["engine_use"], r["overlay_ids"]) for r in proj["rows"]]
        assert [[f.model_dump(mode="json") for f in r.flags] for r in res.rows] == [r["flags"] for r in proj["rows"]]


def test_every_component_result_cites_the_evidence_record_of_its_own_stored_component(reg):
    for code in PILOTS:
        spec = reg.qualification_by_code(code).eligibility
        res = ev(reg, code, all_profiles()[1], "exact")
        stored = [spec.age_rule.components[0].evidence_id] + [c.evidence_id for r in spec.rows for c in r.components]
        got = [res.age.evidence_ids[0]] + [c.evidence_ids[0] for r in res.rows for c in r.components]
        assert got == stored
        for e in got:
            assert reg.evidence_by_id(e).id == e  # the reference resolves in the registry


# ---- criterion 1: Production Supervisor row 4 --------------------------------------------------------------------------


@pytest.mark.parametrize("held", [[SMO], [SSMO], [IC], [SMO, SSMO, IC]])
@pytest.mark.parametrize("match", MATCHES)
def test_c1_production_supervisor_level_4_is_not_met_from_any_pilot_holding_under_both_interpretations(reg, held, match):
    # Levels held: Q0301 2.5, Q2301 3.5, Q0103 3.5 - all below 4, so neither "exactly 4" nor "4 or higher" is satisfied.
    for rel in (held, [], None):  # a failure is definite before relevance is looked at (ARCHITECTURE §11.2 step 4 before 5)
        res = ev(reg, PS, P(age=30, held=held, ext=(), decl=[D(PS, 3, rel)]), match)
        c = comp(res, 4, 1)
        assert c.component_id == f"rule:{PS}/E4#c1" and c.type is ComponentType.PRIOR_NSQF_LEVEL
        assert c.verdict is N and c.condition is None and c.unknown_reason is None
        assert row(res, 4).verdict is N  # AND(NOT_MET, CONDITIONAL experience) = NOT_MET
        assert all(f"qual:{h}.nsqf_level" in {u.field for u in c.inputs_used} for h in held)


@pytest.mark.parametrize("match", MATCHES)
def test_c1_provisional_q_b_under_the_strict_reading_the_same_holdings_are_unknown_not_not_met(reg, match):
    res = ev(reg, PS, P(held=[SMO], ext=(), decl=[D(PS, 3, [SMO])]), match, undecided_level_use=CAP)
    c = comp(res, 4, 1)
    assert c.verdict is U and reason(c) is R.ENGINE_USE_UNDECIDED and c.unknown_reason.resolvable_by == "SOURCE_REVIEW"


@pytest.mark.parametrize("match", MATCHES)
def test_a_declared_external_level_4_does_satisfy_the_rule_when_declared_relevant(reg, match):
    ext = (ExternalQualification(ref="ext-x", label="X", nsqf_level=4.0),)
    c = comp(ev(reg, PS, P(held=[], ext=ext, decl=[D(PS, 3, ["ext-x"])]), match), 4, 1)
    assert c.verdict is C and c.condition.key == f"declarations[{PS}].relevant_prior_qualifications"
    assert {u.field: u.evidence_class.value for u in c.inputs_used}["profile.external_qualifications[ext-x].nsqf_level"] == "DECLARED"


# ---- criterion 2: Q0301 satisfies the level part of SSMO row 9 and IC row 4 ------------------------------------------------


@pytest.mark.parametrize("match", MATCHES)
@pytest.mark.parametrize(("target", "s_no", "years"), [(SSMO, 9, 3), (IC, 4, 3)])
def test_c2_holding_q0301_satisfies_the_level_component_under_both_interpretations(reg, match, target, s_no, years):
    res = ev(reg, target, P(age=25, held=[SMO], ext=(), decl=[D(target, years, [SMO])]), match)
    c = comp(res, s_no, 1)
    assert c.verdict is C and c.type is ComponentType.PRIOR_NSQF_LEVEL
    assert c.condition.key == f"declarations[{target}].relevant_prior_qualifications" and c.condition.value == (SMO,)
    used = {u.field: (u.value, u.evidence_class.value) for u in c.inputs_used}
    assert used["profile.held_qualification_codes"] == ((SMO,), "DECLARED")
    assert used[f"qual:{SMO}.nsqf_level"] == (2.5, "OFFICIAL")
    assert used["config.nsqf_level_match"] == (match, "CONFIG")
    assert row(res, s_no).verdict is C and f"rule:{target}/E{s_no}" in res.decisive_rule_ids
    assert res.verdict is C


def test_c2_provisional_q_b_the_same_holding_is_unknown_under_the_strict_reading(reg):
    res = ev(reg, SSMO, P(held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])]), "exact", undecided_level_use=CAP)
    c = comp(res, 9, 1)
    assert c.verdict is U and reason(c) is R.ENGINE_USE_UNDECIDED
    assert row(res, 9).verdict is U


@pytest.mark.parametrize(("held", "target", "s_no", "exact", "at_least"), [
    (SMO, SSMO, 8, N, N),    # level 3 against 2.5: neither reading
    (SMO, IC, 3, N, N),
    (SSMO, IC, 3, N, C),     # level 3 against 3.5: only "or higher"
    (SSMO, IC, 4, N, C),     # level 2.5 against 3.5
    (SMO, SMO, 6, N, C),     # level 2 against 2.5
    (SMO, SMO, 7, N, C),     # level 1 against 2.5
])
def test_exact_and_at_least_differ_exactly_where_the_held_level_is_higher(reg, held, target, s_no, exact, at_least):
    for match, expected in (("exact", exact), ("at_least", at_least)):
        res = ev(reg, target, P(held=[held], ext=(), decl=[D(target, 5, [held])]), match)
        assert comp(res, s_no, 1).verdict is expected, (held, target, s_no, match)


# ---- criterion 3: config unset ----------------------------------------------------------------------------------------------


def test_c3_the_pilots_have_exactly_seven_prior_level_components(reg):
    assert {c: len(prior_components(reg, c)) for c in PILOTS} == {SMO: 2, SSMO: 2, IC: 2, PS: 1}


@pytest.mark.parametrize("target", PILOTS)
@pytest.mark.parametrize("held", [[SMO], [SMO, SSMO, IC]])
def test_c3_unset_config_with_a_declared_holding_makes_every_level_component_unknown_config_unset(reg, target, held):
    res = ev(reg, target, P(held=held, ext=(), decl=[D(target, 20, held)]), None)
    for s_no, n in prior_components(reg, target):
        c = comp(res, s_no, n)
        assert c.verdict is U and reason(c) is R.CONFIG_UNSET and c.unknown_reason.resolvable_by == "CONFIG", (target, s_no)
        assert c.unknown_reason.ref == f"rule:{target}/E{s_no}#c{n}"


def test_c3_even_where_both_interpretations_agree_the_result_is_still_config_unset(reg):
    # PS level 4 with Q0301 held: both readings say NOT_MET, yet an unset config gives UNKNOWN (decision D3)
    for match in MATCHES:
        assert comp(ev(reg, PS, P(held=[SMO], ext=(), decl=[D(PS, 3, [SMO])]), match), 4, 1).verdict is N
    unset = comp(ev(reg, PS, P(held=[SMO], ext=(), decl=[D(PS, 3, [SMO])]), None), 4, 1)
    assert unset.verdict is U and reason(unset) is R.CONFIG_UNSET


@pytest.mark.parametrize("target", PILOTS)
@pytest.mark.parametrize("match", [None, *MATCHES])
def test_c3_holdings_declared_as_none_are_not_met_whatever_the_config(reg, target, match):
    res = ev(reg, target, P(held=[], ext=(), decl=[D(target, 20, [])]), match)
    for s_no, n in prior_components(reg, target):
        c = comp(res, s_no, n)
        assert c.verdict is N and c.unknown_reason is None and c.condition is None


@pytest.mark.parametrize(("held", "ext"), [(None, None), ([], None), (None, ()), ([SMO], None)])
def test_c3_incomplete_holdings_are_unknown_input_not_declared_never_not_met(reg, held, ext):
    # "no listed holding satisfies" is only a failure if BOTH profile lists were declared (P3.2 audit A-5)
    res = ev(reg, PS, P(held=held, ext=ext, decl=[D(PS, 3, None)]), "at_least")
    c = comp(res, 4, 1)
    assert c.verdict is U and reason(c) is R.INPUT_NOT_DECLARED and c.unknown_reason.resolvable_by == "PROFILE"


def test_c3_an_unlisted_holding_cannot_be_ruled_out_but_a_listed_qualifying_one_still_counts(reg):
    ext = (ExternalQualification(ref="ext-x", label="X", nsqf_level=4.0),)
    c = comp(ev(reg, PS, P(held=None, ext=ext, decl=[D(PS, 3, ["ext-x"])]), "exact"), 4, 1)
    assert c.verdict is C  # codes undeclared, but the declared external level 4 satisfies the rule


# ---- criterion 4: age --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("target", PILOTS)
@pytest.mark.parametrize("match", [None, *MATCHES])
def test_c4_age_17_makes_every_pilot_target_not_met_with_the_decisive_reason_on_the_age_rule(reg, target, match):
    rich = P(age=17, grade=12, creds=["UG_DIPLOMA", "UG_CERTIFICATE"], held=[SMO, SSMO, IC], ext=(),
             decl=[D(target, 30, [SMO, SSMO, IC])])
    res = ev(reg, target, rich, match)
    assert res.verdict is N
    assert res.age.component_id == f"rule:{target}/AGE#c1" and res.age.type is ComponentType.AGE_MIN
    assert res.age.verdict is N and res.age.unknown_reason is None
    assert [(u.field, u.value, u.evidence_class.value) for u in res.age.inputs_used] == [("profile.age_years", 17, "DECLARED")]
    assert res.decisive_rule_ids == tuple(r.rule_id for r in res.rows)  # all rows if NOT_MET (API_SPEC §2.4)
    assert res.unknown_reasons == ()


@pytest.mark.parametrize(("target", "minimum"), [(SMO, 18), (SSMO, 18), (IC, 18), (PS, 20)])
def test_c4_the_age_boundary_is_the_printed_minimum(reg, target, minimum):
    assert reg.qualification_by_code(target).eligibility.age_rule.raw_text == f"Age: {minimum} years"
    below = ev(reg, target, P(age=minimum - 1, grade=12, decl=[D(target, 30)]))
    at = ev(reg, target, P(age=minimum, grade=12, decl=[D(target, 30)]))
    assert below.age.verdict is N and below.verdict is N
    assert at.age.verdict is M and at.verdict is not N


@pytest.mark.parametrize("target", PILOTS)
def test_c4_a_missing_age_is_unknown_input_not_declared_never_a_pass_or_a_failure(reg, target):
    res = ev(reg, target, P(age=None, grade=12, creds=["UG_DIPLOMA"], held=[], ext=(), decl=[D(target, 30, [])]), "exact")
    assert res.age.verdict is U and reason(res.age) is R.INPUT_NOT_DECLARED
    assert res.verdict in (U, N)  # never MET/CONDITIONAL while the age is unknown
    if res.verdict is U:
        assert res.unknown_reasons[0].ref == f"rule:{target}/AGE#c1"


@pytest.mark.parametrize("target", PILOTS)
def test_an_empty_profile_is_unknown_for_every_pilot_with_reasons_on_what_to_declare(reg, target):
    res = evaluate(reg.qualification_by_code(target).eligibility, ProfileState(), EngineConfig(), reg)
    assert res.verdict is U and res.unknown_reasons
    assert res.unknown_reasons[0].code is R.INPUT_NOT_DECLARED and res.unknown_reasons[0].resolvable_by == "PROFILE"


# ---- criterion 5: unapproved overlays ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("match", [None, *MATCHES])
def test_c5_without_approval_of_ov_002_to_004_ssmo_rows_2_to_4_are_never_met_or_conditional(reg, match):
    assert yaml.safe_load((REPO / "config" / "overlay_approvals.yaml").read_text(encoding="utf-8"))["approved"] == []
    best = P(age=40, grade=12, creds=["UG_DIPLOMA", "UG_CERTIFICATE"], held=[SMO, IC], ext=(), decl=[D(SSMO, 20, [SMO, IC])])
    res = ev(reg, SSMO, best, match)
    expected = {2: (R.DIPLOMA_YEAR_NOT_MODELLED, "OV-002"), 3: (R.ENROLMENT_NOT_MODELLED, "OV-003"),
                4: (R.NTC_NAC_CITS_NOT_MODELLED, "OV-004")}
    for s_no, (first, overlay) in expected.items():
        r = row(res, s_no)
        assert r.verdict is U and r.verdict not in (M, C)
        assert [reason(c) for c in r.components] == [first, R.OVERLAY_NOT_APPROVED]
        assert [(f.code.value, f.refs) for f in r.flags if f.code.value == "OVERLAY_PENDING_APPROVAL"] == [("OVERLAY_PENDING_APPROVAL", [overlay])]
        assert overlay not in r.overlay_ids  # the decided list excludes a pending proposal; only the flag names it


def test_c5_the_target_stays_conditional_only_through_routes_that_do_not_rely_on_a_pending_overlay(reg):
    res = ev(reg, SSMO, P(age=40, grade=12, held=[SMO], ext=(), decl=[D(SSMO, 20, [SMO])]), "at_least")
    assert res.verdict is C
    assert set(res.decisive_rule_ids) == {f"rule:{SSMO}/E{n}" for n in (7, 8, 9) if row(res, n).verdict is C}
    for n in (2, 3, 4):
        assert f"rule:{SSMO}/E{n}" not in res.decisive_rule_ids


def test_uncertain_extraction_caps_a_component_whatever_the_profile_says(reg):
    res = ev(reg, SSMO, P(age=40, grade=12, decl=[D(SSMO, 20)]))
    c = comp(res, 1, 1)  # "11th Grade pass": the academic cell is PARSED_UNCERTAIN
    assert c.verdict is U and reason(c) is R.UNCERTAIN_EXTRACTION and c.unknown_reason.resolvable_by == "SOURCE_REVIEW"
    assert comp(res, 1, 2).verdict is M  # "No Experience required" is safe and is still evaluated
    assert row(res, 1).verdict is U
    for n in (5, 6):  # experience cells of PARSED_UNCERTAIN rows stay capped
        assert reason(comp(res, n, 2)) is R.UNCERTAIN_EXTRACTION


def test_an_undecided_engine_use_cell_is_unknown_even_with_ample_declared_experience(reg):
    # SMO row 5: the 5-year experience cell has engine_use UNKNOWN (ARCHITECTURE §11.3 item 6)
    res = ev(reg, SMO, P(age=40, grade=12, decl=[D(SMO, 40)]))
    assert [reason(c) for c in row(res, 5).components] == [R.LITERACY_NOT_MODELLED, R.ENGINE_USE_UNDECIDED]
    assert row(res, 5).verdict is U


# ---- criterion 6: progression claims ---------------------------------------------------------------------------------------


def test_c6_the_smo_to_ssmo_claim_is_supporting_evidence_and_removing_it_changes_nothing_else(reg):
    state = P(age=24, grade=10, creds=[], held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])])
    res = ev(reg, SSMO, state, "exact")
    claims = {c.id: c for c in reg.qualification_by_code(SMO).progression_claims}
    target_claim = claims[f"claim:{SMO}/P2"]
    assert target_claim.text_verbatim == "Specialized Sewing Machine Operator(Vertical)"
    shown = {e.evidence_ids: e for e in res.supporting_evidence}
    assert (target_claim.evidence_id,) in shown
    item = shown[(target_claim.evidence_id,)]
    assert item.kind == "PROGRESSION_CLAIM" and item.evidence_class.value == "OFFICIAL"
    assert "Specialized Sewing Machine Operator(Vertical)" in item.text and "does not change the verdict" in item.text

    stripped = strip_claims(reg)
    without = ev(stripped, SSMO, state, "exact")
    assert without.supporting_evidence == ()
    keep = {"supporting_evidence"}
    assert res.model_dump(exclude=keep) == without.model_dump(exclude=keep)  # same verdict, rows, conditions, flags
    assert res.verdict is C


def strip_claims(reg: Registry) -> Registry:
    quals = [Qualification.model_validate({**q.model_dump(mode="json"), "progression_claims": []}) for q in reg.qualifications()]
    return Registry.from_records(qualifications=quals, nos_units=reg.nos_units(), conflicts=reg.conflicts(), build=reg.build)


@pytest.mark.parametrize("target", PILOTS)
def test_c6_claims_never_change_any_result_for_any_pilot_or_profile(reg, target):
    stripped = strip_claims(reg)
    for state, match in itertools.product(all_profiles(), [None, *MATCHES]):
        a, b = ev(reg, target, state, match), ev(stripped, target, state, match)
        assert a.model_dump(exclude={"supporting_evidence"}) == b.model_dump(exclude={"supporting_evidence"})


def test_a_claim_is_not_shown_unless_the_holder_is_declared_relevant_to_the_target(reg):
    assert ev(reg, SSMO, P(held=[SMO], ext=(), decl=[D(SSMO, 3, [])]), "exact").supporting_evidence == ()
    assert ev(reg, SSMO, P(held=[SMO], ext=(), decl=[D(SSMO, 3, None)]), "exact").supporting_evidence == ()
    assert ev(reg, SSMO, P(held=[], ext=(), decl=[D(SSMO, 3, [])]), "exact").supporting_evidence == ()


# ---- criterion 7: credits and other display-only values -------------------------------------------------------------------


def with_all_credits(reg: Registry, value: float) -> Registry:
    def mutate(d: dict) -> dict:
        d = {**d, "credits": {**d["credits"], "value": value}}
        d["nos_memberships"] = [{**m, "credits": {**m["credits"], "value": value}} for m in d.get("nos_memberships", [])]
        d["credit_groups"] = [{**g, "credits": {**g["credits"], "value": value}} for g in d.get("credit_groups", [])]
        return d
    quals = [Qualification.model_validate(mutate(q.model_dump(mode="json"))) for q in reg.qualifications()]
    return Registry.from_records(qualifications=quals, nos_units=reg.nos_units(), conflicts=reg.conflicts(), build=reg.build)


def test_c7_mutating_every_credit_value_in_a_copied_registry_leaves_all_results_identical(reg):
    originals = {q.code: q.credits.value for q in reg.qualifications()}
    for value in (0.0, 1.0, 12345.5):
        mutated = with_all_credits(reg, value)
        assert {q.code: q.credits.value for q in mutated.qualifications()} != originals  # the mutation took effect
        assert any(m.credits.value == value for m in mutated.qualification_by_code(SSMO).nos_memberships)
        for target, state, match in itertools.product(PILOTS, all_profiles(), [None, *MATCHES]):
            assert ev(mutated, target, state, match).model_dump() == ev(reg, target, state, match).model_dump()


def test_credits_never_appear_in_inputs_used(reg):
    for target, state in itertools.product(PILOTS, all_profiles()):
        res = ev(reg, target, state, "at_least")
        fields = [u.field for c in [res.age, *(c for r in res.rows for c in r.components)] for u in c.inputs_used]
        assert not any("credit" in f.lower() for f in fields)


# ---- criterion 8 and the result invariants --------------------------------------------------------------------------------


@pytest.mark.parametrize("target", PILOTS)
@pytest.mark.parametrize("policy", list(UndecidedLevelUse))
def test_c8_every_conditional_has_a_condition_and_every_unknown_has_a_reason(reg, target, policy):
    seen = set()
    for state, match in itertools.product(all_profiles(), [None, *MATCHES]):
        res = ev(reg, target, state, match, undecided_level_use=policy)
        seen.add(res.verdict)
        comps = [res.age, *(c for r in res.rows for c in r.components)]
        for c in comps:
            assert (c.verdict is C) == (c.condition is not None) and (c.verdict is U) == (c.unknown_reason is not None)
        for r in res.rows:
            assert r.verdict is min((c.verdict for c in r.components), key=lambda v: v.rank)  # AND = the lowest
        if res.verdict is C:
            assert res.conditions
        if res.verdict is U:
            assert res.unknown_reasons
        else:
            assert res.unknown_reasons == ()
        assert list(res.conditions) == sorted(res.conditions, key=lambda x: (x.key, x.kind.value, repr(x.value), x.text))
    assert {U, N} <= seen  # the spread of profiles reaches both unknown and not-met targets


@pytest.mark.parametrize("target", PILOTS)
def test_the_target_verdict_is_age_and_the_best_row(reg, target):
    rank = {N: 0, U: 1, C: 2, M: 3}
    for state, match in itertools.product(all_profiles(), [None, *MATCHES]):
        res = ev(reg, target, state, match)
        assert rank[res.verdict] == min(rank[res.age.verdict], max(rank[r.verdict] for r in res.rows))


# ---- worked examples: E07 and ARCHITECTURE §11.5 ---------------------------------------------------------------------------


def e07_state():
    return P(age=24, grade=10, creds=[], held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])])


def test_the_e07_example_profile_is_conditional_with_the_documented_conditions_in_the_documented_order(reg):
    res = ev(reg, SSMO, e07_state(), "exact")
    assert res.verdict is C and res.target.model_dump() == {
        "id": f"qual:{SSMO}", "code": SSMO, "slug": "AMH.Q2301", "title": "Specialized Sewing Machine Operator", "nsqf_level": 3.5}
    assert res.age.verdict is M and res.age.requirement_text == "Age: 18 years"
    e9 = row(res, 9)
    assert e9.verdict is C and e9.raw_text == "Previous relevant Qualification of NSQF Level 2.5 || 3 year relevant experience"
    assert [c.verdict for c in e9.components] == [C, C]
    assert e9.components[0].params == {"level": 2.5, "requires_relevance": True}
    assert e9.components[1].params == {"years": 3.0, "requires_relevance": True}
    inputs = [(u.field, u.value, u.evidence_class.value) for u in e9.components[0].inputs_used]
    for expected in [("profile.held_qualification_codes", (SMO,), "DECLARED"), (f"qual:{SMO}.nsqf_level", 2.5, "OFFICIAL"),
                     ("config.nsqf_level_match", "exact", "CONFIG")]:
        assert expected in inputs
    assert [(c.kind.value, c.key, c.value) for c in res.conditions] == [
        ("CONFIG", "config.nsqf_level_match", "exact"),
        ("DECLARATION", f"declarations[{SSMO}].relevant_experience_years", 3.0),
        ("DECLARATION", f"declarations[{SSMO}].relevant_prior_qualifications", (SMO,)),
    ]
    assert [f.code.value for f in res.quality_flags] == ["DEPENDS_ON_CONFIG", "DEPENDS_ON_DECLARATION"]
    # The E07 example is abridged and lists only E9 as decisive. Row 7 ("8th Grade pass || 3 year relevant experience") is
    # also CONDITIONAL for this profile (grade 10 >= 8, 3 relevant years >= 3), so both are decisive here.
    assert res.decisive_rule_ids == (f"rule:{SSMO}/E7", f"rule:{SSMO}/E9")
    assert [reason(c) for c in row(res, 2).components] == [R.DIPLOMA_YEAR_NOT_MODELLED, R.OVERLAY_NOT_APPROVED]  # as in the example
    assert row(res, 8).verdict is N  # level 3 against the held 2.5, under exact
    assert res.unknown_reasons == ()


def test_the_e07_profile_gives_the_same_verdict_under_both_interpretations_but_different_conditions_when_unset(reg):
    exact, at_least = ev(reg, SSMO, e07_state(), "exact"), ev(reg, SSMO, e07_state(), "at_least")
    assert exact.verdict is at_least.verdict is C
    assert [c.value for c in exact.conditions if c.kind.value == "CONFIG"] == ["exact"]
    assert [c.value for c in at_least.conditions if c.kind.value == "CONFIG"] == ["at_least"]
    unset = ev(reg, SSMO, e07_state(), None)  # row 9 is UNKNOWN(CONFIG_UNSET); row 7 needs no level, so the target holds
    assert unset.verdict is C and reason(comp(unset, 9, 1)) is R.CONFIG_UNSET
    assert unset.decisive_rule_ids == (f"rule:{SSMO}/E7",)
    assert [c.kind.value for c in unset.conditions] == ["DECLARATION"]


def test_architecture_11_5_worked_example_holds(reg):
    # "A profile holds AMH/Q0301, sets exact, declares AMH/Q0301 relevant and 3 relevant years: the row is CONDITIONAL with
    # conditions [relevance of Q0301, relevance of 3 years, nsqf_level_match=exact]."
    res = ev(reg, SSMO, P(age=30, held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])]), "exact")
    assert row(res, 9).verdict is C
    assert {c.key for c in res.conditions} == {"config.nsqf_level_match", f"declarations[{SSMO}].relevant_experience_years",
                                               f"declarations[{SSMO}].relevant_prior_qualifications"}


# ---- other pilot rows -------------------------------------------------------------------------------------------------------


def test_smo_row_1_met_by_grade_9_and_no_experience(reg):
    res = ev(reg, SMO, P(age=18, grade=9))
    assert row(res, 1).verdict is M and res.verdict is M
    assert res.decisive_rule_ids == (f"rule:{SMO}/E1",) and res.conditions == () and res.unknown_reasons == ()
    assert res.quality_flags == ()


def test_smo_row_1_grade_8_is_unknown_not_not_met_by_decision_d5_provisional_q_a(reg):
    res = ev(reg, SMO, P(age=18, grade=8, decl=[D(SMO, 1)]))
    c = comp(res, 1, 1)
    assert c.params == {"grade": 9, "below_required_verdict": "UNKNOWN"}
    assert c.verdict is U and reason(c) is R.REVIEW_FLAG  # PROVISIONAL-Q-A: the code, not the UNKNOWN verdict
    assert row(res, 3).verdict is C  # "8th grade pass || 1 year relevant experience"
    assert res.verdict is C and res.decisive_rule_ids == (f"rule:{SMO}/E3",)
    assert row(res, 4).verdict is N  # 5th grade pass || 4 years: 1 year declared is definitely short


def test_ic_experience_boundaries_and_grade_boundaries(reg):
    at = ev(reg, IC, P(age=20, grade=10, held=[], ext=(), decl=[D(IC, 1.5, [])]), "exact")
    assert row(at, 1).verdict is C and comp(at, 1, 2).condition.value == 1.5
    short = ev(reg, IC, P(age=20, grade=10, held=[], ext=(), decl=[D(IC, 1.4, [])]), "exact")
    assert comp(short, 1, 2).verdict is N and row(short, 1).verdict is N
    low_grade = ev(reg, IC, P(age=20, grade=9, held=[], ext=(), decl=[D(IC, 1.5, [])]), "exact")
    assert comp(low_grade, 1, 1).verdict is N  # grade 9 < 10, no equivalent and no D5 flag on this row


def test_ic_is_not_met_when_every_route_definitely_fails(reg):
    res = ev(reg, IC, P(age=20, grade=12, held=[], ext=(), decl=[D(IC, 1.4, [])]), "at_least")
    assert [r.verdict for r in res.rows] == [N, N, N, N] and res.verdict is N
    assert res.decisive_rule_ids == tuple(r.rule_id for r in res.rows)
    assert res.conditions == ()  # no component of any row is CONDITIONAL, so nothing is conditional on a declaration


def test_ps_credential_rows_and_equivalence_are_never_resolved_by_the_engine(reg):
    res = ev(reg, PS, P(age=25, grade=11, creds=[], held=[], ext=(), decl=[D(PS, 3, [])]), "exact")
    assert reason(comp(res, 1, 1)) is R.EQUIVALENCE_UNDEFINED      # "UG Diploma or equivalent"
    assert comp(res, 2, 1).verdict is N                            # "UG Certificate": nothing else held, definitely not
    assert reason(comp(res, 3, 1)) is R.EQUIVALENCE_UNDEFINED      # "12th or Equivalent": grade 11 < 12
    assert comp(res, 3, 2).verdict is N                            # 3 declared years < 4
    assert [r.verdict for r in res.rows] == [U, N, N, N]
    assert res.verdict is U and res.decisive_rule_ids == (f"rule:{PS}/E1",)
    assert [(u.code, u.ref) for u in res.unknown_reasons] == [(R.EQUIVALENCE_UNDEFINED, f"rule:{PS}/E1#c1")]
    other = ev(reg, PS, P(age=25, creds=["OTHER"], decl=[D(PS, 3)]))
    assert reason(comp(other, 2, 1)) is R.CREDENTIAL_ORDER_UNDEFINED


def test_ps_age_minimum_is_20(reg):
    res = ev(reg, PS, P(age=19, grade=12, creds=["UG_DIPLOMA"], decl=[D(PS, 20)]))
    assert res.age.verdict is N and res.verdict is N


def test_ps_credential_route_is_conditional_on_the_declared_experience(reg):
    res = ev(reg, PS, P(age=30, creds=["UG_DIPLOMA"], decl=[D(PS, 1)]))
    assert comp(res, 1, 1).verdict is M and comp(res, 1, 2).verdict is C and row(res, 1).verdict is C
    assert res.verdict is C and res.decisive_rule_ids == (f"rule:{PS}/E1",)
    assert [c.key for c in res.conditions] == [f"declarations[{PS}].relevant_experience_years"]


# ---- Q-B on the real build: non-authoritative levels never gain authority ---------------------------------------------------


def catalogue_with_level(reg, level):
    return next(q for q in reg.qualifications() if q.coverage.value == "CATALOGUE_ONLY" and q.nsqf_level.value == level)


@pytest.mark.parametrize("policy", list(UndecidedLevelUse))
@pytest.mark.parametrize(("target", "s_no", "level", "match"), [(SSMO, 9, 2.5, "exact"), (IC, 4, 2.5, "at_least"), (PS, 4, 5.0, "at_least")])
def test_q_b_a_display_only_catalogue_level_that_would_satisfy_the_rule_is_never_compared(reg, policy, target, s_no, level, match):
    held = catalogue_with_level(reg, level)
    assert held.nsqf_level.engine_use.value == "DISPLAY_ONLY" and held.nsqf_level.value >= reg.qualification_by_code(target).eligibility.rows[s_no - 1].components[0].params["level"]
    res = ev(reg, target, P(age=30, held=[held.code], ext=(), decl=[D(target, 5, [held.code])]), match, undecided_level_use=policy)
    c = comp(res, s_no, 1)
    assert c.verdict is U and reason(c) is R.ENGINE_USE_UNDECIDED  # the number exists, but it is "shown, never computed"
    assert f"qual:{held.code}.nsqf_level" not in {u.field for u in c.inputs_used}


def test_q_b_a_conflicted_or_uncertain_level_on_the_real_rules_is_capped_under_both_policies(reg):
    base = reg.qualification_by_code(SMO).model_dump(mode="json")
    for patch, expected in [({"conflict_id": "conflict:OV-777"}, R.SOURCE_CONFLICT), ({"value_status": "PARSED_UNCERTAIN"}, R.UNCERTAIN_EXTRACTION)]:
        edited = Qualification.model_validate({**base, "nsqf_level": {**base["nsqf_level"], **patch}})
        others = [q for q in reg.qualifications() if q.code != SMO]
        mutated = Registry.from_records(qualifications=[edited, *others], nos_units=reg.nos_units(), conflicts=reg.conflicts(), build=reg.build)
        for policy in UndecidedLevelUse:
            res = ev(mutated, SSMO, P(held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])]), "exact", undecided_level_use=policy)
            assert reason(comp(res, 9, 1)) is expected and comp(res, 9, 1).verdict is U


# ---- determinism ----------------------------------------------------------------------------------------------------------


def test_repeated_evaluation_is_byte_identical(reg):
    for target, state, match, policy in itertools.product(PILOTS, all_profiles(), [None, *MATCHES], list(UndecidedLevelUse)):
        first = ev(reg, target, state, match, undecided_level_use=policy).model_dump_json()
        assert ev(reg, target, state, match, undecided_level_use=policy).model_dump_json() == first


def test_a_reloaded_registry_gives_identical_results(reg, build_dir):
    again = load(build_dir)
    for target, state in itertools.product(PILOTS, all_profiles()):
        assert ev(again, target, state, "at_least").model_dump_json() == ev(reg, target, state, "at_least").model_dump_json()
