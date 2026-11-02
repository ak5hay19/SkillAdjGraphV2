# Module A source and access inventory (P2.1)

**Status:** initial evidence-backed inventory, **subject to review**. P2.1 is not marked DONE by this document. **Section H (P2.2 terms and reuse review) was appended on 2026-11-01 (run 2); sections A–G were not altered except for the pointer notes marked "(run 2)".** Section H is also **subject to review and not marked DONE**. **(Task 1A, 2026-11-01)** PLFS files that exist **outside** the repository (`C:\skillathon26\plfs-2025`) were later located and assessed read-only in `docs/feasibility/existing_plfs_files_assessment.md`; nothing in sections A–H was changed by that task, and acquisition and reuse terms for those files remain **not established**.
**Prepared:** 2026-11-01 (revised by correction task P2.1-A-R1 and the P2.1 close-out consolidation) · **Branch / HEAD at preparation:** `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0`
**Gate state at preparation:** `config/labour_market.yaml` has `gate_decision: NOT_ASSESSED`; `config/overlay_approvals.yaml` has `approved: []`. Neither was touched.

---

## A. Purpose and scope

This is the P2.1 source and access inventory required by `TASKS.md` Phase 2 (P2.1): for each candidate source it records the official URL, access route, account requirement, rounds, file formats, and whether files were obtained (with manifest entries). It answers one question: **what can actually be obtained, and what has been observed?**

It is **not**:

- a lawful-reuse assessment (P2.2). Terms pages are located only; no source is classified `PERMITTED`, `RESTRICTED` or `UNCLEAR`, and nothing here concludes whether competition display or publication is allowed.
- a variable or codebook check (P2.3). No FG-3, FG-4, FG-6 or FG-8 determination is made.
- a sample or reproduction analysis (P2.4). No estimate, count or weighted indicator was produced.
- a gate decision (P2.5). No `GO`, `GO_REDUCED` or `NO_GO` is declared.

**Method and limits.** Official public HTML pages were read through a page-text fetch tool on 2026-11-01. Nothing was downloaded, saved to the repository, registered, logged in to, submitted or installed. PDF, XLSX and other file links were **not** opened. Web-search results were used only as leads and are labelled `SEARCH_LEAD_ONLY` unless the official page itself was read. Where a page returned no usable content, that is stated rather than filled in.

**Evidence labels used in section C:**

| Label | Meaning |
|---|---|
| `PAGE_OBSERVED` | The official HTML page was read and the statement is taken from it. |
| `LISTING_OBSERVED` | The official page lists a downloadable file; the file was not opened or obtained. |
| `FILE_OBTAINED_LOCAL` | A local file exists and is in the 2026-10-30 manifest (historical acquisition). |
| `SEARCH_LEAD_ONLY` | A URL or claim appeared only in search results or in a search-tool summary. Not verified on the official page. |
| `NOT_VERIFIED` | Could not be established in this task. |
| `NOT_ATTEMPTED` | Deliberately not attempted (download, registration, or reserved for a later task). |
| `PENDING_USER_ACTION` | Needs a user action or decision before anything further can be done. |

---

## B. Historical acquisition inventory

### B.1 Historical claims versus current verification

The task brief described the 2026-10-30 acquisition as a historical claim (15 files, nine PDFs plus HTML and reports, 17 of 20 planned items). Those figures are **not** reproduced exactly by the current filesystem and manifest:

| Historical claim | Currently verified |
|---|---|
| 15 files downloaded | 15 manifest rows with a non-robots local file and a manifest `validation_status` of `PASS` or `PASS_WITH_DISCREPANCIES` (A1, A1b, A2–A5, B1–B4 incl. B2b, C1, C2, D1-src, D2-p5). Three `robots.txt` files are also saved (18 manifest rows with a local file). `data/raw/` holds 22 files in total (the 18, plus `_state.json`, `ACQUISITION_REPORT.md`, `MANIFEST.csv`, `VALIDATION.json`). |
| Nine PDFs | **10** PDF files on disk, all manifest-referenced: 1 catalogue list, 4 AMHSSC QFs, 4 AMHSSC QPs, 1 NQR-hosted QF copy (B2). |
| 17 of 20 planned items | The manifest has **22 rows** (3 `robots.txt` + 19 items). 4 rows have no local file (C3, C4, D1, D2). The "17 of 20" ratio **could not be reproduced** from the manifest. Not reconciled here. |
| Four QFs, four QPs | Confirmed: QFs A3, A5, B2b, B4 (AMHSSC) plus B2 (NQR copy of the Inline Checker QF); QPs A2, A4, B1, B3. |
| NQR C3/C4 and NCO PDF D1 unsuccessful | Confirmed in the manifest: C3 `FAIL_HTTP` (404), C4 `NOT_FOUND`, D1 `FAIL_HTTP` (404). D2 (online NCO table summary) is `NOT_FOUND`; only its page 5 was saved (D2-p5). |
| No competency/adjacency dataset obtained | Consistent with the filesystem: nothing of that kind was identified (see the limits in section B.3). |

### B.2 Repository state at inspection

| Item | Result |
|---|---|
| Repository root | `C:/skillathon26/SkillAdjGraphV2` |
| Branch / HEAD | `chore/repo-foundation` / `b0fcff46b93b986d97ed04dcbbf8e87b6c1c0ae0` (`b0fcff4 project handoff for consultant gpt chat`) |
| Working tree | Clean: `git status --short`, `git status --porcelain=v1 --untracked-files=all`, `git diff --stat` and `git diff --check` all produced no output (exit 0). |
| Caveat | `data/` and `docs/PROJECT_HANDOFF.md` are gitignored, so a clean tree says nothing about changes inside `data/`. Their integrity is covered by the hashes below. |

### B.3 Present and absent

**Present (all under `data/`, local only, gitignored):**

- `data/raw/2026-10-30/`: 22 files, the only raw acquisition folder. No newer acquisition folder exists.
- `data/processed/acquisition_2026-10-30/`: 1 file (`approved_qualifications_parsed.csv`).
- `data/processed/extracted_2026-10-30/`: 9 files.
- `data/processed/audit_2026-10-30_m1s1/`: 2 files (`AUDIT_NOTE.md`, `corrections_overlay.csv`).
- `data/curated/`: four build directories: `cb-0e76c97bea00`, `cb-4ff16acc3b27`, `cb-601c0399c999`, `cb-744256fa29dc`. Existence and identifiers only; contents were not opened, rebuilt or validated. Which one is "current" was not determined.
- `data_acquisition/acquire_2026-10-30.py` (42,865 bytes), `data_extraction/extract_2026-10-30.py` (56,934 bytes), `data_extraction/test_reconcile_2026-10-30.py` (3,712 bytes). Frozen legacy scripts; metadata only.

**Absent:**

- `data/labour/` and `data/outputs/` do not exist.
- **No identifiable Module A dataset (PLFS file, Karnataka labour-market report, employment table or unit-level microdata) was found in the inspected inventory and filename-pattern search.** The inspected inventory covered `data/raw/`, `data/processed/`, `data/curated/` and the legacy script folders (metadata for all; hashes for raw and processed). The filename search ran over the repository outside `.venv` and `.git` (patterns: plfs, labour, labor, employment, periodic, microdata, `.dta`, `.zip`, `.xls[x]`, `.sav`) and matched only `config/labour_market.yaml`.
- **Limits of that finding:** the search is by filename pattern. The contents of unrelated or generically named files were **not** comprehensively inspected: the extraction CSVs, curated JSON and raw PDFs were not opened. A missing filename match is not proof that no relevant data is embedded in some other file.
- The 404 response bodies for C3 and D1 were not saved; the manifest still records a hash and size for each. There is no local file to compare, so these are recorded as missing, not recreated.

