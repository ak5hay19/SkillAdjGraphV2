# P3.2 contract audit and P3.1 policy review

- **Date:** 2026-11-01 (run 5 of `session_log.md`)
- **Scope:** P3.2 (`src/skillgraph/eligibility/logic.py`, `components.py`) against ARCHITECTURE §11 and API_SPEC §2.4; assumptions A-1 to A-6 in `TASKS.md` (P3.2); the three P3.1 registry policies (`src/skillgraph/registry/store.py`).
- **Status:** audit record. It decides nothing that the contract does not decide. Two questions need your decision (Q-A and Q-B below). P3.3 was not started.
- **Evidence read:** `API_SPEC.md` §2.1 (enums), §2.3 (profile), §2.4 (result, component conventions), E02, E07 example; `ARCHITECTURE.md` §6.2 (dependency rules), §11.1–§11.3, §13.1, §17, DQ-09; `data/processed/audit_2026-10-30_m1s1/AUDIT_NOTE.md` and `corrections_overlay.csv` (D4, D5, OV-005); `config/curation_defaults.yaml`; the real build `cb-601c0399c999` (read only, through the registry).

## Verdicts

| # | Issue | Verdict | Change made |
|---|---|---|---|
| 1 | A-1 multiple conditions versus singular `ComponentResult.condition` | **PASS** (with a guard added and a P3.3 obligation) | invariant added to `ComponentOutcome` |
| 2 | A-2 `REVIEW_FLAG` for the below-grade case | **NEEDS DECISION** (Q-A); verdict itself is correct | none |
| 3 | A-3 `requires_relevance` and experience | **PASS** | none |
| 4 | A-4 `resolvable_by` and wording; A-6 tie-breaks | **PASS** (verdict-neutral); one residual wording point noted | none |
| 5 | A-5 `ComponentInputs` / `HeldQualification` | **FAIL, corrected**, plus one **NEEDS DECISION** (Q-B) | `holdings_complete` and `level_cap` added |
| 6a | Refuse stale `curation_code_version` | **PASS** | none |
| 6b | Missing `validation_report.json` served as `NOT_RUN` | **NEEDS DECISION** (Q-C) | none |
| 6c | Registry imports from `curation.build` | **PASS** (direct-import reading; transitive note) | none |

## 1. A-1 — conditions: PASS

- **Contract.** `ComponentResult.condition` is singular (`API_SPEC.md` §2.4, `ComponentResult`). `EligibilityResult.conditions` is `Condition[]`, "union over decisive rows, de-duplicated, sorted by key" (§2.4, `EligibilityResult`). ARCHITECTURE §11.3 item 3: conditions are "collected from the winning route(s)".
- **The contract's own example already splits them.** E07 shows the prior-level component with `condition` = the DECLARATION and the `nsqf_level_match` interpretation only in that component's `inputs_used` (`config.nsqf_level_match`, `CONFIG`); the CONFIG condition then appears in the target-level `conditions`. So the supported projection is: component `condition` = the declaration; the interpretation is not discarded, because it is in `inputs_used` and in the target-level union.
- **Finding.** `ComponentOutcome.conditions` (plural, declaration first) is internal and compatible with that projection. The one way to lose a material condition would be for P3.3 to build the target-level list from `.condition` instead of `.conditions`.
- **Correction (narrow).** `ComponentOutcome` now rejects an outcome with more than one DECLARATION condition and any non-declaration condition that is not also present in `inputs_used`, so the singular projection can never drop a condition. Tested (`test_the_config_condition_is_always_visible_…`, `test_an_outcome_with_two_declaration_conditions_…`).
- **P3.3 obligation.** The target-level `conditions` list is built from `ComponentOutcome.conditions` of every component of every decisive row (not from `.condition`), de-duplicated and sorted by `key`.
- **Presentation only (not a contract point).** The E07 example text names the held qualification by title; P3.2's text uses the code. The spec fixes the structure, not the wording of conditions.

## 2. A-2 — `REVIEW_FLAG` for "Grade 9": NEEDS DECISION (Q-A)

