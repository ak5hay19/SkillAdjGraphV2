# Assessment of existing PLFS files outside the repository (Task 1A)

**Status:** read-only assessment, **subject to review**. It does **not** change the Module A decision (`NO_GO`, `docs/decisions/MODULE_A_GATE.md`) or any config.
**Prepared:** 2026-11-01, about 23:07–23:35 IST (Asia/Kolkata) · **Branch / HEAD:** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0` (uncommitted tree)
**Paths assessed (outside the repository):** `C:\skillathon26\plfs-2025` and `C:\skillathon26\nqr`.

---

## 1. Four things that must not be confused

Each file below is reported against four separate questions. A "yes" to one is never read as a "yes" to the next.

| Level | Question | Result for every file here |
|---|---|---|
| **L1 Exists locally** | Is there a file at that path? | Established (section 3). |
| **L2 Contents inspected** | What did I actually read? | Varies per file; stated in section 3. |
| **L3 Official acquisition established** | Is there a saved access record, manifest, hash-at-download or other evidence of how and from where it was obtained? | **Not established for any file.** There is no manifest. The README text names the National Statistics Office as author, but a document's own heading is not an access record. No file's provenance was inferred from its filename. |
| **L4 Reuse terms established** | Do quoted terms permit analysis, display or publication? | **Not established for any file.** The README contains one use-limiting sentence (section 4, item 7). It is a rider, not a licence, and it does not address display or publication. |

---

## 2. What was done and not done

**Done (read-only):** existence, size and timestamp listing; SHA-256 of the 11 non-CSV files; the README text read from its XML parts; workbook sheet names, headers and a few rows read through `openpyxl` in read-only mode (`data_only`); the member list of the ZIP's central directory; text extracted from the four PDFs with `pypdf`; the first 4,000 bytes of each CSV (header line and one data row, to confirm column count only); one public metadata page of the National Microdata Portal (dataset 291 data dictionary) to compare counts; a names-and-sizes listing of two sibling folders (section 7).

**Not done:** nothing was copied, moved, modified, deleted, extracted, executed or installed. The ZIP was **not** extracted (its single member is an `.exe`; it was not run). `HH.csv` and `PER.csv` were **not** loaded, counted, hashed or scanned: only a 4,000-byte head of each was read, and no value from a data row is recorded here. **No statistic, count or estimate was produced.** Nothing was downloaded. No account was used. `config/labour_market.yaml` (SHA-256 `3ff5d350…c6e4`) and `config/overlay_approvals.yaml` (`287e3f67…81f1`) are unchanged.

---

## 3. Per-file report

Sizes are from the filesystem. Timestamps are filesystem modification times only (all 2026-10-30); they say nothing about when or how the content was produced.

### 3.1 `C:\skillathon26\plfs-2025\`

| File | Found | Size (bytes) | Appears to contain | Actually inspected (L2) | Gates it could help | What it does **not** establish |
|---|---|---|---|---|---|---|
| `Data_in_CSV\Data_in_CSV\HH.csv` | **Yes** | 103,648,714 | Household-level records (39 columns by header) | First 4,000 bytes: header and one row. Header: `file_id, sch, qtr, month, visit, sec, st, dc, nss_reg, bstrm, strm, grp, sstrm, sro, mfsu, sss, ssu, smonth, …, nsc, mult, totalsd, zst, caph, smallh, panel` | FG-1 (a file exists), FG-3/FG-4 (fields present), later FG-5 | Row count (not counted); that the content matches the README or the portal; authenticity; how it was produced (the README says the TXT→CSV converter is an `.exe`; who ran it is unknown). **Not hashed** (a full read). |
| `Data_in_CSV\Data_in_CSV\PER.csv` | **Yes** | 838,165,660 | Person-level records (108 columns by header) | First 4,000 bytes: header and one row. The 108 header names equal, in count, the 108 fields listed in layout sheet `MPER_04_12_2025`; the leading and trailing names seen (`st`, `ocu_cws`, `acws`, `mult`, `nsc`, `zst`, `caph`, `smallh`, `panel`) are among them. | FG-3, FG-4, FG-8, and FG-5/FG-7 **if** later analysed | Row count; value ranges; whether `st` contains the code for Karnataka; coding of `ocu_cws`; completeness; authenticity. **No value from any row is recorded.** |
| `1_README_PLFS_M2025.docx` | **Yes** | 31,501 | README titled "Periodic Labour Force Survey (PLFS), Monthly Data 2025. Final Multiplier-posted Unit-Level Data for Schedule- 10.4", headed "Government of India, Household Survey Division, National Statistics Office, … Kolkata" | Full text read. Document properties: author field "NSSO"; last-modified property 2026-04-30 | FG-3, FG-7 (weights; variance fields), FG-2 (use rider) | That this copy was obtained from an official channel; that it is the version distributed with the data; **any licence**. |
| `2_Data_LayoutPLFS_M2025.xlsx` | **Yes** | 61,823 | Fixed-width layout of the monthly household and person files | Sheet names (`Data Layout`, `MHH_04_12_2025`, `MPER_04_12_2025`; hidden: `hhrv`, `perrv`, `perv1 (2)`); the full person sheet (108 fields with Full Name, length, byte positions, field name) | FG-3, FG-4, FG-8 | Code lists (values and meanings); classification version (the layout labels do not name one); population coverage. Three hidden sheets were noted and not examined. |
| `3_Bstrm_file.xlsx` | **Yes** | 76,580 | Basic-stratum table with a `Metadata` sheet | Sheet names, header and first rows | FG-3, FG-7 (design) | Variance method; completeness. |
| `4_Indian_States_and_UTs_Code_Name.xlsx` | **Yes** | 9,395 | State / UT code to name list | Whole sheet (36 rows read). It lists **29 = Karnataka** | FG-4 | That the `st` column of the data uses these codes (not checked in the data); provenance. |
| `5_Indian_Districts_Code_Name.xlsx` | **Yes** | 32,510 | State, district code and name | Sheet name and first rows | Not needed for the current gates | n/a |
| `6_PLFStxt2csv_M2025.zip` | **Yes** | 92,670,796 | One member, `6. PLFStxt2csv_M2025.exe` (93,614,467 bytes) | Central-directory listing only. **Not extracted. The executable was not run.** | None | What the executable does. It is unvetted and **must not be run** without a separate decision. |
| `7_Schedule0_0_PLFS_January-December_2025.pdf` | **Yes** | 116,031 | Schedule 0.0PL, "List of Households", 8 pages | Text extracted, first page and keyword scan | None directly | n/a |
| `8_Schedule10_4_FIRSTVISIT_Janaury-June_2025.pdf` | **Yes** | 559,388 | Schedule 10.4 (First Visit), January–June 2025, 12 pages | Text extracted; classification and CWS lines read | FG-3, FG-8, FG-6 | That the monthly data were collected with this exact schedule version. |
| `10_Schedule10_4_FIRSTVISIT_July-Dec_2025.pdf` | **Yes** | 566,317 | Schedule 10.4 (First Visit), July–December 2025, 12 pages | Same | FG-3, FG-8, FG-6 | Same. |
| `11_Schedule10_4_REVISIT_July-Dec_2025.pdf` | **Yes** | 329,242 | Schedule 10.4 (Revisit), July–December 2025, 8 pages | Same | FG-3, FG-8 | Same. |
| `9_…REVISIT_Janaury-June_2025.pdf` (implied by numbering 7, 8, **9**, 10, 11) | **Not found** | n/a | n/a | n/a | n/a | The numbering gap is observed; nothing is inferred about it. |

SHA-256 of the non-CSV files (for a future manifest):

| File | SHA-256 |
|---|---|
| `1_README_PLFS_M2025.docx` | `b4a61e7526619aa433e7996a2c7b45c9a478c62ee68b78dba2d2183baa77a737` |
| `2_Data_LayoutPLFS_M2025.xlsx` | `7d902e4d91578b9488bb92c802acbf714dc876e4f41a3546ea13ff6f56b99f07` |
| `3_Bstrm_file.xlsx` | `1ed6df66820ece1cb23ae4a400be30a92b64cf2f963e2f59df45e2f3da3febc0` |
| `4_Indian_States_and_UTs_Code_Name.xlsx` | `5c246ed07a4582b3965854d5a887eb87669610245fd316b3cf62e063f38fc05f` |
| `5_Indian_Districts_Code_Name.xlsx` | `bcee9c392bd8660e94b3915fc366703f16cfbf14e7f0abe007ec905737bebf34` |
| `6_PLFStxt2csv_M2025.zip` | `b07a61a16d4bd8b91157a0dd84624bff0cdf4140d3bd8c7e16edcdcafc679d69` |
| `7_Schedule0_0_PLFS_January-December_2025.pdf` | `e65eb647934882ce53fffe5bf1115b74fe9fa4b34d491d2bb121227d16357214` |
| `8_Schedule10_4_FIRSTVISIT_Janaury-June_2025.pdf` | `ec8be2b82d5274f9e0828407199a15aaa19c3c604686b19507968e6f8b4a7da4` |
| `10_Schedule10_4_FIRSTVISIT_July-Dec_2025.pdf` | `5a62664f4035ba4f87fb99fbd23239c9ae940d8ac81f03622163c45df75d4e1f` |
| `11_Schedule10_4_REVISIT_July-Dec_2025.pdf` | `1f995a4840843d5245dcb9e3f9f9571ff5717843689e0f62d8fcf7e04bf0a7d1` |
| `HH.csv`, `PER.csv` | not computed (would need a full read) |

### 3.2 `C:\skillathon26\nqr\`

| File | Found | Size | Appears to contain | Inspected | Gates | Does not establish |
|---|---|---|---|---|---|---|
| `Data_Qualification_Register_30-Oct-2026.xlsx` | **Yes** | 249,123 | A qualification register: one sheet, `Documents`, header plus 2,081 data rows, 24 columns (Sr. No., Qualification Name, NQR Code, Sector, Sub-Sector, NSQF Level, Type of Training, Type of Qualification, … hours and dates columns). Workbook properties: creator "Apache POI", created 2026-10-29, last-modified property 2026-11-01 (the file's own timestamp is 2026-10-30; the discrepancy is unexplained). SHA-256 given below the table. | Sheet names, header row, first two data rows (columns only), row count. **Not merged with, or compared to, any project data.** | **None of the Module A gates.** It is qualification (Module B) material only. | Acquisition route, completeness, or any relation to the curated build. Any use is a separate Phase 1/Module B decision. |

Full hash: `6c85c0c0420828121bff04b65219b05c6c38ca82210837f284ab8580808f8925`.

---

## 4. What the files themselves say (L2 evidence; provenance unestablished)

Every statement below is a statement made **by these local files**, not a verified fact about the official data.

1. **Which release.** The README says: "Periodic Labour Force Survey (PLFS), Monthly Data 2025 … Monthly Unit level data for Sch. 10.4 … for April-December 2025"; "2 data files (one each for Household level and Person level)" for "9 months"; `MHH_04_12_2025.txt` 804,145 records of 128+1 bytes; `MPER_04_12_2025.txt` 3,394,123 records of 301+1 bytes. The layout workbook's person sheet has 108 fields and the household sheet is titled "MHH_04_12_2025".
   **Comparison with the public portal** (public page `https://microdata.gov.in/NADA/index.php/catalog/291/data-dictionary`, read today): "unit-level data of PLFS for monthly (April to December 2025)"; files `HH` 804145 cases / 39 variables and `PER` **3394129** cases / 108 variables. The household count and both variable counts match the README and the local headers (39 and 108). **The person-record count differs by 6 (README 3,394,123; portal 3,394,129).** This is a metadata discrepancy that I cannot resolve; the local CSV row count was not checked. This is corroboration of consistency, **not** evidence of how the local files were obtained.
