# Skill Adjacency Graph — Implementation Plan (TASKS)

**Document status:** Approved baseline, 2026-10-31. Phase 0 is complete (P0.1–P0.5 DONE: `fbdc28f`, `63a83dd`, `33ac1cc`). Phase 1 (P1.1–P1.6) is **engineering accepted with documented exceptions** and committed; P1.1–P1.6 are marked DONE as engineering stages (`1a1e843`, `771675e`, `4c18e0d`, `abcdd27`, `7f43f66`, `2a65abd`). Phase 1 is **not declared complete**: DQ-01/02/03, Q-2, A2, P1.5-R1 and the other evidence gates remain open. Phase 1 closure status and the open decisions are in the **Phase 1 closure assessment** below (after P1.6).
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

### P1.1 — Source integrity verifier · MUST · DONE (1a1e843)

- **DONE (2026-10-31, engineering acceptance):** all four acceptance criteria met; integrity is checked before every build (`build` calls `verify_sources`). DONE here means the engineering criteria are verified and committed; it does not resolve or approve any evidence item. See the Phase 1 closure assessment.

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
- **[Historical — superseded by the DONE marking above and the Phase 1 closure assessment.]** **Status (2026-10-31):** implemented, **uncommitted, awaiting review**. All four acceptance criteria are met. The definition of done ("integrity is checked automatically before every build") is now met by the P1.4 `build`, which runs `verify_sources` before consuming any input and fails on a `SourceIntegrityError` (tested, including tampered sources); P1.4 itself is not DONE. Evidence:
  - `python -m skillgraph verify-sources` on the real data: exit 0; 18 of 18 local files matched; 4 `NO_LOCAL_FILE` (C3 `FAIL_HTTP`, C4 `NOT_FOUND`, D1 `FAIL_HTTP`, D2 `NOT_FOUND`); 265 of 265 extraction rows resolved (0 `UNRESOLVED` rows present to exclude); 52 of 52 overlay `evidence_sha256` values resolved.
  - Beyond the criteria, each row's `source_file` must also equal the manifest path for its hash (ARCHITECTURE §3 principle 3), and any check that cannot run (missing manifest, overlay or extraction CSVs, missing column, or a header-only CSV with no data rows) fails the report instead of being skipped. Several manifest paths may share one hash; a row must still name its own manifest path. A hash recorded for a non-local item (C3, D1) does not count as a resolvable source.
  - Exit codes: 0 verified, 1 `SourceIntegrityError` (the full report is still printed on stdout), 3 settings or configuration error (`SettingsError`, invalid values, unreadable file; no traceback, empty stdout).
  - `tests/integration/test_integrity.py`: 35 tests, synthetic trees in temporary directories (including the one-altered-byte case); the two real-data tests skip when `data/` is absent. Full suite: 86 passed. Legacy baseline: MATCH, 23 passed, 1 failed (DQ-01 unresolved), not a passing suite.

### P1.2 — Source-of-truth schemas · MUST · DONE (771675e)

- **DONE (2026-10-31, engineering acceptance):** all five acceptance criteria met and enforced by `tests/unit/test_model_*.py`; `docs/schemas.md` is checked by `tools/gen_schema_docs.py --check`. DONE here means the engineering criteria are verified and committed; it does not resolve or approve any evidence item. See the Phase 1 closure assessment.

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
- **[Historical — superseded by the DONE marking above and the Phase 1 closure assessment.]** **Status (2026-10-31):** implemented, **uncommitted, awaiting review**. All five acceptance criteria are met; each is enforced by a test in `tests/unit/test_model_*.py`. Beyond them: `src/skillgraph/model/base.py` (shared strict base and numeric types), `tools/gen_schema_docs.py` and the generated `docs/schemas.md` (a test fails when it is stale), and `tests/integration/test_model_source_formats.py` (real identifiers, enum values and numbers fit the schemas; skips when `data/` is absent). Design decisions and limits:
  - **Final audit finding N1, corrected.** Stored qualification facts were plain `Valued`, so hypothetical, declared, config or inferred values could pass as, for example, `SAFE_HOURS` qualification hours. Hours, NSQF level, minimum age, credits, NCO codes and NOS-membership values (including versions) are now `OfficialValued`/`CreditValue`/`DisplayValued`, which refuse every class except `OFFICIAL`; they keep the evidence, `value_status` and conflict rules of `Valued`. The general `Valued` still accepts every class, for profile inputs, scenarios and path results. `RULE_DERIVED` is refused too, deliberately: the specifications show it only for path totals, edges, explanations and `nco_levels`, never for a stored qualification fact (ARCHITECTURE §10.1, §12). If a stored field ever needs a derived value, that is a documented decision, not a loosened check. Regression tests: `tests/unit/test_model_stored_facts.py` (11 field categories × 5 refused classes, valid `OFFICIAL` values, and the demonstrated hypothetical-hours, credit and level cases).
  - Models check format and local consistency only. Referential integrity, `Evidence.source_sha256` against `SourceDocument.sha256`, and cross-source comparisons are P1.4 / P1.6.
  - Added to ARCHITECTURE §9.2 (the specification is not rewritten): `Evidence.source_sha256` (P1.4 requires an `OFFICIAL` record to carry the SHA-256; it needs a page **or** a location, because the catalogue A1 has no page); an `evidence_id` on eligibility rules for the verbatim `raw_text`; the `Module` entity (§9.2 lists `modules[]`, §9.1 defines `mod:`); `Conflict.overlay_ids` (the id is the lowest of them); `ResolvedTarget` as an object (the API form) instead of `resolved_target_id`; hours parts, `min_age` and `eligibility` optional for `CATALOGUE_ONLY` (all five hours and the others required for `CURATED`); `CoreOrNonCore`; `ManifestStatus` (the four statuses in `MANIFEST.csv` today).
  - Documented discrepancies between the specifications, not resolved by rewriting either: (a) ARCHITECTURE §9.1 gives `src`, `ev` and `mod` slugs, API_SPEC §1.2 lists none; `slug_of` follows §9.1 (an `ev` slug is the whole id) and no endpoint uses them. (b) §9.2 shows `Valued` without `evidence_class` and API_SPEC §2.2 with it; the API form is used. (c) §9.2 names the evidence field `extraction_status`, API_SPEC §2.2 `value_status`; the API name is used.
  - Remaining limitations (audit N2–N4): (N2) an `OFFICIAL` value need not carry an `engine_use`, and `value_status = UNRESOLVED` may hold a non-null value; both are left to P1.4/P1.6 checks. (N3) models are only shallowly immutable: fields cannot be reassigned, but lists and dicts inside them (`params`, `quality_flags`) can still be mutated in place. (N4) an unparametrised `Valued` accepts any value type; no model uses it bare. The slug-collision check is a safety net: strict ID grammars make a natural collision impossible, so the test forces one with an explicit slug.
  - **DQ-03 remains unresolved for a deliberate P1.4 decision.** §9.1 derives a conflict ID from an overlay ID and the DQ-03 lead has no overlay row, so `Conflict` cannot represent `UNRESOLVED_LEAD_SOURCE_UNAVAILABLE` without a new ID convention or a borrowed overlay ID (which would be fabricated provenance). Neither was introduced.

### P1.3 — Overlay approval mechanism · MUST · DONE (4c18e0d, abcdd27)

- **DONE (2026-10-31, engineering acceptance):** mechanism criteria met in `4c18e0d`; the three "after a build" criteria were verified once `build` existed (`abcdd27`). `config/overlay_approvals.yaml` remains `approved: []`; OV-002…004 and OV-034/035 stay pending. DONE here means the engineering criteria are verified and committed; it does not resolve or approve any evidence item. See the Phase 1 closure assessment.

- **Objective:** apply audit proposals only with your explicit approval (Q-2).
- **Dependencies:** P1.2.
- **Deliverables:** the `config/overlay_approvals.yaml` schema (`approved: [{overlay_id, approved_by, approved_on, note}]`); `src/skillgraph/curation/overlay.py`, which loads the overlay and classifies each row as `APPLY`, `INTERPRET`, `DISPLAY`, `PENDING` or `IGNORE` by `status` × approval.
- **Acceptance criteria:**
  - With an empty approvals file, OV-002…004 and OV-034/035 are `PENDING` and change no value.
  - When OV-002 is approved, the curated SSMO row 2 experience component holds the overlay value with `value_status = CORRECTION_APPLIED` and `overlay_ids = ["OV-002"]`, and the source value is still recorded.
  - Approving an ID that does not exist fails the build.
  - The extraction CSVs and the overlay CSV are byte-identical before and after a build. A test checks their hashes.
- **Effort:** 2–3 h.
- **[Historical — superseded by the DONE marking above and the Phase 1 closure assessment.]** **Status (2026-10-31):** mechanism implemented, **uncommitted, awaiting review**. It is **not marked DONE**: the criteria are phrased in terms of "the build" and "the curated row", and `build` does not exist until P1.4. What is verified:
  - `src/skillgraph/curation/overlay.py`: `load_overlay`, `load_approvals`, `classify`, `load_plan`, `resolve_field`. Read-only; no CLI command is added.
  - Empty approvals file: OV-002…004 and OV-034/035 are `PENDING`, `resolve_field` returns the extraction value unchanged with flag `OVERLAY_PENDING_APPROVAL` (real data, `tests/integration/test_overlay_real.py`).
  - OV-002 approved (in memory in the test; `config/overlay_approvals.yaml` stays `approved: []`): `resolve_field` returns `value = "No Experience required"`, `value_status = CORRECTION_APPLIED`, `overlay_ids = ("OV-002",)`, and `source_value = ""` is kept. This is the field-level behaviour only; the curated SSMO row itself is assembled by P1.4.
  - An approval naming a missing overlay_id raises `OverlayError`. **P1.4 calls `load_plan` and lets that error fail the build (tested).**
  - The extraction and overlay CSVs have identical SHA-256 before and after loading, classifying and resolving. A test checks this. The same check after a build is done in P1.4 (`tests/integration/test_build.py`).
  - Decisions beyond the text (the specification does not say): an approval of a row that is not `PROPOSED_*` is an error; an unknown `status` or `engine_use` is an error; a missing or non-list approvals file is an error rather than "nothing approved"; an overlay `source_value` that differs from the extraction value is a "stale overlay" error; an approved `PROPOSED_REPRESENTATION` (OV-034/035) is classified `APPLY` but replaces no value. The mapping of the other statuses to `INTERPRET`/`DISPLAY`/`IGNORE` is the module's reading of AUDIT_NOTE §4 (table in the module docstring); `engine_use` still governs engine behaviour (§11.4).
  - Q-2 stays open. DQ-01 and DQ-03 are untouched.

### P1.4 — Curated build · MUST · DONE (abcdd27, 7f43f66, 2a65abd)

