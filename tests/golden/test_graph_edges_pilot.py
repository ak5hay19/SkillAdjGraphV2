"""P3.4 golden cases: static edges of the four curated pilots, on the real local build (TASKS P3.4 acceptance criteria).

The expectations come from the audit and the architecture, not from the builder's output: ARCHITECTURE §8.5 (OBS-01: the
exact shared NOS codes, all Non-Core, the Sewing Machine Operator shares none), §8.6 (DQ-02 / OV-040 on DGT/VSQ/N0102 in
SSMO), §10.3 (edge types) and TASKS P3.4. Two groups of values are *observations of the current build* and are labelled so:
the printed-version agreement and the counts of rows/claims (read independently from the registry, not hard-coded).
Skipped, not failed, when ``data/`` or an installed build of the current curation code is absent.
"""

import itertools
import json

import pytest

from skillgraph.graph import EdgeType, build_static_edges, static_legend
from skillgraph.model.qualification import Coverage
from skillgraph.registry import load

SMO, SSMO, IC, PS = "qual:AMH/Q0301", "qual:AMH/Q2301", "qual:AMH/Q0103", "qual:AMH/Q2101"
N0309, N0102 = "AMH/N0309", "DGT/VSQ/N0102"


@pytest.fixture(scope="module")
def registry(build_dir):
    reg = load(build_dir)
    assert reg.build is not None and reg.build.validation == "PASSED"  # the P3.3 convention: golden on a validated build
    return reg


@pytest.fixture(scope="module")
def edges(registry):
    return build_static_edges(registry)


def evidence_of(registry, edges):
    """The evidence records that the edges cite (each once)."""
    return [registry.evidence_by_id(i) for i in sorted({i for e in edges for i in e.evidence_ids})]


def of_type(edges, t):
    return [e for e in edges if e.type is t]


def shares(edges):
    return {(e.source, e.target): e for e in of_type(edges, EdgeType.SHARES_NOS)}


# ---- OBS-01 -----------------------------------------------------------------------------------------------------------


def test_obs01_shares_nos_exists_exactly_for_the_three_documented_pairs(edges):
    got = {k: v.attributes["shared_codes"] for k, v in shares(edges).items()}
    assert got == {
        tuple(sorted((SSMO, IC))): sorted([N0309, N0102]),
        tuple(sorted((IC, PS))): [N0102],
        tuple(sorted((SSMO, PS))): [N0102],
    }


def test_the_sewing_machine_operator_has_no_shares_nos_edge(edges):
    assert not [e for e in of_type(edges, EdgeType.SHARES_NOS) if SMO in (e.source, e.target)]


def test_all_shared_units_are_non_core(edges):
    for e in of_type(edges, EdgeType.SHARES_NOS):
        a = e.attributes
        assert a["core_shared_count"] == 0 and a["mixed_core_codes"] == []
        assert a["noncore_shared_count"] == len(a["shared_codes"])


def test_the_shared_units_are_non_core_in_the_registry_itself_not_only_in_the_edges(registry):
    """An independent read of the NOS tables, so the edge attribute cannot agree with itself by construction."""
    shared = {n.id for n in registry.nos_units() if len(registry.qualification_ids_with_nos(n.id)) > 1}
    assert shared == {f"nos:{N0309}", f"nos:{N0102}"}
    for nid in shared:
        for q in registry.qualifications_with_nos(nid):
            assert {m.core_or_noncore.value for m in q.nos_memberships if m.nos_id == nid} == {"Non-Core"}


def test_ov040_is_flagged_where_the_ssmo_membership_of_n0102_is_involved(edges):
    got = shares(edges)
    ssmo_edges = [e for k, e in got.items() if SSMO in k]
    assert len(ssmo_edges) == 2 and all(N0102 in e.attributes["shared_codes"] for e in ssmo_edges)
    for e in ssmo_edges:
        assert [f.refs for f in e.flags] == [["conflict:OV-040"]]
        assert (e.flags[0].code.value, e.flags[0].severity.value) == ("SOURCE_CONFLICT", "INFO")
    (ic_ps,) = [e for k, e in got.items() if SSMO not in k]
    assert ic_ps.flags == []  # neither membership of N0102 in IC or PS is conflicted


def test_ov040_is_on_the_ssmo_includes_edge_of_n0102_and_no_other_n0102_edge(edges):
    flagged = {e.id: [f.refs for f in e.flags] for e in of_type(edges, EdgeType.INCLUDES_NOS) if "N0102" in e.target and e.flags}
    assert flagged == {f"e:INCLUDES_NOS:AMH/Q2301:{N0102}": [["conflict:OV-040"]]}


