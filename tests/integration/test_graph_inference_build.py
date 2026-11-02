"""P3.5 inference edges over builds produced by the real builder from the synthetic input tree (always runs).

Nothing here writes into ``data/`` or touches ``config/``; the builder output lives in pytest temporary directories.
"""

from itertools import combinations
from pathlib import Path

import pytest
from synth_tree import Tree

from skillgraph.graph import EdgeType, build_inference_edges, build_static_edges, claim_title_candidates
from skillgraph.model.evidence import EvidenceClass
from skillgraph.registry import load


@pytest.fixture(scope="module")
def synthetic_build(tmp_path_factory) -> Path:
    return Tree(tmp_path_factory.mktemp("graph_inference_synth")).build(approve=[]).path


def groups_of(reg, digits):
    """Independent of the builder: the code prefixes each qualification states, read from the stated codes themselves."""
    return {q.id: {c.value.split(".")[0][:digits] for c in q.nco_codes} for q in reg.qualifications()}


@pytest.mark.parametrize("digits", [4, 3])
def test_inference_edges_of_a_builder_made_build_follow_its_stated_codes(synthetic_build, digits):
    reg = load(synthetic_build)
    expected = {(a, b) for (a, ga), (b, gb) in combinations(sorted(groups_of(reg, digits).items()), 2) if ga & gb}
    edges = build_inference_edges(reg, nco_group_digits=digits)
    assert {(e.source, e.target) for e in edges} == expected
    for e in edges:
        assert e.type is EdgeType.NCO_GROUP_PROXIMITY and e.evidence_class is EvidenceClass.INFERENCE and e.experimental
        for eid in e.evidence_ids:
            assert reg.evidence_by_id(eid).evidence_class is EvidenceClass.OFFICIAL


def test_static_edges_of_a_builder_made_build_are_unchanged_by_inference(synthetic_build):
    reg = load(synthetic_build)
    both = build_static_edges(reg, include_inference=True)
    assert [e for e in both if not e.experimental] == build_static_edges(reg)
    assert [e for e in both if e.experimental] == build_inference_edges(reg)
    assert build_static_edges(load(synthetic_build), include_inference=True) == both  # a second load: equal


def test_claim_candidates_of_a_builder_made_build_are_unreviewed_and_set_no_target(synthetic_build):
    reg = load(synthetic_build)
    report = claim_title_candidates(reg)
    total = sum(len(q.progression_claims) for q in reg.qualifications())
    assert len({c.claim_id for c in report.candidates}) + len(report.unmatched_claim_ids) == total
    assert all(c.status == "UNREVIEWED_CANDIDATE" for c in report.candidates)
    assert all(c.resolved_target is None for q in reg.qualifications() for c in q.progression_claims)