- **DONE (2026-10-31, engineering acceptance):** all criteria met; the definition of done (rely on `data/curated/` alone) is met now that P1.5 and P1.6 exist. Documented exceptions remain: `VALIDATION.json` is hashed but has no expected hash, and the QP title alias is not PDF-checked (closure item D1). DONE here means the engineering criteria are verified and committed; it does not resolve or approve any evidence item. See the Phase 1 closure assessment.

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
- **[Historical — superseded by the DONE marking above and the Phase 1 closure assessment.]** **Status (2026-10-31):** implemented and recorded as a **checkpoint commit, not DONE** (final acceptance awaits P1.5/P1.6 and your review). All eight acceptance criteria and the three P1.3 "after a build" criteria are met and tested. It is **not marked DONE**: the definition of done (rely on `data/curated/` alone) needs the structured eligibility rules of P1.5 and the validation report of P1.6, and two build inputs are recorded but not integrity-verified (below). Evidence and decisions:
  - `python -m skillgraph build` on the real data (empty approvals): exit 0, `cb-0e76c97bea00`, a second run reuses the identical build. Output in `data/curated/<id>/`: `qualifications.json` (4 `CURATED` + 33 `CATALOGUE_ONLY`), `nos_units.json` (22), `occupations.json` (4), `sources.json` (22), `evidence.json`, `conflicts.json` (3), `eligibility_source_rows.json` (24 rows + 4 age rows), `build_manifest.json` (written last; its presence marks a complete build). Counts: APPLY 0, INTERPRET 35, DISPLAY 11, PENDING 5, IGNORE 1.
  - **Order of operations:** hash all inputs; `verify_sources` (a `SourceIntegrityError` exits 1 with the full report, before any data is consumed); `load_plan` (a nonexistent or non-proposal approval raises `OverlayError`); every one of the 52 `target_row_key` values must resolve exactly (`curation/targets.py`: eligibility row, age row, NOS row, QP header, fact, claim, plus the composite `bridge(s_no n)+<nos>` key of OV-034/035, the claim range of OV-033 and the `s_no sequence` of OV-041) **and** its recorded `source_value` must equal the extraction. Models are built, validated, written to `.staging-*`, reloaded and reference-checked, the inputs are re-hashed (any change fails the build), and one directory rename installs the build. Any failure removes the staging directory and leaves existing builds untouched. Output paths overlapping an input directory are refused.
  - **Classification versus effect.** `build.overlays.applied` = rows classified `APPLY` (an approved `PROPOSED_*` row written to a curated record); `pending` = `PENDING`; `display_only` = rows classified `DISPLAY` (11), **not** the 7 rows whose `engine_use` is `DISPLAY_ONLY` (`overlay_engine_use_counts` in `build_manifest.json` shows both). `overlay_effects` records, for each of the 52 rows, its class and what the build did (`VALUE_REPLACED`, `GROUP_RECORDED`, `STATUS_UPGRADED`, `INTERPRETATION_ATTACHED`, `EVIDENCE_ATTACHED`, `CONFLICT_REGISTERED`, `FLAG_ATTACHED`, `PENDING_FLAGGED`, `NO_RELATIONSHIP_ASSERTED`). The API_SPEC E02 example (`applied: ["OV-001", "OV-028"]`, `display_only: 14`) is illustrative and is **not** reproduced: OV-001 and OV-028 are `CONFIRMED_BY_GEOMETRY` (INTERPRET) and apply nothing. API_SPEC E02 gained a note saying so; its example values are unchanged.
  - **`engine_use`:** copied from the overlay row for the targeted cell; otherwise from `config/curation_defaults.yaml` (each entry cites AUDIT_NOTE/ARCHITECTURE); otherwise `UNKNOWN`. The qualification-level `nsqf_level` has no entry (no document states its use outside an eligibility row), so it is `UNKNOWN`. Classification and approval never raise it (tested; an approved OV-002 leaves the field and the row `UNKNOWN`).
  - **Corrections:** a field-level correction replaces only that field (`CORRECTION_APPLIED`, `source_value` kept, `""` distinct from absent). It is applied only if the cited source resolves to an available manifest item with a local file, the cited page is on the row's page and inside the document, and the corrected value is printed on that page in the extraction itself (otherwise `EvidenceError`: the evidence cannot substantiate it). Two evidence records result (source value and correction), with distinct ids. The row's `extraction_status`, its `UNCERTAIN_EXTRACTION` flag and every other field are unchanged. `experience_years` is not back-filled (P1.5).
  - **Model extensions (P1.2 models extended, not paralleled):** `Valued.source_value`/`source_evidence_id` (only with `CORRECTION_APPLIED`, then both required); `Qualification.credit_groups` (`CreditGroup`: `member_s_nos`, one `CreditValue`, `overlay_ids`; recorded only for an approved representation, members keep their own values); `Qualification.eligibility` optional for `CURATED` until P1.5; `EligibilitySourceRow` (the pre-structuring eligibility row with the same `rule:` id, no components). `OverlayRow` now reads the evidence columns. `docs/schemas.md` regenerated. The overlay has no `evidence_class`/`evidence_id` columns; evidence class is assigned by the build rule, never from the overlay's say-so.
  - **Conflicts and leads:** `conflict:OV-036` (N2302 credits 3 vs 5), `conflict:OV-038` (item 10 / totals 14, 14 vs the QF row sum 12, a `RULE_DERIVED` evidence record) and `conflict:OV-040` (DGT/VSQ/N0102 level 3.5 vs 4). No value is selected; the affected `Valued` fields carry `conflict_id`. DQ-03 is the flag `SOURCE_UNAVAILABLE` (`refs=["src:C3"]`) on AMH/Q2301 plus `open_leads` in `build_manifest.json`; the build fails if C3 ever becomes available. DQ-01 and DQ-03 stay unresolved.
  - **Limits:** `VALIDATION.json` is hashed into the build id and listed under `unverified_inputs`; nothing verifies it against an expected hash (P1.1 does not cover it). `approved_qualifications_parsed.csv` is hashed and verified field by field against A1. Catalogue S.No. 27 has a non-ASCII en dash (U+2013) printed in A1 itself: preserved verbatim and flagged `UNCERTAIN_EXTRACTION` (searchability caveat). The PII scan test masks hexadecimal hash runs (a 10-digit run inside a SHA-256 matches the legacy phone regex by chance). Catalogue and title-alias evidence cite a `location`, not a `page` (the catalogue HTML has none; `Evidence` allows page or location). `CURATION_CODE_VERSION` (`p1.4-2`) is bumped by hand.
  - **Final acceptance fixes (third audit, 2026-10-31).** (1) `EligibilitySourceRow` refuses a computing (safe or conditional) row-level `engine_use` unless the row is substantiated: no required text value may be `PARSED_UNCERTAIN`/`UNRESOLVED`, and an uncertain extraction needs its row-level component confirmed by geometry, corroborated or corrected; `audit_hints` are never evidence; the build wraps a refusal as a `BuildError` naming the row. (2) `engine_constraint` is carried on each source row, verbatim, from the decided overlay row on the row's own component (`raw_row_text`; `min_age`); it is separate from evidence and classification, is never interpreted or used to raise `engine_use`, two different texts on one row fail the build, and `SAFE_WITH_CONSTRAINT` requires it. Field-level constraints stay in `audit_hints`. Not yet carried (no consumer before P1.5/P3): constraints on facts-hours (`SAFE_HOURS`), credits (`NOT_USED`) and the pending-proposal experience cells. (3) Q2301/E1 stays `UNKNOWN` at row level: its experience component is `SAFE_HARD_RULE` (geometry-confirmed), but its academic component and row text remain `PARSED_UNCERTAIN`; AUDIT_NOTE section 5 (local, gitignored) and ARCHITECTURE section 11.4 now say the audit's "safe now" for SSMO row 1 is the experience component only. A stronger classification needs an audit decision that substantiates the academic component; none was invented and no overlay was approved. `CURATION_CODE_VERSION` is `p1.4-3`.
  - **Audit fixes (second review, 2026-10-31).** **L10:** every `CONFIRMED_BY_GEOMETRY`/`CORROBORATED` upgrade now passes `_overlay_source()` (same source as the row, cited page within the row's page and the document, non-empty location and method), a second upgrade row on one cell fails, and the cell's evidence is a separate record carrying the overlay's own method, location and page (`Builder._upgrade_evidence`); a `source_value` that differs from the extraction is rejected earlier by `check_source_value` (`TargetError`). **M5:** `curation/catalogue_source.py` re-parses A1's HTML table (stdlib) and the build fails (`BuildError`) unless all 37 catalogue rows agree with it on S.No., name, code, NQR, version, level, hours, credits and CCN (whitespace-collapse only; an en dash is compared as an en dash); the CSV moves from `unverified_inputs` to `verified_derived_inputs`, and catalogue evidence uses method `html_table_parse_verified`. The QP-title alias cannot be checked against the PDF (no PDF reader is a project dependency), so it no longer has an OFFICIAL evidence record: `titles.qp` is kept with a `TITLE_VARIANT` CAUTION flag (`refs=["src:B1"]`) that says it is not independently verified; the build also requires `VALIDATION.json`'s B1 file hash to equal the manifest's. The S.No. 27 en dash is in A1 itself and is no longer called an encoding artifact. **M2:** the effective row-level `engine_use` is the use of the row's own component (`raw_row_text`, or `min_age` for the age row), enforced by the `EligibilitySourceRow` model (a safe row use requires the same use on that component); a decision the overlay states about another field (OV-001's experience cell) is kept in `audit_hints` and authorizes nothing. Q2301/E1 is now `UNKNOWN`; its experience cell stays `SAFE_HARD_RULE` and no other row changed. Rows are not capped by their academic/experience cells: the audit's explicit row-level decisions on `raw_row_text` (20 rows) are kept. **M3:** OV-033 is recorded only (generated claims always have `resolved_target = null` and are `DISPLAY_ONLY` per ARCHITECTURE sections 9.2 and 11; the overlay's `NOT_USED` describes the absent relationship, not the claim text); the always-passing guard was removed. Earlier-round fixes (proposal `engine_use` never reaches output, contiguous OV-001..052, merged-cell substantiation, unmatched conflict targets, credit groups only for approved `PROPOSED_REPRESENTATION`) remain. `CURATION_CODE_VERSION` is `p1.4-2`; the real build is `cb-0e76c97bea00` (older `cb-4ff16acc3b27` (`p1.4-1`) and `cb-744256fa29dc` (`p1.4-2`) may remain in the ignored `data/curated/`). **Still open:** the QP title alias and the NCO titles rest on `VALIDATION.json`, which has no expected hash (NCO titles are cross-checked against the DGE HTML; the alias is not checked against the PDF); catalogue/alias evidence has a `location`, not a `page`; seven evidence records (six CORROBORATED Q2101 totals) are validated but referenced by no curated field.
  - **Verification (2026-10-31):** full suite 654 passed; `verify-sources` exit 0 (18 of 18 local files matched, 4 `NO_LOCAL_FILE`); `tools/gen_schema_docs.py --check` exit 0; `pip check` no broken requirements; legacy baseline `MATCH`, 23 passed, 1 failed, DQ-01 unresolved. This is not a passing suite. `config/overlay_approvals.yaml` is still `approved: []`.

### P1.5 — Eligibility rule structuring and human review file · MUST · DONE (7f43f66, 2a65abd)

- **DONE (2026-10-31, engineering acceptance):** acceptance criteria met by the committed work; the one-time review took place and C-4 was ruled with its limitation. Documented exceptions remain open and unresolved: A2 (Q-2), P1.5-R1, Q0301/E5 `ENGINE_USE_UNDECIDED`, Q2301/E1#c1 (closure items E5–E8). DONE here means the engineering criteria are verified and committed; it does not resolve or approve any evidence item. See the Phase 1 closure assessment.

- **Objective:** translate the 24 eligibility rows and 4 age rows into structured components (ARCHITECTURE §11.2), strictly following the overlay's `engine_use` and `engine_constraint` and decisions D2–D5.
- **Dependencies:** P1.4; Q-3 and Q-4 (defaults apply if undecided).
- **Deliverables:** `src/skillgraph/curation/eligibility_rules.py`; `data/curated/<build_id>/eligibility_rules_review.md`, a table per qualification with the verbatim row text → components → engine use → overlay IDs → unresolved parts.
- **Acceptance criteria:**
  - Each of the 24 rows maps to ≥ 1 component.
  - Rows with `engine_use = UNKNOWN` contain an `UNMODELLED` component with a reason code: SMO rows 2 and 5; SSMO rows 2–6. **Documented exception (exactly one row): SSMO row 1, `rule:AMH/Q2301/E1`.** It is `UNKNOWN` at row level (verified P1.4 output, ARCHITECTURE §11.4) but has no unmodellable text. The test asserts the set of `UNKNOWN` rows is exactly {Q0301/E2, Q0301/E5, Q2301/E1, E2, E3, E4, E5, E6}; that every one of them except `Q2301/E1` has at least one `UNMODELLED` component; and that `Q2301/E1` has `#c1` = `SCHOOL_GRADE_MIN` grade 11 (not safe, `UNCERTAIN_EXTRACTION`: its academic cell is `PARSED_UNCERTAIN`) and `#c2` = `EXPERIENCE_MIN_YEARS` years 0.0 (safe: its cell is geometry-confirmed `SAFE_HARD_RULE`, OV-001). The exception is not extended to any other row without new evidence (decisions P1.5-D1/D2).
  - Rows needing relevance carry `requires_relevance = true`.
  - Rows using "Level X" carry `PRIOR_NSQF_LEVEL` with no embedded interpretation.
  - "or equivalent" rows carry `or_equivalent = true`: PS rows 1 and 3.
  - SMO row 1 "Grade 9" is stored verbatim, with the decision D5 constraint.
  - SSMO row 5 is stored verbatim with `REVIEW_FLAG` (decision D4).
  - A test asserts that no component type exists for equivalence, exemption, RPL or reduced hours.
  - **You review `eligibility_rules_review.md` once.** Corrections go through config or the overlay, never through code constants.
- **Effort:** 4–6 h, plus your review time.
- **Decisions (2026-10-31; ARCHITECTURE §20.2):**
  - **P1.5-D1:** SSMO E1 is `UNKNOWN` at row level and is not upgraded.
  - **P1.5-D2:** a component inside an `UNKNOWN` row may stay evaluable only if it is independently supported by its own cell (text, evidence, classification). A component never raises its row's `engine_use`; a safe component does not make the row safe; `UNKNOWN` parts stay `UNKNOWN`/`UNMODELLED`.
  - **P1.5-D3:** `component_id` and `requirement_text` are derived downstream, not stored in the model. `component_id` = `<source row id>#c<n>`, n = 1-based position (academic cell first, then experience; the age row has `#c1`), as in API_SPEC §2.4/§2.5.
  - **P1.5-D4:** structured rules are stored in `Qualification.eligibility`; `eligibility_source_rows.json` stays unchanged as the provenance record.
  - **P1.5-O1:** new `UnknownReasonCode` `ENGINE_USE_UNDECIDED` for a parsed (not uncertain) requirement whose engine use is undecided: SMO row 5 experience stays verbatim (5 years, relevant), not safe. Literacy stays `UNMODELLED` / `LITERACY_NOT_MODELLED`.
  - **P1.5-O2:** DQ-09 does not override ARCHITECTURE §11.3.1/§11.4; experience cells of uncertain rows stay capped until individually substantiated. **Audit review requested (request only; no overlay row, evidence or classification created or changed):** `Q2301/E5`, `Q2301/E6`, `Q0301/E2`, `Q0301/E5` experience cells.
  - **P1.5-O3:** params `grade` (int), `credential` (`UG_DIPLOMA`/`UG_CERTIFICATE`), `below_required_verdict` (only `UNKNOWN`, SMO row 1), `years`/`level` floats, `min_age` int.
  - **P1.5-O4:** "12th or Equivalent" is `SCHOOL_GRADE_MIN` grade 12 with `or_equivalent`; below the threshold stays `UNKNOWN` (`EQUIVALENCE_UNDEFINED`, Q-3 default).
  - **P1.5-O5:** `or_equivalent = false` on SSMO row 6's `UNMODELLED` component (no effect there); `or_equivalent` rows remain PS rows 1 and 3.
  - **P1.5-O6:** `overlay_ids` lists decided overlay rows only; pending proposals appear in `OVERLAY_PENDING_APPROVAL` flag refs. OV-002…004 stay unapplied.
  - **P1.5-O7:** verbatim cell text is canonical; one component per printed cell; `requirement_text` is derived downstream.
