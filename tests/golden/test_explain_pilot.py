"""P3.8 golden tests: explanation templates over the four curated pilots on the REAL curated build (skipped when absent).

Scope: ``explain.for_eligibility`` only. All profiles are synthetic and hypothetical.

Where each expectation comes from (none is copied from template output, and none from the first smoke run of the templates):

* Hours: the table in ARCHITECTURE §8.4 (T / P / OJT-mandatory / total for the four pilots), checked against the text.
* Verdicts: the hand-derived cases of ``tests/golden/test_eligibility_pilot.py`` (SMO grade 9 -> MET; the E07 profile on SSMO
  -> CONDITIONAL with rows 7 and 9 deciding; an empty profile -> UNKNOWN for every pilot; age 17 -> NOT_MET for every pilot;
  SSMO rows 2-4 carry ``OVERLAY_NOT_APPROVED`` as the C5 test states). Each case re-asserts its verdict first, so a change in
  the engine fails there and not in a wording check.
* Cited evidence IDs: the evidence IDs stored on the curated rules (``EligibilitySpec``) and on the hours, claims and
  qualification records, and each ID is resolved through ``Registry.evidence_by_id`` to a stored OFFICIAL record whose source
  document is the qualification's own primary QF. The engine result is not the source of any expected ID.
* Source page: read from the evidence record; SSMO's ``3-4`` also matches the API_SPEC E10 example (illustrative there).

What these tests cannot establish: an ``Evidence`` record holds a source, a page, a method and a value status but not the
value, so no test here (or anywhere) can confirm that a record *states* a given figure. They show that each cited ID resolves
to a stored record of the right class, source and page, and that the figures equal the documented ones.
"""

import itertools
import re
from pathlib import Path

import pytest
import yaml

from skillgraph.eligibility.evaluate import (
    EngineConfig,
    ExternalQualification,
    PostSchoolCredential,
    ProfileState,
    TargetDeclaration,
    evaluate,
)
from skillgraph.explain import CAVEAT_TEXT, for_eligibility
from skillgraph.explain.lint import find_forbidden
from skillgraph.model.eligibility import UnknownReasonCode as R
from skillgraph.model.eligibility import Verdict
from skillgraph.model.evidence import EvidenceClass
from skillgraph.registry import Registry, load

SMO, SSMO, IC, PS = "AMH/Q0301", "AMH/Q2301", "AMH/Q0103", "AMH/Q2101"
PILOTS = (SMO, SSMO, IC, PS)
N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
PREFIX = {M: "Met:", C: "Conditional:", U: "Unknown:", N: "Not met:"}
REPO = Path(__file__).resolve().parents[2]
# ARCHITECTURE §8.4: official notional hours (theory, practical, OJT mandatory, total) of the four pilots
ARCH_HOURS = {SMO: (90, 210, 0, 300), SSMO: (150, 270, 0, 420), IC: (150, 240, 30, 420), PS: (180, 330, 60, 570)}


@pytest.fixture(scope="session")
def _registry(build_dir) -> Registry:
    return load(build_dir)


@pytest.fixture
def reg(_registry) -> Registry:
    assert _registry.build is not None and _registry.build.validation == "PASSED"
    return _registry


def P(*, age=30, grade=None, creds=None, held=None, ext=None, decl=()) -> ProfileState:
    return ProfileState(
        age_years=age, school_grade_passed=grade,
        post_school_credentials=None if creds is None else tuple(PostSchoolCredential(type=t) for t in creds),
        held_qualification_codes=held, external_qualifications=ext, declarations=tuple(decl))


def D(code, years=None, rel=None) -> TargetDeclaration:
    return TargetDeclaration(target_code=code, relevant_experience_years=years, relevant_prior_qualifications=rel)


def run(reg, code, state, match=None):
    return evaluate(reg.qualification_by_code(code).eligibility, state, EngineConfig(nsqf_level_match=match), reg)


E07 = P(age=24, grade=10, creds=[], held=[SMO], ext=(), decl=[D(SSMO, 3, [SMO])])  # the E07 example profile
PROFILES = [
    ProfileState(),
    P(age=17, grade=12, creds=["UG_DIPLOMA"], held=[SMO, SSMO, IC], ext=(), decl=[D(c, 20, [SMO, SSMO, IC]) for c in PILOTS]),
    P(age=18, grade=8, creds=[], held=[], ext=(), decl=[D(c, 0, []) for c in PILOTS]),
    E07,
    P(age=40, grade=12, creds=["UG_CERTIFICATE", "OTHER"], held=[SMO, SSMO],
      ext=(ExternalQualification(ref="ext-x", label="X", nsqf_level=4.0),), decl=[D(c, 5, [SMO, "ext-x"]) for c in PILOTS]),
    P(age=21, held=[SMO], ext=None, decl=[D(IC, 3, [SMO])]),
]


