"""P1.1 source integrity verifier. Tampering tests use synthetic trees in tmp_path; only the last section reads the
restricted local data, and it skips cleanly when that data is absent."""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from skillgraph.cli import main
from skillgraph.provenance.manifest import SourceIntegrityError, check_sources, verify_sources

REPO = Path(__file__).resolve().parents[2]
MANIFEST_COLS = ["item_id", "local_relative_path", "sha256", "validation_status"]
EXTRACT_COLS = ["qp_code", "source_file", "source_sha256", "extraction_status"]
OVERLAY_COLS = ["overlay_id", "evidence_source_file", "evidence_sha256"]

# Opaque bytes with PDF-like names: the verifier must hash them without ever parsing them.
FILES = {
    "amhssc/qp/one.pdf": b"%PDF-1.4 synthetic one \x00\xff\x10",
    "amhssc/qf/two.pdf": b"%PDF-1.4 synthetic two \x00\xfe\x11",
    "nqr/html/three.html": b"<html>synthetic three</html>",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def tree(tmp_path: Path) -> dict:
    """A data root laid out like data/: raw/2026-10-30, processed/extracted_2026-10-30, processed/audit_2026-10-30_m1s1."""
    raw = tmp_path / "raw" / "2026-10-30"
    for rel, data in FILES.items():
        (raw / rel).parent.mkdir(parents=True, exist_ok=True)
        (raw / rel).write_bytes(data)
    manifest_rows = [
        {"item_id": f"S{i}", "local_relative_path": f"data/raw/2026-10-30/{rel}", "sha256": sha(data),
         "validation_status": "PASS"}
        for i, (rel, data) in enumerate(FILES.items(), 1)
    ] + [
        # C3-like: a hash recorded from a failed fetch, no local file
        {"item_id": "C3", "local_relative_path": "", "sha256": sha(b"failed fetch"), "validation_status": "FAIL_HTTP"},
        {"item_id": "C4", "local_relative_path": "", "sha256": "", "validation_status": "NOT_FOUND"},
    ]
    write_csv(raw / "MANIFEST.csv", MANIFEST_COLS, manifest_rows)
    ext = tmp_path / "processed" / "extracted_2026-10-30"
    for name in ("facts.csv", "qualifications.csv"):
        write_csv(ext / name, EXTRACT_COLS, [
            {"qp_code": "Q1", "source_file": "amhssc/qp/one.pdf", "source_sha256": sha(FILES["amhssc/qp/one.pdf"]),
             "extraction_status": "TRANSCRIBED"},
            {"qp_code": "Q2", "source_file": "amhssc/qf/two.pdf", "source_sha256": sha(FILES["amhssc/qf/two.pdf"]),
             "extraction_status": "PARSED_UNCERTAIN"},
        ])
    overlay = tmp_path / "processed" / "audit_2026-10-30_m1s1" / "corrections_overlay.csv"
    write_csv(overlay, OVERLAY_COLS, [
        {"overlay_id": "OV-001", "evidence_source_file": "amhssc/qf/two.pdf",
         "evidence_sha256": sha(FILES["amhssc/qf/two.pdf"])},
    ])
    return {"root": tmp_path, "raw": raw, "manifest": raw / "MANIFEST.csv", "ext": ext, "overlay": overlay}


def run_check(t: dict):
    return check_sources(t["manifest"], t["raw"], t["ext"], t["overlay"])


def rewrite(path: Path, edit) -> None:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        cols, rows = list(reader.fieldnames), list(reader)
    edit(rows)
    write_csv(path, cols, rows)


@pytest.fixture
def cli_env(tree, monkeypatch):
    monkeypatch.setenv("SKILLGRAPH_DATA_ROOT", str(tree["root"]))
    monkeypatch.setenv("SKILLGRAPH_CONFIG", str(REPO / "config" / "default.yaml"))


# ---------------------------------------------------------------- the clean case

def test_clean_tree_passes_and_reports_non_local_items(tree):
    report = run_check(tree)
    assert report.ok and not report.errors
    assert (report.local_files_listed, report.local_files_matched, report.local_files_failed) == (3, 3, 0)
    non_local = {f.item_id: f.manifest_status for f in report.files if f.status == "NO_LOCAL_FILE"}
    assert non_local == {"C3": "FAIL_HTTP", "C4": "NOT_FOUND"}
    assert report.no_local_file == 2
    assert [c.checked for c in report.extraction] == [2, 2] and report.overlay.checked == 1


def test_verify_sources_returns_the_report_when_clean(tree):
    report = verify_sources(tree["manifest"], tree["raw"], tree["ext"], tree["overlay"])
    assert report.ok


def test_pdf_content_is_never_parsed(tree):
    run_check(tree)
    assert not {"pdfplumber", "pypdf", "pdfminer", "fitz"} & set(sys.modules)


def test_checks_do_not_modify_inputs(tree):
    paths = [p for p in tree["root"].rglob("*") if p.is_file()]
    before = {p: p.read_bytes() for p in paths}
    run_check(tree)
    assert {p: p.read_bytes() for p in paths} == before


# ---------------------------------------------------------------- tampering

def test_one_altered_byte_raises_source_integrity_error(tree):
    target = tree["raw"] / "amhssc/qp/one.pdf"
    data = bytearray(target.read_bytes())
    data[5] ^= 0x01
    target.write_bytes(bytes(data))
    with pytest.raises(SourceIntegrityError) as err:
        verify_sources(tree["manifest"], tree["raw"], tree["ext"], tree["overlay"])
    mismatch = [f for f in err.value.report.files if f.status == "MISMATCH"]
    assert [f.item_id for f in mismatch] == ["S1"]
    assert mismatch[0].actual_sha256 != mismatch[0].expected_sha256


def test_one_altered_byte_makes_the_cli_exit_nonzero(tree, cli_env, capsys):
    target = tree["raw"] / "nqr/html/three.html"
    target.write_bytes(target.read_bytes().replace(b"three", b"thrEe"))
    assert main(["verify-sources"]) == 1
    out = capsys.readouterr()
    assert "SourceIntegrityError" in out.err
    report = json.loads(out.out)  # the failing report is still printed in full
    assert report["ok"] is False and report["local_files_failed"] == 1


def test_missing_local_file_is_a_failure_unlike_a_non_local_item(tree):
    (tree["raw"] / "amhssc/qf/two.pdf").unlink()
    report = run_check(tree)
    assert not report.ok
    assert [f.item_id for f in report.files if f.status == "MISSING"] == ["S2"]


def test_manifest_path_escaping_the_raw_root_is_rejected(tree):
    rewrite(tree["manifest"], lambda rows: rows[0].update(
        local_relative_path="data/raw/2026-10-30/../../outside.pdf"))
    report = run_check(tree)
    assert not report.ok and report.files[0].status == "INVALID_PATH"


def test_malformed_manifest_hash_is_a_failure(tree):
    rewrite(tree["manifest"], lambda rows: rows[0].update(sha256="not-a-hash"))
    report = run_check(tree)
    assert not report.ok and report.files[0].status == "INVALID_HASH"


def test_duplicate_manifest_item_ids_are_a_failure(tree):
    rewrite(tree["manifest"], lambda rows: rows[1].update(item_id="S1"))
    report = run_check(tree)
    assert not report.ok and any("duplicated" in e for e in report.errors)


# ---------------------------------------------------------------- extraction references

def test_unmatched_extraction_hash_fails(tree):
    rewrite(tree["ext"] / "facts.csv", lambda rows: rows[0].update(source_sha256=sha(b"unknown")))
    report = run_check(tree)
    facts = next(c for c in report.extraction if c.file == "facts.csv")
    assert not report.ok and [p.row for p in facts.problems] == [2]


def test_hash_of_a_non_local_manifest_entry_does_not_resolve(tree):
    rewrite(tree["ext"] / "facts.csv", lambda rows: rows[0].update(source_sha256=sha(b"failed fetch")))
    assert not run_check(tree).ok


def test_unresolved_rows_are_excluded_and_counted(tree):
    rewrite(tree["ext"] / "facts.csv", lambda rows: rows[0].update(
        source_sha256="", source_file="", extraction_status="UNRESOLVED"))
    report = run_check(tree)
    facts = next(c for c in report.extraction if c.file == "facts.csv")
    assert report.ok and (facts.rows, facts.checked, facts.excluded_unresolved) == (2, 1, 1)


def test_empty_hash_without_unresolved_status_fails(tree):
    rewrite(tree["ext"] / "facts.csv", lambda rows: rows[0].update(source_sha256=""))
    assert not run_check(tree).ok


def test_source_file_must_agree_with_the_manifest_path(tree):
    rewrite(tree["ext"] / "facts.csv", lambda rows: rows[0].update(source_file="amhssc/qp/other.pdf"))
    report = run_check(tree)
    problem = next(c for c in report.extraction if c.file == "facts.csv").problems[0]
    assert not report.ok and "source_file" in problem.reason


# ---------------------------------------------------------------- overlay references

def test_overlay_unmatched_evidence_hash_fails(tree):
    rewrite(tree["overlay"], lambda rows: rows[0].update(evidence_sha256=sha(b"unknown")))
    report = run_check(tree)
    assert not report.ok and len(report.overlay.problems) == 1


def test_overlay_rows_have_no_unresolved_exemption(tree):
    rewrite(tree["overlay"], lambda rows: rows[0].update(evidence_sha256=""))
    assert not run_check(tree).ok


# ---------------------------------------------------------------- incomplete checks never pass

def test_missing_overlay_is_incomplete_not_ok(tree):
    tree["overlay"].unlink()
    report = run_check(tree)
    assert not report.ok and report.overlay is None and any("overlay" in e for e in report.errors)


def test_missing_extraction_csvs_is_incomplete_not_ok(tree):
    for p in tree["ext"].glob("*.csv"):
        p.unlink()
    report = run_check(tree)
    assert not report.ok and any("no extraction CSVs" in e for e in report.errors)


def test_missing_manifest_is_incomplete_not_ok(tree):
    tree["manifest"].unlink()
    with pytest.raises(SourceIntegrityError):
        verify_sources(tree["manifest"], tree["raw"], tree["ext"], tree["overlay"])


def test_extraction_csv_missing_a_required_column_is_incomplete(tree):
    write_csv(tree["ext"] / "facts.csv", ["qp_code"], [{"qp_code": "Q1"}])
    report = run_check(tree)
    assert not report.ok and any("missing column" in e for e in report.errors)


# ---------------------------------------------------------------- CLI

def test_cli_clean_tree_prints_report_json_and_exits_zero(tree, cli_env, capsys):
    assert main(["verify-sources"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True and report["local_files_matched"] == 3 and report["no_local_file"] == 2


def test_cli_bad_settings_exit_3(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SKILLGRAPH_CONFIG", str(tmp_path / "missing.yaml"))
    assert main(["verify-sources"]) == 3
    assert "settings file not found" in capsys.readouterr().err


def test_cli_incomplete_data_root_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SKILLGRAPH_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("SKILLGRAPH_CONFIG", str(REPO / "config" / "default.yaml"))
    assert main(["verify-sources"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_unknown_settings_key_exits_3_without_traceback(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("bogus_key: 1\n", encoding="utf-8")
    monkeypatch.setenv("SKILLGRAPH_CONFIG", str(bad))
    assert main(["verify-sources"]) == 3
    out = capsys.readouterr()
    assert out.out == "" and "invalid settings" in out.err and "bogus_key" in out.err
    assert "Traceback" not in out.err


def test_cli_settings_io_error_exits_3_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SKILLGRAPH_CONFIG", str(tmp_path))  # a directory: reading it raises OSError
    assert main(["verify-sources"]) == 3
    out = capsys.readouterr()
    assert out.out == "" and "invalid settings" in out.err and "Traceback" not in out.err


def test_integrity_failure_and_settings_error_have_different_exit_codes(tree, cli_env, monkeypatch, capsys):
    (tree["raw"] / "amhssc/qp/one.pdf").write_bytes(b"tampered")
    assert main(["verify-sources"]) == 1
    capsys.readouterr()
    monkeypatch.setenv("SKILLGRAPH_CONFIG", str(tree["root"] / "missing.yaml"))
    assert main(["verify-sources"]) == 3


# ---------------------------------------------------------------- duplicate content hashes

def test_two_manifest_paths_with_identical_bytes_both_resolve(tree):
    twin = tree["raw"] / "amhssc/qp/one_copy.pdf"
    twin.write_bytes(FILES["amhssc/qp/one.pdf"])
    shared = sha(FILES["amhssc/qp/one.pdf"])

    def add_entry(rows):
        rows.append({"item_id": "S1-copy", "local_relative_path": "data/raw/2026-10-30/amhssc/qp/one_copy.pdf",
                     "sha256": shared, "validation_status": "PASS"})
    rewrite(tree["manifest"], add_entry)
    rewrite(tree["ext"] / "facts.csv", lambda rows: rows[1].update(
        source_file="amhssc/qp/one_copy.pdf", source_sha256=shared))
    report = run_check(tree)
    assert report.ok and report.local_files_matched == 4


def test_shared_hash_does_not_excuse_a_wrong_source_file(tree):
    shared = sha(FILES["amhssc/qp/one.pdf"])
    (tree["raw"] / "amhssc/qp/one_copy.pdf").write_bytes(FILES["amhssc/qp/one.pdf"])
    rewrite(tree["manifest"], lambda rows: rows.append(
        {"item_id": "S1-copy", "local_relative_path": "data/raw/2026-10-30/amhssc/qp/one_copy.pdf",
         "sha256": shared, "validation_status": "PASS"}))
    rewrite(tree["ext"] / "facts.csv", lambda rows: rows[0].update(source_file="amhssc/qf/two.pdf"))
    report = run_check(tree)
    assert not report.ok and "source_file" in next(c for c in report.extraction if c.file == "facts.csv").problems[0].reason


# ---------------------------------------------------------------- empty required CSVs

def test_header_only_extraction_csv_is_incomplete(tree):
    write_csv(tree["ext"] / "facts.csv", EXTRACT_COLS, [])
    report = run_check(tree)
    assert not report.ok and any("facts.csv has no data rows" in e for e in report.errors)


def test_header_only_overlay_is_incomplete(tree):
    write_csv(tree["overlay"], OVERLAY_COLS, [])
    report = run_check(tree)
    assert not report.ok and any("corrections_overlay.csv has no data rows" in e for e in report.errors)


def test_header_only_input_makes_the_cli_exit_1_with_json(tree, cli_env, capsys):
    write_csv(tree["overlay"], OVERLAY_COLS, [])
    assert main(["verify-sources"]) == 1
    out = capsys.readouterr()
    assert json.loads(out.out)["ok"] is False and "SourceIntegrityError" in out.err


def test_non_empty_csv_of_only_unresolved_rows_is_not_rejected_as_empty(tree):
    def edit(rows):
        for r in rows:
            r.update(source_sha256="", source_file="", extraction_status="UNRESOLVED")
    rewrite(tree["ext"] / "facts.csv", edit)
    report = run_check(tree)
    assert report.ok and not report.errors


# ---------------------------------------------------------------- real local data (skipped when absent)

@pytest.mark.requires_local_data
def test_real_data_verifies(repo_data):
    raw = repo_data / "raw" / "2026-10-30"
    if not (raw / "MANIFEST.csv").is_file():
        pytest.skip("local manifest not found")
    report = verify_sources(raw / "MANIFEST.csv", raw)
    assert report.local_files_listed == report.local_files_matched == 18 and report.local_files_failed == 0
    non_local = {f.item_id: f.manifest_status for f in report.files if f.status == "NO_LOCAL_FILE"}
    assert non_local == {"C3": "FAIL_HTTP", "C4": "NOT_FOUND", "D1": "FAIL_HTTP", "D2": "NOT_FOUND"}
    assert sum(c.checked for c in report.extraction) == 265 and report.overlay.checked == 52
    assert not any(c.problems for c in report.extraction) and not report.overlay.problems


@pytest.mark.requires_local_data
def test_real_data_cli_in_a_subprocess(repo_data):
    proc = subprocess.run([sys.executable, "-m", "skillgraph", "verify-sources"], cwd=REPO,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
