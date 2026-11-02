"""P3.4 static graph edges (ARCHITECTURE §10.3; API_SPEC E08; TASKS P3.4). Synthetic fixtures only: TEST/... codes, registries
assembled with ``Registry.from_records``, no file and no real data. The real-build golden cases are in
``tests/golden/test_graph_edges_pilot.py``.

Expected values are derived from the documented contract (which relationship each edge type states, its direction, the
E08 attribute shape) and from the fixture's own construction (the evidence ids written per cell), never copied from the
builder's output. The choices that the specification leaves open are D-7 ... D-14 in ``skillgraph.graph.edges``; a test
that depends on one says so.
"""

import ast
import itertools
import random
from pathlib import Path

import pytest
from model_factory import curated, ev, hours, official
from pydantic import ValidationError

from skillgraph.graph import (
    STATIC_EDGE_TYPES,
    EdgeBuildError,
    EdgeType,
    GraphEdge,
    GraphError,
    LegendEntry,
    build_static_edges,
    static_legend,
)
from skillgraph.model.conflict import Conflict
from skillgraph.model.evidence import Evidence, OfficialValued
from skillgraph.model.ids import slug_of
from skillgraph.model.occupation import Occupation
from skillgraph.model.qualification import NosUnit, Qualification
from skillgraph.registry import Registry

# ---- fixture builders -------------------------------------------------------------------------------------------------

EVIDENCE = [
    Evidence.model_validate({"id": ev(n), "evidence_class": "OFFICIAL", "source_id": "src:T1",
                             "source_sha256": "0" * 64, "location": "QF item 13"})
    for n in range(1, 1200)
]


def code_of(n: int) -> str:
    return f"TEST/Q900{n}"


def nos(n: int) -> str:
    return f"nos:TEST/N900{n}"


def base_of(qn: int, s_no: int) -> int:
    """First of the four evidence ids of one NOS-table row: level, version, hours (all five parts), credits."""
    return 100 * qn + 4 * s_no


def row_evidence(qn: int, s_no: int, *, with_version: bool = True) -> set[str]:
    b = base_of(qn, s_no)
    return {ev(b), ev(b + 2), ev(b + 3)} | ({ev(b + 1)} if with_version else set())


def row(s_no: int, nos_id: str | None, core: str = "Core", version: str | None = "1.0", conflict: str | None = None) -> dict:
    return {"s_no": s_no, "nos_id": nos_id, "core": core, "version": version, "conflict": conflict}


def mk_qual(qn: int, rows=(), *, claims=(), nco=("8153.0101",), eligibility=None, **changes) -> Qualification:
    """Curated TEST/Q900<qn>. A row with ``nos_id=None`` is a bridge module. ``claims`` are (text, resolved_target) pairs."""
    code = code_of(qn)
    qid = f"qual:{code}"
    memberships, modules = [], []
    for r in rows:
        b = base_of(qn, r["s_no"])
        level = official(2.5, b, **({"conflict_id": r["conflict"]} if r["conflict"] else {}))
        version = None if r["nos_id"] is None or r["version"] is None else official(r["version"], b + 1, engine_use="DISPLAY_ONLY")
        m = {"qualification_id": qid, "nos_id": r["nos_id"], "s_no": r["s_no"], "core_or_noncore": r["core"],
             "nsqf_level": level, "version": version, "hours": hours(100.0, b + 2), "credits": official(4.0, b + 3, engine_use="NOT_USED"),
             "is_bridge": r["nos_id"] is None}
        if r["nos_id"] is None:
            m["module_id"] = f"mod:{code}/S{r['s_no']}"
            modules.append({"id": m["module_id"], "qualification_id": qid, "s_no": r["s_no"], "title": "Bridge", "is_bridge": True})
        memberships.append(m)
    claim_records = [
        {"id": f"claim:{code}/P{i}", "qualification_id": qid, "text_verbatim": text, "direction_label": "Horizontal",
         "resolved_target": target, "evidence_id": ev(900 + 10 * qn + i)}
        for i, (text, target) in enumerate(claims, start=1)
    ]
    body = curated(id=qid, code=code, slug=slug_of(qid), nos_memberships=memberships, modules=modules,
                   progression_claims=claim_records, nco_codes=[official(c, 800 + 10 * qn + i) for i, c in enumerate(nco)],
                   eligibility=eligibility, **changes)
    return Qualification.model_validate(body)


def conflict(oid: str = "OV-001", entity: str = "nos:TEST/N9001") -> Conflict:
    return Conflict.model_validate({
        "id": f"conflict:{oid}", "subject": {"entity_id": entity, "field": "nsqf_level (membership in qual:TEST/Q9001)"},
        "values": [{"value": 3.5, "evidence_id": ev(1)}, {"value": 4.0, "evidence_id": ev(2)}],
        "status": "UNRESOLVED_SOURCE_CONFLICT", "overlay_ids": [oid], "decision_ref": "A1", "engine_effect": "DISPLAY_ONLY"})


def records(quals, *, conflicts=(), evidence=EVIDENCE) -> dict:
    nos_ids = sorted({m.nos_id for q in quals for m in q.nos_memberships if m.nos_id})
    users = {n: [q.id for q in quals if any(m.nos_id == n for m in q.nos_memberships)] for n in nos_ids}
    codes = sorted({c.value for q in quals for c in q.nco_codes if c.value})
    return {
        "qualifications": list(quals),
        "nos_units": [NosUnit.model_validate({"id": n, "code": n[4:], "titles_by_source": {u: "Title" for u in users[n]}}) for n in nos_ids],
        "occupations": [Occupation.model_validate({"id": f"nco:{c}", "nco_code": c, "title_verification": "NOT_CHECKED"}) for c in codes],
        "evidence": list(evidence),
        "conflicts": list(conflicts),
    }