- **Allowed?** Yes. `REVIEW_FLAG` is a member of `UnknownReasonCode` (`API_SPEC.md` §2.1; `model/eligibility.py`). No code was invented.
- **Verdict preserved?** Yes. ARCHITECTURE §11.2 (`SCHOOL_GRADE_MIN`, exception 1) and API_SPEC §2.4 (`below_required_verdict`) require `UNKNOWN`, not `NOT_MET`, below the threshold; at or above it the result is `MET`. The evaluator does exactly this (tests: `test_below_required_verdict_unknown_replaces_not_met_only_below_the_threshold`).
- **Why not simply PASS.** The spec gives that case no reason code. API_SPEC §2.1 defines `REVIEW_FLAG` as "the audit flagged the verbatim text for review (decision D4)". The "Grade 9" row is decision **D5** (OV-005: "Grade 9" printed without "pass"; `SAFE_WITH_CONSTRAINT`), not D4. The other candidates are excluded by their definitions: `UNCERTAIN_EXTRACTION` is "never used for a `TRANSCRIBED` cell" and `ENGINE_USE_UNDECIDED` is for `engine_use = UNKNOWN`; the row's `engine_use` is `SAFE_WITH_CONSTRAINT`. `REVIEW_FLAG` is the least wrong member of the existing enum, but it is used outside its written definition.
- **Question Q-A.** For `below_required_verdict = "UNKNOWN"` (SMO row 1, D5), which existing `UnknownReasonCode` does the API return? Options: (a) keep `REVIEW_FLAG` and widen its API_SPEC definition to "D4 or D5"; (b) add a new code (an API_SPEC and model change, deliberately not made here). No consumer branches on this code today; the choice affects display and `resolvable_by` only, not any verdict. Until decided, the code stays `REVIEW_FLAG`.

## 3. A-3 — `requires_relevance` and experience: PASS

- **§11.2 rules compared** (`ARCHITECTURE.md` §11.2 table): `PRIOR_NSQF_LEVEL` is always relevance-checked (step 5); `EXPERIENCE_MIN_YEARS`: "Y = 0 → MET; declared ≥ Y → CONDITIONAL (relevance is declared, not verified; D2); declared < Y → NOT_MET; undeclared → UNKNOWN". The table does not branch on the stored `requires_relevance` flag.
- **Curated shapes** (all 52 stored components of `cb-601c0399c999`, counted): `requires_relevance = true` occurs on all 7 `PRIOR_NSQF_LEVEL` components and on exactly the `EXPERIENCE_MIN_YEARS` components with `years > 0`; it is `false` on every `years = 0` experience component, on all `AGE_MIN`, `SCHOOL_GRADE_MIN`, `NAMED_CREDENTIAL` and `UNMODELLED` components. The evaluator's behaviour (always relevance-checked prior level; `CONDITIONAL` for `years > 0`; `MET` for `years = 0`) therefore coincides with the flag on all real data.
- **Cases where the evaluator ignores a required flag or invents a basis:** none. Every `CONDITIONAL` carries a DECLARATION condition naming the declaration it rests on. An unflagged `years > 0` experience component or an unflagged prior level does not occur in the build; if one did, the evaluator would still apply the §11.2 rule (more conservative than trusting the flag).

## 4. A-4 and A-6 — wording, `resolvable_by`, tie-breaks: PASS

- **Contract-fixed points.** `ENGINE_USE_UNDECIDED` → `SOURCE_REVIEW` (ARCHITECTURE §11.3 item 6); `DIPLOMA_YEAR_NOT_MODELLED` text and `SOURCE_REVIEW` (API_SPEC E07 example); "declare X → PROFILE, set config Y → CONFIG, or not resolvable from current sources" (ARCHITECTURE §11.3 item 4). P3.2's assignments agree with all of them.
- **Chosen by P3.2.** `INPUT_NOT_DECLARED`/`RELEVANCE_NOT_DECLARED` → `PROFILE`, `CONFIG_UNSET` → `CONFIG` (direct instances of §11.3 item 4); `EQUIVALENCE_UNDEFINED`/`CREDENTIAL_ORDER_UNDEFINED` → `NOT_RESOLVABLE_FROM_CURRENT_SOURCES` (§11.3 item 5: no equivalence or order rule exists); the other stored causes → `SOURCE_REVIEW` (following the two fixed examples). `resolvable_by` and text never feed a verdict, so these are metadata choices. One residual: the `*_NOT_MODELLED` codes could arguably be `NOT_RESOLVABLE_FROM_CURRENT_SOURCES`; the only specified instance (`DIPLOMA_YEAR_NOT_MODELLED`) says `SOURCE_REVIEW`, so that was followed. Recheck at P5.1 (E07) if a UI needs them distinguished.
- **Tie-breaks (A-6), each checked for an effect on the verdict:**
  - `or_equivalent` before other-credentials, and `or_equivalent` before `below_required_verdict`: both outcomes are `UNKNOWN`; only the code differs. Curation never sets `or_equivalent` and `below_required_verdict` together.
  - `OTHER` counts as a held post-school credential, so a declared `OTHER` without the required credential is `UNKNOWN(CREDENTIAL_ORDER_UNDEFINED)`, not `NOT_MET`. This is the only tie-break that could affect a verdict. It is the fail-closed reading (an unspecified credential cannot be shown to fail the requirement) and §11.2 says "if other credentials are held → UNKNOWN". `OTHER` is a member of `PostSchoolCredentialType` (API_SPEC §2.1).
  - Satisfying holdings not in the declared-relevant list are "declared not relevant" (`NOT_MET`): §11.2 step 5, with the list the only form of declaration (API_SPEC §2.3).
