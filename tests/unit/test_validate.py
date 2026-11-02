"""Pure tests of the known-deviations rule and the register loaders (no local data needed)."""
from pathlib import Path

import pytest

from skillgraph.curation.validate import (
    Deviation,
    Discrepancy,
    ValidationConfigError,
    compare_deviations,
    load_deviations,
    load_findings,
)


def dev(**kw):
    base = dict(id="KD-9", finding="DQ-99", check="c", subject="S", observed={"a": 1, "b": 2}, evidence={},
                status="UNRESOLVED", resolution_criteria="x")
    base.update(kw)
    return Deviation(**base)


def kinds(found, reg):
    return sorted(p.kind for p in compare_deviations(found, reg))


def test_exact_match_has_no_problem_and_numbers_compare_by_value():
    assert kinds([Discrepancy("c", "S", {"a": 1.0, "b": 2.0})], [dev()]) == []


def test_extra_changed_and_vanished():
    assert kinds([Discrepancy("c", "S", {"a": 1, "b": 2}), Discrepancy("c", "T", {"a": 1})], [dev()]) == ["UNREGISTERED"]
    assert kinds([Discrepancy("c", "S", {"a": 1, "b": 3})], [dev()]) == ["CHANGED_VALUES"]
    assert kinds([Discrepancy("c", "S", {"a": 1})], [dev()]) == ["CHANGED_VALUES"]  # a missing key is a change
    problems = compare_deviations([], [dev()])
    assert [p.kind for p in problems] == ["VANISHED"]
    assert "resolution review required: follow the baseline document section 5" in problems[0].message


def test_bool_is_not_a_number():
    assert kinds([Discrepancy("c", "S", {"a": True, "b": 2})], [dev()]) == ["CHANGED_VALUES"]


def test_duplicates_are_configuration_errors():
    with pytest.raises(ValidationConfigError):
        compare_deviations([], [dev(), dev(id="KD-10")])
    with pytest.raises(ValidationConfigError):
        compare_deviations([Discrepancy("c", "S", {}), Discrepancy("c", "S", {})], [dev()])


def test_repository_registers_load():
    devs = load_deviations()
    assert [d.id for d in devs] == ["KD-001", "KD-002", "KD-003"]
    assert all(d.status == "UNRESOLVED" for d in devs)
    assert next(d for d in devs if d.id == "KD-001").observed == {
        "row_sum": 12, "item10": 14, "totals_row": 14, "qf_N2302": 3, "qp_N2302": 5}
    specs, _ = load_findings()
    assert len(specs) == 15


def test_register_rejects_a_resolved_status_and_extra_keys(tmp_path: Path):
    good = Path("config/known_deviations.yaml").read_text(encoding="utf-8")
    p = tmp_path / "d.yaml"
    p.write_text(good.replace("status: UNRESOLVED", "status: RESOLVED", 1), encoding="utf-8")
    with pytest.raises(ValidationConfigError):
        load_deviations(p)
    p.write_text(good.replace("    status: UNRESOLVED\n", "    status: UNRESOLVED\n    waived: true\n", 1), encoding="utf-8")
    with pytest.raises(ValidationConfigError):
        load_deviations(p)
    p.write_text("deviations: []\nextra: 1\n", encoding="utf-8")
    with pytest.raises(ValidationConfigError):
        load_deviations(p)
