"""P3.5 experimental inference edges (ARCHITECTURE §10.1, §10.3, §13.4; API_SPEC E08; TASKS P3.5). Synthetic fixtures only:
TEST/... codes, registries assembled with ``Registry.from_records``, no file and no real data. The real-build golden cases
are in ``tests/golden/test_graph_inference_pilot.py``.

Expected values come from the documented contract (an NCO_GROUP_PROXIMITY edge joins two qualifications whose stated NCO
codes share a 4-digit unit group, or a 3-digit group when configured; it is INFERENCE and experimental; it is absent unless
requested) and from the fixture's own construction (which code each qualification states), never from the builder's output.
The choices that the specification leaves open are D-15 ... D-23 in ``skillgraph.graph.inference`` and ``claim_candidates``;
a test that depends on one says so.
"""

import ast
import json
import random
from pathlib import Path

import pytest
from model_factory import catalogue_only, curated, official
from pydantic import ValidationError
from test_graph_edges import EVIDENCE, mk_qual, records, registry, row, world

from skillgraph.graph import (
    INFERENCE_EDGE_TYPES,
    STATIC_EDGE_TYPES,
    ClaimTitleCandidate,
    EdgeBuildError,
    EdgeType,
    GraphEdge,
    build_inference_edges,
    build_static_edges,
    claim_title_candidates,
    inference_legend,
    normalise_name,
    render_review_section,
    static_legend,
)
from skillgraph.model.evidence import EvidenceClass, OfficialValued, QualityFlagCode
from skillgraph.model.ids import slug_of
from skillgraph.model.qualification import Qualification
from skillgraph.registry import Registry

SRC = Path(__file__).resolve().parents[2] / "src" / "skillgraph"
PROX = EdgeType.NCO_GROUP_PROXIMITY


def key(n: int) -> str:
    return f"TEST/Q900{n}"


def qid(n: int) -> str:
    return f"qual:{key(n)}"


def eid(n: int, i: int = 0) -> str:
    """Evidence id of the i-th stated NCO code of qualification n (the fixture writes ``800 + 10 n + i``)."""
    return f"ev:{800 + 10 * n + i:016x}"


def nco_world(**codes) -> list[Qualification]:
    """``codes`` maps q<n> -> the NCO codes that qualification n states."""
    return [mk_qual(int(name[1:]), [row(2, "nos:TEST/N9001")], nco=tuple(c)) for name, c in codes.items()]


def prox(reg, **kw) -> list[GraphEdge]:
    return build_inference_edges(reg, **kw)


def pairs(edges) -> set[tuple[str, str]]:
    return {(e.source, e.target) for e in edges}


# ---- the shared definition --------------------------------------------------------------------------------------------


@pytest.fixture
def smo_ssmo() -> Registry:
    """The pilot situation: 1 and 2 state different 8153 codes; 3 states 7543; 4 states 7549 (same 754, other 4 digits);
    5 states 8154 (same 815, other 4 digits); 6 states nothing; 7 states 8153.0101 twice-over in one group (two codes)."""
    return registry(nco_world(
        q1=["8153.0101"], q2=["8153.0103"], q3=["7543.0301"], q4=["7549.0101"], q5=["8154.0101"], q6=[],
        q7=["8153.0101", "8153.0104"],
    ))


def test_the_default_level_is_the_4_digit_unit_group(smo_ssmo):
    edges = prox(smo_ssmo)
    assert pairs(edges) == {(qid(1), qid(2)), (qid(1), qid(7)), (qid(2), qid(7))}
    assert all(e.attributes["group_digits"] == 4 and e.attributes["shared_groups"] == ["8153"] for e in edges)


def test_the_3_digit_level_is_configurable_and_widens_the_match(smo_ssmo):
    edges = prox(smo_ssmo, nco_group_digits=3)
    assert pairs(edges) == {
        (qid(1), qid(2)), (qid(1), qid(5)), (qid(1), qid(7)), (qid(2), qid(5)), (qid(2), qid(7)), (qid(5), qid(7)),  # 815
        (qid(3), qid(4)),  # 754
    }
    by = {(e.source, e.target): e for e in edges}
    assert by[(qid(3), qid(4))].attributes["shared_groups"] == ["754"]
    assert by[(qid(1), qid(2))].attributes["shared_groups"] == ["815"]
    assert all(e.attributes["group_digits"] == 3 for e in edges)