2. **State.** Person layout field 7: `st`, "State/Ut Code", length 2. The local state-code workbook lists `29` = "Karnataka". Whether the `st` values in `PER.csv` use these codes was **not** checked.
3. **Occupation.** The monthly person layout has **one** occupation field: `ocu_cws`, "Occupation Code (CWS)", **length 3** (bytes 249–251). There is no principal- or subsidiary-status occupation field in the monthly person file. Schedule 10.4 (First Visit and Revisit) states, for the current weekly activity: "7. occupation (3-digit NCO-2015 code)"; the first-visit schedules also state "col. (6): occupation: 3-digit code as per NCO-2015". **So the schedules state NCO-2015 at 3 digits; whether the data values are stored that way was not checked.**
4. **Industry.** `aind_cws`, "Industry Code (CWS)", length 2; the daily-activity industry fields (`ind11`…`ind17`, `ind21`…`ind27`) are length 2. The Revisit schedule says "industry (2-digit NIC-2008 code)"; the first-visit schedules say "5-digit code as per NIC-2008" for the usual-activity block. The monthly layout carries 2-digit industry fields only.
5. **Activity status.** `acws` "Current Weekly Status (CWS)" (length 2) and daily "Status Code for activity 1/2" fields (`das11`…`das27`) are present. **There are no usual principal / subsidiary status fields in the monthly person layout.** The "ps+ss" basis named in `TASKS.md` P2.3 is therefore not available in these files; a CWS basis is. The schedules describe the weekly block as "current weekly activity particulars … during the week ended on …"; the numerical reference-period wording was not found in the extracted text.
6. **Earnings.** `ern_reg` (regular salaried/wage), `ern_self` (self-employed), length 8 each, plus daily `ern11`…`ern27`. Reference period and conventions were not found in the files read.
7. **Weights and design (README).**
   - "Final Weight = MULT /100" ("MULT … weight or multiplier (in two places of decimal) calculated at the level of Second Stage Stratum (SSS) of a first stage unit (FSU) within sector x state x stratum x group x substratum").
   - "For computation of design based variance or Relative Standard Error, one has to use ZST, NSC, Caph and smallh fields."
   - Layout fields present: `mfsu` (FSU), `strm`, `bstrm`, `sstrm`, `grp`, `sss`, `nsc`, `mult`, `zst`, `caph`, `smallh`, `panel`, `totalsd`.
   - The README says a total of "39 FSUs, which were received after the end of a particular month has been considered only in the Annual estimates", i.e. the monthly file omits them.