def test_conflict_flags_match_the_membership_conflicts_registered_in_the_build(registry, edges):
    """Every flag refers to a registered conflict and to a membership value that carries it (no invented flag)."""
    registered = {c.id for c in registry.conflicts()}
    carried = set()
    for q in registry.qualifications():
        for m in q.nos_memberships:
            for cell in (m.nsqf_level, m.credits, m.hours.total, m.version):
                if cell is not None and cell.conflict_id:
                    carried.add(cell.conflict_id)
    seen = {f.refs[0] for e in edges for f in e.flags}
    assert seen == carried and seen <= registered
    assert not any(f for e in of_type(edges, EdgeType.PROGRESSION_CLAIM) + of_type(edges, EdgeType.ALIGNED_TO_NCO) for f in e.flags)


def test_printed_version_agreement_is_reported_per_code(edges):
    """Observation of build cb-601c0399c999 (not an audit expectation): N0309 prints 1.0 in IC and SSMO; N0102 prints 1.0
    in IC and PS but nothing in SSMO."""
    got = shares(edges)
    assert got[tuple(sorted((SSMO, IC)))].attributes["version_agreement"] == {N0102: "NOT_STATED", N0309: "SAME"}
    assert got[tuple(sorted((IC, PS)))].attributes["version_agreement"] == {N0102: "SAME"}
    assert got[tuple(sorted((SSMO, PS)))].attributes["version_agreement"] == {N0102: "NOT_STATED"}


# ---- the other edge types ---------------------------------------------------------------------------------------------


def test_includes_nos_has_one_edge_per_nos_table_row_of_each_curated_qualification(registry, edges):
    expected = {(q.id, m.nos_id or m.module_id) for q in registry.qualifications() for m in q.nos_memberships}
    got = {(e.source, e.target) for e in of_type(edges, EdgeType.INCLUDES_NOS)}
    assert got == expected and len(of_type(edges, EdgeType.INCLUDES_NOS)) == len(expected) > 0
    assert {q.id for q in registry.qualifications() if q.coverage is Coverage.CATALOGUE_ONLY}.isdisjoint({s for s, _ in got})
    bridges = [e for e in of_type(edges, EdgeType.INCLUDES_NOS) if e.target.startswith("mod:")]
    assert {e.source for e in bridges} == {SMO, SSMO} and all(e.attributes["is_bridge"] for e in bridges)


def test_progression_claim_edges_end_at_claim_nodes_and_never_at_a_qualification(registry, edges):
    claims = {c.id: q.id for q in registry.qualifications() for c in q.progression_claims}
    got = of_type(edges, EdgeType.PROGRESSION_CLAIM)
    assert {(e.source, e.target) for e in got} == {(q, c) for c, q in claims.items()} and len(claims) == len(got) > 0
    assert all(e.target.startswith("claim:") for e in got)
    assert not [e for e in edges if e.type is not EdgeType.SHARES_NOS and e.target.startswith("qual:")]
    assert all(e.evidence_class.value == "OFFICIAL" and not e.experimental for e in got)


def test_the_smo_to_ssmo_claim_is_a_claim_edge_not_a_qualification_edge(registry, edges):
    """The SMO claim text 'Specialized Sewing Machine Operator(Vertical)' becomes a claim node; linking it to SSMO is P3.5."""
    smo = registry.qualification_by_id(SMO)
    (claim,) = [c for c in smo.progression_claims if "Specialized Sewing Machine Operator" in c.text_verbatim]
    (e,) = [e for e in of_type(edges, EdgeType.PROGRESSION_CLAIM) if e.target == claim.id]
    assert e.source == SMO and e.evidence_ids == [claim.evidence_id] and e.attributes == {"direction_label": "Vertical"}
    assert not any(x.source == SMO and x.target == SSMO for x in edges)


def test_aligned_to_nco_edges_are_the_stated_codes_of_the_pilots_only(registry, edges):
    got = {(e.source, e.target) for e in of_type(edges, EdgeType.ALIGNED_TO_NCO)}
    assert got == {(SMO, "nco:8153.0101"), (SSMO, "nco:8153.0103"), (IC, "nco:7543.0301"), (PS, "nco:3122.3551")}
    for e in of_type(edges, EdgeType.ALIGNED_TO_NCO):
        assert registry.occupation_by_id(e.target) and e.evidence_class.value == "OFFICIAL"


def test_no_edge_joins_two_qualifications_except_a_shares_nos_edge(edges):
    assert all(e.type is EdgeType.SHARES_NOS for e in edges if e.source.startswith("qual:") and e.target.startswith("qual:"))


