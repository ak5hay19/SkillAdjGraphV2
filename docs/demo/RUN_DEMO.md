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

## Reliable demo script (hypothetical profiles only)

1. **Sewing helper** (sample button): garment work, Grade 10, 2 years, age 30 -> Operator (SMO) *Entry rules met*,
   Inline Checker *Conditionally met* (holds only if the 2 years are relevant), Specialized Operator *Can't be determined*
   (uncertain extraction / unapproved overlay). Open "See evidence and requirements": every rule row shows its verdict, your answer
   used, and the source document, page and location.
2. **Holds Operator cert.**: shows the held qualification is not offered again and later steps depend on declared relevance.
3. **Under 18**: no option is open; each blocked qualification shows which rule is not met.

## What is real, what is not

- Real: verdicts, rule rows, hours, skill units, sources/pages come from the validated curated build through
  `eligibility.evaluate` and `graph.enumerate_paths`.
- Ordering: verdict class, then official hours (ARCHITECTURE section 13.2 default, partial; P3.7 not built). No difficulty labels.
- Not verified, shown as such: enrolment availability, deadlines (no listing data exists).
- Not used: any labour-market statistic (Module A is NO_GO). Not a prediction of jobs, placement or earnings.
- Age is an optional extra input: every qualification has a minimum age, so without it no option can be MET.