- No test was changed to make behaviour pass; no policy was changed in this item.

## 5. A-5 — input contract: FAIL (corrected) and one open question

**Method.** Every state that P3.3 must resolve from `HypotheticalProfile` (API_SPEC §2.3) and the registry was listed and mapped to `ComponentInputs`:

| Source state | Representation | Result |
|---|---|---|
| `age_years` null / integer | `age_years` None / int | OK |
| `school_grade_passed` null / 0–12 | same | OK |
| `post_school_credentials` null / `[]` / list | None / `()` / tuple of types | OK |
| `held_qualification_codes` and `external_qualifications`: **two independent nullable lists** | one `held_qualifications` tuple | **gap — see below** |
| per-target `relevant_experience_years` null / ≥ 0 | same | OK |
| per-target `relevant_prior_qualifications` null / list | None / tuple, must refer to declared holdings | OK |
| registry holding's level, OFFICIAL, with provenance (`value_status`, `conflict_id`, `engine_use`) | level only | **gap — see below** |
| external holding's level, DECLARED | `HeldQualification` with `ext-…` ref | OK |
| HYPOTHETICAL holdings added by path enumeration (ARCHITECTURE §13.1) | not representable | not needed by P3.3; **P3.6/P3.7 must extend** (an `origin` on `HeldQualification`; `ConditionKind.HYPOTHETICAL` is already defined) |

**Gap 1 (fixed): partial holdings.** The profile has two independently nullable lists. The input contract could express only "neither declared" (`None`) or a single combined tuple. A profile that declares `external_qualifications: []` and leaves `held_qualification_codes: null` would have to be resolved by P3.3 to `()` and the evaluator would return `NOT_MET` ("declared none"), although the person may hold registry qualifications that were never listed. ARCHITECTURE §11.1 requires `NOT_MET` to be a definitively failed rule, and API_SPEC §2.3 says "null = not declared; [] = none". **Correction:** `ComponentInputs.holdings_complete` (default `False`, fail closed; true only when both lists were declared). With incomplete holdings, "no listed holding satisfies the level" is `UNKNOWN(INPUT_NOT_DECLARED)` (`resolvable_by` `PROFILE`); a listed holding that does satisfy the level still counts. `holdings_complete = True` with undeclared holdings is rejected. The seven existing tests that assumed complete holdings now declare it explicitly (the helper `prior()` sets it); none was weakened, and new tests cover the incomplete case, precedence with `CONFIG_UNSET`, and the unchanged definite failure when both lists are declared.

