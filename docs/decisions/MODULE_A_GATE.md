# Module A feasibility gate: decision record (P2.5)

**Decision: `NO_GO`** (Module A deferred) · **Decided:** 2026-11-01 (Asia/Kolkata), run 2 · **Status of this record:** produced; **awaiting user acceptance** (`TASKS.md` P2.5 definition of done: "you have read and accepted the record"). Not marked DONE.
**Branch / HEAD when written:** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0` (working tree uncommitted).
**Rules applied:** `ARCHITECTURE.md` §21.1 (gate criteria) and §21.2 (outcomes), applied as written. No alternative rule was invented.

**Addendum (Task 1A, 2026-11-01):** PLFS files were later found outside the repository. They were assessed read-only in `docs/feasibility/existing_plfs_files_assessment.md`. **The decision and the statuses below were not changed**: existence of files does not establish official acquisition (FG-1) or reuse terms (FG-2), and the README with those files carries a purpose-limitation sentence. The assessment lists which gates could be reassessed next.

**Consequence.** Module A stays disabled. Module B (the qualification adjacency and pathway engine) is the **graph-only baseline** and is unaffected (`ARCHITECTURE.md` §21.3). **No labour-market statistic may appear anywhere in the repository, API, UI, demo or pitch.** `config/overlay_approvals.yaml` (`approved: []`) was not touched.

---

## 1. Results for FG-1 … FG-8

Statuses use only `PASS`, `FAIL` or `UNKNOWN`. A `FAIL` below means "the criterion's stated evidence is not met", and is explained per row; it is not a claim that access or reuse is impossible.

| Gate | Criterion (§21.1) | Status | Evidence | Reasoning | What could change it |
|---|---|---|---|---|---|
| **FG-1** | Data files actually obtained through an official channel; saved terms and access record; file hashes in a new manifest | **FAIL** | `data/raw/2026-10-30/MANIFEST.csv` has 22 rows, from AMHSSC, DGE, NQR and SSCAMH; none is PLFS or a MoSPI/NSO file. `data/labour/` does not exist; no PLFS file was found by filename search (module_a_sources.md §B.3, re-checked 2026-11-01). Registration was not attempted: `module_a_sources.md` §E, Q-6 open. | The criterion is "actually obtained". Nothing was obtained, so its evidence requirement is not met. The route itself was observed (login, free account, dataset 292 "Get Microdata" page: `module_a_sources.md` row 11) but not used. | A user-approved registration and download to a new run folder `data/labour/raw/<date>/` with a manifest and hashes (`TASKS.md` Phase 2 header). |
| **FG-2** | Lawful reuse: the terms permit this analysis and displaying aggregates in the competition; quoted terms clause; licence status | **FAIL** | `module_a_sources.md` §H. Microdata (S1): `UNCLEAR`. MoSPI/NSO published reports (S2): `UNCLEAR`. Karnataka DES (S3): `RESTRICTED` ("only with prior permission"). DGE/NCO (S4): `RESTRICTED` ("may not be reproduced partially or fully, without due permission"). PIB, eSankhyiki, Planning Dept., GODL: `UNCLEAR`. No source `PERMITTED`. | `TASKS.md` P2.2: "`UNCLEAR` means FG-2 is `FAIL` until clarified." The primary route (microdata) is `UNCLEAR`; the policy documents on dissemination conditions (GSDD, 1999 policy, download manual) could not be read. This is a rule-driven `FAIL`, **not** a finding that reuse is prohibited. | Quoted conditions from the unread MoSPI policy documents or the download manual; written clarification from MoSPI; written permission from Karnataka DES / DGE where their content would be displayed. |
| **FG-3** | Variables: state, occupation (with NCO version and digits), industry, activity status, earnings, weights, design variables; codebook extract | **UNKNOWN** | `module_a_variables.md` §B, §C, §F. Labels for all the required fields were read on the public data-dictionary pages of datasets 284 and 213 (e.g. `st`, `ocu_pas`, `ind_pas`, `pas`/`sas`/`acws`, `ern_reg`, `mult`, `mfsu`, `strm`, `panel`). | Present at label level, but the criterion asks for the NCO version **and digits**; digits are not established, the NIC version for 2023-24 and all code lists, definitions and reference periods are unverified, and design variables differ across rounds. The layout, README and questionnaires were not opened. | Reading the README, layout and questionnaires for the chosen round(s): needs downloads (approval). |
| **FG-4** | Karnataka identification: state code present and documented; codebook | **UNKNOWN** | `module_a_variables.md` §B row 1. State variables exist (`st`, `state_perv1`). | The Karnataka value is documented only in a State/UT code spreadsheet (listed under dataset 284's materials) that was not opened. No code is assumed from general knowledge. | The State/UT code list for the chosen round. |
| **FG-5** | Sample adequacy: enough Karnataka cells meet the §14.3 thresholds at the intended NCO level; table of unweighted counts | **UNKNOWN** | None. **P2.4 was not executed** (no microdata files). | No count exists. Counts were not invented, and no thresholds were set (`config/labour_market.yaml` records none). | P2.4 on obtained files, with thresholds justified in config. |
| **FG-6** | Comparability: at least two rounds share definitions and classification, or a documented concordance exists | **UNKNOWN** | `module_a_variables.md` §D. The 284 page says the sampling methodology "has been revamped from January 2025"; 2023-24 and CY2025 differ in variable and weight naming; the NCO/NIC versions are stated for CY2025 only. The PIB / "Changes in 2025" material is `SEARCH_LEAD_ONLY` (`module_a_sources.md` §D.8). | Nothing read shows two rounds that are comparable, and nothing read shows none is. The relevant notes and estimation procedure were not opened. | The official 2025-changes note, README and estimation procedure for the rounds in question. |
| **FG-7** | Understanding: weights and estimation understood; one published Karnataka figure reproduced within tolerance; script output | **UNKNOWN** | None. **P2.4 not executed.** The estimation procedure was not read. No tolerance is defined anywhere in the repository. | A reproduction was neither attempted nor failed. Marking it `FAIL` would assert a result that was never obtained. If P2.4 were run and the reproduction missed tolerance, it would become `FAIL` (`TASKS.md` P2.4). | P2.4 with obtained files and a tolerance stated in config. |
| **FG-8** | Join: the pilot NCO-2015 codes map to the available occupation level; mapping table, `INFERENCE` where aggregated | **UNKNOWN** | `module_a_variables.md` §E. The four pilot codes (3122.3551, 7543.0301, 8153.0101, 8153.0103) and their division, sub-division, group and family are tabulated. The CY2025 dataset page cites NCO-2015; the PLFS occupation field's digit depth is not established; no NCO volume or concordance was obtained (historical D1 returned 404; indexed PDF paths are `SEARCH_LEAD_ONLY`). | The join level cannot be fixed without the field's depth, and for any round not coded in NCO-2015 a concordance would be needed (`TASKS.md` P2.3). Code `3122.3551` also has no verified title in the Module B build (unrelated Phase 1 evidence item, unchanged). | Depth and NCO version per round from the layout/README; the NCO-2015 volumes or concordance. |

**Tally:** `PASS` 0 · `FAIL` 2 (FG-1, FG-2) · `UNKNOWN` 6 (FG-3, FG-4, FG-5, FG-6, FG-7, FG-8).

---

## 2. Mechanical application of §21.2

| Outcome | Condition (as written) | Satisfied? | Why |
|---|---|---|---|
| `GO` | FG-1…FG-8 `PASS` | **No** | No gate is `PASS`. |
| `GO_REDUCED` | FG-1–4, 7 `PASS`; FG-5/6/8 partially | **No** | FG-1 and FG-2 are `FAIL`; FG-3, FG-4 and FG-7 are `UNKNOWN`. The condition requires FG-1–4 and 7 to be `PASS`. No meaning was invented for a "partially passing" gate. |
| **`NO_GO`** | **FG-1, FG-2 or FG-7 `FAIL`**, or the time-box expires | **Yes** | **FG-1 is `FAIL` and FG-2 is `FAIL`.** Either alone satisfies the condition. (FG-7 is `UNKNOWN` and is **not** relied on. The time-box was **not** relied on: the effort spent against it has not been measured.) |
| `NOT_ASSESSED` | Gate not run yet | **No** | The gate has been run on the available evidence (P2.1–P2.3 and this record), and the evaluation produced the `FAIL` results above. `NOT_ASSESSED` is defined only as "not run yet". |

**Decision: `NO_GO`.**

**Point for the reviewer.** The `NO_GO` follows from an evidence shortfall, not from a refusal by any data provider: nothing was requested from or refused by MoSPI, DES or DGE, and no registration was attempted (Q-6 is open). The rules in §21.2 contain no "evidence pending" outcome, so `NO_GO` is the outcome the rules give. The record is not final: it states below what would reopen it.

---

## 3. Product behaviour under `NO_GO` (§21.2, §21.3)

- Module A is **deferred**. `GET /labour-market/status` (E13, P5.6) will return the reasons and the pointer to this record; the UI panel will say "deferred — see the decision record". Those endpoints are not built yet (Phase 5).
- Conditional endpoints return `404 MODULE_UNAVAILABLE` (`API_SPEC.md` error table, `MODULE_UNAVAILABLE`).
- **No labour-market statistic anywhere.** Re-checked on 2026-11-01: the repository holds no `frontend/`, no `data/labour/` and no `data/outputs/`; the only occurrences of "WPR" / "LFPR" / "unemployment rate" are in `ARCHITECTURE.md`, `TASKS.md` and `docs/feasibility/module_a_sources.md`, as definitions or targets and without any figure. Nothing is deleted or altered. The P2.5 criterion that "a test greps the analysis outputs and the frontend strings for indicator numbers" cannot be implemented yet because neither exists; it is carried to Phases 4–5 (`TASKS.md` P4 / P5).
- Module B is unchanged; eligibility, pathway existence and ranking never use Module A.
- **P2.4 not executed; P2.6 deferred.** P2.6 depends on `GO` or `GO_REDUCED`.

---

## 4. What would change the decision

In order of dependency:

1. **User decisions Q-6 and Q-8** (register for PLFS microdata, which rounds, deadline/format).
2. **FG-1:** user-approved registration and download of the chosen round(s) into `data/labour/raw/<date>/`, with a manifest and hashes.
3. **FG-2:** the conditions text of the microdata policy documents and download manual; written clarification from MoSPI on competition display of aggregates; written permission from DES / DGE if their content is shown.
4. **FG-3, FG-4, FG-6, FG-8:** README, layout, State/UT code list, questionnaires, estimation procedure and the 2025-changes note for the chosen round(s); NCO depth and version; a concordance only if a round is not NCO-2015.
5. **FG-5, FG-7:** P2.4 on the obtained files: unweighted Karnataka counts by NCO level; one published Karnataka figure reproduced within a tolerance stated and justified in `config/labour_market.yaml`.

Then the gate is re-evaluated by the same rules. **A `GO_REDUCED` could only be reached if FG-1–4 and FG-7 become `PASS`.**

---

## 5. Sources of this record

`docs/feasibility/module_a_sources.md` (P2.1 inventory, §H terms review) · `docs/feasibility/module_a_variables.md` (P2.3) · `ARCHITECTURE.md` §14, §21 · `TASKS.md` Phase 2 · `API_SPEC.md` E13 · `data/raw/2026-10-30/MANIFEST.csv` · `config/labour_market.yaml`. Public pages read on 2026-11-01 are cited in those documents with URLs.
