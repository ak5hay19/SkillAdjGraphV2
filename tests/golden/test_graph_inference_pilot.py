"""P3.5 golden cases: experimental inference edges of the four curated pilots, on the real local build (TASKS P3.5 criteria).

Expectations come from the contract, not from the builder's output: TASKS P3.5 ("SMO-SSMO share unit group 8153, so they get
an NCO_GROUP_PROXIMITY edge"; every inference edge is INFERENCE and experimental; off unless requested), ARCHITECTURE §10.3
(inference edges never create, remove or reorder feasibility), §13.4 and §8.5 (OBS-01). The NCO codes are read independently,
through the registry's occupation records. Values that are *observations of the current build* are labelled so.
Skipped, not failed, when ``data/`` or an installed build of the current curation code is absent.
"""

import itertools
import json

import pytest

from skillgraph.eligibility.evaluate import EngineConfig, PostSchoolCredential, ProfileState, TargetDeclaration, evaluate
from skillgraph.graph import (
    EdgeType,
    build_inference_edges,
    build_static_edges,
    claim_title_candidates,
    inference_legend,
)
from skillgraph.model.evidence import EvidenceClass
from skillgraph.registry import Registry, load

SMO, SSMO, IC, PS = "qual:AMH/Q0301", "qual:AMH/Q2301", "qual:AMH/Q0103", "qual:AMH/Q2101"
PILOT_CODES = ("AMH/Q0301", "AMH/Q2301", "AMH/Q0103", "AMH/Q2101")
PROX = EdgeType.NCO_GROUP_PROXIMITY


@pytest.fixture(scope="module")
def registry(build_dir):
    reg = load(build_dir)
    assert reg.build is not None and reg.build.validation == "PASSED"  # the P3.3 convention: golden on a validated build
    return reg


@pytest.fixture(scope="module")
def static(registry):
    return build_static_edges(registry)


@pytest.fixture(scope="module")
def both(registry):
    return build_static_edges(registry, include_inference=True)


def dump(edges) -> str:
    return json.dumps([e.model_dump(mode="json") for e in edges], sort_keys=True)


# ---- TASKS P3.5 acceptance criteria -----------------------------------------------------------------------------------


def test_smo_and_ssmo_share_unit_group_8153_so_they_get_an_inference_edge(registry, both):
    """TASKS P3.5: "SMO-SSMO share unit group 8153, so they get an NCO_GROUP_PROXIMITY edge"."""
    # the group is read independently of the builder: from the occupation records of the two stated codes
    groups = {q: {registry.occupation_by_nco_code(c.value).nco_levels.family for c in registry.qualification_by_id(q).nco_codes}
              for q in (SMO, SSMO)}
    assert groups[SMO] == groups[SSMO] == {"8153"}
    (edge,) = [e for e in both if e.type is PROX and {e.source, e.target} == {SMO, SSMO}]
    assert (edge.source, edge.target) == tuple(sorted((SMO, SSMO)))
    assert edge.attributes == {"group_digits": 4, "shared_groups": ["8153"],
                               "codes_by_qualification": {"AMH/Q0301": ["8153.0101"], "AMH/Q2301": ["8153.0103"]}}
    assert edge.id == "e:NCO_GROUP_PROXIMITY:AMH/Q0301:AMH/Q2301"


def test_every_inference_edge_is_inference_and_experimental_and_flagged(both):
    inference = [e for e in both if e.type in (PROX, EdgeType.TITLE_SIMILARITY)]
    assert inference
    for e in inference:
        assert e.evidence_class is EvidenceClass.INFERENCE and e.experimental is True and e.directed is False
        assert [f.code.value for f in e.flags] == ["INFERENCE_EXPERIMENTAL"]
    assert not [e for e in both if e.experimental and e.type is not PROX]
    assert all(e.evidence_class is not EvidenceClass.INFERENCE and not e.experimental for e in both if e.type is not PROX)


