# Legacy test baseline — 2026-10-31

**Suite:** `data_extraction/test_reconcile_2026-10-30.py` (frozen legacy suite; never edited)
**Result:** **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline).**
**This is not a passing suite.** The single failure is an unresolved source-data conflict. It has not been accepted, waived or marked `xfail`.

| Item | Value |
|---|---|
| Recorded on | 2026-10-31 |
| Environment | Project `.venv`: Python 3.12.5, pytest 9.2.0, installed from `requirements-lock.txt` |
| Command | `.\.venv\Scripts\python.exe -B -I -m pytest -p no:cacheprovider data_extraction/test_reconcile_2026-10-30.py` |
| Earlier observation | The same 23/1 result with the global pytest 8.4.2 (2026-10-31, read-only inspection) |
| Checker | [`tools/check_legacy_baseline.py`](../../tools/check_legacy_baseline.py) |

## 1. The failing test

| Field | Value |
|---|---|
| Identifier | `data_extraction/test_reconcile_2026-10-30.py::test_credit_sums_equal_item10[AMH/Q2301]` |
| Assertion (first line, exact) | `AssertionError: assert 12.0 == 14.0` |
| Actual (left) | `12.0`: the sum of the `credits` cells of the Specialized Sewing Machine Operator QF NOS rows in `qf_nos.csv` |
| Expected (right) | `14.0`: QF item 10 credits in `qualifications.csv` |
| What the test checks | The QF NOS-table credit cells must sum to the QF item 10 credit total |
| Finding | **DQ-01** (ARCHITECTURE.md §8.6). Status: **UNRESOLVED_SOURCE_CONFLICT** |

## 2. The source discrepancy

All values below are from the extraction outputs and the audit overlay. Nothing was re-extracted for this record.

| Value | Source (manifest item) | Page | Extraction status | Overlay |
|---|---|---|---|---|
| Bridge module row: credit cell empty | SSMO QF (A5) | 5 | TRANSCRIBED | OV-035: one printed value covers bridge + AMH/N2301 |
| AMH/N2301 row: `5` | SSMO QF (A5) | 5 | **PARSED_UNCERTAIN** (merged credit cell) | OV-035 |
| AMH/N2302 row: `3` | SSMO QF (A5) | 5 | TRANSCRIBED | OV-036: QF row value; geometry shows one clean glyph, not an extraction error |
| AMH/N0310, AMH/N0309, DGT/VSQ/N0102 rows: `1`, `1`, `2` | SSMO QF (A5) | 5 | TRANSCRIBED | — |
| **QF row sum = 12** | (derived) | — | — | — |
| QF NOS-table totals row: `14` | SSMO QF (A5) | 6 | TRANSCRIBED | OV-038 |
| QF item 10 credits: `14` | SSMO QF (A5) | 4 | TRANSCRIBED | OV-039 (agrees with the catalogue) |
| QP NOS Parameters, AMH/N2302 credits: `5` | SSMO QP (A4) | 14 | TRANSCRIBED | OV-037 |
| QP NOS Parameters, AMH/N2301 credits: `5` | SSMO QP (A4) | 10 | TRANSCRIBED | — |

Interpretation, as recorded by the audit (`AUDIT_NOTE.md` §A3, decision D1):

- There is a genuine **internal QF inconsistency**: the rows sum to 12 while the totals row and item 10 say 14.
- There is also a **QF–QP conflict** for AMH/N2302: QF 3 vs QP 5.
- With QP 5 for N2302, the rows would sum to 14. **This does not establish that 5 is correct, and no value is selected.**

Engine impact: credits are `NOT_USED`, so they never affect eligibility, hours or paths. DQ-01 therefore blocks no implementation task.

## 3. Exact baseline (authoritative, read by the checker)

