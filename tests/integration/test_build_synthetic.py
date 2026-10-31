"""P1.4 build against a synthetic, self-consistent tree (no restricted data needed)."""

import json
import shutil

import pytest
from synth_tree import PDF2, QP, SHA1, SHA2, SRC, SRC2, Tree, a1_html, load, ov, src

from skillgraph.curation import build as build_mod
from skillgraph.curation.errors import BuildError, EvidenceError, TargetError
from skillgraph.curation.overlay import OverlayError
from skillgraph.model.evidence import SAFE_USES
from skillgraph.provenance.manifest import SourceIntegrityError

E2 = f"rule:{QP}/E2"


@pytest.fixture
def tree(tmp_path):
    return Tree(tmp_path)


def row(result, rid):
    return next(r for r in load(result, "eligibility_source_rows.json") if r["id"] == rid)


def evidence(result):
    return {e["id"]: e for e in load(result, "evidence.json")}


# ---- classification x approval -------------------------------------------------------------------------------------


def test_empty_approvals_change_nothing_and_flag_pending(tree):
    r = tree.build(approve=[])
    m = r.manifest
    assert m["overlays"] == {"applied": [], "pending": ["OV-002", "OV-003"], "display_only": 1}
    assert m["overlay_classification_counts"] == {"APPLY": 0, "INTERPRET": 3, "DISPLAY": 1, "PENDING": 2, "IGNORE": 1}
    e2 = row(r, E2)
    exp = e2["raw_required_experience"]
    assert exp["value"] == "" and exp["value_status"] == "PARSED_UNCERTAIN" and exp["source_value"] is None
    assert e2["pending_overlay_ids"] == ["OV-002"] and e2["engine_use"] == "UNKNOWN"
    assert any(f["code"] == "OVERLAY_PENDING_APPROVAL" for f in e2["flags"])
    assert load(r, "qualifications.json")[0]["credit_groups"] == []
    assert m["overlay_effects"]["OV-002"] == {"classification": "PENDING", "effect": "PENDING_FLAGGED"}
    assert m["overlay_effects"]["OV-007"]["effect"] == "NO_RELATIONSHIP_ASSERTED"


def test_approved_correction_is_field_level_only_and_linked_to_two_evidence_records(tree):
    r = tree.build(approve=["OV-002"])
    e2 = row(r, E2)
    exp = e2["raw_required_experience"]
    assert (exp["value"], exp["source_value"], exp["value_status"]) == ("No Experience required", "", "CORRECTION_APPLIED")
    ev = evidence(r)
    new, old = ev[exp["evidence_id"]], ev[exp["source_evidence_id"]]
    assert new["id"] != old["id"]  # the id-collision hazard: same source, page, row and field
    assert new["evidence_class"] == old["evidence_class"] == "OFFICIAL"
    assert new["overlay_ids"] == ["OV-002"] and old["overlay_ids"] == []
    assert new["value_status"] == "CORRECTION_APPLIED" and old["value_status"] == "PARSED_UNCERTAIN"
    assert new["source_sha256"] == old["source_sha256"] == SHA1 and new["source_id"] == "src:S1"
    # unrelated field, row status and flags survive; engine_use is not raised; no verdict anywhere
    assert e2["raw_academic_or_skill"]["value_status"] == "PARSED_UNCERTAIN"
    assert e2["raw_academic_or_skill"]["engine_use"] == "UNKNOWN" and exp["engine_use"] == "UNKNOWN"
    assert e2["extraction_status"] == "PARSED_UNCERTAIN" and e2["engine_use"] == "UNKNOWN"
    assert any(f["code"] == "UNCERTAIN_EXTRACTION" for f in e2["flags"])
    assert e2["overlay_ids"] == ["OV-002", "OV-004"]
    assert r.manifest["overlays"]["applied"] == ["OV-002"]
    assert "verdict" not in json.dumps(load(r, "eligibility_source_rows.json")).lower()


