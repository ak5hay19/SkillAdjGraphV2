# Skill Adjacency Graph

*The shortest feasible path from a declining job*. Skillathon 2026.

An evidence-first tool for exploring transitions between vocational qualifications. For a **hypothetical** worker profile, it evaluates:

- eligibility, against official Qualification File rules (`MET` / `NOT_MET` / `UNKNOWN` / `CONDITIONAL`);
- official training hours;
- documented skill-unit (NOS) overlap;
- multi-step paths.

Every value carries its evidence class and source. A path is a reading of entry rules, **not** a prediction of employability, placement or earnings. The pilot covers four AMHSSC garment-sector qualifications. A Karnataka labour-market module is gated on a data feasibility check.

## Status (2026-10-31)

| Area | State |
|---|---|
| Planning | Approved baseline: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`API_SPEC.md`](API_SPEC.md), [`TASKS.md`](TASKS.md) |
| Repository foundation | Done on branch `chore/repo-foundation`, committed in `fbdc28f` ([TASKS P0.1](TASKS.md#p01--repository-hygiene--must--done-fbdc28f)) |
| Python environment | Done: isolated `.venv` from a hashed lock ([TASKS P0.2](TASKS.md#p02--dependency-specification-lock-and-venv--must--done)) |
| Application foundation | Package skeleton, settings, logging and CLI stubs committed in `63a83dd` (P0.3). Test infrastructure (P0.4) is verified, commit pending. **No business logic yet.** The next task is TASKS P1.1. |
| Legacy test baseline | **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**. This is not a passing suite. See [`docs/baselines/legacy_tests_2026-10-31.md`](docs/baselines/legacy_tests_2026-10-31.md). |
| Labour-market module (A) | Not assessed; the graph-only demo is the baseline plan |

## Documents

| Document | Authoritative for |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Design, data model, evidence and eligibility rules, known data issues (§8.6), decision register (§20.2) |
| [`API_SPEC.md`](API_SPEC.md) | The HTTP contract: endpoints, schemas, enums, errors |
| [`TASKS.md`](TASKS.md) | Task order, status, acceptance criteria, verification commands |
| [`docs/baselines/legacy_tests_2026-10-31.md`](docs/baselines/legacy_tests_2026-10-31.md) | The legacy test baseline and the DQ-01 resolution criteria |
| This README | Setup and verification commands |

## Repository layout

```text
ARCHITECTURE.md  API_SPEC.md  TASKS.md  README.md
pyproject.toml            dependency specification (direct pins)
requirements-lock.txt     complete hashed lock (generated, do not edit)
docs/baselines/           test baselines
tools/                    standalone repository tools (legacy baseline checker)
data_acquisition/         frozen 2026-10-30 acquisition script (research; do not run or edit)
data_extraction/          frozen 2026-10-30 extraction script + reconciliation tests (do not edit)
data/                     LOCAL ONLY, gitignored: raw sources, extraction outputs, audit overlay
src/skillgraph/           application package (foundation only: settings, logging, CLI stubs)
```

The planned package structure is in ARCHITECTURE §6.2.

## Data governance

- **`data/` never leaves this machine.** The raw source PDFs contain personal contact details. Reuse rights for the AMHSSC, NQR and DGE documents are unconfirmed (ARCHITECTURE §19). `.gitignore` excludes `data/`, source-document formats, secrets, keys, environments and caches.
- Stage files **by explicit path only**. Never use `git add -A` or `git add .`.
- The repository is **private**. The committed code and documents contain short official facts and public URLs, which were reviewed for the private repository only. Do not make the repository public until reuse rights are settled.

## Setup

Requirements:

- Windows with the `py` launcher and Python 3.12;
- network access to PyPI for the first install.

All commands run from the repository root in PowerShell. **Do not use global packages, and do not create the venv with `--system-site-packages`.** The global environment on the development machine is inconsistent (ARCHITECTURE RS-7).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --no-deps -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check        # must print: No broken requirements found.
```

Now that `src/skillgraph/` exists (P0.3), also install the project itself:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

On macOS/Linux the equivalent is `python3.12 -m venv .venv`, followed by `.venv/bin/python -m pip …`. The lock is universal, but only Windows has been verified.

### Changing dependencies

1. Edit the exact pins in `pyproject.toml`.
2. Regenerate the lock. This needs [uv](https://docs.astral.sh/uv/) 0.11 or later, and only for this step:

   ```powershell
   uv pip compile pyproject.toml --extra dev --extra analysis --universal --python-version 3.12 --generate-hashes --output-file requirements-lock.txt
   ```

3. Recreate `.venv` (delete it, then repeat Setup) and run `pip check`.
4. Check the locked versions for published advisories (for example at [osv.dev](https://osv.dev)).
5. Run all of § Verify.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B tools\check_legacy_baseline.py               # expect MATCH: 23 passed, 1 failed (DQ-01 unresolved)
.\.venv\Scripts\python.exe -B tools\check_legacy_baseline.py --self-test   # expect SELF-TEST PASSED
```

The baseline checker exits `0` only when the frozen legacy suite reproduces its documented result exactly. That result is **not** a passing suite. Any other outcome is a deviation (exit `1`) that must be investigated. A disappearing DQ-01 failure counts as a deviation too. The new test suite (`python -m pytest`) wraps this check in `tests/integration/test_legacy_baseline.py` (P0.4); that test passing means the baseline matched, not that the legacy suite passes.

To run the legacy suite directly:

```powershell
.\.venv\Scripts\python.exe -B -I -m pytest -p no:cacheprovider data_extraction/test_reconcile_2026-10-30.py
```

## Legacy research code

`data_acquisition/acquire_2026-10-30.py` and `data_extraction/extract_2026-10-30.py` produced the evidence under `data/` on 2026-10-30. They are kept for provenance and are **frozen**: do not modify or re-run them. Any new acquisition needs a separate, approved run (ARCHITECTURE §7).

Their recorded run environment was:

- acquisition: Python 3.12.5, httpx 0.28.1, pypdf 6.9.2, beautifulsoup4 4.14.3;
- extraction: pdfplumber 0.11.10.

These packages are deliberately not part of the project lock. The reconciliation tests in `data_extraction/` need only pytest. Use `tools/check_legacy_baseline.py` to run them against their baseline.