<!-- BASELINE-JSON:BEGIN -->
```json
{
  "baseline_id": "legacy_tests_2026-10-31",
  "test_file": "data_extraction/test_reconcile_2026-10-30.py",
  "catalogue_file": "data/processed/acquisition_2026-10-30/approved_qualifications_parsed.csv",
  "extracted_dir": "data/processed/extracted_2026-10-30",
  "expected_counts": {"passed": 23, "failed": 1, "error": 0, "skipped": 0},
  "expected_failures": [
    {
      "name": "test_credit_sums_equal_item10[AMH/Q2301]",
      "finding": "DQ-01",
      "status": "UNRESOLVED",
      "assertion": "AssertionError: assert 12.0 == 14.0"
    }
  ],
  "expected_passes": [
    "test_outputs_exist_and_cover_four_qualifications",
    "test_hours_sums_equal_item13_totals[AMH/Q0301]",
    "test_hours_sums_equal_item13_totals[AMH/Q2301]",
    "test_hours_sums_equal_item13_totals[AMH/Q0103]",
    "test_hours_sums_equal_item13_totals[AMH/Q2101]",
    "test_credit_sums_equal_item10[AMH/Q0301]",
    "test_credit_sums_equal_item10[AMH/Q0103]",
    "test_credit_sums_equal_item10[AMH/Q2101]",
    "test_item10_equals_catalogue_credits[AMH/Q0301]",
    "test_item10_equals_catalogue_credits[AMH/Q2301]",
    "test_item10_equals_catalogue_credits[AMH/Q0103]",
    "test_item10_equals_catalogue_credits[AMH/Q2101]",
    "test_qp_and_qf_nos_code_sets_equal[AMH/Q0301]",
    "test_qp_and_qf_nos_code_sets_equal[AMH/Q2301]",
    "test_qp_and_qf_nos_code_sets_equal[AMH/Q0103]",
    "test_qp_and_qf_nos_code_sets_equal[AMH/Q2101]",
    "test_every_row_has_sha_and_page_unless_unresolved[facts.csv]",
    "test_every_row_has_sha_and_page_unless_unresolved[qualifications.csv]",
    "test_every_row_has_sha_and_page_unless_unresolved[qf_nos.csv]",
    "test_every_row_has_sha_and_page_unless_unresolved[qp_nos_headers.csv]",
    "test_every_row_has_sha_and_page_unless_unresolved[eligibility_rows.csv]",
    "test_every_row_has_sha_and_page_unless_unresolved[progression_claims.csv]",
    "test_no_email_or_phone_patterns_in_any_output"
  ],
  "inputs_sha256": {
    "data_extraction/test_reconcile_2026-10-30.py": "5875897341fa69f699cd34fde73d6a3130d7b65932f35d2f4e4adb8207bbf459",
    "data/processed/acquisition_2026-10-30/approved_qualifications_parsed.csv": "21a83b35c304370cabf61a507be8d3de51d629e201c6647968f229414039d1a3",
    "data/processed/extracted_2026-10-30/eligibility_rows.csv": "5af07ffbe4067f5944270dcf6c840a9f55284dd2ab84cf1bdba1ed3da1b62975",
    "data/processed/extracted_2026-10-30/facts.csv": "e7aedff05f3ee42675bae808c4de6701645148125725b2dc8ea8f32bdbcbd235",
    "data/processed/extracted_2026-10-30/progression_claims.csv": "40c0a47da5b6c252dd03c7915eb1a326ab2d50bce4a7e9c5e4ae769284659251",
    "data/processed/extracted_2026-10-30/qf_nos.csv": "001a9a3344b51ce35e4e866a1d84b47d1b0dad37a63d12fcb1c24f6b9c5b7317",
    "data/processed/extracted_2026-10-30/qp_nos_headers.csv": "b49682d10cf0da7ea214c95587b8e0728ea5a0b73da52da3fb7331c5a8be8060",
    "data/processed/extracted_2026-10-30/qualifications.csv": "f6f7490717ca1b4e2e3f081a9d030a58eadb96b05d40c636421cb668e572d317",
    "data/processed/extracted_2026-10-30/reconciliation.json": "9c0a0b5dea29a104215e7f6223025b7d922679318a466db7f65b1030623958d1",
    "data/processed/extracted_2026-10-30/RECONCILIATION_REPORT.md": "fd35bec088c088f8fe1db94205c01082fee2e2c5cb09914402882e511336b690"
  }
}
```
<!-- BASELINE-JSON:END -->

The hashes cover the test file and every local input the suite reads. They identify the files and reveal no content.

- **The test file is hashed with line endings normalised to LF.** It is versioned, and with `core.autocrlf=true` Git may check it out with CRLF without any change to its content.
- **The data files under `data/` are hashed as exact bytes.** They never pass through Git.

## 4. How the check works

`.\.venv\Scripts\python.exe -B tools\check_legacy_baseline.py` runs the suite **unmodified** in a subprocess and reads pytest's JUnit report. It then compares every test outcome, the first line of every failure message and every input hash with the block above.

| Exit | Meaning |
|---|---|
| `0` `MATCH` | Exactly the documented result. It prints: "…23 passed, 1 failed… This is a documented baseline, NOT a passing suite." |
| `1` `DEVIATION` | Any difference (see below) |
| `2` `ERROR` | pytest produced no report at all. A missing or unreadable suite that still produces a report fails closed as `DEVIATION`. |

| Deviation code | Detects |
|---|---|
| `UNEXPECTED_FAILED` / `UNEXPECTED_ERROR` / `UNEXPECTED_SKIPPED` | Any additional failure, error or skip |
| `ASSERTION_CHANGED` | A changed actual **or** expected value in the DQ-01 assertion |
| `BASELINE_FAILURE_MISSING` + `UNKNOWN_TEST` | A changed failure identifier (renamed or removed test) |
| `BASELINE_FAILURE_NO_LONGER_FAILS` | The original failure disappearing. Resolution review is required (§5). |
| `BASELINE_FAILURE_CHANGED_OUTCOME` | The DQ-01 test erroring or skipping instead of failing |
| `EXPECTED_TEST_MISSING`, `COUNTS_CHANGED` | Lost tests, or changed totals |
| `INPUT_CHANGED` | Any change to the test file or its inputs, even if the outcomes are unchanged |