def test_approved_representation_records_a_group_and_replaces_nothing(tree):
    base = tree.build(approve=[])
    r = tree.build(approve=["OV-003"])
    q = load(r, "qualifications.json")[0]
    (g,) = q["credit_groups"]
    assert g["member_s_nos"] == [1, 2] and g["overlay_ids"] == ["OV-003"]
    assert g["credits"]["value"] == 4.0 and g["credits"]["engine_use"] == "NOT_USED"
    members = {m["s_no"]: m["credits"] for m in q["nos_memberships"]}
    assert members[1]["value"] is None and members[2]["value"] == 4.0  # nothing copied between rows
    assert members[2]["value_status"] == "PARSED_UNCERTAIN"  # the source uncertainty is not cleared
    assert load(base, "qualifications.json")[0]["nos_memberships"] == q["nos_memberships"]
    assert r.manifest["overlay_effects"]["OV-003"]["effect"] == "GROUP_RECORDED"


def test_classification_matrix_never_raises_engine_use(tree):
    ids = ["OV-002", "OV-003"]
    for approve in ([], ["OV-002"], ["OV-003"], ids):
        r = tree.build(approve=approve)
        for rw in load(r, "eligibility_source_rows.json"):
            for fld in ("raw_academic_or_skill", "raw_required_experience", "raw_row_text", "min_age"):
                v = rw.get(fld)
                if v and rw["id"] == E2:
                    assert v["engine_use"] not in {u.value for u in SAFE_USES}
        q = load(r, "qualifications.json")[0]
        assert all(m["credits"]["engine_use"] == "NOT_USED" for m in q["nos_memberships"])
        assert q["hours"]["total"]["engine_use"] == "SAFE_HOURS"  # a documented default, not an overlay or approval
    r = tree.build(approve=[])
    assert load(r, "eligibility_source_rows.json")[0]["id"] == f"rule:{QP}/AGE"
    age = row(r, f"rule:{QP}/AGE")
    assert age["min_age"]["value_status"] == "CONFIRMED_BY_GEOMETRY" and age["min_age"]["engine_use"] == "SAFE_HARD_RULE"
    e1 = row(r, f"rule:{QP}/E1")
    assert e1["raw_required_experience"]["value_status"] == "CONFIRMED_BY_GEOMETRY"
    assert e1["raw_academic_or_skill"]["value_status"] == "PARSED_UNCERTAIN"  # only the targeted field is upgraded
    assert e1["raw_academic_or_skill"]["engine_use"] == "UNKNOWN"


def test_unlisted_cell_defaults_to_unknown(tree):
    q = load(tree.build(approve=[]), "qualifications.json")[0]
    assert q["nsqf_level"]["engine_use"] == "UNKNOWN"  # no overlay row and no documented default


# ---- approvals and target resolution -------------------------------------------------------------------------------


@pytest.mark.parametrize("bad,msg", [("OV-999", "does not exist"), ("OV-001", "not a proposal")])
def test_invalid_approval_fails_and_installs_nothing(tree, bad, msg):
    with pytest.raises(OverlayError, match=msg):
        tree.build(approve=[bad])
    assert tree.installed() == []


def test_stale_correction_fails(tree):
    tree.build(approve=[])
    tree.elig[1]["raw_required_experience"] = "something else"
    with pytest.raises(TargetError, match="stale"):
        tree.build(approve=[])
    assert tree.installed() == [p for p in tree.installed() if p.startswith("cb-")]


def test_unresolved_and_ambiguous_targets_fail(tree):
    tree.overlay[3]["target_row_key"] = f"{QP}|QF|eligibility_row|99"
    with pytest.raises(TargetError, match="matched 0"):
        tree.build(approve=[])
    tree2 = Tree(tree.root / "b")
    tree2.elig.append(dict(tree2.elig[1]))  # duplicate row 2
    with pytest.raises(TargetError, match="matched 2"):
        tree2.build(approve=[])