**Gap 2 (representable now; policy open, Q-B): the provenance of a registry level.** `HeldQualification.nsqf_level` carried a bare number. In the real build the qualification-level `nsqf_level` is OFFICIAL/`TRANSCRIBED` but its `engine_use` is `UNKNOWN` for the 4 `CURATED` qualifications and `DISPLAY_ONLY` for the 33 `CATALOGUE_ONLY` ones (`config/curation_defaults.yaml`: "no document states its engine_use outside an eligibility row"; TASKS P1.4 note). ARCHITECTURE §11.3 items 1, 2 and 6 require a component that depends on an uncertain, conflicted, pending or `engine_use`-undecided value to be `UNKNOWN`. The E07 example, by contrast, uses `qual:AMH/Q0301.nsqf_level = 2.5` (OFFICIAL) as a comparison input and shows API_SPEC's qualification example with `engine_use: SAFE_HARD_RULE`, which the real build does not carry. The contract therefore does not say whether a held registry qualification's own level may be compared. **Correction (representability only):** `HeldQualification.level_cap` (default `None` = comparable) takes one of `UNCERTAIN_EXTRACTION`, `SOURCE_CONFLICT`, `OVERLAY_NOT_APPROVED`, `ENGINE_USE_UNDECIDED`; a capped level is never compared and yields that `UNKNOWN` (a usable satisfying holding still wins; a capped holding beside non-satisfying ones gives `UNKNOWN`, never `NOT_MET`). An external (declared) level cannot be capped. Which provenance states cap a level is **not decided here**.
- **Question Q-B.** For P3.3, should the held registry qualification's `nsqf_level` be treated as comparable when its `engine_use` is `UNKNOWN`/`DISPLAY_ONLY` (matches the E07 example; the required level on the *target row* is separately authorised by that row's `engine_use`), or capped with `ENGINE_USE_UNDECIDED` until an audit decision covers qualification-level NSQF values (stricter; the E07 example, Q0301 held at level 2.5, would then be `UNKNOWN` on the real build)? Default until decided: P3.3 sets no cap, which reproduces the E07 example, and records the choice. Also decide whether a level whose own `value_status` is `PARSED_UNCERTAIN` or whose `conflict_id` is open is capped (recommended: yes; no such level exists in the build today).

## 6. P3.1 policies

**6a. Stale `curation_code_version` refused — PASS.** ARCHITECTURE §7 principle 4 makes the curation-code version part of the deterministic build id, and `skillgraph validate` also selects builds by the current code version; "a valid curated build" (ARCHITECTURE §17 and §6.2 error handling, API_SPEC `DATA_NOT_BUILT`) is not valid for outdated code. A stale build surfaces as `BuildStatus` `INVALID` (`BuildInvalidError`), a value in the API enum. The three older installed builds are therefore refused until rebuilt.

**6b. Missing validation report allowed as `NOT_RUN` — NEEDS DECISION (Q-C).**
- **Can an unvalidated build be served?** Yes: `registry.load` returns a registry with `BuildInfo.validation == "NOT_RUN"` when `validation_report.json` is absent. It refuses a report that belongs to another build, that is unreadable, or that records any failed check. The real build has a report (`checks_passed 18`, `checks_failed 0`), so it loads as `PASSED`.
- **What the contract says.** ARCHITECTURE shows validation as pipeline stage 5 ("schema + referential + known-findings checks") and lists `validation_report.json` among the build's files (§7, data section), but never states that serving requires it. §17 and API_SPEC refer only to "no valid curated build" (`503 DATA_NOT_BUILT`) and `BuildStatus` has `READY | NOT_BUILT | INVALID`. E02's `validation` object is `{checks_passed, checks_failed, known_findings}` and has no `NOT_RUN` state. The contract neither requires nor forbids serving a build without a report.
- **Risk if left as is.** A build that was produced and never validated would answer E07/E09 with `READY` and no visible warning. For P3.3 specifically, golden tests on the real build use a validated build, so P3.3 is not exposed.
- **Question Q-C.** Is a build without a passing `validation_report.json` a "valid curated build" (E02 `READY`)? Options: (a) require `PASSED` to serve (the loader, or the P5.1 status layer, reports `INVALID` or a distinct state for `NOT_RUN`); (b) allow `NOT_RUN` but E02 must expose it. **Recommendation:** (a) at the serving layer in P5.1, keeping `load` able to open a `NOT_RUN` build for tests and tools; and, from P3.3 on, golden tests must assert `BuildInfo.validation == "PASSED"`. No registry change is made now (the instruction was not to redesign it).