def test_every_4_digit_pair_is_also_a_3_digit_pair(smo_ssmo):
    assert pairs(prox(smo_ssmo)) <= pairs(prox(smo_ssmo, nco_group_digits=3))


def test_the_same_full_code_is_in_the_same_unit_group(smo_ssmo):
    reg = registry(nco_world(q1=["8153.0101"], q2=["8153.0101"]))
    assert pairs(prox(reg)) == {(qid(1), qid(2))}


def test_codes_of_different_groups_make_no_edge():
    reg = registry(nco_world(q1=["8153.0101"], q2=["8154.0101"], q3=["7543.0301"]))
    assert prox(reg) == []
    assert prox(reg, nco_group_digits=3) == [e for e in prox(reg, nco_group_digits=3) if e.attributes["shared_groups"] == ["815"]]
    assert pairs(prox(reg, nco_group_digits=3)) == {(qid(1), qid(2))}


def test_two_codes_of_one_qualification_in_one_group_make_no_self_edge_and_both_are_listed(smo_ssmo):
    e = {(x.source, x.target): x for x in prox(smo_ssmo)}[(qid(1), qid(7))]
    assert e.attributes["codes_by_qualification"] == {key(1): ["8153.0101"], key(7): ["8153.0101", "8153.0104"]}
    assert not [x for x in prox(smo_ssmo) if x.source == x.target]
    lone = registry(nco_world(q1=["8153.0101", "8153.0104"]))
    assert prox(lone) == []


def test_a_pair_sharing_two_groups_gets_one_edge_listing_both():
    reg = registry(nco_world(q1=["8153.0101", "7543.0301"], q2=["7543.0399", "8153.0103"]))
    (e,) = prox(reg)
    assert e.attributes["shared_groups"] == ["7543", "8153"]
    assert e.attributes["codes_by_qualification"] == {key(1): ["7543.0301", "8153.0101"], key(2): ["7543.0399", "8153.0103"]}


def test_only_the_codes_in_a_shared_group_are_listed():
    reg = registry(nco_world(q1=["8153.0101", "3122.3551"], q2=["8153.0103"]))
    (e,) = prox(reg)
    assert e.attributes["codes_by_qualification"] == {key(1): ["8153.0101"], key(2): ["8153.0103"]}
    assert e.evidence_ids == sorted({eid(1, 0), eid(2, 0)})


def test_nothing_to_relate_gives_no_edges():
    assert prox(registry(nco_world(q1=["8153.0101"]))) == []
    assert prox(registry(nco_world(q1=[], q2=[]))) == []
    assert prox(registry([])) == []


def test_catalogue_only_records_state_no_code_and_take_no_part():
    quals = nco_world(q1=["8153.0101"], q2=["8153.0103"]) + [
        Qualification.model_validate(catalogue_only(id="qual:TEST/Q9100", code="TEST/Q9100", slug="TEST.Q9100"))]
    reg = Registry.from_records(**{**records(quals), "qualifications": quals})
    assert pairs(prox(reg)) == {(qid(1), qid(2))}


# ---- identity, order, determinism -------------------------------------------------------------------------------------


def test_edge_identity_class_direction_and_flag(smo_ssmo):
    e = {(x.source, x.target): x for x in prox(smo_ssmo)}[(qid(1), qid(2))]
    assert e.id == f"e:NCO_GROUP_PROXIMITY:{key(1)}:{key(2)}"
    assert e.type is PROX and e.directed is False
    assert e.evidence_class is EvidenceClass.INFERENCE and e.experimental is True
    assert [f.code for f in e.flags] == [QualityFlagCode.INFERENCE_EXPERIMENTAL]
    assert e.source < e.target


def test_edges_are_sorted_by_type_source_target_and_stored_once(smo_ssmo):
    edges = prox(smo_ssmo, nco_group_digits=3)
    assert edges == sorted(edges, key=lambda e: (e.type.value, e.source, e.target))
    assert len({e.id for e in edges}) == len(edges)
    assert all((e.target, e.source) not in pairs(edges) for e in edges)


def test_repeated_calls_and_any_record_order_give_equal_results(smo_ssmo):
    first = prox(smo_ssmo)
    assert first == prox(smo_ssmo)
    quals = nco_world(q1=["8153.0101"], q2=["8153.0103"], q3=["7543.0301"], q4=["7549.0101"], q5=["8154.0101"], q6=[],
                      q7=["8153.0101", "8153.0104"])
    rng = random.Random(5)
    for _ in range(5):
        shuffled = quals[:]
        rng.shuffle(shuffled)
        recs = records(shuffled)
        for k in recs:
            rng.shuffle(recs[k])
        assert json.dumps([e.model_dump(mode="json") for e in prox(Registry.from_records(**recs))]) == \
            json.dumps([e.model_dump(mode="json") for e in first])