def sweep(reg):
    for code, state, match in itertools.product(PILOTS, PROFILES, (None, "exact", "at_least")):
        yield run(reg, code, state, match)


def stored_component_ids(reg, code) -> dict[str, str]:
    """component id -> the evidence id stored on that component of the curated rule (not read from any result)."""
    spec = reg.qualification_by_code(code).eligibility
    out = {f"{spec.age_rule.id}#c1": spec.age_rule.components[0].evidence_id}
    for row in spec.rows:
        out |= {f"{row.id}#c{n}": c.evidence_id for n, c in enumerate(row.components, 1)}
    return out


def stored_hours_ids(reg, code) -> set[str]:
    h = reg.qualification_by_code(code).hours
    return {v.evidence_id for v in (h.theory, h.practical, h.ojt_mandatory, h.ojt_recommended, h.total) if v is not None}


def stored_claim_ids(reg) -> set[str]:
    return {c.evidence_id for q in reg.qualifications() for c in q.progression_claims}


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


# ---- the build ------------------------------------------------------------------------------------------------------------


def test_the_real_build_is_valid_and_no_overlay_is_approved(reg):
    assert reg.build.validation == "PASSED"
    assert yaml.safe_load((REPO / "config" / "overlay_approvals.yaml").read_text(encoding="utf-8"))["approved"] == []


# ---- hours: documented figures, stored records, recorded page ----------------------------------------------------------------


@pytest.mark.parametrize("code", PILOTS)
def test_hours_state_the_documented_figures_and_cite_only_stored_hours_records_with_their_recorded_page(reg, code):
    theory, practical, ojt, total = ARCH_HOURS[code]
    h = next(i for i in for_eligibility(run(reg, code, ProfileState()), reg) if i.kind == "HOURS")
    for expected in (f"{total} in total", f"theory {theory}", f"practical {practical}", f"on-the-job training (mandatory) {ojt}"):
        assert expected in h.text
    assert h.evidence_class is EvidenceClass.OFFICIAL and set(h.evidence_ids) == stored_hours_ids(reg, code)
    records = [reg.evidence_by_id(e) for e in h.evidence_ids]
    assert {r.evidence_class for r in records} == {EvidenceClass.OFFICIAL}
    pages = {r.page for r in records}
    assert pages and None not in pages
    assert f"Source page: {next(iter(pages))}." in h.text if len(pages) == 1 else all(p in h.text for p in pages)
    # the records belong to this qualification's own primary QF, not to some other document
    sources = {reg.source_by_id(r.source_id) for r in records}
    assert len(sources) == 1
    (src,) = sources
    assert src.role.value == "PRIMARY" and tokens(reg.qualification_by_code(code).titles.qf) <= tokens(src.title)


def test_the_ssmo_hours_page_matches_the_api_spec_e10_example(reg):
    # API_SPEC E10 shows the SSMO QF hours record with page "3-4" (the example is illustrative; the build agrees)
    h = next(i for i in for_eligibility(run(reg, SSMO, ProfileState()), reg) if i.kind == "HOURS")
    assert {reg.evidence_by_id(e).page for e in h.evidence_ids} == {"3-4"} and "Source page: 3-4." in h.text


# ---- verdict cases with hand-derived expectations ----------------------------------------------------------------------------


def test_met_smo_row_1_with_grade_9_is_explained_as_met_with_its_one_deciding_row(reg):
    res = run(reg, SMO, P(age=18, grade=9))
    assert res.verdict is M and res.decisive_rule_ids == (f"rule:{SMO}/E1",)  # the pilot test's hand-derived case
    items = for_eligibility(res, reg)
    assert items[0].text.startswith("Met:") and "Deciding entry row: 1." in items[0].text
    assert [i for i in items if i.kind in ("CONDITION", "WHAT_WOULD_RESOLVE")] == []  # nothing to confirm, nothing unresolved
    stored = stored_component_ids(reg, SMO)
    assert set(items[0].evidence_ids) == {stored[f"rule:{SMO}/AGE#c1"], stored[f"rule:{SMO}/E1#c1"], stored[f"rule:{SMO}/E1#c2"]}