- **Checkpoint B tests (specified here, not implemented; synthetic fixtures plus the real build):**
  1. *Component count and order.* Each of the 24 eligibility rows yields exactly 2 components, `#c1` from the academic/skill cell and `#c2` from the experience cell; each age rule yields exactly 1 (`#c1`). 52 components in total; ids are `<row id>#c<n>`, unique, 1-based.
  2. *Verbatim round trip.* For every eligibility row `cell₁ + " || " + cell₂ == rule.raw_text` (byte for byte), and each component's configured `text` equals its source cell; splitting `raw_text` once on the first `" || "` returns both cells.
  3. *Empty cells.* `Q2301/E2–E4` keep `raw_text` ending in `" || "` (trailing space preserved, no trimming); the second component is `UNMODELLED` with `OVERLAY_NOT_APPROVED`, its cell text is `""`, and no `years` param exists. A synthetic row with an empty academic cell fails closed (that case is not specified).
  4. *Delimiter safety.* A synthetic cell containing `" || "` makes the parse fail (no silent mis-split); no real cell contains it.
  5. *Stale table.* A changed source cell, row text, `engine_use` or an unknown row id makes the build fail (`expect` guards).
  6. *`safe` / `unknown_reason`.* For every component: `safe = false` ⇒ `unknown_reason` non-null; `safe = true` ⇒ null; a configured reason is dropped only when the computed `safe` is true; a computed-unsafe component with no configured reason fails the build; `UNMODELLED` is never safe.
  7. *`requires_relevance`.* It is a component field; no stored `params` contains the key; it is true exactly for `PRIOR_NSQF_LEVEL` components and for experience components whose cell says "relevant"; it is false for "No Experience required" and for every other type.
  8. *Pending overlays.* OV-002…004 are absent from every `rule.overlay_ids` and present in the `OVERLAY_PENDING_APPROVAL` flag refs; `config/overlay_approvals.yaml` is read-only `approved: []`; a cell with `CORRECTION_APPLIED` makes the parser fail closed (P1.5-A2).
  9. *No upgrade.* No component is safe unless its configured `safe_from` source is a computing, substantiated use; no rule's `engine_use` differs from its source row's.
  10. *Absent types.* `ComponentType` has exactly six members; none for equivalence, exemption, RPL or reduced hours; `or_equivalent` is true exactly on `Q2101/E1` and `E3`.
  11. *Age rule `raw_text`.* Specified as blocked on P1.5-A1; after A1 (below) it asserts the age rules are built from the verbatim text and its own evidence.
- **Open after Checkpoint C:** Checkpoint D (the review file and its real-data review) and, only if Q-2 is ever decided, P1.5-A2 (ARCHITECTURE §20.2).
- **Checkpoints:** **A** decisions, documentation and `config/eligibility_rules.yaml` (the row-by-row proposal, not yet loaded by any code); **B** `eligibility_rules.py` (parser, unit tests); **C** build wiring (`Qualification.eligibility`, `CURATION_CODE_VERSION` bump, `data_build_id` changes; implemented 2026-10-31, see Status); **D** `eligibility_rules_review.md` and real-data tests; **E** close-out.
- **[Historical — superseded by the DONE marking above and the Phase 1 closure assessment.]** **Status (2026-10-31):** **Checkpoints A (decisions, documentation, table), B (the structuring layer) and C (build wiring) are implemented; Checkpoint D (the review file) is generated and awaits your review; Checkpoint E (close-out) has not started.** `config/eligibility_rules.yaml` maps all 28 source rows (24 eligibility + 4 age; 52 components) and is loaded by the build; the O1–O7 decisions are applied to it. The model change is the `ENGINE_USE_UNDECIDED` enum member (model, API_SPEC §2.1, `docs/schemas.md`). The review file is `data/curated/cb-601c0399c999/eligibility_rules_review.md`: a **snapshot for that build**, generated once and not regenerated automatically (the directory is gitignored). P1.4 and P1.5 are not DONE. `config/overlay_approvals.yaml` is still `approved: []`; DQ-01 and DQ-03 are untouched.
  - **Checkpoint B (2026-10-31):** `src/skillgraph/curation/eligibility_rules.py` loads and validates `config/eligibility_rules.yaml`, then structures the P1.4 `eligibility_source_rows.json` into `EligibilityRow` components, fail-closed (stale table, cell/join mismatch, delimiter in a cell, unknown enum or parameter type, applied correction, unsupported age rule). At Checkpoint B it was a pure layer that `build` did not call (build identity and curated files unchanged, asserted then); **Checkpoint C (below) wired it into the build.** Tests: `tests/unit/test_eligibility_rules.py` (synthetic, plus the repository table) and `tests/integration/test_eligibility_rules_real.py` (real source rows from a temporary build); they implement the 11 tests above (test 11, updated after A1, asserts the four age rules are built from the verbatim text and their own evidence; the blocked path stays covered by the synthetic tests).
  - **P1.5-A1 resolved by authorization (Option 1, applied in the builder, 2026-10-31):** the four printed age lines were verified visually in the QF PDFs (SMO p.4, SSMO p.4, Inline Checker p.3, PS p.4) and the P1.4 builder now carries each `AGE_9C` row's verbatim line as `raw_row_text` (`"Age: 18 years"` ×3, `"Age: 20 years"`; the item label "c." is excluded) with its own evidence record (`TRANSCRIBED`, `regex_line`, not geometry-confirmed, `engine_use` `UNKNOWN`). `min_age` and its geometry evidence (OV-028..031) are unchanged. Because that changed the output, the code version was bumped at Checkpoint C (`p1.5-1`); the build `cb-0e76c97bea00` (`p1.4-3`) is untouched and the new build is `cb-601c0399c999` (the build refuses to install different content under an existing id).
  - **[Historical — superseded by the DONE marking above and the Phase 1 closure assessment.]** **Checkpoint C (2026-10-31): implemented, awaiting review; P1.5 is not DONE.** `build()` loads `config/eligibility_rules.yaml`, structures every source row with `structure_all`/`assemble_specs` (`build.structure_eligibility`) and stores the result in `Qualification.eligibility` of the four curated qualifications (24 rows + 4 age rules; catalogue-only qualifications stay empty). `CURATION_CODE_VERSION` is `p1.5-1`; the SHA-256 of the validated table (`eligibility_rules_digest`, location- and comment-independent) is part of `data_build_id` and the manifest. The real build is **`cb-601c0399c999`** (installed under `data/curated/`, which is gitignored); the p1.4-3 build `cb-0e76c97bea00` is never rewritten, and the existing guard still refuses different content under an existing id. Fail-closed cases (all abort the build and install nothing): invalid, stale or incomplete table (including a mapping without a source row or the reverse); a cell text that differs from the table; an applied correction on a used cell (P1.5-A2, `CorrectionNotSupported`); a missing age text; an unsafe component without a reason; any `EligibilityRulesError`. API projection: `project_rule`/`project_spec` give the static response view (component ids, verbatim requirement text, params with `requires_relevance` only when true, evidence ids); `safe`, `or_equivalent`, the stored `unknown_reason` and component `engine_use` are not exposed; verdicts belong to P3. Tests: real-data `test_c1`–`test_c9`, synthetic identity and fail-closed tests; the synthetic fixtures generate their own table (`SynthTree.rules_table`), and the P1.4 tests that apply a correction to an eligibility cell run with the `p14_only` fixture (a test-only stub, no production switch). **Not done:** Checkpoint D (`eligibility_rules_review.md` and your review), the evaluation engine (P3), the four P1.5-R1 cells (audit request only), DQ-01 and DQ-03.
  - **Still blocked:** P1.5-A2 (applied corrections raise `CorrectionNotSupported`). It is not worked around. (Checkpoint C build wiring is implemented; see its status above.)
  - **Checkpoint B hardening (2026-10-31, independent review):** the structuring layer was reviewed adversarially and tightened; no model or provenance change. (1) Every public function re-validates its row and table entry (`model_copy`/`model_construct` skip validators). (2) The table must agree with the text it quotes (type↔cell, grade/years/level/credential/`requires_relevance`/`or_equivalent`/D5 against the verbatim cell; unrecognised experience wording is refused). (3) `SAFE_HOURS` never makes an eligibility component safe. (4) `safe_from: row` also requires the row-level component itself to be certain. (5) Non-finite numbers, duplicate YAML keys and a non-`OPEN_REQUEST_ONLY` audit request are rejected; `requires_relevance` can never be a stored param. Each has a regression test, and each check was removed in turn to confirm a test fails.
- **P1.5-A1 decision memo (the investigation; superseded by the resolution above: the printed lines were then verified visually).**
  - *Source:* the four QF PDFs named by OV-028..031, each at the page of the geometry-confirmed age line (SMO p.4 `amhssc/qf/Q FILE Sewing Machine Operator.pdf`, SSMO p.4 `…Specialized Sewing Machine Operator(1).pdf`, Inline Checker p.3 `nqr/qf/Q FILE Inline Checker Sewing Version 4.0.pdf` and its secondary copy, PS p.4 `…Production Supervisor- Sewing V4_0.pdf`). The local files exist and their hashes equal the extraction's `source_sha256`.
  - *Text:* the extraction records `raw_row_text` "Age: 18 years" (PS: "Age: 20 years"), method `regex_line`, status `TRANSCRIBED`. **I could not verify the printed wording independently**: no PDF library or renderer is installed and the content streams are CID-encoded. The text is the extractor's capture only. It must not be inferred from the API_SPEC example.
  - *Existing evidence:* only for the `min_age` value (OV-028..031, `CONFIRMED_BY_GEOMETRY`, class `OFFICIAL`, e.g. `ev:8a6c77aa46c0cce6`, `src:B2`, location "item 9c age line"). **No evidence record exists for the text cell.** `EligibilitySourceRow` for `AGE_9C` carries `min_age` only.
  - *Official and direct:* yes for the value (QF document of the issuing sector council or NQR); for the text, not yet substantiated.
  - *Proposed (needs authorization; provenance change):* P1.4 carries the age row's `raw_row_text` as a `Valued` cell and emits its own evidence record (same source, page and sha256, method `regex_line`), or an audit decision extends the geometry confirmation to the line. Then `AgeRule.raw_text` is that verbatim text. Until then, no age rule is built.
  - *Minimum information needed:* a one-time confirmation (by you or the audit, or a PDF text tool you approve) that the four printed lines read exactly as extracted, and your choice between the two routes above. *(Resolved afterwards: see above.)*
- **Checkpoint C plan (plan only; not started, nothing wired).**
  1. *Entry point.* `Builder.qualification()` in `curation/build.py` calls `eligibility_rules.assemble_specs(source_rows, config)` after the P1.4 source rows are built and before the manifest is written; the returned `EligibilitySpec` becomes `Qualification.eligibility`. The module stays pure; `build.py` supplies the rows and the loaded table. `eligibility_source_rows.json` is still written unchanged.
  2. *Age rules.* Built only by `structure_age_rule` after A1 is authorized and the source row carries the verbatim text and its evidence; `assemble_specs` refuses without them (`AgeRuleBlocked`); with A1 applied the four age rules build.
  3. *IDs and determinism.* Component ids are `<rule id>#c<n>`; order follows `_order`; `config/eligibility_rules.yaml` is added to the build inputs and its hash to `data_build_id` and the manifest; `CURATION_CODE_VERSION` bumps to `p1.5-1`, so the build id changes by design. Two builds from the same inputs give byte-identical `qualifications.json`.
  4. *Fail closed.* Any `EligibilityRulesError` (stale table, source/text mismatch, `CorrectionNotSupported`, `AgeRuleBlocked`) aborts the build as a `BuildError` naming the rule; no partial output is kept; an approved correction on a used cell fails until A2 is decided.
  5. *API projection.* `response_params` and `check_component_invariant` are applied when the API builds `RowResult`/`ComponentResult` (`requires_relevance` projected only when true; `or_equivalent` not projected; `component_id` and `requirement_text` derived). The stored model is unchanged.
  6. *Tests.* End-to-end real build (marked `requires_local_data`): all 24 + 4 rules present, 8 `UNKNOWN` rows as specified, IDs and bytes stable across two builds, unchanged protected inputs; fail-closed tests (stale table, missing text, applied correction, `approved: []` unchanged, no pending overlay in `overlay_ids`).
  7. *Baselines.* Existing builds under `data/curated/` are not rewritten; `tools/check_legacy_baseline.py` must still report MATCH, 23 passed, 1 failed (DQ-01 unresolved); this is a documented baseline, not a passing suite.
  8. *Stays blocked.* Installing the A1 build (the version bump); applied corrections on A2; the four cells of P1.5-R1 stay capped; DQ-01 and DQ-03 untouched.

### P1.6 — Validation report, known-findings register and known-deviations tests · MUST · DONE (2a65abd)

- **DONE (2026-10-31, engineering acceptance):** acceptance criteria met by the committed work. Documented exceptions: DQ-10 and DQ-13 are `NOT_MACHINE_CHECKED`; DQ-01/02/03 remain registered as unresolved. DONE here means the engineering criteria are verified and committed; it does not resolve or approve any evidence item. See the Phase 1 closure assessment.

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
- **[Historical — superseded by the DONE marking above and the Phase 1 closure assessment.]** **Status (2026-10-31):** implemented, **uncommitted, awaiting your review; not marked DONE**. `python -m skillgraph validate` (`src/skillgraph/curation/validate.py`) validates the newest installed build of the current code version (or `--build-id`) and writes `validation_report.json` into it (canonical JSON, no timestamp). Checks: build completeness and output hashes, model validation of every record, referential integrity, counts recomputed from the extraction tables (DQ-11) against the curated files and the build manifest, structured-rule completeness, the audit status counts (56/3, 49/8, 53/1, 53/8; all six tables, `QF_SECONDARY` excluded; they matched without adjustment), seven cross-document checks, the findings register and unavailable sources. `--rerun-legacy` additionally runs `tools/check_legacy_baseline.py`; by default the documented baseline is quoted as "23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)" with `is_passing_suite: false`.
  - **Registers:** `config/known_deviations.yaml` holds three UNRESOLVED entries: `KD-001` (DQ-01, `qf_nos_credit_sum_vs_item10`, observed exactly as specified above), `KD-002` (DQ-01, `nos_credits_qf_vs_qp`, N2302 QF 3 vs QP 5) and `KD-003` (DQ-02, `nos_level_qf_vs_qp`, DGT/VSQ/N0102 QF 3.5 vs QP 4). KD-002 and KD-003 exist because those are separate validation checks that would otherwise report an unregistered discrepancy; the register schema is the specified one. `config/known_findings.yaml` holds DQ-01…DQ-15 and the audit status counts. The `status` words of DQ-05…DQ-15 (`RECORDED_DISPLAY_ONLY`, `PENDING_APPROVAL`, `UNCERTAIN_EXTRACTION_CAPPED`, `RECOMPUTED_BY_VALIDATION`, `SOURCE_UNAVAILABLE`) are descriptive labels chosen here, not decisions; no finding is resolved, accepted or waived.
  - **Finding presence:** 13 of 15 findings are confirmed against curated records; **DQ-10 and DQ-13 have no curated record and are reported `NOT_MACHINE_CHECKED`** rather than claimed present.
  - **Tests:** `tests/unit/test_validate.py` (the rule and the loaders, no data needed) and `tests/golden/` (`requires_local_data`): the register matches the real observations exactly; extra discrepancy, changed value and vanished discrepancy each fail (in-memory mutation of the real tables, never on disk); an audit-count difference fails.
  - **Fail-safe (final review):** a missing/malformed manifest key, non-numeric cell or missing file raises `ValidationConfigError` (CLI exit 3); `inputs_match_build` re-hashes every input recorded in the build manifest (a stale build fails); `output_hashes` always runs; the report is written atomically and is the only file written; a finding status claiming resolution/acceptance is refused by the loader. `tests/golden/test_validate_failsafe.py`.
  - **DQ-10 / DQ-13 (decided by inspection):** ARCHITECTURE 8.6 treats both as display-only; DQ-10 is a meaning question about a catalogue column (legacy `reconciliation.json` `SEMANTIC_AMBIGUITY`), DQ-13 is prose in `ACQUISITION_REPORT.md` section 7 (the dates are in no extraction table). No requirement asks for a curated record and adding one would invent data, so they stay `NOT_MACHINE_CHECKED`. DQ-14's check covers only the unavailable-source part (C3/C4), not the C1/C2 missing-level part.
  - **Known limits:** the report does not re-verify source hashes (`verify-sources` does). The legacy suite is quoted, not re-run, unless `--rerun-legacy`.

