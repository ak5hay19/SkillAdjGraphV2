"""P1.3 against the real audit overlay and extraction CSVs. Skips when the restricted data is absent.

Approvals used here are constructed in memory only: the committed ``config/overlay_approvals.yaml`` is the user's
decision (Q-2) and no test writes to it.
"""
import csv
import hashlib
from pathlib import Path

import pytest

from skillgraph.curation.overlay import (
    APPROVALS_PATH,
    Approval,
    OverlayClass,
    OverlayError,
    classify,
    load_approvals,
    load_overlay,
    load_plan,
    resolve_field,
)
from skillgraph.model.evidence import ValueStatus

REPO = Path(__file__).resolve().parents[2]
OVERLAY = REPO / "data/processed/audit_2026-10-30_m1s1/corrections_overlay.csv"
PROCESSED = REPO / "data/processed"
ELIGIBILITY = PROCESSED / "extracted_2026-10-30/eligibility_rows.csv"
PENDING_BY_Q2 = ["OV-002", "OV-003", "OV-004", "OV-034", "OV-035"]
EXP = "raw_required_experience"


@pytest.fixture(scope="module")
def real_data():
    if not (OVERLAY.is_file() and ELIGIBILITY.is_file()):
        pytest.skip("local overlay/extraction data not found")


def digests() -> dict[str, str]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PROCESSED.rglob("*.csv"))}


def ssmo_row(s_no: str) -> dict:
    with ELIGIBILITY.open(encoding="utf-8-sig", newline="") as fh:
        (r,) = [
            r for r in csv.DictReader(fh)
            if r["qp_code"] == "AMH/Q2301" and r["row_type"] == "eligibility_row" and r["s_no"] == s_no
        ]
    return r


def resolve_ssmo(plan, s_no):
    r = ssmo_row(s_no)
    key = f"AMH/Q2301|QF|eligibility_row|{s_no}"
    return resolve_field(plan, "eligibility_rows.csv", key, EXP, r[EXP], ValueStatus(r["extraction_status"]))


def approval(oid):
    return Approval(overlay_id=oid, approved_by="test-fixture", approved_on="2026-01-01")


def test_committed_approvals_file_is_empty_and_pending_rows_change_nothing(real_data):
    approved, _ = load_approvals(REPO / APPROVALS_PATH)
    assert approved == [], "approvals are the user's decision; revisit this test when Q-2 is answered"
    plan = load_plan(OVERLAY, REPO / APPROVALS_PATH)
    assert plan.ids(OverlayClass.PENDING) == PENDING_BY_Q2
    assert plan.ids(OverlayClass.APPLY) == []
    assert sum(plan.counts().values()) == 52
    for oid, s_no in (("OV-002", "2"), ("OV-003", "3"), ("OV-004", "4")):
        f = resolve_ssmo(plan, s_no)
        assert f.value == f.source_value == "" and f.value_status is ValueStatus.PARSED_UNCERTAIN
        assert f.pending_overlay_ids == (oid,) and f.overlay_ids == ()


def test_hypothetical_approval_of_ov002_applies_value_and_keeps_source(real_data):
    plan = classify(load_overlay(OVERLAY), [approval("OV-002")])
    assert plan.ids(OverlayClass.PENDING) == ["OV-003", "OV-004", "OV-034", "OV-035"]
    f = resolve_ssmo(plan, "2")
    assert f.value == "No Experience required"
    assert f.source_value == ""
    assert f.value_status is ValueStatus.CORRECTION_APPLIED
    assert f.overlay_ids == ("OV-002",)
    assert resolve_ssmo(plan, "3").value == ""  # rows 3 and 4 stay pending


def test_overlay_source_values_match_the_extraction(real_data):
    # Approving all three corrections raises "stale" if the overlay's recorded source_value drifted from the CSV.
    plan = classify(load_overlay(OVERLAY), [approval(o) for o in ("OV-002", "OV-003", "OV-004")])
    assert [resolve_ssmo(plan, n).value for n in "234"] == ["No Experience required"] * 3


def test_approving_a_nonexistent_or_non_proposal_id_fails_on_real_overlay(real_data):
    rows = load_overlay(OVERLAY)
    with pytest.raises(OverlayError, match="OV-999 does not exist"):
        classify(rows, [approval("OV-999")])
    with pytest.raises(OverlayError, match="not a proposal"):
        classify(rows, [approval("OV-001")])


def test_data_files_byte_identical_around_loading_and_applying(real_data):
    before = digests()
    assert len(before) >= 7
    plan = classify(load_overlay(OVERLAY), [approval("OV-002")])
    resolve_ssmo(plan, "2")
    load_plan(OVERLAY, REPO / APPROVALS_PATH)
    assert digests() == before
