# Session log — Skillathon 2026, Skill Adjacency Graph

Permanent, append-only record of every Claude Code run in this project. Never overwrite earlier entries. No credentials, tokens or secret values are recorded here.

Entry format: 1 run and task · 2 date and time (Asia/Kolkata) · 3 branch and HEAD · 4 working tree before and after · 5 objective · 6 inspected · 7 created or modified · 8 decisions and reasons · 9 tests and checks · 10 exact results · 11 documentation reviewed and updated · 12 outstanding issues and blockers · 13 recommended next task.

Earlier work (P0.x, P1.x, the P2.1 inventory and its corrections) happened before this log existed and is **not** reconstructed here; its record is in `TASKS.md`, `docs/PROJECT_HANDOFF.md` and `git log`.

---

## Run 1 — TASK-1: Phase 2 closeout + session log initialisation

**1. Run and task.** Run 1 of this log. Task: Phase 2 closeout (P2.2, P2.3, P2.4 conditional, P2.5; P2.6 deferred) and creation of this log. *Note:* documents edited in this run label it "run 2" because it followed the P2.1 inventory run; they refer to this entry.

**2. Date and time.** 2026-11-01, about 22:52–23:20 IST (Asia/Kolkata).

**3. Branch and HEAD (checked at start, not assumed).** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. Working directory `C:\skillathon26\SkillAdjGraphV2`. No `CLAUDE.md` exists. `session_log.md` did not exist; created in this run.

**4. Working tree.**
- *Before:* `?? docs/feasibility/` (one untracked file, `module_a_sources.md`). No modified tracked files. `config/labour_market.yaml`: `gate_decision: NOT_ASSESSED`. `config/overlay_approvals.yaml`: `approved: []`, SHA-256 `287e3f677b2ef81f14036b8e427c8271df48ae26c6a34b4b5ce9936ec81df1f3`.
- *After:* modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md`. Also modified but gitignored (invisible to `git status`): `docs/PROJECT_HANDOFF.md`. Overlay-approvals hash unchanged. Nothing staged or committed.

**5. Objective.** Complete the mandatory Phase 2 work with evidence-based outcomes: P2.2 terms review, P2.3 variable feasibility, P2.4 only if files exist, P2.5 gate decision applying `ARCHITECTURE.md` §21.2 mechanically; keep P1 evidence gates and overlays untouched; synchronise documents; initialise this log.

**6. Inspected.** `TASKS.md` (Phase 2, header, P1 closure), `ARCHITECTURE.md` §14, §20.2, §21, `API_SPEC.md` (E13, error table), `README.md`, `docs/PROJECT_HANDOFF.md`, `docs/feasibility/module_a_sources.md`, `config/labour_market.yaml`, `config/overlay_approvals.yaml`, `src/skillgraph/settings.py`, `tests/unit/test_settings.py`, `data/raw/2026-10-30/MANIFEST.csv`, `data/curated/cb-744256fa29dc/occupations.json` and `build_manifest.json` (read only). Public web pages: microdata portal (policy page; dataset 292, 284, 213 descriptions, data dictionaries, variable lists, related-materials pages; catalogue listing), Karnataka DES English index, DGE NCO-2015 page, DGE terms and website-policy pages; MoSPI terms page (returned only a title); `data.gov.in` GODL gazette (HTTP 403). Policy PDFs (read as rendered images): NSS-report policy OM (2017) and microdata OM (2019). Not readable: GSDD (custom font encoding), download manual (compressed; page images extracted, not viewed).

**7. Created / modified.**
- Created: `session_log.md`; `docs/feasibility/module_a_variables.md`; `docs/decisions/MODULE_A_GATE.md`.
- Modified: `docs/feasibility/module_a_sources.md` (status line, T-1 row, next-steps item 4, closing sentence; **new section H appended**; sections A–G otherwise unchanged); `config/labour_market.yaml` (`gate_decision: NO_GO`, `decided_on: "2026-11-01"`, eight criteria; header comment updated); `TASKS.md` (one Phase 2 status paragraph); `README.md` (one table row); `ARCHITECTURE.md` (Q-6 consequence cell only); `docs/PROJECT_HANDOFF.md` (gitignored; four state statements and a §7 update note); `tests/unit/test_settings.py` (see item 8).
- Scratchpad only (outside the repo): `extract_jpeg.py` and extracted JPEG page images of four PDFs.
- **Side effect:** the fetch tool saved four policy/guidance PDFs (NSS-report OM, microdata OM, download manual, GSDD) into the Claude Code tool-results cache under the user profile, **outside the repository**. They are guidance documents, not datasets; nothing was written under `data/`. Disclosed in `module_a_sources.md` §H.1.

**8. Decisions and reasons.**
- **P2.1 consistency:** `module_a_sources.md` does not contradict the earlier closeout. It states P2.1 "is not marked DONE" and defers acceptance to a reviewer, so "operationally accepted" is the user's/reviewer's status, not the document's. HEAD cited (`b0fcff4`) matches. Label vocabulary differs from the task brief: the document uses `PAGE_OBSERVED`, `LISTING_OBSERVED`, `FILE_OBTAINED_LOCAL`, `SEARCH_LEAD_ONLY`, `NOT_VERIFIED`, `NOT_ATTEMPTED`, `PENDING_USER_ACTION`; it has **no** `REQUESTED_PENDING` (nothing was requested) and no bare `FILE_OBTAINED`. No entry was upgraded; P2.1 search work was not redone.
- **FG-2 = FAIL, not UNKNOWN:** `TASKS.md` P2.2 says `UNCLEAR` means FG-2 is `FAIL` until clarified. Recorded as rule-driven, not a prohibition.
- **FG-1 = FAIL:** the criterion is "actually obtained"; zero PLFS files, zero manifest rows, no registration. Stated as an unmet requirement, not a refusal of access.
- **FG-7 = UNKNOWN, not FAIL:** the reproduction was never attempted, so no failed result exists to record. `NO_GO` does not rely on it.
- **FG-3/4/5/6/8 = UNKNOWN:** the decisive documents (README, layout, State/UT code list, estimation procedure, NCO volumes) exist on the portal but need downloads; none was opened. No Karnataka code, NCO depth, threshold or tolerance was assumed.
- **Decision `NO_GO`:** §21.2 `NO_GO` = "FG-1, FG-2 or FG-7 FAIL, or the time-box expires". FG-1 and FG-2 are FAIL. `GO`/`GO_REDUCED` are not met; `NOT_ASSESSED` means "gate not run yet", which is no longer true. The time-box was not relied on (effort not measured). Flagged for the reviewer: the rules have no "evidence pending" outcome, so `NO_GO` is the mechanical result of an evidence shortfall, reversible by re-running the gate.
- **P2.4 not executed:** no PLFS file exists (filename search and manifest, re-checked). No sample counts, thresholds or reproduction invented; `src/skillgraph/labour/feasibility.py` and the CLI command were **not** created.
- **P2.6 deferred.**
- **Test edit (`tests/unit/test_settings.py::test_companion_config_files_have_specified_defaults`):** it pinned `gate_decision == "NOT_ASSESSED"`. P2.5 requires changing that value, so the test failed after the config change (observed: 1 failed, 15 passed). I replaced the pinned equality with a check of allowed values and the record shape (eight FG ids in order; results in PASS/FAIL/UNKNOWN; `decided_on` set). This was a deliberate edit for a legitimately changed state, not to hide a failure; the overlay assertion is unchanged. Reviewer may prefer a different form.
- Policy PDFs were read from rendered images because the fetch tool returned binary; wording is a reading of the scan.
- GODL text, MoSPI site terms, PIB, Planning Dept. pages, GSDD, 1999 policy and download manual were **not** established and are classified `UNCLEAR`.

**9. Tests and checks performed.**
1. Starting-state inspection (`git branch`, `git rev-parse HEAD`, `git status`, listings; hash of the two gate configs).
2. YAML validation of `config/labour_market.yaml`: parsed with `yaml.safe_load`; asserted allowed `gate_decision` value, keys `{id,name,result,note}` per criterion (the shape in `API_SPEC.md` E13), results in PASS/FAIL/UNKNOWN, ids FG-1…FG-8 in order.
3. `pytest tests/unit/test_settings.py` before and after the test edit.
4. Full new suite `.venv/Scripts/python.exe -m pytest -q` once (the config change could touch other tests; none else reads `labour_market.yaml`).
5. Repository search for labour-market statistic words (WPR, LFPR, worker population ratio, labour force participation, unemployment rate) outside `.git`, `.venv`, `data`; existence check of `frontend/`, `data/labour/`, `data/outputs/`.
6. Filename and manifest search for PLFS/microdata files.
7. Re-hash of `config/overlay_approvals.yaml`.
8. Not done: Markdown linting (no tooling configured); no cross-document link checker. References in the three feasibility/decision documents were checked by reading.

**10. Exact results.**
- YAML: schema checks passed (`schema ok`).
- `test_settings.py` before the test edit: **1 failed, 15 passed** (`AssertionError: assert 'NO_GO' == 'NOT_ASSESSED'`, stopped on first failure with `-x`). After: **27 passed**.
- Full new suite: **799 passed, 1 warning** (the known Pydantic serializer warning in `test_eligibility_rules.py`, not investigated). This includes the wrapper of the legacy baseline check; the legacy suite itself remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)** and that match is not a passing suite. The legacy suite was not run separately.
- Statistic-word search: 5 occurrences in 3 files (`ARCHITECTURE.md` 2, `docs/feasibility/module_a_sources.md` 2, `TASKS.md` 1), all definitions or targets, no figure. `frontend/`, `data/labour/`, `data/outputs/` do not exist.
- PLFS files: none; manifest has 22 rows from AMHSSC, DGE, NQR, SSCAMH only.
- Overlay approvals hash: unchanged (`287e3f67…81f1`); `approved: []`.
- Gate tally: PASS 0 · FAIL 2 (FG-1, FG-2) · UNKNOWN 6.

**11. Documentation reviewed and updated.**

| Document | Reviewed | Changed? | Why |
|---|---|---|---|
| `TASKS.md` | yes | **yes** | Phase 2 status paragraph (nothing marked DONE; P2.4 not executed; P2.5 `NO_GO` awaiting acceptance; P2.6 deferred). Line 133 (P0.3 historical deliverable "`gate_decision: NOT_ASSESSED`") left as history. |
| `README.md` | yes | **yes** | Module A row now `NO_GO`. |
| `docs/PROJECT_HANDOFF.md` | yes (gitignored) | **yes** | Three state statements and a §7 update note; the rest is the 2026-10-31 snapshot and is labelled so. |
| `ARCHITECTURE.md` | yes | **yes, one cell** | Q-6 consequence ("`NOT_ASSESSED`" → `NO_GO`). §21 rules untouched. |
| `API_SPEC.md` | yes | no | The `NOT_ASSESSED` values in its examples are labelled illustrative; E13 shape matched the config written. |
| `docs/feasibility/module_a_sources.md` | yes | **yes** | Section H and pointer notes (see item 7). |
| `docs/feasibility/module_a_variables.md` | created | yes | P2.3. |
| `docs/decisions/MODULE_A_GATE.md` | created | yes | P2.5. |
| `config/labour_market.yaml` | yes | **yes** | Decision recorded. |
| `session_log.md` | created | yes | This entry. |

**12. Outstanding issues and blockers.**
- **User acceptance** of P2.1, P2.2, P2.3 and P2.5 (none marked DONE). Phase 2 is not declared complete.
- **Q-6** (register for PLFS microdata; which rounds) and **Q-8** (deadline and demo format) remain open.
- Unread terms: GSDD, 1999 dissemination policy, download manual (ten page images extracted, not viewed), GODL, MoSPI site terms, PIB, Planning Dept.
- Unread metadata: README, layout, State/UT code list, questionnaires, estimation procedure, 2025-changes note; dataset 292 variable lists.
- The P2.5 criterion "a test greps analysis outputs and frontend strings for indicator numbers" cannot be built until those exist (Phases 4–5).
- Possible licence concern for Module B: DGE copyright clause vs NCO titles from the DGE online table (noted in `module_a_sources.md` §H.4; not assessed or changed).
- NCO `3122.3551` has no verified title in the build (existing Phase 1 evidence item, unchanged).
- Phase 1 evidence gates unchanged: DQ-01, DQ-02, DQ-03, Q-2, A2, P1.5-R1 and the rest. P1 is not declared complete. No overlay approved.
- Nothing is committed. `docs/PROJECT_HANDOFF.md` and `data/` are gitignored, so their changes will not appear in a commit.

**13. Recommended next task.** Return to the graph-only baseline: **start Phase 3, P3.1 (registry loader)**, after the user accepts `docs/decisions/MODULE_A_GATE.md` and decides whether to commit this run's documents. Reopening Module A is optional and needs Q-6/Q-8 and user-approved access first.

---

## Run 2 — TASK-1A: Locate and assess existing PLFS files

**1. Run and task.** Run 2 of this log. Task: Task 1A, read-only assessment of PLFS and NQR files found outside the repository.

**2. Date and time.** 2026-11-01, about 23:07–23:40 IST (Asia/Kolkata).

**3. Branch and HEAD (checked at start).** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. Working directory `C:\skillathon26\SkillAdjGraphV2`. No `CLAUDE.md`.

**4. Working tree.**
- *Before:* modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md` (the uncommitted result of Run 1). Config hashes: `labour_market.yaml` `3ff5d350cb503753a0580be1fa67bfba6ea85d03a0b795fca8533c345ea6c8e4`; `overlay_approvals.yaml` `287e3f677b2ef81f14036b8e427c8271df48ae26c6a34b4b5ce9936ec81df1f3`.
- *After:* same set of paths (the new file `docs/feasibility/existing_plfs_files_assessment.md` lies under the already-untracked `docs/feasibility/`). Both config hashes unchanged. Nothing staged or committed.

**5. Objective.** Determine whether files in `C:\skillathon26\plfs-2025` and `C:\skillathon26\nqr` can provide evidence for the outstanding Module A gates, while keeping existence, content inspection, official acquisition and reuse terms strictly separate, and without changing the Phase 2 decision.

**6. Inspected (read-only).** `C:\skillathon26\plfs-2025\`: `HH.csv` and `PER.csv` (first 4,000 bytes each, header and one row, for column counts; no values recorded), the README docx (full text), layout, Bstrm, state and district workbooks (sheet names, headers, a few rows; the full person-layout sheet and the whole state list), the ZIP (central-directory member list only), four schedule PDFs (extracted text and keyword scan). `C:\skillathon26\nqr\` workbook (sheet names, header, two rows, row count). Public page `https://microdata.gov.in/NADA/index.php/catalog/291/data-dictionary` (file and variable counts). Names and sizes only of folders `downloads\nco2015-*`, `downloads\karnataka-econ-survey` and a `work\` listing. Repo documents: `module_a_sources.md`, `module_a_variables.md`, `MODULE_A_GATE.md`, `config/labour_market.yaml`.

**7. Created / modified.**
- Created: `docs/feasibility/existing_plfs_files_assessment.md`.
- Modified (pointer notes only): `docs/feasibility/module_a_sources.md` (status header), `docs/feasibility/module_a_variables.md` (header), `docs/decisions/MODULE_A_GATE.md` (addendum above "Consequence"), `TASKS.md` (Phase 2 status paragraph), `docs/PROJECT_HANDOFF.md` (§7 note; gitignored), `session_log.md` (this entry).
- Scratchpad only: `read_docx.py`, `xl.py`, `pdfq.py` (read-only helper scripts), plus Run 1's files.
- Nothing under `C:\skillathon26\plfs-2025`, `C:\skillathon26\nqr` or any other external path was altered (file sizes and timestamps re-listed afterwards; hashes of the layout, README and register unchanged).

**8. Decisions and reasons.**
- Phase 2 decision (`NO_GO`) and all gate statuses left unchanged, as instructed. Findings are listed as candidates for reassessment.
- CSVs were neither loaded, counted nor hashed, to honour "do not process or load"; hashing and counting would require reading them in full.
- The ZIP was only listed; its only member is an `.exe`, which was not run.
- Provenance was not inferred from names or from the README's own heading; L3 (acquisition) and L4 (terms) are reported as not established for every file.
- Sibling folders (`downloads`, `work`) were reported by name only because they were outside the stated scope and also have unestablished provenance.
- The README's sentence limiting use of the unit-level data to "employment and unemployment indicators" is reported as a restriction signal bearing on FG-2, not as a determination.

**9. Tests and checks performed.** Existence, size and timestamp listings; SHA-256 of 11 non-CSV files; read-only extraction of README, workbook and PDF text; header and column-count comparison of both CSVs against the layout (108 and 39); comparison of README record counts with the public portal metadata; re-hash of both config files; Git status. No test suite was run: no code, config or test file changed.