- **Effort:** 4–6 h.

**Phase 1 definition of done:**

- `verify-sources → build → validate` succeeds on the real local data.
- All Phase 1 tests pass.
- No source file was modified (hash check).
- Unresolved issues remain explicitly unresolved.

### Phase 1 closure assessment (2026-10-31; the single authoritative list)

State: engineering for P1.1–P1.6 is implemented in the working tree. What remains is review, evidence decisions and acceptance. Nothing below was resolved by assumption.

| ID | Class | Status (verified) | Blocks P1? | Minimum safe resolution | Verification |
|---|---|---|---|---|---|
| C1 | Acceptance | **Engineering sign-off given (2026-10-31):** P1.1–P1.6 accepted as engineering-implemented, subject to the documented acceptance criteria (see the sign-off block below). **Committed 2026-10-31** (`7f43f66`, `2a65abd`; earlier stages `1a1e843`, `771675e`, `4c18e0d`, `abcdd27`); P1.1–P1.6 marked DONE as engineering stages. | Closed | None; "P1 COMPLETE" is not declared while the evidence gates stay open. | `git log` |
| C2 | Acceptance | **Done (2026-10-31):** the one-time review of `eligibility_rules_review.md` took place; its outcome is the C-4 ruling (E7) with its limitation, and nothing else in the file was approved. The file is a snapshot of `cb-601c0399c999`, reconciled with the build (52 components, 37 safe / 15 not, 449 evidence records, same digests); it is gitignored and not regenerated automatically. | Review criterion met; P1.5 DONE still depends on C1 | None further; corrections go through config or the overlay. Automatic regeneration is not a P1 requirement (documented, not built). | Read the file; counts above. Age-table headings clarified 2026-10-31 (documentation only) |
| E1 | Evidence | DQ-01 unresolved (KD-001, KD-002). | No (credits are `NOT_USED`) | A source-backed decision per baseline §5. | `validate` fails with "resolution review required" when it changes |
| E2 | Evidence | DQ-02 unresolved (KD-003, OV-040). | No (`DISPLAY_ONLY`) | A source-backed level decision. | same |
| E3 | Evidence | DQ-03 open lead; source C3 unavailable. | No | Obtain C3 or record a decision; the build fails if C3 becomes available. | `build` |
| E4 | Evidence | OV-002…004 and OV-034/035 pending; `config/overlay_approvals.yaml` is `approved: []`. | No | Explicit approval entries backed by evidence. | `build` manifest `overlays.pending` |
| E5 | Evidence | P1.5-A2: applied corrections raise `CorrectionNotSupported`. | No (no correction is approved) | A Q-2 decision and a correction-to-component mapping. | `tests/unit/test_eligibility_rules.py` |
| E6 | Evidence | P1.5-R1: audit review requested for `Q2301/E5#c2`, `Q2301/E6#c2`, `Q0301/E2#c2`, `Q0301/E5#c2`. Request only. | No | An audit decision per cell. | config `OPEN_REQUEST_ONLY` |
| E7 | Evidence | **C-4 — ruled 2026-10-31, with a limitation (see below).** Recomputed independently from the installed build `cb-601c0399c999`: 32 safe components in 16 rows (Q0103 E1–E4: 8; Q0301 E1, E3, E4, E6, E7: 10; Q2101 E1–E4: 8; Q2301 E7–E9: 6), each safe through a row-level `INTERPRETATION_DECIDED` decision on `raw_row_text` (OV-005, 007, 008, 010, 011, 017–027) while its cell evidence is `TRANSCRIBED`. | No | Ruled; an upgrade of any cell needs the authorized evidence process. | review file §2–3 |
| E8 | Evidence | `ENGINE_USE_UNDECIDED` (Q0301/E5) and Q2301/E1#c1 stay fail-closed. | No | Audit decisions. | `tests/integration/test_eligibility_rules_real.py` |
| D1 | Documentation | `VALIDATION.json` has no expected hash (`unverified_inputs`); QP title alias not checked against the PDF; seven evidence records are referenced by no curated field. | No (known limitation) | Out of P1 scope unless you require it. | `build_manifest.json` |
| D2 | Documentation | DQ-10 and DQ-13 have no curated record, so presence cannot be machine-checked. | No | Add a curated record if you want them tested. | `validate` report |

**Phase 1 acceptance matrix (2026-10-31, final review).** Legend: **EC** engineering complete and verified; **EB** evidence/approval blocked; **KL** known limitation permitted by the criteria; **AQ** acceptance question.

| Stage | Criterion | Evidence / verification | Status |
|---|---|---|---|
| P1.1 | Verifier re-hashes sources; tamper fails; runs before every build | `verify-sources` exit 0 (18 matched, 4 no local file); `tests/integration/test_integrity.py`; `build` calls it first | EC; DONE awaits your review (AQ C1) |
| P1.2 | Source-of-truth models; docs match models | `tools/gen_schema_docs.py --check` exit 0; `tests/unit/test_model_*` | EC |
| P1.3 | Overlay approval mechanism; `approved: []` untouched | `tests/unit/test_overlay.py`, `test_overlay_real.py`; file hash unchanged | EC; OV-002/003/004/034/035 pending (EB) |
| P1.4 | 8 criteria + 3 "after a build" criteria; deterministic; fail-closed | `tests/integration/test_build*.py`; rebuild reuses `cb-601c0399c999`; inputs hash-identical | EC; KL: `VALIDATION.json` unverified, alias not PDF-checked |
| P1.4 | Legacy baseline reproduces | `tools/check_legacy_baseline.py`: MATCH, 23 passed, 1 failed (DQ-01) | Baseline only, not a passing suite |
| P1.5 | 24 rows, 4 age rules, 52 components; invariants; fail-closed | `test_eligibility_rules*.py`, review snapshot reconciled with the build | EC for the structuring; EB: A2, R1, E5/E1 stay capped; C-4 ruled (limitation below) |
| P1.5 | "You review `eligibility_rules_review.md` once" | reviewed 2026-10-31; C-4 ruled with limitation | Met (C2); DONE applied after commit (C1) |
| P1.6 | `validate` + `validation_report.json`; independent counts; audit counts 56/3, 49/8, 53/1, 53/8; no legacy-pass claim | `skillgraph validate` exit 0; `tests/unit/test_validate.py`, `tests/golden/` | EC |
| P1.6 | Known-deviations rule: extra / changed / vanished each fail | `tests/golden/test_known_deviations.py`, `test_validate_failsafe.py` | EC |
| P1.6 | DQ-01..15 asserted present with recorded status | 13 machine-confirmed; DQ-10 and DQ-13 `NOT_MACHINE_CHECKED` (above) | EC / KL |
| Phase 1 DoD | `verify-sources -> build -> validate` succeeds | all three exit 0 on the real data | EC |
| Phase 1 DoD | All Phase 1 tests pass; no source file modified | full suite; before/after hashes of `data/raw` and `data/processed` | EC |
| Phase 1 DoD | Unresolved issues remain unresolved | DQ-01/02/03, OV pending, A2, R1, Q0301/E5, Q2301/E1#c1 all unchanged; C-4 ruled, evidence unchanged | EC (the remaining items are EB, none waived) |

**Sign-off and rulings (2026-10-31).** Recorded here only; no evidence, provenance, audit history, safety classification, overlay approval or curated output was changed by recording them.

- **C-4 ruling, with its limitation (user ruling).** The 32 safe components in the 16 rows above may keep their current conditional classifications on the strength of the documented row-level audit decisions. **This is not cell-level geometry confirmation.** Their cell evidence stays `TRANSCRIBED` unless it is separately upgraded through the authorized evidence process. The ruling approves no overlay and upgrades no evidence. It does not apply to the 4 age rules (value geometry-confirmed, printed text `TRANSCRIBED`) or to Q2301/E1#c2 (cell geometry-confirmed by OV-001, row still `UNKNOWN`).
- **Engineering sign-off (user).** P1.1–P1.6 are accepted as engineering-implemented, subject to the acceptance criteria in this document. This is **engineering acceptance, not approval of any pending evidence decision.**
- **Not decided by either item (unchanged):** Q-2 (OV-002/003/004, OV-034/035), A2 corrections, P1.5-R1 (`Q2301/E5#c2`, `Q2301/E6#c2`, `Q0301/E2#c2`, `Q0301/E5#c2`), Q0301/E5 `ENGINE_USE_UNDECIDED`, Q2301/E1#c1, DQ-01, DQ-02, DQ-03. `config/overlay_approvals.yaml` is `approved: []`.
- **Engineering acceptance versus the Phase 1 definition of done.** The definition below asks for: `verify-sources → build → validate` succeeding on the real data, all Phase 1 tests passing, no source file modified, and unresolved issues remaining explicitly unresolved. It therefore **permits** engineering acceptance with the documented unresolved evidence items as exceptions; it does not require them to be resolved. Each of its four conditions has verification evidence in the matrix above. The two administrative items that remain are the commit (C1) and whether the DONE markers are applied; after the commits the P1.1–P1.6 stage markers were set to DONE as engineering stages, and this document still does not declare "P1 COMPLETE" while the evidence gates are open. The legacy suite result (23 passed, 1 failed, DQ-01) is a documented baseline, not a passing suite.

**Not engineering blockers:** Checkpoint E (P1.5 close-out) defines no further work beyond this table and the status reconciliation; the evaluation engine is P3.

---

## Phase 2 — Labour-market data feasibility (Module A gate) · time-boxed, parallel

**Time-box:** at most 2 working days of effort, excluding any wait for access. **Any download needs your approval.** Downloads go to a new run folder, `data/labour/raw/<date>/`, with a manifest, following the 2026-10-30 discipline.

**Phase 2 status (2026-11-01, run 2; uncommitted).** No task below is marked DONE: each needs your acceptance. **P2.1** inventory, **P2.2** terms review (`module_a_sources.md` §H) and **P2.3** variable check (`module_a_variables.md`) are produced and awaiting acceptance. **P2.4 was not executed**: no PLFS microdata file has been obtained (its stated condition, "only if files were obtained", is not met). **P2.5** is produced (`docs/decisions/MODULE_A_GATE.md`): **`NO_GO`**, from FG-1 `FAIL` and FG-2 `FAIL` (FG-3 to FG-8 `UNKNOWN`), recorded in `config/labour_market.yaml`; awaiting acceptance; its "a test greps the analysis outputs and the frontend strings" criterion cannot be built yet (no such outputs or frontend exist) and carries to Phases 4–5. **P2.6 is deferred** (needs `GO` or `GO_REDUCED`). Phase 2 is **not declared complete**; the Phase 2 stopping rule ("If `NO_GO`, Phase 2 stops there") applies once P2.5 is accepted. No labour-market statistic exists in the repository. The Phase 1 evidence gates are unchanged. **Task 1A (2026-11-01):** PLFS monthly-2025 files were later found outside the repository and assessed read-only in `docs/feasibility/existing_plfs_files_assessment.md`; the P2.5 decision and all statuses are unchanged, and their official acquisition and reuse terms are not established.

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

**Phase 3 status (2026-11-01 to 02, runs 3–9; uncommitted).** **P3.1 (registry loader), P3.2 (verdict logic and component evaluators), P3.3 (eligibility evaluator and pilot golden cases), P3.4 (static graph edges) and P3.5 (experimental inference edges) are implemented and verified (below); P3.3's criteria 1 and 2 are PROVISIONAL on the open decision Q-B, and P3.4 is accepted with exceptions (the legend wording for three edge types is reviewed but not approved, and one additive `SHARES_NOS` attribute awaits a documentation amendment; see P3.4 and `docs/decisions/P3_4_CLOSEOUT.md`).** P3.5 is accepted with exceptions (its P3.6 invariant criterion and the claim-candidate review file are PROVISIONAL, the legend and attribute wording is drafted and not approved, and the `TITLE_SIMILARITY` edge is not built; see P3.5 and `docs/decisions/P3_5_INFERENCE.md`). P3.6a (the path-enumeration core, `graph/paths.py`) is implemented and verified (run 13, uncommitted; see P3.6); P3.6b and P3.7 to P3.10 are TODO. Phase 3 is **not declared complete**. The engine is graph-only: Module A stays `NO_GO` and nothing in Phase 3 uses a labour-market statistic. The Phase 1 evidence gates are unchanged (Q-2, A2, P1.5-R1, DQ-01/02/03 and the others), and `config/overlay_approvals.yaml` is still `approved: []`.

### P3.1 — Registry loader · MUST · DONE (2026-11-01, run 3; uncommitted)

