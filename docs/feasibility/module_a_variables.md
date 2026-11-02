# Module A metadata and variable feasibility (P2.3)

**Status:** first evidence-backed pass, **subject to review; P2.3 is not marked DONE by this document.**
**Prepared:** 2026-11-01 (Asia/Kolkata), run 2 · **Branch / HEAD:** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`
**Gate state:** `config/labour_market.yaml` records the decision in `docs/decisions/MODULE_A_GATE.md`. Module A remains disabled.
**Companion documents:** `docs/feasibility/module_a_sources.md` (P2.1, P2.2), `docs/decisions/MODULE_A_GATE.md` (P2.5).
**Later evidence (Task 1A, 2026-11-01):** `docs/feasibility/existing_plfs_files_assessment.md` reports local PLFS monthly 2025 files outside the repository. Their layout and schedules bear on rows 1, 3, 4, 5 and section E of this document (e.g. a 3-digit NCO-2015 occupation field in the monthly file; Karnataka listed as code 29 in a local state-code workbook). **This document and its statuses were not revised**; those findings are provenance-unestablished and are for a targeted P2.3 revision.

---

## A. Scope and evidence base

This document checks FG-3, FG-4, FG-6 and FG-8 (`ARCHITECTURE.md` §21.1; `TASKS.md` P2.3) **from documentation and metadata only**. No microdata, codebook file, questionnaire, layout spreadsheet or README was downloaded or opened. No analysis was run. **No labour-market statistic appears in this document.**

**What was actually observed (read through a page-fetch tool on 2026-11-01, public HTML pages of the National Microdata Portal, no login):**

| Ref | Page | URL | What it gave |
|---|---|---|---|
| M-1 | Catalogue of PLFS datasets | https://microdata.gov.in/NADA/index.php/catalog/PLFS | 14 datasets; IDs and periods (listed in section H below) |
| M-2 | Dataset 284 description (PLFS Calendar Year 2025) | https://microdata.gov.in/NADA/index.php/catalog/284 | Text citing "National Industrial Classification – 2008" and "National Classification of Occupation - 2015"; "A rotational panel sampling design has been used"; "The first stage unit (FSU) is the 2011 census village in the rural sector."; the sampling methodology "has been revamped from January 2025" |
| M-3 | Dataset 284 data dictionary | https://microdata.gov.in/NADA/index.php/catalog/284/data-dictionary | Two data files: `chhv12025` (270,472 cases, 48 variables) and `cperv12025` (1,148,634 cases, 153 variables) |
| M-4 | Dataset 284, variable list of file `cperv12025` | https://microdata.gov.in/NADA/index.php/catalog/284/data-dictionary/F2?file_name=cperv12025 | Variable names and labels (section C). **No code lists or definitions on that page.** |
| M-5 | Dataset 284 related materials | https://microdata.gov.in/NADA/index.php/catalog/284/related-materials | Titles only: two questionnaires (Schedules 0.0 and 10.4 first visit), layout XLSX, States/UTs code XLSX, districts XLSX, field-staff instruction volumes, README, text-to-CSV ZIP, "million-plus" identifier files |
| M-6 | Dataset 213 description (PLFS July 2023 – June 2024) | https://microdata.gov.in/NADA/index.php/catalog/213 | Sampling text only; the fetch reported **no** NCO, NIC or classification-version statement on the page |
| M-7 | Dataset 213 data dictionary and variable list of file `perv1` | https://microdata.gov.in/NADA/index.php/catalog/213/data-dictionary and `.../data-dictionary/F4?file_name=perv1` | Four files (`hhrv`, `hhv1`, `perrv`, `perv1`); variable names and labels for `perv1` (139 variables) |
| M-8 | Dataset 213 related materials | https://microdata.gov.in/NADA/index.php/catalog/213/related-materials | Titles only, including an estimation-procedure PDF, instruction manuals Vol I and II, a layout XLSX, a README and a note on updated instructions |
| M-9 | Dataset 292 related materials and data dictionary | https://microdata.gov.in/NADA/index.php/catalog/292/related-materials and `.../data-dictionary` | Titles and two file names only (`mhhQPlfs`, `MPER_Q2_Q4_2025`); **variable lists not read** |

Also used, from the repository: the curated build's occupation records (`data/curated/cb-744256fa29dc/occupations.json`, read only; which of the four `cb-*` builds is "current" was not determined here) and the P2.1 inventory sections D.7–D.8 (search-lead and caveat material, labelled there as unverified).

**Limits that apply to every row below.**

1. A variable **label** shown on a data-dictionary page is evidence that a field with that label exists in that data file. It is **not** evidence of its code list, number of digits, coding version or population coverage.
2. The documents that would settle most open points (README, layout XLSX, State/UT code XLSX, questionnaires, estimation procedure, field-staff instructions) are listed as materials on the portal, but **were not opened**: reading them means downloading files, which this task may not do.
3. The portal's "Get Microdata" step requires login (P2.1 row 11). Nothing here depends on, or implies, any access to the data files.
4. Where this document says "not verified", it means exactly that. It does not mean absent.

---

## B. Required-variable table

"Verified (label)" means the name and label were read on the cited page. All other cells are `NOT_VERIFIED`.

| # | Needed | Verified variable name(s) and label (file) | Definition / code list | Evidence | Availability status | Limitations | Impact on the proposed analysis |
|---|---|---|---|---|---|---|---|
| 1 | **State / UT identifier; Karnataka code** | `st` "State/Ut Code" (284, `cperv12025`); `state_perv1` "State/Ut Code" (213, `perv1`) | **Not verified.** The code list is in the XLSX titled `Indian_States_and_UTs_CodeName` (284) which was not opened. **The value that denotes Karnataka was not observed.** No value is assumed. | M-4, M-7, M-5 | Variable present (label level). Karnataka value: unverified. | Numeric coding and whether Karnataka is a stable code across rounds not verified. | Without the Karnataka value from the code list, Karnataka cannot be documented as identified (FG-4). |
| 2 | **Occupation variable** | `ocu_pas` and `ocu_sas` "Occupation Code (NCO)" (284); `ocu_cws` "Occupation Code (CWS)" (284). 213: `b5pt1q6_perv1` and `b5pt2q6_perv1` "Occupation Code (NCO)" (principal / subsidiary), `b6q7_perv1` "Occupation Code (CWS)" | **Not verified.** Digit count and code values not observed. The CWS labels do not name a classification. | M-4, M-7 | Present at label level in both files | Whether the CWS occupation uses the same NCO version as the PAS/SAS occupation: not verified. | An occupation field exists, but the analysis level (see rows 3 and 12) cannot be set. |
| 3 | **NCO version and depth** | Labels say "(NCO)". The version is not in the label. | **2025 (284):** the dataset description cites "National Classification of Occupation - 2015" (observed on the page; it is a page-level statement, not a variable-level one). **2023-24 (213):** the page returned no classification statement. **Depth (digits): not observed in any source read.** | M-2, M-6 | Version: stated at dataset level for CY2025 only. Depth: unknown. | If a round used a different NCO version, a concordance would be needed (`TASKS.md` P2.3: otherwise FG-8 is FAIL). None was identified or read. | Depth decides whether any pilot code can be joined (row 12). |
| 4 | **NIC classification and version** | `ind_pas`, `ind_sas` "Industry Code (NIC)", `aind_cws` "Industry Code (CWS)" (284); `b5pt1q5_perv1`, `b5pt2q5_perv1` "Industry Code (NIC)", `b6q6_perv1` "Industry Code (CWS)" (213) | Version at dataset level: "National Industrial Classification – 2008" cited on the 284 page. 213: not stated on the page. Depth: not observed. | M-2, M-4, M-7 | Present at label level | Version for 2023-24 unverified. | Industry could be a context dimension (garments are an industry as well as an occupation group). Not assessed. |
| 5 | **Activity status** | `pas`, `sas` "Status Code"; `acws` "Current Weekly Status (CWS)" (284). 213: `b5pt1q3_perv1`, `b5pt2q3_perv1` "Status Code"; `b6q5_perv1` "Current Weekly Status (CWS)" | **Not verified.** Code values (employed, unemployed, out of labour force categories) not observed. | M-4, M-7 | Principal, subsidiary and current-weekly-status fields present at label level | Which fields the project would combine ("ps+ss") and how, is a method decision that cannot be made without the definitions. | Needed for any worker-population ratio or occupation count. |
| 6 | **Reference period and measurement concepts** | Implied by the labels PAS (principal), SAS (subsidiary), CWS (current weekly status) | **Not verified from any source read.** The reference periods are not stated on the pages read. They are not assumed here. | M-4, M-7 | `NOT_VERIFIED` | The definitions sit in the instruction manuals and questionnaires, which were not opened. | The "activity-status basis" required on each indicator row (`TASKS.md` P2.6) cannot yet be stated from evidence. |
| 7 | **Earnings** | `ern_reg` "Earnings For Regular Salaried/Wage Activity"; `ern_self` "Earnings For Self Employed" (284). 213: `b6q9_perv1`, `b6q10_perv1` with the same two labels | **Not verified.** Reference period, unit and activity-status basis of these fields are not shown. | M-4, M-7 | Present at label level | Not an indicator the architecture currently allows by default (§14.2 is the authority). Sparse in small cells. | Out of scope for the first indicators unless §14.2 permits; recorded for completeness. |
| 8 | **Survey weights** | `mult` "Multiplier" (284). 213: `mult_perv1` "Sub-sample wise Multiplier", plus `NSS_perv1` "Ns count for sector x stratum x substratum x sub-sample" and `NSC_perv1` "Ns count for sector x stratum x substratum" | **Not verified.** How the multiplier is applied (e.g. pooling across sub-samples or quarters) is in the estimation-procedure document (213 lists one; not opened). The 284 documentation list has no estimation document under that title. | M-4, M-7, M-8 | Present at label level; the 2025 and 2023-24 weight variables differ in name and, by label, in construction | The label "Sub-sample wise Multiplier" suggests the multiplier is defined per sub-sample, so combining sub-samples may need an adjustment. **That is a reading of a label, not a verified rule.** | Weighting cannot be said to be understood until the estimation procedure is read (FG-7). |
| 9 | **FSU identifier** | `mfsu` "FSU" (284); `b1q1_perv1` "FSU" (213) | Not verified beyond the label; the 284 page states "The first stage unit (FSU) is the 2011 census village in the rural sector." | M-2, M-4, M-7 | Present at label level | Urban FSU definition not shown on the pages read. | Needed for variance estimation (RSE). |
| 10 | **Stratum and sub-sample / design variables** | 284: `strm` "Stratum", `bstrm` "Basic Stratum", `sstrm` "Sub-Stratum", `panel` "Panel code". 213: `b1q5_perv1` "Stratum", `b1q11_perv1` "Sub-Sample", `qtr_perv1` "Quarter" | Not verified. The 284 file has **no** variable labelled "sub-sample" in the list read (`panel` is the nearest, `sss` "Second Stage Stratum No." is a different concept). The 213 file has "Sub-Sample" but the list read shows no separate sub-round variable. | M-4, M-7 | Present at label level, but **not equivalent across the two files** | Whether the 284 design variables suffice for a defensible RSE is not known. | An RSE estimator cannot be specified from labels alone (FG-5, FG-7). |
| 11 | **Round-to-round comparability** | n/a | See section D. | M-2; P2.1 §D.8 (search-summary caveat) | `UNKNOWN` | | |
| 12 | **NCO-2015 compatibility with the four pilot qualifications** | n/a | See section E. | `occupations.json`; M-2 | `UNKNOWN` | | |

---

## C. Variable lists as read (labels only)

**Dataset 284 (CY2025), file `cperv12025`, 153 variables, 1,148,634 cases; labels read for:** `st` (State/Ut Code), `ocu_pas`, `ocu_sas` (Occupation Code (NCO)), `ocu_cws` (Occupation Code (CWS)), `ind_pas`, `ind_sas` (Industry Code (NIC)), `aind_cws` (Industry Code (CWS)), `pas`, `sas` (Status Code), `acws` (Current Weekly Status (CWS)), `ern_reg`, `ern_self`, `mult` (Multiplier), `mfsu` (FSU), `strm`, `bstrm`, `sstrm`, `panel`. The fetch tool summarised the page into these rows; the other variables on the page were not itemised and are not described.

**Dataset 213 (July 2023 – June 2024), file `perv1`, 139 variables, 418,159 cases; labels read for:** `state_perv1`, `b5pt1q6_perv1`, `b5pt2q6_perv1`, `b6q7_perv1`, `b5pt1q5_perv1`, `b5pt2q5_perv1`, `b6q6_perv1`, `b5pt1q3_perv1`, `b5pt2q3_perv1`, `b6q5_perv1`, `b6q9_perv1`, `b6q10_perv1`, `mult_perv1`, `NSS_perv1`, `NSC_perv1`, `b1q1_perv1`, `b1q5_perv1`, `b1q11_perv1`, `qtr_perv1`.

Dataset 292 (quarterly unit-level, Apr–Jun to Oct–Dec 2025): file names only (`mhhQPlfs` 401,928 cases / 39 variables; `MPER_Q2_Q4_2025` 1,696,741 cases / 108 variables). **Its variable list was not read.**

These counts are descriptions of the portal's metadata pages, not counts of any Karnataka subset. **No Karnataka count exists in this repository.**

---

## D. Round comparability (FG-6)

What was observed:

- The 284 page states that the sampling methodology "has been revamped from January 2025" (M-2). It does not state whether CY2025 data are comparable with earlier rounds.
- P2.1 §D.8 records, from a search-tool summary of a PIB release (not the page; the page returned HTTP 403), that annual 2025 estimates may not be strictly comparable with earlier annual reports; and, from a search summary of the "Changes in 2025" notes (not opened), that the survey period moved from a July–June cycle to a January–December cycle. These remain `SEARCH_LEAD_ONLY`.
- The 2023-24 and CY2025 files use different variable naming schemes and different weight and design variables (section B, rows 8 and 10).
- The 284 page cites NCO-2015 and NIC-2008; the 213 page was reported to cite neither. No concordance, bridging or comparability document was identified or read.

**FG-6: `UNKNOWN`.** It is not `PASS`: nothing read shows that any two rounds share definitions and classification, and nothing documents a concordance. It is not `FAIL`: nothing read shows that no such pair exists, and the relevant materials (README, layout, estimation procedure, the "Changes in 2025" notes) were not opened. **What would change it:** reading, for two specific rounds, the README, the data-layout/variable definitions and the estimation procedure, and the official note on the 2025 changes; or a statement in those documents of which rounds are comparable.

`GO_REDUCED` (§21.2) is built on a single round and tolerates FG-6 only "partially". It is not triggered here (see `docs/decisions/MODULE_A_GATE.md`).

---

## E. NCO-2015 compatibility with the four pilot qualifications (FG-8)

**Pilot codes** (from `data/curated/cb-744256fa29dc/occupations.json`, read only; the code structure below is derived mechanically from the code prefix, which is how the build itself populates `nco_levels`):

| Pilot occupation record | NCO-2015 code | Division (1) | Sub-division (2) | Group (3) | Family (4) | Title status in the build |
|---|---|---|---|---|---|---|
| `nco:8153.0101` | 8153.0101 | 8 | 81 | 815 | 8153 | `VERIFIED_IN_SOURCE`: "Sewing Machine Operator, General" |
| `nco:8153.0103` | 8153.0103 | 8 | 81 | 815 | 8153 | `VERIFIED_IN_SOURCE`: "Specialized Sewing Machine Operator" |
| `nco:7543.0301` | 7543.0301 | 7 | 75 | 754 | 7543 | `VERIFIED_IN_SOURCE`: "Measurement Checker" |
| `nco:3122.3551` | 3122.3551 | 3 | 31 | 312 | 3122 | `NOT_FOUND`: no title found in the source (Phase 1 evidence item, not altered here) |

**What the join would need:** the PLFS occupation field's digit depth, and that its coding is NCO-2015 in the round used. Neither is established:

- Version: stated at dataset level for CY2025 only (M-2); not stated for 2023-24 (M-6).
- Depth: not observed in any source read. Therefore it is **unknown at which of the four levels above (division, sub-division, group, family) the pilot codes can be matched**. Any match above the 8-digit code is an aggregation to a coarser occupation group and would be classed `INFERENCE` (§21.1), carrying the usual caution that a coarse group may include occupations that are not the pilot qualification's target.
- Concordance: P2.1 rows 20a/20b record **search leads** that the NCO-2015 Vol I PDF contains an NCO-2015 ↔ NCO-2004 concordance. No NCO volume was obtained (the historical D1 attempt returned 404), so no concordance mapping exists locally, and nothing supports any pilot-code-by-code mapping. A general reference to a concordance is not evidence that each pilot code maps.

**FG-8: `UNKNOWN`.** **What would change it:** (a) the digit depth and NCO version of the PLFS occupation field for the chosen round, from the layout or README; (b) the NCO-2015 code structure confirmed for the four codes (the build holds `OFFICIAL` NCO values, but one has no title); (c) if a round used NCO-2004, an obtained concordance table covering the four pilot codes.

---

## F. Gate-criterion summary (P2.3)

| Gate | Status | Basis |
|---|---|---|
| **FG-3** Required variables and metadata | **UNKNOWN** | Fields for state, occupation, industry, activity status, earnings, weights, FSU, stratum and a sub-sample/panel field **exist at label level** in the two data dictionaries read. But the criterion's own evidence requires the occupation code "with its NCO version and digits", and the digits are not established; the NIC version for 2023-24 and all code lists, definitions and reference periods are `NOT_VERIFIED`. Design variables differ between rounds. |
| **FG-4** Karnataka identification | **UNKNOWN** | A state variable exists (`st`, `state_perv1`). The value denoting Karnataka is documented only in a State/UT code spreadsheet that was not opened. Nothing is assumed from general knowledge. |
| **FG-6** Comparability | **UNKNOWN** | Section D. |
| **FG-8** NCO join | **UNKNOWN** | Section E. |

None is `PASS`. None is `FAIL`: for each, the decisive documents exist on the portal but were not opened, and no read page contradicts the criterion. This is the evidence-based outcome for a no-download, documentation-only check.

---

## G. Open evidence requirements for P2.3

1. Obtain and read, for each round under consideration, the README, data layout and State/UT code list (requires downloading portal files: user approval, new manifest).
2. Read the estimation procedure and field-staff instructions to settle weights, reference periods and status definitions.
3. Read the official note on the January 2025 changes and any comparability guidance.
4. Establish the occupation field's depth and NCO version per round; obtain a concordance only if a round is not NCO-2015.
5. Read the variable lists of dataset 292 if quarterly data are considered.

---

## H. PLFS datasets listed in the catalogue (M-1)

Catalogue ID, title, period, as returned for the listing page: 292 unit-level quarterly (Apr–Jun 2025 to Oct–Dec 2025); 291 unit-level monthly (Apr–Dec 2025); 284 Calendar Year 2025; 254 key employment-unemployment indicators (Jan–Dec 2024); 217 (Jul 2019–Jun 2020); 216 (Jul 2018–Jun 2019); 214 (Jul 2021–Jun 2022); 213 (Jul 2023–Jun 2024); 211 CY2022; 210 (Jul 2022–Jun 2023); 209 CY2021; 208 CY2023; 206 unit-level (Jul 2020–Jun 2021); 204 (Jul 2017–Jun 2018). A catalogue listing is not evidence that files are obtainable or suitable.