def test_each_call_returns_a_new_list_of_frozen_edges(smo_ssmo):
    a, b = prox(smo_ssmo), prox(smo_ssmo)
    assert a is not b
    with pytest.raises(ValidationError):
        a[0].experimental = False


# ---- provenance -------------------------------------------------------------------------------------------------------


def test_evidence_ids_are_those_of_the_stated_codes_behind_the_edge(smo_ssmo):
    by = {(x.source, x.target): x for x in prox(smo_ssmo)}
    assert by[(qid(1), qid(2))].evidence_ids == sorted({eid(1), eid(2)})
    assert by[(qid(1), qid(7))].evidence_ids == sorted({eid(1), eid(7, 0), eid(7, 1)})
    for e in by.values():
        for i in e.evidence_ids:
            assert smo_ssmo.evidence_by_id(i).evidence_class is EvidenceClass.OFFICIAL


def test_an_inference_edge_cites_the_same_evidence_as_the_aligned_to_nco_edges_it_comes_from(smo_ssmo):
    static = {(e.source, e.target): e for e in build_static_edges(smo_ssmo) if e.type is EdgeType.ALIGNED_TO_NCO}
    for e in prox(smo_ssmo):
        behind = set()
        for q, codes in e.attributes["codes_by_qualification"].items():
            for code in codes:
                behind |= set(static[(f"qual:{q}", f"nco:{code}")].evidence_ids)
        assert e.evidence_ids == sorted(behind)


# ---- disabled, enabled, static edges untouched ------------------------------------------------------------------------


def test_inference_edges_are_absent_unless_requested(smo_ssmo):
    for edges in (build_static_edges(smo_ssmo), build_static_edges(smo_ssmo, include_inference=False),
                  build_static_edges(smo_ssmo, False, nco_group_digits=3)):
        assert edges == build_static_edges(smo_ssmo)
        assert not [e for e in edges if e.experimental or e.type in INFERENCE_EDGE_TYPES]
        assert {e.type for e in edges} <= set(STATIC_EDGE_TYPES)


def test_requesting_inference_adds_exactly_the_inference_edges(smo_ssmo):
    static, both = build_static_edges(smo_ssmo), build_static_edges(smo_ssmo, include_inference=True)
    assert [e for e in both if not e.experimental] == static  # same records, same relative order
    assert [e for e in both if e.experimental] == prox(smo_ssmo)
    assert len(both) == len(static) + len(prox(smo_ssmo))
    assert both == sorted(both, key=lambda e: (e.type.value, e.source, e.target))
    assert {e.type for e in both if e.experimental} == {PROX}


def test_the_configured_level_reaches_the_combined_builder(smo_ssmo):
    both = build_static_edges(smo_ssmo, include_inference=True, nco_group_digits=3)
    assert [e for e in both if e.experimental] == prox(smo_ssmo, nco_group_digits=3)


def test_static_edges_are_byte_equal_with_and_without_inference(smo_ssmo):
    def dump(edges):
        return json.dumps([e.model_dump(mode="json") for e in edges], sort_keys=True)
    assert dump([e for e in build_static_edges(smo_ssmo, True) if not e.experimental]) == dump(build_static_edges(smo_ssmo))


def test_an_inference_edge_and_a_documented_edge_for_one_pair_stay_two_separate_records():
    """Qualifications 1 and 2 share the NOS unit and an NCO group: SHARES_NOS (RULE_DERIVED) and NCO_GROUP_PROXIMITY
    (INFERENCE) coexist; neither replaces, merges into or changes the other."""
    reg = registry(nco_world(q1=["8153.0101"], q2=["8153.0103"]))
    edges = build_static_edges(reg, include_inference=True)
    pair = [e for e in edges if {e.source, e.target} == {qid(1), qid(2)}]
    assert {e.type for e in pair} == {EdgeType.SHARES_NOS, PROX}
    by = {e.type: e for e in pair}
    assert by[EdgeType.SHARES_NOS].evidence_class is EvidenceClass.RULE_DERIVED and by[EdgeType.SHARES_NOS].experimental is False
    assert by[PROX].evidence_class is EvidenceClass.INFERENCE and by[PROX].experimental is True
    assert by[EdgeType.SHARES_NOS].id != by[PROX].id