**6c. Registry imports `MANIFEST_OUT`, `OUTPUT_FILES`, `check_references`, `CURATION_CODE_VERSION`, `BuildError` from `curation` — PASS, direct-import reading.**
- ARCHITECTURE §6.2 dependency rules: "`eligibility/` and `graph/` import only `model/` and `registry/`", "`curation/` is the only code that reads `data/processed/`". Neither restricts what `registry/` imports. Importing `curation.build` does not read `data/processed/` (import-time constants and functions only), and re-using the builder's own `check_references` and file list avoids two copies that could drift (the registry asserts the equality at import time).
- **Note.** The import-boundary test (P3.10) is "AST-based" (§ test table), i.e. direct imports. If it were ever written as a transitive-closure check, `eligibility` → `registry` → `curation` → `provenance`/`settings` would fail it. Resolving that would be a small corrective task (move the two constants and `check_references` to a neutral module), not needed now. P3.2's own modules import only `skillgraph.model` (tested).

## Open decisions (for you)

| ID | Question | Blocks P3.3? | Default meanwhile |
|---|---|---|---|
| Q-A | Which existing `UnknownReasonCode` for D5 "Grade 9" below-threshold; widen `REVIEW_FLAG`'s definition or add a code? | No (display only) | `REVIEW_FLAG` |
| Q-B | May a held registry qualification's `nsqf_level` be compared when its `engine_use` is `UNKNOWN`/`DISPLAY_ONLY`; cap `PARSED_UNCERTAIN`/conflicted levels? | **Affects golden outcomes** (E07 example Q0301 → Q2301) | no cap (reproduces E07 example); P3.3 must state it and test both |
| Q-C | Must serving require a `PASSED` validation report? | No | `load` allows `NOT_RUN`; golden tests assert `PASSED` |

Nothing in this audit changed a dataset, configuration, overlay approval, Module A status, or Phase 1 gate.

## P3.3 follow-up (2026-11-02, run 6)

P3.3 (`src/skillgraph/eligibility/evaluate.py`, `tests/golden/test_eligibility_pilot.py`) acted on this audit's obligations. Nothing above was changed; the three questions stay open.

| Obligation | Done |
|---|---|
| Target-level `conditions` from `ComponentOutcome.conditions`, de-duplicated, sorted by key | yes (D-3); a test shows the CONFIG condition reaches the target list although each `ComponentResult` carries one condition |
| `holdings_complete` true only when both profile lists are declared | yes; tested for all four declared/undeclared combinations, on synthetic and real rules |
| `level_cap` set per the Q-B decision, both cases tested | **implemented as an explicit switch, decision still open** (below) |
| Golden tests assert `BuildInfo.validation == "PASSED"` | yes; every golden test goes through a fixture that asserts it |

**Q-B - status: OPEN; behaviour stated, not decided.** `evaluate(..., undecided_level_use=COMPARE | CAP)`. A held registry qualification's `nsqf_level` is capped (never compared) when it has an open conflict (`SOURCE_CONFLICT`), is `PARSED_UNCERTAIN`/`UNRESOLVED`/null (`UNCERTAIN_EXTRACTION`), or has `engine_use` `DISPLAY_ONLY`, `NOT_USED` or `SAFE_HOURS` (`ENGINE_USE_UNDECIDED`); it is compared when `engine_use` is a computing use. Only `engine_use = UNKNOWN` (or absent) is policy-dependent: `COMPARE` is the default, `CAP` gives `UNKNOWN(ENGINE_USE_UNDECIDED)`. Consequence on the real build: the 33 catalogue-only qualifications (`DISPLAY_ONLY`) can never satisfy a prior-level component (tested with AMH/Q0305, level 2.5, against SSMO row 9 and AMH/Q0104, level 5.0, against Production Supervisor row 4, under both policies); the 4 curated pilots (`UNKNOWN`) satisfy it under `COMPARE` only.

