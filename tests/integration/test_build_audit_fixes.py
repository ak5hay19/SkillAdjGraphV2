"""Regression tests for the P1.4 audit findings L10, M5, M2 and M3 (synthetic tree; no restricted data needed)."""

import pytest
from synth_tree import QP, SHA1, SRC2, SHA2, Tree, a1_html, load, ov

from skillgraph.curation.catalogue_source import parse_a1
from skillgraph.curation.errors import BuildError, EvidenceError, TargetError
from skillgraph.curation.overlay import OverlayError
from skillgraph.model.eligibility import EligibilitySourceRow
from skillgraph.provenance.manifest import SourceIntegrityError
from pydantic import ValidationError

E1, E2 = f"rule:{QP}/E1", f"rule:{QP}/E2"


@pytest.fixture
def tree(tmp_path):
    return Tree(tmp_path)


def row(result, rid):
    return next(r for r in load(result, "eligibility_source_rows.json") if r["id"] == rid)


# ---- L10: every status upgrade is validated like an applied overlay --------------------------------------------------


def test_geometry_upgrade_gets_its_own_confirmation_evidence(tree):
    r = tree.build(approve=[])
    exp = row(r, E1)["raw_required_experience"]
    evidence = {e["id"]: e for e in load(r, "evidence.json")}
    ev = evidence[exp["evidence_id"]]
    assert exp["value_status"] == "CONFIRMED_BY_GEOMETRY" and ev["value_status"] == "CONFIRMED_BY_GEOMETRY"
    assert ev["method"] == "synthetic" and ev["method"] != "pdfplumber_words"  # the overlay's method, not the extraction's
    assert ev["location"] == "synthetic location" and ev["page"] == "3" and ev["overlay_ids"] == ["OV-001"]
    assert "extracted by pdfplumber_words, confirmed by synthetic" in ev["note"]
    # no separate evidence of the extraction is emitted for a cell whose evidence is the confirmation
    assert [e["id"] for e in evidence.values() if "raw_required_experience" in (e["note"] or "")
            and "eligibility_row|1" in (e["note"] or "")] == [ev["id"]]


def test_upgrade_citing_another_source_is_rejected(tree):
    tree.overlay[0].update(evidence_source_file=SRC2, evidence_sha256=SHA2)
    with pytest.raises(EvidenceError, match=r"OV-001: cites src:S2 but the target row comes from src:S1"):
        tree.build(approve=[])
    assert tree.installed() == []


def test_upgrade_citing_a_page_outside_the_row_is_rejected(tree):
    tree.overlay[0]["evidence_page"] = "4"  # the row is on page 3
    with pytest.raises(EvidenceError, match=r"OV-001: cited page 4 is not on the row's page 3"):
        tree.build(approve=[])


def test_upgrade_citing_a_nonexistent_page_is_rejected(tree):
    tree.elig[0]["page"] = "99"
    tree.overlay[0]["evidence_page"] = "99"
    with pytest.raises(EvidenceError, match=r"page 99 is beyond the 20 pages of src:S1"):
        tree.build(approve=[])


@pytest.mark.parametrize("field", ["evidence_location", "method", "evidence_page"])
def test_upgrade_without_location_method_or_page_is_rejected(tree, field):
    tree.overlay[0][field] = ""
    with pytest.raises(EvidenceError, match=rf"OV-001: an applied overlay row needs {field}"):
        tree.build(approve=[])


def test_corroborated_value_must_equal_the_extracted_value(tree):
    tree.overlay[0]["status"] = "CORROBORATED"
    tree.elig[0]["raw_required_experience"] = "No Experience at all"  # no longer what the overlay recorded
    with pytest.raises(TargetError, match=r"OV-001.*stale"):
        tree.build(approve=[])


def test_valid_corroboration_is_accepted(tree):
    tree.overlay[0]["status"] = "CORROBORATED"
    exp = row(tree.build(approve=[]), E1)["raw_required_experience"]
    assert exp["value_status"] == "CORROBORATED"


def test_a_second_upgrade_row_on_one_cell_is_rejected(tree):
    tree.overlay.append(ov("OV-008", f"{QP}|QF|eligibility_row|1", "raw_required_experience", "CORROBORATED",
                           "SAFE_HARD_RULE", src_val="No Experience required"))
    tree.curation["expected_overlay_rows"] = 8
    with pytest.raises(BuildError, match=r"more than one status upgrade \(OV-001, OV-008\)"):
        tree.build(approve=[])


# ---- M5: catalogue values are verified against A1; the title alias carries no unverified OFFICIAL claim -------------