def registry(quals, **kw) -> Registry:
    return Registry.from_records(**records(quals, **kw))


def world() -> list[Qualification]:
    """A: N1 (Core, 1.0), N2 (Non-Core, 1.0)      B: N1 (Core, 1.0), N2 (Non-Core, 2.0), N3 (Non-Core, none printed)
    C: N3 (Non-Core, blank), N4 (Core, 1.0)      D: N4 (Non-Core, 1.0)      E: N5 only
    Shared: A-B {N1, N2}; B-C {N3}; C-D {N4, classified differently}. A, B have a bridge module."""
    return [
        mk_qual(1, [row(1, None), row(2, nos(1), "Core"), row(3, nos(2), "Non-Core")], claims=[("Next role", None)]),
        mk_qual(2, [row(1, None), row(2, nos(1), "Core"), row(3, nos(2), "Non-Core", "2.0"), row(4, nos(3), "Non-Core", None)]),
        mk_qual(3, [row(2, nos(3), "Non-Core", ""), row(3, nos(4), "Core")], nco=("8153.0101", "7543.0301")),
        mk_qual(4, [row(2, nos(4), "Non-Core")], nco=()),
        mk_qual(5, [row(2, nos(5))], nco=("8153.0101",)),
    ]


@pytest.fixture
def reg() -> Registry:
    return registry(world())


def by_type(edges, edge_type):
    return [e for e in edges if e.type is edge_type]


def shares(edges):
    return {(e.source, e.target): e for e in by_type(edges, EdgeType.SHARES_NOS)}


# ---- INCLUDES_NOS -----------------------------------------------------------------------------------------------------


def test_one_includes_edge_per_membership_from_qualification_to_unit_or_module(reg):
    edges = by_type(build_static_edges(reg), EdgeType.INCLUDES_NOS)
    expected = {(q.id, m.nos_id or m.module_id) for q in reg.qualifications() for m in q.nos_memberships}
    assert {(e.source, e.target) for e in edges} == expected and len(edges) == len(expected) == 3 + 4 + 2 + 1 + 1
    for e in edges:
        assert e.source.startswith("qual:") and e.target.split(":")[0] in ("nos", "mod")
        assert (e.directed, e.evidence_class.value, e.experimental) == (True, "OFFICIAL", False)
        assert e.id == f"e:INCLUDES_NOS:{e.source[5:]}:{e.target.split(':', 1)[1]}"


def test_includes_edge_attributes_describe_the_row(reg):
    e = {e.id: e for e in build_static_edges(reg)}
    a = e["e:INCLUDES_NOS:TEST/Q9002:TEST/N9002"].attributes
    assert a == {"s_no": 3, "core_or_noncore": "Non-Core", "is_bridge": False, "version": "2.0"}
    assert e["e:INCLUDES_NOS:TEST/Q9002:TEST/N9001"].attributes["core_or_noncore"] == "Core"
    bridge = e["e:INCLUDES_NOS:TEST/Q9001:TEST/Q9001/S1"]
    assert bridge.target == "mod:TEST/Q9001/S1" and bridge.attributes["is_bridge"] is True and bridge.attributes["version"] is None
    # a version printed as nothing is reported as null (D-10 reads blank as "not stated")
    assert e["e:INCLUDES_NOS:TEST/Q9003:TEST/N9003"].attributes["version"] is None


def test_includes_edge_evidence_is_exactly_the_cells_of_its_row(reg):
    """D-8: level, version (when printed), five hours values (one shared id here), credits."""
    e = {e.id: e for e in build_static_edges(reg)}
    assert e["e:INCLUDES_NOS:TEST/Q9002:TEST/N9002"].evidence_ids == sorted(row_evidence(2, 3))
    assert e["e:INCLUDES_NOS:TEST/Q9002:TEST/N9003"].evidence_ids == sorted(row_evidence(2, 4, with_version=False))  # no version printed
    assert e["e:INCLUDES_NOS:TEST/Q9001:TEST/Q9001/S1"].evidence_ids == sorted(row_evidence(1, 1, with_version=False))


def test_every_edge_carries_evidence_that_resolves_in_the_registry(reg):
    for e in build_static_edges(reg):
        assert e.evidence_ids and e.evidence_ids == sorted(set(e.evidence_ids))
        for eid in e.evidence_ids:
            reg.evidence_by_id(eid)


def test_a_conflicted_membership_value_flags_its_includes_edge_and_only_that_one():
    quals = world()
    quals[0] = mk_qual(1, [row(1, None), row(2, nos(1), "Core", "1.0", "conflict:OV-001"), row(3, nos(2), "Non-Core")])
    edges = {e.id: e for e in build_static_edges(registry(quals, conflicts=[conflict()]))}
    flagged = {i for i, e in edges.items() if e.type is EdgeType.INCLUDES_NOS and e.flags}
    assert flagged == {"e:INCLUDES_NOS:TEST/Q9001:TEST/N9001"}
    (f,) = edges["e:INCLUDES_NOS:TEST/Q9001:TEST/N9001"].flags
    assert (f.code.value, f.severity.value, f.refs) == ("SOURCE_CONFLICT", "INFO", ["conflict:OV-001"])
    assert "nsqf_level" in f.message and "no value has been chosen" in f.message


# ---- SHARES_NOS -------------------------------------------------------------------------------------------------------


def test_shares_edges_exist_exactly_for_pairs_with_a_common_unit(reg):
    got = shares(build_static_edges(reg))
    assert set(got) == {("qual:TEST/Q9001", "qual:TEST/Q9002"), ("qual:TEST/Q9002", "qual:TEST/Q9003"),
                        ("qual:TEST/Q9003", "qual:TEST/Q9004")}
    # E shares nothing; the bridge modules are per-qualification and never shared
    assert not any("Q9005" in k for pair in got for k in pair)