*Exact discrepancy.* For comparing the curated qualification-level NSQF value: ARCHITECTURE §11.2 (the `PRIOR_NSQF_LEVEL` input is "held qualification codes (official levels)"), §11.5 (the audit's A4 notes "become regression tests": a Sewing Machine Operator holding meets the level part of SSMO row 9 and Inline Checker row 4), TASKS P3.3 criteria 1 and 2, and the E07 example (`qual:AMH/Q0301.nsqf_level = 2.5`, OFFICIAL) all treat it as comparable. Against that: ARCHITECTURE §11.4 ("`UNKNOWN`: only the affected component is UNKNOWN"; "`DISPLAY_ONLY`: shown, never computed"), §11.3 item 6, and `config/curation_defaults.yaml` (the qualification-level `nsqf_level` deliberately has no `engine_use`, so it is `UNKNOWN`) say a value with no decided use is not computed. No document states the `engine_use` of the qualification-level value outside an eligibility row. The E07 example also shows `engine_use: SAFE_HARD_RULE` for it in the qualification example, which the real build does not carry. The default `COMPARE` follows the controlling P3.3 criteria; **TASKS P3.3 criteria 1 and 2 and the E07-profile golden test are therefore PROVISIONAL**, and each asserts the `CAP` outcome too. A decision is a one-word change of the default (or a curated `engine_use` for the value).

**Q-A - unchanged.** The D5 "Grade 9" case still returns `REVIEW_FLAG` (golden test `test_smo_row_1_grade_8_is_unknown_not_not_met_by_decision_d5_provisional_q_a` pins the verdict, marks the code provisional). **Q-C - unchanged.** `load` still allows `NOT_RUN`; golden tests assert `PASSED`.

## P3.4 note (2026-11-02, run 7)

**Q-A, Q-B, Q-C - unchanged and not touched.** P3.4 (`graph/edges.py`) builds only documented relationships (NOS-table rows, exact shared NOS codes, claim texts, stated NCO codes). It never reads a qualification-level NSQF value, an `engine_use`, a verdict or an eligibility rule, so none of the three questions bears on it, and no golden result of P3.3 changed. The only value-level field it consults on a NOS-table row is `conflict_id` (to carry the registered conflicts on edges), never the level itself. Decisions D-7 to D-14 are in `TASKS.md` P3.4.

## P3.6a documentation amendment (2026-11-02, run 11)

Documentation only. Nothing above was changed. This section closes the one forward reference in §5 (the row "HYPOTHETICAL holdings added by path enumeration: P3.6/P3.7 must extend, an `origin` on `HeldQualification`") at the level of contract text; no code was written.

- **Holding origin (approved).** `HeldQualification.origin` reuses `EvidenceClass`, restricted to `DECLARED` (the default, so every existing holding and test is unchanged) and `HYPOTHETICAL`. Both members exist in `model/evidence.py` and API_SPEC §2.1. API_SPEC §2.4 already lists `HYPOTHETICAL` for `inputs_used.evidence_class`; the P3.2 `InputUsed` type (`DECLARED | CONFIG | OFFICIAL`) is narrower and has to be widened when the field is implemented. An external qualification cannot be `HYPOTHETICAL`. The HTTP `HypotheticalProfile` cannot carry an origin and is not changed. Text: `API_SPEC.md` §4 (A-2), `TASKS.md` P3.6.
- **Hypothetical relevance (approved as PROVISIONAL, not a permanent policy).** ARCHITECTURE §11.2 step (5) already says "relevance undeclared → UNKNOWN". A hypothetically completed qualification's relevance cannot be declared under API_SPEC §2.3 (a declared list may name only declared holdings), so it is "undeclared" and the component is `UNKNOWN(RELEVANCE_NOT_DECLARED)`, never `NOT_MET`. Steps (1)–(4) of §11.2 are unchanged. Today `_prior_level` gives `NOT_MET` for a satisfying holding that is missing from a declared list, so implementation needs one new branch for origin `HYPOTHETICAL`. Text: `ARCHITECTURE.md` §13.1; open item O-4 in `TASKS.md` P3.6.
- **Q-B - unchanged and still open.** By user decision of 2026-11-02, `undecided_level_use = COMPARE` stays the default, explicitly PROVISIONAL, because §11.4 and `config/curation_defaults.yaml` do not fully agree with the E07/E09 examples. The `CAP` option and its tests are kept. This does not settle the qualification-level policy, and no curation data, config, build or overlay approval changes. The P3.3 criteria 1 and 2 and the E07-profile golden test stay PROVISIONAL.
- **Q-A and Q-C - unchanged.**
- **Not decided here:** how a profile declares the relevance of a path-target qualification (O-4); how hypothetical holdings are passed into `evaluate` (O-7). See `TASKS.md` P3.6 for the full list O-1 to O-8.
- **Implemented (run 13, 2026-11-02).** `HeldQualification.origin`, the widened `InputUsed.evidence_class`, the new branch in `_prior_level` and the keyword-only `evaluate(..., hypothetical_codes=...)` exist now (additive; the 3,048 earlier tests are unchanged and pass). The relevance rule is still PROVISIONAL. Q-A, Q-B and Q-C are untouched and still open.