- **Dependencies:** P1.6.
- **Deliverables:** `src/skillgraph/registry/store.py`, an immutable, indexed in-memory registry (by id, code, slug and NOS code). `registry.load()` refuses an `INVALID` build.
- **Acceptance criteria:**
  - It loads the real build in under 1 s.
  - Lookups by code, slug and id agree.
  - A missing or invalid build raises a typed error that the API later maps to `DATA_NOT_BUILT`.
- **Effort:** 2–3 h.
- **Done (2026-11-01, run 3):**
  - **Code:** `src/skillgraph/registry/store.py` (new) and the re-exports in `registry/__init__.py`. Public surface: `load(build_dir) -> Registry`, `Registry.from_records(...)` (for synthetic registries in later tests), `BuildInfo`, and the errors `BuildNotFoundError` (`build_status == "NOT_BUILT"`), `BuildInvalidError` (`"INVALID"`, with `.problems`) and `UnknownEntityError` (a `LookupError`), all subclasses of `RegistryError`.
  - **What `load` refuses** (`BuildInvalidError`, never a substitute build): a manifest that is unreadable, not `READY`, or whose `data_build_id` differs from the directory; a build from another `curation_code_version` (stale); an output file that is missing, unparsable or differs from its manifest SHA-256; a `validation_report.json` that belongs to another build, is malformed or records a failed check; any record that fails the `skillgraph.model` schemas (extra or missing fields included); a failed `curation.build.check_references`; a duplicate id or code, a slug collision or a dangling NOS, conflict or eligibility-row reference; and manifest counts that differ from what was loaded. A missing directory or missing `build_manifest.json` raises `BuildNotFoundError`.
  - **Indexes:** qualification by id, code and slug; NOS unit by id, code and slug; occupation by id and NCO code; evidence, source, conflict and eligibility source rows by id; reverse `qualification_ids_with_nos`. NOS units are shared (two of the 22 in the real build are listed by several qualifications), so the NOS lookup returns every qualification that lists the unit, ascending. Lookups are exact and case-sensitive.
  - **Immutability:** `Registry` rejects assignment, has no mutator and keeps private tuples and read-only mappings. The frozen models still hold lists and dicts, so every accessor returns a deep copy and `from_records` copies its input.
  - **Verification (actual runs, 2026-11-01):** `tests/unit/test_registry_store.py` (41) and `tests/integration/test_registry_load.py` (73) pass; full suite `913 passed, 1 warning` (799 before this run). Load of the real build `cb-601c0399c999` (37 qualifications: 4 curated and 33 catalogue-only; 22 NOS units; 4 occupations; 449 evidence records), best-of-7 timings 18.7–26.0 ms after imports, against the 1 s limit. Replacing `_copy` with identity makes three immutability tests fail (mutation check, then restored).
  - **Policy choices that are mine, not in the specification (for your review):** (1) a build from an older `curation_code_version` is refused (the three older installed builds `cb-4ff16acc3b27`, `cb-744256fa29dc`, `cb-0e76c97bea00` are therefore INVALID to the loader); (2) an absent `validation_report.json` is allowed and shown as `BuildInfo.validation == "NOT_RUN"`, while a report with a failed check is refused; (3) the registry imports `MANIFEST_OUT`, `OUTPUT_FILES` and `check_references` from `curation.build` instead of repeating them. None changes ARCHITECTURE or API_SPEC.
  - **Not covered here:** choosing *which* build to load (the caller passes a directory; "newest of the current code version" selection exists only in the `validate` command), the mapping of these errors to HTTP codes (P3.10, P5.1), and any eligibility, edge, path, ranking or explanation logic.