def test_shares_edge_shape_direction_and_class(reg):
    for (a, b), e in shares(build_static_edges(reg)).items():
        assert a < b and (e.source, e.target) == (a, b)
        assert (e.directed, e.evidence_class.value, e.experimental) == (False, "RULE_DERIVED", False)
        assert e.id == f"e:SHARES_NOS:{a[5:]}:{b[5:]}"


def test_shares_attributes_codes_counts_and_versions(reg):
    got = shares(build_static_edges(reg))
    ab = got[("qual:TEST/Q9001", "qual:TEST/Q9002")].attributes
    assert ab == {"shared_codes": ["TEST/N9001", "TEST/N9002"], "core_shared_count": 1, "noncore_shared_count": 1,
                  "mixed_core_codes": [], "version_agreement": {"TEST/N9001": "SAME", "TEST/N9002": "DIFFERENT"}}
    bc = got[("qual:TEST/Q9002", "qual:TEST/Q9003")].attributes
    assert bc["shared_codes"] == ["TEST/N9003"] and bc["noncore_shared_count"] == 1 and bc["core_shared_count"] == 0
    assert bc["version_agreement"] == {"TEST/N9003": "NOT_STATED"}  # none printed on one side, blank on the other


def test_a_unit_classified_core_by_one_qf_and_non_core_by_the_other_is_reported_not_counted(reg):
    """D-11: neither count includes it; ``mixed_core_codes`` names it, so core + non-core + mixed == shared."""
    a = shares(build_static_edges(reg))[("qual:TEST/Q9003", "qual:TEST/Q9004")].attributes
    assert (a["core_shared_count"], a["noncore_shared_count"], a["mixed_core_codes"]) == (0, 0, ["TEST/N9004"])
    assert a["shared_codes"] == ["TEST/N9004"]


@pytest.mark.parametrize(("va", "vb", "expected"), [
    ("1.0", "1.0", "SAME"), ("1.0", "2.0", "DIFFERENT"), ("1.0", None, "NOT_STATED"), (None, "1.0", "NOT_STATED"),
    (None, None, "NOT_STATED"), ("1.0", "", "NOT_STATED"), ("", "", "NOT_STATED"), (" ", "1.0", "NOT_STATED"),
    ("1.0", " 1.0 ", "SAME"),
])
def test_version_agreement_rule(va, vb, expected):
    quals = [mk_qual(1, [row(2, nos(1), version=va)]), mk_qual(2, [row(2, nos(1), version=vb)])]
    (e,) = by_type(build_static_edges(registry(quals)), EdgeType.SHARES_NOS)
    assert e.attributes["version_agreement"] == {"TEST/N9001": expected}


def test_three_qualifications_sharing_one_unit_give_three_edges_stored_once_each():
    quals = [mk_qual(n, [row(2, nos(1), "Non-Core")]) for n in (3, 1, 2)]
    got = shares(build_static_edges(registry(quals)))
    assert set(got) == {("qual:TEST/Q9001", "qual:TEST/Q9002"), ("qual:TEST/Q9001", "qual:TEST/Q9003"),
                        ("qual:TEST/Q9002", "qual:TEST/Q9003")}


def test_shares_evidence_is_the_union_of_both_rows_for_every_shared_unit(reg):
    e = shares(build_static_edges(reg))[("qual:TEST/Q9001", "qual:TEST/Q9002")]
    expected = row_evidence(1, 2) | row_evidence(1, 3) | row_evidence(2, 2) | row_evidence(2, 3)
    assert e.evidence_ids == sorted(expected)
    # a single-code edge carries only the rows of that code
    bc = shares(build_static_edges(reg))[("qual:TEST/Q9002", "qual:TEST/Q9003")]
    assert bc.evidence_ids == sorted(row_evidence(2, 4, with_version=False) | row_evidence(3, 2))


def test_shares_edge_carries_the_conflict_of_a_membership_on_either_side_and_only_for_involved_pairs():
    quals = world()
    quals[1] = mk_qual(2, [row(1, None), row(2, nos(1), "Core", "1.0", "conflict:OV-001"), row(3, nos(2), "Non-Core", "2.0"),
                           row(4, nos(3), "Non-Core", None)])
    edges = shares(build_static_edges(registry(quals, conflicts=[conflict()])))
    flagged = {k for k, e in edges.items() if e.flags}
    assert flagged == {("qual:TEST/Q9001", "qual:TEST/Q9002")}
    (f,) = edges[("qual:TEST/Q9001", "qual:TEST/Q9002")].flags
    assert f.refs == ["conflict:OV-001"] and f.code.value == "SOURCE_CONFLICT"


def test_the_same_conflict_on_both_sides_is_one_flag_and_two_conflicts_are_two_sorted_flags():
    quals = [mk_qual(1, [row(2, nos(1), "Non-Core", "1.0", "conflict:OV-002"), row(3, nos(2), "Non-Core", "1.0")]),
             mk_qual(2, [row(2, nos(1), "Non-Core", "1.0", "conflict:OV-002"), row(3, nos(2), "Non-Core", "1.0", "conflict:OV-001")])]
    (e,) = by_type(build_static_edges(registry(quals, conflicts=[conflict("OV-001"), conflict("OV-002")])), EdgeType.SHARES_NOS)
    assert [f.refs for f in e.flags] == [["conflict:OV-001"], ["conflict:OV-002"]]