def test_composite_target_must_be_adjacent_and_exact(tree):
    tree.qfnos[1]["s_no"] = "3"
    with pytest.raises(TargetError, match="not adjacent"):
        tree.build(approve=[])
    t2 = Tree(tree.root / "b")
    t2.overlay[2]["target_row_key"] = f"{QP}|QF|bridge(s_no 1)+TST/N0099"
    with pytest.raises(TargetError, match="matched 0"):
        t2.build(approve=[])
    t3 = Tree(tree.root / "c")
    t3.overlay[2]["source_value"] = "bridge=''; TST/N0001='5'"
    with pytest.raises(TargetError, match="stale"):
        t3.build(approve=[])


def test_unknown_grammar_and_qp_mismatch_fail(tree):
    tree.overlay[0]["target_row_key"] = f"{QP}|QF|nonsense|1"
    with pytest.raises(TargetError, match="unknown eligibility_rows.csv key"):
        tree.build(approve=[])
    t2 = Tree(tree.root / "b")
    t2.overlay[0]["target_row_key"] = f"TST/Q0009|QF|eligibility_row|1"
    with pytest.raises(TargetError, match="qp_code"):
        t2.build(approve=[])


# ---- evidence ------------------------------------------------------------------------------------------------------


def test_correction_without_printed_value_cannot_be_substantiated(tree):
    tree.overlay[1]["overlay_value"] = "Ten years required"
    with pytest.raises(EvidenceError, match="cannot substantiate"):
        tree.build(approve=["OV-002"])
    assert tree.installed() == []
    # ... but unapproved, the same overlay row is merely pending
    assert tree.build(approve=[]).manifest["overlays"]["pending"] == ["OV-002", "OV-003"]


def test_applied_overlay_evidence_must_name_the_rows_source_and_page(tree):
    tree.overlay[1].update(evidence_source_file=SRC2, evidence_sha256=SHA2)
    with pytest.raises(EvidenceError, match="cites src:S2"):
        tree.build(approve=["OV-002"])
    t2 = Tree(tree.root / "b")
    t2.overlay[1]["evidence_page"] = "4"  # row is on page 3
    with pytest.raises(EvidenceError, match="not on the row's page"):
        t2.build(approve=["OV-002"])
    t3 = Tree(tree.root / "c")
    t3.overlay[1]["evidence_location"] = ""
    with pytest.raises(EvidenceError, match="needs evidence_location"):
        t3.build(approve=["OV-002"])


def test_evidence_page_beyond_the_document_fails(tree):
    tree.elig[1]["page"] = "99"
    tree.overlay[1]["evidence_page"] = "99"
    with pytest.raises(EvidenceError, match="beyond"):
        tree.build(approve=["OV-002"])


def test_evidence_with_unlisted_hash_fails_integrity_first(tree):
    tree.overlay[1]["evidence_sha256"] = "a" * 64
    with pytest.raises(SourceIntegrityError):
        tree.build(approve=[])
    assert tree.installed() == []


def test_unavailable_source_cannot_be_cited(tree):
    tree.elig[1].update(source_sha256="0" * 64)
    with pytest.raises(SourceIntegrityError):
        tree.build(approve=[])


def test_all_official_evidence_has_source_sha_and_page(tree):
    r = tree.build(approve=["OV-002", "OV-003"])
    srcs = {s["id"]: s for s in load(r, "sources.json")}
    for e in evidence(r).values():
        assert e["evidence_class"] == "OFFICIAL"
        assert e["source_sha256"] == srcs[e["source_id"]]["sha256"] and (e["page"] or e["location"])
    assert srcs["src:C3"]["sha256"] is None  # an unavailable source has no hash


# ---- integrity, byte identity, atomicity ---------------------------------------------------------------------------


def test_tampered_source_stops_the_build_before_any_output(tree):
    tree.write()
    (tree.raw / SRC).write_bytes((tree.raw / SRC).read_bytes() + b"x")
    called = []
    with pytest.raises(SourceIntegrityError):
        build_mod.build(tree.settings(), approvals_path=tree.approvals, config_path=tree.config, out_root=tree.out,
                        hook=called.append)
    assert called == [] and tree.installed() == []