def test_the_inference_edges_are_off_unless_requested(registry, static):
    assert build_static_edges(registry, include_inference=False) == static == build_static_edges(registry)
    assert not [e for e in static if e.experimental or e.evidence_class is EvidenceClass.INFERENCE]
    assert {e.type for e in static} == {EdgeType.INCLUDES_NOS, EdgeType.SHARES_NOS, EdgeType.PROGRESSION_CLAIM, EdgeType.ALIGNED_TO_NCO}


def test_the_only_pair_is_smo_ssmo_at_both_levels(registry):
    """Observation of build cb-601c0399c999: IC states 7543.0301 and PS 3122.3551, so neither shares a 4-digit unit group
    (7543, 3122) or a 3-digit group (754, 312) with another pilot; no catalogue-only record states a code."""
    assert [(e.source, e.target) for e in build_inference_edges(registry)] == [tuple(sorted((SMO, SSMO)))]
    three = build_inference_edges(registry, nco_group_digits=3)
    assert [(e.source, e.target, e.attributes["shared_groups"]) for e in three] == [(*sorted((SMO, SSMO)), ["815"])]


# ---- static edges unchanged -------------------------------------------------------------------------------------------


def test_static_edges_are_identical_with_and_without_inference(static, both):
    assert dump([e for e in both if not e.experimental]) == dump(static)
    assert len(static) == 40 and len(both) == 41  # observation of this build: 40 static edges plus the one inference edge


def test_obs01_is_unchanged_and_the_inference_pair_is_not_a_documented_overlap(both):
    shares = {(e.source, e.target) for e in both if e.type is EdgeType.SHARES_NOS}
    assert shares == {tuple(sorted(p)) for p in ((SSMO, IC), (IC, PS), (SSMO, PS))}
    assert tuple(sorted((SMO, SSMO))) not in shares  # SMO has no SHARES_NOS edge; the inference edge does not create one
    assert not [e for e in both if e.type is EdgeType.SHARES_NOS and SMO in (e.source, e.target)]


def test_no_progression_claim_edge_targets_a_qualification_even_with_inference(both):
    claims = [e for e in both if e.type is EdgeType.PROGRESSION_CLAIM]
    assert len(claims) == 6 and all(e.target.startswith("claim:") for e in claims)


def test_sorted_by_type_source_target_and_deterministic(build_dir, both):
    assert both == sorted(both, key=lambda e: (e.type.value, e.source, e.target))
    assert dump(both) == dump(build_static_edges(load(build_dir), include_inference=True))  # a second, independent load


# ---- provenance -------------------------------------------------------------------------------------------------------


def test_the_inference_edge_cites_the_official_evidence_of_the_two_stated_codes(registry, both):
    (edge,) = [e for e in both if e.type is PROX]
    aligned = {(e.source, e.target): e for e in both if e.type is EdgeType.ALIGNED_TO_NCO}
    expected = sorted(set(aligned[(SMO, "nco:8153.0101")].evidence_ids) | set(aligned[(SSMO, "nco:8153.0103")].evidence_ids))
    assert edge.evidence_ids == expected and len(expected) == 2
    for eid in edge.evidence_ids:
        ev = registry.evidence_by_id(eid)
        assert ev.evidence_class is EvidenceClass.OFFICIAL  # the inputs are documented; the inference is not
        assert registry.source_by_id(ev.source_id)  # traceable to a source document


def test_the_legend_entry_exists_for_the_edge_type_and_says_what_it_does_not_mean():
    (entry,) = inference_legend()
    assert entry.edge_type is PROX and entry.evidence_class is EvidenceClass.INFERENCE and entry.does_not_mean


# ---- inference never changes eligibility, authoritative records or feasibility ----------------------------------------


def profiles():
    held_sets = (None, (), ("AMH/Q0301",), ("AMH/Q2301",), ("AMH/Q0103", "AMH/Q0301"))
    for age, grade, held, creds in itertools.product((17, 30), (None, 10), held_sets, (None, ())):
        yield ProfileState(
            age_years=age, school_grade_passed=grade, held_qualification_codes=held,
            external_qualifications=() if held is not None else None,
            post_school_credentials=None if creds is None else tuple(PostSchoolCredential(type=t) for t in creds),
            declarations=tuple(TargetDeclaration(target_code=c, relevant_experience_years=3, relevant_prior_qualifications=held)
                               for c in PILOT_CODES))