def test_a_membership_conflict_id_missing_from_the_registry_is_reported():
    quals = [mk_qual(1, [row(2, nos(1), conflict="conflict:OV-009")])]
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(registry(quals))
    assert any("conflict:OV-009" in p for p in exc.value.problems)


# ---- PROGRESSION_CLAIM ------------------------------------------------------------------------------------------------


def test_claim_edge_runs_from_the_qualification_to_its_claim_node(reg):
    (e,) = by_type(build_static_edges(reg), EdgeType.PROGRESSION_CLAIM)
    assert (e.source, e.target, e.directed) == ("qual:TEST/Q9001", "claim:TEST/Q9001/P1", True)
    assert (e.evidence_class.value, e.experimental, e.id) == ("OFFICIAL", False, "e:PROGRESSION_CLAIM:TEST/Q9001:TEST/Q9001/P1")
    assert e.evidence_ids == [ev(900 + 10 + 1)] and e.attributes == {"direction_label": "Horizontal"}


def test_no_claim_edge_targets_a_qualification_even_when_a_claim_has_a_resolved_target():
    """D-13 / TASKS P3.4: the name-based link is an INFERENCE for P3.5; it is not read and changes nothing."""
    target = {"qualification_id": "qual:TEST/Q9002", "evidence_class": "INFERENCE", "evidence_id": ev(950)}
    plain = [mk_qual(1, [row(2, nos(1))], claims=[("Next role", None)]), mk_qual(2, [row(2, nos(1))])]
    linked = [mk_qual(1, [row(2, nos(1))], claims=[("Next role", target)]), mk_qual(2, [row(2, nos(1))])]
    a, b = build_static_edges(registry(plain)), build_static_edges(registry(linked))
    assert a == b
    assert all(e.target.startswith("claim:") for e in by_type(b, EdgeType.PROGRESSION_CLAIM))
    assert not any(e.target.startswith("qual:") for e in b if e.type is not EdgeType.SHARES_NOS)


def test_several_claims_each_get_an_edge_in_claim_order():
    quals = [mk_qual(1, [], claims=[("One", None), ("Two", None), ("Three", None)])]
    edges = by_type(build_static_edges(registry(quals)), EdgeType.PROGRESSION_CLAIM)
    assert [e.target for e in edges] == [f"claim:TEST/Q9001/P{i}" for i in (1, 2, 3)]


# ---- ALIGNED_TO_NCO ---------------------------------------------------------------------------------------------------


def test_nco_edges_run_from_the_qualification_to_each_stated_occupation(reg):
    edges = by_type(build_static_edges(reg), EdgeType.ALIGNED_TO_NCO)
    assert {(e.source, e.target) for e in edges} == {
        ("qual:TEST/Q9001", "nco:8153.0101"), ("qual:TEST/Q9002", "nco:8153.0101"), ("qual:TEST/Q9003", "nco:7543.0301"),
        ("qual:TEST/Q9003", "nco:8153.0101"), ("qual:TEST/Q9005", "nco:8153.0101")}  # Q9004 states none: no edge
    e = next(e for e in edges if e.target == "nco:7543.0301")
    assert (e.directed, e.evidence_class.value, e.experimental, e.attributes) == (True, "OFFICIAL", False, {})
    assert e.evidence_ids == [ev(800 + 30 + 1)] and e.id == "e:ALIGNED_TO_NCO:TEST/Q9003:7543.0301"


def test_two_qualifications_with_one_nco_code_get_no_edge_between_them(reg):
    """Alignment to the same occupation is not adjacency (ARCHITECTURE §10.3: no qual-qual edge from a shared NCO code)."""
    quals = {(e.source, e.target) for e in build_static_edges(reg) if e.type is not EdgeType.SHARES_NOS}
    assert not any(t.startswith("qual:") for _, t in quals)


# ---- invalid input is reported, never repaired (D-9) ------------------------------------------------------------------


def test_the_same_unit_listed_twice_by_one_qualification_is_an_error_not_a_merge():
    quals = [mk_qual(1, [row(2, nos(1)), row(3, nos(1), "Non-Core")])]
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(registry(quals))
    assert any("INCLUDES_NOS:TEST/Q9001:TEST/N9001" in p and "more than once" in p for p in exc.value.problems)
    assert isinstance(exc.value, GraphError)


def test_the_same_nco_code_twice_in_one_qualification_is_an_error():
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(registry([mk_qual(1, [], nco=("8153.0101", "8153.0101"))]))
    assert any("ALIGNED_TO_NCO" in p and "more than once" in p for p in exc.value.problems)


def test_a_null_nco_code_is_an_error():
    q = mk_qual(1, [])
    q = q.model_copy(update={"nco_codes": [OfficialValued[str].model_validate(official(None, 1))]})
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(registry([q]))
    assert any("null" in p for p in exc.value.problems)


def test_evidence_missing_from_the_registry_is_an_error_naming_the_row():
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(registry([mk_qual(1, [row(2, nos(1))])], evidence=[]))
    assert any("S.No. 2" in p and "not in the registry" in p for p in exc.value.problems)


def test_all_problems_are_listed_not_just_the_first():
    quals = [mk_qual(1, [row(2, nos(1)), row(3, nos(1))], nco=("8153.0101", "8153.0101"))]
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(registry(quals))
    assert len(exc.value.problems) == 2 and "more than once" in str(exc.value)


class Stub:
    """A registry wrapper that overrides some reads, to reach the defensive checks that ``from_records`` already forbids."""

    def __init__(self, real, **overrides):
        self._real, self._overrides = real, overrides

    def __getattr__(self, name):
        return self._overrides.get(name) or getattr(self._real, name)


def test_a_membership_of_an_unknown_unit_is_a_dangling_endpoint():
    real = registry([mk_qual(1, [row(2, nos(1))])])
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(Stub(real, nos_units=lambda: ()))
    assert any("unknown NOS unit nos:TEST/N9001" in p for p in exc.value.problems)


