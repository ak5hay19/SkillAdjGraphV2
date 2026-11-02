"""Validation fails safely on stale, malformed or tampered inputs, and writes only its report (TASKS P1.6)."""
import copy
import shutil
from pathlib import Path

import pytest

from skillgraph.curation.validate import ValidationConfigError, load_findings, validate, write_report

pytestmark = pytest.mark.requires_local_data


def _status(report, name):
    return next(c for c in report["checks"] if c["name"] == name)["status"]


@pytest.fixture
def copy_of_build(build_dir, tmp_path):
    dst = tmp_path / build_dir.name
    shutil.copytree(build_dir, dst)
    return dst


def test_tampered_output_file_fails_output_hashes(copy_of_build, settings):
    f = copy_of_build / "conflicts.json"
    f.write_bytes(f.read_bytes() + b" ")
    assert _status(validate(copy_of_build, settings), "output_hashes") == "FAIL"


def test_stale_build_fails_when_a_recorded_input_changed(build_dir, settings, real_inputs):
    inp = copy.deepcopy(real_inputs)
    first = sorted(inp.build_manifest["input_files"])[0]
    inp.build_manifest["input_files"][first] = "0" * 64
    assert _status(validate(build_dir, settings, inputs=inp), "inputs_match_build") == "FAIL"


def test_unmodified_build_is_current(build_dir, settings, real_inputs):
    assert _status(validate(build_dir, settings, inputs=real_inputs), "inputs_match_build") == "PASS"


def test_malformed_manifest_raises_config_error(build_dir, settings, real_inputs):
    inp = copy.deepcopy(real_inputs)
    del inp.build_manifest["counts"]
    with pytest.raises(ValidationConfigError):
        validate(build_dir, settings, inputs=inp)


def test_non_numeric_cell_raises_config_error(build_dir, settings, real_inputs):
    inp = copy.deepcopy(real_inputs)
    next(r for r in inp.tables["qf_nos"] if r["doc_type"] == "QF" and r["credits"])["credits"] = "abc"
    with pytest.raises(ValidationConfigError):
        validate(build_dir, settings, inputs=inp)


def test_missing_build_manifest_is_refused(tmp_path, settings):
    with pytest.raises(ValidationConfigError):
        validate(tmp_path, settings)


def test_a_dropped_finding_is_refused(tmp_path):
    text = Path("config/known_findings.yaml").read_text(encoding="utf-8")
    p = tmp_path / "f.yaml"
    p.write_text("\n".join(line for line in text.splitlines() if not line.startswith("  - {id: DQ-07")) + "\n", encoding="utf-8")
    with pytest.raises(ValidationConfigError):
        load_findings(p)


def test_a_resolved_status_is_refused(tmp_path):
    text = Path("config/known_findings.yaml").read_text(encoding="utf-8")
    p = tmp_path / "f.yaml"
    p.write_text(text.replace("status: PENDING_APPROVAL", "status: APPROVED", 1), encoding="utf-8")
    with pytest.raises(ValidationConfigError):
        load_findings(p)


def test_report_is_deterministic_and_only_the_report_is_written(copy_of_build, settings):
    before = {p.name: p.read_bytes() for p in copy_of_build.iterdir() if p.name != "validation_report.json"}
    a = write_report(copy_of_build, validate(copy_of_build, settings)).read_bytes()
    b = write_report(copy_of_build, validate(copy_of_build, settings)).read_bytes()
    assert a == b
    after = {p.name: p.read_bytes() for p in copy_of_build.iterdir() if p.name != "validation_report.json"}
    assert before == after
    assert not (copy_of_build / "validation_report.json.tmp").exists()


def test_registered_deviations_never_become_resolved(build_dir, settings, real_inputs):
    report = validate(build_dir, settings, inputs=real_inputs)
    assert report["overlays"]["applied"] == []
    assert all(d["status"] == "UNRESOLVED" for d in report["known_deviations"])
    assert report["legacy_baseline"]["is_passing_suite"] is False