8. **A use-limiting statement (relevant to FG-2).** The README's "rider for users" says: "The unit level data of PLFS should not be specifically used for studying of any variable other than the employment and unemployment indicators." This is a purpose limitation on **the unit-level data**, stated in a file of unknown provenance. It does not say anything about displaying or publishing aggregates, attribution or redistribution. Whether an occupation-group count for Karnataka falls inside "employment and unemployment indicators" is **not established**. The sentence makes the FG-2 question **harder**, not easier.

---

## 5. Comparison with existing Phase 2 documents

| Existing statement | Effect of these local files |
|---|---|
| `module_a_sources.md` §B.3, gate record FG-1: "no identifiable Module A dataset" in the repository | **Still correct for the repository.** These files sit outside it; the search was limited to the repository and its `data/` folder. Not an error, but the picture is incomplete. |
| `module_a_variables.md` row 1: Karnataka value not observed | A local file now shows `29` (L2). Not yet matched against data values; provenance unestablished. |
| `module_a_variables.md` rows 2–3: NCO digit depth "not verified" | The monthly layout (field length 3) and the schedules ("3-digit NCO-2015 code") give 3 digits for the CWS occupation field. This applies to the **monthly CWS** field, not to the quarterly/annual files read earlier (which have `ocu_pas`, `ocu_sas`, `ocu_cws` and whose digits are still unstated). |
| `module_a_variables.md` row 5: PAS/SAS/CWS labels present | True for the quarterly and annual files; **the monthly file in this folder has CWS and daily status fields only**. The two file families differ. |
| `module_a_variables.md` §E: pilot codes can join at "division, sub-division, group or family; depth unknown" | With 3 digits, the match is to NCO-2015 **group** only: 815 (the two sewing-machine-operator codes), 754 (the measurement-checker code), 312 (the production-supervisor code). That is an aggregation and would be classed `INFERENCE` (`ARCHITECTURE.md` §21.1). The family level (4 digits) is not available in the monthly file. |
| `module_a_sources.md` row 11: registration needed | These files imply that someone held them locally. How (login, other route) is unknown; the portal "Get Microdata" page requires login (observed earlier). |
| `module_a_variables.md` §D (FG-6): rounds not comparable evidence | Unchanged. The local data cover one release (April–December 2025). The 2025 methodology note was not in the folder. |
| `MODULE_A_GATE.md` | **No change to the decision.** See section 6 for candidates for reassessment. |