def test_verified_catalogue_is_recorded(tree):
    r = tree.build(approve=[])
    assert r.manifest["unverified_inputs"] == ["raw/2026-10-30/VALIDATION.json"]
    assert r.manifest["verified_derived_inputs"] == ["processed/acquisition_2026-10-30/approved_qualifications_parsed.csv"]
    q = next(q for q in load(r, "qualifications.json") if q["code"] == "TST/Q0002")
    ev = {e["id"]: e for e in load(r, "evidence.json")}[q["credits"]["evidence_id"]]
    assert ev["method"] == "html_table_parse_verified" and ev["source_id"] == "src:A1"


@pytest.mark.parametrize("col,bad", [("qp_name", "Renamed"), ("qp_code", "TST/Q0009"), ("nqr_code", "QG-XX"),
                                     ("qp_version", "9"), ("nsqf_level", "5"), ("notional_hours", "12345"),
                                     ("credits", "999"), ("ccn", "7"), ("sno", "9")])
def test_tampered_catalogue_row_fails_the_build(tree, col, bad):
    tree.catalogue[2][col] = bad
    with pytest.raises(BuildError, match=r"the catalogue CSV does not match its source A1"):
        tree.build(approve=[])
    assert tree.installed() == []


def test_an_en_dash_is_compared_as_an_en_dash(tree):
    tree.catalogue[1]["qp_name"] = "Other - Role"  # ASCII hyphen instead of the A1 en dash
    with pytest.raises(BuildError, match=r"S\.No\. 2 qp_name: catalogue 'Other - Role' differs from A1 'Other – Role'"):
        tree.build(approve=[])


def test_row_missing_from_the_csv_or_from_a1_fails(tree):
    del tree.catalogue[2]
    tree.curation["expected_catalogue_only"] = 1
    with pytest.raises(BuildError, match=r"S\.No\. 3 \(TST/Q0003\) is in A1 but not in the catalogue CSV"):
        tree.build(approve=[])
    t2 = Tree(tree.root / "b")
    t2.set_a1(a1_html(t2.catalogue[:2]))
    with pytest.raises(BuildError, match=r"S\.No\. 3 \(TST/Q0003\) is not in A1"):
        t2.build(approve=[])


def test_duplicate_rows_fail(tree):
    tree.set_a1(a1_html(tree.catalogue + [tree.catalogue[0]]))
    with pytest.raises(BuildError, match=r"A1 lists S\.No\. 1 twice"):
        tree.build(approve=[])
    t2 = Tree(tree.root / "b")
    t2.catalogue.append(dict(t2.catalogue[0]))
    with pytest.raises(BuildError, match=r"the catalogue CSV lists S\.No\. 1 twice"):
        t2.build(approve=[])


@pytest.mark.parametrize("content,msg", [
    (b"<html><body>no table here</body></html>", r"A1 contains no qualification table"),
    (b"<table><tr><th>QP Code</th><th>S.No.</th></tr><tr><td>x</td><td>1</td></tr></table>", r"lacks the column"),
    (b"<table><tr><th>S.No.</th></tr></table>", r"A1 contains no qualification table"),
    (b"\xff\xfe\x00 not utf-8 \xc3(", r"A1 is not valid UTF-8"),
])
def test_unreadable_or_malformed_a1_fails(tree, content, msg):
    tree.set_a1(content)  # the hash is updated too, so source integrity passes and the content check is what fails
    with pytest.raises(BuildError, match=msg):
        tree.build(approve=[])
    assert tree.installed() == []


def test_a1_with_a_header_but_no_rows_or_short_rows_fails():
    head = "".join(f"<th>{h}</th>" for h in ["S.No.", "QP Name", "QP Code", "NQR Code", "QP Version", "NSQF Level",
                                            "Notional Hours", "Credits", "CCN"])
    with pytest.raises(BuildError, match=r"no data rows"):
        parse_a1(f"<table><tr>{head}</tr></table>".encode())
    with pytest.raises(BuildError, match=r"has 2 cells, expected 9"):
        parse_a1(f"<table><tr>{head}</tr><tr><td>1</td><td>x</td></tr></table>".encode())


def test_tampered_a1_bytes_fail_source_integrity_before_the_content_check(tree):
    tree.write()
    page = tree.raw / "catalogue" / "page.html"
    page.write_bytes(page.read_bytes().replace(b"Third Role", b"Third Rolf"))
    from skillgraph.curation import build as build_mod
    with pytest.raises(SourceIntegrityError):
        build_mod.build(tree.settings(), approvals_path=tree.approvals, config_path=tree.config, out_root=tree.out)
    assert tree.installed() == []


