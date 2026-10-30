# Skill Adjacency Graph — Implementation Plan (TASKS)

**Document status:** Approved baseline, 2026-10-31. Phase 0 is complete: P0.1–P0.5 are DONE, with evidence below (P0.1/P0.2/P0.5 `fbdc28f`, P0.3 `63a83dd`, P0.4 `33ac1cc`). The foundation package exists (settings, logging, CLI stubs) with **no business logic**. The next task is **P1.1** (§3).
**Authority:** this document is authoritative for task order, status and acceptance criteria. The other documents:

- design: [`ARCHITECTURE.md`](ARCHITECTURE.md);
- decisions: the register in ARCHITECTURE §20.2;
- HTTP contract: [`API_SPEC.md`](API_SPEC.md);
- setup commands: [`README.md`](README.md).

**Conventions:**

- **Priorities:**
  - **MUST:** required for a credible end-to-end demo.
  - **SHOULD:** strongly wanted; dropped only under time pressure.
  - **COULD:** only after all MUST items in the same phase are done.
  - **CONDITIONAL:** depends on the Module A gate.
- **Status:** **DONE** means verified, with the evidence recorded. TODO means not started.
- **`python` in commands** means the project interpreter `.\.venv\Scripts\python.exe`, or an activated `.venv`. The global interpreter is never used (ARCHITECTURE RS-7).
- **Effort figures** are rough ranges of focused working time, not commitments.

---

## 0. Decisions

