"""P3.4 static edges over builds produced by the real builder from the synthetic input tree (always runs), and the refusal
path: a missing or damaged build never reaches the edge builder because ``registry.load`` raises first.

Nothing here writes into ``data/`` or touches ``config/``; the damaged copies live in pytest temporary directories.
"""

import shutil
from pathlib import Path

import pytest
from synth_tree import Tree

from skillgraph.curation.build import MANIFEST_OUT
from skillgraph.graph import EdgeType, build_static_edges
from skillgraph.registry import BuildInvalidError, BuildNotFoundError, load


@pytest.fixture(scope="module")
def synthetic_build(tmp_path_factory) -> Path:
    return Tree(tmp_path_factory.mktemp("graph_synth")).build(approve=[]).path


def test_edges_of_a_builder_made_build_follow_its_records(synthetic_build):
    reg = load(synthetic_build)
    edges = build_static_edges(reg)
    includes = {(e.source, e.target) for e in edges if e.type is EdgeType.INCLUDES_NOS}
    assert includes == {(q.id, m.nos_id or m.module_id) for q in reg.qualifications() for m in q.nos_memberships}
    nco = {(e.source, e.target) for e in edges if e.type is EdgeType.ALIGNED_TO_NCO}
    assert nco == {(q.id, f"nco:{c.value}") for q in reg.qualifications() for c in q.nco_codes}
    claims = {(e.source, e.target) for e in edges if e.type is EdgeType.PROGRESSION_CLAIM}
    assert claims == {(q.id, c.id) for q in reg.qualifications() for c in q.progression_claims}
    assert not [e for e in edges if e.type is EdgeType.SHARES_NOS]  # the synthetic tree shares no NOS unit
    for e in edges:
        for eid in e.evidence_ids:
            reg.evidence_by_id(eid)


def test_two_loads_of_one_build_give_equal_edges(synthetic_build):
    assert build_static_edges(load(synthetic_build)) == build_static_edges(load(synthetic_build))


def test_a_missing_build_never_yields_edges(tmp_path):
    with pytest.raises(BuildNotFoundError) as exc:
        build_static_edges(load(tmp_path / "cb-000000000000"))
    assert exc.value.build_status == "NOT_BUILT"


def test_a_damaged_build_never_yields_edges(synthetic_build, tmp_path):
    copy = tmp_path / synthetic_build.name
    shutil.copytree(synthetic_build, copy)
    victim = copy / "qualifications.json"
    victim.write_bytes(victim.read_bytes() + b" ")  # a one-byte change breaks the manifest hash
    with pytest.raises(BuildInvalidError) as exc:
        build_static_edges(load(copy))
    assert exc.value.build_status == "INVALID"


def test_a_directory_without_a_manifest_is_not_a_build(synthetic_build, tmp_path):
    copy = tmp_path / synthetic_build.name
    shutil.copytree(synthetic_build, copy)
    (copy / MANIFEST_OUT).unlink()
    with pytest.raises(BuildNotFoundError):
        build_static_edges(load(copy))