def alias(tree):
    tree.curation["title_aliases"] = [{"qualification": QP, "kind": "qp", "title": "Alias Title", "source_item": "S1",
                                       "validation_item": "S1", "location": "cover"}]
    tree.validation["items"] = {"S1": {"snippets": ["Alias Title QP Code: TST/Q0001"], "transport": {"sha256": SHA1}}}


def test_title_alias_is_flagged_unverified_and_has_no_official_evidence(tree):
    alias(tree)
    r = tree.build(approve=[])
    q = load(r, "qualifications.json")[0]
    assert q["titles"]["qp"] == "Alias Title"
    (f,) = [f for f in q["quality_flags"] if f["code"] == "TITLE_VARIANT"]
    assert f["refs"] == ["src:S1"] and f["severity"] == "CAUTION" and "not independently verified" in f["message"]
    assert not [e for e in load(r, "evidence.json") if e["method"] == "qp_cover_snippet"]


def test_tampered_validation_snippet_or_hash_fails(tree):
    alias(tree)
    tree.validation["items"]["S1"]["snippets"] = ["Something else entirely"]
    with pytest.raises(EvidenceError, match=r"alias 'Alias Title' is not in VALIDATION\.json items\.S1"):
        tree.build(approve=[])
    t2 = Tree(tree.root / "b")
    alias(t2)
    t2.validation["items"]["S1"]["transport"]["sha256"] = "f" * 64
    with pytest.raises(EvidenceError, match=r"describes a different file than src:S1"):
        t2.build(approve=[])


# ---- M2: a row is never safer than its own row-level component -------------------------------------------------------


def test_row_level_use_ignores_a_field_level_decision_and_keeps_it_as_an_audit_hint(tree):
    r = tree.build(approve=[])
    e1 = row(r, E1)
    assert e1["raw_required_experience"]["engine_use"] == "SAFE_HARD_RULE"  # the cell keeps its own classification
    assert e1["raw_academic_or_skill"]["engine_use"] == "UNKNOWN" and e1["raw_row_text"]["engine_use"] == "UNKNOWN"
    assert e1["engine_use"] == "UNKNOWN" and e1["extraction_status"] == "PARSED_UNCERTAIN"
    assert [(h["overlay_id"], h["field"], h["engine_use"]) for h in e1["audit_hints"]] == [
        ("OV-001", "raw_required_experience", "SAFE_HARD_RULE")]
    # the age row's own component is its row-level component, so it keeps its safe use and has no hint
    age = row(r, f"rule:{QP}/AGE")
    assert age["engine_use"] == "SAFE_HARD_RULE" and age["audit_hints"] == []
    assert row(r, E2)["engine_use"] == "UNKNOWN"


def test_a_decision_on_the_row_text_still_sets_the_row_level_use(tree):
    tree.elig[0]["extraction_status"] = "TRANSCRIBED"  # a substantiated row
    tree.overlay.append(ov("OV-008", f"{QP}|QF|eligibility_row|1", "raw_row_text", "INTERPRETATION_DECIDED",
                           "CONDITIONAL_ON_DECLARED_RELEVANCE", src_val="11th Grade pass | No Experience required"))
    tree.curation["expected_overlay_rows"] = 8
    e1 = row(tree.build(approve=[]), E1)
    assert e1["engine_use"] == "CONDITIONAL_ON_DECLARED_RELEVANCE" == e1["raw_row_text"]["engine_use"]
    assert e1["raw_academic_or_skill"]["engine_use"] == "UNKNOWN"  # no field becomes usable through the row decision
    assert [h["overlay_id"] for h in e1["audit_hints"]] == ["OV-001"]


def test_a_computing_decision_on_an_uncertain_row_text_fails_the_build(tree):
    # E1 is PARSED_UNCERTAIN: an overlay decision on its row text (or on the experience cell) cannot make it computing
    tree.overlay.append(ov("OV-008", f"{QP}|QF|eligibility_row|1", "raw_row_text", "INTERPRETATION_DECIDED",
                           "CONDITIONAL_ON_DECLARED_RELEVANCE", src_val="11th Grade pass | No Experience required"))
    tree.curation["expected_overlay_rows"] = 8
    with pytest.raises(BuildError, match=rf"{QP}\|QF\|eligibility_row\|1: eligibility row refused: .*requires a substantiated row"):
        tree.build(approve=[])
    assert tree.installed() == []


