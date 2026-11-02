"""`python -m skillgraph build`: exit codes and stdout/stderr contract (TASKS P1.4).

Real-data cases run the CLI in a subprocess against a private copy of the data tree (SKILLGRAPH_DATA_ROOT), so the
repository's own data/ and config/overlay_approvals.yaml are never written.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from skillgraph import cli
from skillgraph.curation.config import ConfigError
from skillgraph.curation.errors import BuildError
from skillgraph.curation.overlay import OverlayError
from skillgraph.provenance.manifest import SourceIntegrityError, check_sources

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
needs_data = pytest.mark.skipif(not (DATA / "raw" / "2026-10-30" / "MANIFEST.csv").is_file(), reason="local data not found")


def run_cli(root: Path, **env) -> subprocess.CompletedProcess:
    e = {**os.environ, "SKILLGRAPH_DATA_ROOT": str(root), **env}
    return subprocess.run([sys.executable, "-m", "skillgraph", "build"], capture_output=True, text=True, cwd=REPO, env=e)


@pytest.fixture
def private_data(tmp_path):
    root = tmp_path / "data"
    for d in ("raw", "processed"):
        shutil.copytree(DATA / d, root / d)
    return root


@needs_data
def test_build_succeeds_and_installs_a_complete_build(private_data):
    approvals = (REPO / "config/overlay_approvals.yaml").read_bytes()
    out = run_cli(private_data)
    assert out.returncode == 0, out.stderr
    manifest = json.loads(out.stdout)
    assert manifest["status"] == "READY" and manifest["overlays"]["applied"] == []
    built = private_data / "curated" / manifest["data_build_id"]
    assert (built / "build_manifest.json").is_file() and (built / "qualifications.json").is_file()
    assert (REPO / "config/overlay_approvals.yaml").read_bytes() == approvals  # the build never writes the approvals
    again = run_cli(private_data)
    assert again.returncode == 0 and json.loads(again.stdout)["data_build_id"] == manifest["data_build_id"]


@needs_data
def test_tampered_source_exits_1_with_the_full_report_and_no_output(private_data):
    pdf = next((private_data / "raw" / "2026-10-30" / "amhssc" / "qf").glob("*.pdf"))
    pdf.write_bytes(pdf.read_bytes() + b"\0")
    out = run_cli(private_data)
    assert out.returncode == 1
    assert "SourceIntegrityError" in out.stderr and json.loads(out.stdout)["ok"] is False
    assert not (private_data / "curated").exists() or not list((private_data / "curated").iterdir())


@needs_data
def test_altered_extraction_hash_reference_exits_1(private_data):
    p = private_data / "processed" / "extracted_2026-10-30" / "facts.csv"
    p.write_bytes(p.read_bytes().replace(b"607d1b38", b"707d1b38", 1))
    out = run_cli(private_data)
    assert out.returncode == 1 and "SourceIntegrityError" in out.stderr
    assert not (private_data / "curated").exists()


@needs_data
def test_stale_or_missing_overlay_target_exits_1(private_data):
    p = private_data / "processed" / "extracted_2026-10-30" / "eligibility_rows.csv"
    text = p.read_text(encoding="utf-8-sig")
    p.write_text(text.replace("AMH/Q2301,QG-3.5-AP-01871-2024-V1.1-AMHSSC,QF,eligibility_row,2,", "AMH/Q2301,QG-3.5-AP-01871-2024-V1.1-AMHSSC,QF,eligibility_row,22,", 1),
                 encoding="utf-8")
    out = run_cli(private_data)
    assert out.returncode == 1 and "TargetError" in out.stderr and out.stdout == ""
    assert not (private_data / "curated").exists()


def test_unreadable_settings_exit_3_with_empty_stdout(tmp_path):
    out = run_cli(tmp_path, SKILLGRAPH_CONFIG=str(tmp_path / "missing.yaml"))
    assert out.returncode == 3 and out.stdout == "" and "invalid settings" in out.stderr


def test_missing_inputs_fail_the_integrity_check_without_a_traceback(tmp_path):
    # Like verify-sources, a check that cannot run is a failed check (exit 1 with the report), never skipped.
    out = run_cli(tmp_path / "empty")
    assert out.returncode == 1 and "Traceback" not in out.stderr and "SourceIntegrityError" in out.stderr
    report = json.loads(out.stdout)
    assert report["ok"] is False and report["errors"]
    assert not (tmp_path / "empty" / "curated").exists()


@pytest.mark.parametrize(("exc", "code", "name"), [
    (BuildError("x"), 1, "BuildError"), (OverlayError("OV-999 does not exist"), 1, "OverlayError"),
    (ConfigError("bad"), 3, "cannot run"), (PermissionError("denied"), 3, "cannot run"),
])
def test_error_mapping(monkeypatch, capsys, exc, code, name):
    def boom(_settings):
        raise exc
    monkeypatch.setattr(cli, "build", boom)
    assert cli.main(["build"]) == code
    captured = capsys.readouterr()
    assert name in captured.err and captured.out == ""


def test_integrity_error_prints_report(monkeypatch, capsys, tmp_path):
    report = check_sources(tmp_path / "none.csv", tmp_path, tmp_path, tmp_path / "none2.csv")

    def boom(_settings):
        raise SourceIntegrityError("broken", report)
    monkeypatch.setattr(cli, "build", boom)
    assert cli.main(["build"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["ok"] is False and "SourceIntegrityError" in captured.err


def test_build_is_registered_as_implemented():
    assert "build" in cli.IMPLEMENTED