**Identifiable Module A data located: none, within the limits stated above.**

### B.4 Manifest comparison (`data/raw/2026-10-30/MANIFEST.csv`)

Columns found: `item_id, item_name, phase, required_for_gate, source_org, source_url, catalogue_url_raw, final_url, local_relative_path, retrieved_at, http_status, content_type, size_bytes, sha256, file_type, pdf_pages, validation_status, reason, notes`. There are 22 data rows.

**Result: all 18 manifest rows that name a local file exist, and each recorded SHA-256 and `size_bytes` matches the file now on disk. No hash mismatch. No missing manifest-referenced file. No manifest-referenced path is absent.** The four rows without a local path (C3, C4, D1, D2) are failed or partial acquisitions recorded as such.

Four files in `data/raw/2026-10-30/` are **not** manifest-referenced (they are the run's own working and report files): `_state.json`, `ACQUISITION_REPORT.md`, `MANIFEST.csv` (the manifest itself), `VALIDATION.json`.

| Item | Local path (under `data/raw/2026-10-30/`) | Size (bytes) | SHA-256 (full) | Manifest status | Hash agrees |
|---|---|---|---|---|---|
| R-sscamh | `robots/sscamh__robots.txt` | 437 | `5d64116fce7a2a90babb5a389e45ef6451dd3065170038e57d0962354074a55a` | PASS | yes |
| R-nqr | `robots/nqr__robots.txt` | 23 | `c485097f6dfeba79467a4a492ef25b357a78c0c228540ef9f9e6763f321aa0fc` | PASS | yes |
| R-dge | `robots/dge__robots.txt` | 2027 | `773fb8d35bb9a39d35335ee6db8dc5c912d2aacbfb823152d9c61cd647dd902d` | PASS | yes |
| A1 | `amhssc/catalogue/approved-qualification.html` | 100611 | `a793f3991fc763438966605a084642c12cb133d03665ebfe455735bac3da2229` | PASS | yes |
| A1b | `amhssc/catalogue/Approved Qualification List.pdf` | 459146 | `d9ad76f86f48ea0041d98f91619b9feb35f675293f8dcd1877043aa6ad92479b` | PASS | yes |
| A2 | `amhssc/qp/Sewing Machine Operator.pdf` | 195890 | `5ea732a18451e43b0e6d9da160657486932933251dfe03190aca4b53a49ddf4d` | PASS | yes |
| A3 | `amhssc/qf/Q FILE Sewing Machine Operator.pdf` | 1529658 | `c630f3c46e9f17cee25738e3948f9885df95c362ef2ed481073f810f8afb52ea` | PASS_WITH_DISCREPANCIES | yes |
| A4 | `amhssc/qp/Specialized Sewing Machine Operator.pdf` | 209871 | `e07412cb6b266de44caa14a2af12c7ca7664b66c7327e450ff8fadc7ba1395aa` | PASS | yes |
| A5 | `amhssc/qf/Q FILE Specialized Sewing Machine Operator(1).pdf` | 1520098 | `607d1b38c386e397a80527681669770909d2816e50f67fc77e421a714456f52d` | PASS_WITH_DISCREPANCIES | yes |
| B1 | `amhssc/qp/Inline Checker Sewing QP File.pdf` | 192493 | `86fc03447d419eb08da84159fda1e25301c1848c61a86d3d2c9b392aef14809a` | PASS_WITH_DISCREPANCIES | yes |
| B2 | `nqr/qf/Q FILE Inline Checker Sewing Version 4.0.pdf` | 752981 | `9b2cf9c8533e615677052a04410090c1d810a89da6352e804d7405350e218ac7` | PASS_WITH_DISCREPANCIES | yes |
| B2b | `amhssc/qf/Inline Checker Sewing V4_0.pdf` | 357927 | `ca3a898dbd8396f98cebefed40477464d04d417656eb69349d179dbaa0c436f6` | PASS_WITH_DISCREPANCIES | yes |
| B3 | `amhssc/qp/Production Supervisor Sewing QP File.pdf` | 243892 | `199f2422e99b3999accfcc203d0cc4b28e509e833a621a74796d510115d4aafb` | PASS | yes |
| B4 | `amhssc/qf/Production Supervisor- Sewing V4_0.pdf` | 365069 | `8f2811ecc222215996e862198fb19882b8c92db9d827d7250abe3a7dd00fb0fc` | PASS_WITH_DISCREPANCIES | yes |
| C1 | `nqr/html/13152.html` | 74691 | `86c4e5a4a87cc5d7960e96881f770ca1218e5cea66fec0661a5847b811d2e9e5` | PASS_WITH_DISCREPANCIES | yes |
| C2 | `nqr/html/12774.html` | 75769 | `eafbb5c910fa8780289a0db8bb85551d1e131c91000733cb5d42d167a464d115` | PASS_WITH_DISCREPANCIES | yes |
| D1-src | `dge/nco/nco-2015.html` | 80230 | `ff88e51d9a35b41343a1ff29cad02a0d87013dc2073e5778373a5fa013659f4d` | PASS | yes |
| D2-p5 | `dge/nco/dge_nat_page_5.html` | 1078508 | `46145e523572eda07ce977624f40d47c3fd87bc6a767d306d1945c2ad7ca4fcd` | PASS | yes |
| C3 | none | n/a | manifest records a hash for the 404 body only | FAIL_HTTP (404) | no local file |
| C4 | none | n/a | none | NOT_FOUND | no local file |
| D1 | none | n/a | manifest records a hash for the 404 body only | FAIL_HTTP (404) | no local file |
| D2 | none (summary row; page 5 is D2-p5) | n/a | none | NOT_FOUND | no local file |

**Integrity limits.** A matching hash shows consistency with this manifest only. It does **not** establish the authenticity of the original source, lawful reuse, completeness of any dataset, or suitability for labour-market analysis. The PDFs were hashed by bytes only; none was opened, rendered or parsed in this task.

### B.5 Classification of existing artifacts

| Class | Artifacts | Notes |
|---|---|---|
| **1. Module B qualification evidence** | QFs: A3, A5, B2b, B4, plus NQR copy B2. QPs: A2, A4, B1, B3. Catalogue: A1, A1b. NQR records: C1, C2. Extracted catalogue `data/processed/acquisition_2026-10-30/approved_qualifications_parsed.csv`. Extraction tables in `data/processed/extracted_2026-10-30/`. Audit overlay in `data/processed/audit_2026-10-30_m1s1/`. `data/curated/cb-*` builds. | Qualification and eligibility evidence only. **NOS extraction from these documents is not a competency or adjacency dataset obtained from elsewhere, and none of this is Module A data.** |
| **2. NCO classification evidence** (possibly relevant to FG-8; not labour-market observations) | D1-src (`dge/nco/nco-2015.html`, DGE landing page), D2-p5 (`dge/nco/dge_nat_page_5.html`, page 5 of the online NCO table, which the manifest notes contains target codes 8153.0101, 8153.0103, 7543.0301). | Partial and classification-only. The full NCO-2015 volumes were **not** obtained (D1 returned 404). No FG-8 determination is made here. |
| **3. Module A labour-market data** | **None identified.** | No PLFS or other Karnataka employment, occupation or earnings dataset was identified locally (see the limits in section B.3). |
| **4. Unrelated or uncertain** | Three `robots.txt` files (acquisition-discipline records); `_state.json`, `ACQUISITION_REPORT.md`, `VALIDATION.json` (run bookkeeping). | Provenance records, not source content. |

### B.6 Processed, config and script metadata

All raw, processed and config files were hashed (bytes only, 40 files) before this document was written, and re-hashed afterwards for comparison. Only the two gate files are listed here.

| File | Size | SHA-256 |
|---|---|---|
| `config/labour_market.yaml` | 322 | `f94ba49d8adeb18678830dee62ab8a5cccc419970108ed16a759f877d3bccda6` |
| `config/overlay_approvals.yaml` | 374 | `287e3f677b2ef81f14036b8e427c8271df48ae26c6a34b4b5ce9936ec81df1f3` |

Config observations: `labour_market.yaml` contains `gate_decision: NOT_ASSESSED`, `decided_on: null`, `criteria: []`. `overlay_approvals.yaml` contains exactly `approved: []`.

### B.7 Document disagreements noted (not reconciled)

1. The brief's "nine PDFs" and "17 of 20 items" do not match the manifest (section B.1).
2. `ARCHITECTURE.md` §14.1 says the NCO Vol I PDF "returned 404 earlier". The official DGE NCO-2015 page now **lists** Vol I as a PDF (section C, row 20). That is a listing observation only. Whether the file can be retrieved was not tested, and the page's link target was not inspected, so whether it differs from the URL that returned 404 on 2026-10-30 is unknown. Separately, the Vol I URL supplied by the independent review (row 20a, (i)) is identical to the manifest D1 URL that returned 404; a different indexed path (`2023-07`) also exists as a search lead. Neither was fetched. A further `2024-05` path supplied by the final review (row 20b) is likewise an unreproduced search lead.
3. `docs/PROJECT_HANDOFF.md` is gitignored and was used as historical context only. Its Phase 2 notes say it is undefined whether reading public pages without saving them needs approval (`TASKS.md` says only "any download"). This task read public HTML pages and saved nothing; that interpretation should be confirmed by the reviewer.
4. `ARCHITECTURE.md` §14.1 lists the Karnataka Economic Survey as a candidate source with "table provenance, definitions, years, licence" unverified; section C records only what the listing page shows.

---

## C. Official source inventory

Access date for every observation below: **2026-11-01**. "Local file obtained?" refers to files under this repository; for all new sources below it is **No**. "Manifest reference" is **none** for all new sources because nothing was obtained.

| # | Source | Official URL | Access route | Account required | Rounds / years | File formats | Local file obtained? | Manifest reference | Evidence / status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | MoSPI PLFS publications listing | https://www.mospi.gov.in/download-reports/1000 | Public web listing (as intended) | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | No | none | **NOT_VERIFIED.** The page is client-rendered; the fetch returned only the site title "Ministry of Statistics and Program Implementation \| Government Of India" and no listing. A second listing URL cited by a search summary (`https://www.mospi.gov.in/download-reports?main_cat=ODU5&cat=All&sub_category=All`) gave the same empty result. |
| 2 | MoSPI FAQ | https://mospi.gov.in/faq | Public web page | NOT_VERIFIED | n/a | n/a | No | none | **NOT_VERIFIED.** Client-rendered; title only. A search result pointed to an FAQ PDF (`https://www.mospi.gov.in/sites/default/files/main_menu/FAQ/FAQ-CC05072023.pdf`), not opened: `SEARCH_LEAD_ONLY`. |
| 3 | MoSPI eSankhyiki | https://esankhyiki.mospi.gov.in/ | Public web portal | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | No | none | **NOT_VERIFIED.** Client-rendered; title only. A search for eSankhyiki PLFS products returned no eSankhyiki pages. Whether eSankhyiki offers PLFS state tables or an API is unestablished. |
| 4 | MoSPI home page | https://mospi.gov.in/ | Public web page | n/a | n/a | n/a | No | none | `NOT_ATTEMPTED` as a separate fetch; the three other `mospi.gov.in`-hosted pages above returned only the site shell. |
| 5 | PLFS Annual Report, July 2023 – June 2024 | `https://www.mospi.gov.in/sites/default/files/publication_reports/AnnualReport_PLFS2023-24L2.pdf` (as cited inside a MoSPI document, per search summary) | Public report download (PDF) | NOT_VERIFIED | July 2023 – June 2024 (named in a MoSPI Sarvekshana issue per search summary) | PDF | No | none | `SEARCH_LEAD_ONLY`. Not seen on an observed listing page; not opened. A MoSPI press note (`https://www.mospi.gov.in/sites/default/files/press_release/Press_note_AR_PLFS_2023_24_22092024.pdf`) also appeared in search. Karnataka tables inside the report: NOT_VERIFIED. |
| 6 | Press note on the PLFS Annual Report 2025 (**a press note, not the report**) | press note URL seen in search: `https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774607827733_3e8964a9-268b-4cc9-ad65-cfc8a9e32f08_Press_note_AR_PLFS_2025_23032025_V2.1_26032026_final.pdf` | Public press note (PDF) | NOT_VERIFIED | Calendar year 2025 | PDF | No | none | `SEARCH_LEAD_ONLY`. Not opened. This is the press note only. The report itself is row 6a. (Correction: the previous revision of this table treated this row as the annual report.) |
| 6a | **PLFS Annual Report 2025 (the report itself)** | `https://mospi.gov.in/uploads/publications_reports/publications_reports1780040415321_0624fb13-fb47-40bc-b470-7c7e9635c3ef_PLFS_2025_F_REV_29052026.pdf` | Public report download (PDF, per the URL path and extension) | NOT_VERIFIED | Calendar year 2025 (January–December 2025), as stated in the press-note text returned by search | PDF (per URL extension) | No | none | `SEARCH_LEAD_ONLY`. Identified through an official `mospi.gov.in` search-index result, as reported by the independent review. **Not downloaded, opened or directly inspected.** Not seen on an observed listing page. One search in this correction task did not return this URL, so it is reported, not independently reproduced here (the close-out search did not return it either). Official MoSPI search indexing is reported to identify the report and its detailed tables. Contents: section D, item 7. Methodology caveat: section D, item 8. Official release: row 6b. |
| 6b | PIB release: "Periodic Labour Force Survey (PLFS) Annual Report, 2025" | `https://www.pib.gov.in/PressReleasePage.aspx?PRID=2246009&lang=1&reg=1` | Public government press-release page (HTML) | NOT_VERIFIED | Report period January–December 2025 | HTML | No | none | `SEARCH_LEAD_ONLY`. A direct fetch returned **HTTP 403 Forbidden** in this environment (not bypassed), so the page was not directly inspected. A search in the close-out task returned a PIB page with the same release ID (`PRID=2246009`, query variant `reg=3`), titled "Periodic Labour Force Survey (PLFS) Annual Report, 2025 [January, 2025…" (title truncated in the result). A search-tool summary of it (not the page) says it points readers to the MoSPI website for detailed tables and carries the comparability caveat in section D, item 8. Release date **27 March 2026** is as supplied by the final independent review; not observed here. |
| 6c | PLFS "Changes in 2025" methodology notes | PIB: `https://www.pib.gov.in/PressReleasePage.aspx?PRID=2128662&reg=3&lang=2` ("Changes in Periodic Labour Force Survey (PLFS) from 2025"); MoSPI: `https://www.mospi.gov.in/sites/default/files/publication_reports/PLFS_Changes-in-2025_rev.pdf`; MoSPI press note: `https://www.mospi.gov.in/sites/default/files/press_release/Press_note_changes_sample_design_Final.pdf` | Public HTML (PIB) and PDF (MoSPI) | NOT_VERIFIED | From January 2025 | HTML, PDF | No | none | `SEARCH_LEAD_ONLY`. Returned by the close-out search as official-domain results; none opened. Listed as supporting leads for the caveat in section D, item 8. Contents not verified. |
| 7 | PLFS Quarterly Bulletins (state-level tables) | e.g. `https://www.mospi.gov.in/sites/default/files/publication_reports/QuarterlyBulletinPLFS_July_September_2024.pdf`; `https://www.mospi.gov.in/uploads/publications_reports/publications_reports1770719506668_061eb34b-ec61-4890-9e61-73cc717b4d0b_Quarterly_Bulletin_PLFS_OCT-DEC_2025.pdf` | Public bulletin download (PDF) | NOT_VERIFIED | Seen in search: Jan–Mar 2024, Jul–Sep 2024, Oct–Dec 2025 | PDF (a search summary also mentions linked Excel files; NOT_VERIFIED) | No | none | `SEARCH_LEAD_ONLY`. A search-tool summary says the Jul–Sep 2024 bulletin presents state-level tables that include Karnataka; **not verified by opening the file**. Whether any table breaks Karnataka down by occupation or industry: NOT_VERIFIED. |
| 7a | **Labour Market Snapshot of Selected Districts** (district-level PLFS publication) | PIB release: `https://www.pib.gov.in/PressReleasePage.aspx?PRID=2312001&lang=1&reg=48&v=sd`; MoSPI PDF returned by search: `https://www.mospi.gov.in/uploads/publications_reports/publications_reports1789723407069_3196eda8-6346-42ca-a271-bc24d443dcb6_Labour_Market_Snapshot_of_Selected_Districts-PLFS_2025.pdf` | Public press-release page (HTML) and report (PDF) | NOT_VERIFIED | PLFS 2025 (title of the MoSPI file) | HTML; PDF | No | none | `SEARCH_LEAD_ONLY`. The PIB page returned **HTTP 403 Forbidden** on a direct fetch (not bypassed) and the close-out search did not return that PIB URL; the MoSPI PDF title was returned by search and was not opened. Release date **18 September 2026** is as supplied by the final independent review; not observed here. Stated scope, as supplied by the review and consistent with a search-tool summary: district-level PLFS indicators (LFPR, WPR, unemployment, NEET), with Karnataka districts referenced; district results are said to use the revised PLFS methodology introduced in January 2025 (that sentence was not observed here; see D item 8). Suitability for qualification-specific occupational context is **unverified**. No numerical statistics from this publication are recorded in this document. |
| 8 | PLFS monthly bulletins | none found | n/a | n/a | n/a | n/a | No | none | `NOT_VERIFIED`. No monthly-bulletin page was located. Monthly **unit-level** data are listed in the microdata catalogue (row 10), which is a separate route. |
| 9 | National Microdata Portal (NADA), PLFS collection | https://microdata.gov.in/NADA/index.php/catalog/PLFS | Public catalogue; data via "Get Microdata" (login) | See row 11 | 14 datasets listed (see row 10) | Metadata exports DDI/XML and JSON observed; data-file format not stated on the pages read | No | none | `PAGE_OBSERVED`. Catalogue page lists 14 PLFS datasets with a "Public use data files" licence filter and a "Login" link. |
| 10 | PLFS dataset IDs listed in the catalogue | same catalogue page | same | same | Listed periods: Jul 2017–Jun 2018, Jul 2018–Jun 2019, Jul 2019–Jun 2020, Jul 2020–Jun 2021, Jul 2021–Jun 2022, CY2021, CY2022, Jul 2022–Jun 2023, CY2023, Jul 2023–Jun 2024, Jan–Dec 2024 (key indicators entry), CY2025 (Jan–Dec), monthly Apr–Dec 2025, quarterly Apr–Jun 2025 to Oct–Dec 2025 | not stated on catalogue listing | No | none | `PAGE_OBSERVED` (titles and IDs only, e.g. `DDI-IND-CSO-PLFS-2023-24`, `DDI-IND-NSO-PLFS-2024-24`, `DDI-IND-NSO-PLFS-Jan2025-Dec2025`). Listing of a dataset is **not** evidence that its data files can be obtained or are suitable. |
| 11 | Microdata access page, dataset 292 | https://microdata.gov.in/NADA/index.php/catalog/292/get-microdata | Free account, then login | **Yes (observed):** page states "To access data for this study, user must be logged in" and offers log in or register for a free account | Apr–Jun 2025 to Oct–Dec 2025 (quarterly unit-level) | not stated | No | none | `PAGE_OBSERVED` for the login requirement on this one dataset page. Whether an application form or data-access agreement applies: **NOT_VERIFIED** (a search-tool summary of MoSPI's download guide says so; the guide PDF was not opened). Same requirement for other datasets: assumed, not observed. |
| 12 | Microdata dataset 292 description | https://microdata.gov.in/NADA/index.php/catalog/292 | Public metadata page | Metadata page: no login observed | Apr–Jun 2025 to Oct–Dec 2025 | DDI/XML and JSON metadata | No | none | `PAGE_OBSERVED`. National coverage; the page does not name Karnataka. No licence text on this page; links to "Policies and Guidelines". |
| 13 | Microdata Policies and Guidelines (terms location only) | https://microdata.gov.in/NADA/index.php/dissemination | Public web page | n/a | n/a | n/a | No | none | Location recorded from the portal home page. **Not opened. Reserved for P2.2.** |
| 14 | Microdata download manual | https://microdata.gov.in/NADA/Guide_to_download_microdata.pdf | Public PDF | n/a | n/a | PDF | No | none | `LISTING_OBSERVED` (linked from the portal). Not opened. |
| 15 | Karnataka Economic Survey (DES listing) | https://des.karnataka.gov.in/48/economics-survey/en | Public web listing | No login observed | 13 editions: 2013-14 to 2025-26 (the 2021-22 row's link title reads "Economic Survey 2020-21", an apparent labelling error on the page) | PDF (inferred from `.pdf` link extensions; the page states no format label) | No | none | `LISTING_OBSERVED`. Contents of any edition (employment, occupation or industry tables, years, definitions): **NOT_VERIFIED**; no PDF opened. |
| 16 | Karnataka Economic Survey 2025-26 (DES "Latest News" link) | `https://des.karnataka.gov.in/uploads/Economic_Survey_2025-26_English_FinalMpdf_1772796504.pdf` | Public PDF | No login observed | 2025-26 | PDF | No | none | `LISTING_OBSERVED` on https://des.karnataka.gov.in/english. Not opened. |
| 17 | Karnataka DES English index | https://des.karnataka.gov.in/english | Public web page | No login observed | n/a | n/a | No | none | `PAGE_OBSERVED`. Lists Economics Survey, Other Publications, Economics Census, division report pages (ARC, AGS, CIS, CNL, PTC, SIP, "Karnataka At a Glance"). The page has no labour or employment section. |
| 18 | Karnataka DES, CNL division reports (NSS) | https://des.karnataka.gov.in/30/reports/en | Public web listing | No login observed | NSS rounds 64th (2007-08) to 73rd listed | not stated | No | none | `PAGE_OBSERVED`. No report titled PLFS, employment or labour force was seen. Subject of the "64th Round" and "73rd Round" entries is not shown. |
| 19 | Karnataka Planning, Programme Monitoring and Statistics Dept. Economic Survey Reports | https://planning.karnataka.gov.in/info-4/Reports/Economic+Survey+Reports/en | Public web listing | n/a | n/a | n/a | No | none | **NOT_VERIFIED.** Two fetches (https and http) failed with "unable to verify the first certificate" in this environment. A search result listed the page; contents not read. Not bypassed. |
| 20 | NCO-2015 (DGE page) | https://dge.gov.in/nco-2015 | Public web page with PDF links | No login observed | NCO-2015 | PDF: Vol I, Vol II-A, Vol II-B (6.79, 6.7, 6.32 MB; dated 17/05/2016 on the page) | Partial (historical): landing page saved as D1-src; the PDFs were **not** obtained | D1-src (page); D1 = `FAIL_HTTP` 404 for the Vol I URL tried on 2026-10-30 (the URL behind the page's current link was not inspected) | `PAGE_OBSERVED` and `LISTING_OBSERVED` for the three PDFs. The landing page text does not mention a concordance with NCO-2004 or ISCO (indexed PDF content is a separate lead: row 20a). Retrievability of the PDFs: `NOT_ATTEMPTED`. |
| 20a | NCO-2015 Vol I PDF (**indexed leads, not the landing page**) | (i) `https://dge.gov.in/dge/sites/default/files/2022-07/National_Classification_of_Occupations_Vol_I-2015.pdf` (supplied by the independent review); (ii) `https://dge.gov.in/dge/sites/default/files/2023-07/National_Classification_of_Occupations_Vol_I-2015.pdf` (returned by a search in this correction task, titled "NATIONAL CLASSIFICATION OF OCCUPATIONS-2015 (Code Structure) Vol-I") | Public PDF on `dge.gov.in` | NOT_VERIFIED | NCO-2015 | PDF | No | **(i) is character-for-character the URL of manifest row D1, which returned HTTP 404 on 2026-10-30 (`FAIL_HTTP`, no local file).** (ii) has no manifest row. | `SEARCH_LEAD_ONLY` for both. Per the independent review, the indexed content of (i) identifies a concordance between NCO-2015 and NCO-2004. A search-tool summary for (ii) describes a concordance table (pp. 33–238) and an alphabetical index (pp. 239–371); that was not verified against the file. Neither PDF was downloaded, opened or inspected, and my own search did not return (i). Three states are kept distinct: **(a)** landing page listing the volumes (`LISTING_OBSERVED`, row 20); **(b)** indexed PDF content describing a concordance (`SEARCH_LEAD_ONLY`, this row); **(c)** a file obtained and verified locally (none: no Vol I file exists locally). No FG-8 determination is made. |
| 20b | NCO-2015 Vol I PDF (**alternative DGE path, indexed lead**) | `https://www.dge.gov.in/sites/default/files/2024-05/National_Classification_of_Occupations_Vol_I-2015.pdf` (supplied by the final independent review) | Public PDF on `dge.gov.in` | NOT_VERIFIED | NCO-2015 | PDF | No | none. Manifest row D1 is unchanged: it still records the `2022-07` URL (row 20a (i)) and its historical HTTP 404. | `SEARCH_LEAD_ONLY`. Per the review, the indexed content identifies the NCO-2015/NCO-2004 concordance. Two close-out searches did **not** return this URL. They returned the `2023-07` Vol I path (row 20a (ii)) and a `2024-05` path for a different file, Vol II-A (`https://dge.gov.in/sites/default/files/2024-05/National_Classification_of_Occupations_Vol_II-A-2015.pdf`), which shows only that other NCO-2015 files sit in a `2024-05` folder, nothing about Vol I there. The host form also differs from row 20a (`www.dge.gov.in/sites/...` against `dge.gov.in/dge/sites/...`). Not downloaded, opened or inspected. **No local acquisition, no successful download and no completed concordance verification.** No FG-8 determination is made. |
| 21 | NCO online table search (DGE) | https://dge.gov.in/nat?page=N | Public web table | n/a (manifest D2-p5 records an HTTP 200 plain GET on 2026-10-30; no account used) | NCO table | HTML | Partial (historical): page 5 only | D2-p5 (saved), D2 (`NOT_FOUND`, summary) | `FILE_OBTAINED_LOCAL` for page 5 only (hash-verified, section B.4). Whether the current online table is complete: `NOT_VERIFIED`. |

---

## D. Public-source-first findings

These are leads for further investigation, **not** findings about suitability.

1. **Published PLFS reports and bulletins (MoSPI).** Search leads indicate that annual reports (July 2023 – June 2024; calendar-year 2025) and quarterly bulletins exist and that at least one quarterly bulletin reports state-level tables that include Karnataka. None of this is confirmed on an observed official listing, because the MoSPI listing pages are client-rendered and returned no content to the fetch tool. **What would resolve it:** a user opening the MoSPI listing in a browser, or an approved retrieval of one report, followed by a read of its table index. That would need user approval because it is a download.
2. **Occupation-by-state breakdowns are unestablished.** Nothing observed shows whether any published PLFS table cross-tabulates Karnataka with NCO occupation or industry. Reports that mention NCO divisions at the all-India level cannot be assumed to give Karnataka-by-occupation tables, and that is not assumed here. Status: `NOT_VERIFIED`. See item 7 for table descriptions reported by the independent review.
3. **Karnataka Directorate of Economics and Statistics.** The official site lists 13 Economic Survey editions (2013-14 to 2025-26, PDF). No labour or employment section and no PLFS-titled report was seen on the pages read; the CNL division lists NSS rounds only up to the 73rd. Whether the Economic Survey carries usable employment or occupation tables is `NOT_VERIFIED`. It is more likely a sector-context source (as `ARCHITECTURE.md` §14.1 anticipates), but that is not confirmed.
4. **Planning department site.** Could not be read because of a TLS certificate verification failure in this environment. Treated as inaccessible, not as empty.
5. **eSankhyiki.** Not verifiable with the available fetch method. It remains a candidate public-data route to check in a browser.
6. **NCO-2015.** DGE lists Vol I, Vol II-A and Vol II-B as PDFs. Locally we hold only the landing page and one page of the online table. Indexed PDF content that reportedly describes an NCO-2015 to NCO-2004 concordance is a `SEARCH_LEAD_ONLY` (rows 20a and 20b; the page listing the volumes is row 20). Whether the full hierarchy or the concordance is obtainable, and whether either is adequate, is a separate question for the FG-8 work in P2.3, which is out of scope here.
7. **PLFS 2025 annual report: table descriptions reported by the independent review (bounded note).** The review identified the descriptions below from the **indexed contents** of the official 2025 annual report (row 6a). The evidence is that indexed content only; the PDF was **not** downloaded, opened or inspected here, and my own searches in the correction and close-out tasks did not return the report or its table list. They are therefore reported, not reproduced, and table numbers or titles may differ in the final PDF. A search summary of the *2017-18* annual report describes its own Table 25 as a distribution of workers by occupation group, sub-division and division; table numbering and scope differ between reports.

   | Table(s) | Description as reported | Level of the description | What it does and does not establish |
   |---|---|---|---|
   | 22–24 | State/UT LFPR, WPR and unemployment rates by education | **State/UT-level**; education dimension; no occupation dimension described | A Karnataka row is expected in a State/UT table but is not verified. Education breakdown of headline indicators only. |
   | 25 | Worker distribution by NCO-2015 occupation group, sub-division and division | **Occupation-level**; the title gives no State/UT dimension, so it is treated as occupation-level context of unestablished geography (possibly national) | **The title does not establish a Karnataka-by-occupation cross-tabulation, and none is claimed.** Not to be read as Karnataka-specific. |
   | 27 | Industry distribution by NIC-2008 sections for each State/UT | **State/UT-level**; industry dimension | Potentially useful state-level **industry** context. Not an occupation table. A Karnataka row is not verified. |
   | 38 | Regular wage/salary earnings for regular wage/salaried employees in CWS, for each State/UT | **State/UT-level**; earnings; activity-status basis CWS as described | State-level earnings. Whether it is broken down further, and whether the CWS basis fits the project's needs, are unknown. |

   Whether any of these tables meets the project's requirements is **unverified**. The report is **not** described here as sufficient for Module A. No FG-3, FG-4, FG-5, FG-6, FG-7 or FG-8 determination is made, and nothing here assesses reuse terms (P2.2).
8. **PLFS 2025 methodology change: comparability caveat.** The official PIB release on the 2025 annual report (row 6b; the page itself returned HTTP 403, so this is taken from a search-tool summary of it and is a paraphrase, not a quotation) is reported to say that the PLFS sampling methodology was revamped from January 2025, and that the annual 2025 estimates may not be strictly comparable with previous PLFS annual reports, or with calendar-year 2022–2024 results from unit-level data. In brief, the change concerns the **sampling design and estimation methodology**. A search-tool summary of the "Changes in 2025" notes (row 6c, not opened) adds that the survey period moved from a July–June cycle to a January–December calendar year and that users comparing against estimates published up to December 2024 should account for the changes. This is a **documented methodological caveat to carry into any future FG-6 (comparability) assessment, not an FG-6 decision**: it does not say comparison is impossible, and no determination is made here. The district publication (row 7a) is stated by the review to use the same revised methodology (not observed here).

**Overall:** at this point in P2.1, published tables are worth pursuing first, but their Karnataka usefulness cannot be stated from what has been observed. The unit-level microdata catalogue is the only Module A candidate whose listing and login requirement were directly observed.

---

## E. Deferred microdata route

- **Official portal:** National Microdata Portal, https://microdata.gov.in/ (NADA catalogue), operated by the National Statistics Office, MoSPI (as stated on the portal home page).
- **Catalogue observed:** 14 PLFS datasets (section C, rows 9–10).
- **Access route observed:** dataset page -> "Get Microdata" page -> the page states a logged-in user is required and offers registration for a free account (observed on dataset 292 only).
- **Not verified:** whether an application and data-access agreement are required; data-file formats; licence wording. The download manual and the Policies and Guidelines page (https://microdata.gov.in/NADA/index.php/dissemination) were **not opened**.
- **Status of this route:**
  - **Registration has not been attempted. No account was created and no login was made.**
  - **No microdata or other data file has been downloaded.**
  - **Q-6 remains open** (`ARCHITECTURE.md` §20.2): whether to register for PLFS microdata access, and for which rounds.
  - **Round selection is pending user decision.** Registration is a user action (`TASKS.md` P2.1) and is `PENDING_USER_ACTION`.
- Any eventual download needs the user's approval and a new run folder with a manifest (`TASKS.md` Phase 2 header; `ARCHITECTURE.md` §7, §19).

---

## F. Outstanding questions

| ID | Question / gap | Owner / status |
|---|---|---|
| Q-6 | Which PLFS microdata rounds, if any, should be pursued; register at all? | User decision; open |
| Q-8 | Competition deadline and demonstration / publication format (live, recorded, slides)? | User decision; open; affects whether the Phase 2 time-box is worth extending |
| F-1 | MoSPI pages (`download-reports/1000`, `faq`, home, eSankhyiki) are client-rendered and returned no content; PLFS report listings and eSankhyiki PLFS products are unverified. | Needs a browser view by the user, or approved alternative |
| F-2 | `planning.karnataka.gov.in` could not be read (TLS certificate verification error in this environment). | Unresolved |
| F-3 | Whether any published PLFS table gives Karnataka by NCO occupation or NIC industry. | `NOT_VERIFIED` |
| F-4 | Whether the Karnataka Economic Survey editions contain employment, occupation or industry tables, and for which years. | `NOT_VERIFIED` |
| F-5 | Whether the NCO-2015 Vol I / II PDFs listed by DGE are retrievable (the earlier Vol I URL returned 404; the URL supplied by the review, row 20a (i), is that same URL; rows 20a (ii) and 20b are other indexed paths). | `NOT_ATTEMPTED` |
| F-9 | The PIB pages (rows 6b, 7a) returned HTTP 403 to direct fetch. Release dates (27 March 2026; 18 September 2026) and the district publication's methodology statement are as supplied by the review and not observed. | Unresolved; not bypassed |
| F-10 | The 2025 methodology change (section D, item 8) is a caveat for future FG-6 work. Which rounds are comparable, and whether any concordance or bridging guidance exists, is unassessed. | Reserved for P2.3 |
| F-11 | Suitability of the district-level publication (row 7a) and of PLFS 2025 Tables 22–38 (section D, item 7) for qualification-specific occupational context. | `NOT_VERIFIED` |
| F-12 | Whether any PLFS 2025 table (Table 25 in particular) has a State/UT dimension. | `NOT_VERIFIED` |
| F-6 | Whether the microdata route needs an application and agreement beyond free registration. | `NOT_VERIFIED` |
| F-7 | Whether browsing public pages without saving them needs approval (`TASKS.md` says only "any download"). Treated as permitted in this task. | Reviewer to confirm |
| F-8 | The brief's "17 of 20" and "nine PDFs" figures do not match the manifest (section B.1). | Noted; not reconciled |
| T-1 | **Terms and rights** for MoSPI/NSO publications, the microdata portal, Karnataka DES publications and NCO-2015. | (run 2) **Reviewed in section H.** Result: no source is `PERMITTED`; Karnataka DES and DGE content are `RESTRICTED`; MoSPI publications and PLFS microdata are `UNCLEAR`. FG-2 is `FAIL` under the TASKS P2.2 rule. |

---

## G. Next steps

1. **Acceptance review of this inventory** (P2.1) by the user or an independent reviewer, including section B's integrity findings and the unverified items in section F. This document does not mark P2.1 accepted or DONE.
2. **User decisions Q-6 and Q-8**, which determine whether any registration or download is pursued and how much time Phase 2 should take.
3. **If the user approves,** a bounded follow-up under P2.1: browser-assisted confirmation of the MoSPI PLFS report listing and eSankhyiki, and approval for retrieving one report, so that the Karnataka table question (F-3) can be answered. This would be new acquisition and needs a new manifest under the 2026-10-30 discipline.
4. **Then P2.2** (terms review) for whichever sources survive. (run 2) P2.2 was performed on 2026-11-01; see section H.

(Historical wording of the first revision: "P2.3–P2.6 and the gate record are untouched. The gate remains `NOT_ASSESSED`.") **(run 2)** That sentence described the state when sections A–G were written. P2.3 (`docs/feasibility/module_a_variables.md`) and the gate record (`docs/decisions/MODULE_A_GATE.md`) were produced in run 2; P2.4 was not executed; P2.6 is deferred. **No labour-market statistic appears in this document.**

---

## H. Terms and reuse review (P2.2) — added 2026-11-01, run 2

**Status:** review performed; **subject to user acceptance; P2.2 is not marked DONE here.** No data were obtained. No account was created and nothing was submitted.

### H.1 Method and limits

- Public pages and public policy documents were read through a page-fetch tool on 2026-11-01. Quotes below are verbatim from what that tool returned, or (where stated) from a rendered image of the document.
- **Side effect to disclose:** for PDF URLs, the fetch tool wrote a copy of each PDF it was given into the Claude Code tool-results cache folder under the user profile (`C:\Users\aksha\.claude\projects\...\tool-results\`), **outside the repository**. Four PDFs are affected: the NSS-report policy memorandum, the microdata OM, the microdata download manual and the GSDD. They are policy and guidance documents, not datasets. Nothing was written under the repository's `data/`. The JPEG images embedded in those PDFs were extracted with a standard-library script into the session scratchpad so that the scanned pages could be read; no tool was installed.
- Where a page is client-rendered, a PDF could not be read, or a page returned HTTP 403, that is recorded and the source is **not** given the benefit of the doubt.
- Classification rule (task brief): `PERMITTED`, `RESTRICTED` or `UNCLEAR`. Nothing was inferred from government ownership, public accessibility, search-result descriptions, or technical downloadability. `TASKS.md` P2.2: **`UNCLEAR` means FG-2 is `FAIL` until clarified.**

### H.2 Terms documents located and what was established

| ID | Document | URL | Read? | Result |
|---|---|---|---|---|
| T-A | Microdata portal "Policies and Guidelines" page | https://microdata.gov.in/NADA/index.php/dissemination | Yes (page) | Lists four linked policy documents (T-B to T-E) and a disclaimer. Contains **no** licence or terms-of-use text itself. |
| T-B | Policy Guidelines for using materials from published NSS reports (OM No. P-12011/1/2017-NSSO (CPD), 22 Sept 2017) | https://mospi.gov.in/sites/default/files/main_menu/data_discremination/policy_nss_pub_25se17.pdf | **Yes, rendered image** (the PDF is a scan; text extraction impossible, read visually; page 2 is a blank annexure form) | Quoted in H.3. |
| T-C | OM "Online Microdata Dissemination of Census/ Surveys conducted by MoSPI" (F.No.O-11015/18/2015-ASI, 22.03.2019) | https://mospi.gov.in/sites/default/files/data_disemination/OM%20_to_disseminate_data%20free_.pdf | **Yes, rendered image** (one page) | Quoted in H.3. It states a policy intent and audience only; it contains **no** conditions of use. |
| T-D | Revised Guidelines for Statistical Data Dissemination (GSDD) | http://mospi.gov.in/uploads/acts_and_policies/acts_and_policies1778231030122_a1a3ee77-e36d-4895-8da5-b294751cbb1a_272304_(1).pdf (URL as reported by the portal page) | **No: not readable.** The fetch returned compressed PDF content; the text uses a custom font encoding that the available tools could not decode. | **Content unknown.** Whether it states conditions for unit-level data, publication of results or attribution is **not established**. |
| T-E | National Policy on Dissemination of Statistical Data (6 Jan 1999) | https://mospi.gov.in/sites/default/files/main_menu/data_discremination/national_policy_data_dissemination_6jan1999.pdf | **No (not attempted)** | Content unknown. |
| T-F | Microdata download manual | https://microdata.gov.in/NADA/Guide_to_download_microdata.pdf | **Fetched but not read:** the fetch returned compressed content, and ten embedded page images were extracted but **not viewed** (time-box). | Content unknown. Registration steps and any agreement or undertaking: **not established**. |
| T-G | Microdata portal disclaimer (footer modal) | on https://microdata.gov.in/NADA/index.php/dissemination and dataset pages | Partly: only fragments were returned | Liability disclaimer only. See H.3. |
| T-H | MoSPI website terms (`https://www.mospi.gov.in/terms-conditions`) | — | **No: client-rendered.** The fetch returned only the page title. | Content unknown. Also not established: whether that URL exists. |
| T-I | Karnataka DES site policies (on https://des.karnataka.gov.in/english) | https://des.karnataka.gov.in/english | Yes (page sections) | Quoted in H.3. |
| T-J | DGE site policies | https://dge.gov.in/website-policy and https://dge.gov.in/terms-conditions | Yes | Quoted in H.3. |
| T-K | Government Open Data Licence – India (GODL), referenced by NDSAP | https://data.gov.in/sites/default/files/Gazette_Notification_OGDL.pdf | **No: HTTP 403 Forbidden** (not bypassed) | The licence text was **not observed**. Search-engine descriptions of it are secondary and are not relied on. Nothing observed says that any MoSPI, DES or DGE source in this inventory is published under GODL. |
| T-L | PIB release pages (rows 6b, 7a) | see section C | **No: HTTP 403** (P2.1) | Content unknown. |
| T-M | Karnataka Planning Dept. site | https://planning.karnataka.gov.in/ | **No: TLS certificate error** (P2.1) | Content unknown. |

### H.3 Quoted clauses

**T-A / T-G, microdata portal (disclaimer fragments as returned by the fetch tool; the full disclaimer modal was not seen):**
- "disclaims any liability or responsibility arising from the use of the Microdata Portal"
- "shall not be liable for any financial or other consequences whatsoever arising from the use of the content of the portal"

The dataset 292 description page (https://microdata.gov.in/NADA/index.php/catalog/292) carries **no licence text**, no citation requirement and no access policy, and only links to "Policies and Guidelines", "Get Microdata" and the "Download Manual". The dataset 284 and 213 description pages were likewise reported to carry no access policy or licence text. (P2.1 row 9 noted a "Public use data files" licence **filter** on the catalogue listing; the licence **text** behind that label was not seen.)

**T-C, MoSPI Office Memorandum, 22.03.2019 (read from the rendered page):**
> "Official statistics are key inputs for decision making and policy interventions and become public assets for conducting research both in public and private spheres. Recognizing the requirement and potential of data, Ministry of Statistics & Programme Implementation (MoSPI), Government of India has decided to provide free of cost, single point access and support of Microdata of Census and Surveys conducted by the Ministry to Students/ Researchers/ Institutes in India and abroad through National repository from 1st April, 2019."

What this does and does not say: it states an intent to give free access to *students, researchers and institutes*. It states **no** terms on aggregate analysis, display, publication, attribution or redistribution. Whether a competition team qualifies as one of those audiences is not stated.

**T-B, NSS-report policy memorandum, 22 September 2017 (read from the rendered scan; wording transcribed by reading):**
> "2. The publishers desirous of making use of the excerpts from the NSS survey reports should send a request in the prescribed format (Annexure I) to the Additional Director General, Coordination and Publication Division, National Sample Survey Office, Ministry of Statistics and P. I., Sankhyiki Bhavan, 'C' Block, 1st floor, Maharshi Valmiki Marg, Delhi–110032."
> "4. However, no permission will be required for use of any data from a published NSS report."
> "5. The publishers receiving an affirmative response regarding using the excerpts from the published NSS surveys reports from the CPD has to duly acknowledge the source materials in favour of NSSO, Ministry of Statistics & P. I., Government of India. Further a copy of the proposed publication in which the excerpts from NSS reports have been used, shall be provided free of charge to the Additional Director General, Coordination and Publication Division, National Sample Survey Office, …"
> "6. Any contravention by the user agency, if brought to the notice of the Ministry however, shall be dealt in terms of the Copyright Act, 1957."

What this does and does not say: it concerns *excerpts* from published NSS survey reports used by *publishers* (books, journals); paragraph 4 says no permission is needed for use of *data* from a published NSS report; paragraph 5 requires acknowledgement when excerpts are used. **It does not say whether PLFS reports, bulletins or press notes are "NSS reports" within its meaning**, and it is dated 2017. Annexure I is a blank request form for book publishers.

**T-I, Karnataka DES site (https://des.karnataka.gov.in/english, as returned by the fetch tool):**
> "Information featured on this website can be re-published in any media form free of any charge only with prior permission"
> "The information published on the website comes under copyright policy and obtaining authorization for their republish is a pre-requisite."
> "Under no circumstances will this Department be liable for any expense, loss or damage"

Hyperlinking: "We do not object to you linking directly to the information that is hosted on our site and no prior permission is required for the same." The page gives a hyperlinking-permission contact for departments that require permission.

**T-J, DGE website policy (https://dge.gov.in/website-policy), Copyright Policy:**
> "Contents of this website may not be reproduced partially or fully, without due permission" … "from the Directorate General of Employment."
> If content is referred to or forms part of another website, "the content-source must be appropriately acknowledged."
> "The contents of this website cannot be used in any misleading or objectionable context."

DGE terms page (https://dge.gov.in/terms-conditions): "Website Content Managed by DGE, Ministry of Labour & Employment, GoI"; "Material provided on the website is provided "as is", without warranty of any kind, either express or implied." No copyright or reuse clause was returned for that page. The NCO-2015 landing page itself (https://dge.gov.in/nco-2015) carries no copyright, licence or disclaimer text and links to the two policy pages above.

### H.4 Per-source classification

The seven questions are: **(1)** applicable terms; **(2)** terms accessible; **(3)** aggregate analysis permitted; **(4)** aggregates displayable in a competition demo; **(5)** results publishable; **(6)** attribution required; **(7)** restrictions on redistribution or derived outputs.

| # | Source (section C rows) | (1) Applicable terms identified | (2) Accessible | (3) Aggregate analysis | (4) Competition display | (5) Publication | (6) Attribution | (7) Redistribution / derived restrictions | **Class** |
|---|---|---|---|---|---|---|---|---|---|
| S1 | **PLFS unit-level microdata** (NADA; rows 9–14) | Intent only (T-C). Licence or conditions text for the microdata: not found on dataset pages; manual (T-F) and GSDD (T-D) not read | **Partly**: T-C and portal disclaimer only | Not stated | Not stated | Not stated | Not stated | Not stated (nothing on redistribution of microdata or of derived tables) | **UNCLEAR** |
| S2 | **MoSPI/NSO published PLFS reports, bulletins, press notes** (rows 5–7a) | Possibly T-B (2017 NSS-report OM), whose applicability to PLFS publications is **not established**; MoSPI site terms (T-H) not readable | **Partly** | Not stated | If T-B applies: para 4, "no permission will be required for use of any data from a published NSS report" | If T-B applies: excerpts need a request (para 2); data use does not (para 4) | If T-B applies: acknowledge NSSO, MoSPI (para 5) | If T-B applies: Copyright Act 1957 (para 6); otherwise unknown | **UNCLEAR** |
| S3 | **Karnataka Economic Survey / DES publications** (rows 15–18) | T-I | **Yes** (site policy) | Not addressed | Republication "in any media form … only with prior permission" | Same clause | Not stated | "obtaining authorization for their republish is a pre-requisite" | **RESTRICTED** (permission required; none sought) |
| S4 | **NCO-2015 (DGE site content and online table; PDFs)** (rows 20–21) | T-J for the website. Separate terms inside the PDF volumes: not read | **Yes** for the site policy | Not addressed | "may not be reproduced partially or fully, without due permission" | Same clause | Yes: "content-source must be appropriately acknowledged" | Same permission clause | **RESTRICTED** (permission required; none sought) |
| S5 | **PIB release pages** (rows 6b, 7a) | None observed (403) | No | Unknown | Unknown | Unknown | Unknown | Unknown | **UNCLEAR** |
| S6 | **eSankhyiki and the MoSPI portal pages** (rows 1–4) | None observed (client-rendered) | No | Unknown | Unknown | Unknown | Unknown | Unknown | **UNCLEAR** |
| S7 | **Karnataka Planning Dept. reports** (row 19) | None observed (TLS error) | No | Unknown | Unknown | Unknown | Unknown | Unknown | **UNCLEAR** |
| S8 | **GODL / data.gov.in as a licence route** (T-K) | Licence text not observed (403). Nothing observed ties any source above to it | No | Unknown | Unknown | Unknown | Unknown | Unknown | **UNCLEAR** (a possible licence, not a source; no applicability evidence) |

**No source is `PERMITTED`.** `RESTRICTED` here means *permission is required and has not been obtained*, not that reuse is forbidden. Neither DGE nor Karnataka DES was contacted.

**Side observation, outside P2.2 scope (Module B).** Module B's curated build uses NCO codes and titles taken from a DGE online table page (D2-p5, source of the `VERIFIED_IN_SOURCE` NCO titles). The DGE copyright clause above is potentially relevant to that use. This is **not** assessed or changed here; `TASKS.md` already lists "unconfirmed licences" among the known limitations and Phase 6 includes a licence check.

### H.5 Consequence for FG-2

Per `TASKS.md` P2.2: "`UNCLEAR` means FG-2 is `FAIL` until clarified." The primary Module A route (S1, microdata) and the published-report route (S2) are both `UNCLEAR`, and S3/S4 are `RESTRICTED` without permission. **FG-2 is therefore `FAIL` under the documented rule.** This is a rule-driven result about evidence not established, **not** a finding that reuse is prohibited. See `docs/decisions/MODULE_A_GATE.md`.

### H.6 What would change this

1. A person reading the microdata Policies and Guidelines documents (T-D, T-E) and the download manual (T-F) in a PDF reader, and quoting the conditions on unit-level data, aggregate publication and attribution.
2. Written confirmation from MoSPI (the portal "Contact Us" page lists a contact route) of whether competition display of aggregates derived from PLFS microdata or from published PLFS tables is allowed, and whether T-B applies to PLFS reports.
3. Written permission from Karnataka DES and from DGE if their content is to be republished or displayed.
4. Reading the GODL text on data.gov.in in a browser, and evidence that a specific source is released under it.
5. Reading the MoSPI website terms, PIB terms and the Planning Dept. page in a browser.