@pytest.mark.parametrize("use", ["SAFE_HARD_RULE", "SAFE_WITH_CONSTRAINT", "CONDITIONAL_ON_DECLARED_RELEVANCE"])
def test_the_model_rejects_a_row_safer_than_its_component(tree, use):
    e1 = row(tree.build(approve=[]), E1)
    e1["engine_use"] = use
    with pytest.raises(ValidationError, match=r"cannot be safer than the row's own row-level component"):
        EligibilitySourceRow.model_validate(e1)
    age = row(tree.build(approve=[]), f"rule:{QP}/AGE")
    age["min_age"]["engine_use"] = "UNKNOWN"
    with pytest.raises(ValidationError, match=r"cannot be safer than the row's own row-level component"):
        EligibilitySourceRow.model_validate(age)


def test_no_row_is_safer_than_its_component_anywhere(tree):
    r = tree.build(approve=["OV-002"])
    for rw in load(r, "eligibility_source_rows.json"):
        comp = rw["min_age"] if rw["kind"] == "AGE_9C" else rw["raw_row_text"]
        if rw["engine_use"] not in ("UNKNOWN", "DISPLAY_ONLY", "NOT_USED"):
            assert comp["engine_use"] == rw["engine_use"], rw["id"]


# ---- M3: OV-033-style NO_OFFICIAL_RELATIONSHIP rows are recorded only ------------------------------------------------


def test_no_official_relationship_is_recorded_only(tree):
    r = tree.build(approve=[])
    (claim,) = load(r, "qualifications.json")[0]["progression_claims"]
    assert claim["resolved_target"] is None and claim["engine_use"] == "DISPLAY_ONLY"
    assert r.manifest["overlay_effects"]["OV-007"] == {"classification": "IGNORE", "effect": "NO_RELATIONSHIP_ASSERTED"}
    assert r.manifest["overlays"]["applied"] == []
    with pytest.raises(OverlayError, match="not a proposal"):
        tree.build(approve=["OV-007"])  # it can never be approved into an effect


# ---- engine_constraint reaches the curated row, verbatim and separate --------------------------------------------


def test_constraints_are_carried_verbatim_and_never_alter_engine_use(tree):
    wording = "education >= '8th grade pass'; experience_years >= 1.0; relevance is a user declaration, not verified"
    tree.elig[0]["extraction_status"] = "TRANSCRIBED"
    tree.overlay[0]["engine_constraint"] = "experience_years = 0"
    tree.overlay.append(ov("OV-008", f"{QP}|QF|eligibility_row|1", "raw_row_text", "INTERPRETATION_DECIDED",
                           "CONDITIONAL_ON_DECLARED_RELEVANCE", src_val="11th Grade pass | No Experience required"))
    tree.overlay[-1]["engine_constraint"] = wording
    tree.curation["expected_overlay_rows"] = 8
    r = tree.build(approve=[])
    e1, e2, age = row(r, E1), row(r, E2), row(r, f"rule:{QP}/AGE")
    assert e1["engine_constraint"] == wording and e1["engine_use"] == "CONDITIONAL_ON_DECLARED_RELEVANCE"
    assert e2["engine_constraint"] is None  # OV-004 states none; nothing is invented
    assert age["engine_constraint"] is None and age["engine_use"] == "SAFE_HARD_RULE"
    # a field-level constraint stays an audit hint and is not the row's wording
    assert [(h["overlay_id"], h["engine_constraint"]) for h in e1["audit_hints"]] == [("OV-001", "experience_years = 0")]


def test_two_different_constraints_on_one_row_decision_are_refused(tree):
    tree.elig[0]["extraction_status"] = "TRANSCRIBED"
    for oid, text in (("OV-008", "one wording"), ("OV-009", "another wording")):
        tree.overlay.append(ov(oid, f"{QP}|QF|eligibility_row|1", "raw_row_text", "INTERPRETATION_DECIDED",
                               "CONDITIONAL_ON_DECLARED_RELEVANCE", src_val="11th Grade pass | No Experience required"))
        tree.overlay[-1]["engine_constraint"] = text
    tree.curation["expected_overlay_rows"] = 9
    with pytest.raises(BuildError, match="overlay rows give different engine_constraint texts"):
        tree.build(approve=[])


def test_safe_with_constraint_without_its_wording_fails_the_build(tree):
    tree.elig[0]["extraction_status"] = "TRANSCRIBED"
    tree.overlay.append(ov("OV-008", f"{QP}|QF|eligibility_row|1", "raw_row_text", "INTERPRETATION_DECIDED",
                           "SAFE_WITH_CONSTRAINT", src_val="11th Grade pass | No Experience required"))
    tree.curation["expected_overlay_rows"] = 8
    with pytest.raises(BuildError, match="SAFE_WITH_CONSTRAINT requires the engine_constraint"):
        tree.build(approve=[])
