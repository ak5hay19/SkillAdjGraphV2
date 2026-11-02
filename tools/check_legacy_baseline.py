"""Exact-baseline check for the frozen legacy reconciliation suite (data_extraction/test_reconcile_2026-10-30.py).

The legacy suite does not pass: it has one documented failure caused by an unresolved source conflict (DQ-01).
This tool runs the suite unmodified and compares the real result with the reviewed baseline embedded in
docs/baselines/legacy_tests_2026-10-31.md. Exit codes:

  0  MATCH      the result equals the documented baseline exactly (this is NOT a passing suite)
  1  DEVIATION  any difference: an additional failure, a changed or missing failure identifier, a changed
                assertion (actual or expected value), a baseline failure that now passes (resolution review
                required), errors, skips, unknown tests, or changed input/test-file hashes
  2  ERROR      pytest produced no report at all (a missing suite that still yields a report fails closed as 1)

Run with the project environment:  .venv\\Scripts\\python.exe -B tools\\check_legacy_baseline.py [--self-test]
--self-test copies the suite and its local inputs to a temporary directory, mutates the copies and verifies
that every deviation class is detected. Real data under data/ is only read, never modified.
"""
import argparse
import copy
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
BASELINE_DOC = REPO / "docs" / "baselines" / "legacy_tests_2026-10-31.md"
BLOCK = re.compile(r"<!-- BASELINE-JSON:BEGIN -->\s*```json\s*(.*?)\s*```\s*<!-- BASELINE-JSON:END -->", re.S)


def load_baseline(doc=BASELINE_DOC):
    m = BLOCK.search(doc.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"ERROR: no BASELINE-JSON block in {doc}")
    return json.loads(m.group(1))


def sha256(path, normalize_eol=False):
    data = Path(path).read_bytes()
    if normalize_eol:  # Git (core.autocrlf) may check the versioned test file out with CRLF; content is unchanged
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def input_hashes(root, baseline):
    """Hash the test file (EOL-normalised; it is versioned), the catalogue and every extraction file (exact bytes)."""
    out = {}
    for rel, eol in [(baseline["test_file"], True), (baseline["catalogue_file"], False)]:
        p = root / rel
        out[rel] = sha256(p, normalize_eol=eol) if p.is_file() else None
    ext = root / baseline["extracted_dir"]
    if ext.is_dir():
        for p in sorted(ext.iterdir()):
            if p.is_file():
                out[f"{baseline['extracted_dir']}/{p.name}"] = sha256(p)
    return out


def run_suite(root, baseline):
    """Run the unmodified suite in a subprocess; return {test name: (outcome, first message line)}."""
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        cmd = [sys.executable, "-B", "-I", "-m", "pytest", "-p", "no:cacheprovider", "-q", "-o", "addopts=",
               f"--junitxml={junit}", baseline["test_file"]]
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if not junit.is_file():
            raise RuntimeError(f"pytest produced no report (exit {proc.returncode}):\n{proc.stdout[-2000:]}{proc.stderr[-2000:]}")
        results = {}
        for case in ET.parse(junit).getroot().iter("testcase"):
            outcome, message = "passed", ""
            for tag in ("failure", "error", "skipped"):
                el = case.find(tag)
                if el is not None:
                    outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                    message = (el.get("message") or "").splitlines()[0] if el.get("message") else ""
                    break
            results[case.get("name")] = (outcome, message)
        return results


def compare(baseline, results, hashes):
    """Return a list of (code, detail) deviations; empty means an exact match."""
    dev = []
    expected_fail = {f["name"]: f for f in baseline["expected_failures"]}
    expected_pass = set(baseline["expected_passes"])
    for name, (outcome, message) in sorted(results.items()):
        if name in expected_fail:
            if outcome == "passed":
                dev.append(("BASELINE_FAILURE_NO_LONGER_FAILS",
                            f"{name} ({expected_fail[name]['finding']}) now passes: resolution review required before re-baselining"))
            elif outcome != "failed":
                dev.append(("BASELINE_FAILURE_CHANGED_OUTCOME", f"{name}: {outcome} ({message})"))
            elif message != expected_fail[name]["assertion"]:
                dev.append(("ASSERTION_CHANGED", f"{name}: expected '{expected_fail[name]['assertion']}', observed '{message}'"))
        elif name in expected_pass:
            if outcome != "passed":
                dev.append(("UNEXPECTED_" + outcome.upper(), f"{name}: {message}"))
        else:
            dev.append(("UNKNOWN_TEST", f"{name}: {outcome} {message}".rstrip()))
    for name in sorted(set(expected_fail) | expected_pass):
        if name not in results:
            code = "BASELINE_FAILURE_MISSING" if name in expected_fail else "EXPECTED_TEST_MISSING"
            dev.append((code, f"{name} was not reported (renamed, removed or not collected)"))
    counts = {k: sum(1 for o, _ in results.values() if o == k) for k in ("passed", "failed", "error", "skipped")}
    if counts != baseline["expected_counts"]:
        dev.append(("COUNTS_CHANGED", f"expected {baseline['expected_counts']}, observed {counts}"))
    for rel in sorted(set(baseline["inputs_sha256"]) | set(hashes)):
        if baseline["inputs_sha256"].get(rel) != hashes.get(rel):
            dev.append(("INPUT_CHANGED", f"{rel}: hash differs from baseline (or file added/missing)"))
    return dev, counts