All decisions are in the register in [ARCHITECTURE.md §20.2](ARCHITECTURE.md#202-decision-register-authoritative). This plan only references them.

- **Resolved in the foundation pass:** Q-1, Q-5, Q-9, Q-10, F-1, F-2, F-3.
- **Open:**

  | Decision | Affects |
  |---|---|
  | Q-2 | P1.3 |
  | Q-3 | P1.5, P3.2 |
  | Q-4 | P1.5 |
  | Q-6 | P2.1 |
  | Q-7 | Backlog B-1 |
  | Q-8 | Scheduling |

  **None blocks P0.3–P1.6.** Each open decision has a safe default that yields `UNKNOWN` or leaves a value unapplied.

---

## 1. Critical path and parallelism

```
P0 ──► P1 ──► P3 ──┬──► P4 ──┐
 │                 └──► P5 ──┴──► P6
 └──► P2 (time-boxed, parallel; its outcome only selects what P4.5/P5.6 show)
```

| Phase | Rough effort | Exit checkpoint |
|---|---|---|
| 0 Foundation | Done | P0.4 |
| 1 Evidence & curated build | 1.5–3 days | P1.6 |
| 2 Module A feasibility | 1–2 days + access wait | P2.5 (always) |
| 3 Engine | 2.5–4 days | P3.10 |
| 4 Analysis | 1–2 days | P4.6 |
| 5 API + dashboard | 2.5–4 days | P5.10 |
| 6 Validation & demo | 1–1.5 days | P6.6 |

**Graph-only fallback is the baseline plan.** Nothing on the critical path depends on Phase 2.

---

## Phase 0 — Repository and environment foundation

| Checkpoint | Priority | Status |
|---|---|---|
| P0.1 Repository hygiene | MUST | **DONE**: committed in `fbdc28f` |
| P0.2 Dependency specification, lock and `.venv` | MUST | **DONE** |
| P0.3 Package skeleton, configuration and logging | MUST | **DONE**: committed in `63a83dd` |
| P0.4 Test infrastructure | MUST | **DONE**: committed in `33ac1cc` |
| P0.5 Legacy test baseline check | MUST | **DONE** |

### P0.1 — Repository hygiene · MUST · DONE (`fbdc28f`)

- **Objective:** make the research code versionable without exposing data (ARCHITECTURE RS-1/RS-2/RS-3).
- **Done (2026-10-31):**
  1. **Read-only scan of the 3 legacy files.** There were 0 email, phone, credential, secret, token-value or user-path hits.
     - The "token" and "cookie" hits are NQR's public-form CSRF token, which is fetched at run time and stored only as a boolean.
     - The embedded official facts, public URLs and short phrases were reviewed and accepted for the private repository (ARCHITECTURE §19).
  2. **`.gitignore` changes:**
     - removed the PowerShell wrapper lines and `/data_*/`;
     - added `!/frontend/index.html` (F-3);
     - added `*.p12`, `*.pfx`, `*.egg-info/`, `.coverage`, `.coverage.*` and `htmlcov/`.
  3. **Branch and staging.** Created `chore/repo-foundation` from `main` (`3362d87`). Staged by explicit path only:
     - `.gitignore`, `README.md`, `ARCHITECTURE.md`, `API_SPEC.md`, `TASKS.md`;
     - `pyproject.toml`, `requirements-lock.txt`;
     - `docs/baselines/legacy_tests_2026-10-31.md`, `tools/check_legacy_baseline.py`;
     - `data_acquisition/acquire_2026-10-30.py`, `data_extraction/extract_2026-10-30.py`, `data_extraction/test_reconcile_2026-10-30.py`.
- **Acceptance criteria (verified):**
  - `git check-ignore -v data/raw/2026-10-30/MANIFEST.csv` matches `/data/`.
  - `git check-ignore` exits 1 for the three legacy files and for `frontend/index.html`.
  - `.gitignore` contains no `@'` or `Set-Content` line.
  - The staged set contains nothing under `data/` or `.venv/`, and no `.pdf`, `.csv` or `.html` file.
- **Committed:** `fbdc28f chore: establish project foundation` (together with the P0.2 and P0.5 files). Nothing is pushed.

### P0.2 — Dependency specification, lock and `.venv` · MUST · DONE

- **Deliverables:**
  - **`pyproject.toml`**, the authoritative dependency specification:
    - project `skillgraph` 0.1.0; `requires-python = ">=3.12,<3.13"`; classifier `Private :: Do Not Upload`;
    - runtime: `fastapi==0.162.0`, `uvicorn==0.34.0`, `pydantic==2.12.5`, `PyYAML==6.0.3`;
    - extras: `dev` = `pytest==9.2.0`, `httpx==0.28.1`; `analysis` = `pandas==2.3.1`;
    - build backend `setuptools==80.9.0`; `src/` layout.
  - **`requirements-lock.txt`**: 30 packages with SHA-256 hashes and universal environment markers, generated by uv. The exact command is in the file header.
  - **`.venv/`**: Python 3.12.5, `include-system-site-packages = false`. It is gitignored.
- **Decisions:** F-1 (pins changed because of advisories), F-2 (tooling). There is no `research` extra: the legacy scripts are frozen and never re-run ([README](README.md#legacy-research-code)).
- **Acceptance criteria (verified 2026-10-31):**
  - `pip install --require-hashes --no-deps -r requirements-lock.txt` succeeded.
  - `pip check` reports "No broken requirements found."
  - The venv contains exactly the 30 locked packages plus pip.
  - Global-only packages (streamlit, pdfplumber, networkx) are not importable from the venv.
  - An OSV query reports 0 advisories for the 30 locked packages.
  - The legacy baseline check reports MATCH (P0.5).
- **Deliberately not done here:** installing the project itself. `src/skillgraph/` is created in P0.3, so `import skillgraph` is a P0.3 criterion. This resolves the earlier ordering conflict.
- **Re-verification:** README § Setup and § Verify.

### P0.3 — Package skeleton, configuration and logging · MUST · DONE (`63a83dd`)

- **Objective:** the empty, correctly layered package from ARCHITECTURE §6.2, installed into `.venv`, with configuration and logging behaviour defined.
- **Prerequisites:** P0.2 (DONE). Committing P0.1 first is recommended, but it is not technically required.
- **Deliverables:**
  - `src/skillgraph/__init__.py` (`__version__ = "0.1.0"`), plus `__main__.py`, `cli.py`, `settings.py`, `logging_setup.py` and `services.py` (an empty façade class).
  - Empty subpackages, each with `__init__.py`: `model/`, `provenance/`, `curation/`, `registry/`, `eligibility/`, `graph/`, `explain/`, `analysis/`, `labour/`, `api/`.
  - `config/default.yaml`:
    - data paths relative to `SKILLGRAPH_DATA_ROOT`;
    - `engine.nsqf_level_match: null`;
    - `paths.max_steps_default: 3`, `paths.max_steps_limit: 4`, `paths.result_limit: 20`, `paths.max_expansions`;
    - `inference.enabled: false`;
    - `labour_market.config: config/labour_market.yaml`.
  - `config/labour_market.yaml` with `gate_decision: NOT_ASSESSED`.
  - `config/overlay_approvals.yaml` with `approved: []` and a schema comment.
  - `settings.py` reads `SKILLGRAPH_CONFIG` (default `config/default.yaml`) and `SKILLGRAPH_DATA_ROOT` (default `data/`), the only environment variables (ARCHITECTURE §17). It validates with Pydantic and rejects unknown keys.
  - `logging_setup.py`: JSON lines to stderr, with a helper that logs a profile only as its SHA-256 digest.
  - `cli.py`: the six commands from API_SPEC §4 (`verify-sources`, `build`, `validate`, `report`, `serve`, `check-repo-hygiene`). Each is a stub that exits with code 2 and prints "not implemented (P<n.n>)".
  - `tests/unit/test_settings.py` and `tests/unit/test_logging.py`.
- **Install step:** `python -m pip install --no-deps -e .`. Build isolation fetches the pinned `setuptools==80.9.0`, so network access is needed once. The `*.egg-info/` output is gitignored.
- **Acceptance criteria:**
  - `python -c "import skillgraph; print(skillgraph.__version__)"` prints `0.1.0`.
  - `python -m pip check` is still clean.
  - `python -m skillgraph --help` lists the six commands, and each stub exits with code 2 naming its checkpoint.
  - Defaults load; `SKILLGRAPH_CONFIG` overrides the file; an unknown key raises a validation error.
  - The logger emits JSON with `event` and `request_id` fields, and a test shows that logging a profile records only its digest.
  - No business logic exists yet: no curation, eligibility or graph code.
- **Verification:** `python -m pytest tests/unit/test_settings.py tests/unit/test_logging.py`.
- **Effort:** 2–4 h.
- **Status (verified 2026-10-31):** committed as `63a83dd feat: add application foundation and configuration`. `import skillgraph` prints `0.1.0`; `python -m skillgraph --help` lists the six commands; each stub exits 2 naming its checkpoint (P1.1, P1.4, P1.6, P4.6, P5.1, P6.3); the settings, logging and CLI unit tests pass.

### P0.4 — Test infrastructure · MUST · DONE (`33ac1cc`)

- **Objective:** test conventions that keep restricted data out of Git, make data-dependent tests skip cleanly, and bring the legacy baseline check into the normal suite **without** presenting the legacy suite as passing.
- **Prerequisites:** P0.3.
- **Deliverables:**
  - `[tool.pytest.ini_options]` in `pyproject.toml`: `testpaths = ["tests"]`; markers `requires_local_data` and `slow`; `addopts = "-p no:cacheprovider"`. The legacy suite stays outside `testpaths`.
  - `tests/conftest.py`:
    - a `local_data` fixture that skips when `$SKILLGRAPH_DATA_ROOT/processed/extracted_2026-10-30/` is absent;
    - a `repo_data` fixture that skips when the repository's own `data/` tree is absent. The baseline checker always reads `data/` under the repository root.
  - `tests/fixtures/synthetic/`: JSON/YAML only, because `*.csv` is gitignored. It uses fictional codes (`TEST/Q9001`, `TEST/N9001`) and has a README saying the fixtures are synthetic.
  - Directories `tests/unit/`, `tests/integration/` and `tests/golden/`.
  - `tests/integration/test_legacy_baseline.py` (`requires_local_data`). It runs `tools/check_legacy_baseline.py` and `tools/check_legacy_baseline.py --self-test` as subprocesses with `sys.executable`. It asserts exit code 0, that the output contains `MATCH` and `NOT a passing suite`, and that it contains `SELF-TEST PASSED`. On failure, it includes the checker output in the assertion message.
- **Acceptance criteria:**
  - `python -m pytest` passes. The legacy baseline test passes only because the documented 23/1 result matched.
  - With `SKILLGRAPH_DATA_ROOT` pointing to an empty directory, `local_data` tests are *skipped*, not *failed*.
  - With `data/` absent, the `repo_data` tests are skipped.
  - No `.pytest_cache` is created.
- **Verification:** `python -m pytest -q`; `python -m pytest -q -m requires_local_data`.
- **Effort:** 1–2 h.
- **Status (verified 2026-10-31):**
  - `python -m pytest -q`: 52 passed; with `-m "not requires_local_data"`: 50 passed, 2 deselected.
  - With `SKILLGRAPH_DATA_ROOT` pointing to an empty directory: 50 passed, 2 skipped.
  - No `.pytest_cache` is created.
  - The `repo_data` fixture's missing-`data/` skip is a plain directory check; it was not exercised by removing real data.
  - The baseline test passing means the documented 23 passed / 1 failed result matched (DQ-01 unresolved). It is not a passing legacy suite.
  - Committed as `33ac1cc test: add test infrastructure and complete phase 0 tracking`.

### P0.5 — Legacy test baseline check · MUST · DONE

- **Objective:** represent DQ-01 without hiding regressions and without presenting the legacy suite as passing (Q-5).
- **Deliverables:**
  - [`docs/baselines/legacy_tests_2026-10-31.md`](docs/baselines/legacy_tests_2026-10-31.md): the failing identifier, observed values, discrepancy, evidence and resolution criteria, plus the embedded machine-readable baseline.
  - [`tools/check_legacy_baseline.py`](tools/check_legacy_baseline.py): runs the unmodified suite, compares it with the baseline, and has a `--self-test`.
- **Acceptance criteria (verified 2026-10-31; output recorded in the baseline document §6):**
  - The check reports `MATCH … 23 passed, 1 failed … (DQ-01 unresolved) … NOT a passing suite` with exit 0.
  - The self-test matches the unmodified copy (S0), and detects:
    - an additional failure (S1);
    - a changed actual value (S2);
    - a changed expected value (S3);
    - the failure disappearing (S4, `BASELINE_FAILURE_NO_LONGER_FAILS`);
    - a changed identifier (S5).
  - The legacy test file and the real data hashes are unchanged.
- **Re-baselining** happens only through the baseline document §5, its resolution criteria.

**Phase 0 definition of done:**

- P0.1–P0.5 are complete, and P0.1 is committed. *(Verified 2026-10-31: P0.1/P0.2/P0.5 in `fbdc28f`, P0.3 in `63a83dd`; P0.4 in `33ac1cc`.)*
- `python -m pip check` is clean.
- `python -m pytest` passes.
- The legacy baseline check reports MATCH: 23 passed, 1 failed, DQ-01 unresolved.

---

## Phase 1 — Existing evidence and data-validation pipeline

No acquisition is repeated. Everything reads `data/raw/2026-10-30/`, `data/processed/extracted_2026-10-30/` and `data/processed/audit_2026-10-30_m1s1/`, and writes only under `data/curated/`.

### P1.1 — Source integrity verifier · MUST

- **Objective:** prove the evidence base is the one that was audited.
- **Dependencies:** P0.4.
- **Deliverables:**
  - `src/skillgraph/provenance/manifest.py`: parse `MANIFEST.csv`; re-hash every local file listed; verify that every `source_sha256` in the extraction CSVs and the overlay `evidence_sha256` refers to a manifest file with the same hash.
  - The `verify-sources` CLI command.
  - `IntegrityReport` (JSON to stdout plus an exit code).
- **Acceptance criteria:**
  - On the current data: every listed local file matches. Items without a local file (C3, C4, D1, D2 summary) are reported as `NO_LOCAL_FILE` with their manifest status, not as failures.
  - Every extraction row's `source_sha256` resolves, except rows with `extraction_status = UNRESOLVED`, mirroring the legacy test rule.
  - A synthetic fixture with one altered byte makes the command exit non-zero with `SourceIntegrityError`.
  - The command never opens PDF content. It hashes bytes only.
- **Verification:** `python -m skillgraph verify-sources`; `python -m pytest tests/integration/test_integrity.py`.
- **Definition of done:** integrity is checked automatically before every build.
- **Effort:** 2–4 h.

### P1.2 — Source-of-truth schemas · MUST

- **Objective:** Pydantic models for ARCHITECTURE §9.2, with the identifier rules of §9.1.
- **Dependencies:** P0.3.
- **Deliverables:** `src/skillgraph/model/{ids,evidence,qualification,eligibility,occupation,source,conflict}.py`; `docs/schemas.md`, generated from the models (SHOULD).
- **Acceptance criteria:**
  - An ID round-trip test passes: code → `id` → `slug` → registry lookup.
  - A slug collision raises.
  - `Valued` refuses an `OFFICIAL` value without `evidence_id`.
  - `EvidenceClass`, `Verdict`, `EngineUse` and `ValueStatus` enums exactly match `API_SPEC.md` §2.1, checked by a test that parses the spec's enum table.
  - No model has a field that treats credits as hours.
- **Verification:** `python -m pytest tests/unit/test_model_*.py`.
- **Effort:** 3–5 h.

### P1.3 — Overlay approval mechanism · MUST

- **Objective:** apply audit proposals only with your explicit approval (Q-2).
- **Dependencies:** P1.2.
- **Deliverables:** the `config/overlay_approvals.yaml` schema (`approved: [{overlay_id, approved_by, approved_on, note}]`); `src/skillgraph/curation/overlay.py`, which loads the overlay and classifies each row as `APPLY`, `INTERPRET`, `DISPLAY`, `PENDING` or `IGNORE` by `status` × approval.
- **Acceptance criteria:**
  - With an empty approvals file, OV-002…004 and OV-034/035 are `PENDING` and change no value.
  - When OV-002 is approved, the curated SSMO row 2 experience component holds the overlay value with `value_status = CORRECTION_APPLIED` and `overlay_ids = ["OV-002"]`, and the source value is still recorded.
  - Approving an ID that does not exist fails the build.
  - The extraction CSVs and the overlay CSV are byte-identical before and after a build. A test checks their hashes.
- **Effort:** 2–3 h.

### P1.4 — Curated build · MUST

- **Objective:** a deterministic, evidence-linked dataset (ARCHITECTURE §7 and §9).
- **Dependencies:** P1.1, P1.2, P1.3.
- **Deliverables:**
  - `src/skillgraph/curation/build.py`, which:
    - builds qualifications (primary QF, with the Inline Checker secondary copy as corroboration, DQ-06);
    - builds hours (item 13), NOS memberships and modules (bridge modules as `mod:` IDs), credits (`NOT_USED`), NCO occupations with `title_verification` from `VALIDATION.json`, and progression claims (`DISPLAY_ONLY`);
    - registers conflicts (DQ-01 as `conflict:OV-036`, DQ-02 as `conflict:OV-040`) and leads (DQ-03 as `UNRESOLVED_LEAD_SOURCE_UNAVAILABLE`);
    - builds the 33 `CATALOGUE_ONLY` records from `approved_qualifications_parsed.csv`;
    - creates evidence records and computes `data_build_id`.
  - The `build` CLI command.
  - Output in `data/curated/<build_id>/`.
- **Acceptance criteria:**
  - Running the build twice gives the same `data_build_id` and byte-identical JSON. `build_manifest.json` is excluded, because it holds the wall-clock time.
  - Every `OFFICIAL` value has an evidence record with source ID, SHA-256 and page.
  - Credits appear only with `engine_use = NOT_USED`.
  - The SSMO credit conflict and the DGT/VSQ/N0102 level conflict exist, with no selected value.
  - `nco:3122.3551` has `title = null` and `title_verification = NOT_FOUND`.
  - The QP title variant for AMH/Q0103 is kept as an alias (DQ-05).
  - The catalogue encoding artifact (row 27) is preserved and flagged, not "fixed".
  - The existing PII regexes find 0 hits in `data/curated/**`.
- **Verification:** `python -m skillgraph build`; `python -m pytest -m requires_local_data tests/integration/test_build.py`.
- **Definition of done:** the application can rely on `data/curated/` alone.
- **Effort:** 5–8 h.

### P1.5 — Eligibility rule structuring and human review file · MUST

- **Objective:** translate the 24 eligibility rows and 4 age rows into structured components (ARCHITECTURE §11.2), strictly following the overlay's `engine_use` and `engine_constraint` and decisions D2–D5.
- **Dependencies:** P1.4; Q-3 and Q-4 (defaults apply if undecided).
- **Deliverables:** `src/skillgraph/curation/eligibility_rules.py`; `data/curated/<build_id>/eligibility_rules_review.md`, a table per qualification with the verbatim row text → components → engine use → overlay IDs → unresolved parts.
- **Acceptance criteria:**
  - Each of the 24 rows maps to ≥ 1 component.
  - Rows with `engine_use = UNKNOWN` contain an `UNMODELLED` component with a reason code: SMO rows 2 and 5; SSMO rows 2–6.
  - Rows needing relevance carry `requires_relevance = true`.
  - Rows using "Level X" carry `PRIOR_NSQF_LEVEL` with no embedded interpretation.
  - "or equivalent" rows carry `or_equivalent = true`: PS rows 1 and 3.
  - SMO row 1 "Grade 9" is stored verbatim, with the decision D5 constraint.
  - SSMO row 5 is stored verbatim with `REVIEW_FLAG` (decision D4).
  - A test asserts that no component type exists for equivalence, exemption, RPL or reduced hours.
  - **You review `eligibility_rules_review.md` once.** Corrections go through config or the overlay, never through code constants.
- **Effort:** 4–6 h, plus your review time.

### P1.6 — Validation report, known-findings register and known-deviations tests · MUST

- **Objective:** an honest, machine-checkable statement of data quality that feeds E02. Every known source discrepancy is registered exactly; nothing is waived.
- **Dependencies:** P1.4, P1.5, P0.4.
- **Deliverables:**
  1. **`src/skillgraph/curation/validate.py`** and the `validate` CLI command, writing `validation_report.json`. It contains:
     - schema checks and referential integrity;
     - counts recomputed independently, which fixes the reporting issue DQ-11 without touching the legacy extractor;
     - the known-findings register DQ-01…DQ-15, with status;
     - the unavailable sources (C3, C4, D1);
     - the legacy baseline check result, quoted as "23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)".
  2. **`config/known_deviations.yaml`**, the known-deviations register.
     - **Scope:** one entry per source discrepancy that a validation check would otherwise report.
     - **Schema:** `id`; `finding` (DQ ID); `check` (validation check name); `subject` (qualification, NOS and field); `observed` (the exact recorded values); `evidence` (overlay IDs, source item, pages); `status` (`UNRESOLVED`); `resolution_criteria` (a link).
     - **Initial entry, DQ-01:**
       - check `qf_nos_credit_sum_vs_item10`, subject `AMH/Q2301`;
       - `observed`: `{row_sum: 12, item10: 14, totals_row: 14, qf_N2302: 3, qp_N2302: 5}`;
       - evidence: OV-035…OV-039 and [baseline §2](docs/baselines/legacy_tests_2026-10-31.md#2-the-source-discrepancy);
       - resolution criteria: [baseline §5](docs/baselines/legacy_tests_2026-10-31.md#5-resolution-criteria-for-dq-01).
     - DQ-02 (OV-040) is added in the same way if a validation check compares NOS levels across QF and QP.
  3. **`tests/golden/test_known_deviations.py`**, which applies these rules to every validation check over the real build. There is no `xfail` and no tolerance.
     - **Unregistered discrepancy → fail.**
     - **Registered discrepancy whose observed values differ from the register → fail** (changed values).
     - **Registered entry whose discrepancy no longer occurs → fail**, with the message "resolution review required: follow the baseline document §5". A disappearance is never accepted silently.
  4. **`tests/golden/test_known_findings.py`**: the findings DQ-01…DQ-15 are asserted **present**, with their recorded status.
- **Acceptance criteria:**
  - With the real data, the known-deviations tests pass *because* the register matches exactly.
  - Three synthetic-fixture tests show that each of these causes a failure: (a) an extra discrepancy, (b) a changed value, (c) a vanished discrepancy.
  - The independent status counts match the audit's corrected counts (TRANSCRIBED/PARSED_UNCERTAIN, excluding the secondary copy): SMO 56/3, SSMO 49/8, IC 53/1, PS 53/8. Any difference is investigated and documented, not forced.
  - `validation_report.json` never describes the legacy suite as passing.
- **Verification:** `python -m skillgraph validate`; `python -m pytest -m requires_local_data tests/golden`.
- **Definition of done:** E02's data is available as a Python object.
- **Effort:** 4–6 h.

**Phase 1 definition of done:**

- `verify-sources → build → validate` succeeds on the real local data.
- All Phase 1 tests pass.
- No source file was modified (hash check).
- Unresolved issues remain explicitly unresolved.

---

## Phase 2 — Labour-market data feasibility (Module A gate) · time-boxed, parallel

**Time-box:** at most 2 working days of effort, excluding any wait for access. **Any download needs your approval.** Downloads go to a new run folder, `data/labour/raw/<date>/`, with a manifest, following the 2026-10-30 discipline.

### P2.1 — Source inventory and access · MUST

- **Objective:** establish what can *actually* be obtained.
- **Dependencies:** Q-6. Registration on the official microdata portal is a user action.
- **Deliverables:** `docs/feasibility/module_a_sources.md`, listing each candidate source with: official URL, access route, account requirement, rounds, file formats, and whether files were obtained (with manifest entries).
- **Acceptance criteria:** every claim about availability cites an observed page or obtained file. "Not attempted" and "requested, pending" are valid outcomes.
- **Effort:** 2–4 h + wait.

### P2.2 — Licence and terms review · MUST

- **Deliverables:** a section of the same document quoting the relevant terms clauses. It answers: may aggregates be shown in a competition demo, may they be published, is attribution required?
- **Acceptance criteria:** the result is `PERMITTED`, `RESTRICTED` or `UNCLEAR` per source, with the quoted text. `UNCLEAR` means FG-2 is `FAIL` until clarified.
- **Effort:** 1–2 h.

### P2.3 — Metadata and variable check · MUST

- **Objective:** check FG-3, FG-4, FG-6 and FG-8 from documentation and codebooks before any analysis.
- **Deliverables:** `docs/feasibility/module_a_variables.md`, covering: state code; occupation variable, with its NCO version (verify whether it is NCO-2004 or NCO-2015 per round) and its digits; NIC; activity status (ps+ss, CWS); earnings variables; weights; design variables (FSU, stratum, sub-sample); and the comparability of the rounds.
- **Acceptance criteria:** each FG criterion is marked PASS, FAIL or UNKNOWN with a citation. If the NCO version differs from NCO-2015, the concordance source is identified or FG-8 is FAIL.
- **Effort:** 2–4 h.

### P2.4 — Sample-size and reproduction check · MUST (only if files were obtained)

- **Objective:** FG-5 and FG-7.
- **Deliverables:**
  - `src/skillgraph/labour/feasibility.py` and the CLI `report module-a-feasibility`, producing:
    - unweighted Karnataka counts per NCO division and sub-division (counts only);
    - the reproduction of one published Karnataka figure (e.g. WPR for one round), with the stated tolerance.
  - The thresholds (minimum unweighted n, maximum RSE) chosen and justified in `config/labour_market.yaml`.
- **Acceptance criteria:**
  - The reproduction is within tolerance, or FG-7 is FAIL.
  - The count table shows which garment-relevant groups (e.g. NCO division 8, or group 753 if supported) meet the thresholds.
  - No estimate other than the reproduction target is produced in this step.
- **Effort:** 3–6 h.

### P2.5 — Go/no-go decision record · MUST (always produced)

- **Deliverables:** `docs/decisions/MODULE_A_GATE.md`, recording FG-1…FG-8 results, evidence links, the decision (`GO`, `GO_REDUCED`, `NO_GO` or `NOT_ASSESSED`), the reasons, and what would change the decision. It also updates `config/labour_market.yaml` (`gate_decision`, `decided_on`, `criteria`).
- **Acceptance criteria:**
  - The decision follows the rules in ARCHITECTURE §21.2 mechanically.
  - If `NO_GO` or `NOT_ASSESSED`, **no labour-market statistic appears anywhere in the repository or the UI**. A test greps the analysis outputs and the frontend strings for indicator numbers.
  - E13 returns this record (P5.6).
- **Definition of done:** you have read and accepted the record.
- **Effort:** 1 h.

### P2.6 — Minimal indicator pipeline · CONDITIONAL (GO / GO_REDUCED) · SHOULD

- **Objective:** only the indicators allowed by the decision (ARCHITECTURE §14.2), with suppression.
- **Dependencies:** P2.5 = GO or GO_REDUCED.
- **Deliverables:** `src/skillgraph/labour/indicators.py`; `data/labour/outputs/<build_id>/indicators.json`, which stays local; tests.
- **Acceptance criteria:**
  - Every row carries: definition, activity-status basis, unweighted n, RSE (or `UNCERTAINTY_NOT_ESTIMABLE`), a suppression flag and evidence.
  - Cells below the thresholds are suppressed.
  - No "declining" or "in demand" label exists in v1 outputs.
  - The published-figure reproduction test is part of the suite.
- **Effort:** 4–8 h.

**Phase 2 definition of done:** P2.5 exists, whatever the outcome. If `NO_GO`, Phase 2 stops there and the reason is recorded. No findings are fabricated.

---

## Phase 3 — Deterministic graph and eligibility engine

### P3.1 — Registry loader · MUST

- **Dependencies:** P1.6.
- **Deliverables:** `src/skillgraph/registry/store.py`, an immutable, indexed in-memory registry (by id, code, slug and NOS code). `registry.load()` refuses an `INVALID` build.
- **Acceptance criteria:**
  - It loads the real build in under 1 s.
  - Lookups by code, slug and id agree.
  - A missing or invalid build raises a typed error that the API later maps to `DATA_NOT_BUILT`.
- **Effort:** 2–3 h.

### P3.2 — Verdict logic and component evaluators · MUST

- **Objective:** ARCHITECTURE §11.1–§11.3, exactly.
- **Dependencies:** P1.2; Q-3, Q-4 and Q-9 (defaults apply).
- **Deliverables:** `src/skillgraph/eligibility/logic.py` (`and_`, `or_`); `src/skillgraph/eligibility/components.py` (one evaluator per `ComponentType`).
- **Acceptance criteria:**
  - Exhaustive truth tables for `and_`/`or_` over the 4 verdicts (16 pairs each, plus n-ary associativity).
  - For each component type, tests cover: met; not met; undeclared → `UNKNOWN(INPUT_NOT_DECLARED)`; relevance undeclared → `UNKNOWN(RELEVANCE_NOT_DECLARED)`; relevance declared false → `NOT_MET`; config unset → `UNKNOWN(CONFIG_UNSET)`; uncertain input → `UNKNOWN(UNCERTAIN_EXTRACTION)`; conflicted input → `UNKNOWN(SOURCE_CONFLICT)`.
  - The "or equivalent" branch with the credential not held → `UNKNOWN(EQUIVALENCE_UNDEFINED)`.
  - An `UNMODELLED` component is always `UNKNOWN`.
  - All tests use synthetic fixtures only.
- **Effort:** 4–6 h.

### P3.3 — Eligibility evaluator and golden cases · MUST

- **Objective:** `evaluate(spec, state, config, registry) → EligibilityResult`, with decisive rules, conditions, unknown reasons and supporting evidence.
- **Dependencies:** P3.1, P3.2, P1.5.
- **Deliverables:** `src/skillgraph/eligibility/evaluate.py`; `tests/golden/test_eligibility_pilot.py`.
- **Acceptance criteria (golden tests, real local data):**
  1. Production Supervisor row 4: for a profile holding any of AMH/Q0301, AMH/Q2301 or AMH/Q0103, the `PRIOR_NSQF_LEVEL(4)` component is `NOT_MET` under both `exact` and `at_least` (audit A4).
  2. A profile holding AMH/Q0301: the *level* component of SSMO row 9 and of IC row 4 is satisfied under both interpretations (CONDITIONAL with relevance declared; audit A4).
  3. `nsqf_level_match = null` with ≥ 1 declared prior qualification → every `PRIOR_NSQF_LEVEL` component is `UNKNOWN(CONFIG_UNSET)`, even where both interpretations agree. With holdings declared as none → `NOT_MET`.
  4. Age 17 against any pilot target → target `NOT_MET`, with the decisive reason on the age rule.
  5. Without approval of OV-002…004, SSMO rows 2–4 are not `MET` or `CONDITIONAL`.
  6. The progression claim SMO → SSMO appears in `supporting_evidence` and never changes the verdict: a test removes the claim and compares the results.
  7. **Credits invariance:** mutating every credit value in a copied registry leaves all results identical.
  8. Every `CONDITIONAL` result has ≥ 1 condition; every `UNKNOWN` has ≥ 1 unknown reason.
- **Effort:** 4–6 h.

### P3.4 — Static graph edges · MUST

- **Dependencies:** P3.1.
- **Deliverables:** `src/skillgraph/graph/edges.py` (`INCLUDES_NOS`, `SHARES_NOS` with core/non-core and version agreement, `PROGRESSION_CLAIM` to `CLAIM_TEXT` nodes, `ALIGNED_TO_NCO`); the legend text from `API_SPEC.md` E08.
- **Acceptance criteria:**
  - **OBS-01 reproduced:** `SHARES_NOS` exists exactly for {SSMO, IC} = {AMH/N0309, DGT/VSQ/N0102}, {IC, PS} = {DGT/VSQ/N0102} and {SSMO, PS} = {DGT/VSQ/N0102}.
  - SMO has no `SHARES_NOS` edge.
  - All shared units are Non-Core.
  - The DGT/VSQ/N0102 edges carry the OV-040 conflict flag where the SSMO membership is involved.
  - No `PROGRESSION_CLAIM` edge targets a qualification code, except through a reviewed inference (P3.5).
- **Effort:** 2–4 h.

### P3.5 — Experimental inference edges · SHOULD

- **Deliverables:**
  - `src/skillgraph/graph/inference.py`: `NCO_GROUP_PROXIMITY` at the 4-digit unit group, with the 3-digit level configurable.
  - Name-normalised matching of claim text to catalogue titles, written to the review file as candidates (e.g. "Sampling Coordinator" → AMH/Q1801; "QC Executive – Sewing Line" has **no** exact match).
  - `TITLE_SIMILARITY` is COULD and not planned.
- **Acceptance criteria:**
  - Every inference edge has `evidence_class = INFERENCE` and `experimental = true`.
  - The edges are off unless they are requested.
  - SMO–SSMO share unit group 8153, so they get an `NCO_GROUP_PROXIMITY` edge.
  - The invariant test in P3.6 passes.
- **Effort:** 2–3 h.

### P3.6 — Path enumeration · MUST

- **Objective:** ARCHITECTURE §13.1.
- **Dependencies:** P3.3.
- **Deliverables:** `src/skillgraph/graph/paths.py`.
- **Acceptance criteria:**
  - Deterministic: two runs give identical serialised output.
  - Only `CURATED` qualifications are targets.
  - No repeated qualifications; `max_steps` is respected; the expansion guard raises `LimitExceededError`.
  - `NOT_MET` steps are never extended and never appear in ranked paths.
  - Experience does not accrue unless the scenario says so.
  - A non-default scenario sets `is_hypothetical = true` and the flag `HYPOTHETICAL_SCENARIO`.
  - **Inference invariant:** toggling `include_inference` leaves path IDs, verdicts and order unchanged.
  - Path verdict = `and_` over the steps.
- **Effort:** 4–6 h.

### P3.7 — Ranking · MUST

- **Deliverables:** `src/skillgraph/graph/rank.py`.
- **Acceptance criteria:**
  - The verdict class always sorts first.
  - Each `PathSortKey` orders as specified in ARCHITECTURE §13.2.
  - `sort_values` exposes the keys actually used.
  - Ties are resolved by `path_id`.
  - There is no composite score.
- **Effort:** 1–2 h.

### P3.8 — Deterministic explanations · MUST

- **Deliverables:** `src/skillgraph/explain/templates.py`, covering verdict summary, per-row reasoning, hours, overlap, progression claim, conditions, "what would resolve this", and the caveat.
- **Acceptance criteria:**
  - Every `ExplanationItem` has an evidence class.
  - Every factual sentence cites ≥ 1 evidence ID.
  - The caveat item is present on every eligibility result and every path.
  - A text lint test forbids the words "guarantee", "will get", "eligible for job", "in demand" and "declining" in templates.
  - Output is identical across runs.
- **Effort:** 3–5 h.

### P3.9 — Hypothetical incremental hours policy · SHOULD

- **Deliverables:** policy handling in `graph/paths.py` (ARCHITECTURE §12).
- **Acceptance criteria:**
  - With `NONE`, the field is `null`.
  - With `EXCLUDE_SHARED_NOS_CODE`, the value = official total − the hours of shared NOS codes. Bridge modules and conflict-flagged units are never deducted.
  - The value is labelled `HYPOTHETICAL`, and the path `is_hypothetical`.
  - Official hours are unchanged.
  - `evidence_backed_incremental_hours` is always `null`, with `NO_OFFICIAL_REDUCTION_SOURCE`.
- **Effort:** 1–2 h.

### P3.10 — Service façade, API schemas and boundaries · MUST

- **Objective:** freeze the contract before the UI work.
- **Dependencies:** P3.1–P3.8.
- **Deliverables:** `src/skillgraph/services.py` (API_SPEC §4); `src/skillgraph/api/schemas.py` (all API_SPEC §2 models); `tests/unit/test_import_boundaries.py` (AST-based: `eligibility/` and `graph/` must not import `api`, `labour` or any LLM SDK; `labour/` must not import `eligibility`/`graph`).
- **Acceptance criteria:**
  - Every JSON example in `API_SPEC.md` validates against the schemas. Ellipsis placeholders are replaced by fixture values in the test copy.
  - The boundary test passes.
  - The CLI can run an evaluation through the façade: `python -m skillgraph report eligibility --profile config/demo/profile_a.yaml`.
- **Definition of done (Phase 3):**
  - All unit and golden tests pass.
  - The façade is usable from Python.
  - No HTTP is needed to demonstrate the engine.
- **Effort:** 3–5 h.

---

## Phase 4 — Analytical outputs and baselines

All outputs go to `data/outputs/<build_id>/`, which is local and ignored: they derive from sources whose licence is unconfirmed. Each output is stamped with `data_build_id`, `config_digest` and the code commit.

### P4.1 — Feasibility matrix and interpretation sensitivity · MUST

- **Deliverables:** `analysis/feasibility_matrix.py`. For each (held pilot qualification → target) pair, under `nsqf_level_match ∈ {null, exact, at_least}` and the relevance declarations {undeclared, declared true}, it records the target verdict, the decisive rows and the reasons, as `feasibility_matrix.{json,md}`.
- **Acceptance criteria:**
  - All combinations are present.
  - Each cell links to the rule IDs.
  - A summary lists exactly which cells change between `exact` and `at_least` and why.
  - No cell is described as a prediction.
- **Effort:** 2–4 h.

### P4.2 — UNKNOWN-cause audit · MUST

- **Deliverables:** `analysis/unknown_audit.py` → `unknown_audit.md`: counts of `UNKNOWN` components by reason code and qualification, and which open questions (Q-2, Q-3, Q-4) or unavailable sources would resolve them.
- **Acceptance criteria:**
  - The totals reconcile with the feasibility matrix.
  - Every reason links to the overlay or the decision.
- **Effort:** 1–2 h.

### P4.3 — Baseline comparison · MUST

- **Deliverables:** `analysis/baselines.py` → `baselines.md`: B0 official progression, B1 NSQF ladder, B2 documented overlap and B3 NCO proximity versus the engine (ARCHITECTURE §13.5). It produces agreement and disagreement tables, with explanations per disagreement.
- **Acceptance criteria:**
  - Each baseline is described with what it measures and what it does not.
  - The comparison is reported as agreement, not accuracy.
  - Disagreements cite the rows or units.
  - B2 reproduces OBS-01.
- **Effort:** 2–4 h.

### P4.4 — Overlap and hours analysis · SHOULD

- **Deliverables:** `analysis/overlap_hours.py` → `overlap_hours.md`: the official hours per qualification and per path; core versus non-core composition of the shared units; and the hypothetical incremental hours under each policy, in a separate, clearly labelled section.
- **Acceptance criteria:**
  - Official and hypothetical figures are never placed in the same column.
  - Credits appear only in a "not used" note referencing DQ-01.
- **Effort:** 1–3 h.

### P4.5 — Module A indicator report · CONDITIONAL (GO / GO_REDUCED)

- **Deliverables:** `analysis/labour_context.py` → `labour_context.md`: suppressed and flagged indicators for the NCO groups aligned to the pilot qualifications.
- **Acceptance criteria:** as in P2.6. Every join is labelled `AGGREGATION_CONTEXT_ONLY`. There are no trend claims unless the ARCHITECTURE §14.4 criterion is met and documented.
- **Effort:** 2–4 h.

### P4.6 — Reproducible report runner · MUST

- **Deliverables:** `python -m skillgraph report --all`, which writes every output above plus `run_manifest.json`.
- **Acceptance criteria:**
  - Two consecutive runs produce byte-identical outputs, excluding `run_manifest.json` timestamps (test).
  - The PII regex scan of the outputs finds 0 hits.
  - The outputs contain no labour-market numbers unless `gate_decision ∈ {GO, GO_REDUCED}`.
- **Definition of done (Phase 4):**
  - Reports exist and reproduce.
  - The analysis narrative for the demo can be written from them alone.
- **Effort:** 1–2 h.

---

## Phase 5 — Dashboard and integration

### P5.1 — FastAPI application, health, status, errors · MUST

- **Dependencies:** P3.10, P1.6.
- **Deliverables:** `src/skillgraph/api/app.py` and routers; the error envelope handlers (API_SPEC §1.6); E01, E02; `python -m skillgraph serve`, which binds to 127.0.0.1.
- **Acceptance criteria:**
  - E01 returns 200.
  - E02 matches the schema.
  - With no curated build, E01 returns 200, E02 reports `NOT_BUILT`, and the data endpoints return `503 DATA_NOT_BUILT`.
  - Request logs contain no profile fields.
- **Verification:** `python -m pytest tests/api/test_health_status.py`.
- **Effort:** 2–3 h.

### P5.2 — Qualification and occupation endpoints · MUST (E03, E04) / SHOULD (E05, E06)

- **Acceptance criteria:**
  - The responses match the API_SPEC schemas.
  - `coverage` filtering works.
  - `nco:3122.3551` shows `title: null`.
  - E06 shows `labour_market.module_status` from config.
  - Unknown slug → 404 envelope.
- **Effort:** 2–4 h.

### P5.3 — Eligibility endpoint (E07) · MUST

- **Acceptance criteria:**
  - Contract tests for each error code in E07.
  - The response equals the façade output for the same input.
  - `UNKNOWN`/`NOT_MET` verdicts return 200.
- **Effort:** 1–2 h.

### P5.4 — Graph and paths endpoints (E08, E09) · MUST

- **Acceptance criteria:**
  - E08 legend entries are present for every edge type returned.
  - Inference edges appear only with `include_inference=true`.
  - E09 enforces the limits (`max_steps` > 4 → 422).
  - The determinism test over HTTP passes (identical bodies apart from `request_id`).
- **Effort:** 2–3 h.

### P5.5 — Evidence, conflicts and sources (E10 MUST; E11, E12 SHOULD)

- **Acceptance criteria:**
  - E10 handles the `missing` IDs.
  - A test asserts that no route serves files from `data/raw/`: route enumeration plus attempted path traversal.
  - E12 marks C3, C4 and D1 as unavailable.
- **Effort:** 1–2 h.

### P5.6 — Labour-market status and indicators (E13 MUST; E14 CONDITIONAL)

- **Acceptance criteria:**
  - E13 reflects `config/labour_market.yaml`.
  - E14 returns `404 MODULE_UNAVAILABLE`, with details, when the decision is not GO or GO_REDUCED.
  - When it is, E14 returns suppressed or flagged rows per the API_SPEC.
- **Effort:** 1–3 h.

### P5.7 — Frontend scaffold · MUST

- **Dependencies:** P0.1 (the `!/frontend/index.html` rule), P5.1.
- **Deliverables:**
  - `frontend/` (Vite + React + TypeScript), with `package.json` and `package-lock.json` committed. New npm dependencies need your approval when they are installed.
  - `src/api/client.ts`, with types generated from `/api/v1/openapi.json` (SHOULD) or hand-mirrored and checked by a contract test.
  - The Vite dev-server proxy to `:8000`.
  - A production build served by FastAPI under `/` (SHOULD).
- **Acceptance criteria:**
  - `npm run build` succeeds.
  - `git check-ignore frontend/index.html` exits 1.
  - `node_modules/` and `dist/` are ignored.
- **Effort:** 2–3 h.

### P5.8 — Core screens · MUST

- **Deliverables:**
  1. **Global banner:** build ID, Module A status, licence notice.
  2. **Profile builder:** hypothetical label enforced; per-target declarations; NSQF interpretation selector with an "unset → unknown" explanation; scenario toggles, behind an "Illustrative scenarios" disclosure.
  3. **Path explorer:** paths grouped by verdict; totals; conditions as "This holds only if …"; unknowns as "What would resolve this"; a blocked section.
  4. **Qualification detail:** hours, NOS, verbatim and structured eligibility, claims, occupations, conflicts.
  5. **Evidence drawer:** evidence class badge, source title, page, location, overlay and decision refs.
  6. **Data status page.**
- **Acceptance criteria:**
  - Every verdict and value shows its evidence class as **text plus colour** (never colour alone).
  - The caveat is visible on every path and eligibility result.
  - `HYPOTHETICAL` paths are visually distinct and labelled.
  - The UI makes no claim the API did not return.
  - It works at a 1280 px laptop width and is legible at 1920 px for projection.
- **Effort:** 8–14 h.

### P5.9 — Graph view (Cytoscape.js) · SHOULD

- **Acceptance criteria:**
  - Documented edges are solid and inference edges dashed and hidden by default, behind an "Experimental" toggle.
  - The legend shows `meaning` and `does_not_mean` from E08.
  - Clicking a node opens its detail.
  - A path can be highlighted from the path explorer.
- **Effort:** 3–5 h.

### P5.10 — Unavailable and future feature labelling · MUST

- **Acceptance criteria:**
  - The Module A panel shows exactly the E13 state. With `NO_GO` or `NOT_ASSESSED` it shows "Deferred", the reasons and a link to the decision record, and **no numbers**.
  - Catalogue-only qualifications are labelled "catalogue entry only — no eligibility evidence".
  - Features not built (LLM rephrase, Docker) do not appear in the UI.
  - A manual checklist is in `docs/demo/ui_checklist.md`.
- **Definition of done (Phase 5):** journeys J1–J4 and J6 work end to end in the browser on the real local build; J5 shows the correct state.
- **Effort:** 1–2 h.

### P5.11 — Optional LLM rephrasing · COULD

- **Constraints:** ARCHITECTURE §15.6. It is off without an API key. Its output is labelled. The deterministic text is always shown. It is never used in tests of verdicts.
- **Effort:** 2–4 h. **Only after all MUST items in Phases 5–6 are done.**

### P5.12 — Docker packaging · COULD

- **Constraints:** ARCHITECTURE §15.7. The image never contains `data/`; data is mounted at runtime.
- **Effort:** 2–4 h. **Only after P6.4 works locally.**

---

## Phase 6 — Validation and final demo

### P6.1 — Full test and integration run · MUST

- **Verification:**
  - `python -m pytest` (all);
  - `python -m pytest -m requires_local_data`;
  - `python -B tools/check_legacy_baseline.py` (expect MATCH: 23 passed, 1 failed, DQ-01 unresolved, unless it was resolved under the baseline document §5);
  - `npm run build` (and `npm test`, if Vitest exists).
- **Acceptance criteria:**
  - The new suite (`python -m pytest`) has 0 failures and 0 errors.
  - The legacy baseline check reports MATCH. It is reported as "23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)", never as passing.
  - The results are recorded in `docs/demo/test_run.md`, with the date and build ID.
- **Effort:** 1–2 h.

### P6.2 — Provenance and reproducibility verification · MUST

- **Acceptance criteria:**
  - Delete `data/curated/` and `data/outputs/`, which are regenerable. Then `verify-sources → build → validate → report --all` reproduces the **same `data_build_id`** and byte-identical reports.
  - A sample of 10 UI values, spread across qualifications, is traced to the evidence page by hand, and the result is recorded in `docs/demo/provenance_spotcheck.md`.
- **Effort:** 1–2 h.

### P6.3 — Data handling and licensing check · MUST

- **Deliverables:** the `python -m skillgraph check-repo-hygiene` command.
- **Acceptance criteria:**
  - It fails if `git ls-files` contains `data/` paths or `.pdf/.csv/.html/.htm/.xlsx/.docx/.parquet` files, apart from the allow-list `frontend/index.html`.
  - It runs the PII regex scan over tracked files.
  - It warns if any `SourceDocument.licence_status` is `UNCONFIRMED` while any public-sharing setting is enabled.
  - The check passes.
  - The README states the data-governance position.
- **Effort:** 1–2 h.

### P6.4 — Demo scenario and script · MUST

- **Deliverables:**
  - `config/demo/profile_a.yaml`, `profile_b.yaml`, `profile_c.yaml`. All are hypothetical and clearly labelled.
    - **A:** holds SMO, age 24, 10th grade passed, relevance declared for SSMO and IC.
    - **B:** the same holdings with declarations missing; this shows `UNKNOWN` and "what would resolve this".
    - **C:** age 17; this shows a definitive `NOT_MET`, distinct from unknown.
  - `docs/demo/DEMO_SCRIPT.md`, a 5–7 minute flow:
    1. Problem and data-status page (evidence base, conflicts, Module A state).
    2. Profile A → path explorer. Covers: SMO → SSMO with an official progression claim shown as supporting evidence only; SMO → Inline Checker with no official relationship (OV-033); and the effect of switching `exact` ↔ `at_least`.
    3. Evidence drawer on one hours value and one eligibility row.
    4. Profile B → unknowns and how they are resolved.
    5. Profile C → a definitive failure.
    6. Graph view: thin documented overlap (OBS-01), with the inference toggle.
    7. Analysis highlights from Phase 4.
    8. Limitations and what was deliberately not claimed.
  - `tests/golden/test_demo_scenarios.py`, which freezes the demo outputs for the current build so the live demo is repeatable.
- **Acceptance criteria:**
  - The script's expected screens match the golden test outputs, which are generated by the engine, not hand-written.
  - The demo runs offline.
  - It finishes within the time limit in two dry runs (P6.6).
- **Effort:** 3–5 h.

### P6.5 — Claims register and limitations · MUST

- **Deliverables:** `docs/CLAIMS.md`, with three sections:
  - **Defensible claims**, each with the evidence or report it rests on;
  - **Explicitly not claimed**: employability, placement, earnings, demand, "declining" (unless Module A meets ARCHITECTURE §14.4), skill equivalence from overlap, exemptions, RPL;
  - **Known limitations**: DQ-01…DQ-15; the pilot of 4; unconfirmed licences; Module A status.
- **Acceptance criteria:** every claim in the demo script and the slides appears in the defensible list with a reference. You review the register.
- **Effort:** 1–2 h.

### P6.6 — Dry runs · SHOULD

- **Acceptance criteria:** two timed dry runs on the demo machine, run from a cold start (`serve` plus the browser), with notes on any fixes made.
- **Effort:** 1–2 h.

**Phase 6 definition of done (project):**

- P6.1–P6.5 pass.
- The demo is repeatable from a fresh clone plus the local `data/` folder, using README instructions only.
- No restricted data is tracked.
- Every on-screen claim is traceable.

---

## 2. Backlog (not scheduled)

| ID | Item | Priority | Precondition |
|---|---|---|---|
| B-1 | Expand to more AMHSSC qualifications (e.g. AMH/Q1801 Sampling Coordinator, AMH/Q1401 QC Executive – Stitched Items, AMH/Q0305 SMO Knits) | SHOULD (post-demo) | Q-7 approval; a new acquisition run with manifest and robots/throttle discipline; re-run P1 for the new records |
| B-2 | Retry the unavailable sources (C3, C4, D1) to test DQ-03 and DQ-04 | SHOULD | Approval; acquisition discipline; Playwright only with a verified per-host throttle |
| B-3 | Trend labels for Module A | COULD | `GO` plus the ARCHITECTURE §14.4 criterion met |
| B-4 | `TITLE_SIMILARITY` inference | COULD | P3.5 done; never on PC/KU text |
| B-5 | New extractor version fixing the count and truncation issues (audit A1) | COULD | A new run ID; the old outputs are kept |
| B-6 | Model literacy, enrolment, NTC/NAC/CITS and diploma-year inputs | COULD | Q-4 decision |

---

## 3. First implementation task

> **Update 2026-10-31:** P0.3 is done (`63a83dd`) and P0.4 is done (`33ac1cc`). The next task is **P1.1** (source integrity verifier). The text below is the original P0.3 hand-off, kept for the record.

**P0.3 — Package skeleton, configuration and logging.** The full specification and acceptance criteria are in P0.3 above.

- **Prerequisites (met):**
  - `.venv` was installed from the hashed lock, and `pip check` is clean (P0.2).
  - `pyproject.toml` declares the package and the `src/` layout.
- **Recommended first:** commit the staged foundation on `chore/repo-foundation` (P0.1).
- **Begin with:**

  ```powershell
  .\.venv\Scripts\python.exe -m pip check                        # expect: No broken requirements found.
  .\.venv\Scripts\python.exe -B tools\check_legacy_baseline.py   # expect: MATCH ... 23 passed, 1 failed (DQ-01 unresolved)
  # create src/skillgraph/ and config/ as specified in P0.3, then:
  .\.venv\Scripts\python.exe -m pip install --no-deps -e .
  .\.venv\Scripts\python.exe -c "import skillgraph; print(skillgraph.__version__)"
  ```
