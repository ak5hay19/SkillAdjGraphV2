"""The known-deviations rule over the real build (TASKS P1.6). No xfail, no tolerance: the register must match exactly."""
import copy

import pytest

from skillgraph.curation.validate import (
    compare_deviations,
    cross_document_discrepancies,
    load_deviations,
    validate,
)

pytestmark = pytest.mark.requires_local_data


def _check(report, name):
    return next(c for c in report["checks"] if c["name"] == name)


def test_register_matches_real_observations_exactly(real_inputs):
    found = cross_document_discrepancies(real_inputs)
    assert compare_deviations(found, load_deviations()) == []
    assert {(d.check, d.subject) for d in found} == {d.key for d in load_deviations()}


def test_dq01_observed_values_are_the_recorded_ones(real_inputs):
    found = {(d.check, d.subject): d.observed for d in cross_document_discrepancies(real_inputs)}
    assert found[("qf_nos_credit_sum_vs_item10", "AMH/Q2301")] == {
        "row_sum": 12, "item10": 14, "totals_row": 14, "qf_N2302": 3, "qp_N2302": 5}


def test_real_report_passes_because_the_register_matches(build_dir, settings, real_inputs):
    report = validate(build_dir, settings, inputs=real_inputs)
    assert report["checks_failed"] == 0, [c for c in report["checks"] if c["status"] == "FAIL"]
    assert report["deviation_problems"] == []
    assert all(d["matches_observation"] and d["status"] == "UNRESOLVED" for d in report["known_deviations"])
    assert report["legacy_baseline"]["result"] == "23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)"
    assert report["legacy_baseline"]["is_passing_suite"] is False


# Synthetic-fixture tests: the real tables are mutated in memory (never on disk) to cause each failure.


def _mutated(real_inputs, table, match, field, value):
    inp = copy.deepcopy(real_inputs)
    hit = [r for r in inp.tables[table] if all(r[k] == v for k, v in match.items())]
    assert len(hit) == 1, hit
    hit[0][field] = value
    return inp


def test_extra_discrepancy_fails(build_dir, settings, real_inputs):
    inp = _mutated(real_inputs, "qf_nos", {"qp_code": "AMH/Q0301", "doc_type": "QF", "s_no": "2"}, "credits", "9")
    report = validate(build_dir, settings, inputs=inp)
    kinds = {(p["kind"], p["check"]) for p in report["deviation_problems"]}
    assert ("UNREGISTERED", "qf_nos_credit_sum_vs_item10") in kinds
    assert _check(report, "qf_nos_credit_sum_vs_item10")["status"] == "FAIL"
    assert report["checks_failed"] >= 1


def test_changed_value_fails(build_dir, settings, real_inputs):
    inp = _mutated(real_inputs, "qp_nos_headers", {"qp_code": "AMH/Q2301", "nos_code": "AMH/N2302"}, "credits", "6")
    report = validate(build_dir, settings, inputs=inp)
    kinds = {(p["kind"], p["check"]) for p in report["deviation_problems"]}
    assert ("CHANGED_VALUES", "nos_credits_qf_vs_qp") in kinds
    assert _check(report, "nos_credits_qf_vs_qp")["status"] == "FAIL"


def test_vanished_discrepancy_fails_with_review_message(build_dir, settings, real_inputs):
    inp = _mutated(real_inputs, "qp_nos_headers", {"qp_code": "AMH/Q2301", "nos_code": "DGT/VSQ/N0102"}, "nsqf_level", "3.5")
    report = validate(build_dir, settings, inputs=inp)
    vanished = [p for p in report["deviation_problems"] if p["kind"] == "VANISHED"]
    assert [p["deviation_id"] for p in vanished] == ["KD-003"]
    assert "resolution review required: follow the baseline document section 5" in vanished[0]["message"]
    assert _check(report, "nos_level_qf_vs_qp")["status"] == "FAIL"


def test_audit_status_counts_difference_fails(build_dir, settings, real_inputs):
    inp = _mutated(real_inputs, "facts", {"qp_code": "AMH/Q0301", "doc_type": "QF", "field": "nsqf_level"},
                   "extraction_status", "PARSED_UNCERTAIN")
    assert _check(validate(build_dir, settings, inputs=inp), "audit_status_counts")["status"] == "FAIL"