A bare `xfail` was rejected. It would pass on *any* failure of that test, including a different one, and it would require editing the frozen legacy file.

`--self-test` copies the suite and its inputs to a temporary directory and mutates **the copies only**: scenarios S0–S5 in §6. The real files under `data/` are only read. `--print-observed` prints the observed result as JSON, for a reviewed re-baseline.

## 5. Resolution criteria for DQ-01

DQ-01 may be marked resolved, and this baseline replaced, only when **all** of the following hold:

1. **Authoritative evidence.** An official source, newer than or above the current QF/QP, states the AMH/N2302 credits and a consistent total. Examples: a corrected QF or QP version, or the NQR record for the qualification (acquisition item C3 currently returns HTTP 404). The source is acquired in a new, approved acquisition run with a manifest and hashes.
2. **Recorded decision.** You approve the resolution. It is recorded as a decision referencing the evidence.
3. **Non-destructive change.** The correction enters through a new extraction run or an approved overlay entry. The existing extraction CSVs, the overlay CSV and the legacy test are **never edited**.
4. **Reviewed re-baseline.** A new baseline document, `docs/baselines/legacy_tests_<date>.md`, is created from `--print-observed` output, with an explanation of every difference. The checker then returns `MATCH` against it.
5. **Register updated.** The DQ-01 entry in the new suite's known-deviations register (TASKS.md P1.6) is updated or closed in the same reviewed change.

A `BASELINE_FAILURE_NO_LONGER_FAILS` result **without** steps 1–5 is treated as a regression to investigate, never as a fix.

## 6. Verification record

The checker was run on 2026-10-31 in the project `.venv`. The outputs are recorded verbatim below.

<!-- VERIFICATION:BEGIN -->
```text
> .\.venv\Scripts\python.exe -B tools\check_legacy_baseline.py
MATCH with baseline legacy_tests_2026-10-31: 23 passed, 1 failed, 0 errors, 0 skipped (DQ-01 unresolved). This is a documented baseline, NOT a passing suite.
exit=0

> .\.venv\Scripts\python.exe -B tools\check_legacy_baseline.py --self-test
[ok] S0 unmodified copy: exit 0, detected none
[ok] S1 additional failure (SMO item 13 total 300 -> 301): exit 1, detected ['COUNTS_CHANGED', 'INPUT_CHANGED', 'UNEXPECTED_FAILED']
[ok] S2 changed actual value (SSMO N0310 credits 1 -> 2: sum 13): exit 1, detected ['ASSERTION_CHANGED', 'INPUT_CHANGED']
[ok] S3 changed expected value (SSMO item 10 and catalogue 14 -> 15): exit 1, detected ['ASSERTION_CHANGED', 'INPUT_CHANGED']
[ok] S4 failure disappears (SSMO N2302 credits 3 -> 5: sum 14): exit 1, detected ['BASELINE_FAILURE_NO_LONGER_FAILS', 'COUNTS_CHANGED', 'INPUT_CHANGED']
[ok] S5 changed failure identifier (test function renamed in the copy): exit 1, detected ['BASELINE_FAILURE_MISSING', 'EXPECTED_TEST_MISSING', 'INPUT_CHANGED', 'UNKNOWN_TEST']
SELF-TEST PASSED: every deviation class was detected.
exit=0
```

An additional manual probe ran the check against an empty directory, so the suite and its inputs were missing. pytest still wrote a report, so the check failed closed with `DEVIATION` (`BASELINE_FAILURE_MISSING`, `COUNTS_CHANGED`, `EXPECTED_TEST_MISSING`, `INPUT_CHANGED`), not `ERROR`. The `ERROR` exit (2) is reserved for a run that produces no report at all. That path was not triggered in this pass.

After the runs, the SHA-256 values of all real inputs still equal §3, and no `__pycache__` or `.pytest_cache` was created in the repository.

**Fresh-checkout simulation (2026-10-31).** The staged files were exported with `git checkout-index -a`, which applied `core.autocrlf`, so the test file had CRLF on all 97 lines. Only the suite's data inputs were copied in (the extraction folder and the catalogue). Then:

1. A new `.venv` was built from `requirements-lock.txt` with `--require-hashes`.
2. `pip check` reported "No broken requirements found."
3. The check reported `MATCH … 23 passed, 1 failed …`.
4. `--self-test` reported `SELF-TEST PASSED`.

The temporary copy was deleted afterwards. The line-ending normalisation of the test-file hash (§3) is what makes step 3 match on a CRLF checkout.
<!-- VERIFICATION:END -->
