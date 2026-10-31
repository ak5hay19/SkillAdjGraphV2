"""P1.3 overlay approval mechanism on synthetic overlays (no restricted data, no real provenance)."""
import csv
from pathlib import Path

import pytest

from skillgraph.curation.overlay import (
    OVERLAY_COLUMNS,
    Approval,
    OverlayClass,
    OverlayError,
    OverlayStatus,
    classify,
    load_approvals,
    load_overlay,
    load_plan,
    resolve_field,
)
from skillgraph.model.evidence import QualityFlagCode, ValueStatus

FILE, KEY, FIELD = "eligibility_rows.csv", "ZZZ/Q0001|QF|eligibility_row|2", "raw_required_experience"


def row(oid, status, **kw):
    base = dict(
        overlay_id=oid, category="CORRECTION_PROPOSED", qp_code="ZZZ/Q0001", target_file=FILE,
        target_row_key=KEY, target_field=FIELD, source_value="", overlay_value="synthetic value",
        status=status, engine_use="UNKNOWN",
    )
    base.update(kw)
    return base


def write_overlay(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[*OVERLAY_COLUMNS, "rationale"])
        w.writeheader()
        for r in rows:
            w.writerow({"rationale": "synthetic", **r})
    return path


def ap(oid, **kw):
    return Approval(**{"overlay_id": oid, "approved_by": "tester", "approved_on": "2026-01-01", **kw})