def test_inputs_are_byte_identical_after_a_build(tree):
    tree.approved = ["OV-002", "OV-003"]
    tree.write()
    before = tree.snapshot()
    build_mod.build(tree.settings(), approvals_path=tree.approvals, config_path=tree.config, out_root=tree.out)
    assert tree.snapshot() == before


def test_failure_leaves_no_partial_output_and_keeps_existing_builds(tree):
    ok = tree.build(approve=[])
    files = {p.name: p.read_bytes() for p in ok.path.iterdir()}
    for stage in ("verified", "validated", "staged", "installing"):
        def boom(s, stage=stage):
            if s == stage:
                raise RuntimeError("injected")
        with pytest.raises(RuntimeError):
            tree.build(approve=["OV-002"], hook=boom)
        assert tree.installed() == [ok.data_build_id], f"stage {stage} left something behind"
        assert {p.name: p.read_bytes() for p in ok.path.iterdir()} == files


def test_complete_build_has_its_manifest_last_marker_and_staging_is_removed(tree):
    r = tree.build(approve=[])
    assert (r.path / "build_manifest.json").is_file()
    assert not [p for p in tree.out.iterdir() if p.name.startswith(".")]


def test_output_directory_must_not_overlap_inputs(tree):
    tree.write()
    for bad in (tree.ext, tree.raw / "sub", tree.data / "processed", tree.data / "raw"):
        with pytest.raises(BuildError, match="overlaps"):
            build_mod.build(tree.settings(), approvals_path=tree.approvals, config_path=tree.config, out_root=bad)


def test_incomplete_directory_with_the_same_name_is_refused(tree):
    ok = tree.build(approve=[])
    (ok.path / "build_manifest.json").unlink()
    with pytest.raises(BuildError, match="not a complete build"):
        tree.build(approve=[])
    assert (ok.path / "qualifications.json").is_file()


def test_same_id_with_different_content_is_refused(tree):
    ok = tree.build(approve=[])
    (ok.path / "evidence.json").write_bytes(b"[]\n")
    with pytest.raises(BuildError, match="different content"):
        tree.build(approve=[])


# ---- reproducibility -----------------------------------------------------------------------------------------------


def test_build_is_reproducible_and_inputs_change_the_id(tree, monkeypatch):
    from datetime import UTC, datetime

    a = tree.build(approve=[], now=datetime(2026, 1, 1, tzinfo=UTC))
    snap = {p.name: p.read_bytes() for p in a.path.iterdir() if p.name != "build_manifest.json"}
    shutil.rmtree(tree.out)
    b = tree.build(approve=[], now=datetime(2027, 6, 1, tzinfo=UTC))
    assert a.data_build_id == b.data_build_id and not b.reused
    assert snap == {p.name: p.read_bytes() for p in b.path.iterdir() if p.name != "build_manifest.json"}
    assert a.manifest["built_at"] != b.manifest["built_at"]
    again = tree.build(approve=[])
    assert again.reused and again.data_build_id == a.data_build_id
    assert tree.build(approve=["OV-002"]).data_build_id != a.data_build_id  # approvals digest
    monkeypatch.setattr(build_mod, "CURATION_CODE_VERSION", "other")
    assert tree.build(approve=[]).data_build_id != a.data_build_id  # code version
    monkeypatch.undo()
    tree.curation["expected_catalogue_only"] = 2
    tree.curation["engine_use_defaults"][0]["basis"] = "changed"
    assert tree.build(approve=[]).data_build_id != a.data_build_id  # relevant config
    tree.catalogue[2]["qp_name"] = "Renamed"
    tree.set_a1(a1_html(tree.catalogue))  # a renamed catalogue row that A1 agrees with is a different input
    assert tree.build(approve=[]).data_build_id not in (a.data_build_id,)


# ---- model validation, conflicts, leads, catalogue -------------------------------------------------------------------


def test_model_validation_errors_fail_the_build(tree):
    tree.qual[0]["nsqf_level"] = "3.3"  # not a multiple of 0.5
    with pytest.raises(BuildError, match="model validation failed"):
        tree.build(approve=[])
    assert tree.installed() == []