def test_inference_edges_do_not_depend_on_documented_edges_or_nos_membership():
    with_nos = registry(nco_world(q1=["8153.0101"], q2=["8153.0103"]))
    other = [mk_qual(1, [row(2, "nos:TEST/N9001")], nco=("8153.0101",)), mk_qual(2, [row(2, "nos:TEST/N9002")], nco=("8153.0103",))]
    assert pairs(prox(with_nos)) == pairs(prox(registry(other))) == {(qid(1), qid(2))}


def test_building_never_changes_the_registry_or_any_source_record(smo_ssmo):
    before = (smo_ssmo.qualifications(), smo_ssmo.nos_units(), smo_ssmo.occupations(), smo_ssmo.conflicts())
    build_static_edges(smo_ssmo, include_inference=True, nco_group_digits=3)
    assert (smo_ssmo.qualifications(), smo_ssmo.nos_units(), smo_ssmo.occupations(), smo_ssmo.conflicts()) == before


def test_titles_hours_credits_levels_and_eligibility_do_not_change_inference_edges(smo_ssmo):
    base = prox(smo_ssmo)
    changed = []
    for q in nco_world(q1=["8153.0101"], q2=["8153.0103"], q3=["7543.0301"], q4=["7549.0101"], q5=["8154.0101"], q6=[],
                       q7=["8153.0101", "8153.0104"]):
        body = q.model_dump(mode="json")
        body.update(titles={"qf": "Another title"}, eligibility=None, min_age={**body["min_age"], "value": 99})
        body["nsqf_level"] = {**body["nsqf_level"], "value": 9.0, "engine_use": None}
        body["hours"]["total"] = {**body["hours"]["total"], "value": 1.0}
        body["credits"] = {**body["credits"], "value": 99.0}
        changed.append(Qualification.model_validate(body))
    assert prox(Registry.from_records(**records(changed))) == base


# ---- invalid input follows D-19: reported, never repaired -------------------------------------------------------------


def test_a_null_stated_code_is_an_error():
    q = mk_qual(1, [row(2, "nos:TEST/N9001")])
    q = q.model_copy(update={"nco_codes": [OfficialValued[str].model_validate(official(None, 1))]})
    with pytest.raises(EdgeBuildError) as exc:
        prox(registry([q]))
    assert any("null" in p for p in exc.value.problems)


def test_a_code_stated_twice_by_one_qualification_is_an_error():
    q = mk_qual(1, [row(2, "nos:TEST/N9001")], nco=("8153.0101", "8153.0101"))
    with pytest.raises(EdgeBuildError, match="more than once"):
        prox(registry([q]))


def test_a_code_without_an_occupation_record_is_an_error():
    quals = nco_world(q1=["8153.0101"], q2=["8153.0103"])
    recs = records(quals)
    recs["occupations"] = [o for o in recs["occupations"] if o.nco_code != "8153.0103"]
    with pytest.raises(EdgeBuildError) as exc:
        prox(Registry.from_records(**recs))
    assert any("unknown occupation nco:8153.0103" in p for p in exc.value.problems)


def test_an_unresolved_evidence_id_is_an_error():
    quals = nco_world(q1=["8153.0101"], q2=["8153.0103"])
    with pytest.raises(EdgeBuildError) as exc:
        prox(Registry.from_records(**records(quals, evidence=[e for e in EVIDENCE if e.id != eid(2)])))
    assert any(eid(2) in p for p in exc.value.problems)


def test_a_stated_code_without_an_evidence_id_is_an_error():
    q = mk_qual(1, [row(2, "nos:TEST/N9001")])
    code = q.nco_codes[0]
    q = q.model_copy(update={"nco_codes": [code.model_copy(update={"evidence_id": None})]})
    with pytest.raises(EdgeBuildError, match="no evidence id"):
        prox(registry([q]))


def test_every_problem_is_listed_and_no_partial_result_is_returned():
    bad = mk_qual(1, [row(2, "nos:TEST/N9001")], nco=("8153.0101", "8153.0101"))
    bad2 = mk_qual(2, [row(2, "nos:TEST/N9001")]).model_copy(update={"nco_codes": [OfficialValued[str].model_validate(official(None, 3))]})
    good = [mk_qual(3, [row(2, "nos:TEST/N9001")], nco=("8153.0102",)), mk_qual(4, [row(2, "nos:TEST/N9001")], nco=("8153.0103",))]
    with pytest.raises(EdgeBuildError) as exc:
        prox(registry([bad, bad2, *good]))
    assert len(exc.value.problems) == 2