def all_results(reg: Registry):
    out = []
    for state in profiles():
        for match in (None, "exact", "at_least"):
            for code in PILOT_CODES:
                spec = reg.qualification_by_code(code).eligibility
                out.append(evaluate(spec, state, EngineConfig(nsqf_level_match=match), reg).model_dump_json())
    return out


def test_building_inference_edges_changes_no_record_and_no_eligibility_result(registry):
    before_records = (registry.qualifications(), registry.nos_units(), registry.occupations(), registry.conflicts())
    before = all_results(registry)
    build_static_edges(registry, include_inference=True)
    build_static_edges(registry, include_inference=True, nco_group_digits=3)
    claim_title_candidates(registry)
    assert (registry.qualifications(), registry.nos_units(), registry.occupations(), registry.conflicts()) == before_records
    assert all_results(registry) == before and len(before) > 100


def test_eligibility_results_do_not_depend_on_which_inference_edges_exist(registry):
    """A registry whose records state no NCO code has no inference edge at all; every eligibility result is identical.
    (Evidence is left out of the copy: the evaluator never resolves it, and the edge builder is not run on the copy.)"""
    stripped = Registry.from_records(
        qualifications=[q.model_copy(update={"nco_codes": []}) for q in registry.qualifications()],
        nos_units=registry.nos_units(), occupations=registry.occupations(), sources=registry.sources(),
        conflicts=registry.conflicts(),
        eligibility_source_rows=[r for q in registry.qualifications() for r in registry.eligibility_source_rows(q.id)])
    assert build_inference_edges(stripped) == [] and len(build_inference_edges(registry)) == 1
    assert all_results(stripped) == all_results(registry)


# ---- claim-title candidates (unreviewed; not edges) -------------------------------------------------------------------


def test_the_contract_examples_on_the_real_catalogue(registry):
    """TASKS P3.5 / DQ-15: "Sampling Coordinator" -> AMH/Q1801; "QC Executive - Sewing Line" has no exact match."""
    report = claim_title_candidates(registry)
    by_claim = {c.claim_id: c for c in report.candidates}
    assert by_claim["claim:AMH/Q2301/P1"].candidate_qualification_id == "qual:AMH/Q1801"
    assert by_claim["claim:AMH/Q2301/P1"].candidate_title == "Sampling Coordinator"
    assert {"claim:AMH/Q0103/P1", "claim:AMH/Q2101/P1"} <= set(report.unmatched_claim_ids)  # the two "QC Executive - Sewing Line" claims


def test_the_candidates_of_this_build_are_exactly_three_and_all_unreviewed(registry):
    """Observation of build cb-601c0399c999 under the D-21 normalisation (the third is not anticipated by the contract:
    "Sewing Machine Operator-Knits" equals the catalogue title "Sewing Machine Operator Knits" once the hyphen is a separator)."""
    report = claim_title_candidates(registry)
    assert [(c.claim_id, c.candidate_qualification_id) for c in report.candidates] == [
        ("claim:AMH/Q0301/P1", "qual:AMH/Q0305"), ("claim:AMH/Q0301/P2", "qual:AMH/Q2301"), ("claim:AMH/Q2301/P1", "qual:AMH/Q1801")]
    assert report.unmatched_claim_ids == ["claim:AMH/Q0103/P1", "claim:AMH/Q2101/P1", "claim:AMH/Q2101/P2"]
    assert all(c.status == "UNREVIEWED_CANDIDATE" and c.evidence_class is EvidenceClass.INFERENCE and c.candidate_count == 1
               and not c.target_is_source for c in report.candidates)
    total = sum(len(q.progression_claims) for q in registry.qualifications())
    assert len({c.claim_id for c in report.candidates}) + len(report.unmatched_claim_ids) == total == 6


def test_no_claim_of_the_build_has_a_resolved_target_and_candidates_do_not_set_one(registry):
    claim_title_candidates(registry)
    assert all(c.resolved_target is None for q in registry.qualifications() for c in q.progression_claims)