def test_catalogue_artifact_is_preserved_and_flagged_not_fixed(tree):
    quals = {q["code"]: q for q in load(tree.build(approve=[]), "qualifications.json")}
    q = quals["TST/Q0002"]
    assert q["titles"]["catalogue"] == "Other – Role" and q["coverage"] == "CATALOGUE_ONLY"
    assert any(f["code"] == "UNCERTAIN_EXTRACTION" and "U+2013" in f["message"] for f in q["quality_flags"])
    assert not any(f["code"] == "UNCERTAIN_EXTRACTION" for f in quals["TST/Q0003"]["quality_flags"])
    assert q["credits"]["engine_use"] == "NOT_USED" and q["hours"]["total"]["engine_use"] == "DISPLAY_ONLY"


def test_catalogue_count_mismatch_fails(tree):
    tree.curation["expected_catalogue_only"] = 5
    with pytest.raises(BuildError, match="expected 5"):
        tree.build(approve=[])


def conflict_tree(tree):
    tree.overlay += [
        ov("OV-008", f"{QP}|QF|TST/N0001", "credits", "UNRESOLVED_SOURCE_CONFLICT", "NOT_USED", file="qf_nos.csv",
           src_val="4", cat="SOURCE_CONFLICT", page="5", decision="D1"),
        ov("OV-009", f"{QP}|QP|TST/N0001", "credits", "UNRESOLVED_SOURCE_CONFLICT", "NOT_USED", file="qp_nos_headers.csv",
           src_val="9", cat="SOURCE_CONFLICT", page="14", decision="D1"),
    ]
    tree.curation["expected_overlay_rows"] = 9
    tree.curation["conflict_groups"] = [{
        "id": "OV-008", "overlays": ["OV-008", "OV-009"], "decision_ref": "D1", "engine_effect": "NOT_USED",
        "subject": {"entity_id": "nos:TST/N0001", "field": "credits"},
        "values": [{"overlay": "OV-008"}, {"overlay": "OV-009"}],
        "attach": [f"membership_credits:{QP}:TST/N0001"]}]


def test_conflict_registers_both_values_and_selects_none(tree):
    conflict_tree(tree)
    r = tree.build(approve=[])
    (c,) = load(r, "conflicts.json")
    assert c["id"] == "conflict:OV-008" and c["status"] == "UNRESOLVED_SOURCE_CONFLICT"
    assert sorted(v["value"] for v in c["values"]) == [4.0, 9.0] and c["engine_effect"] == "NOT_USED"
    assert "selected" not in json.dumps(c) and set(c) >= {"values", "overlay_ids"}
    q = load(r, "qualifications.json")[0]
    m = next(m for m in q["nos_memberships"] if m["s_no"] == 2)
    assert m["credits"]["conflict_id"] == "conflict:OV-008" and m["credits"]["value"] == 4.0
    assert r.manifest["counts"]["conflicts_open"] == 1
    assert r.manifest["overlay_effects"]["OV-009"]["effect"] == "CONFLICT_REGISTERED"
    assert any(f["code"] == "SOURCE_CONFLICT" and f["refs"] == ["conflict:OV-008"] for f in q["quality_flags"])


def test_unregistered_conflict_overlay_fails(tree):
    conflict_tree(tree)
    tree.curation["conflict_groups"] = []
    with pytest.raises(BuildError, match="without a conflict group"):
        tree.build(approve=[])


def test_conflict_that_no_longer_differs_fails(tree):
    conflict_tree(tree)
    tree.qpnos[0]["credits"] = "4"
    tree.overlay[-1]["source_value"] = "4"
    with pytest.raises(BuildError, match="no longer differ"):
        tree.build(approve=[])


def lead(tree):
    tree.curation["open_leads"] = [{
        "id": "DQ-03", "status": "UNRESOLVED_LEAD_SOURCE_UNAVAILABLE", "qualification": QP,
        "subject": "bridge/N0001 hours", "source_item": "C3", "reference": "synthetic"}]