def check(root=REPO, baseline=None, quiet=False):
    baseline = baseline or load_baseline()
    results = run_suite(root, baseline)
    dev, counts = compare(baseline, results, input_hashes(root, baseline))
    if not quiet:
        summary = f"{counts['passed']} passed, {counts['failed']} failed, {counts['error']} errors, {counts['skipped']} skipped"
        if dev:
            print(f"DEVIATION from baseline {baseline['baseline_id']} ({summary}):")
            for code, detail in dev:
                print(f"  - {code}: {detail}")
        else:
            findings = ", ".join(f"{f['finding']} {f['status'].lower()}" for f in baseline["expected_failures"])
            print(f"MATCH with baseline {baseline['baseline_id']}: {summary} ({findings}). "
                  "This is a documented baseline, NOT a passing suite.")
    return dev, results


# ---------------------------------------------------------------- self-test

def _edit_csv(path, match, field, value):
    """Rewrite one cell of a CSV copy (preserving BOM presence); raise if no row matched."""
    raw = path.read_bytes()
    enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    with open(path, encoding=enc, newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    hits = [r for r in rows if all(r.get(k) == v for k, v in match.items())]
    if len(hits) != 1:
        raise RuntimeError(f"self-test mutation matched {len(hits)} rows in {path.name}: {match}")
    hits[0][field] = value
    with open(path, "w", encoding=enc, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def self_test():
    baseline = load_baseline()
    ext, cat, test = baseline["extracted_dir"], baseline["catalogue_file"], baseline["test_file"]
    q2301 = {"qp_code": "AMH/Q2301", "doc_type": "QF"}
    scenarios = [
        ("S0 unmodified copy", None, set(), 0),
        ("S1 additional failure (SMO item 13 total 300 -> 301)",
         lambda r: _edit_csv(r / ext / "qualifications.csv", {"qp_code": "AMH/Q0301", "doc_type": "QF"}, "hours_total", "301"),
         {"UNEXPECTED_FAILED", "INPUT_CHANGED"}, 1),
        ("S2 changed actual value (SSMO N0310 credits 1 -> 2: sum 13)",
         lambda r: _edit_csv(r / ext / "qf_nos.csv", {**q2301, "nos_code": "AMH/N0310"}, "credits", "2"),
         {"ASSERTION_CHANGED", "INPUT_CHANGED"}, 1),
        ("S3 changed expected value (SSMO item 10 and catalogue 14 -> 15)",
         lambda r: (_edit_csv(r / ext / "qualifications.csv", q2301, "credits", "15"),
                    _edit_csv(r / cat, {"qp_code": "AMH/Q2301"}, "credits", "15")),
         {"ASSERTION_CHANGED", "INPUT_CHANGED"}, 1),
        ("S4 failure disappears (SSMO N2302 credits 3 -> 5: sum 14)",
         lambda r: _edit_csv(r / ext / "qf_nos.csv", {**q2301, "nos_code": "AMH/N2302"}, "credits", "5"),
         {"BASELINE_FAILURE_NO_LONGER_FAILS", "INPUT_CHANGED"}, 1),
        ("S5 changed failure identifier (test function renamed in the copy)",
         lambda r: (r / test).write_text((r / test).read_text(encoding="utf-8").replace(
             "def test_credit_sums_equal_item10", "def test_credit_sums_match_item10"), encoding="utf-8"),
         {"BASELINE_FAILURE_MISSING", "UNKNOWN_TEST", "INPUT_CHANGED"}, 1),
    ]
    ok = True
    for label, mutate, must_include, want_exit in scenarios:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (test, cat):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO / rel, root / rel)
            shutil.copytree(REPO / ext, root / ext)
            if mutate:
                mutate(root)
            dev, _ = check(root, copy.deepcopy(baseline), quiet=True)
            codes = {c for c, _ in dev}
            got_exit = 1 if dev else 0
            passed = must_include <= codes and got_exit == want_exit and (want_exit == 1 or not codes)
            ok &= passed
            print(f"[{'ok' if passed else 'FAILED'}] {label}: exit {got_exit}, detected {sorted(codes) or 'none'}")
    print("SELF-TEST PASSED: every deviation class was detected." if ok else "SELF-TEST FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true", help="verify detection on mutated temporary copies")
    ap.add_argument("--print-observed", action="store_true", help="print the observed result as JSON (for a reviewed re-baseline)")
    args = ap.parse_args()
    try:
        if args.self_test:
            return self_test()
        baseline = load_baseline()
        if args.print_observed:
            results = run_suite(REPO, baseline)
            print(json.dumps({"results": {k: list(v) for k, v in results.items()},
                              "inputs_sha256": input_hashes(REPO, baseline)}, indent=2))
            return 0
        dev, _ = check(REPO, baseline)
        return 1 if dev else 0
    except (RuntimeError, OSError) as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