@pytest.fixture
def rows(tmp_path):
    p = write_overlay(tmp_path / "o.csv", [
        row("OV-001", "PROPOSED_CORRECTION"),
        row("OV-002", "PROPOSED_CORRECTION", target_row_key="ZZZ/Q0001|QF|eligibility_row|3"),
        row("OV-003", "PROPOSED_REPRESENTATION", target_file="qf_nos.csv", target_field="credits",
            source_value="bridge=''; N='4'", overlay_value="credit_group: one value"),
        row("OV-004", "INTERPRETATION_DECIDED", engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE"),
        row("OV-005", "SUPPORTING_EVIDENCE_ONLY", engine_use="DISPLAY_ONLY"),
        row("OV-006", "NO_OFFICIAL_RELATIONSHIP", engine_use="NOT_USED"),
    ])
    return load_overlay(p)


def test_empty_approvals_leave_proposals_pending_and_change_nothing(rows):
    plan = classify(rows, [])
    assert plan.ids(OverlayClass.PENDING) == ["OV-001", "OV-002", "OV-003"]
    assert plan.ids(OverlayClass.APPLY) == []
    f = resolve_field(plan, FILE, KEY, FIELD, "", ValueStatus.PARSED_UNCERTAIN)
    assert (f.value, f.source_value, f.value_status) == ("", "", ValueStatus.PARSED_UNCERTAIN)
    assert f.overlay_ids == () and f.pending_overlay_ids == ("OV-001",)
    assert f.quality_flags == (QualityFlagCode.OVERLAY_PENDING_APPROVAL,)


def test_every_status_classified_once(rows):
    plan = classify(rows, [])
    assert plan.ids(OverlayClass.INTERPRET) == ["OV-004"]
    assert plan.ids(OverlayClass.DISPLAY) == ["OV-005"]
    assert plan.ids(OverlayClass.IGNORE) == ["OV-006"]
    assert sum(plan.counts().values()) == len(rows)


def test_approved_correction_applies_and_keeps_source_value(rows):
    plan = classify(rows, [ap("OV-001")])
    assert plan.ids(OverlayClass.APPLY) == ["OV-001"] and "OV-001" not in plan.ids(OverlayClass.PENDING)
    f = resolve_field(plan, FILE, KEY, FIELD, "", ValueStatus.PARSED_UNCERTAIN)
    assert f.value == "synthetic value" and f.source_value == ""
    assert f.value_status is ValueStatus.CORRECTION_APPLIED
    assert f.overlay_ids == ("OV-001",) and f.pending_overlay_ids == () and f.quality_flags == ()


def test_approving_one_does_not_apply_another(rows):
    plan = classify(rows, [ap("OV-001")])
    other = resolve_field(plan, FILE, "ZZZ/Q0001|QF|eligibility_row|3", FIELD, "", None)
    assert other.value == "" and other.pending_overlay_ids == ("OV-002",)


def test_approved_representation_never_replaces_a_value(rows):
    plan = classify(rows, [ap("OV-003")])
    assert plan.get("OV-003").classification is OverlayClass.APPLY
    f = resolve_field(plan, "qf_nos.csv", KEY, "credits", "bridge=''; N='4'", ValueStatus.TRANSCRIBED)
    assert f.value == "bridge=''; N='4'" and f.value_status is ValueStatus.TRANSCRIBED
    assert f.overlay_ids == ("OV-003",)


def test_approving_missing_id_fails(rows):
    with pytest.raises(OverlayError, match=r"OV-099 does not exist"):
        classify(rows, [ap("OV-099")])


@pytest.mark.parametrize("oid", ["OV-004", "OV-005", "OV-006"])
def test_approving_a_non_proposal_fails(rows, oid):
    with pytest.raises(OverlayError, match="not a proposal"):
        classify(rows, [ap(oid)])


def test_duplicate_approval_fails(rows):
    with pytest.raises(OverlayError, match="more than once"):
        classify(rows, [ap("OV-001"), ap("OV-001")])


def test_stale_overlay_source_value_fails(rows):
    plan = classify(rows, [ap("OV-001")])
    with pytest.raises(OverlayError, match="stale"):
        resolve_field(plan, FILE, KEY, FIELD, "something else", None)


def test_approved_correction_with_empty_value_fails(tmp_path):
    p = write_overlay(tmp_path / "o.csv", [row("OV-001", "PROPOSED_CORRECTION", overlay_value="  ")])
    plan = classify(load_overlay(p), [ap("OV-001")])
    with pytest.raises(OverlayError, match="empty overlay_value"):
        resolve_field(plan, FILE, KEY, FIELD, "", None)


def test_two_approved_corrections_on_one_field_fail(tmp_path):
    p = write_overlay(tmp_path / "o.csv", [row("OV-001", "PROPOSED_CORRECTION"), row("OV-002", "PROPOSED_CORRECTION")])
    plan = classify(load_overlay(p), [ap("OV-001"), ap("OV-002")])
    with pytest.raises(OverlayError, match="more than one"):
        resolve_field(plan, FILE, KEY, FIELD, "", None)


# ---- malformed overlay -------------------------------------------------------------------------------------------


def test_unknown_status_is_an_error_not_a_guess(tmp_path):
    p = write_overlay(tmp_path / "o.csv", [row("OV-001", "SOMETHING_NEW")])
    with pytest.raises(OverlayError, match="status"):
        load_overlay(p)


def test_unknown_engine_use_is_an_error(tmp_path):
    p = write_overlay(tmp_path / "o.csv", [row("OV-001", "PROPOSED_CORRECTION", engine_use="SAFE_ISH")])
    with pytest.raises(OverlayError, match="engine_use"):
        load_overlay(p)


def test_bad_overlay_id_duplicate_id_missing_file_empty_and_missing_column(tmp_path):
    with pytest.raises(OverlayError, match="overlay_id"):
        load_overlay(write_overlay(tmp_path / "a.csv", [row("OV-1", "PROPOSED_CORRECTION")]))
    with pytest.raises(OverlayError, match="duplicate"):
        load_overlay(write_overlay(tmp_path / "b.csv", [row("OV-001", "UNRESOLVED"), row("OV-001", "UNRESOLVED")]))
    with pytest.raises(OverlayError, match="cannot read"):
        load_overlay(tmp_path / "missing.csv")
    with pytest.raises(OverlayError, match="no overlay rows"):
        load_overlay(write_overlay(tmp_path / "c.csv", []))
    (tmp_path / "d.csv").write_text("overlay_id,status\nOV-001,UNRESOLVED\n", encoding="utf-8")
    with pytest.raises(OverlayError, match="missing column"):
        load_overlay(tmp_path / "d.csv")


def test_short_row_is_malformed(tmp_path):
    p = write_overlay(tmp_path / "o.csv", [row("OV-001", "UNRESOLVED")])
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text(lines[0] + "\nOV-001,CAT\n", encoding="utf-8")
    with pytest.raises(OverlayError, match="columns"):
        load_overlay(p)


# ---- approvals file ----------------------------------------------------------------------------------------------


def approvals_file(tmp_path, text):
    p = tmp_path / "a.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_empty_approved_list_loads_with_digest(tmp_path):
    approved, digest = load_approvals(approvals_file(tmp_path, "approved: []\n"))
    assert approved == [] and digest.startswith("sha256:") and len(digest) == 71


def test_valid_approval_parses_yaml_date(tmp_path):
    text = "approved:\n  - overlay_id: OV-002\n    approved_by: Someone\n    approved_on: 2026-11-01\n    note: ok\n"
    (a,), _ = load_approvals(approvals_file(tmp_path, text))
    assert a.overlay_id == "OV-002" and a.approved_on.isoformat() == "2026-11-01"


@pytest.mark.parametrize(
    "text",
    [
        "",  # empty file
        "approved:\n",  # null, not a list
        "approved: yes\n",
        "- OV-002\n",  # not a mapping
        "approved: []\nextra: 1\n",  # unknown key
        "approved: [{overlay_id: OV-002, approved_by: '', approved_on: 2026-01-01}]\n",  # blank approver
        "approved: [{overlay_id: OV-002, approved_by: x, approved_on: not-a-date}]\n",
        "approved: [{overlay_id: OV-002, approved_by: x}]\n",  # missing date
        "approved: [{overlay_id: ov-2, approved_by: x, approved_on: 2026-01-01}]\n",  # bad id
        "approved: [{overlay_id: OV-002, approved_by: x, approved_on: 2026-01-01, junk: 1}]\n",
        "approved: [{overlay_id: OV-002, approved_by: x, approved_on: 2026-01-01},"
        " {overlay_id: OV-002, approved_by: y, approved_on: 2026-01-02}]\n",  # duplicate
        "approved: [unclosed\n",  # invalid YAML
    ],
)
def test_malformed_approvals_fail(tmp_path, text):
    with pytest.raises(OverlayError):
        load_approvals(approvals_file(tmp_path, text))


def test_missing_approvals_file_is_not_treated_as_empty(tmp_path):
    with pytest.raises(OverlayError, match="cannot read approvals"):
        load_approvals(tmp_path / "nope.yaml")


def test_load_plan_end_to_end_and_files_unmodified(tmp_path):
    o = write_overlay(tmp_path / "o.csv", [row("OV-001", "PROPOSED_CORRECTION")])
    a = approvals_file(tmp_path, "approved:\n  - {overlay_id: OV-001, approved_by: x, approved_on: 2026-01-01}\n")
    before = (o.read_bytes(), a.read_bytes())
    plan = load_plan(o, a)
    assert plan.ids(OverlayClass.APPLY) == ["OV-001"]
    assert (o.read_bytes(), a.read_bytes()) == before
    assert {p.name for p in tmp_path.iterdir()} == {"o.csv", "a.yaml"}


def test_status_enum_matches_audit_note_table():
    expected = {
        "PROPOSED_CORRECTION", "CONFIRMED_BY_GEOMETRY", "INTERPRETATION_DECIDED", "UNRESOLVED",
        "UNRESOLVED_SOURCE_CONFLICT", "REVIEW_FLAG", "SOURCE_NUMBERING_GAP", "PARSED_UNCERTAIN_RETAINED",
        "CORROBORATED", "PROPOSED_REPRESENTATION", "SUPPORTING_EVIDENCE_ONLY", "NO_OFFICIAL_RELATIONSHIP",
    }
    assert {s.value for s in OverlayStatus} == expected