### P3.2 — Verdict logic and component evaluators · MUST · DONE (2026-11-01, run 4; uncommitted)

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
- **Done (2026-11-01, run 4):**
  - **Code:** `src/skillgraph/eligibility/logic.py` (`and_` = minimum, `or_` = maximum, over the existing `Verdict` and its `rank`; no second verdict type; an empty call raises `ValueError`, a non-`Verdict` operand raises `TypeError`) and `src/skillgraph/eligibility/components.py` (`evaluate_component(component, *, component_id, inputs, nsqf_level_match) -> ComponentOutcome`, with `ComponentInputs`, `HeldQualification`, `InputUsed`, `Condition`, `UnknownReason`, `component_id()`, `ComponentError`). One evaluator per `ComponentType` (`AGE_MIN`, `SCHOOL_GRADE_MIN`, `NAMED_CREDENTIAL`, `PRIOR_NSQF_LEVEL`, `EXPERIENCE_MIN_YEARS`); `UNMODELLED` and every component with `safe = false` return `UNKNOWN` with their stored reason, whatever the profile says. The modules import only `skillgraph.model`, pydantic and the standard library (a test checks the import list).
  - **Contract followed:** ARCHITECTURE §11.1–§11.3 and API_SPEC §2.4 (each rule of the §11.2 table, the Q-3 default, AS-5/Q-9 "at least" for grades, D3 config-unset, D5 `below_required_verdict`). An outcome obeys the P3.3 invariants at the component level: an `UNKNOWN` carries exactly one reason, a `CONDITIONAL` at least one condition, nothing else carries either (enforced by the model). Each outcome keeps the component's own `evidence_id` in `evidence_ids`.
  - **Not done here (P3.3):** row/target aggregation, resolving a `HypotheticalProfile` against the registry, `EligibilityResult`, decisive rules, projection to `ComponentResult`/`RowResult`, golden tests on the real data.
  - **Verification (actual runs, 2026-11-01):** `tests/unit/test_eligibility_logic.py` (1407 passed: the 16 pairs of each of `and_` and `or_` against hand-written tables, commutativity, idempotence, all 64 triples for associativity, all 4- and 5-operand folds) and `tests/unit/test_eligibility_components.py` (217 passed at the time; 248 after the run-5 audit); full suite `2537 passed, 1 warning` (913 before this run; 2568 after the audit). Six deliberate mutations (age `>=` to `>`, config-unset check removed, zero-years shortcut removed, `or_equivalent` branch removed, `and_` using `max`, the unsafe/`UNMODELLED` guard removed) each made at least one test fail; the code was restored. As a no-crash check only (not a golden test), all 52 stored components of the real build `cb-601c0399c999` were evaluated under 312 profile/config combinations without an exception.
  - **Assumptions where the architecture is silent (for your review):**
    - **A-1** `ComponentResult.condition` (API_SPEC §2.4) is singular, but a `CONDITIONAL` prior-level component rests on a relevance declaration *and* the `nsqf_level_match` interpretation (§11.3 item 3). `ComponentOutcome.conditions` holds both (declaration first); `ComponentOutcome.condition` returns the declaration, as the E07 example does, and the CONFIG condition reaches the target-level list in P3.3.
    - **A-2** `below_required_verdict = "UNKNOWN"` (D5) names no reason code. `REVIEW_FLAG` is used, with `resolvable_by = SOURCE_REVIEW` and wording that states the D5 reason.
    - **A-3** The §11.2 table does not branch on `requires_relevance`, so the flag is not used to grant `MET`: a prior level is always relevance-checked, and a required experience above zero years is always `CONDITIONAL`. In the real build the flag is false only on 0-year experience components, which are `MET` by the table.
    - **A-4** `resolvable_by` and the wording of each `UnknownReason` are assigned per code (`INPUT_NOT_DECLARED`, `RELEVANCE_NOT_DECLARED` → `PROFILE`; `CONFIG_UNSET` → `CONFIG`; `EQUIVALENCE_UNDEFINED`, `CREDENTIAL_ORDER_UNDEFINED` → `NOT_RESOLVABLE_FROM_CURRENT_SOURCES`; every stored cause → `SOURCE_REVIEW`). Only the `DIPLOMA_YEAR_NOT_MODELLED` pair appears in the specification (E07 example).
    - **A-5** The evaluator input contract is mine, because no `ProfileState` exists in code: `ComponentInputs` (per target, `None` = not declared) and `HeldQualification` (a code or `ext-…` ref with its already-resolved NSQF level; registry levels are recorded `OFFICIAL`, external ones `DECLARED`). The level interpretation is passed as a plain value rather than `settings.EngineSettings`, so that `eligibility/` imports only `model/` (ARCHITECTURE §6.2). `relevant_prior_qualifications` must refer to declared holdings (API_SPEC §2.3). Params the model leaves open are checked here (`grade` an integer 0–12, `credential` in `UG_CERTIFICATE`/`UG_DIPLOMA`, `years` ≥ 0), and a stored component with a per-evaluation reason, or `safe` inconsistent with `unknown_reason`, is rejected as malformed.
    - **A-6** Tie-breaks inside the §11.2 table: for `NAMED_CREDENTIAL` the `or_equivalent` branch precedes the other-credentials branch (as listed); `OTHER` counts as a held post-school credential; `or_equivalent` takes precedence over `below_required_verdict` (curation forbids both together); holdings that satisfy the level but are not in the declared-relevant list are "declared not relevant".
  - **Contract audit (2026-11-01, run 5): [`docs/decisions/P3_2_AUDIT.md`](docs/decisions/P3_2_AUDIT.md).** P3.2 stays DONE; the acceptance criteria are unchanged. A-1, A-3, A-4 and A-6 audited **PASS**; A-2 and the provenance of a registry level are **NEEDS DECISION** (Q-A, Q-B); P3.1 policies: stale-build refusal and the `curation.build` imports **PASS**, serving a build without a validation report is **NEEDS DECISION** (Q-C). One defect was found and fixed in A-5: the two profile holding lists are independently nullable, but `ComponentInputs` could not say that only one was declared, so an undeclared list could become `NOT_MET`. **Amended contract:** `ComponentInputs.holdings_complete` (default `False`; "no listed holding satisfies" is `UNKNOWN(INPUT_NOT_DECLARED)` unless both lists were declared) and `HeldQualification.level_cap` (a registry level that must not be compared is `UNKNOWN` with the cap's reason; which provenance states cap a level is Q-B). `ComponentOutcome` now also rejects more than one DECLARATION condition and any other condition that is not in `inputs_used`, so a singular `ComponentResult.condition` projection loses nothing. **P3.3 must:** build the target-level `conditions` from `ComponentOutcome.conditions`, set `holdings_complete` only when both lists are declared, set `level_cap` per the Q-B decision, and assert `BuildInfo.validation == "PASSED"` in golden tests. Tests after the audit: logic 1407, components 248 (1655 together); full suite **2568 passed, 1 warning**; a re-run of the no-crash check evaluated the 52 real components under 624 combinations without an exception.

### P3.3 — Eligibility evaluator and golden cases · MUST · DONE as an engineering stage, criteria 1 and 2 PROVISIONAL on Q-B (2026-11-02, run 6; uncommitted)

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
- **Done (2026-11-02, run 6; timebox met; nothing committed):**
  - **Code:** `src/skillgraph/eligibility/evaluate.py`: `evaluate(spec, state, config, registry, *, undecided_level_use=COMPARE) -> EligibilityResult`, plus the profile and result models of API_SPEC §2.3/§2.4 (`ProfileState`, `EngineConfig`, `ComponentResult`, `RowResult`, `QualificationRef`, `ExplanationItem`, `EligibilityResult`). It calls `evaluate_component` (P3.2) for every component and `and_`/`or_` (P3.2) for `AND(age, OR(rows))`; no component logic is repeated (a test checks it). It imports only `model/`, `registry/` and `eligibility/` (a test checks it). No LLM, similarity, credit, NOS membership, occupation or labour-market figure is read when deciding.
  - **Held qualifications:** `holdings_complete` is true only when BOTH `held_qualification_codes` and `external_qualifications` are declared; with one undeclared, "no listed holding satisfies the level" is `UNKNOWN(INPUT_NOT_DECLARED)` and a listed satisfying holding still counts. Target-level `conditions` are built from `ComponentOutcome.conditions` (the P3.2 audit obligation), not from the singular `.condition`.
  - **Decisions where the specification is silent (D-1 … D-6, in the module docstring; for your review):** **D-1** a specification without rows raises `EligibilityError` (an empty `or_` is undefined; `NOT_MET` would claim a definite failure; `UNKNOWN` has no fitting reason code). **D-2** `decisive_rule_ids` are row ids only, as API_SPEC §2.4 words it (rows attaining the target verdict; all rows if `NOT_MET`); when only the age limits the target (for example age unknown, a `CONDITIONAL` row) the list is empty and the always-returned `age` component carries the reason. The age rule id is deliberately not added to the list. **D-3** conditions = union over the components of the decisive rows, exact duplicates removed, sorted by `(key, kind, value, text)`; two conditions with one key and different values are both kept; a consumer reads the verdict first (conditions on a `NOT_MET` or `UNKNOWN` target describe the decisive rows and do not say the target is conditional). **D-4** target-level `unknown_reasons` only when the target is `UNKNOWN`: the age reason, then every `UNKNOWN` component of the decisive rows. **D-5** `supporting_evidence` lists the verbatim progression claims of each registry qualification the profile holds AND declares relevant to the target ("The X QF lists '…' as a progression. Supporting evidence only; it does not change the verdict."); no claim is linked to the target by name, because that link is an inference (P3.5). `explanation` stays empty (P3.8). **D-6** Q-B, below.
  - **Q-B outcome (NOT resolved; implemented as an explicit, tested switch).** A held registry qualification's own `nsqf_level` is capped, never compared, when: it has an open conflict (`SOURCE_CONFLICT`), is uncertain or null (`UNCERTAIN_EXTRACTION`; ARCHITECTURE §11.3 items 1–2), or its `engine_use` is `DISPLAY_ONLY`, `NOT_USED` or `SAFE_HOURS` (`ENGINE_USE_UNDECIDED`; §11.4 "shown, never computed"). A computing `engine_use` is compared. The one undecided case is `engine_use = UNKNOWN` (every curated qualification-level NSQF value in the real build; the 33 catalogue-only ones are `DISPLAY_ONLY` and are therefore never compared): `undecided_level_use = COMPARE` (default) compares it; `CAP` yields `UNKNOWN(ENGINE_USE_UNDECIDED)`. **The documented discrepancy:** ARCHITECTURE §11.2 (input: "held qualification codes (official levels)"), §11.5, TASKS P3.3 criteria 1–2 and the E07 example all compare AMH/Q0301's level 2.5, while §11.4 ("`UNKNOWN`: only the affected component is UNKNOWN"), §11.3 item 6 and the curation default (`config/curation_defaults.yaml`: the qualification-level `nsqf_level` has no `engine_use` on purpose) say a value with no decided use does not compute. The default follows the controlling P3.3 criteria; **every golden result that depends on it (criteria 1 and 2 and the E07 profile) is PROVISIONAL** and each such test also asserts the `CAP` outcome, so a decision either way is a one-word change. Nothing in `ARCHITECTURE.md`, `API_SPEC.md` or the E07 example was edited.
  - **Verification (actual runs, 2026-11-02):** `tests/unit/test_eligibility_evaluate.py` **129 passed** (synthetic: aggregation tables, decisive rows, conditions, holdings completeness, Q-B both ways, claims/credits/overlays invariance, determinism, validation, boundaries); `tests/golden/test_eligibility_pilot.py` **122 passed** on the real build `cb-601c0399c999` (every test goes through a fixture that asserts `BuildInfo.validation == "PASSED"`); full suite **2819 passed, 1 warning** (2568 before; +251). Thirteen deliberate mutations of `evaluate.py` (holdings always complete, conditions from `.condition`, display-only level compared, `or_` for the age, `or_` for a row, every row decisive, conflict cap removed, uncertain cap removed, unknown level always compared, claims shown for every holding, target unknown reasons dropped, no de-duplication, config ignored) were each killed by at least one test; a fourteenth (the age component given a different `match`) is an equivalent mutant (the age evaluator ignores it). The code was restored byte-identical.
  - **Acceptance criteria:** 1 PASS (provisional Q-B); 2 PASS (provisional Q-B); 3 PASS (not Q-B dependent: the config-unset check precedes level caps, and "declared none" has no level to compare); 4 PASS; 5 PASS; 6 PASS (the claim appears as supporting evidence for a held, declared-relevant qualification; removing every claim changes nothing but `supporting_evidence`; the SMO → SSMO claim is shown with its verbatim text, without a name-based link, see D-5); 7 PASS; 8 PASS.
  - **Not done / limits:** Q-A (reason code for the D5 case, `REVIEW_FLAG`) and Q-C (serving requires `PASSED`) are unchanged; `explanation` is empty (P3.8); no HYPOTHETICAL holdings (P3.6/P3.7 must add an origin to `HeldQualification`); the façade, `PROFILE`/`UNKNOWN_QUALIFICATION_CODE` error mapping and HTTP are P3.10/P5; E07 validation rules about unknown codes surface as `UnknownEntityError`. The registry imports from `curation`, so `eligibility` reaches `curation` transitively (see the P3.2 audit, 6c). Phase 3 is not complete; Phase 1 evidence gates, DQ-01 and Module A `NO_GO` are unchanged.

### P3.4 — Static graph edges · MUST · DONE as an engineering stage, with exceptions (2026-11-02, run 7; uncommitted)

- **Dependencies:** P3.1.
- **Deliverables:** `src/skillgraph/graph/edges.py` (`INCLUDES_NOS`, `SHARES_NOS` with core/non-core and version agreement, `PROGRESSION_CLAIM` to `CLAIM_TEXT` nodes, `ALIGNED_TO_NCO`); the legend text from `API_SPEC.md` E08.
- **Acceptance criteria:**
  - **OBS-01 reproduced:** `SHARES_NOS` exists exactly for {SSMO, IC} = {AMH/N0309, DGT/VSQ/N0102}, {IC, PS} = {DGT/VSQ/N0102} and {SSMO, PS} = {DGT/VSQ/N0102}.
  - SMO has no `SHARES_NOS` edge.
  - All shared units are Non-Core.
  - The DGT/VSQ/N0102 edges carry the OV-040 conflict flag where the SSMO membership is involved.
  - No `PROGRESSION_CLAIM` edge targets a qualification code, except through a reviewed inference (P3.5).
- **Effort:** 2–4 h.
- **Done (2026-11-02, run 7; nothing committed):**
  - **Code:** `src/skillgraph/graph/edges.py` (new) and the re-exports in `graph/__init__.py`. Public surface: `build_static_edges(registry, include_inference=False) -> list[GraphEdge]` (API_SPEC §4), `static_legend() -> tuple[LegendEntry, ...]`, the models `EdgeType` (all six API_SPEC values), `GraphEdge` (E08 shape; the model refuses an edge that breaks the contract of its type) and `LegendEntry`, and the errors `GraphError` and `EdgeBuildError` (`.problems` lists every problem found). The module imports only `skillgraph.model`, `skillgraph.registry`, pydantic and the standard library (an AST test checks it); it does not import `eligibility/`.
  - **Where each edge comes from (nothing else creates an edge):** `INCLUDES_NOS` (qual → `nos:` or `mod:`, OFFICIAL, directed) one per `Qualification.nos_memberships` row; `SHARES_NOS` (qual ↔ qual, RULE_DERIVED, stored once with `source < target`) from an exact NOS-code match on two such memberships, carrying `shared_codes`, `core_shared_count`, `noncore_shared_count`, `version_agreement` per code, and the conflict flags; `PROGRESSION_CLAIM` (qual → `claim:` node, OFFICIAL) one per `Qualification.progression_claims`; `ALIGNED_TO_NCO` (qual → `nco:`, OFFICIAL) one per `Qualification.nco_codes`. A documented relationship is not a claim of eligibility or of a feasible move: no edge is read by the eligibility evaluator. No title, level, hours, credit, age, eligibility rule, occupation similarity, labour-market figure, probability or LLM takes part; **Q-B is not touched** (the qualification-level NSQF value is never read; only a `conflict_id` on a membership value is).
  - **Decisions where the specification is silent (D-7 … D-14, continuing D-1 … D-6 of P3.3; in the module docstring; for your review):**
    - **D-7** Edges and the legend only: nodes (labels, attributes, flags) and the `focus` / `include_catalogue_only` filters belong to the E08 view (P3.10 / P5.4). `include_inference=True` raises `NotImplementedError` (P3.5) rather than silently returning a graph without inference edges. Edges are built for every qualification that states a relationship, whatever its `coverage`.
    - **D-8** Provenance: a membership is not itself a `Valued`, so an `INCLUDES_NOS` edge cites the evidence ids of every printed cell of its NOS-table row (level, version when printed, the five hours values, credits); `SHARES_NOS` cites the union over both rows of every shared code; a claim or NCO edge cites its own evidence id. Every id must resolve in the registry. Only ids are read, never a cell's value.
    - **D-9** Invalid input is reported, never repaired: a dangling endpoint (unknown NOS unit, module or occupation; a membership or claim of another qualification), a null NCO code, an unresolved evidence or conflict id, or a relationship stated twice (a qualification listing one NOS unit or NCO code twice) raises `EdgeBuildError` with every problem; nothing is dropped, merged or picked. The real build has none.
    - **D-10** `version_agreement`: `SAME` if both rows print a version and the strings are equal, `DIFFERENT` if both print one and they differ, `NOT_STATED` if either prints none (null, empty or blank). Versions are DISPLAY_ONLY and are compared for this annotation only.
    - **D-11** `core_shared_count` / `noncore_shared_count` count codes that are Core / Non-Core in **both** QFs. A code classified differently by the two QFs is counted in neither and listed in an extra attribute `mixed_core_codes` (always present; empty in the real build). **Closeout (run 8, [`docs/decisions/P3_4_CLOSEOUT.md`](docs/decisions/P3_4_CLOSEOUT.md)): RESOLVED ON THE EVIDENCE, retained as an additive attribute.** API_SPEC §1.1 allows additive fields within v1, `GraphEdge.attributes` is a free-form `object`, and E08 (line 681) lists four keys without closing the set (the earlier statement "exactly four" overstated the text). The key preserves a source disagreement without asserting a classification; each QF's own label stays on its `INCLUDES_NOS` edge. A documentation-only amendment of `API_SPEC.md:681` is recommended and awaits explicit approval; if line 681 is read as a closed set, the smallest alternative is Option B in the record (a `SEMANTIC_AMBIGUITY` flag instead of the key).
    - **D-12** A membership value that carries a `conflict_id` puts one `SOURCE_CONFLICT` flag (severity `INFO`, as in the E08 example; `refs = [conflict id]`) on its `INCLUDES_NOS` edge and on every `SHARES_NOS` edge that uses it; flags are de-duplicated and sorted; no value is chosen between sources.
    - **D-13** Edge id `e:<TYPE>:<source key>:<target key>`; list sorted by `(type, source, target)` (E08); equal results for repeated calls and for any record order.
    - **D-14** The `SHARES_NOS` legend text is E08's verbatim; E08 gives no text for the other three types, so those `meaning` / `does_not_mean` strings are drafted from ARCHITECTURE §10.2–§10.3. **Closeout (run 8):** exact strings inspected against E08, ARCHITECTURE §10.2–§10.3 and the build's evidence (QF documents for every edge type); the `SHARES_NOS` text is verbatim. One defect corrected: the `PROGRESSION_CLAIM` `does_not_mean` said the text does not name a qualification, which is false when a claim equals a catalogue title (SMO's "Specialized Sewing Machine Operator"); it now says the edge states no link to a qualification. **REVIEWED, NOT APPROVED** (E08 gives no text for three of the four entries); the strings are pinned by a test.
  - **Verification (actual runs, 2026-11-02):** `tests/unit/test_graph_edges.py` **91 passed** (85 in run 7, +6 in the run-8 closeout) (synthetic: every edge type and direction, attribute shape, counts, version rule, mixed Core/Non-Core, conflict flags, evidence, claims with a `resolved_target`, duplicates and dangling references, empty registries, order and determinism, independence from credits/hours/levels/ages/titles/eligibility, the `GraphEdge` contract, legend, import boundary); `tests/golden/test_graph_edges_pilot.py` **21 passed** on the real build `cb-601c0399c999` (validated `PASSED`); `tests/integration/test_graph_edges_build.py` **5 passed** (a builder-made build; missing and damaged builds never reach the edge builder). Full suite **2936 passed, 1 warning** (2819 before P3.4; +117). Sixteen deliberate mutations of `edges.py` (core counted from one side, version rule inverted, blank version counted as stated, flags dropped on `SHARES_NOS` and on `INCLUDES_NOS`, evidence from one side only, mixed codes hidden, final sort removed, duplicates silently merged, NCO / claim / bridge-module edges skipped, `include_inference` ignored, evidence not resolved, dangling unit not checked, version not stripped) were each killed by a test; the file was restored byte-identical. Real build: 40 edges (27 `INCLUDES_NOS`, 3 `SHARES_NOS`, 6 `PROGRESSION_CLAIM`, 4 `ALIGNED_TO_NCO`) in about 6 ms. The legacy suite remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
  - **Acceptance criteria (real build):** OBS-01 reproduced **PASS** (exactly the three pairs and codes); SMO has no `SHARES_NOS` edge **PASS**; all shared units Non-Core **PASS** (also checked against the registry's own NOS tables); OV-040 flag on the two SSMO `SHARES_NOS` edges and on the SSMO `INCLUDES_NOS` edge of N0102, and on no other N0102 edge **PASS**; no `PROGRESSION_CLAIM` edge targets a qualification **PASS** (all six end at `claim:` nodes; `resolved_target` is not read). None depends on Q-B. **Deliverable "legend text from API_SPEC E08": PROVISIONAL** (D-14: only the `SHARES_NOS` text exists in E08; the other three strings were reviewed in run 8 and are awaiting approval).
  - **Exceptions and specification gaps (reported; nothing edited in ARCHITECTURE or API_SPEC):** (1) D-11 adds `mixed_core_codes` to the `SHARES_NOS` attributes. Run 8 found no contract conflict (API_SPEC §1.1 allows additive fields; line 681 does not close the set), so the key is retained; the specification still does not say how a unit classified Core by one QF and Non-Core by the other is counted. Owner/action: approve the documentation-only amendment of `API_SPEC.md:681` (or, if you read line 681 as closed, choose Option B in the closeout record). (2) D-14 legend wording: reviewed and one string corrected in run 8; owner/action: explicit approval of the three drafted entries. (3) `GraphNode` assembly is not part of this stage (D-7); P3.10 / P5.4 must build nodes (labels, `coverage`, `NCO_TITLE_NOT_FOUND`) and the `include_catalogue_only` / `focus` filters.
  - **Not done / limits:** no inference edge (P3.5) and no `ELIGIBILITY_ROUTE` (per request, P3.6); the name-based `ProgressionClaim.resolved_target` is deliberately ignored; version agreement is observed on one build only (four curated qualifications); Q-A, Q-B and Q-C are unchanged (see `docs/decisions/P3_2_AUDIT.md`). Phase 3 is not complete; Phase 1 evidence gates, DQ-01 and Module A `NO_GO` are unchanged.

### P3.5 — Experimental inference edges · SHOULD · DONE as an engineering stage, with exceptions (2026-11-02, run 9; uncommitted)

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
- **Done (2026-11-02, run 9; nothing committed; full record: [`docs/decisions/P3_5_INFERENCE.md`](docs/decisions/P3_5_INFERENCE.md)):**
  - **Contract found, not invented.** The documents fix one edge type completely enough to build: `NCO_GROUP_PROXIMITY` (ARCHITECTURE §10.3, §13.4; TASKS P3.5; API_SPEC E08), qual ↔ qual, two qualifications whose **stated** NCO codes share the first 4 digits (3 configurable), `INFERENCE` and `experimental`, hidden by default, never used for feasibility. They fix **no** attribute set, confidence semantics, provenance form, settings key, legend wording or claim-normalisation rule (record §2); where the choice is not forced, the narrowest one was taken and flagged below. No score, weight, distance or confidence exists in the implementation.
  - **Code.** `src/skillgraph/graph/inference.py`: `build_inference_edges(registry, *, nco_group_digits=4)` and `inference_legend()`. `src/skillgraph/graph/edges.py`: `build_static_edges(registry, include_inference=False, *, nco_group_digits=4)` now returns the static edges **unchanged** plus the inference edges (sorted by `(type, source, target)`) when asked (it raised `NotImplementedError` until now, D-7), and `GraphEdge` enforces the contract of the new type (undirected, INFERENCE, experimental, `source < target`, `INFERENCE_EXPERIMENTAL` flag, exact attribute shape); no static id, attribute, meaning or order changed. `src/skillgraph/graph/claim_candidates.py`: unreviewed claim → catalogue-title **candidates** (not edges). `graph/__init__.py` re-exports. The new modules import only `model/`, `registry/` and `graph/` (AST test); the eligibility modules do not import `graph/` (AST test); no title, level, hours, credit, age, rule, labour figure or LLM is read for the edges.
  - **Semantics.** An `NCO_GROUP_PROXIMITY` edge says only that two qualifications' official documents state occupation codes with a common 4-digit (3-digit, if configured) prefix. It does not say skills overlap, qualifications are equivalent, anyone is eligible, people move, or jobs exist; it never changes a verdict, path or order. Provenance: the evidence ids of the stated codes behind it (OFFICIAL cells). It coexists with, and never replaces, a documented edge for the same pair.
  - **Decisions where the specification is silent (D-15 … D-23, continuing D-1 … D-14; settled implementation choices, for review):** **D-15** one edge per unordered pair of distinct qualifications sharing ≥ 1 group at the level (several shared groups → one edge); no self-edge. **D-16** attributes `group_digits`, `shared_groups`, `codes_by_qualification` (the smallest traceable set; E08 defines none for this type). **D-17** `evidence_ids` = evidence of the stated codes behind the edge. **D-18** id `e:NCO_GROUP_PROXIMITY:<A>:<B>`, `source < target`, sorted, deterministic and record-order independent (as D-13). **D-19** invalid input (null code, code with no occupation, missing/unresolved evidence, a code stated twice) raises `EdgeBuildError` listing every problem; a bad level raises `ValueError`; nothing is repaired (as D-9). **D-20** the level is a keyword parameter (no settings key was invented); every edge carries the `INFERENCE_EXPERIMENTAL` flag (severity `INFO`). **D-21** claim normalisation: the claim's own trailing `(direction_label)` removed, NFKC, case-fold, letters/digits tokens; exact equality with the normalised **catalogue** title, no similarity. **D-22** ambiguity and self-reference reported, not resolved. **D-23** candidates are returned/renderable; no file written (the build's `eligibility_rules_review.md` lies in the protected `data/` tree).
  - **Unresolved policy questions (not decided; record §3):** **Q-D** acceptance of the D-21 normalisation (it yields one candidate the contract did not anticipate, SMO's "Sewing Machine Operator-Knits" → the catalogue-only AMH/Q0305); **Q-E** where the reviewed claim-candidate artefact lives (TASKS: "the review file"); **Q-F** a settings key for the 3-digit level (`inference.nco_group_digits` proposed); **Q-G** approval of the drafted attributes and legend wording and a documentation-only E08 amendment; **Q-H** the name `build_static_edges` now that it can return experimental edges (kept, API_SPEC §4 fixes it). **Q-A, Q-B and Q-C are unchanged and not touched.** D-11 keeps its run-8 status (resolved on the evidence, retained); D-14 stays **reviewed, not approved**, and the inference legend entry is likewise drafted and not approved.
  - **Verification (actual runs, 2026-11-02):** `tests/unit/test_graph_inference.py` **93 passed** (synthetic: both levels, shared/non-shared groups, several groups per pair, same-qualification codes, empty and catalogue-only inputs, id/order/determinism/shuffled records, provenance, absence when disabled, static edges byte-equal when enabled, coexistence with `SHARES_NOS`, independence from titles/hours/credits/levels/eligibility, every invalid-input path, level validation, the `GraphEdge` contract refusals, legend wording and lint, import and attribute boundaries, claim normalisation and candidates incl. ambiguity, self-reference and the two contract examples); `tests/golden/test_graph_inference_pilot.py` **15 passed** on the real build `cb-601c0399c999` (validated `PASSED`); `tests/integration/test_graph_inference_build.py` **4 passed** (a builder-made build); related graph/registry/eligibility files **2137 passed**; full suite **3048 passed, 1 warning** (2936 before P3.5; +112; the warning is the existing Pydantic serializer warning in `test_eligibility_rules.py`). Twenty-six deliberate mutations of `inference.py`, `claim_candidates.py` and the new `edges.py` code were run: **25 killed**; one survivor is an equivalent mutant (reversing the intermediate pair order, undone by the final sort); the files were restored byte-identical. `tools/check_legacy_baseline.py`: "MATCH with baseline legacy_tests_2026-10-31: 23 passed, 1 failed, 0 errors, 0 skipped (DQ-01 unresolved)". The legacy suite remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
  - **One existing test replaced, none weakened:** `test_inference_edges_are_not_built_here_and_asking_for_them_is_an_error_not_a_silent_omission` pinned the P3.4 `NotImplementedError`, which D-7 described as the behaviour "until P3.5"; it is now `test_static_edges_are_off_by_default_free_of_inference_and_unchanged_when_inference_is_requested` (every earlier check kept, plus unchanged static edges when enabled).
  - **Acceptance criteria:** every inference edge is `INFERENCE` and `experimental` **PASS**; off unless requested **PASS**; SMO–SSMO share unit group 8153 and get an `NCO_GROUP_PROXIMITY` edge **PASS** (the only pair at 4 and at 3 digits; IC states 7543 and PS 3122); "the invariant test in P3.6 passes" **PROVISIONAL** (P3.6 does not exist; shown now: static edges byte-equal, no registry record changed, 480 pilot eligibility results identical with edges built and with a registry whose records state no NCO code); deliverable "claim candidates written to the review file" **PROVISIONAL** (candidates produced and recorded in the record §5, no file written: Q-D, Q-E); `TITLE_SIMILARITY` not built (COULD, not planned).
  - **Real build observations (not decisions):** 41 edges with inference = the 40 static edges + `e:NCO_GROUP_PROXIMITY:AMH/Q0301:AMH/Q2301` (shared `8153`; at 3 digits `815`). SMO ↔ SSMO has no `SHARES_NOS` edge, so this is the only relationship drawn between them. Claim candidates under D-21: three, all unreviewed (SMO P1 → AMH/Q0305, SMO P2 → AMH/Q2301, SSMO P1 → AMH/Q1801); no match for the two "QC Executive - Sewing Line" claims and "Production Manager".
  - **Not done / limits:** `TITLE_SIMILARITY`; `inference_annotations` on path steps and the API-level `INFERENCE_EXPERIMENTAL` response warning and `legend` assembly (P3.6 / P3.10 / P5.4); node assembly and filters (D-7); a settings key (Q-F). Phase 3 is not complete; Phase 1 evidence gates, DQ-01 and Module A `NO_GO` are unchanged; `config/overlay_approvals.yaml` is still `approved: []`.

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
- **Status (2026-11-02, runs 10–13): P3.6a (the enumeration core) is implemented and verified in run 13 (below); P3.6 is NOT complete (P3.6b and the path-ID question remain).** Run 10 stopped for want of a limit source, run 11 amended the documentation only (below), run 12 stopped because five necessary choices were specified nowhere (P-1 to P-5 below), and run 13 implemented P3.6a on your explicit decisions.
- **P3.6a result (2026-11-02, run 13; uncommitted): implemented and verified as an engineering stage, with the exceptions below. P3.6 is not complete.**
  - **Code.** `src/skillgraph/graph/paths.py` (new): `enumerate_paths(state, registry, config, scenario, max_steps, target_code, *, max_expansions, max_steps_limit)`, `RawPath { steps, verdict }`, `RawStep { index, from_state, target_code, eligibility }`, `Scenario`, `IncrementalHoursPolicy`, `LimitExceededError`, `TargetNotEvaluableError`, `ScenarioNotSupportedError` (the three errors subclass `GraphError`). `graph/__init__.py` exports them. Additive changes to the evaluator, all backward compatible: `HeldQualification.origin` (`DECLARED` default | `HYPOTHETICAL`) and its use in `_held_used` / `_prior_level` (`eligibility/components.py`); `InputUsed.evidence_class` also allows `HYPOTHETICAL` (as API_SPEC §2.4 lists); keyword-only `hypothetical_codes` on `evaluate` (`eligibility/evaluate.py`).
  - **Explicit implementation decisions of 2026-11-02 (the contract does not specify them; they are decisions, not contract text):** **P-1** every valid non-empty prefix is a path, in depth-first pre-order with candidates in ascending `qualification_id`; with `target_code` only paths whose last step is the target (stopping at the target changes no result); **P-2** a held target gives `[]`; **P-3** an unknown target raises `UnknownEntityError`, an existing `CATALOGUE_ONLY` one `TargetNotEvaluableError`, both before any evaluation; **P-4** a `CURATED` qualification with `eligibility is None` raises `EligibilityError`; **P-5** `from_state` is the declared registry holdings sorted ascending, then the earlier path targets in step order; plus module placement of the new types, the keyword name `hypothetical_codes`, and `resolvable_by = PROFILE` for `RELEVANCE_NOT_DECLARED`. Approved O-1 / O-2 decisions (guard and argument validation) are implemented as recorded above.
  - **Tests (new files; no existing test was edited).** `tests/unit/test_graph_paths.py`, `tests/unit/test_eligibility_hypothetical.py`, `tests/golden/test_graph_paths_pilot.py`: 137 tests. Results are in `session_log.md` Run 13.
  - **Criteria (the TASKS P3.6 list, as met by the P3.6a core).** Deterministic output **PASS** (repeated and reloaded runs byte-identical, registry order irrelevant); only `CURATED` targets **PASS** (P-3); no repeats, `max_steps` respected, guard raises `LimitExceededError` **PASS** (equality allowed, budget plus one refused, before any evaluation); `NOT_MET` never extended nor returned **PASS**; path verdict = `and_` of the steps **PASS** (recomputed independently); experience does not accrue **PASS for the default scenario only** (no scenario that accrues is supported); a non-default scenario sets `is_hypothetical` and the flag `HYPOTHETICAL_SCENARIO` **NOT MET, deferred to P3.6b** (such a scenario is rejected with `ScenarioNotSupportedError`; the departure from E09 is UNRESOLVED and the façade must not expose E09); **inference invariant NOT MET / NOT PROVEN**: `enumerate_paths` has no inference input and imports nothing from the edge or inference modules, and building the static and inference edges leaves the paths (compared as serialised output) and every registry record unchanged on synthetic and real data, but there is no `path_id` and no `include_inference` toggle on paths yet, so the invariant as written cannot be tested (P3.6b / P3.10).
  - **PROVISIONAL.** Q-B (`undecided_level_use = COMPARE`, the `evaluate` default, no switch on `enumerate_paths`): the E07-profile path result (SSMO `CONDITIONAL`) depends on it. The hypothetical-relevance rule (A-3 / O-4): a satisfying hypothetical holding with undeclared relevance gives `UNKNOWN(RELEVANCE_NOT_DECLARED)`, never `NOT_MET`; consequently, in P3.6a a later step that needs an earlier one for its level is `UNKNOWN` unless a declared holding already qualifies. **The permanent policy is now decided (A-7, Option C) but not implemented, so this behaviour still holds in the code.**
  - **Still open:** `path_id` (decided for P3.6b, A-6) and the permanent relevance policy (decided, A-7), both not implemented; the other fields with no assigned stage (O-5); the E09 departure for non-default scenarios (O-8); Q-A, Q-C, Q-D to Q-H unchanged; scenario flags, the inference invariant, `is_hypothetical` (P3.6b); ranking, explanations, hours (P3.7 onwards).
- **Run split (user instruction, 2026-11-02).** The first bounded run, "P3.6a", is the enumeration core: bounded depth-first search, `CURATED` targets only, no repeats, `NOT_MET` neither extended nor returned, the expansion guard, and `and_` path verdicts, under the default scenario only. Scenario flags, the `HYPOTHETICAL_SCENARIO` flag and inference annotations (so the **inference invariant**) belong to a later run, "P3.6b". The criteria above that need them stay unmet until then. **`path_id` also belongs to P3.6b** (decided 2026-11-02, API_SPEC §4 A-6); it is not implemented in P3.6a.
- **Contract amendments approved on 2026-11-02 (documentation only; text in `API_SPEC.md` §4, `ARCHITECTURE.md` §6.2 and §13.1):**
  - **A-1 Limits.** `enumerate_paths` gains required keyword-only `max_expansions` and `max_steps_limit`, with no default in `graph/`; the caller supplies the validated `Settings.paths` values; `graph/` never imports `settings`. The six positional parameters are unchanged. The `max_steps` default of 3 stays a `Settings`/E09 default. (Precedent for a keyword-only addition: `undecided_level_use`, P3.3 D-6.)
  - **A-2 Holding origin.** `HeldQualification.origin` reuses `EvidenceClass`, restricted to `DECLARED` (default; every existing holding) and `HYPOTHETICAL`. Confirmed: both members exist in `model/evidence.py` and API_SPEC §2.1; `HYPOTHETICAL` is already listed for `inputs_used.evidence_class` (API_SPEC §2.4), although the P3.2 `InputUsed` type is narrower (`DECLARED | CONFIG | OFFICIAL`) and will have to be widened to match. No enum is added; the HTTP profile cannot carry an origin.
  - **A-3 Provisional relevance rule.** *[Superseded in policy by A-7 (2026-11-02). The implemented P3.6a behaviour is unchanged until A-7 is implemented; the original text follows.]* An undeclared-relevance hypothetical holding that satisfies a `PRIOR_NSQF_LEVEL` component gives `UNKNOWN(RELEVANCE_NOT_DECLARED)`, never `NOT_MET`. This applies §11.2 step (5), "relevance undeclared → UNKNOWN", to a holding whose relevance the profile contract cannot state; steps (1)–(4) are unchanged and a declared-relevant satisfying holding still gives `CONDITIONAL`. **PROVISIONAL; not a permanent policy (O-4).** In the current evaluator a satisfying holding that is absent from a *declared* list gives `NOT_MET`, so this requires one new branch at implementation time.
  - **A-4 Dependency rule.** `graph/paths.py` alone may import `eligibility/`; the other graph modules keep the `model/` + `registry/` rule, and `eligibility/` never imports `graph/`. The existing boundary tests name their modules (`edges.py`, `inference.py`, `claim_candidates.py`, the eligibility modules), so by reading they are unaffected; no test was run in this documentation-only run. A boundary test for `paths.py` is added with the code.
  - **A-5 `RawPath` minimum.** `RawPath { steps, verdict }` and `RawStep { index, from_state, target_code, eligibility }`; everything else is assigned to a later stage or listed in O-5.
  - **A-6 Path identity (decided 2026-11-02; documentation only; implemented in P3.6b, not before).** New `eligibility.identity_profile_digest(state)`; `logging_setup.profile_digest` and its tests unchanged; `path_id = "p-"` + the first 12 lowercase hex characters of the SHA-256 of the canonical JSON of exactly `{config, profile_digest, scenario, steps}`; required keyword-only `profile_digest` on `enumerate_paths` (`^sha256:[0-9a-f]{64}$`; the graph layer neither imports `logging_setup` nor computes it); duplicate IDs in one result raise `GraphError`; the three labels are excluded (verified display-only); credential duplicates are kept (verified: they change the serialised result); build ID, `sort_by`, `limit` and `include_inference` are excluded. Text: `API_SPEC.md` §1.2 and §4 A-6. **Required P3.6b tests:** (a) a golden vector computed independently with `hashlib` from a literal canonical-JSON string; (b) format `p-` + 12 lowercase hex; (c) identical across processes and `PYTHONHASHSEED` values; (d) a different ID for a different step order, step set, config, scenario or profile digest; (e) no change from `sort_by`, `limit`, `include_inference` or any of the three labels; (f) permuting codes, external refs, credentials, relevant lists **and declarations** (unique `target_code` keys) leaves the digest unchanged, while `null` versus `[]`, a duplicate credential, and any engine-relevant value change it; (g) a malformed `profile_digest` is rejected; (h) duplicate IDs raise `GraphError`; (i) building the static and inference edges changes no ID, verdict or order.
  - **A-7 Relevance of a pending qualification, "Option C" (decided 2026-11-02; documentation only; NOT implemented).** A pending registry qualification is relevant to a target only if that target's `relevant_prior_qualifications` names it; unnamed (even with an explicit `[]`) gives `UNKNOWN(RELEVANCE_NOT_DECLARED)`; named gives `CONDITIONAL` with a `DECLARATION` and a `HYPOTHETICAL` condition; `is_hypothetical` is true if any step carries a `HYPOTHETICAL` condition; an unknown registry code is rejected for every declaration (`UnknownEntityError`, mapped to the existing `UNKNOWN_QUALIFICATION_CODE`), whether or not its target is evaluated; no new error type. Text: `API_SPEC.md` §2.3 and §4 A-7, `ARCHITECTURE.md` §13.1. **Changes it will require, none made:** the `ProfileState` validator (`evaluate.py`, currently "must refer to declared holdings"); an all-declarations code check in `evaluate` and a pre-check in `enumerate_paths`; `components.py` (`_prior_level`: a named hypothetical holding is relevant and adds a `HYPOTHETICAL` condition; `Condition.evidence_class` must allow `HYPOTHETICAL`); `is_hypothetical` derivation (P3.6b); and tests, including the existing test that pins the old validation (`tests/unit/test_eligibility_hypothetical.py`, "declared holdings") and the A-3 cases. Unchanged and not decided: experience-gain semantics, non-default scenarios and E09, the `HYPOTHETICAL_SCENARIO` flag wording and severity, inference annotations and E08, Q-A, Q-B (`COMPARE`, PROVISIONAL), Q-C.
  - **Unchanged by this amendment:** Q-A, Q-B (the default stays `undecided_level_use = COMPARE`, **PROVISIONAL** by user decision of 2026-11-02, with the `CAP` option and its tests kept; the underlying qualification-level policy is not decided), Q-C, Q-D to Q-H, the legend and inference contracts, `config/default.yaml` (`max_expansions: 10000`, still PROVISIONAL), every curated and data file, and `config/overlay_approvals.yaml` (`approved: []`).
- **Open items (status after run 13). A proposal is not an approved requirement unless it says APPROVED / ACCEPTED; the existing contract text is unchanged.**
  - **O-1 Guard formula.** ARCHITECTURE §13.1 says the guard "estimates n^k" and refuses if the expansion "would exceed" `paths.max_expansions`; it defines neither `n`, `k`, the unit of an "expansion", nor strict or non-strict comparison. **APPROVED 2026-11-02 (run 12):** `n` = the count of `CURATED` qualifications not already held, `k = max_steps`, `estimate = n ** k` computed before any eligibility evaluation; `LimitExceededError` only if `estimate > max_expansions` (equality allowed); a conservative budget estimate, not an exact count of evaluations; the ARCHITECTURE wording is unchanged. **Implemented in run 13.** Analysis in the next block.
  - **O-2 `max_steps` checks.** Not specified for the Python function: whether `enumerate_paths` or the façade rejects `max_steps > max_steps_limit` (API_SPEC §1.6 and E09 give the HTTP result `422 LIMIT_EXCEEDED` for `> 4`, and `422 VALIDATION_ERROR` covers a range violation such as `max_steps < 1`); the exception type for `max_steps < 1`; and the check on the types and minimum of the two limits. **APPROVED 2026-11-02 (run 12):** a `max_steps` that is not an `int`, or is a `bool`, raises `TypeError`; `max_steps < 1` raises `ValueError`; `max_steps > max_steps_limit` raises `LimitExceededError`; `max_expansions` and `max_steps_limit` are validated the same way (non-`int` or `bool`: `TypeError`; less than 1: `ValueError`); all validation happens before enumeration and before any eligibility evaluation. **Implemented in run 13.**
  - **O-3 Exceptions.** `LimitExceededError` is named in ARCHITECTURE §6.2 and here but is defined nowhere in code; its module is unspecified (proposed: `graph/paths.py`, subclass of `GraphError`). A non-`CURATED` target maps to the existing HTTP code `TARGET_NOT_EVALUABLE` (API_SPEC §1.6, E09) but no Python exception exists; any new exception class is **not approved**.
  - **O-4 Hypothetical relevance, permanent policy.** **RESOLVED 2026-11-02 (Option C, A-7): decided, documentation only, not implemented.** *Original statement of the gap:* ARCHITECTURE §13.1 says the relevance of a hypothetically completed qualification "must be declared", but API_SPEC §2.3 allows `relevant_prior_qualifications` to name only declared holdings, so the declaration route cannot be expressed. How it is to be expressed (a profile amendment), how it combines with `scenario.assume_intermediate_relevance`, and whether `resolvable_by` should stay `PROFILE` for this reason, are undecided.
  - **O-5 `RawPath` details.** **`path_id` is RESOLVED 2026-11-02 (A-6): assigned to P3.6b, derivation recorded in API_SPEC §4 A-6, not implemented.** The rest of O-5 stays open. No stage is assigned in this file to `totals`, step `official_hours`, `shared_nos_with_held`, `progression_claim`, `quality_flags` or `evidence_classes_present`. The element order of `from_state` is unspecified.
  - **O-6 Enumeration semantics.** Not specified, so not decided: whether every non-empty prefix of a path is itself returned or only complete paths; the order of the returned list; whether the search stops extending at `target_code` or is pruned by it; the result for a `target_code` that is already held; and what to do for a `CURATED` qualification that has no structured eligibility rules.
  - **O-7 Passing hypothetical holdings to `evaluate`.** `ProfileState` has no origin, and a hypothetical holding must not be written into the user's declared holdings. A proposed additive keyword-only argument on `eligibility.evaluate` (a collection of registry codes treated as origin `HYPOTHETICAL`, disjoint from the declared codes, with `holdings_complete` computed from the profile's own two lists before any merge) was **approved on 2026-11-02 (run 12) only conditionally**: it may be used if the existing types support it. Checked in run 12: `EvidenceClass.DECLARED` / `HYPOTHETICAL` exist, `ProfileState` is not touched, and `HeldQualification` has no `origin` yet (the approved A-2 field must be added with the code). **Implemented in run 13** (`hypothetical_codes`, `HeldQualification.origin`).
  - **O-8 Scenario in P3.6a.** `Scenario` and `IncrementalHoursPolicy` exist only in API_SPEC §2.1 and §2.3, not in code, and their module is unspecified. A proposal to reject any non-default scenario in P3.6a with a new exception would depart from E09, which accepts such scenarios and marks the paths `HYPOTHETICAL`. In run 12 you approved rejecting a non-default scenario in P3.6a with a narrow explicit exception that stays internal to this stage; the departure from E09 stays **unresolved**, and the façade must not expose E09 until it is decided. **Implemented in run 13** (`ScenarioNotSupportedError`, internal to P3.6a).
- **Decisions P-1 to P-5 (raised by the run 12 stop; ACCEPTED as recommended on 2026-11-02 and implemented in run 13 as explicit implementation decisions: they are decisions, not contract text).** The contract text was re-read: API_SPEC E09 says `target_code` gives "only paths ending at this `CURATED` qualification" and otherwise "all reachable qualifications"; ARCHITECTURE §13.1 says "for every qualification not yet held" and fixes the candidate order (ascending `qualification_id`); API_SPEC §1.6 has the HTTP codes `UNKNOWN_QUALIFICATION_CODE` and `TARGET_NOT_EVALUABLE`. Nothing else is stated, and there are no path tests.
  - **P-1 Prefix emission and output order (O-6).** Is every valid non-empty prefix returned as its own path (A, then A→B, then A→B→C), or only complete paths? If prefixes are returned, in what order? *Recommended:* every prefix is a path (consistent with "paths ending at this target" being shorter than `max_steps`), in depth-first pre-order (a path before its extensions; candidates in ascending `qualification_id`). Stopping the search at `target_code` needs no decision: it cannot change the result, because no qualification repeats, so it is only an optimisation.
  - **P-2 Held target (O-6).** `target_code` is already held by the profile. *Recommended:* an empty list (no step can enter a held qualification); the alternative is an error.
  - **P-3 Target that is not `CURATED` (O-3).** An unknown code raises the existing `UnknownEntityError` (registry behaviour, P3.3 note). For an existing `CATALOGUE_ONLY` code no Python exception exists, only the HTTP code `TARGET_NOT_EVALUABLE`. *Recommended:* a new `TargetNotEvaluableError(GraphError)` in `graph/paths.py`, raised before any evaluation.
  - **P-4 `CURATED` qualification with no structured rules (O-6).** A specification with no rows already raises `EligibilityError` in `evaluate` (P3.3 D-1, existing). A `CURATED` record whose `eligibility` is `None` has no defined handling. *Recommended:* raise `EligibilityError`, never skip silently.
  - **P-5 Order of `from_state` (O-5).** *Recommended:* the declared registry holdings sorted ascending, then the earlier path targets in step order.
  - *Settled without a decision (say so if you want otherwise):* `LimitExceededError` (a `GraphError` subclass) and `Scenario` / `IncrementalHoursPolicy` are placed in `graph/paths.py`; the keyword is named `hypothetical_codes`; `resolvable_by` for `RELEVANCE_NOT_DECLARED` stays `PROFILE`.
- **O-1 guard-formula analysis (the formula is approved; nothing is implemented).**
  - *What the contract fixes.* A guard, evaluated before enumeration, from a quantity written n^k, against the CONFIG key `paths.max_expansions`; exceeding it is `LimitExceededError` / `LIMIT_EXCEEDED`. `config/default.yaml` calls the value 10000 "PROVISIONAL … a starting point … revisit once path enumeration exists (P3.6)". It says nothing else.
  - *What `n` can mean.* (a) The `CURATED` qualifications that are not held at the start. The acceptance criterion "only `CURATED` qualifications are targets" makes these the only possible steps. On the real build that is at most 4, so `n^k` is at most 256. (b) Every registry qualification (4 `CURATED` + 33 `CATALOGUE_ONLY` = 37). Then `37^3 = 50 653 > 10 000`, so the default `max_steps = 3` would be refused on every request, contradicting E09's default and example. Reading (b) is therefore not tenable, and (a) is the only reading consistent with the other text.
  - *What an "expansion" can be counted as.* Each candidate is checked by one call of `evaluate`, so the exact worst-case number of evaluations is the number of simple paths of length 1 to k: F(n, k) = Σ n!/(n−j)! for j = 1…k. `n^k` is an upper bound of F(n, k) (checked for n ≤ 39 and k ≤ 4 in a scratch calculation; equal for k ≤ 2; examples: n=3, k=3: 27 against 15; n=4, k=4: 256 against 64; n=37, k=3: 50 653 against 47 989). It is therefore a safe, simple and conservative estimate in the unit the budget is naturally written in; F is tighter, but it is not the quantity the contract names.
  - *Testable interpretation (approved 2026-11-02, run 12; not yet implemented).* Estimate = `n ** max_steps`, with `n` = the number of `CURATED` qualifications whose codes are not in the profile's declared holdings, taken before enumeration; refuse (`LimitExceededError`) if and only if the estimate is **greater than** `max_expansions` (equality is allowed); the estimate does not depend on `target_code`, on the scenario, or on any eligibility outcome (none is known yet); `max_expansions` is a budget on the estimate, not a measurement. Tests: on a synthetic registry with `n` curated records, a budget of `n**k` is accepted and `n**k − 1` is refused; a spy shows that the refusal happens before any `evaluate` call; a property test shows that the measured number of `evaluate` calls never exceeds the estimate, and equals F(n, k) when no step is `NOT_MET`; a test with `max_expansions` set small proves the guard can actually trip.
  - *Consequences to note.* At the unchanged default of 10000 the guard trips for `n ≥ 22` at `k = 3` (21³ = 9 261, 22³ = 10 648) and for `n ≥ 11` at `k = 4`. With 4 curated pilots it never trips (n ≤ 4). If the catalogue is later expanded to about 37 curated qualifications, the default `max_steps = 3` would be refused at 10000; that is the purpose of the guard and would need a deliberate change of the CONFIG value, not a code change.
  - *Alternative.* Use F(n, k) as the estimate: tighter, the same tests with F in place of `n**k`, but the documentation (ARCHITECTURE §13.1) would have to be reworded because it names n^k.

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