def test_a_module_that_the_qualification_does_not_own_is_a_dangling_endpoint():
    real = registry([mk_qual(1, [row(1, None)])])
    q = real.qualifications()[0].model_copy(update={"modules": []})
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(Stub(real, qualifications=lambda: (q,)))
    assert any("is not a module of qual:TEST/Q9001" in p for p in exc.value.problems)


def test_a_membership_that_belongs_to_another_qualification_is_refused():
    real = registry([mk_qual(1, [row(2, nos(1))])])
    q = real.qualifications()[0]
    q = q.model_copy(update={"nos_memberships": [q.nos_memberships[0].model_copy(update={"qualification_id": "qual:TEST/Q9002"})]})
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(Stub(real, qualifications=lambda: (q,)))
    assert any("belongs to qual:TEST/Q9002" in p for p in exc.value.problems)


def test_a_claim_that_belongs_to_another_qualification_is_refused():
    real = registry([mk_qual(1, [], claims=[("Next", None)])])
    q = real.qualifications()[0]
    q = q.model_copy(update={"progression_claims": [q.progression_claims[0].model_copy(update={"qualification_id": "qual:TEST/Q9002"})]})
    with pytest.raises(EdgeBuildError):
        build_static_edges(Stub(real, qualifications=lambda: (q,)))


def test_an_occupation_missing_from_the_registry_is_a_dangling_endpoint():
    real = registry([mk_qual(1, [])])
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(Stub(real, occupations=lambda: ()))
    assert any("unknown occupation nco:8153.0101" in p for p in exc.value.problems)


def test_a_registry_index_that_disagrees_with_the_nos_tables_is_reported():
    real = registry([mk_qual(1, [row(2, nos(1))]), mk_qual(2, [])])
    stub = Stub(real, qualification_ids_with_nos=lambda n: ("qual:TEST/Q9001", "qual:TEST/Q9002"))
    with pytest.raises(EdgeBuildError) as exc:
        build_static_edges(stub)
    assert any("do not match the NOS tables" in p for p in exc.value.problems)


# ---- empty and degenerate registries ----------------------------------------------------------------------------------


def test_an_empty_registry_is_a_valid_graph_with_no_edges():
    assert build_static_edges(Registry.from_records()) == []


def test_qualifications_with_no_relationships_give_no_edges():
    quals = [mk_qual(1, [], nco=()), mk_qual(2, [], nco=())]
    assert build_static_edges(registry(quals)) == []


def test_catalogue_only_records_contribute_no_edges_without_stating_any():
    from model_factory import catalogue_only
    cat = Qualification.model_validate(catalogue_only())
    assert build_static_edges(Registry.from_records(qualifications=[cat])) == []


def test_a_catalogue_only_record_that_states_an_nco_code_gets_its_edge_and_filtering_is_not_done_here():
    """D-7: the E08 ``include_catalogue_only`` filter belongs to the view, not to the edge builder."""
    from model_factory import catalogue_only
    cat = Qualification.model_validate(catalogue_only(nco_codes=[official("8153.0101", 6)]))
    reg = Registry.from_records(qualifications=[cat], evidence=EVIDENCE, occupations=records([mk_qual(1, [])])["occupations"])
    (e,) = build_static_edges(reg)
    assert (e.type, e.source, e.target) == (EdgeType.ALIGNED_TO_NCO, "qual:TEST/Q9002", "nco:8153.0101")


def test_a_single_qualification_never_shares_with_itself():
    assert by_type(build_static_edges(registry([mk_qual(1, [row(2, nos(1)), row(3, nos(2))])])), EdgeType.SHARES_NOS) == []


# ---- determinism and order --------------------------------------------------------------------------------------------


def test_edges_are_sorted_by_type_source_target(reg):
    edges = build_static_edges(reg)
    keys = [(e.type.value, e.source, e.target) for e in edges]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    assert [k for k, _ in itertools.groupby(keys, key=lambda k: k[0])] == [
        "ALIGNED_TO_NCO", "INCLUDES_NOS", "PROGRESSION_CLAIM", "SHARES_NOS"]