---

## 6. Which gates these files could help, and which still need independent evidence

None of the status changes below is made here. "Could be reassessed" means the content inspected is relevant evidence, not that the status would be `PASS`.

| Gate | Current | Could be reassessed on this material? | Still needs independent evidence |
|---|---|---|---|
| FG-1 Access | FAIL | **Only if** you establish provenance: a statement from you of how and when the files were obtained (an official channel), an access/terms record, and a manifest with hashes of **all** files including the two CSVs. Existence alone does not meet the criterion. | The access record, a manifest, the CSV hashes. |
| FG-2 Reuse | FAIL | **No improvement from these files.** The README rider (section 4, item 8) is a restriction signal. | The portal's actual conditions/undertaking and the unread MoSPI policy documents; clarification that competition display of aggregates is allowed. |
| FG-3 Variables | UNKNOWN | **Yes**, for the monthly file: variables are documented at name, length, position and label level; NCO-2015 (3-digit) and NIC-2008 are stated in the schedules. | Code lists (value meanings); whether the stored values match the layout; reference-period definitions; the monthly file lacks usual-status (ps+ss) fields. |
| FG-4 Karnataka | UNKNOWN | **Yes**: `st` exists and the state workbook lists `29` = Karnataka. | A check that `st` in the data takes that value (needs a bounded read of the data). |
| FG-5 Sample | UNKNOWN | **Could be run (P2.4)** if FG-1/FG-2 questions are resolved first: the data files exist. | Thresholds with justification; the count itself; whether a 3-digit NCO base is enough. |
| FG-6 Comparability | UNKNOWN | **Slightly**: both schedule halves (Jan–Jun, Jul–Dec 2025) state NCO-2015 / NIC-2008; but one release only. | The 2025 methodology note; a second release; a concordance if classifications differ. |
| FG-7 Reproduction | UNKNOWN | **Could be attempted** with a published Karnataka figure for the matching period. The README gives the weight rule (MULT/100). | A named published Karnataka figure for the same release, a stated tolerance, and a decision that analysing the data is permitted (FG-2). |
| FG-8 NCO join | UNKNOWN | **Yes, partly**: the occupation field is 3-digit NCO-2015 per layout and schedule, so the join level is **group** (815, 754, 312), classed `INFERENCE`. | Evidence that the stored values really are 3-digit NCO-2015; the official NCO-2015 structure for the three groups (the NCO volumes are not in this folder; see section 7); the question of whether a group-level join is meaningful for the pilot qualifications. |