def test_only_the_four_static_types_exist_and_none_is_experimental(edges):
    assert {e.type for e in edges} == {EdgeType.INCLUDES_NOS, EdgeType.SHARES_NOS, EdgeType.PROGRESSION_CLAIM, EdgeType.ALIGNED_TO_NCO}
    assert not any(e.experimental for e in edges)
    assert {e.edge_type for e in static_legend()} == {e.type for e in edges}


# ---- provenance, identity, determinism --------------------------------------------------------------------------------


def test_every_endpoint_and_every_evidence_id_resolves_in_the_registry(registry, edges):
    for e in edges:
        for end in (e.source, e.target):
            kind = end.split(":", 1)[0]
            {"qual": registry.qualification_by_id, "nos": registry.nos_by_id, "nco": registry.occupation_by_id}.get(
                kind, lambda x: x)(end)
        assert e.evidence_ids
        for eid in e.evidence_ids:
            registry.evidence_by_id(eid)
    modules = {m.id for q in registry.qualifications() for m in q.modules}
    claims = {c.id for q in registry.qualifications() for c in q.progression_claims}
    for e in edges:
        if e.target.startswith("mod:"):
            assert e.target in modules
        if e.target.startswith("claim:"):
            assert e.target in claims


def test_shares_evidence_is_exactly_the_union_of_the_cells_of_the_shared_rows(registry, edges):
    for (a, b), e in shares(edges).items():
        expected = set()
        for q in (registry.qualification_by_id(a), registry.qualification_by_id(b)):
            for m in q.nos_memberships:
                if m.nos_id and f"{m.nos_id[4:]}" in e.attributes["shared_codes"]:
                    cells = [m.nsqf_level, m.credits, m.version, m.hours.theory, m.hours.practical, m.hours.ojt_mandatory,
                             m.hours.ojt_recommended, m.hours.total]
                    expected |= {c.evidence_id for c in cells if c is not None}
        assert e.evidence_ids == sorted(expected)


def test_edge_ids_are_unique_and_in_the_documented_order(edges):
    assert len({e.id for e in edges}) == len(edges)
    keys = [(e.type.value, e.source, e.target) for e in edges]
    assert keys == sorted(keys)


def test_two_independent_loads_give_identical_serialised_edges(build_dir):
    runs = [json.dumps([e.model_dump(mode="json") for e in build_static_edges(load(build_dir))], sort_keys=True) for _ in range(2)]
    assert runs[0] == runs[1]


def test_counts_of_the_current_build(registry, edges):
    """Observation of the current build: 4 curated qualifications, 27 NOS-table rows, 6 claims, 4 stated NCO codes."""
    counts = {t: len(of_type(edges, t)) for t in EdgeType if of_type(edges, t)}
    assert counts == {EdgeType.INCLUDES_NOS: 27, EdgeType.SHARES_NOS: 3, EdgeType.PROGRESSION_CLAIM: 6, EdgeType.ALIGNED_TO_NCO: 4}


# ---- independence -----------------------------------------------------------------------------------------------------


def test_edges_are_unchanged_when_every_credit_value_is_mutated(registry, edges):
    """TASKS P3.3 criterion 7 applied to edges: credits are not an input (decision D1)."""
    def bump(q):
        return q.model_copy(update={
            "credits": q.credits.model_copy(update={"value": 999.0}),
            "nos_memberships": [m.model_copy(update={"credits": m.credits.model_copy(update={"value": 999.0})})
                                for m in q.nos_memberships],
        })
    from skillgraph.registry import Registry
    mutated = Registry.from_records(
        qualifications=[bump(q) for q in registry.qualifications()], nos_units=registry.nos_units(),
        occupations=registry.occupations(), sources=registry.sources(), evidence=evidence_of(registry, edges),
        conflicts=registry.conflicts(), eligibility_source_rows=list(itertools.chain.from_iterable(
            registry.eligibility_source_rows(q.id) for q in registry.qualifications())))
    assert build_static_edges(mutated) == edges


def test_edges_are_unchanged_when_the_structured_eligibility_rules_are_removed(registry, edges):
    from skillgraph.registry import Registry
    stripped = Registry.from_records(
        qualifications=[q.model_copy(update={"eligibility": None}) for q in registry.qualifications()],
        nos_units=registry.nos_units(), occupations=registry.occupations(),
        evidence=evidence_of(registry, edges), conflicts=registry.conflicts())
    assert build_static_edges(stripped) == edges