**10. Exact results.**
- All listed paths exist; the schedule file numbered 9 (`9_…REVISIT_Janaury-June_2025.pdf`) is absent from the folder (numbering gap observed).
- `PER.csv` header: 108 columns; `HH.csv` header: 39 columns. These equal the person layout's 108 fields and the portal's variable counts for the monthly dataset (HH 39, PER 108).
- README record counts: household 804,145 (portal 804145: matches); person 3,394,123 (portal 3394129: **differs by 6**, unexplained; local row counts not checked).
- Monthly person layout: `st` (2), `ocu_cws` (3), `aind_cws` (2), `acws` (2), daily `ind1x/2x` (2), `mult` (10), `nsc`, `zst`, `caph`, `smallh`, `panel`. No principal/subsidiary-status occupation or status fields.
- Schedules (all three Schedule 10.4 PDFs read): "occupation (3-digit NCO-2015 code)"; "industry (2-digit NIC-2008 code)" for the weekly block.
- State-code workbook lists `29` = Karnataka.
- README rider: unit-level data "should not be specifically used for studying of any variable other than the employment and unemployment indicators".
- NQR workbook: one sheet `Documents`, 24 columns, 2,081 data rows; not merged with anything.
- Both config hashes unchanged after the task. No statistic produced.

**11. Documentation reviewed and updated.**

| Document | Changed? | Why |
|---|---|---|
| `docs/feasibility/existing_plfs_files_assessment.md` | created | The deliverable. |
| `docs/feasibility/module_a_sources.md` | pointer in the status header | Existence of out-of-repo files; sections A–H untouched. |
| `docs/feasibility/module_a_variables.md` | pointer in the header | Statuses and rows untouched; a targeted P2.3 revision is proposed. |
| `docs/decisions/MODULE_A_GATE.md` | addendum | Decision and the eight gate rows unchanged. |
| `TASKS.md` | one sentence | Phase 2 status paragraph. |
| `docs/PROJECT_HANDOFF.md` | one sentence | §7 note (gitignored). |
| `README.md`, `ARCHITECTURE.md`, `API_SPEC.md`, `config/labour_market.yaml` | **no** | Statuses are unchanged, so no edit is needed. |

**12. Outstanding issues and blockers.**
- Provenance of the PLFS files is **unknown** (only the user can state how and when they were obtained). FG-1 and FG-2 cannot move without it and without the terms.
- The two CSVs are unhashed, not row-counted, and their values unverified; a person-record count discrepancy (README vs portal) is unexplained.
- Hidden sheets in the layout workbook and the missing schedule 9 are unexamined.
- `6_PLFStxt2csv_M2025.zip` contains an unvetted executable that must not be run.
- Out-of-repository folders `downloads\` (NCO-2015 volumes, Economic Survey) and `work\` (e.g. `nco_vol1_concordance.csv`) exist and bear on FG-8 and P2.1; nothing was opened.
- NQR workbook modified-property date (2026-11-01) differs from the file's own timestamp (2026-10-30); unexplained.
- All Run 1 items remain: user acceptance of P2.1–P2.5, Q-6, Q-8, unread terms documents, Phase 1 evidence gates unchanged, nothing committed.

**13. Recommended next task.** A **targeted, no-analysis P2 revision**, after you state the provenance of the files: (a) a manifest of the existing PLFS files with hashes (needs a bounded read to hash the two CSVs), (b) re-assess FG-3, FG-4 and FG-8 against the local layout, schedules and state workbook, and (c) a check of the monthly dataset's access conditions in a browser for FG-2. Do not run the `.exe` or analyse the CSVs until FG-2 is settled. If you prefer not to reopen Module A, proceeding with graph-only Phase 3 (P3.1) remains valid and unaffected.

---

## Run 3 — P3.1: Registry loader

**1. Run and task.** Run 3 of this log (the log held Runs 1 and 2; the number was taken from it, not assumed). Task P3.1, the registry loader (`TASKS.md` Phase 3). First run of Phase 3.

**2. Date and time.** 2026-11-01, about 23:16–23:30 IST (Asia/Kolkata), from the machine clock.

**3. Branch and HEAD (checked at start).** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. Working directory `C:\skillathon26\SkillAdjGraphV2`. No `CLAUDE.md` exists. No commit, stage, fetch, reset, rebase, merge or branch change was made.

**4. Working tree.**
- *Before:* modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md` (the uncommitted results of Runs 1 and 2). `src/skillgraph/registry/__init__.py` existed as a one-line docstring. Hashes: `config/overlay_approvals.yaml` `287e3f67…81f1` (`approved: []`); `config/labour_market.yaml` `3ff5d350…c8e4`; one SHA-256 over the sorted hashes of every file under `data/` began `23025fe2…`.
- *After:* the same paths, plus modified `src/skillgraph/registry/__init__.py`, and untracked `src/skillgraph/registry/store.py`, `tests/unit/test_registry_store.py`, `tests/integration/test_registry_load.py`. `TASKS.md`, `README.md` and `session_log.md` carry further edits; `docs/PROJECT_HANDOFF.md` is gitignored and also edited. All three hashes above are unchanged. Nothing staged or committed.

**5. Objective.** Implement `registry.load()` and an immutable, indexed in-memory registry (by id, code, slug and NOS code) that refuses a missing or invalid build, loads the real build in under 1 s, and gives agreeing lookups; test it; synchronise the documents. Out of scope: the evaluator, edges, paths, ranking, explanations, Module A.

**6. Inspected.** `session_log.md`, `TASKS.md` (header, Phase 1 closure, P3.1 and the neighbouring P3 items), `ARCHITECTURE.md` (§6.2, §7, §9.1, §17, dependency rules), `API_SPEC.md` (E02, error table, `BuildStatus`, §4 signatures: `registry.load(build_dir: Path) -> Registry`), `README.md`, `docs/PROJECT_HANDOFF.md`. Code: `src/skillgraph/registry/__init__.py`, `services.py`, `cli.py`, `settings.py`, `curation/build.py` (output files, manifest, `check_references`), `curation/validate.py`, `curation/errors.py`, the `model/` modules that the build serialises, `tests/conftest.py`, `tests/unit/model_factory.py`, `tests/integration/synth_tree.py`, `tests/golden/conftest.py`. Data (read only): the four installed builds under `data/curated/` (manifests, record counts, shared NOS units, the one `validation_report.json`). No registry loader, store or index existed before this run, so nothing was duplicated.

**7. Created / modified.**
- Created: `src/skillgraph/registry/store.py`; `tests/unit/test_registry_store.py`; `tests/integration/test_registry_load.py`.
- Modified: `src/skillgraph/registry/__init__.py` (re-exports); `TASKS.md` (Phase 3 status paragraph; P3.1 marked DONE with evidence); `README.md` (one Status row); `docs/PROJECT_HANDOFF.md` (gitignored; one update note in §7); `session_log.md` (this entry).
- Scratchpad only: two probe scripts, a backup copy of `store.py` used for the mutation check (restored; the file in the repository is the intended one), and the draft of this entry.

**8. Decisions and reasons.**
- **One file, one entry point.** `store.py` holds the errors, the load pipeline and `Registry`, as the deliverable names. `load(build_dir)` takes an explicit directory, as `API_SPEC` §4 says. No "find the newest build" logic was added: it already exists in `cli._validate`, and silently choosing a build is what the task forbids.
- **What makes a build `INVALID`** is the list in `TASKS.md` P3.1 "Done". The checks reuse the builder's own constants and `check_references` (no second copy of the file list or reference rules) and the existing `skillgraph.model` schemas (extra fields forbidden, so malformed data is refused, never dropped).
- **Missing versus invalid.** No directory, or a directory without `build_manifest.json`, is `BuildNotFoundError` (`NOT_BUILT`); the builder writes the manifest last, so its absence means no complete build. Anything wrong with a build that has a manifest is `BuildInvalidError` (`INVALID`). Both carry `build_status` for the `BuildStatus` enum and are meant to map to `DATA_NOT_BUILT`.
- **Policy choices not stated in the specification (flagged for your review):**
  1. A build from an older `curation_code_version` is refused. Consequence: of the four installed builds only `cb-601c0399c999` (`p1.5-1`) loads; `cb-4ff16acc3b27`, `cb-744256fa29dc` and `cb-0e76c97bea00` (`p1.4-x`) are refused with "rebuild". Reason: `validate` treats them as not current, and the older ones lack the structured eligibility rules.
  2. An absent `validation_report.json` is allowed (`BuildInfo.validation == "NOT_RUN"`); a report that is malformed, for another build, or records a failed check is refused. Reason: `validate` is a separate step run after `build`, and the loader already re-checks hashes, schemas, references and counts itself.
  3. The registry imports from `curation.build`. The architecture's import rules restrict `eligibility/` and `graph/` (they may import only `model/` and `registry/`); they do not restrict `registry/`. An import check confirmed that importing `skillgraph.registry` pulls in no `labour`, `api`, `eligibility`, `graph` or network module.
- **Duplicates.** Ids are unique per collection, and a qualification or NOS code is unique because the id is derived from it. A duplicate id or code, or two ids with one slug, makes the build INVALID with every problem found listed; none is resolved by picking one. A NOS code is **not** assumed to belong to one qualification: the contract is a many-to-many membership (the real build has two shared units), so the NOS lookup returns all qualifications ascending. Slugs are indexed per kind (qualification, NOS) with the existing `SlugIndex`. By the id grammar two different valid qualification ids cannot share a slug, so the collision path is guarded and tested with records that skip validation, but it is not reachable from valid data.
- **Immutability by copy.** The models are frozen but their lists and dicts are mutable, so every accessor returns a deep copy and `from_records` copies its input. Cost: about 0.7 ms per `qualification_by_id` of a curated qualification (100 calls: 74 ms). I judged it acceptable at this size (37 qualifications) and chose it over editing the model classes or retyping their fields, which belong to P1.2. It may matter for P3.6 path enumeration; a copy-free internal view could be added then if measured to be needed. `Registry` is not proof against reaching private attributes by name; the tests cover the public surface.
- **`Registry.from_records`** is public because P3.2, P3.3 and the "mutating every credit value in a copied registry" test need registries built from synthetic records without files. It checks typed references between qualifications, NOS units, conflicts and eligibility rows; evidence-reference integrity is checked by `load` only, on the dumped build.
- **Errors for unknown keys** (`UnknownEntityError`, a `LookupError`) rather than `None`, so the API can map to `NOT_FOUND`/`UNKNOWN_*` later. The loader does not validate key format (that is a 422 concern in P3.10).
- **Timing test.** The load requirement is asserted on the real build only (skips if absent), after one warm-up load, over five runs, with the limit 1 s. Python and pydantic imports are not part of the measured call.
- **Existing tests:** none edited, weakened, skipped or deleted.

**9. Tests and checks performed.**
1. Initial inspection: `Get-Location`, `git branch --show-current`, `git rev-parse HEAD`, `git status --short`, file listings, hashes of the two config files and of the `data/` tree.
2. Probes on the real build: schema validation of all seven collections in a script; import-time measurement of the models and of `curation.build`; counts, shared NOS units, slugs.
3. `.venv\Scripts\python.exe -m pytest tests/unit/test_registry_store.py -q`.
4. `.venv\Scripts\python.exe -m pytest tests/integration/test_registry_load.py -q` (twice: one failure fixed in between, see item 10).
5. Both together: `pytest tests/integration/test_registry_load.py tests/unit/test_registry_store.py -q`.
6. Mutation check: temporarily made `_copy` return its argument, ran `tests/unit/test_registry_store.py`, restored the file from the backup, re-ran.
7. Full suite: `.venv\Scripts\python.exe -m pytest -q`.
8. Import-boundary check: `python -c "import sys, skillgraph.registry; …"` listing loaded modules whose names start with `skillgraph.labour`, `.api`, `.eligibility`, `.graph`, `anthropic`, `openai`, `requests`, `httpx`, `urllib3`.
9. Timing: seven timed `load()` calls on `data/curated/cb-601c0399c999`.
10. After the work: re-hash of `config/overlay_approvals.yaml`, `config/labour_market.yaml` and the `data/` tree; `git status --short`; `git diff --check` (only the existing LF/CRLF notices).
11. Not done: the legacy baseline checker (`tools/check_legacy_baseline.py`) was not run separately; the full suite includes its wrapper test. `python -m skillgraph build` and `validate` were not run (they write into `data/curated/`). No linter or type checker is configured, so none was run. The 1-second criterion was measured on this machine only.

**10. Exact results.**
- `test_registry_store.py`: **41 passed** (0.34 s).
- `test_registry_load.py`, first run: **72 passed, 1 failed**. The failure was in my own test: it parametrised "missing required field" over `conflicts.json`, and the synthetic build has no conflict records (`assert ([])`). Fix: removed that parameter and added a separate real-build test that edits a *temporary copy* of the real build's conflicts file. Second run: **73 passed**.
- Both files together: **114 passed** (2.39 s). Six of the 73 are real-build tests; they skip if the local data is absent and ran here.
- Mutation check: with `_copy` as identity, **3 failed, 38 passed** (`test_mutating_a_returned_record_never_changes_the_registry`, `test_every_access_returns_a_distinct_object`, `test_mutating_the_input_after_construction_never_changes_the_registry`); after restoring, **41 passed**.
- Full suite: **913 passed, 1 warning** in 27.7 s (Run 1: 799 passed; difference 114 = the new tests). The warning is the existing Pydantic serializer warning in `tests/unit/test_eligibility_rules.py`, not investigated. The legacy suite itself remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
- Import-boundary check: forbidden modules loaded: **none** (`[]`).
- Real build `cb-601c0399c999` loaded: 37 qualifications (4 `CURATED`, 33 `CATALOGUE_ONLY`), 22 NOS units, 4 occupations, 3 conflicts, 449 evidence records, 22 sources, 28 eligibility source rows; `BuildInfo.validation == "PASSED"` (its `validation_report.json`: 18 passed, 0 failed). Shared NOS: `nos:AMH/N0309` (Q0103, Q2301); `nos:DGT/VSQ/N0102` (Q0103, Q2101, Q2301).
- Load time of the real build, seven runs, in ms: 24.7, 23.1, 19.9, 26.0, 19.3, 19.0, 18.7 (requirement: under 1 s). One earlier cold-call figure: 22.3 ms. The model import takes about 0.2–0.3 s once per process and is not in these figures.
- Older builds: `load` of `cb-0e76c97bea00` raised `BuildInvalidError` ("built by curation code 'p1.4-3', current is 'p1.5-1'; rebuild"); a nonexistent directory raised `BuildNotFoundError`.
- After the work: overlay approvals `287e3f67…`, `labour_market.yaml` `3ff5d350…`, `data/` tree hash `23025fe2…`: **all unchanged**.

**11. Documentation reviewed and updated.**

| Document | Reviewed | Changed? | Why |
|---|---|---|---|
| `TASKS.md` | yes | **yes** | Phase 3 status paragraph; P3.1 marked DONE with the evidence above, the policy choices and what is not covered. Criteria met: real build under 1 s (18.7–26.0 ms), lookups by id/code/slug agree (asserted for all 37), a missing or invalid build raises a typed error carrying `NOT_BUILT`/`INVALID`. The mapping to `DATA_NOT_BUILT` itself is later work (P3.10/P5.1), as the criterion states ("later maps"). |
| `README.md` | yes | **yes** | One Status row for P3.1. The layout comment "foundation only" (handoff discrepancy D-2) is stale but predates this run and was left alone. |
| `docs/PROJECT_HANDOFF.md` | yes (gitignored) | **yes** | One update note at the top of §7. Its 2026-10-31 snapshot text, §9 table and Appendix A were left as written. |
| `ARCHITECTURE.md` | yes | no | No discrepancy: the registry follows §6.2, §9.1 and §17. The registry importing `curation` is not a violation of the stated dependency rules (decision 3 above). |
| `API_SPEC.md` | yes | no | `registry.load(build_dir: Path) -> Registry` and `BuildStatus` already match. The error mapping is for P3.10/P5. No endpoint was added or changed. |
| `docs/decisions/MODULE_A_GATE.md`, `docs/feasibility/*` | boundary only | no | Module A stays `NO_GO`; Phase 3 uses no labour-market data. |
| `config/*` | hashes only | no | None changed. |
| `session_log.md` | yes | yes | This entry. |