def test_open_lead_is_a_flag_and_a_manifest_entry_not_a_conflict(tree):
    lead(tree)
    r = tree.build(approve=[])
    q = load(r, "qualifications.json")[0]
    f = next(f for f in q["quality_flags"] if f["code"] == "SOURCE_UNAVAILABLE")
    assert f["refs"] == ["src:C3"]
    assert r.manifest["open_leads"][0]["id"] == "DQ-03" and load(r, "conflicts.json") == []
    assert {"manifest_item_id": "C3", "title": "Unavailable record", "reason": "404 FAIL_HTTP"} in r.manifest["sources_unavailable"]


def test_lead_whose_source_becomes_available_fails(tree):
    lead(tree)
    tree.curation["open_leads"][0]["source_item"] = "S1"
    with pytest.raises(BuildError, match="now available"):
        tree.build(approve=[])


def test_secondary_copy_must_agree(tree):
    tree.qual.append(src(doc_type="QF_SECONDARY", qualification_name="Synthetic Operator", nsqf_level="3", min_age="18",
                         credits="4", hours_theory="20", hours_practical="80", hours_ojt_mandatory="0",
                         hours_ojt_recommended="0", hours_total="100", nco_2015_code="8153.0101", page="3-4",
                         source_file=SRC2, source_sha256=SHA2))
    r = tree.build(approve=[])
    q = load(r, "qualifications.json")[0]
    assert any(f["code"] == "SECONDARY_COPY_BINARY_DIFFERS" for f in q["quality_flags"])
    assert next(s for s in load(r, "sources.json") if s["id"] == "src:S2")["role"] == "SECONDARY"
    tree.qual[1]["hours_total"] = "101"
    with pytest.raises(BuildError, match="secondary QF copy disagrees"):
        tree.build(approve=[])


def test_overlay_row_that_is_not_consumed_is_not_silently_dropped(tree):
    tree.overlay.append(ov("OV-008", f"{QP}|QF|age_9c", "min_age", "INTERPRETATION_DECIDED", "SAFE_HARD_RULE",
                           src_val="18", page="4"))
    tree.curation["expected_overlay_rows"] = 8
    r = tree.build(approve=[])  # a second row on a consumed cell is fine; effects are recorded for all
    assert set(r.manifest["overlay_effects"]) == {f"OV-{i:03d}" for i in range(1, 9)}
    tree.overlay[-1]["engine_use"] = "SAFE_HOURS"
    with pytest.raises(BuildError, match="disagree on"):
        tree.build(approve=[])


def test_dropped_or_gapped_overlay_rows_fail_cleanly(tree):
    del tree.overlay[0]  # OV-001 gone: contiguous ids and the expected count both catch it
    with pytest.raises(BuildError, match="incomplete or has gaps"):
        tree.build(approve=[])
    t2 = Tree(tree.root / "b")
    t2.curation["expected_overlay_rows"] = 8
    with pytest.raises(BuildError, match="expected 8"):
        t2.build(approve=[])


def test_proposal_engine_use_never_reaches_output(tree):
    # a pending or approved correction that claims a SAFE use must not make its cell safe
    tree.overlay[1]["engine_use"] = "SAFE_HARD_RULE"
    for approve in ([], ["OV-002"]):
        r = tree.build(approve=approve)
        exp = row(r, E2)["raw_required_experience"]
        assert exp["engine_use"] == "UNKNOWN" and row(r, E2)["engine_use"] == "UNKNOWN"


def test_substantiating_value_must_sit_in_the_same_merged_cell(tree):
    # row 1 prints "No Experience required"; a non-empty cell between it and row 2 breaks the merged cell
    tree.elig.insert(1, dict(tree.elig[0], s_no="9", raw_required_experience="2 years"))
    tree.elig[0]["raw_required_experience"] = "No Experience required"
    with pytest.raises(EvidenceError, match=r"OV-002: the value 'No Experience required' is not printed on the cited "
                                             r"source page, so the cited evidence cannot substantiate the correction"):
        tree.build(approve=["OV-002"])