def test_the_combined_builder_reports_static_problems_first_and_returns_nothing():
    q = mk_qual(1, [row(2, "nos:TEST/N9001")], nco=("8153.0101", "8153.0101"))
    with pytest.raises(EdgeBuildError):
        build_static_edges(registry([q]), include_inference=True)


@pytest.mark.parametrize("bad", [0, 1, 2, 5, 8, -4, True, False, 4.0, "4", None])
def test_only_3_or_4_digits_are_accepted(smo_ssmo, bad):
    with pytest.raises(ValueError, match="nco_group_digits"):
        prox(smo_ssmo, nco_group_digits=bad)
    with pytest.raises(ValueError, match="nco_group_digits"):
        build_static_edges(smo_ssmo, include_inference=True, nco_group_digits=bad)


# ---- the GraphEdge contract of the new type ---------------------------------------------------------------------------


def good_prox() -> dict:
    (e,) = prox(registry(nco_world(q1=["8153.0101"], q2=["8153.0103"])))
    return e.model_dump(mode="json")


def test_a_well_formed_inference_edge_validates():
    GraphEdge.model_validate(good_prox())


@pytest.mark.parametrize("change", [
    {"directed": True},
    {"evidence_class": "RULE_DERIVED", "experimental": False},
    {"evidence_class": "OFFICIAL", "experimental": False},
    {"evidence_class": "INFERENCE", "experimental": False},
    {"evidence_class": "RULE_DERIVED", "experimental": True},
    {"flags": []},
    {"evidence_ids": []},
    {"source": qid(2), "target": qid(1), "id": f"e:NCO_GROUP_PROXIMITY:{key(2)}:{key(1)}"},
    {"target": "nco:8153.0103", "id": f"e:NCO_GROUP_PROXIMITY:{key(1)}:8153.0103"},
    {"id": "e:NCO_GROUP_PROXIMITY:TEST/Q9001:TEST/Q9003"},
])
def test_an_inference_edge_that_breaks_its_contract_is_refused(change):
    with pytest.raises(ValidationError):
        GraphEdge.model_validate({**good_prox(), **change})