**12. Outstanding issues and blockers.**
- **Your review of the three policy choices** in item 8 (stale code version refused; missing validation report allowed; registry imports from `curation`). Choice 1 makes three installed builds unloadable until they are rebuilt or you decide otherwise; the loader's behaviour is easy to relax or tighten.
- **Which build to serve** (newest of the current code version) is not decided in code; the application layer must choose it (P3.10/P5.1).
- **Copy-on-read cost** (about 0.7 ms per curated qualification) is untested at path-enumeration scale; revisit in P3.6 if measured to matter.
- The specification does not say whether API lookups should normalise case or whitespace; the loader does not, and the 422/404 behaviour is left to P3.10.
- Unchanged and open: user acceptance of P2.1–P2.5 (Module A `NO_GO`), Q-6, Q-8, and every Phase 1 evidence gate (DQ-01/02/03, Q-2, A2, P1.5-R1, Q0301/E5, Q2301/E1#c1, OV-002/003/004/034/035). P1 is not declared complete. Phase 3 is not declared complete. Nothing is committed; `docs/PROJECT_HANDOFF.md` and `data/` are gitignored.

**13. Recommended next task.** **P3.2**, verdict logic and component evaluators (`src/skillgraph/eligibility/logic.py` and `components.py`; truth tables for `and_`/`or_` and one evaluator per `ComponentType`, synthetic fixtures only; Q-3, Q-4 and Q-9 defaults apply). It depends on the models, not on this registry, and is independent of the open evidence gates. Before it, decide whether to commit Runs 1–3 and whether you accept the three policy choices above.

---

## Run 4 — P3.2: Verdict logic and component evaluators

**1. Run and task.** Run 4 of this log (the log held Runs 1 to 3; the number was taken from it). Task P3.2, verdict logic and component evaluators (`TASKS.md` Phase 3). P3.3 and later were not started.

**2. Date and time.** 2026-11-01, about 23:32–23:45 IST (Asia/Kolkata), from the machine clock.

**3. Branch and HEAD (checked at start).** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. Working directory `C:\skillathon26\SkillAdjGraphV2`. No `CLAUDE.md` exists. No commit, stage, fetch, reset, rebase, merge or branch change was made.

**4. Working tree.**
- *Before:* modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `src/skillgraph/registry/__init__.py`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md`, `src/skillgraph/registry/store.py`, `tests/integration/test_registry_load.py`, `tests/unit/test_registry_store.py` (the uncommitted results of Runs 1 to 3). `src/skillgraph/eligibility/` held only a one-line `__init__.py`. Hashes: `config/overlay_approvals.yaml` `287e3f67…81f1` (`approved: []`); `config/labour_market.yaml` `3ff5d350…c8e4`; the `data/` tree hash began `23025fe2…`.
- *After:* the same set, plus untracked `src/skillgraph/eligibility/logic.py`, `src/skillgraph/eligibility/components.py`, `tests/unit/test_eligibility_logic.py`, `tests/unit/test_eligibility_components.py`. `TASKS.md`, `README.md`, `session_log.md` carry further edits; `docs/PROJECT_HANDOFF.md` (gitignored) is also edited. All three hashes above are unchanged (re-checked after the full suite). Nothing staged or committed.

**5. Objective.** Implement ARCHITECTURE §11.1 to §11.3 at component level: the verdict lattice operations `and_`/`or_` and one evaluator per `ComponentType`, with stable component-level reasons, conditions and evidence references, fail-closed on unknown, unmodelled, uncertain and conflicted inputs; test them with synthetic fixtures; record whether the P3.1 policies are compatible with the architecture; synchronise the documents. Out of scope: row and target aggregation, profile resolution, `EligibilityResult`, golden tests (P3.3).

**6. Inspected.** `session_log.md` (all of it), `TASKS.md` (P3.2, P3.3, P1.5 and the P3.1 entry), `ARCHITECTURE.md` (§6.2, §9.2, §10.1, §11.1 to §11.5, §17, §20 decisions Q-3, Q-4, Q-9, AS-5), `API_SPEC.md` (§2.1 enums, §2.3 profile, §2.4 eligibility result and component conventions, E07 examples, §4 signatures), `README.md`, `docs/PROJECT_HANDOFF.md`. Code: `src/skillgraph/model/eligibility.py`, `model/base.py`, `model/evidence.py` (`EvidenceClass`, `EngineUse`), `model/ids.py`, `curation/eligibility_rules.py` (how `safe` and `unknown_reason` are stored and which params exist), `registry/store.py` (compatibility only), `settings.py`, `tests/unit/model_factory.py`, `tests/unit/test_eligibility_rules.py`. Data (read only, via the registry): the stored components of the real build `cb-601c0399c999`, to learn which flag/param combinations occur (for example `requires_relevance = false` occurs only on 0-year experience components).

**7. Created / modified.**
- Created: `src/skillgraph/eligibility/logic.py`; `src/skillgraph/eligibility/components.py`; `tests/unit/test_eligibility_logic.py`; `tests/unit/test_eligibility_components.py`.
- Modified: `TASKS.md` (Phase 3 status paragraph; P3.2 marked DONE with evidence and assumptions A-1 to A-6); `README.md` (the Phase 3 Status row); `docs/PROJECT_HANDOFF.md` (gitignored; one update note in §7); `session_log.md` (this entry).
- Scratchpad only: the documentation-edit script, backup copies of the two modules used for the mutation checks (restored; verified by search that no `if False` mutation remains and by the passing suite), and the draft of this entry.
- Not modified: `src/skillgraph/eligibility/__init__.py`, any model, any registry file, any existing test, any config, any data.

**8. Decisions and reasons.**
- **No new verdict type or reason enum.** `Verdict` (with `rank`) and `UnknownReasonCode` come from `skillgraph.model.eligibility`. `and_`/`or_` are min/max over `rank`; the tests compare against hand-written 4x4 tables, not against `rank`, so a wrong order would fail.
- **Empty `and_()`/`or_()` raise** instead of returning an identity (`MET` would be a vacuous pass). The architecture defines no verdict for a rule with no operands; P3.3 must decide what an `EligibilitySpec` with no rows means.
- **Order of rules in `evaluate_component`:** re-validate the stored component (the project hardens against `model_construct`), check ids and the level interpretation, then (1) an `UNMODELLED` or `safe = false` component is `UNKNOWN` with its stored reason regardless of the profile (§11.3 items 1, 2, 6), (2) otherwise the §11.2 rule of its type. Uncertain, pending-overlay, undecided and conflicted values are already encoded by the curated `safe` and `unknown_reason`; the evaluator does not re-derive them, and it rejects a stored per-evaluation reason or an inconsistent `safe`/`unknown_reason` pair as malformed.
- **Missing versus malformed.** A valid but incomplete profile gives `UNKNOWN` (never a crash, never a pass or a failure). A malformed object gives a `ValidationError` or `ComponentError`, in line with the pydantic-first conventions of the model layer.
- **The input contract** (`ComponentInputs`, `HeldQualification`) and the six assumptions A-1 to A-6 (recorded in full in `TASKS.md` under P3.2): conditions as a tuple with a declaration-first singular view; `REVIEW_FLAG` for the D5 below-threshold case; `requires_relevance` does not grant `MET`; `resolvable_by` and wording per reason code; the input contract itself, with the level interpretation passed as a plain value so that `eligibility/` imports only `model/`; tie-breaks inside the table. None changes ARCHITECTURE or API_SPEC. Where the specification gives wording (E07 example for `DIPLOMA_YEAR_NOT_MODELLED`) it is used and pinned by a test.
- **Credits, shared NOS, occupations, titles, similarity and labour-market context are not inputs.** A test asserts that none is a field of `ComponentInputs`; another asserts the two modules import only `skillgraph.model`, pydantic and the standard library. No LLM or probabilistic code.
- **Test sizing.** The logic file is large (1407 items) because the 4- and 5-operand folds and all 64 triples are enumerated exhaustively; it runs in under a second.
- **Existing tests:** none edited, weakened, skipped or deleted.

**9. Tests and checks performed.**
1. Initial inspection: `Get-Location`, `git branch --show-current`, `git rev-parse HEAD`, `git status --short`, clock, file listings, hashes of the two config files and of the `data/` tree.
2. `.venv\Scripts\python.exe -m pytest tests/unit/test_eligibility_logic.py -q`.
3. `.venv\Scripts\python.exe -m pytest tests/unit/test_eligibility_components.py -q -x`.
4. Six mutation runs of both files (each followed by the two test files; the code restored afterwards): age `>=` to `>`; config-unset check disabled; zero-years shortcut disabled; `or_equivalent` branch disabled; `and_` using `max`; the unsafe/`UNMODELLED` guard disabled.
5. One import-boundary test tightened after the first run (see item 10).
6. A read-only smoke run (a script, not a test): every stored component of the real build `cb-601c0399c999` evaluated under two profiles and three level interpretations.
7. `.venv\Scripts\python.exe -m pytest tests/unit/test_eligibility_logic.py tests/unit/test_eligibility_components.py -q` after restoring the code.
8. Full suite: `.venv\Scripts\python.exe -m pytest -q`.
9. After the work: re-hash of `config/overlay_approvals.yaml`, `config/labour_market.yaml` and the `data/` tree; `git status --short`.
10. Not done: `tools/check_legacy_baseline.py` was not run separately (the full suite includes its wrapper test); `build`/`validate` were not run; no linter or type checker is configured. Timing was not an acceptance criterion here and was not measured.

**10. Exact results.**
- `test_eligibility_logic.py`: **1407 passed** (0.94 s).
- `test_eligibility_components.py`: **217 passed** (0.34 s). It passed on the first run. Because a first-run pass proves little, the mutation runs were added; I also noticed the first version of the import-boundary test compared only the first dotted segment, so a forbidden `skillgraph.api` import would have passed; I replaced it with a whole-prefix comparison before the mutation runs.
- Mutations: **each of the six made at least one test fail** (`1 failed`, run with `-x`); after restoring: **1624 passed** (1407 + 217).
- Smoke run on the real build: **312 evaluations, no exception**, every outcome kept its component's evidence id. Counts (profile / verdict): empty profile: 6 `MET` (0-year components), 150 `UNKNOWN`; full profile: 51 `CONDITIONAL`, 42 `MET`, 8 `NOT_MET`, 55 `UNKNOWN`. These are not golden results and are not claims about any real person.
- Full suite: **2537 passed, 1 warning** in 29.4 s (Run 3: 913 passed; difference 1624 = the new tests). The warning is the existing Pydantic serializer warning in `tests/unit/test_eligibility_rules.py`, not investigated. The legacy suite itself remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
- After the work: overlay approvals `287e3f67…`, `labour_market.yaml` `3ff5d350…`, `data/` tree hash `23025fe2…`: **all unchanged**.

**11. P3.1 compatibility review (interfaces only; the registry was not changed).**

| P3.1 policy | Architecture check | Result |
|---|---|---|
| Stale builds (older `curation_code_version`) are rejected | ARCHITECTURE §7 principle 4 (deterministic build id includes the curation-code version) and §15/§17 ("must re-build after a data change"); consistent with `skillgraph validate`, which also selects builds by code version. | **Compatible.** Limit: staleness is judged by code version only; input-hash staleness is `validate`'s check. Consequence already recorded: three installed builds are refused until rebuilt. |
| A missing `validation_report.json` is allowed and shown as `NOT_RUN` | §7 lists validation as stage 5 before a build is used; §17 says only "no valid curated build" without defining "valid"; API_SPEC E02 shows `validation {checks_passed, checks_failed}` with no state for a missing report. | **No conflict, one specification gap.** The architecture neither requires nor forbids serving an unvalidated build. Recommend that P5.1 decides whether E02/serving must require `PASSED` (a change to one condition in `load`, if so). |
| Registry reuses `MANIFEST_OUT`, `OUTPUT_FILES` and `check_references` from `curation.build` | §6.2 states import rules for `eligibility/`, `graph/`, `labour/`, `curation/` and `tools/`; none restricts `registry/`. The §6.2 diagram draws no `registry -> curation` arrow. | **Compatible with the stated rules.** Note: `eligibility/` imports `registry/` (P3.3), so `curation` becomes a transitive dependency. P3.2's own modules do not import the registry at all. If the P3.10 import-boundary test is written against direct imports it is unaffected; if a stricter reading is wanted, a small separate corrective task could move the constants and `check_references` to a neutral module. |

No P3.1 compatibility issue blocks P3.2 or P3.3. The registry's public interface (`qualification_by_code`, `eligibility`-bearing `Qualification`, `from_records`) is what P3.3 needs.

**12. Documentation reviewed and updated.**

| Document | Reviewed | Changed? | Why |
|---|---|---|---|
| `TASKS.md` | yes | **yes** | Phase 3 status paragraph (runs 3 to 4); P3.2 marked DONE with the code, contract, verification and assumptions A-1 to A-6. Criteria: truth tables (16 pairs each + n-ary associativity), every type's required cases, the `or_equivalent` branch, `UNMODELLED` always `UNKNOWN`, synthetic fixtures only: all covered by the tests above. |
| `README.md` | yes | **yes** | The Phase 3 Status row now names P3.1 and P3.2. |
| `docs/PROJECT_HANDOFF.md` | yes (gitignored) | **yes** | One update note at the top of §7. Its 2026-10-31 snapshot text, §9 and Appendix A were left as written. |
| `ARCHITECTURE.md` | yes | no | The evaluators follow §11 exactly; the assumptions fill gaps without changing a rule. The singular-versus-plural condition point (A-1) is recorded in `TASKS.md`, not edited into the architecture. |
| `API_SPEC.md` | yes | no | `ComponentResult` shapes, reason codes and `resolvable_by` values are unchanged; `ComponentOutcome` is an internal type that P3.3 projects onto them. A-1 notes the one place where the outcome is richer than `ComponentResult.condition`. No endpoint was added or changed. |
| `docs/decisions/MODULE_A_GATE.md`, `docs/feasibility/*`, `config/*` | boundary and hashes only | no | Module A remains `NO_GO`; Phase 3 uses no labour-market data; no config changed. |
| `session_log.md` | yes | yes | This entry. |

**13. Outstanding issues and blockers.**
- **Your review of A-1 to A-6**, especially A-2 (the reason code for the "Grade 9" below-threshold case), A-3 (the `requires_relevance` flag does not grant `MET`) and A-5 (the input contract that P3.3 must build from a `HypotheticalProfile`).
- **Specification gaps noticed** (not changed): `ComponentResult.condition` is singular; no reason code is named for `below_required_verdict`; `resolvable_by` is specified only by one example; behaviour of `and_`/`or_` on an empty rule is undefined. The P3.1 `NOT_RUN` gap for E02 is in item 11.
- The P3.3 golden criterion 3 says "with holdings declared as none -> `NOT_MET`" for every `PRIOR_NSQF_LEVEL` component; the evaluator already does this (config unset or set), which P3.3 should confirm on the real rules.
- Unchanged and open: user acceptance of P2.1 to P2.5 (Module A `NO_GO`), Q-6, Q-8, and every Phase 1 evidence gate (DQ-01/02/03, Q-2, A2, P1.5-R1, Q0301/E5, Q2301/E1#c1, OV-002/003/004/034/035). P1 and Phase 3 are not declared complete. Nothing is committed; `docs/PROJECT_HANDOFF.md` and `data/` are gitignored.

**14. Recommended next task.** **P3.3**, the eligibility evaluator and golden cases (`src/skillgraph/eligibility/evaluate.py`; `tests/golden/test_eligibility_pilot.py`): resolve a profile against the registry into `ComponentInputs`, aggregate `AND(age, OR(rows))` with `logic.py`, collect decisive rules, conditions and unknown reasons, and run the eight golden criteria on the real build. Before it, decide whether to commit Runs 1 to 4 and whether you accept A-1 to A-6 and the three P3.1 policy choices.

---

## Run 5 — P3.2 contract audit and P3.1 policy review

**1. Run and task.** Run 5 (the log held Runs 1 to 4). A bounded post-implementation audit of P3.2 and of the three P3.1 policy choices. P3.3 was not started.

**2. Date and time.** 2026-11-01, about 23:43 IST onward (clock at start 23:43:52 +0530).

**3. Branch and HEAD.** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`, unchanged. No commit, stage, fetch, reset, install or download.

**4. Working tree.**
- *Before:* as at the end of Run 4 (modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `src/skillgraph/registry/__init__.py`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md`, `registry/store.py`, `eligibility/logic.py`, `eligibility/components.py`, and the four test files of Runs 3 and 4). Hashes: `overlay_approvals.yaml` `287e3f67…`, `labour_market.yaml` `3ff5d350…`, `data/` tree `23025fe2…`.
- *After:* the same set of paths (no new tracked-status path; `docs/decisions/` now also holds `P3_2_AUDIT.md`). Hashes unchanged (re-checked after the full suite). `config/overlay_approvals.yaml` still `approved: []`.

**5. Objective.** Audit six issues against ARCHITECTURE/API_SPEC: A-1 (multiple conditions), A-2 (`REVIEW_FLAG`), A-3 (`requires_relevance`), A-4/A-6 (`resolvable_by`, wording, tie-breaks), A-5 (input contract), P3.1 policies (stale builds, `NOT_RUN` validation, `curation.build` imports). Correct only what the contract clearly decides; document the rest as exact questions.

**6. Inspected.** `session_log.md`; `API_SPEC.md` §2.1, §2.3, §2.4, E02, E07 and its example; `ARCHITECTURE.md` §6.2 (dependency rules), §7 principle 4, §11.2, §11.3, §13.1, §17, DQ-09; `TASKS.md` P3.1/P3.2 and the P1.4 `engine_use` note; `data/processed/audit_2026-10-30_m1s1/AUDIT_NOTE.md` and `corrections_overlay.csv` (D4, D5, OV-005); `config/curation_defaults.yaml`; `src/skillgraph/eligibility/components.py`; `src/skillgraph/registry/store.py` (validation, staleness, imports); the real build `cb-601c0399c999` (read only, via the registry: component shapes counted, qualification-level `nsqf_level` provenance, validation report header).

**7. Findings (details and citations in `docs/decisions/P3_2_AUDIT.md`).**

| # | Issue | Verdict |
|---|---|---|
| 1 | A-1 conditions | PASS; the E07 example already carries the config interpretation in `inputs_used` and the target-level `conditions`; invariant added so a singular projection loses nothing |
| 2 | A-2 `REVIEW_FLAG` | NEEDS DECISION (Q-A): allowed enum member and the verdict is correct, but its written definition names D4 and the "Grade 9" case is D5; no code invented |
| 3 | A-3 `requires_relevance` | PASS: the flag is true exactly on the 7 prior-level and the `years > 0` experience components of the real build; no case ignores a required flag |
| 4 | A-4/A-6 | PASS: `resolvable_by`/wording are metadata that never feed a verdict; only the `OTHER`-credential tie-break can affect a verdict and it is the fail-closed reading |
| 5 | A-5 input contract | FAIL, corrected: two independently nullable holding lists could not be represented (an undeclared list could become `NOT_MET`); registry-level provenance was not representable. Q-B open |
| 6a | stale code version | PASS |
| 6b | `NOT_RUN` validation | NEEDS DECISION (Q-C): an unvalidated build can be served; the contract neither requires nor forbids it |
| 6c | `curation.build` imports | PASS for direct imports; a transitive-closure import test would flag `registry -> curation` (noted, not needed now) |

**8. Changes made.**
- `src/skillgraph/eligibility/components.py`: `ComponentInputs.holdings_complete` (default `False`); with incomplete holdings, "no listed holding satisfies the level" gives `UNKNOWN(INPUT_NOT_DECLARED)` (`resolvable_by PROFILE`), a satisfying listed holding still counts, and `holdings_complete` without declared holdings is rejected. `HeldQualification.level_cap` (one of `UNCERTAIN_EXTRACTION`, `SOURCE_CONFLICT`, `OVERLAY_NOT_APPROVED`, `ENGINE_USE_UNDECIDED`; not allowed on an external ref): a capped level is never compared and yields that `UNKNOWN`; a usable satisfying holding wins; a capped holding beside non-satisfying ones gives `UNKNOWN`, not `NOT_MET`; `CONFIG_UNSET` still precedes. `ComponentOutcome` rejects more than one DECLARATION condition and any non-declaration condition missing from `inputs_used`. The default (`level_cap = None`) reproduces the E07 example, so Q-B is not pre-empted.
- `tests/unit/test_eligibility_components.py`: the `prior()` helper and `FULL` profile now state `holdings_complete` explicitly so that the seven existing tests keep their meaning (none weakened, skipped or deleted); 31 new tests (partial holdings, caps and their precedence, invalid caps, A-1 invariants).
- Docs: new `docs/decisions/P3_2_AUDIT.md`; `TASKS.md` (P3.2 audit bullet with link and amended contract, verification counts); `docs/PROJECT_HANDOFF.md` (gitignored; note at the top of §7). `README.md`, `ARCHITECTURE.md`, `API_SPEC.md` not changed (no status or contract wording changed; questions are recorded, not decided). P3.2 acceptance criteria and its DONE status are unchanged.
- Not changed: `registry/store.py`, `logic.py`, any config, data, overlay approval, frozen script.

**9. Tests and checks.**
- `.venv\Scripts\python.exe -m pytest tests/unit/test_eligibility_components.py -q` after the first edit: 7 failed, 210 passed (exactly the seven tests that assumed complete holdings; expected).
- After the helper update and new tests: `.venv\Scripts\python.exe -m pytest tests/unit/test_eligibility_components.py tests/unit/test_eligibility_logic.py -q`: **1655 passed** (1407 + 248).
- Full suite `.venv\Scripts\python.exe -m pytest -q`: **2568 passed, 1 warning** in 29.1 s (2537 before; +31). The warning is the existing Pydantic serializer warning.
- Read-only no-crash check on the real build (script, not a test): 52 components under 624 combinations (complete/incomplete holdings x capped/uncapped x three level settings): no exception (144 MET, 96 CONDITIONAL, 116 NOT_MET, 268 UNKNOWN; not golden results).
- Hashes of `overlay_approvals.yaml`, `labour_market.yaml` and the `data/` tree unchanged; `git status --short` shows no new tracked-status path other than those listed; HEAD unchanged.
- Not run: `build`, `validate`, the legacy baseline checker separately (the full suite wraps it; legacy wording unchanged: 23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)).
- Process note: my first scripted edit of the test file failed on an anchor mismatch (the file has CRLF line endings) and two quoting errors in shell heredocs; no partial edit was applied (verified: the run that finally applied the edit printed `ok` and the file kept its CRLF endings).

**10. Open decisions (exact questions in the audit record).** Q-A reason code for the D5 "Grade 9" below-threshold case. Q-B whether a held registry qualification's `nsqf_level` (engine_use `UNKNOWN` for the 4 curated, `DISPLAY_ONLY` for the 33 catalogue-only) may be compared, and whether uncertain/conflicted levels are capped. Q-C whether serving must require a `PASSED` validation report. Unchanged: Phase 1 evidence gates; Module A `NO_GO`; acceptance of P2.1 to P2.5.

**11. Recommendation.** P3.3 can begin with these constraints: (1) state the Q-B behaviour in P3.3 (default no cap, tested both ways); (2) build target-level `conditions` from `ComponentOutcome.conditions`; (3) set `holdings_complete` only when both profile lists are declared; (4) golden tests assert `BuildInfo.validation == "PASSED"`. Q-A and Q-C do not block it. Nothing is committed.

---

## Run 6 — P3.3: Eligibility evaluator and pilot golden cases

**1. Run and task.** Run 6 of this log (the log held Runs 1 to 5; the number was taken from it). Task P3.3, the qualification-level eligibility evaluator and golden cases for the four curated pilots (`TASKS.md` Phase 3). P3.4 and later were not started.

**2. Date and time.** Started 2026-11-01 23:57 IST (Asia/Kolkata, machine clock); work finished about 2026-11-02 00:13 IST. The run crossed midnight, so its documents carry both dates.

**3. Branch and HEAD.** Start and end: `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. Working directory `C:\skillathon26\SkillAdjGraphV2`. No commit, stage, fetch, pull, reset, rebase, merge, amend or branch change; `git diff --cached` was empty at the end. No download, installation or external action.

**4. Working tree.**
- *Before:* modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `src/skillgraph/registry/__init__.py`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md`, `registry/store.py`, `eligibility/logic.py`, `eligibility/components.py` and the four test files of Runs 3 and 4. Protected-file hashes: `config/overlay_approvals.yaml` `287e3f67…df1f3` (`approved: []`); `config/labour_market.yaml` `3ff5d350…c8e4`; the `data/` tree (SHA-256 over the sorted per-file hashes, the PowerShell method of this run) began `d89db664…`.
- *After:* the same set plus untracked `src/skillgraph/eligibility/evaluate.py`, `tests/unit/test_eligibility_evaluate.py`, `tests/golden/test_eligibility_pilot.py`. `TASKS.md`, `README.md`, `docs/decisions/P3_2_AUDIT.md`, `session_log.md` carry further edits; `docs/PROJECT_HANDOFF.md` (gitignored) is also edited. All three hashes above re-checked after the full suite: **unchanged**. `config/overlay_approvals.yaml` is still `approved: []`.

**5. Objective.** Implement `evaluate(spec, state, config, registry) -> EligibilityResult` (ARCHITECTURE §11.1 to §11.3, API_SPEC §2.3/§2.4): resolve a hypothetical profile against the registry, call the P3.2 component evaluators, aggregate `AND(age, OR(rows))` with the P3.2 lattice, collect decisive rows, target-level conditions, unknown reasons, supporting evidence and quality flags; resolve Q-B safely; write the pilot golden tests (TASKS criteria 1 to 8); synchronise the documents.

**6. Inspected.** `session_log.md` (all of it), `docs/decisions/P3_2_AUDIT.md`, `TASKS.md` (P3.1 to P3.4, the P3.2 audit paragraph), `ARCHITECTURE.md` (§6.2 dependency rules, §9.2, §10.3, §11.1 to §11.5, §13), `API_SPEC.md` (§2.1 to §2.4, E07 with its example and invariants, §4 signatures), `README.md`, `docs/PROJECT_HANDOFF.md` (§7, §9), `config/curation_defaults.yaml` (the qualification-level `nsqf_level` has no `engine_use` on purpose), `data/processed/audit_2026-10-30_m1s1/corrections_overlay.csv` (OV-032, OV-033; read only). Code: `eligibility/logic.py`, `eligibility/components.py`, `model/eligibility.py`, `model/evidence.py`, `model/qualification.py`, `model/base.py`, `registry/store.py` (and its `__init__`), `curation/eligibility_rules.py` (`project_spec`, `split_cells`, `response_params`), `tests/unit/model_factory.py`, `tests/golden/conftest.py`, `tests/conftest.py`, `tests/unit/test_eligibility_components.py`. Data (read only, through the registry): the real build `cb-601c0399c999` (`BuildInfo.validation == "PASSED"`): every rule, component, flag, claim and the qualification-level NSQF provenance of all 37 qualifications.

**7. Created / modified.**
- Created: `src/skillgraph/eligibility/evaluate.py`; `tests/unit/test_eligibility_evaluate.py` (129 tests); `tests/golden/test_eligibility_pilot.py` (122 tests).
- Modified: `TASKS.md` (Phase 3 status; P3.3 marked DONE as an engineering stage with criteria 1 and 2 provisional; Done block with D-1 to D-6); `README.md` (Phase 3 Status row); `docs/decisions/P3_2_AUDIT.md` (a "P3.3 follow-up" section appended; nothing earlier rewritten); `docs/PROJECT_HANDOFF.md` (gitignored; one note at the top of §7); `session_log.md` (this entry).
- Not modified: `ARCHITECTURE.md`, `API_SPEC.md` (the E07 example was not rewritten), `components.py`, `logic.py`, `registry/store.py`, any model, config, overlay approval, frozen script, dataset or earlier test.
- Scratchpad only: a read-only dump script, a smoke script, a mutation harness, a byte-exact backup of `evaluate.py`, a backup of `session_log.md`, and the draft of this entry.

**8. Decisions and reasons.**
- **No component logic in `evaluate.py`.** It calls `evaluate_component`, `and_` and `or_`; a test checks the calls and that no component parameter is read. It imports only `skillgraph.model`, `skillgraph.registry`, `skillgraph.eligibility`, pydantic and the standard library (tested by AST). `curation` is not imported (the registry does, transitively; P3.2 audit 6c). `requirement_text` is derived locally by the same single `partition` on `" || "` as `curation.project_spec`, and a golden test compares the two for all four pilots.
- **Types.** No `ProfileState`, `EngineConfig` or result type existed in code, so `ProfileState`, `EngineConfig`, `ComponentResult`, `RowResult`, `QualificationRef`, `ExplanationItem`, `EligibilityResult` were added in `evaluate.py`, mirroring API_SPEC §2.2 to §2.4 field for field; no field was invented. Existing types (`Verdict`, `UnknownReasonCode`, `Condition`, `InputUsed`, `QualityFlag`, `EngineUse`, …) are reused. `EligibilityResult` validates the P3.3 invariants itself.
- **Holdings.** `holdings_complete` is true only when both `held_qualification_codes` and `external_qualifications` are declared (the P3.2 audit obligation).
- **Conditions (audit obligation).** Built from `ComponentOutcome.conditions`; the CONFIG condition appears in the target list although each `ComponentResult` carries one DECLARATION condition (tested, and killed by a mutation to `.condition`).
- **D-1 to D-6** (specification silent; recorded in the module docstring and `TASKS.md` P3.3): no rows raises; `decisive_rule_ids` are row ids only (the age rule id is not added); conditions union/dedup/sort; target `unknown_reasons` only for an `UNKNOWN` target; `supporting_evidence` = verbatim claims of held registry qualifications that the profile declares relevant to the target, with no name-based link to the target (that link is a P3.5 inference); Q-B below.
- **Q-B: stated, implemented, still open.** `undecided_level_use = COMPARE (default) | CAP`. Capped always: open conflict (`SOURCE_CONFLICT`), uncertain or null value (`UNCERTAIN_EXTRACTION`), `DISPLAY_ONLY`/`NOT_USED`/`SAFE_HOURS` (`ENGINE_USE_UNDECIDED`, §11.4 "shown, never computed"). Compared: a computing `engine_use`. Policy-dependent only: `engine_use = UNKNOWN` or absent (all four curated pilots). Consequence: the 33 catalogue-only (`DISPLAY_ONLY`) qualifications never satisfy a rule; the curated pilots do only under `COMPARE`. Tested both ways on synthetic and real rules. **Exact discrepancy:** §11.2 ("official levels"), §11.5 (A4 regression notes), TASKS criteria 1 and 2 and the E07 example compare AMH/Q0301's level 2.5; §11.4 ("`UNKNOWN`: only the affected component is UNKNOWN"; "`DISPLAY_ONLY`: never computed"), §11.3 item 6 and `config/curation_defaults.yaml` (no `engine_use` for the qualification-level value) say a value with no decided use does not compute. The default follows the controlling P3.3 criteria; criteria 1 and 2 and the E07-profile golden test are **PROVISIONAL** and each asserts the `CAP` result too. Not resolved, not hidden, no document rewritten.
- **E07 example versus the evaluator (noted, not edited).** For the E07 profile, row 7 ("8th Grade pass || 3 year relevant experience") is also `CONDITIONAL`, so `decisive_rule_ids` is `[E7, E9]`; the example (abridged, "verdicts are illustrative") lists only E9. The condition set and its order match the example exactly.
- **Existing tests:** none edited, weakened, skipped or deleted.

**9. Tests and checks performed.**
1. Initial inspection: clock, `git rev-parse`, `git status --short`, `git diff --cached --stat`, file listings, hashes of the two config files and of the `data/` tree.
2. Read-only dump of the pilot rules and of every qualification's `nsqf_level` provenance from the real build (script, not a test).
3. Smoke run of `evaluate` on the E07 profile under `exact`, `at_least` and unset (script, not a test).
4. `.venv\Scripts\python.exe -m pytest tests/unit/test_eligibility_evaluate.py -q` (first run: 3 failures, all in my own helper `run()`, see item 10; then green).
5. `.venv\Scripts\python.exe -m pytest tests/golden/test_eligibility_pilot.py -q -x`.
6. Mutation harness over `evaluate.py` (14 mutations, each followed by both new test files; the file was then restored byte-identical from a backup and checked with `cmp`).
7. `.venv\Scripts\python.exe -m pytest tests/unit/test_eligibility_evaluate.py tests/golden/test_eligibility_pilot.py -q` (twice: after restoring, and after the wording edits).
8. Full suite: `.venv\Scripts\python.exe -m pytest -q` (twice).
9. `.venv\Scripts\python.exe tools/check_legacy_baseline.py`.
10. After the work: re-hash of the three protected items, `git rev-parse HEAD`, `git diff --cached --stat`, `git status --short`.
11. Not done: `build` / `validate` (they write into `data/curated/`); no linter or type checker is configured, so none was run; timing was not an acceptance criterion and was not measured.

**10. Exact results.**
- `test_eligibility_evaluate.py`: first run **126 passed, 3 failed**. The three failures were in my own fixture: `run()` built a default profile without an age, so the age rule was (correctly) `UNKNOWN`; I changed the helper to use `profile()` (age 30). Not an evaluator defect. Then **129 passed** (0.47 s).
- `test_eligibility_pilot.py`: **122 passed** (4.1 s) on the real build `cb-601c0399c999`; each test goes through a fixture that asserts `BuildInfo.validation == "PASSED"`. It passed on the first run, so the mutation run was added. Before it I also replaced two vacuous assertions of my own (`… or True`, and a tautology about conditions).
- Mutations: **13 of 14 killed** (`1 failed` with `-x` each): holdings always complete; conditions from the singular `.condition`; display-only level compared; `or_` for the age; `or_` for a row; every row decisive; conflict cap removed; uncertain cap removed; unknown level always compared; claims shown for every holding; target unknown reasons dropped; no de-duplication of conditions; config ignored. The 14th (the age component evaluated with a different `match`) **survived and is an equivalent mutant**: the age evaluator ignores the level interpretation. After restoring: **251 passed**. (My harness's own restore wrote CRLF line endings through `write_text`, which `cmp` flagged; I restored the file by `cp` from the backup and verified it byte-identical, with no `if False` left.)
- Focused (both new files): **251 passed**.
- Full suite: **2819 passed, 1 warning** in about 35 s (Run 5: 2568; difference 251 = the new tests). The warning is the existing Pydantic serializer warning in `tests/unit/test_eligibility_rules.py`, not investigated. `tools/check_legacy_baseline.py`: "MATCH with baseline legacy_tests_2026-10-31: 23 passed, 1 failed, 0 errors, 0 skipped (DQ-01 unresolved)". The legacy suite remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
- Protected files after the work: `overlay_approvals.yaml` `287e3f67…` (`approved: []`), `labour_market.yaml` `3ff5d350…`, `data/` tree `d89db664…`: **all unchanged**. HEAD unchanged; nothing staged.

**11. Acceptance criteria (TASKS P3.3), each on the real build.**

| # | Criterion | Result | Notes |
|---|---|---|---|
| 1 | PS row 4 `PRIOR_NSQF_LEVEL(4)` `NOT_MET` for any of Q0301/Q2301/Q0103, both interpretations | **PASS, PROVISIONAL (Q-B)** | Held levels 2.5, 3.5, 3.5 are below 4; holds with relevance declared, undeclared and declared none. Under `CAP`: `UNKNOWN(ENGINE_USE_UNDECIDED)`. |
| 2 | Holding Q0301: level of SSMO row 9 and IC row 4 satisfied under both (`CONDITIONAL`) | **PASS, PROVISIONAL (Q-B)** | Also the exact-versus-at-least differences where the held level is higher. Under `CAP`: `UNKNOWN`. |
| 3 | `nsqf_level_match = null` with ≥ 1 declared holding: every `PRIOR_NSQF_LEVEL` is `UNKNOWN(CONFIG_UNSET)`; declared none: `NOT_MET` | **PASS** | All 7 components of the 4 pilots; not Q-B dependent (the config check precedes caps). |
| 4 | Age 17: `NOT_MET`, decisive reason on the age rule | **PASS** | All four targets, any config; boundaries 18/18/18/20. |
| 5 | Without OV-002…004, SSMO rows 2 to 4 not `MET`/`CONDITIONAL` | **PASS** | Under the richest profile; reasons and `OVERLAY_PENDING_APPROVAL` flags checked; `approved: []` asserted. |
| 6 | SMO → SSMO claim in `supporting_evidence`, never changes the verdict | **PASS (with D-5)** | Shown for a held, declared-relevant qualification with its verbatim text; removing every claim changes only `supporting_evidence`, for all pilots and profiles. No name-based link to the target is asserted. |
| 7 | Credits invariance | **PASS** | Every qualification, membership and credit-group value mutated (3 values); results identical for 4 targets × 7 profiles × 3 configs. |
| 8 | `CONDITIONAL` has ≥ 1 condition; `UNKNOWN` has ≥ 1 reason | **PASS** | Enforced by `EligibilityResult` and asserted over all pilots, profiles, configs and both policies. |

P3.3 is marked **DONE as an engineering stage with criteria 1 and 2 PROVISIONAL on Q-B**, the same convention as the P1 stages. If you prefer "in progress" until Q-B is decided, change the heading in `TASKS.md`.

**12. Documentation reviewed and updated.**

| Document | Reviewed | Changed? | Why |
|---|---|---|---|
| `TASKS.md` | yes | **yes** | Phase 3 status; P3.3 heading and Done block (D-1 to D-6, Q-B outcome and discrepancy, verification, criteria, limits). |
| `README.md` | yes | **yes** | Phase 3 Status row names P3.3 and its provisional status. |
| `docs/decisions/P3_2_AUDIT.md` | yes | **yes** | Appended "P3.3 follow-up": obligations done; Q-B stated and still OPEN; Q-A and Q-C unchanged. |
| `docs/PROJECT_HANDOFF.md` | yes (gitignored) | **yes** | One note at the top of §7. |
| `ARCHITECTURE.md` | yes | no | The evaluator follows §11.1 to §11.3. The Q-B tension between §11.2/§11.5 and §11.4 is recorded in `TASKS.md` and the audit record, not edited into the architecture. |
| `API_SPEC.md` | yes | no | The result mirrors §2.4. The E07 example was not rewritten; its decisive-row difference is noted above. |
| `docs/decisions/MODULE_A_GATE.md`, `docs/feasibility/*`, `config/*` | boundary and hashes only | no | Module A stays `NO_GO`; no labour-market data was used; nothing changed. |
| `session_log.md` | yes | yes | This entry, appended; Runs 1 to 5 verified byte-identical. |

**13. Outstanding issues and blockers.**
- **Q-B (your decision).** Is the curated qualification-level NSQF value (`engine_use` `UNKNOWN`) comparable? Either answer is a small change: the default of `undecided_level_use`, or a curated `engine_use` for that value. Until then criteria 1 and 2 and the E07-profile test are provisional.
- **D-2 and D-5 for your review.** D-2: `decisive_rule_ids` omits the age rule, as API_SPEC words it, so an age-limited target has an empty list. D-5: supporting evidence shows all claims of a held, declared-relevant qualification (for example SMO's "Knits (Horizontal)" beside the SSMO claim), because linking a claim to the target is an inference.
- **Q-A** (reason code for the D5 case) and **Q-C** (serving requires `PASSED`) unchanged. The registry → `curation` transitive import is unchanged (audit 6c).
- `HeldQualification` has no origin for HYPOTHETICAL holdings; P3.6/P3.7 must add it. `explanation` is empty until P3.8. Error mapping (`UnknownEntityError` to `UNKNOWN_QUALIFICATION_CODE`) is P3.10/P5.
- Unchanged and open: user acceptance of P2.1 to P2.5 (Module A `NO_GO`), Q-6, Q-8, DQ-01/02/03, Q-2, A2, P1.5-R1, Q0301/E5, Q2301/E1#c1, OV-002/003/004/034/035. P1 and Phase 3 are not declared complete. Nothing is committed; `docs/PROJECT_HANDOFF.md` and `data/` are gitignored.

**14. Recommended next task.** Decide Q-B (and, cheaply, Q-A, D-2 and D-5), then **P3.4 static graph edges** (`graph/edges.py`: `INCLUDES_NOS`, `SHARES_NOS` with core/non-core and version agreement, `PROGRESSION_CLAIM` to `CLAIM_TEXT` nodes, `ALIGNED_TO_NCO`; OBS-01 reproduced). It depends only on the registry, so it is independent of Q-B. Before it, decide whether to commit Runs 1 to 6.

---

## Run 7 — P3.4: Static graph edges

**1. Run and task.** Run 7 of this log (the log held Runs 1 to 6; the number was taken from it). Task P3.4, static graph edges (`TASKS.md` Phase 3). P3.5 and later were not started.

**2. Date and time.** 2026-11-02, about 00:21–00:35 IST (Asia/Kolkata, machine clock).

**3. Branch and HEAD.** Start and end: `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. Working directory `C:\skillathon26\SkillAdjGraphV2`. No commit, stage, fetch, pull, reset, rebase, merge, amend, clean or branch change; `git diff --cached` was empty at the start and at the end. No download, installation or external action.

**4. Working tree.**
- *Before:* modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `src/skillgraph/registry/__init__.py`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md`, `registry/store.py`, `eligibility/logic.py`, `components.py`, `evaluate.py` and the seven test files of Runs 3 to 6. `src/skillgraph/graph/__init__.py` was tracked and unmodified (a one-line docstring). Protected-file hashes: `config/overlay_approvals.yaml` `287e3f67…df1f3` (`approved: []`); `config/labour_market.yaml` `3ff5d350…c8e4`; the `data/` tree (SHA-256 over the sorted per-file hashes, the PowerShell method of Run 6) `d89db664…`. A byte copy of `session_log.md` (hash `6D093F4B…330F`), `TASKS.md` and `README.md` was kept in the scratchpad for the final comparison.
- *After:* the same paths plus untracked `src/skillgraph/graph/edges.py`, `tests/unit/test_graph_edges.py`, `tests/golden/test_graph_edges_pilot.py`, `tests/integration/test_graph_edges_build.py`, and **modified (tracked) `src/skillgraph/graph/__init__.py`** (re-exports). `TASKS.md`, `README.md`, `docs/decisions/P3_2_AUDIT.md` (untracked directory), `session_log.md` carry further edits; `docs/PROJECT_HANDOFF.md` (gitignored) is also edited. All three protected hashes re-checked after the full suite and the mutation runs: **unchanged**. `config/overlay_approvals.yaml` is still `approved: []`.

**5. Objective.** Implement the repository-defined P3.4 deliverable: `graph/edges.py` with the four static edge types (`INCLUDES_NOS`, `SHARES_NOS` with core/non-core and version agreement, `PROGRESSION_CLAIM` to `CLAIM_TEXT` nodes, `ALIGNED_TO_NCO`) and the legend, from the P3.1 registry only, reproducing OBS-01; test it; synchronise the documents. Out of scope: inference edges (P3.5), `ELIGIBILITY_ROUTE` and paths (P3.6), ranking, explanations, the E08 view, any change to P3.1 to P3.3.

**6. Inspected.** `session_log.md` (all of Runs 1 to 6), `TASKS.md` (Phase 3 status, P3.1 to P3.5, P3.6 neighbours), `ARCHITECTURE.md` (§6.2 import rules, §8.5 OBS-01, §8.6 DQ-02, §10.1 to §10.3), `API_SPEC.md` (§2.1 `NodeType` / `EdgeType`, E08 with its request, `GraphEdge` / `LegendEntry` shapes and example, §4 signature `graph.build_static_edges(registry, include_inference) -> list[GraphEdge]`, traceability), `README.md`, `docs/PROJECT_HANDOFF.md` (§7 notes), `docs/decisions/P3_2_AUDIT.md`. Code: `registry/store.py`, `registry/__init__.py`, `graph/__init__.py`, `model/qualification.py` (`NosMembership`, `Module`, `ProgressionClaim`, `ResolvedTarget`), `model/evidence.py` (`Valued`, `QualityFlag`, `EvidenceClass`), `model/conflict.py`, `model/occupation.py`, `model/ids.py`, `model/base.py`, `eligibility/evaluate.py` (module docstring, error convention), `tests/unit/model_factory.py`, `tests/unit/test_registry_store.py`, `tests/integration/test_registry_load.py`, `tests/integration/synth_tree.py`, `tests/golden/conftest.py`. Data (read only, through the registry): the real build `cb-601c0399c999` (`BuildInfo.validation == "PASSED"`): every NOS-table row with its version, Core/Non-Core label, evidence ids and conflict ids; all claims; stated NCO codes; the three registered conflicts.

**7. Created / modified.**
- Created: `src/skillgraph/graph/edges.py`; `tests/unit/test_graph_edges.py` (85 tests); `tests/golden/test_graph_edges_pilot.py` (21 tests); `tests/integration/test_graph_edges_build.py` (5 tests).
- Modified: `src/skillgraph/graph/__init__.py` (re-exports, a tracked file); `TASKS.md` (Phase 3 status; P3.4 heading and Done block with D-7 to D-14, exceptions, verification); `README.md` (the Phase 3 Status row); `docs/decisions/P3_2_AUDIT.md` (a short "P3.4 note" appended); `docs/PROJECT_HANDOFF.md` (gitignored; one note at the top of §7); `session_log.md` (this entry).
- Not modified: `ARCHITECTURE.md`, `API_SPEC.md`, `registry/`, `eligibility/`, any model, config, overlay approval, frozen script, dataset or earlier test.
- Scratchpad only: probe scripts, a mutation harness (it wrote its first mutation and crashed once on a bad interpreter path; I restored `edges.py` from the backup immediately and added an exit-time restore), a byte backup of `edges.py`, the docs patch script, byte backups of `session_log.md`, `TASKS.md`, `README.md`, and the draft of this entry.

**8. Decisions and reasons.** (Full text in the `edges.py` docstring and `TASKS.md` P3.4; numbering continues D-1 to D-6 of P3.3.)
- **Contract found, not invented.** Edge types, directions, classes and attributes are from ARCHITECTURE §10.3 and API_SPEC E08; the OBS-01 sets and the OV-040 requirement are from TASKS P3.4, ARCHITECTURE §8.5 and §8.6. Nothing needed Q-B: P3.4 never reads a qualification-level NSQF value or an `engine_use`; the only value-level field it consults on a NOS-table row is `conflict_id`.
- **D-7** Edges and legend only; no nodes, no `focus` / `include_catalogue_only` filter (the E08 view, P3.10 / P5.4). `include_inference=True` raises `NotImplementedError`.
- **D-8** Provenance is the evidence ids of every printed cell of the NOS-table row (a membership is not itself a `Valued`); `SHARES_NOS` is the union over both rows of every shared code; all ids must resolve.
- **D-9** Invalid input is reported, never repaired: dangling endpoint, null NCO code, unresolved evidence or conflict id, or a relationship stated twice raises `EdgeBuildError` listing every problem. The contract is silent on duplicates; merging or choosing one would hide a conflicting source relationship.
- **D-10** `version_agreement`: `SAME` / `DIFFERENT` only if both rows print a version; otherwise `NOT_STATED`.
- **D-11** Core/Non-Core counts require agreement of both QFs; a disagreement is listed in an extra attribute `mixed_core_codes`. **This extends API_SPEC E08** (four attributes listed); reported as an exception, not edited into the specification.
- **D-12** Membership conflicts become `SOURCE_CONFLICT` / `INFO` flags with `refs = [conflict id]` on the `INCLUDES_NOS` edge and every `SHARES_NOS` edge that uses the membership.
- **D-13** Edge id `e:<TYPE>:<source key>:<target key>`; sorted `(type, source, target)`; `SHARES_NOS` stored once with `source < target`.
- **D-14** `SHARES_NOS` legend text is E08's verbatim; the other three entries are drafted from ARCHITECTURE §10.2 to §10.3 (E08 gives none).
- **`resolved_target` not read.** The name-based claim link is an INFERENCE for P3.5; ignoring it keeps the criterion "no `PROGRESSION_CLAIM` edge targets a qualification" true by construction and by `GraphEdge` validation. The synthetic tests show that a claim with a `resolved_target` changes nothing.
- **Q-A, Q-B, Q-C** preserved as unresolved; no P3.3 code, golden expectation or decision D-1 to D-6 was changed.
- **Line endings.** The repository's source and test files are CRLF; the two new/changed graph source files were converted to CRLF for consistency. Existing tests: none edited, weakened, skipped or deleted.

**9. Tests and checks performed.**
1. Initial inspection: clock, `git rev-parse HEAD`, `git status --short`, `git diff --cached --stat`, hashes of the two config files and of the `data/` tree, byte backups of the three documents.
2. Read-only probes of the real build through the registry (memberships, versions, conflict ids, claims, NCO codes), a smoke run of the new builder on it, and a probe of the builder-made synthetic tree.
3. `.venv\Scripts\python.exe -m pytest tests/unit/test_graph_edges.py -q` (first run: 2 failures, both in my own tests; see item 10).
4. `.venv\Scripts\python.exe -m pytest tests/golden/test_graph_edges_pilot.py -q` (first run: 2 failures in my own test helper; see item 10).
5. `.venv\Scripts\python.exe -m pytest tests/integration/test_graph_edges_build.py -q`.
6. Mutation harness over `edges.py` (16 mutations, each followed by the three new test files with `-x`; the file restored byte-identical and checked with `cmp`).
7. Full suite `.venv\Scripts\python.exe -m pytest -q`.
8. `.venv\Scripts\python.exe tools/check_legacy_baseline.py`.
9. After the work: re-hash of `overlay_approvals.yaml`, `labour_market.yaml` and the `data/` tree; `git rev-parse HEAD`; `git diff --cached --stat`; `git status --short`; byte comparison of the earlier `session_log.md` content with the new file's prefix.
10. Not done: `build` / `validate` (they write into `data/curated/`); no linter or type checker is configured, so none was run. The older installed builds are refused by the loader (Run 3), so the edge builder was exercised on one real build only.

**10. Exact results.**
- `test_graph_edges.py`: first run **83 passed, 2 failed**. Both failures were in my own tests: a `records()` helper that did not skip a null NCO code (the test used a dict where the model needs a `Valued`), and a source-scan assertion that wrongly forbade `.value` on two enum labels. Fixed in the tests; the builder was not changed. Then **85 passed** (about 1.1 s).
- `test_graph_edges_pilot.py`: first run **19 passed, 2 failed**: my helper passed a duplicated list of evidence records to `Registry.from_records`, which (correctly) refuses duplicate ids. Fixed in the test. Then **21 passed** on the real build `cb-601c0399c999`.
- `test_graph_edges_build.py`: **5 passed**.
- Mutations: **16 of 16 killed**, no survivor (core counted from one side, version rule inverted, blank version counted as stated, flags dropped on `SHARES_NOS`, evidence from one side only, mixed codes hidden, final sort removed, duplicates silently merged, NCO edges skipped, claim edges skipped, bridge modules skipped, `include_inference` ignored, flags dropped on `INCLUDES_NOS`, evidence not resolved, dangling unit not checked, version not stripped). The first harness run crashed after writing its first mutation (relative interpreter path); the file was restored from the backup before anything else ran, and again at the end (`cmp`: identical).
- Focused (three new files): **111 passed**. After the CRLF conversion: **111 passed**.
- Full suite: **2930 passed, 1 warning** in 36 s (Run 6: 2819; difference 111 = the new tests). The warning is the existing Pydantic serializer warning in `tests/unit/test_eligibility_rules.py`, not investigated. `tools/check_legacy_baseline.py`: "MATCH with baseline legacy_tests_2026-10-31: 23 passed, 1 failed, 0 errors, 0 skipped (DQ-01 unresolved)". The legacy suite remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
- Real build `cb-601c0399c999`: **40 edges** in about 6 ms: 27 `INCLUDES_NOS` (including 2 bridge modules), 3 `SHARES_NOS`, 6 `PROGRESSION_CLAIM`, 4 `ALIGNED_TO_NCO`. `SHARES_NOS`: {Q0103, Q2301} = {AMH/N0309, DGT/VSQ/N0102}, {Q0103, Q2101} = {DGT/VSQ/N0102}, {Q2101, Q2301} = {DGT/VSQ/N0102}; all Core count 0; flag `conflict:OV-040` on the two SSMO edges only; `INCLUDES_NOS` flags: `conflict:OV-040` (Q2301 to N0102) and `conflict:OV-036` (Q2301 to N2302, a credits conflict on the membership). Observed version agreement: N0309 `SAME`; N0102 `NOT_STATED` with SSMO (SSMO prints no version) and `SAME` between IC and PS.
- After the work: overlay approvals `287e3f67…` (`approved: []`), `labour_market.yaml` `3ff5d350…`, `data/` tree `d89db664…`: **all unchanged**. HEAD unchanged; nothing staged.

**11. Acceptance criteria (TASKS P3.4), on the real build.**

| # | Criterion | Result | Notes |
|---|---|---|---|
| 1 | OBS-01 reproduced: `SHARES_NOS` exactly for {SSMO, IC}, {IC, PS}, {SSMO, PS} with the listed codes | **PASS** | Exactly three edges; code sets equal; also cross-checked against the registry's own NOS-user index. |
| 2 | SMO has no `SHARES_NOS` edge | **PASS** | |
| 3 | All shared units Non-Core | **PASS** | `core_shared_count == 0`, no mixed code; also read independently from the NOS tables. |
| 4 | DGT/VSQ/N0102 edges carry the OV-040 flag where the SSMO membership is involved | **PASS** | The two SSMO `SHARES_NOS` edges and the SSMO `INCLUDES_NOS` edge of N0102; no other N0102 edge. |
| 5 | No `PROGRESSION_CLAIM` edge targets a qualification code except via a reviewed inference | **PASS** | All six end at `claim:` nodes; `resolved_target` is not read (P3.5); the model rejects a qualification target. |
| D | Deliverable: legend text from API_SPEC E08 | **PROVISIONAL** | Only the `SHARES_NOS` text exists in E08 (used verbatim, pinned against the file); the other three are drafted (D-14). |

None of the criteria depends on Q-B. P3.4 is marked **DONE as an engineering stage with exceptions** (the D-11 attribute extension and the drafted legend wording), the same convention as P1 and P3.3. If you prefer "in progress" until those are decided, change the heading in `TASKS.md`.

**12. Documentation reviewed and updated.**

| Document | Reviewed | Changed? | Why |
|---|---|---|---|
| `TASKS.md` | yes | **yes** | Phase 3 status; P3.4 heading and Done block (code, sources, D-7 to D-14, verification, criteria, exceptions, limits). |
| `README.md` | yes | **yes** | Phase 3 Status row names P3.4 and no longer says edges are unstarted. |
| `docs/decisions/P3_2_AUDIT.md` | yes | **yes** | Short P3.4 note: Q-A, Q-B, Q-C unchanged and not touched. |
| `docs/PROJECT_HANDOFF.md` | yes (gitignored) | **yes** | One note at the top of §7. |
| `ARCHITECTURE.md` | yes | no | The edges follow §10.2 to §10.3 and §8.5. The Core/Non-Core disagreement case is not covered by the text; recorded in `TASKS.md`, not edited in. |
| `API_SPEC.md` | yes | no | `GraphEdge`, `LegendEntry`, `EdgeType` and the `SHARES_NOS` example match, except the extra `mixed_core_codes` key (reported). The E08 example is "abridged" and its `version_agreement` values are "illustrative"; the real build gives different values (observed above). |
| `docs/decisions/MODULE_A_GATE.md`, `docs/feasibility/*`, `config/*` | boundary and hashes only | no | Module A stays `NO_GO`; no labour-market data was used; nothing changed. |
| `session_log.md` | yes | yes | This entry, appended; Runs 1 to 6 verified byte-identical. |

**13. Outstanding issues and blockers.**
- **Your review of D-7 to D-14**, especially **D-11** (an extra `SHARES_NOS` attribute that API_SPEC E08 does not list; decide to accept and amend E08, or prescribe another rule for a unit that the two QFs classify differently) and **D-14** (drafted legend wording for `INCLUDES_NOS`, `PROGRESSION_CLAIM`, `ALIGNED_TO_NCO`). Both are small, localised changes.
- **D-9** makes a duplicated relationship fail the whole edge build (fail-closed). If a future build legitimately lists one NOS unit twice in a QF, that needs a data/contract decision, not a silent merge.
- **Node assembly and the E08 filters** (`focus`, `depth`, `node_types`, `include_catalogue_only`) are not built; P3.10 / P5.4 must do it. `NCO_TITLE_NOT_FOUND` and similar node flags belong there.
- Version agreement is observed on four curated qualifications of one build; E08's example values are illustrative and do not match.
- Unchanged and open: **Q-A, Q-B, Q-C**; D-2 and D-5 of P3.3 (your review); user acceptance of P2.1 to P2.5 (Module A `NO_GO`), Q-6, Q-8, DQ-01/02/03, Q-2, A2, P1.5-R1, Q0301/E5, Q2301/E1#c1, OV-002/003/004/034/035. P1 and Phase 3 are not declared complete. Nothing is committed; `docs/PROJECT_HANDOFF.md` and `data/` are gitignored.

**14. Recommended next task.** **P3.5 experimental inference edges** (`graph/inference.py`; depends on P3.4 for `GraphEdge`, `EdgeType` and the `include_inference` hook, which currently raises) or, on the critical path, **P3.6 path enumeration** (depends on P3.3 and, for the inference-invariant test, on P3.5's toggle). Before either: decide D-11 and D-14 (cheap), Q-B (affects P3.6 reachability from catalogue-only and uncertain-level holdings), and whether to commit Runs 1 to 7.

---

## Run 8 — P3.4 closeout: D-11 and D-14

**1. Run and task.** Run 8 of this log (the log held Runs 1 to 7). Narrow contract closeout of two P3.4 decisions: D-11 (mixed Core/Non-Core classification) and D-14 (graph legend wording). P3.5 and later were not started.

**2. Date and time.** 2026-11-02, about 00:32–00:50 IST (machine clock).

**3. Branch and HEAD.** Start and end: `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. No commit, stage, fetch, reset, clean, rebase, merge or branch change; `git diff --cached` empty at start and end. No download or installation.

**4. Working tree.**
- *Before:* as at the end of Run 7. `session_log.md` hash `F4433A7A…ECBB3`; `config/overlay_approvals.yaml` `287e3f67…` (`approved: []`); `config/labour_market.yaml` `3ff5d350…`; `data/` tree `d89db664…`.
- *After:* the same paths plus untracked `docs/decisions/P3_4_CLOSEOUT.md` (inside the already-untracked `docs/decisions/`). Modified in this run: `src/skillgraph/graph/edges.py` (one legend string and the D-14 docstring note), `tests/unit/test_graph_edges.py` (+6 tests), `TASKS.md`, `docs/PROJECT_HANDOFF.md` (gitignored), `session_log.md`. The three protected hashes are re-checked at the end (item 10).

**5. Objective.** (a) Decide, from the actual contract text, whether `mixed_core_codes` conflicts with API_SPEC E08. (b) Review the four legend strings against E08, ARCHITECTURE §10.2 to §10.3 and the build's evidence; keep the `SHARES_NOS` wording verbatim; claim no approval that the evidence does not support.

**6. Inspected.** `session_log.md` (all of it), `TASKS.md` (P3.4 and its D-7 to D-14), `API_SPEC.md` (§1 conventions, E08 request/response/example lines 658 to 711, §2.1, §4), `ARCHITECTURE.md` (§8.5, §10.1 to §10.3, line 558 overlap sentence, DQ-15), `src/skillgraph/graph/edges.py`, the output of `static_legend()` (printed, not taken from the earlier report), and the real build `cb-601c0399c999` (read only): the source document and extraction method behind every evidence id cited by each edge type.

**7. Created / modified.**
- Created: `docs/decisions/P3_4_CLOSEOUT.md` (evidence table, dispositions, exact strings).
- Modified: `src/skillgraph/graph/edges.py` (the `PROGRESSION_CLAIM` `does_not_mean` string; docstring D-14 note); `tests/unit/test_graph_edges.py` (six tests appended); `TASKS.md` (status paragraph, D-11, D-14, verification counts, criteria note, exceptions); `docs/PROJECT_HANDOFF.md` (one note at the top of §7); `session_log.md` (this entry).
- Not modified: `ARCHITECTURE.md`, `API_SPEC.md`, `README.md`, `docs/decisions/P3_2_AUDIT.md`, anything in `registry/`, `eligibility/`, `model/`, any config, overlay approval, dataset or earlier test.

**8. Decisions and findings.**
- **D-11: RESOLVED ON THE EVIDENCE, retained.** `API_SPEC.md:20` "Additive fields are allowed within v1"; `:677` `attributes: object` (free-form); `:681` lists four keys and does not say "exactly" or "only"; no closed-set wording exists in the file; `api/schemas.py` does not exist yet. So no contract conflict is established. **Correction of my Run 7 wording:** I wrote that E08 "lists exactly four" attributes; that overstated the text. The attribute preserves a source disagreement without asserting a classification (counted in neither count; each QF's label stays on its `INCLUDES_NOS` edge). A documentation-only amendment of `API_SPEC.md:681` is recommended and **awaits explicit approval**; Option B (a `SEMANTIC_AMBIGUITY` flag instead of the key) is recorded for the stricter reading. No graph semantics changed. Consumer rule recorded for P3.8: do not say "both Non-Core" when `mixed_core_codes` is non-empty.
- **D-14: REVIEWED, NOT APPROVED, one defect corrected.** `SHARES_NOS` is verbatim E08 (tested against the file). The other three are drafted wording, consistent with ARCHITECTURE §10.2 to §10.3 and with the evidence (QF documents behind every `INCLUDES_NOS`, `PROGRESSION_CLAIM` and `ALIGNED_TO_NCO` edge). The `PROGRESSION_CLAIM` `does_not_mean` said "The text names a qualification in this graph", which can be false (SMO's claim text equals SSMO's title; DQ-15 notes "Sampling Coordinator" matches AMH/Q1801 by name). It now reads "That the text is linked to a qualification in this graph (any such link is an experimental inference), that anyone is eligible for it, or that people make this move." No edge, id, attribute or ordering changed. "Item 15" in the `PROGRESSION_CLAIM` meaning comes from ARCHITECTURE §10.2; the evidence records carry no `location` text, so it is not independently confirmed.
- **Tests added** pin the reviewed legend strings (a later change must be deliberate), check that no affirmative `meaning` promises eligibility, employability or a path, show the claim-equals-title case yields only a claim node, and pin D-11 as additive (the documented four keys keep their types; the one extra key is `mixed_core_codes`; the sum invariant; the disagreement stays traceable).
- **Not done, on purpose:** no edit of `API_SPEC.md` or `ARCHITECTURE.md`; Q-A, Q-B, Q-C untouched; D-1 to D-6, D-7 to D-10, D-12, D-13 unchanged.

**9. Tests and checks performed.** (1) Start state: clock, HEAD, `git diff --cached`, hashes of the three protected items and of `session_log.md`, byte copies of `session_log.md` and `TASKS.md`. (2) `static_legend()` printed. (3) Read-only probe of evidence sources per edge type on the real build. (4) `pytest tests/unit/test_graph_edges.py tests/golden/test_graph_edges_pilot.py tests/integration/test_graph_edges_build.py -q`. (5) `pytest -q`. (6) `tools/check_legacy_baseline.py`. (7) Final hashes, `git status`, byte comparison of Runs 1 to 7. Not done: no linter or type checker is configured; `build` / `validate` not run.

**10. Exact results.**
- Focused graph tests, first run after adding the tests: **116 passed, 1 failed**: my new wording test scanned the negated half for affirmative phrases and so flagged "is eligible" in `does_not_mean`. Fixed in the test (it now scans only `meaning`). Then **117 passed** (91 unit, 21 golden, 5 integration).
- Full suite: **2936 passed, 1 warning** (Run 7: 2930; difference 6 = the new tests). The warning is the existing Pydantic serializer warning in `tests/unit/test_eligibility_rules.py`.
- `tools/check_legacy_baseline.py`: "MATCH with baseline legacy_tests_2026-10-31: 23 passed, 1 failed, 0 errors, 0 skipped (DQ-01 unresolved)". The legacy suite remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
- Protected files, `git`, and Runs 1 to 7: see the final report of this run (item 11).

**11. Final verification.** Recorded after this entry was written: overlay approvals `287e3f67…` (`approved: []`), `labour_market.yaml` `3ff5d350…`, `data/` tree `d89db664…` all unchanged; HEAD unchanged; nothing staged; Runs 1 to 7 byte-identical (this entry was appended to the Run 7 file contents).

**12. Documentation reviewed and updated.** `TASKS.md` updated; `docs/decisions/P3_4_CLOSEOUT.md` created; `docs/PROJECT_HANDOFF.md` note added (gitignored); `README.md` reviewed, unchanged (its row says "accepted with exceptions", still true); `ARCHITECTURE.md`, `API_SPEC.md` reviewed, not edited.

**13. Outstanding.** Explicit approval needed for (a) the documentation amendment of `API_SPEC.md:681` (or Option B), and (b) the three drafted legend entries. Unchanged and open: Q-A, Q-B, Q-C; D-2 and D-5 of P3.3; Module A `NO_GO` acceptance; Phase 1 evidence gates. Nothing is committed.

**14. Recommended next task.** With D-11 and D-14 closed on the evidence, **P3.6 path enumeration** is the critical-path stage, but it should wait for a decision on Q-B (it governs which holdings can start a path). **P3.5 inference edges** can start now (it depends only on P3.4's `GraphEdge` and the `include_inference` hook) and unblocks the P3.6 inference-invariant test.

---

## Run 9 — P3.5: Experimental inference edges

**1. Run and task.** Run 9 of this log (the log held Runs 1 to 8). Task P3.5, experimental inference edges (`TASKS.md` Phase 3). P3.6 and later were not started.

**2. Date and time.** 2026-11-02. The start time was not recorded; the machine clock read 00:50:56 +0530 at the final verification.

**3. Branch and HEAD.** Start and end: `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`. Working directory `C:\skillathon26\SkillAdjGraphV2`. No commit, stage, fetch, pull, reset, clean, rebase, merge, amend or branch change; `git diff --cached` was empty at the start and at the end. No download or installation.

**4. Working tree.**
- *Before:* as at the end of Run 8 (modified `ARCHITECTURE.md`, `README.md`, `TASKS.md`, `config/labour_market.yaml`, `src/skillgraph/graph/__init__.py`, `src/skillgraph/registry/__init__.py`, `tests/unit/test_settings.py`; untracked `docs/decisions/`, `docs/feasibility/`, `session_log.md` and the Run 3 to 8 source and test files). Protected items: `config/overlay_approvals.yaml` `287e3f67…81f1` (`approved: []`), `config/labour_market.yaml` `3ff5d350…c8e4`, `session_log.md` `6aef7322…` (98,541 bytes); the `data/` tree (SHA-256 over the sorted per-file hashes, the Git Bash method of this run: `find . -type f | sort | xargs sha256sum | sha256sum`) began `bb467525…`. Byte copies of `session_log.md`, `TASKS.md`, `README.md`, `docs/PROJECT_HANDOFF.md`, `docs/decisions/`, `edges.py` and `graph/__init__.py` were kept in the scratchpad.
- *After:* the same paths plus untracked `src/skillgraph/graph/inference.py`, `src/skillgraph/graph/claim_candidates.py`, `tests/unit/test_graph_inference.py`, `tests/golden/test_graph_inference_pilot.py`, `tests/integration/test_graph_inference_build.py`, and `docs/decisions/P3_5_INFERENCE.md` (inside the already-untracked `docs/decisions/`). Modified in this run: `src/skillgraph/graph/edges.py` (untracked file), `src/skillgraph/graph/__init__.py` (tracked), `tests/unit/test_graph_edges.py` (untracked file), `TASKS.md`, `README.md`, `docs/PROJECT_HANDOFF.md` (gitignored), `session_log.md`. The protected hashes are re-checked in item 11.

**5. Objective.** Implement only what the repository-defined P3.5 contract specifies: derive the contract from `TASKS.md`, `ARCHITECTURE.md` and `API_SPEC.md` before coding; reuse P3.4's `GraphEdge`, edge types and `include_inference` hook; keep inference edges distinguishable, traceable, deterministic and unable to affect eligibility, feasibility, paths or authoritative records; where the contract is silent, record the gap instead of inventing a heuristic.

**6. Inspected.** `session_log.md` (all of Runs 1 to 8), `TASKS.md` (P3.4, P3.5, P3.6 and neighbours, the Phase 3 status paragraph), `ARCHITECTURE.md` (§10.1 to §10.3, §13.4, §13.5, DQ-15, line 87 scope), `API_SPEC.md` (§2.1 `EdgeType` / `QualityFlagCode`, E08 request, response, `GraphEdge`, warnings; E09 `include_inference`; §4), `docs/decisions/P3_2_AUDIT.md` and `P3_4_CLOSEOUT.md` (headings and the D-11 / D-14 status), `README.md`, `docs/PROJECT_HANDOFF.md` (§7 notes), `config/default.yaml` and `settings.py` (`inference.enabled` only), `src/skillgraph/graph/edges.py`, `model/occupation.py` (`NcoLevels`), `model/qualification.py` (`ProgressionClaim`, `Titles`), `registry/store.py` (public lookups), `tests/unit/test_graph_edges.py`, `tests/golden/test_graph_edges_pilot.py`, `tests/integration/test_graph_edges_build.py`, `tests/unit/model_factory.py`, `tests/golden/test_eligibility_pilot.py`. Data (read only, through the registry): the real build `cb-601c0399c999` (`BuildInfo.validation == "PASSED"`): stated NCO codes, occupation records, claims and catalogue titles of all 37 qualifications.

**7. Created / modified.**
- Created: `src/skillgraph/graph/inference.py`; `src/skillgraph/graph/claim_candidates.py`; `tests/unit/test_graph_inference.py` (93 tests); `tests/golden/test_graph_inference_pilot.py` (15); `tests/integration/test_graph_inference_build.py` (4); `docs/decisions/P3_5_INFERENCE.md`.
- Modified: `src/skillgraph/graph/edges.py` (the `include_inference` hook; the `GraphEdge` contract for `NCO_GROUP_PROXIMITY`; docstrings; no static id, attribute, meaning or order changed); `src/skillgraph/graph/__init__.py` (re-exports); `tests/unit/test_graph_edges.py` (one test replaced, item 8); `TASKS.md` (Phase 3 status paragraph; P3.5 heading and Done block); `README.md` (the Phase 3 Status row); `docs/PROJECT_HANDOFF.md` (gitignored; one note at the top of §7); `session_log.md` (this entry).
- Not modified: `ARCHITECTURE.md`, `API_SPEC.md`, `config/*` (in particular `overlay_approvals.yaml` and `labour_market.yaml`), anything in `data/`, `registry/`, `eligibility/`, `model/`, `curation/`, any earlier test other than the one above, `docs/decisions/P3_2_AUDIT.md`, `P3_4_CLOSEOUT.md`.
- Scratchpad only: probe scripts, the mutation harness, documentation-edit scripts, byte backups, the draft of this entry. Line endings: the repository's source and test files are CRLF and the new ones were written CRLF; the Markdown documents are LF and were edited in binary mode.

**8. Decisions and reasons.** (Full text in `docs/decisions/P3_5_INFERENCE.md` and `TASKS.md` P3.5.)
- **Contract found.** The documents fully specify one inference edge: `NCO_GROUP_PROXIMITY` (qual ↔ qual; stated NCO codes sharing a 4-digit unit group, 3-digit configurable; `INFERENCE`, `experimental`; hidden by default; never feasibility). `TITLE_SIMILARITY` is "COULD and not planned". The documents do **not** specify attributes, confidence semantics, provenance form, a settings key, legend wording or the claim-normalisation rule. Because a meaningful safe implementation of the specified part exists, the verdict is not BLOCKED; the gaps are recorded as questions and the narrowest choices were taken.
- **D-15 to D-20** (the edge): one edge per unordered pair of distinct qualifications, several shared groups in one edge; attributes `group_digits`, `shared_groups`, `codes_by_qualification` and nothing else (no score of any kind); `evidence_ids` are the evidence of the stated codes behind the edge; identity and order as D-13; invalid input reported, never repaired, as D-9; the level is a keyword parameter `nco_group_digits` (4 or 3) because no settings key is specified; `INFERENCE_EXPERIMENTAL` flag (severity `INFO`) on every edge.
- **D-21 to D-23** (claim candidates): an unreviewed candidate list, not edges, because the contract defines no edge type for a claim-to-qualification link and requires review; the normalisation is the narrowest reading that reproduces the two contract examples (the claim's own trailing direction label removed, NFKC, case-fold, letters/digits tokens), exact equality with the normalised **catalogue** title; ambiguity and self-reference reported, not resolved; nothing is written to the build's `eligibility_rules_review.md` because that file lies in the protected `data/` tree and is a generated snapshot.
- **Design.** `build_static_edges(registry, include_inference, *, nco_group_digits=4)` returns the unchanged static edges plus the inference edges, sorted by the same key; the static sub-list is value-equal and order-equal to the default result (tested byte-for-byte). `inference.py` imports `edges.py` for the edge types, so the hook imports it inside the function. The change to the signature of API_SPEC §4 is one added optional keyword.
- **One existing test replaced.** `test_inference_edges_are_not_built_here_and_asking_for_them_is_an_error_not_a_silent_omission` asserted `NotImplementedError` for `include_inference=True`, which D-7 described as the behaviour until P3.5. P3.5 is the deliverable that replaces it. The new test keeps every other check and adds "static edges unchanged when enabled". No test was weakened, skipped or deleted.
- **Preserved.** Q-A, Q-B and Q-C untouched (no eligibility, registry or P3.3 file changed). D-11 `mixed_core_codes` semantics and the Core / Non-Core / mixed distinction untouched. D-14 stays **reviewed, not approved**; the new legend entry is drafted and not approved; the unresolved source-location question for "item 15" (D-14) was not touched.
- **Open (new): Q-D** D-21 normalisation (one candidate not anticipated by the contract), **Q-E** location of the reviewed claim-candidate artefact, **Q-F** settings key for the 3-digit level, **Q-G** approval of the drafted attributes and legend and a documentation-only E08 amendment, **Q-H** the function name.

**9. Tests and checks performed.**
1. Initial inspection: `git rev-parse HEAD`, `git status --short`, `git diff --cached --stat`, hashes of the config files, of `session_log.md` and of the `data/` tree, byte copies.
2. Read-only probes of the real build through the registry (stated codes, occupations, claims, catalogue titles); a smoke run of the new builder on it (1 inference edge at 4 and at 3 digits; 3 claim candidates).
3. `.venv\Scripts\python.exe -m pytest tests/unit/test_graph_inference.py -q` (several runs while fixing my own fixtures, item 10).
4. `.venv\Scripts\python.exe -m pytest tests/golden/test_graph_inference_pilot.py -q` (the same).
5. `.venv\Scripts\python.exe -m pytest tests/integration/test_graph_inference_build.py -q`.
6. `pytest tests/unit/test_graph_edges.py tests/golden/test_graph_edges_pilot.py tests/integration/test_graph_edges_build.py -q` (one expected failure, then green).
7. Mutation harness (26 mutations of `inference.py`, `claim_candidates.py` and the new `edges.py` code; each followed by the four graph test files with `-x`; every file restored from a backup and checked with `cmp`).
8. Related files: the graph, registry and eligibility test files (9 files).
9. Full suite `.venv\Scripts\python.exe -m pytest -q`.
10. `.venv\Scripts\python.exe tools/check_legacy_baseline.py`.
11. After the work: re-hash of the protected items, `git rev-parse HEAD`, `git diff --cached --stat`, `git status --short`, a diff of `edges.py` against its pre-run copy, byte comparison of Runs 1 to 8.
12. Not done: `build` / `validate` (they write into `data/curated/`); no linter or type checker is configured, so none was run; the P3.6 invariant test cannot be run because P3.6 does not exist.

**10. Exact results.**
- `test_graph_inference.py`: the first run (with `-x`) stopped at **1 failed, 9 passed**, then after the first fix **91 passed, 2 failed**. All three failures were in my own fixtures: (a) the catalogue-only record I added reused the id of `mk_qual(2)` (`duplicate qualification id: qual:TEST/Q9002`); (b) `cand_registry` built records from an empty list, so curated test records stated a code with no occupation. Fixed in the tests; the builder was not changed. Then **93 passed**.
- `test_graph_inference_pilot.py`: first run **13 passed, 2 failed**: my profile helper passed `True` where `TargetDeclaration.relevant_prior_qualifications` takes a tuple of references. Fixed in the test. Then **15 passed** (about 4.6 s) on the real build `cb-601c0399c999`.
- `test_graph_inference_build.py`: **4 passed**. All three new files together: **112 passed**.
- P3.4 graph tests after the hook change: **116 passed, 1 failed**, the failure being exactly the test replaced in item 8; after the replacement **91 passed** in `test_graph_edges.py`.
- Mutations: **25 of 26 killed**. Killed: levels swapped, 4-digit using the 3-digit group, self pairs, flag removed, evidence from one side, duplicate unchecked, unknown occupation ignored, all codes listed instead of the shared ones, first group only, directed, level unvalidated, bool accepted as a level, problems ignored, `include_inference` ignored, combined list unsorted, level not forwarded, flag not required by the model, class / direction unchecked by the model, NFKC removed, case-fold removed, label never stripped, whitespace-only tokens, self flag lost, ambiguity resolved to the first match, QF title used as a fallback. Survivor: "pair order reversed", an **equivalent mutant** (the final `sorted` restores the order). All files restored byte-identical (`cmp`).
- Related graph / registry / eligibility files (9): **2137 passed**.
- Full suite: **3048 passed, 1 warning** in about 45 s (Run 8: 2936; difference 112 = the new tests). The warning is the existing Pydantic serializer warning in `tests/unit/test_eligibility_rules.py`.
- `tools/check_legacy_baseline.py`: "MATCH with baseline legacy_tests_2026-10-31: 23 passed, 1 failed, 0 errors, 0 skipped (DQ-01 unresolved). This is a documented baseline, NOT a passing suite." The legacy suite remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**; a baseline match is not a passing suite.
- Real build `cb-601c0399c999`: 40 static edges unchanged (value- and order-equal with inference on); with inference 41. The one inference edge is `e:NCO_GROUP_PROXIMITY:AMH/Q0301:AMH/Q2301` (shared `8153`, codes `8153.0101` / `8153.0103`; at 3 digits `815`); IC (`7543.0301`) and PS (`3122.3551`) share no group with another pilot; SMO and SSMO have no `SHARES_NOS` edge. Claim candidates: AMH/Q0301/P1 → AMH/Q0305, AMH/Q0301/P2 → AMH/Q2301, AMH/Q2301/P1 → AMH/Q1801; no match for AMH/Q0103/P1, AMH/Q2101/P1 and P2. 480 pilot eligibility results (40 profiles × 3 level settings × 4 pilots) are identical before and after building the edges and on a registry whose records state no NCO code.
- Process notes: one shell heredoc containing triple quotes failed to parse and was rewritten as a script file (no partial edit was applied); a `sed` call that added carriage returns was checked and found to have produced pure CRLF files (no `\r\r\n`).

**11. Acceptance criteria (TASKS P3.5), on the real build.**

| # | Criterion | Result | Notes |
|---|---|---|---|
| 1 | Every inference edge has `evidence_class = INFERENCE` and `experimental = true` | **PASS** | Enforced by `GraphEdge`; asserted synthetic and real. |
| 2 | The edges are off unless requested | **PASS** | Default and `False` build static edges only. |
| 3 | SMO–SSMO share unit group 8153 and get an `NCO_GROUP_PROXIMITY` edge | **PASS** | Group read independently from the occupation records. |
| 4 | The invariant test in P3.6 passes | **PROVISIONAL** | P3.6 does not exist. Shown now: static edges byte-equal, no registry record changed, 480 eligibility results identical. Path-set and order invariance needs P3.6. |
| D1 | `NCO_GROUP_PROXIMITY`, 4-digit, 3-digit configurable | **PASS** | Configurable by parameter; settings key is Q-F. |
| D2 | Name-normalised claim → catalogue-title candidates "written to the review file" | **PROVISIONAL** | Implemented and recorded in `P3_5_INFERENCE.md` §5; no file written (Q-D, Q-E). |
| D3 | `TITLE_SIMILARITY` | not built | COULD, "not planned"; contract undefined. |

P3.5 is marked **DONE as an engineering stage with exceptions** (the PROVISIONAL items, the drafted and unapproved attribute and legend wording, the unbuilt `TITLE_SIMILARITY`), the same convention as P1, P3.3 and P3.4. If you prefer "in progress" until Q-D to Q-G are decided, change the heading in `TASKS.md`.

**12. Documentation reviewed and updated.**

| Document | Reviewed | Changed? | Why |
|---|---|---|---|
| `TASKS.md` | yes | **yes** | Phase 3 status paragraph; P3.5 heading and Done block (code, semantics, D-15 to D-23, Q-D to Q-H, verification, criteria, observations, limits). |
| `README.md` | yes | **yes** | Phase 3 Status row names P3.5; "P3.6 onwards not started". |
| `docs/decisions/P3_5_INFERENCE.md` | created | yes | Contract table, gaps, implementation, decisions, open questions, real-build observations, criteria. |
| `docs/PROJECT_HANDOFF.md` | yes (gitignored) | **yes** | One note at the top of §7. |
| `ARCHITECTURE.md` | yes | no | The edge follows §10.3 / §13.4; the gaps are recorded, not edited in. |
| `API_SPEC.md` | yes | no | `GraphEdge`, `EdgeType` and the warning match; the missing `NCO_GROUP_PROXIMITY` attribute set and legend are Q-G (documentation-only amendment proposed, awaiting approval). §4 gains one optional keyword in code only. |
| `docs/decisions/P3_2_AUDIT.md`, `P3_4_CLOSEOUT.md`, `MODULE_A_GATE.md`, `docs/feasibility/*`, `config/*` | boundary and hashes only | no | Module A stays `NO_GO`; Q-A to Q-C unchanged. |
| `session_log.md` | yes | yes | This entry, appended; Runs 1 to 8 verified byte-identical (item 13). |

**13. Final verification.** Recorded after this entry was written: `config/overlay_approvals.yaml` `287e3f67…` (`approved: []`), `config/labour_market.yaml` `3ff5d350…`, `data/` tree `bb467525…` all unchanged; HEAD unchanged; nothing staged; the earlier 98,541 bytes of `session_log.md` are an exact prefix of the file, so Runs 1 to 8 are byte-identical.

**14. Outstanding issues and blockers.**
- Your decisions on **Q-D** (claim normalisation), **Q-E** (where reviewed candidates live), **Q-F** (settings key), **Q-G** (approval of the drafted `NCO_GROUP_PROXIMITY` attributes and legend, and a documentation-only E08 amendment), **Q-H** (function name; keep recommended).
- **P3.6 invariant** ("toggling `include_inference` leaves path IDs, verdicts and order unchanged") is untested until P3.6; `inference_annotations` on path steps and the API-level warning / legend assembly belong to P3.6, P3.10 and P5.4.
- Unchanged and open: **Q-A, Q-B, Q-C**; D-14 approval of the three drafted static legend entries and the `API_SPEC.md:681` amendment for D-11; D-2 and D-5 of P3.3; user acceptance of P2.1 to P2.5 (Module A `NO_GO`); Q-6, Q-8; DQ-01/02/03, Q-2, A2, P1.5-R1, Q0301/E5, Q2301/E1#c1, OV-002/003/004/034/035. P1 and Phase 3 are not declared complete. Nothing is committed; `docs/PROJECT_HANDOFF.md` and `data/` are gitignored.

**15. Recommended next task.** **P3.6 path enumeration** (`graph/paths.py`) is the critical-path stage and now has the inference toggle it needs for its invariant test, but it should wait for a decision on **Q-B** (it governs which holdings can start a path). A cheap, independent alternative is to settle Q-D to Q-G and the Run 8 approvals first, then commit Runs 1 to 9.

---

## Run 10 — P3.6a: Path enumeration core (STOPPED at preflight; no code written)

- **Date:** 2026-11-02. **Outcome:** stopped safely at the mandatory preflight because one required contract detail cannot be resolved without amending the documented interface. No source, test, config, data or decision file was edited; only this entry was appended.
- **Explicit decisions received for this run (recorded, not yet implemented):**
  - **Q-B — PROVISIONAL COMPARE.** `undecided_level_use=COMPARE` stays the default for compatibility with the E07/E09 examples and the existing golden expectations. It is PROVISIONAL because `ARCHITECTURE.md` §11.4 and `config/curation_defaults.yaml` do not fully agree with those examples. It does not settle the qualification-level policy permanently. No curation data, `config/curation_defaults.yaml`, data build or `config/overlay_approvals.yaml` change; the `CAP` option and its tests stay.
  - **Hypothetical relevance — PROVISIONAL UNKNOWN.** When the relevance of a hypothetically completed qualification is not explicitly established, the outcome is `UNKNOWN` with reason `RELEVANCE_NOT_DECLARED`, never a fabricated `NOT_MET`. Both `Verdict.UNKNOWN` and `UnknownReasonCode.RELEVANCE_NOT_DECLARED` already exist (API_SPEC §2.1), so no public enum is needed. Requires later contract reconciliation.
- **Preflight findings (read-only):**
  1. **Signature has no source for the guard limit (BLOCKER).** `enumerate_paths(state, registry, config, scenario, max_steps, target_code) -> list[RawPath]` appears only in `API_SPEC.md` §4; `TASKS.md` P3.6 gives no signature. `ARCHITECTURE.md` §13.1 makes the expansion guard depend on `paths.max_expansions` (CONFIG), and `max_steps` has a hard limit of 4 (CONFIG). Both live in `Settings.paths` (`config/default.yaml`: `max_steps_limit: 4`, `max_expansions: 10000`, PROVISIONAL). Neither is reachable from the six parameters: `EngineConfig` is `{nsqf_level_match}` only (API_SPEC §2.3, `eligibility/evaluate.py`), and the engine functions are pure ("no I/O, no global state"). The layer that rejects `max_steps` > 4 is also unspecified: API_SPEC E09 says `422 LIMIT_EXCEEDED` at the request, the façade (`explore_paths`) is P3.10, and `LimitExceededError` is named in ARCHITECTURE §6.2 but defined nowhere. Resolving it needs a signature amendment (keyword-only limits, a limits parameter, or new `EngineConfig` fields). **Decision requested; options offered: required keyword-only `max_expansions` / `max_steps_limit` (recommended), keyword-only with duplicated defaults, or amend the contract first. The user chose: stop and amend the contract first.**
  2. **Types the signature needs do not exist in code:** `Scenario` (fields are specified in API_SPEC §2.3: `assume_intermediate_relevance`, `assumed_experience_gain_years_per_step`, `incremental_hours_policy`), `IncrementalHoursPolicy` (values `NONE`, `EXCLUDE_SHARED_NOS_CODE`, `EXCLUDE_SHARED_NOS_CODE_AND_VERSION` appear in ARCHITECTURE §12), `RawPath` (no field list anywhere) and `LimitExceededError`. `RawPath` is internal, so a minimal shape would need to be defined and recorded.
  3. **Origin of a hypothetically completed qualification.** `docs/decisions/P3_2_AUDIT.md` §5 says P3.6/P3.7 "must extend ... an `origin` on `HeldQualification`", and ARCHITECTURE §13.1 says the evidence class is `HYPOTHETICAL`. The field name is therefore stated; the accepted values are not (the evidence-class vocabulary suggests `DECLARED` default and `HYPOTHETICAL`). `HeldQualification` today has `ref`, `nsqf_level`, `level_cap` only. `ProfileState` cannot carry an origin, so `evaluate` would also need an additive keyword-only way to mark codes as hypothetical, and `holdings_complete` would have to be computed from the profile's own two lists, not from a merged list.
  4. **Relevance of hypothetical holdings.** `ProfileState` rejects a `relevant_prior_qualifications` entry that is not a declared holding, so the profile contract cannot name a not-yet-completed qualification as relevant. Under the existing contract the only way to establish its relevance is `scenario.assume_intermediate_relevance = true` (HYPOTHETICAL), which is the scenario-flag work excluded from P3.6a. `_prior_level` (`eligibility/components.py`) would give `NOT_MET` for a satisfying hypothetical holding that is absent from a declared list; that is the case the PROVISIONAL UNKNOWN decision must change.
  5. **Not assigned by TASKS.md to a sub-stage:** `TASKS.md` has no P3.6a/P3.6b split; `path_id` derivation is unspecified (the example `p-3c9e0a1b2d4f` shows only the format), so it would be left out of the enumeration core and reported.
- **Working-tree facts at the time of the preflight:** HEAD `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`; nothing staged; the unstaged and untracked files are those listed at the start of the session (runs 1 to 9 uncommitted), unchanged by this run.
- **Not done:** every P3.6a deliverable (`graph/paths.py`, tests, the origin extension, the record updates in `TASKS.md` and `docs/decisions/`). P3.6 and P3.6a are **not started and not complete**. The P3.5 inference-toggle invariant is still unproven.
- **Verification:** no test or tool was run (nothing was changed). `config/overlay_approvals.yaml` and `config/labour_market.yaml` were not touched and `data/` was not touched. Nothing was staged or committed.
- **To resume:** amend the contract for finding 1 (the user's choice), then rerun P3.6a. Suggested amendment: keyword-only `max_expansions: int` and `max_steps_limit: int` on `enumerate_paths` (no defaults), plus a decision on the accepted values of `HeldQualification.origin` (`DECLARED` default, `HYPOTHETICAL`) and on rejecting a non-default `Scenario` in P3.6a until P3.6b.

---

## Run 11 — P3.6a contract amendments (documentation only; no P3.6a implementation)

- **Date:** 2026-11-02. **Scope:** documentation only. Run 10 stopped at the preflight; between runs 10 and 11 a clarification run produced an amendment proposal in the conversation only (no file, no log entry). This run applied only the parts the user approved in principle and recorded every other proposal as an open item. No implementation, test, config, curation or `data/` file was changed; no test was run.
- **Approved and applied (documentation text only):**
  - **A-1** `API_SPEC.md` §4: `enumerate_paths` gains required keyword-only `max_expansions` and `max_steps_limit`, no defaults in `graph/`; the caller supplies the validated `Settings.paths` values; `graph/` does not import `settings`. The six positional parameters are unchanged. Compatible with ARCHITECTURE §13.1 ("`max_steps` default 3, hard limit 4, both CONFIG").
  - **A-2** `API_SPEC.md` §4, `TASKS.md` P3.6, `docs/decisions/P3_2_AUDIT.md` (new last section): `HeldQualification.origin` reuses `EvidenceClass.DECLARED` (default) and `EvidenceClass.HYPOTHETICAL`. Confirmed that both exist (`model/evidence.py`, API_SPEC §2.1) and that API_SPEC §2.4 already lists `HYPOTHETICAL` for `inputs_used`; noted that the P3.2 `InputUsed` type is narrower and must be widened with the code.
  - **A-3** `ARCHITECTURE.md` §13.1 (one sub-bullet): an undeclared-relevance hypothetical holding gives `UNKNOWN(RELEVANCE_NOT_DECLARED)`, not `NOT_MET`. Labelled PROVISIONAL and "not a permanent resolution". It applies ARCHITECTURE §11.2 step (5) and leaves steps (1)–(4) unchanged.
  - **A-4** `ARCHITECTURE.md` §6.2: only `graph/paths.py` may import `eligibility/` (the diagram's `GR --> ELI` arrow); `edges.py`, `inference.py` and `claim_candidates.py` keep the stricter rule; `graph/` never imports `settings`.
  - **A-5** `API_SPEC.md` §4, `TASKS.md` P3.6: the `RawPath { steps, verdict }` / `RawStep { index, from_state, target_code, eligibility }` minimum; ranking, explanations, hours and inference annotations stay with their stages; `path_id` and the other fields with no assigned stage are listed in O-5.
  - `TASKS.md` P3.6 also gained a status line (TODO, blocked on the open items) and the run split (P3.6a core, P3.6b scenario flags and the inference invariant).
- **NOT approved; recorded as open items O-1 to O-8 in `TASKS.md` P3.6 (the existing contract is preserved for each):** the `n ** max_steps` guard formula (O-1, analysed separately: n^k bounds the exact count of evaluator calls, n must be the `CURATED` not-held count, equality allowed was the recommendation); the `max_steps` checks and exception types (O-2); `LimitExceededError`'s module and any new exception such as one for a non-`CURATED` target (O-3); the permanent hypothetical-relevance policy and the missing declaration route (O-4); `path_id`, `from_state` order and the other unassigned `RawPath` fields (O-5); prefix emission, ordering, target stopping, held-target and no-rules behaviour (O-6); the keyword that passes hypothetical holdings to `evaluate` (O-7); rejection of non-default scenarios and where `Scenario` lives (O-8).
- **Unchanged:** Q-A, Q-B (`COMPARE`, PROVISIONAL, `CAP` kept), Q-C, Q-D to Q-H, legend and inference contracts, `config/default.yaml` (`max_expansions: 10000`, PROVISIONAL), the curation data, `config/overlay_approvals.yaml` (`approved: []`).
- **Files changed:** `API_SPEC.md` (§4), `ARCHITECTURE.md` (§6.2, §13.1), `TASKS.md` (P3.6), `docs/decisions/P3_2_AUDIT.md` (appended section), `session_log.md` (this entry). P3.6 and P3.6a are **not started**; Phase 3 is not complete.
- **Verification:** no code run. Pre-edit copies and hashes were taken; final checks are in the run report (diff of the five files, source/tests/config tree hash, `data/` tree hash, `approved: []`, HEAD, nothing staged).

---

## Run 12 — P3.6a implementation attempt (STOPPED before coding; documentation only)

- **Date:** 2026-11-02. **Outcome:** no code or test written. The run was told to stop before coding if a necessary semantic is not clearly established by the contract. It is not.
- **Decisions received and recorded in `TASKS.md` P3.6 (O-1, O-2; approved by the user this run):** guard `estimate = n ** k` with `n` = `CURATED` qualifications not already held and `k = max_steps`, computed before any eligibility evaluation, `LimitExceededError` only if `estimate > max_expansions` (equality allowed), a conservative budget and not an exact count; argument validation (`TypeError` for non-`int` or `bool`, `ValueError` for values below 1, `LimitExceededError` for `max_steps > max_steps_limit`, the same type/range rule for the two limits, all before enumeration or evaluation). Also recorded: the keyword-only hypothetical-code argument to `evaluate` is approved only if existing types support it (checked: `EvidenceClass` does; `HeldQualification` needs the approved A-2 `origin` field), and rejection of non-default scenarios with a narrow internal exception is approved, with the E09 departure left unresolved. The dependency rule (only `graph/paths.py` imports `eligibility/`; `graph/` never imports `settings`) was already documented (A-4).
- **What blocks coding (verified by re-reading API_SPEC E09, §1.6, §4, ARCHITECTURE §13.1 and TASKS P3.6; no path code or tests exist):** the contract does not establish (P-1) whether every valid prefix is returned and in which output order; (P-2) the result for an already-held target; (P-3) the exception for an existing non-`CURATED` target (only the HTTP code `TARGET_NOT_EVALUABLE` exists; an unknown code already raises `UnknownEntityError`); (P-4) a `CURATED` qualification whose `eligibility` is `None`; (P-5) the element order of `from_state`. "Stop at the target" is output-neutral (no repeats), so it is not a decision. Each has a recommendation in `TASKS.md` P3.6; none is approved.
- **Files changed:** `TASKS.md` (P3.6 status line; O-1, O-2, O-7, O-8 wording; new block "Decisions needed before any P3.6a code") and this entry. No source, test, config, curation or `data/` file changed; no test run; nothing staged or committed.
- **Verification:** see the run report (HEAD, tree hashes of `src/`, `tests/`, `config/`, `data/`, `config/overlay_approvals.yaml` with `approved: []`).
- **Next action:** answer P-1 to P-5 (accept the recommendations in one line, or name the changes), then rerun the implementation.

---

## Run 13 — P3.6a: Path enumeration core (implemented; P3.6 NOT complete)

- **Date:** 2026-11-02. **Scope:** `TASKS.md` P3.6a only, on your explicit decisions: the O-1 guard and O-2 validation rules, P-1 to P-5 (explicit implementation decisions; the contract does not specify them), module placement of the new types, the keyword `hypothetical_codes`, `resolvable_by = PROFILE`. No P3.6b, P3.7+ or Module A work. No curation, config, data or overlay change.
- **Blocker check before coding:** none found. `EvidenceClass.DECLARED` / `HYPOTHETICAL` exist (`model/evidence.py`, API_SPEC §2.1); `HeldQualification` had no `origin` (added, as the approved A-2); `InputUsed.evidence_class` was narrower than API_SPEC §2.4 (widened); `ProfileState` is untouched; `GraphError` exists in `graph/edges.py`; `Registry`, `Coverage`, `UnknownEntityError`, `EligibilityError` exist. One existing test (`test_evaluate_imports_only_model_registry_and_eligibility_modules`) whitelists only `json`, `enum`, `typing`, `__future__`; the first draft imported `collections.abc` and failed it, so `evaluate.py` uses `typing.Collection` instead (no existing test was edited).
- **Files changed.**
  - New: `src/skillgraph/graph/paths.py`; tests `tests/unit/test_graph_paths.py`, `tests/unit/test_eligibility_hypothetical.py`, `tests/golden/test_graph_paths_pilot.py`.
  - Modified (additive, backward compatible): `src/skillgraph/eligibility/components.py` (`HeldQualification.origin`, `is_hypothetical`; `InputUsed.evidence_class` also `HYPOTHETICAL`; `_held_used` labels hypothetical holdings; `_prior_level` never counts a hypothetical holding as declared relevant and returns `UNKNOWN(RELEVANCE_NOT_DECLARED)` instead of `NOT_MET` for one); `src/skillgraph/eligibility/evaluate.py` (keyword-only `hypothetical_codes`, validated: strings only, registry codes, disjoint from declared holdings, not the target; `holdings_complete` still computed from the profile's own two lists); `src/skillgraph/graph/__init__.py` (exports).
  - Records: `TASKS.md` (P3.6 status, P3.6a result block, open-item statuses, Phase 3 status line), `API_SPEC.md` §4 (the two "not yet specified" notes now state the decisions), `README.md` (Phase 3 row), `docs/decisions/P3_2_AUDIT.md` (one bullet), this entry.
- **Tests run (exact commands, `.venv\Scripts\python.exe`).**
  1. `-m pytest tests/unit/test_eligibility_components.py tests/unit/test_eligibility_evaluate.py tests/golden/test_eligibility_pilot.py -q` after the eligibility change: first run **1 failed, 498 passed** (the import whitelist above), then **499 passed**.
  2. New files while writing them: `test_eligibility_hypothetical.py` **26 passed, 1 failed** (my test used `rel=None`, which takes the pre-existing branch; test corrected, not the code), then green; `test_graph_paths.py` one failed case from my own parametrisation (budget minus one of 0 is rightly rejected: replaced the case), one failed because the inference-edge builder needs evidence and occupation records in my fixture (fixture fixed), then **110 passed** for the two unit files; `tests/golden/test_graph_paths_pilot.py` **27 passed**.
  3. Focused: `-m pytest tests/unit/test_graph_paths.py tests/unit/test_eligibility_hypothetical.py tests/golden/test_graph_paths_pilot.py -q` → **137 passed**.
  4. Mutation harness (28 mutations over `paths.py`, `components.py`, `evaluate.py`; each followed by the five focused/eligibility files with `-x`; each file restored and checked byte-identical, no backups left): **27 killed**. Killed include: guard `>=`, `n*k`, held counted in `n`, `NOT_MET` kept, one level too deep, descending order, repeats, hypothetical codes not passed, `from_state` without declared holdings, last-step verdict, only complete paths, bool accepted, 0 accepted, limit `>=`, scenario ignored, target coverage unchecked, held target not empty, rules-less record skipped, target filter always true, guard skipped with a target, the A-3 branch removed, hypothetical counted as relevant, hypothetical labelled OFFICIAL, external hypothetical allowed, holdings complete with hypotheticals, declared overlap allowed, target as hypothetical. **Survivor (equivalent mutant):** removing "stop extending at the target" changes no output (no qualification repeats), as decided under P-1.
  5. Related files (12: graph edges / inference / registry / eligibility unit, golden and integration): `2249 passed`.
  6. Full suite `-m pytest -q`: **3185 passed, 1 warning** in 51 s (previous 3048 + 137 new; the warning is the existing Pydantic serializer warning).
  7. `tools/check_legacy_baseline.py`: "MATCH with baseline legacy_tests_2026-10-31: 23 passed, 1 failed, 0 errors, 0 skipped (DQ-01 unresolved). This is a documented baseline, NOT a passing suite." The legacy suite remains **23 passed, 1 failed (DQ-01, unresolved; checked against an exact baseline)**.
  - Not run: `build` / `validate` (they write to `data/curated/`); no linter or type checker is configured.
- **Criteria (TASKS P3.6, as met by P3.6a).** PASS: deterministic output; only `CURATED` targets; no repeats, `max_steps` respected, guard raises `LimitExceededError` before any evaluation (equality allowed, budget plus one refused); `NOT_MET` never extended nor returned; path verdict = `and_`. PASS for the default scenario only: experience does not accrue. **NOT MET (deferred to P3.6b):** a non-default scenario sets `is_hypothetical` and `HYPOTHETICAL_SCENARIO` (such a scenario is rejected). **NOT MET / NOT PROVEN:** the inference invariant: there is no `path_id` and no `include_inference` input on paths; shown only that building static and inference edges leaves the serialised paths and every registry record unchanged (synthetic and real build) and that `paths.py` imports nothing from the edge or inference modules.
- **PROVISIONAL / unresolved.** Q-B `COMPARE` (the E07-profile path result, SSMO `CONDITIONAL`, depends on it); the hypothetical-relevance rule (consequence: a later step that needs an earlier one for its level is `UNKNOWN` unless a declared holding already qualifies); the E09 departure for non-default scenarios (O-8); `path_id` and the other fields with no assigned stage (O-5); the declaration route for relevance (O-4); P-1 to P-5 are implementation decisions, not contract text. Q-A, Q-C, Q-D to Q-H unchanged.
- **Protected items.** HEAD `b0fcff46…` unchanged; nothing staged, nothing committed. `data/` and `config/` tree hashes equal to the pre-run values; `config/overlay_approvals.yaml` `287e3f67…` with `approved: []`; `config/labour_market.yaml` `3ff5d350…`. `git status`: the pre-run entries are unchanged and exactly four untracked files were added (`paths.py` and the three test files). Earlier session-log entries are an exact prefix of this file.
- **Recommended next:** your acceptance (or changes) of the P-1 to P-5 behaviours as written in the code, and the O-4/O-5 questions (`path_id` derivation; how relevance of a path-target qualification is declared), before P3.6b.