def test_the_e07_profile_is_explained_as_conditional_with_each_condition_citing_only_the_cells_that_carry_it(reg):
    res = run(reg, SSMO, E07, "exact")
    assert res.verdict is C and res.decisive_rule_ids == (f"rule:{SSMO}/E7", f"rule:{SSMO}/E9")  # pilot test, E07 example
    items = for_eligibility(res, reg)
    assert items[0].text.startswith("Conditional:") and "Deciding entry rows: 7, 9." in items[0].text
    stored = stored_component_ids(reg, SSMO)
    c = lambda row, n: stored[f"rule:{SSMO}/E{row}#c{n}"]  # noqa: E731
    by_key = {cond.key: item for cond, item in zip(res.conditions, [i for i in items if i.kind == "CONDITION"], strict=True)}
    # E9#c1 is the level component (relevance of SMO under the exact reading); E7#c2 and E9#c2 are the 3-year experience cells
    assert by_key["config.nsqf_level_match"].evidence_ids == (c(9, 1),)
    assert by_key[f"declarations[{SSMO}].relevant_prior_qualifications"].evidence_ids == (c(9, 1),)
    assert by_key[f"declarations[{SSMO}].relevant_experience_years"].evidence_ids == (c(7, 2), c(9, 2))
    cited = {e for i in by_key.values() for e in i.evidence_ids}
    assert c(7, 1) not in cited  # "8th Grade pass" is MET and carries no condition
    assert not cited & {c(8, 1), c(8, 2)}  # row 8 is NOT_MET (level 3 against 2.5) and is not a deciding row
    assert by_key["config.nsqf_level_match"].evidence_class is EvidenceClass.CONFIG
    assert by_key[f"declarations[{SSMO}].relevant_experience_years"].evidence_class is EvidenceClass.DECLARED


@pytest.mark.parametrize("code", PILOTS)
def test_an_empty_profile_is_explained_as_unknown_with_one_cause_specific_resolution_per_reason(reg, code):
    res = run(reg, code, ProfileState())
    assert res.verdict is U and res.unknown_reasons[0].code is R.INPUT_NOT_DECLARED  # pilot test, empty profile
    items = for_eligibility(res, reg)
    assert items[0].text.startswith("Unknown:") and "Unknown is not a negative result" in items[0].text
    resolve = [i for i in items if i.kind == "WHAT_WOULD_RESOLVE"]
    assert len(resolve) == len(res.unknown_reasons)
    first = resolve[0]
    assert first.text.startswith(res.unknown_reasons[0].text) and "Adding the missing input to the profile" in first.text
    stored = stored_component_ids(reg, code)
    assert all(set(i.evidence_ids) <= set(stored.values()) for i in resolve)


def test_ssmo_rows_2_to_4_pending_overlays_get_overlay_guidance_not_a_generic_source_review(reg):
    res = run(reg, SSMO, ProfileState())
    overlay_reasons = [r for r in res.unknown_reasons if r.code is R.OVERLAY_NOT_APPROVED]
    assert len(overlay_reasons) == 3  # rows 2, 3 and 4 (the C5 test: [first reason, OVERLAY_NOT_APPROVED] each)
    items = for_eligibility(res, reg)
    overlay_items = [i for i in items if i.kind == "WHAT_WOULD_RESOLVE" and i.text.startswith(overlay_reasons[0].text)]
    assert len(overlay_items) == 3
    for i in overlay_items:
        assert "overlay approvals" in i.text and "neither makes nor assumes that approval" in i.text
        assert "review of the source" not in i.text
    rows = {r.s_no: i for r, i in zip(res.rows, [x for x in items if x.kind == "ROW_REASONING"], strict=True)}
    for s_no, overlay in ((2, "OV-002"), (3, "OV-003"), (4, "OV-004")):  # the C5 test's flag references
        assert overlay in rows[s_no].text and "pending overlay proposal" in rows[s_no].text
    assert yaml.safe_load((REPO / "config" / "overlay_approvals.yaml").read_text(encoding="utf-8"))["approved"] == []


@pytest.mark.parametrize("code", PILOTS)
def test_age_17_is_explained_as_not_met_on_the_age_rule_and_cites_the_stored_age_cell(reg, code):
    rich = P(age=17, grade=12, creds=["UG_DIPLOMA", "UG_CERTIFICATE"], held=[SMO, SSMO, IC], ext=(),
             decl=[D(code, 30, [SMO, SSMO, IC])])
    res = run(reg, code, rich, "exact")
    assert res.verdict is N  # the pilot test's C4 case
    items = for_eligibility(res, reg)
    assert items[0].text.startswith("Not met:") and "age requirement is not met" in items[0].text
    age = next(i for i in items if i.kind == "AGE_REASONING")
    assert age.evidence_ids == (stored_component_ids(reg, code)[f"rule:{code}/AGE#c1"],)
    assert "profile.age_years = 17 (declared)" in age.text
    assert [i for i in items if i.kind == "WHAT_WOULD_RESOLVE"] == []  # no advice is given for a definite failure


