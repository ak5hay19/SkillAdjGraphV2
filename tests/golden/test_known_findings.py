"""DQ-01..DQ-15 are asserted present, with their recorded status (TASKS P1.6)."""
import pytest

from skillgraph.curation.validate import load_findings, validate

pytestmark = pytest.mark.requires_local_data

EXPECTED_STATUS = {
    "DQ-01": "UNRESOLVED_SOURCE_CONFLICT", "DQ-02": "UNRESOLVED_SOURCE_CONFLICT",
    "DQ-03": "UNRESOLVED_LEAD_SOURCE_UNAVAILABLE", "DQ-04": "NOT_FOUND",
}


@pytest.fixture(scope="module")
def report(build_dir, settings, real_inputs):
    return validate(build_dir, settings, inputs=real_inputs)


def test_all_fifteen_findings_are_reported(report):
    assert [f["id"] for f in report["known_findings"]] == [f"DQ-{i:02d}" for i in range(1, 16)]


def test_recorded_statuses(report):
    by = {f["id"]: f for f in report["known_findings"]}
    for dq, status in EXPECTED_STATUS.items():
        assert by[dq]["status"] == status
    assert {by[d]["status"] for d in ("DQ-07", "DQ-12")} == {"PENDING_APPROVAL"}


def test_no_finding_is_marked_resolved_or_accepted(report):
    forbidden = {"RESOLVED", "ACCEPTED", "WAIVED", "PASSED", "OK"}
    assert not [f for f in report["known_findings"] if f["status"] in forbidden]


def test_every_testable_finding_is_present_in_the_build(report):
    for f in report["known_findings"]:
        assert f["verification"] in ("PRESENT", "NOT_MACHINE_CHECKED"), f
    unchecked = {f["id"] for f in report["known_findings"] if f["verification"] == "NOT_MACHINE_CHECKED"}
    assert unchecked == {"DQ-10", "DQ-13"}  # honest: no curated record exists to test these two


def test_unavailable_sources_and_pending_overlays(report):
    ids = {u["manifest_item_id"] for u in report["sources_unavailable"]}
    assert {"C3", "C4", "D1"} <= ids
    assert report["overlays"]["applied"] == []
    assert {"OV-002", "OV-003", "OV-004"} <= set(report["overlays"]["pending"])


def test_findings_register_is_complete_and_ordered():
    specs, counts = load_findings()
    assert [s.id for s in specs] == [f"DQ-{i:02d}" for i in range(1, 16)]
    assert counts["AMH/Q2301"] == (49, 8)