---

## 7. Incidental observation (names and sizes only; **not inspected, not assessed**)

Listing the parent folder `C:\skillathon26\` for this task revealed other existing material outside the repository. Nothing was opened.

- `downloads\nco2015-vol1\National_Classification_of_Occupations_Vol_I-2015.pdf` (7,115,143 bytes), `downloads\nco2015-vol2a\…Vol_II-A-2015.pdf` (7,024,082), `downloads\nco2015-vol2b\…Vol_II-B-2015.pdf` (6,624,287). `module_a_sources.md` rows 20, 20a, 20b and F-5 record these volumes as not obtained and not attempted.
- `downloads\karnataka-econ-survey\economic_survey_2025-26_english.pdf` (15,118,530) and five small `ka-*.csv` files. `module_a_sources.md` rows 15–16 record the Economic Survey as listing-only.
- `work\` holds many analysis files, including `nco_vol1_concordance.csv`, `nco_full.csv`, `nco_pilot.csv`, `nco_vol1_families.csv` and `nco_full_report.md`.
- Also `SkillAdjacencyGraph\` (an earlier project folder), `link_report.md`, `verific.py`, `skillathon_passes\`.

These may bear on FG-8 and P2.1 and on the DGE/DES terms issue, but their provenance and terms are as unestablished as those of the PLFS files. They were outside this task's stated scope.

---

## 8. Conclusions and open points

1. **Do the files materially change the Phase 2 evidence picture?** **Yes for FG-3, FG-4 and FG-8** (documentation-level evidence now exists locally). **No for FG-1 and FG-2:** existence is not acquisition, and the README rider narrows rather than opens the reuse question. The recorded decision stays `NO_GO` until FG-1 and FG-2 are independently established.
2. **Provenance is the single most valuable open fact.** Only you can say how and when these files were obtained. Without it FG-1 cannot be assessed.
3. **Safety flags for any later step:** do not run `6. PLFStxt2csv_M2025.exe`; do not process `PER.csv` or `HH.csv` before the FG-1/FG-2 questions are settled and approved; keep them outside the repository (`data/` is gitignored; the files are not).
4. **Unexplained items:** the person-record count difference (README 3,394,123; portal 3,394,129); missing schedule file 9; hidden sheets in the layout workbook; the NQR workbook's modified-property date.
