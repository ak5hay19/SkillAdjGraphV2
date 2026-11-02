# Running the SkillPath India demo (prototype, not the API_SPEC contract)

From the repository root, in PowerShell (project interpreter only):

```powershell
.\.venv\Scripts\python.exe -m uvicorn skillgraph.api.demo_app:create_app --factory --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>. The server reads the newest curated build of the current code version (`data/curated/`, read-only)
and refuses to serve (HTTP 503, an explicit "Data not available" screen) unless that build's validation state is `PASSED`.

Tests: `tests/golden/test_demo_journey.py` covers the API journey (pytest).

Browser check (needs Playwright and Google Chrome; Playwright is NOT a project dependency and was run from the global Python,
with the server above already running). It drives input -> results -> detail, validation, the empty state, no-age, the 390 px
layout, network/503 error states and a 1920 px view, and rewrites the screenshots:

```powershell
$env:PYTHONIOENCODING = "utf-8"; python docs/demo/browser_check.py docs/demo/screenshots
```

Screenshots of the verified version are in `docs/demo/screenshots/` (`02_results`, `03_detail`, `06_empty_under18`,
`08_mobile_results`, `09_mobile_detail`, `11_1920` are the useful ones). They contain only hypothetical profiles and
official-source titles; no labour-market figure appears.

## What a judge sees first

The page opens with a pre-filled example (the "Sewing helper" sample: garment work, Grade 10, 2 years, age 30) and a
"How it works" strip (hypothetical profile -> documented entry-rule evaluation -> evidence-backed results; it folds away once
results appear and can be reopened). Press **Show my options**. Every "Can't be determined" card lists the reasons the API
returned (its own messages and codes, grouped, with the number of requirement parts each affects); nothing is hidden or shown
as a match. Only the front end was changed for this: no verdict, rule, data or policy.

## Opening statement (say this first)

> SkillPath evaluates four garment-sector qualifications against official AMHSSC entry rules and documented training hours.
> It shows supporting evidence and preserves uncertainty instead of guessing. The other 33 qualifications are catalogue-only
> and have not been evaluated, because their qualification-level evidence has not yet been acquired and curated. Cross-sector
> transitions are a future expansion goal requiring additional official sources, review, and approval.

Every profile is hypothetical. The rules are applied by fixed code, not by an AI model. Nothing here predicts jobs, placement or
earnings.

## Talk track (about 5 minutes; hypothetical profiles only)

Checked against the current code and the validated build `cb-601c0399c999` on 2026-11-02 by calling `/demo/explore` in-process.
Re-check after any data rebuild: the verdicts below are the engine's output for these inputs, not fixed facts.

1. **Orient (30 s).** Point at the status chips (build id, `Validation: PASSED`, "Labour-market module: deferred (NO_GO)",
   "Prototype - not the final API"), the "Not a prediction" banner, and the footer: "4 evaluated qualifications + 33
   catalogue-only entries (not evaluated)". The inputs are: current qualification or job, education, years in the job, age
   (optional), and NSQF level comparison (default "Not set").
2. **A verified `MET` (90 s).** Keep the pre-filled **Sewing helper** (garment work, Grade 10, 2 years, age 30) and press
   **Show my options**. Sewing Machine Operator (`AMH/Q0301`) shows "Entry rules met" and "Official training hours: 300 h".
   Open "See evidence and requirements":
   - the minimum-age rule (18) is met by age 30 (SMO qualification file, page 4, item 9c age line);
   - the deciding entry row is "Grade 9 || No Experience required", met by Grade 10 (qualification file, page 3);
   - the hours table reads theory 90, practical 210, on-the-job 0 and 0, total 300: the full qualification's official
     notional hours. The page says no reduction for prior knowledge is claimed.
   - Disclose: Grade 10 satisfies "Grade 9" because a school-grade requirement is read as "at least" (decision Q-9, adopted
     by default, reversible).
3. **A `CONDITIONAL` (30 s).** Same screen: Inline Checker - Sewing (`AMH/Q0103`, 420 h) is "Conditionally met": "Holds only
   if your 2 years of experience are relevant (your declaration; not verified)." The system does not decide relevance for you.
4. **An `UNKNOWN` (60 s).** Same screen: Specialized Sewing Machine Operator (`AMH/Q2301`, 420 h) is "Can't be determined"
   and lists why, with codes: an uncertain extraction not yet substantiated, diploma-year routes not modelled, and a value that
   exists only as an unapproved overlay proposal. Production Supervisor - Sewing (`AMH/Q2101`, 570 h, under "Other options
   considered") is also undecided: the entry rule allows an "equivalent" and no equivalence rule is defined. The point: when
   the evidence cannot settle a rule, the result stays undecided; it is never rounded up to yes or down to no.
   Optional second `UNKNOWN`: clear the age field and press the button; the callout "Age not stated" appears and no option
   can be shown as met.
5. **A `NOT_MET` (45 s).** Press the **Under 18** sample (garment work, Grade 10, 1 year, age 17). The heading becomes "No
   option is open from these answers" and "Not open from your answers" lists all four as "Not met", each with its reasons
   (for example "Age: 18 years - not met"; Production Supervisor requires 20).
6. **Evaluated versus catalogue-only (45 s).** Only the four pilot qualifications appear in the "I hold a qualification" list
   and in results. The other 33 exist as catalogue rows only: a code, title, NSQF level and total hours, with no qualification
   file, entry rules, skill units or minimum age. They are shown as a count, not as results, and the API refuses to evaluate
   one (`TARGET_NOT_EVALUABLE`). Their catalogue hours and levels are display values, not evaluated facts.
7. **Routes and claims (30 s).** In a detail screen the "Multi-step routes" section says "Route recommendations are not
   available in this prototype". No verified rule says which sequences are meaningful, so none are shown. "What the
   qualification file says about progression" quotes the file's own text only (for SSMO: "Sampling Coordinator(Vertical)").
   That text is not a link: the system does not evaluate that target or say anyone can move to it.
8. **Optional: held qualification (30 s).** **Holds Operator cert.** (holds SMO, Grade 10, 3 years, age 30): SMO is not offered
   again; Inline Checker and Specialized Operator are "Conditionally met" (same relevance declaration), Production Supervisor
   is undecided. Say these results are **provisional**: how a held qualification's level is used (Q-B) and the relevance rule
   are not decided.
9. **Close (30 s):** limitations and evidence gates below.

## The LLM judge (separate, advisory; not part of the demo)

Mention only if asked or if time allows. The web demo and API do not use it.

- It is an offline checker (`src/skillgraph/judge/`, `docs/judge/README.md`). It reviews one candidate explanation text against
  one engine result and its evidence, and reports `PASS`, `FAIL` or `REVIEW_REQUIRED` per dimension (evidence faithfulness,
  verdict consistency, uncertainty handling, completeness, unsupported claims).
- It **does not decide eligibility**. The engine verdict is copied in and cannot be changed; its output has no field for a
  verdict, edge, path or approval, and a reply that contains one is rejected. Nothing in the engine imports it.
- State of evidence: its only evaluation set is a 19-case synthetic set written by the engineer, run with a scripted mock judge. That
  checks the pipeline, not model quality. No live model run has been made, no human-labelled set exists, and **no accuracy
  figure exists or may be quoted**. A live run sends data to a third party and needs three explicit opt-ins.

## Limitations and evidence gates (say these plainly)

Current limitations:

- Four qualifications from one sector body (AMHSSC, garment sector). No other sector's data is in the project.
- Many results stay `UNKNOWN` or `CONDITIONAL` by design: open evidence items include the unapproved overlays (Q-2), the
  uncertain cells, and two unresolved source conflicts on the SSMO record (DQ-01 credits, DQ-02 level), plus one unobtainable
  record that could not be compared (DQ-03).
- NSQF-level comparison has no default reading; "Not set" leaves level-based rules undecided (Q-B is provisional).
- Enrolment availability and application deadlines are not verified (no listing data). Labour-market context (Module A) is NO_GO.
- No skill-equivalence, exemption or reduced-hours claim is made. Documented skill-unit overlap between the pilot
  qualifications is thin and generic.
- Source-reuse rights for AMHSSC, NQR and DGE documents are unconfirmed; the data stays local and the repository private.

Gates before any cross-sector expansion (none is satisfied today):

1. A decision to expand (register item Q-7) and approval of a new, documented acquisition (robots.txt and throttle discipline,
   fresh manifest).
2. Source-reuse rights confirmed for anything shown publicly.
3. Official qualification and qualification-file documents for the new sector(s), which the project does not hold.
4. Extraction, audit and curated build for those records, with validation passing.
5. An official source for any cross-sector relationship. A name match or shared occupational classification is only an
   inference, and inference never makes a step feasible.
6. Review of any name-matched link (open items Q-D, Q-E) and a decision on the level-comparison policy.

## Presenter FAQ

**Why are only four qualifications evaluated?** The pilot was built from the qualification files the project actually
acquired and audited: Sewing Machine Operator, Specialized Sewing Machine Operator, Inline Checker - Sewing and Production
Supervisor - Sewing. Each needed its entry rules structured and checked against the source, which is slow and evidence-bound.

**Why are the other 33 not evaluated?** They are in the AMHSSC catalogue, but their qualification files have not been acquired
or curated, so there are no entry rules, skill units or minimum ages to evaluate. Adding them needs approval and a new
acquisition. Showing them as results would be guessing.

**Can the system recommend verified cross-sector routes today?** No. All four evaluated qualifications are in the same sector,
and no cross-sector data or official cross-sector relationship is in the project. The screen shows no multi-step routes at
all. Cross-sector transitions are a future goal that needs the gates above.

**Does the LLM judge decide eligibility?** No. Eligibility comes from fixed rules applied to documented entry requirements. The
judge is an optional offline reviewer of explanation text; it cannot change a verdict, and it has not been run against a live
model.

**What evidence is needed to expand responsibly?** Approved acquisition of official qualification files for the new sector,
confirmed reuse rights, extraction and audit with a passing validation, an official source for each cross-sector
relationship, and review of any name-matched or inferred link before it is shown.

## What is real, what is not

- Real: verdicts, rule rows, hours, skill units, sources and pages come from the validated curated build through
  `eligibility.evaluate`. The API response also carries a `routes` field built with `graph.enumerate_paths`, but the screen
  deliberately does not display it.
- Ordering: verdict class, then official hours (ARCHITECTURE section 13.2 default, partial; P3.7 not built). No difficulty labels.
- Not verified, shown as such: enrolment availability, deadlines (no listing data exists).
- Not used: any labour-market statistic (Module A is NO_GO). Not a prediction of jobs, placement or earnings.
- Age is an optional extra input: every qualification has a minimum age, so without it no option can be MET.
- Not supported: cross-sector transitions, evaluation of any catalogue-only qualification, multi-step route recommendations,
  skill equivalence, reduced training hours.