@pytest.mark.parametrize("attributes", [
    {},
    {"group_digits": 4, "shared_groups": ["8153"]},
    {"group_digits": 4, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.0103"]}, "score": 0.9},
    {"group_digits": 5, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.0103"]}},
    {"group_digits": True, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.0103"]}},
    {"group_digits": 3, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.0103"]}},
    {"group_digits": 4, "shared_groups": [], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.0103"]}},
    {"group_digits": 4, "shared_groups": ["8153", "7543"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.0103"]}},
    {"group_digits": 4, "shared_groups": ["81x3"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.0103"]}},
    {"group_digits": 4, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"]}},
    {"group_digits": 4, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"], key(3): ["8153.0103"]}},
    {"group_digits": 4, "shared_groups": ["8153"], "codes_by_qualification": {key(1): [], key(2): ["8153.0103"]}},
    {"group_digits": 4, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["7543.0301"]}},
    {"group_digits": 4, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0101"], key(2): ["8153.01"]}},
    {"group_digits": 4, "shared_groups": ["8153"], "codes_by_qualification": {key(1): ["8153.0103", "8153.0101"], key(2): ["8153.0103"]}},
])
def test_an_inference_edge_with_wrong_attributes_is_refused(attributes):
    with pytest.raises(ValidationError):
        GraphEdge.model_validate({**good_prox(), "attributes": attributes})


def test_no_confidence_score_or_weight_attribute_exists(smo_ssmo):
    """The contract names no confidence semantics (TASKS P3.5, ARCHITECTURE §13.4), so none is stored."""
    for e in prox(smo_ssmo, nco_group_digits=3):
        assert set(e.attributes) == {"group_digits", "shared_groups", "codes_by_qualification"}


def test_title_similarity_is_not_built_and_its_contract_is_not_defined(smo_ssmo):
    assert INFERENCE_EDGE_TYPES == (PROX,)
    assert EdgeType.TITLE_SIMILARITY not in {e.type for e in build_static_edges(smo_ssmo, include_inference=True)}
    assert [x.edge_type for x in inference_legend()] == [PROX]


# ---- legend -----------------------------------------------------------------------------------------------------------


def test_the_inference_legend_says_what_it_does_not_mean():
    (entry,) = inference_legend()
    assert entry.edge_type is PROX and entry.evidence_class is EvidenceClass.INFERENCE
    assert entry.meaning.startswith("Experimental inference")
    for phrase in ("share skills", "equivalent", "eligible", "people move", "jobs exist"):
        assert phrase in entry.does_not_mean


def test_no_legend_text_promises_eligibility_employability_or_demand():
    forbidden = ("guarantee", "will get", "eligible for job", "in demand", "declining")
    for e in inference_legend():
        assert not [w for w in forbidden if w in (e.meaning + " " + e.does_not_mean).lower()]
        assert " eligible" not in e.meaning.lower() and "employab" not in e.meaning.lower()


def test_the_static_legend_is_unchanged_by_p3_5():
    assert [x.edge_type for x in static_legend()] == list(STATIC_EDGE_TYPES)


def test_the_inference_legend_wording_is_pinned_so_that_a_change_is_deliberate():
    (entry,) = inference_legend()
    assert entry.meaning == ("Experimental inference: the official documents of both qualifications state NCO-2015 occupation "
                             "codes that begin with the same digits (4 digits = unit group, 3 digits = minor group).")
    assert entry.does_not_mean == ("That the qualifications share skills, are equivalent or interchangeable, that anyone is "
                                   "eligible for one after the other, that people move between these roles, or that jobs "
                                   "exist in the occupation.")


# ---- module boundaries ------------------------------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            found |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            found.add(("skillgraph.graph" if n.level == 1 else n.module or "") + (("." + n.module) if n.level == 1 and n.module else ""))
    return found


@pytest.mark.parametrize("name", ["inference.py", "claim_candidates.py"])
def test_the_new_modules_import_only_model_registry_graph_and_the_standard_library(name):
    forbidden = ("skillgraph.eligibility", "skillgraph.labour", "skillgraph.api", "skillgraph.curation", "anthropic", "openai",
                 "requests", "httpx", "urllib", "socket", "random", "numpy", "sklearn", "torch")
    imported = _imports(SRC / "graph" / name)
    assert not [m for m in imported if m.startswith(forbidden)], imported
    internal = {m for m in imported if m.startswith("skillgraph")}
    assert all(m == "skillgraph.registry" or m.startswith(("skillgraph.model", "skillgraph.graph")) for m in internal), internal


def test_the_eligibility_modules_do_not_import_the_graph():
    for path in (SRC / "eligibility").glob("*.py"):
        assert not [m for m in _imports(path) if m.startswith("skillgraph.graph")], path.name


def test_the_inference_module_reads_only_codes_prefixes_and_evidence_ids():
    attrs = {n.attr for n in ast.walk(ast.parse((SRC / "graph" / "inference.py").read_text(encoding="utf-8")))
             if isinstance(n, ast.Attribute)}
    assert not attrs & {"eligibility", "min_age", "titles", "hours", "credits", "nsqf_level", "progression_claims",
                        "resolved_target", "awarding_body", "sector", "coverage", "nos_memberships", "text_verbatim"}


# ---- claim-title candidates (unreviewed inference; not edges) ---------------------------------------------------------


def cq(n: int, catalogue: str | None, *, claims=(), label="Vertical", curated_=False) -> Qualification:
    """A record with catalogue title ``catalogue`` and claims ``claims`` (text only, each with ``label``)."""
    code = f"TEST/Q91{n:02d}"
    if curated_:
        body = curated(id=f"qual:{code}", code=code, slug=slug_of(f"qual:{code}"), nos_memberships=[], modules=[], eligibility=None,
                       titles={"qf": f"QF title {n}", **({"catalogue": catalogue} if catalogue else {})},
                       progression_claims=[{"id": f"claim:{code}/P{i}", "qualification_id": f"qual:{code}", "text_verbatim": t,
                                            "direction_label": label, "resolved_target": None, "evidence_id": f"ev:{900 + 10 * n + i:016x}"}
                                           for i, t in enumerate(claims, start=1)])
    else:
        body = catalogue_only(id=f"qual:{code}", code=code, slug=slug_of(f"qual:{code}"), titles={"catalogue": catalogue})
    return Qualification.model_validate(body)


def cand_registry(*quals) -> Registry:
    return Registry.from_records(**records(list(quals)))


def test_normalisation_follows_d21():
    assert normalise_name("Sampling Coordinator(Vertical)", "Vertical") == "sampling coordinator"
    assert normalise_name("Sampling  Coordinator ( vertical )", "Vertical") == "sampling coordinator"
    assert normalise_name("QC Executive – Sewing Line") == normalise_name("QC Executive - Sewing Line") == "qc executive sewing line"
    assert normalise_name("QC Executive-Sewing Line") == "qc executive sewing line"
    assert normalise_name("Pressman-Stitched Items") == normalise_name("pressman — stitched   items")
    assert normalise_name("Café Ａ") == normalise_name("CAFÉ a")  # NFKC then case folding
    assert normalise_name("") == normalise_name(" - ()") == ""


def test_normalisation_removes_only_the_claims_own_trailing_label():
    assert normalise_name("Sampling Coordinator (Horizontal)", "Vertical") == "sampling coordinator horizontal"
    assert normalise_name("Sampling (Vertical) Coordinator", "Vertical") == "sampling vertical coordinator"
    assert normalise_name("Sampling Coordinator(Vertical)") == "sampling coordinator vertical"  # no label given: nothing removed


def test_normalisation_is_exact_not_fuzzy():
    assert normalise_name("Sewing Machine Operator") != normalise_name("Sewing Machine Operators")
    assert normalise_name("QC Executive - Sewing Line") != normalise_name("QC Executive - Stitched Items")
    assert normalise_name("Operator Sewing Machine") != normalise_name("Sewing Machine Operator")
    assert normalise_name("AB") != normalise_name("A-B")


def test_the_two_contract_examples():
    """TASKS P3.5: "Sampling Coordinator" matches the catalogue entry; "QC Executive - Sewing Line" has no exact match."""
    reg = cand_registry(
        cq(1, "Specialised source", claims=["Sampling Coordinator(Vertical)", "QC Executive – Sewing Line (Vertical)"], curated_=True),
        cq(2, "Sampling Coordinator"), cq(3, "QC Executive - Stitched Items"))
    report = claim_title_candidates(reg)
    assert [(c.claim_id, c.candidate_qualification_id) for c in report.candidates] == [("claim:TEST/Q9101/P1", "qual:TEST/Q9102")]
    assert report.unmatched_claim_ids == ["claim:TEST/Q9101/P2"]


def test_a_candidate_is_marked_inference_unreviewed_display_only_and_carries_the_claim_evidence():
    reg = cand_registry(cq(1, None, claims=["Fabric Cutter(Vertical)"], curated_=True), cq(2, "Fabric Cutter"))
    (c,) = claim_title_candidates(reg).candidates
    assert c.evidence_class is EvidenceClass.INFERENCE and c.status == "UNREVIEWED_CANDIDATE"
    assert c.engine_use.value == "DISPLAY_ONLY" and c.candidate_count == 1 and c.target_is_source is False
    assert c.claim_text == "Fabric Cutter(Vertical)" and c.candidate_title == "Fabric Cutter" and c.normalised_name == "fabric cutter"
    assert c.evidence_ids == [f"ev:{900 + 10 * 1 + 1:016x}"]
    reg.evidence_by_id(c.evidence_ids[0])


def test_an_ambiguous_name_gives_every_candidate_and_prefers_none():
    reg = cand_registry(cq(1, None, claims=["Pattern Master(Vertical)"], curated_=True), cq(2, "Pattern Master"),
                        cq(3, "pattern  master"), cq(4, "Pattern Master Apparel"))
    cands = claim_title_candidates(reg).candidates
    assert [c.candidate_qualification_id for c in cands] == ["qual:TEST/Q9102", "qual:TEST/Q9103"]
    assert all(c.candidate_count == 2 for c in cands)


def test_a_claim_equal_to_its_own_qualifications_title_is_kept_and_marked():
    reg = cand_registry(cq(1, "Pressman", claims=["Pressman(Horizontal)"], label="Horizontal", curated_=True))
    (c,) = claim_title_candidates(reg).candidates
    assert c.target_is_source is True and c.candidate_qualification_id == c.source_qualification_id


def test_a_record_without_a_catalogue_title_cannot_match():
    reg = cand_registry(cq(1, None, claims=["QF title 1(Vertical)"], curated_=True))
    report = claim_title_candidates(reg)
    assert report.candidates == [] and report.unmatched_claim_ids == ["claim:TEST/Q9101/P1"]


def test_an_empty_normalised_claim_matches_nothing():
    reg = cand_registry(cq(1, None, claims=["(Vertical)", " - "], curated_=True), cq(2, "-"))
    report = claim_title_candidates(reg)
    assert report.candidates == [] and len(report.unmatched_claim_ids) == 2


def test_candidates_are_sorted_deterministic_and_independent_of_record_order():
    quals = [cq(1, None, claims=["Fabric Cutter(Vertical)", "Fashion Designer(Vertical)"], curated_=True),
             cq(2, "Fashion Designer"), cq(3, "Fabric Cutter"), cq(4, "Fabric Cutter.")]
    first = claim_title_candidates(cand_registry(*quals))
    assert first == claim_title_candidates(cand_registry(*quals))
    assert [(c.claim_id, c.candidate_qualification_id) for c in first.candidates] == sorted(
        (c.claim_id, c.candidate_qualification_id) for c in first.candidates)
    assert claim_title_candidates(cand_registry(*reversed(quals))) == first


def test_candidates_create_no_edge_set_no_resolved_target_and_change_nothing():
    reg = cand_registry(cq(1, None, claims=["Fabric Cutter(Vertical)"], curated_=True), cq(2, "Fabric Cutter"))
    before = (reg.qualifications(), reg.occupations())
    static = build_static_edges(reg)
    claim_title_candidates(reg)
    assert (reg.qualifications(), reg.occupations()) == before
    assert all(c.resolved_target is None for q in reg.qualifications() for c in q.progression_claims)
    assert build_static_edges(reg) == static == build_static_edges(reg, include_inference=True)  # no occupation, no NCO edge
    assert not [e for e in build_static_edges(reg, include_inference=True)
                if e.type is EdgeType.PROGRESSION_CLAIM and e.target.startswith("qual:")]


def test_a_progression_claim_edge_still_ends_at_the_claim_text_when_inference_is_requested():
    reg = cand_registry(cq(1, None, claims=["Fabric Cutter(Vertical)"], curated_=True), cq(2, "Fabric Cutter"))
    edges = [e for e in build_static_edges(reg, include_inference=True) if e.type is EdgeType.PROGRESSION_CLAIM]
    assert [e.target for e in edges] == ["claim:TEST/Q9101/P1"]
    with pytest.raises(ValidationError):  # the model still refuses a qualification target (TASKS P3.4, criterion 5)
        GraphEdge.model_validate({**edges[0].model_dump(mode="json"), "target": "qual:TEST/Q9102",
                                  "id": "e:PROGRESSION_CLAIM:TEST/Q9101:TEST/Q9102"})


def test_a_candidate_model_refuses_a_non_inference_class():
    reg = cand_registry(cq(1, None, claims=["Fabric Cutter(Vertical)"], curated_=True), cq(2, "Fabric Cutter"))
    (c,) = claim_title_candidates(reg).candidates
    with pytest.raises(ValidationError):
        ClaimTitleCandidate.model_validate({**c.model_dump(mode="json"), "evidence_class": "OFFICIAL"})
    with pytest.raises(ValidationError):
        ClaimTitleCandidate.model_validate({**c.model_dump(mode="json"), "status": "REVIEWED"})
    with pytest.raises(ValidationError):
        ClaimTitleCandidate.model_validate({**c.model_dump(mode="json"), "engine_use": "SAFE_HARD_RULE"})


def test_the_review_section_states_that_nothing_is_a_decision_and_lists_unmatched_claims():
    reg = cand_registry(cq(1, None, claims=["Fabric Cutter(Vertical)", "Nobody(Vertical)"], curated_=True), cq(2, "Fabric Cutter"))
    text = render_review_section(claim_title_candidates(reg))
    assert "Nothing here is a decision or an official link" in text
    assert "`claim:TEST/Q9101/P1` | Fabric Cutter(Vertical) | `qual:TEST/Q9102` | Fabric Cutter | 1 |" in text
    assert "No exact match: `claim:TEST/Q9101/P2`." in text
    assert text == render_review_section(claim_title_candidates(reg))
    assert render_review_section(claim_title_candidates(cand_registry())).endswith("No exact match: none.\n")


def test_the_candidate_module_neither_writes_files_nor_builds_edges():
    src = (SRC / "graph" / "claim_candidates.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"open", "write_text", "write_bytes", "GraphEdge", "build_static_edges", "resolved_target", "ResolvedTarget"}