def test_repeated_calls_give_identical_edges_and_identical_json(reg):
    runs = [build_static_edges(reg) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert [e.model_dump_json() for e in runs[0]] == [e.model_dump_json() for e in runs[2]]


def test_record_order_does_not_change_the_result():
    expected = build_static_edges(registry(world()))
    rng = random.Random(7)
    for _ in range(5):
        rec = records(world())
        for name in rec:
            rng.shuffle(rec[name])
        got = build_static_edges(Registry.from_records(**rec))
        assert got == expected and [e.model_dump_json() for e in got] == [e.model_dump_json() for e in expected]


def test_each_call_returns_a_new_list_of_new_edges_so_a_caller_cannot_poison_later_calls(reg):
    first = build_static_edges(reg)
    shares(first)[("qual:TEST/Q9001", "qual:TEST/Q9002")].attributes["shared_codes"].append("X")
    first.clear()
    again = build_static_edges(reg)
    assert shares(again)[("qual:TEST/Q9001", "qual:TEST/Q9002")].attributes["shared_codes"] == ["TEST/N9001", "TEST/N9002"]
    assert again == build_static_edges(reg)


def test_building_never_changes_the_registry(reg):
    before = (reg.qualifications(), reg.nos_units(), reg.occupations(), reg.conflicts())
    build_static_edges(reg)
    assert (reg.qualifications(), reg.nos_units(), reg.occupations(), reg.conflicts()) == before


def test_static_edges_are_off_by_default_free_of_inference_and_unchanged_when_inference_is_requested(reg):
    """P3.5 superseded the P3.4 behaviour (D-7: ``include_inference=True`` raised ``NotImplementedError`` until P3.5 existed).
    What stays pinned: the default and ``False`` build static edges only, and requesting inference never changes them. The
    inference edges themselves are tested in ``test_graph_inference.py``."""
    assert build_static_edges(reg, include_inference=False) == build_static_edges(reg)
    assert {e.type for e in build_static_edges(reg)} <= set(STATIC_EDGE_TYPES)
    assert not any(e.experimental for e in build_static_edges(reg))
    both = build_static_edges(reg, include_inference=True)
    assert [e for e in both if not e.experimental] == build_static_edges(reg)
    assert {e.type for e in both if e.experimental} <= {EdgeType.NCO_GROUP_PROXIMITY}


# ---- independence from everything that is not a documented relationship -----------------------------------------------


def test_edges_do_not_depend_on_credits_hours_levels_ages_titles_or_eligibility():
    """TASKS P3.4: eligibility, hours, credits and levels are not edge inputs; Q-B is not touched. Every value is changed,
    every evidence id is kept (ids are provenance, not values)."""
    quals = world()
    base = build_static_edges(registry(quals))

    def changed(q: Qualification) -> Qualification:
        ms = [m.model_copy(update={
            "credits": m.credits.model_copy(update={"value": 99.0}),
            "hours": m.hours.model_copy(update={"total": m.hours.total.model_copy(update={"value": 9999.0})}),
            "nsqf_level": m.nsqf_level.model_copy(update={"value": 9.5}),
        }) for m in q.nos_memberships]
        return q.model_copy(update={
            "nos_memberships": ms, "credits": q.credits.model_copy(update={"value": 77.0}),
            "min_age": q.min_age.model_copy(update={"value": 99}), "eligibility": None,
            "titles": q.titles.model_copy(update={"qf": "Another title"}),
            "nsqf_level": q.nsqf_level.model_copy(update={"value": 9.0, "engine_use": None}),
            "hours": q.hours.model_copy(update={"total": q.hours.total.model_copy(update={"value": 1.0})}),
        })

    assert build_static_edges(registry([changed(q) for q in quals])) == base


def test_a_qualification_with_and_without_eligibility_rules_has_the_same_edges():
    from model_factory import age_rule
    from model_factory import row as rule_row
    rules = {"age_rule": age_rule(), "rows": [rule_row(1)]}
    other = mk_qual(2, [row(2, nos(1))])
    with_rules = mk_qual(1, [row(2, nos(1))], eligibility=rules)
    assert with_rules.eligibility is not None
    assert build_static_edges(registry([with_rules, other])) == build_static_edges(registry([mk_qual(1, [row(2, nos(1))]), other]))


def test_shares_edges_ignore_titles_levels_and_nco_codes_when_no_unit_code_matches():
    """No edge from similarity: identical titles, levels and NCO codes without a common NOS code give no SHARES_NOS."""
    quals = [mk_qual(1, [row(2, nos(1))]), mk_qual(2, [row(2, nos(2))])]
    assert quals[0].titles == quals[1].titles and quals[0].nsqf_level == quals[1].nsqf_level
    assert by_type(build_static_edges(registry(quals)), EdgeType.SHARES_NOS) == []


def test_unit_matching_is_by_exact_code_only():
    quals = [mk_qual(1, [row(2, nos(1))]), mk_qual(2, [row(2, "nos:TEST/N9011")])]
    assert by_type(build_static_edges(registry(quals)), EdgeType.SHARES_NOS) == []


# ---- the GraphEdge contract -------------------------------------------------------------------------------------------


def good_edge(**changes) -> dict:
    base = dict(id="e:INCLUDES_NOS:TEST/Q9001:TEST/N9001", type="INCLUDES_NOS", source="qual:TEST/Q9001",
                target="nos:TEST/N9001", directed=True, evidence_class="OFFICIAL", experimental=False, attributes={},
                evidence_ids=[ev(1)], flags=[])
    return {**base, **changes}


def good_shares(**attr_changes) -> dict:
    attrs = {"shared_codes": ["TEST/N9001"], "core_shared_count": 1, "noncore_shared_count": 0, "mixed_core_codes": [],
             "version_agreement": {"TEST/N9001": "SAME"}, **attr_changes}
    return good_edge(id="e:SHARES_NOS:TEST/Q9001:TEST/Q9002", type="SHARES_NOS", target="qual:TEST/Q9002", directed=False,
                     evidence_class="RULE_DERIVED", attributes=attrs)


def test_a_well_formed_edge_validates_and_is_frozen():
    e = GraphEdge.model_validate(good_edge())
    with pytest.raises(ValidationError):
        e.directed = False  # type: ignore[misc]
    GraphEdge.model_validate(good_shares())


@pytest.mark.parametrize("changes", [
    {"id": "e:INCLUDES_NOS:TEST/Q9001:TEST/N9002"},          # id does not match endpoints
    {"source": "nos:TEST/N9001"},                            # wrong source kind
    {"target": "qual:TEST/Q9002", "id": "e:INCLUDES_NOS:TEST/Q9001:TEST/Q9002"},  # wrong target kind
    {"target": "mod:TEST/Q9002/S1", "id": "e:INCLUDES_NOS:TEST/Q9001:TEST/Q9002/S1"},  # module of another qualification
    {"directed": False}, {"evidence_class": "RULE_DERIVED"}, {"experimental": True},
    {"evidence_ids": []}, {"evidence_ids": [ev(2), ev(1)]}, {"evidence_ids": [ev(1), ev(1)]},
    {"source": "not-an-id"}, {"type": "UNKNOWN_TYPE"}, {"extra": 1},
])
def test_a_malformed_edge_is_refused(changes):
    with pytest.raises(ValidationError):
        GraphEdge.model_validate(good_edge(**changes))


@pytest.mark.parametrize("bad", [
    {"source": "qual:TEST/Q9003"},                                            # source not before target
    {"shared_codes": []}, {"shared_codes": ["TEST/N9002", "TEST/N9001"]},      # empty / unsorted
    {"core_shared_count": 0}, {"noncore_shared_count": 1},                    # counts do not account for the codes
    {"mixed_core_codes": ["TEST/N9999"]},                                     # not a shared code
    {"version_agreement": {"TEST/N9001": "MAYBE"}}, {"version_agreement": {}},
])
def test_a_malformed_shares_edge_is_refused(bad):
    data = good_shares() if "source" in bad else good_shares(**bad)
    if "source" in bad:
        data = {**data, **bad, "id": "e:SHARES_NOS:TEST/Q9003:TEST/Q9002"}
    with pytest.raises(ValidationError):
        GraphEdge.model_validate(data)


def test_a_shares_edge_with_missing_or_extra_attributes_is_refused():
    attrs = good_shares()["attributes"]
    for bad in ({k: v for k, v in attrs.items() if k != "mixed_core_codes"}, {**attrs, "extra": 1}):
        with pytest.raises(ValidationError):
            GraphEdge.model_validate({**good_shares(), "attributes": bad})


def test_claim_and_nco_endpoint_rules():
    claim = good_edge(id="e:PROGRESSION_CLAIM:TEST/Q9001:TEST/Q9001/P1", type="PROGRESSION_CLAIM", target="claim:TEST/Q9001/P1")
    GraphEdge.model_validate(claim)
    with pytest.raises(ValidationError):  # a claim edge never ends at a qualification
        GraphEdge.model_validate({**claim, "target": "qual:TEST/Q9002", "id": "e:PROGRESSION_CLAIM:TEST/Q9001:TEST/Q9002"})
    with pytest.raises(ValidationError):  # a claim of another qualification
        GraphEdge.model_validate({**claim, "target": "claim:TEST/Q9002/P1", "id": "e:PROGRESSION_CLAIM:TEST/Q9001:TEST/Q9002/P1"})
    GraphEdge.model_validate(good_edge(id="e:ALIGNED_TO_NCO:TEST/Q9001:8153.0101", type="ALIGNED_TO_NCO", target="nco:8153.0101"))


def test_an_inference_edge_must_be_experimental():
    data = good_shares() | {"id": "e:TITLE_SIMILARITY:TEST/Q9001:TEST/Q9002", "type": "TITLE_SIMILARITY",
                            "evidence_class": "INFERENCE", "experimental": True, "attributes": {}}
    GraphEdge.model_validate(data)
    with pytest.raises(ValidationError):
        GraphEdge.model_validate({**data, "experimental": False})


def test_edge_types_match_api_spec():
    assert [t.value for t in EdgeType] == ["INCLUDES_NOS", "SHARES_NOS", "PROGRESSION_CLAIM", "ALIGNED_TO_NCO",
                                           "NCO_GROUP_PROXIMITY", "TITLE_SIMILARITY"]
    assert [t.value for t in STATIC_EDGE_TYPES] == ["INCLUDES_NOS", "SHARES_NOS", "PROGRESSION_CLAIM", "ALIGNED_TO_NCO"]


# ---- legend -----------------------------------------------------------------------------------------------------------


def test_legend_covers_each_static_type_once_with_a_does_not_mean(reg):
    legend = static_legend()
    assert [e.edge_type for e in legend] == list(STATIC_EDGE_TYPES)
    assert all(isinstance(e, LegendEntry) and e.meaning.strip() and e.does_not_mean.strip() for e in legend)
    # the class stated in the legend is the class the builder gives the edge
    classes = {e.type: e.evidence_class for e in build_static_edges(reg)}
    assert {e.edge_type: e.evidence_class for e in legend} == classes


def test_shares_nos_legend_text_is_the_api_spec_e08_text():
    (e,) = [e for e in static_legend() if e.edge_type is EdgeType.SHARES_NOS]
    assert e.meaning == "Both qualifications list the same NOS code in their official QF."
    assert e.does_not_mean == "Skills are equivalent, units are exempt, or people move between these roles."
    spec = (Path(__file__).resolve().parents[2] / "API_SPEC.md").read_text(encoding="utf-8")
    assert e.meaning in spec and e.does_not_mean in spec


def test_no_legend_text_promises_eligibility_or_transitions():
    banned = ("guarantee", "will get", "eligible for job", "in demand", "declining")
    for e in static_legend():
        assert not any(b in (e.meaning + e.does_not_mean).lower() for b in banned)


# ---- boundaries -------------------------------------------------------------------------------------------------------


def test_the_edge_module_imports_only_model_and_registry():
    """ARCHITECTURE §6.2: ``graph/`` imports only ``model/`` and ``registry/`` (plus the standard library and pydantic)."""
    src = Path(__file__).resolve().parents[2] / "src" / "skillgraph" / "graph" / "edges.py"
    imported = set()
    for node in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add(node.module)
    internal = {m for m in imported if m.split(".")[0] == "skillgraph"}
    assert internal and all(m == "skillgraph.registry" or m.startswith("skillgraph.model") for m in internal), internal
    forbidden = ("skillgraph.eligibility", "skillgraph.labour", "skillgraph.api", "skillgraph.curation", "anthropic", "openai",
                 "requests", "httpx", "urllib", "socket", "random")
    assert not [m for m in imported if m.startswith(forbidden)]


def test_the_edge_module_reads_no_eligibility_hours_credit_level_title_or_inference_value():
    """Only ids, codes, lists, the core/non-core label and the printed version are read (D-8, D-10, D-13)."""
    src = Path(__file__).resolve().parents[2] / "src" / "skillgraph" / "graph" / "edges.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attrs & {"eligibility", "min_age", "titles", "resolved_target", "awarding_body", "sector", "coverage"}
    value_of = {n.value.attr for n in ast.walk(tree)
                if isinstance(n, ast.Attribute) and n.attr == "value" and isinstance(n.value, ast.Attribute)}
    # `.value` is taken only of the printed version and of two enum labels, never of credits, hours or a level
    assert value_of <= {"version", "core_or_noncore", "type"}, value_of


# ---- closeout (run 8): D-11 and D-14 ----------------------------------------------------------------------------------

E08_SHARES_ATTRIBUTES = {"shared_codes", "core_shared_count", "noncore_shared_count", "version_agreement"}


def test_d11_the_only_attribute_beyond_the_e08_four_is_mixed_core_codes_and_it_is_additive(reg):
    """API_SPEC E08 documents four SHARES_NOS attributes; API_SPEC 1.1 allows additive fields within v1. The documented four
    keep their documented types, and removing the extra key leaves exactly the documented shape."""
    for e in by_type(build_static_edges(reg), EdgeType.SHARES_NOS):
        a = e.attributes
        assert set(a) - E08_SHARES_ATTRIBUTES == {"mixed_core_codes"}
        assert isinstance(a["shared_codes"], list) and all(isinstance(c, str) for c in a["shared_codes"])
        assert type(a["core_shared_count"]) is int and type(a["noncore_shared_count"]) is int
        assert set(a["version_agreement"]) == set(a["shared_codes"])


def test_d11_a_disagreement_is_preserved_and_traceable_without_asserting_a_classification(reg):
    """The code is counted as neither Core nor Non-Core, and each QF's own printed label stays readable on its INCLUDES_NOS edge."""
    edges = build_static_edges(reg)
    cd = shares(edges)[("qual:TEST/Q9003", "qual:TEST/Q9004")].attributes
    assert cd["mixed_core_codes"] == ["TEST/N9004"] and cd["core_shared_count"] == 0 and cd["noncore_shared_count"] == 0
    ids = {e.id: e for e in edges}
    assert ids["e:INCLUDES_NOS:TEST/Q9003:TEST/N9004"].attributes["core_or_noncore"] == "Core"
    assert ids["e:INCLUDES_NOS:TEST/Q9004:TEST/N9004"].attributes["core_or_noncore"] == "Non-Core"


def test_d11_agreement_is_never_reported_as_mixed(reg):
    for (a, b), e in shares(build_static_edges(reg)).items():
        attrs = e.attributes
        assert attrs["core_shared_count"] + attrs["noncore_shared_count"] + len(attrs["mixed_core_codes"]) == len(attrs["shared_codes"])
    ab = shares(build_static_edges(reg))[("qual:TEST/Q9001", "qual:TEST/Q9002")].attributes
    assert ab["mixed_core_codes"] == []


REVIEWED_LEGEND = {
    "INCLUDES_NOS": ("OFFICIAL",
                     "The qualification's official QF lists this NOS unit or module as a row of its NOS table.",
                     "The unit is separately certified, exempt from re-training, or transferable to another qualification."),
    "SHARES_NOS": ("RULE_DERIVED",
                   "Both qualifications list the same NOS code in their official QF.",
                   "Skills are equivalent, units are exempt, or people move between these roles."),
    "PROGRESSION_CLAIM": ("OFFICIAL",
                          "The qualification's official QF (item 15) lists this text as a progression.",
                          "That the text is linked to a qualification in this graph (any such link is an experimental inference), "
                          "that anyone is eligible for it, or that people make this move."),
    "ALIGNED_TO_NCO": ("OFFICIAL",
                       "The qualification's official documents state this NCO-2015 occupation code.",
                       "The qualification leads to that occupation, jobs exist in it, or qualifications sharing a code are interchangeable."),
}


def test_d14_the_reviewed_legend_strings_are_pinned():
    """Any change to a legend string must be a deliberate change to this reviewed set (docs/decisions/P3_4_CLOSEOUT.md)."""
    got = {e.edge_type.value: (e.evidence_class.value, e.meaning, e.does_not_mean) for e in static_legend()}
    assert got == REVIEWED_LEGEND


def test_d14_no_legend_string_states_proof_of_eligibility_employment_or_a_path():
    claims = ("is eligible", "will be eligible", "will get", "guarantee", "employable", "employability", "placement",
              "in demand", "declining", "a valid path", "can progress", "will progress")
    for e in static_legend():
        # the affirmative half (what the edge means) never says any of it; such words may appear only in the negated half
        assert not [c for c in claims if c in e.meaning.lower()]
        for word in ("eligible", "jobs", "move"):
            assert word not in e.meaning.lower()


def test_d14_a_claim_text_that_equals_a_qualification_title_still_yields_only_a_claim_node():
    """The legend says the edge states no qualification link; this is why: a claim can name a catalogue title exactly."""
    q1 = mk_qual(1, [row(2, nos(1))], claims=[("Synthetic Qualification", None)])
    q2 = mk_qual(2, [row(2, nos(2))])
    assert q1.progression_claims[0].text_verbatim == q2.titles.qf
    edges = build_static_edges(registry([q1, q2]))
    (claim,) = by_type(edges, EdgeType.PROGRESSION_CLAIM)
    assert claim.target == "claim:TEST/Q9001/P1" and not any(e.source == "qual:TEST/Q9001" and e.target == "qual:TEST/Q9002" for e in edges)