# ---- every pilot result: structure, citations, wording ---------------------------------------------------------------------


def test_the_sweep_exercises_all_four_verdicts_and_each_summary_names_its_verdict(reg):
    seen = set()
    for res in sweep(reg):
        seen.add(res.verdict)
        items = for_eligibility(res, reg)
        assert items[0].kind == "VERDICT_SUMMARY" and items[0].text.startswith(PREFIX[res.verdict])
        assert items[-1].kind == "CAVEAT" and items[-1].text == CAVEAT_TEXT and sum(i.kind == "CAVEAT" for i in items) == 1
        assert len([i for i in items if i.kind == "ROW_REASONING"]) == len(res.rows)
        assert len([i for i in items if i.kind == "CONDITION"]) == len(res.conditions)
        assert len([i for i in items if i.kind == "WHAT_WOULD_RESOLVE"]) == (
            len(res.unknown_reasons) if res.verdict is U else 1 if res.verdict is C else 0)
    assert seen == set(Verdict)


def test_every_cited_id_resolves_to_a_stored_official_record_from_the_right_stored_source(reg):
    claims = stored_claim_ids(reg)
    for res in sweep(reg):
        code = res.target.code
        components, hours = set(stored_component_ids(reg, code).values()), stored_hours_ids(reg, code)
        for i in for_eligibility(res, reg):
            for e in i.evidence_ids:
                rec = reg.evidence_by_id(e)  # raises UnknownEntityError for an ID the registry does not hold
                assert rec.evidence_class is EvidenceClass.OFFICIAL and rec.source_id is not None and (rec.page or rec.location)
                reg.source_by_id(rec.source_id)
            if i.kind == "HOURS":
                assert set(i.evidence_ids) <= hours
            elif i.kind == "PROGRESSION_CLAIM":
                assert set(i.evidence_ids) <= claims
            elif i.kind != "CAVEAT":
                assert set(i.evidence_ids) <= components, (code, i.kind)
            if i.kind != "CAVEAT" and i.evidence_class in (EvidenceClass.OFFICIAL, EvidenceClass.RULE_DERIVED):
                assert i.evidence_ids


def test_no_generated_or_engine_supplied_text_matches_a_forbidden_claim_pattern(reg):
    engine_texts, generated = set(), set()
    for res in sweep(reg):
        for c in (res.age, *(c for r in res.rows for c in r.components)):
            engine_texts.add(c.requirement_text)
            engine_texts |= {t for t in (c.unknown_reason and c.unknown_reason.text, c.condition and c.condition.text) if t}
        engine_texts |= {c.text for c in res.conditions} | {r.text for r in res.unknown_reasons}
        engine_texts |= {r.raw_text for r in res.rows} | {f.message for r in res.rows for f in r.flags}
        generated |= {i.text for i in for_eligibility(res, reg)}
    assert len(engine_texts) > 50 and len(generated) > 100  # the sweep produced a real variety of text
    assert [(t, find_forbidden(t)) for t in sorted(engine_texts | generated) if find_forbidden(t)] == []


# ---- determinism and non-interference ---------------------------------------------------------------------------------------


def test_output_is_identical_across_repeated_runs_and_a_reloaded_build(reg, build_dir):
    first = [[i.model_dump(mode="json") for i in for_eligibility(r, reg)] for r in sweep(reg)]
    again = [[i.model_dump(mode="json") for i in for_eligibility(r, reg)] for r in sweep(reg)]
    fresh = load(build_dir)
    reloaded = [[i.model_dump(mode="json") for i in for_eligibility(r, fresh)] for r in sweep(fresh)]
    assert first == again == reloaded


def test_explaining_changes_no_result_and_no_stored_record(reg):
    q_before = {q.code: q.model_dump_json() for q in reg.qualifications()}
    for res in sweep(reg):
        before = res.model_dump_json()
        for_eligibility(res, reg)
        assert res.model_dump_json() == before and res.explanation == ()
    assert q_before == {q.code: q.model_dump_json() for q in reg.qualifications()}
