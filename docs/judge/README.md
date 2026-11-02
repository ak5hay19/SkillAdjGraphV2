# Offline LLM-as-judge evaluation (advisory)

Added after the Skillathon submission (2026-11-02). Code: `src/skillgraph/judge/`. Task record: `TASKS.md` J1.

## Purpose

The deterministic engine decides eligibility. Its explanation text, whether a template (P3.8, `for_eligibility` only), the demo's wording, or a future
LLM rephrase (P5.11), can still be wrong, over-certain or incomplete. The judge reviews **one candidate explanation text against one
engine result and its evidence** and reports, per dimension, `PASS`, `FAIL` or `REVIEW_REQUIRED`:

| Dimension | Question |
|---|---|
| `EVIDENCE_FAITHFULNESS` | Is every claim supported by the evidence and rule texts supplied? |
| `VERDICT_CONSISTENCY` | Does the text agree with the engine's verdict and each rule/component verdict? |
| `UNCERTAINTY_HANDLING` | Do `UNKNOWN` and `CONDITIONAL` stay uncertain? Is missing or conflicting evidence stated, not guessed? |
| `COMPLETENESS` | Are the relevant blockers, conditions and evidence gaps explained? |
| `UNSUPPORTED_CLAIMS` | Any invented eligibility, equivalence, exemption, reduced hours, labour demand, employment, placement or earnings claim? |

The case status is `PASS`, `FAIL`, `REVIEW_REQUIRED` or `ERROR` (the judge produced no usable result). It is the worst dimension outcome. There
is no numeric score, and the per-dimension outcomes are always reported next to it.

## What the judge cannot do (enforced, and tested)

- Decide, override or soften eligibility; turn `UNKNOWN` into a yes or a no. The engine verdict is copied from the packet into the result and
  nothing can change it. The output schema has no field for a verdict, a score, an edge, a path, a rank or an approval; a reply that contains one is
  rejected (`SCHEMA_INVALID`).
- Change graph edges, path existence, order or ids; resolve open evidence decisions or source conflicts; approve overlays. The package imports
  none of `graph`, `curation`, `api`, `settings`; calls neither `evaluate` nor `enumerate_paths`; never names `config/overlay_approvals.yaml`;
  and nothing in the engine imports the judge (`tests/unit/test_judge_boundaries.py`, AST scans).
- Enter the decision path: only the opt-in CLI writes files (a report directory you name); the demo and the HTTP API do not use it.

## How it works

```
EligibilityResult + Registry evidence + candidate text
        │  packet.py   deterministic, allowlisted, privacy-checked, SHA-256 digest   (no model)
        ▼
   JudgePacket ──► prompt.py ──► Judge.complete(request) ──► raw text      (the only external step: mock or opt-in provider)
        │                                                        │
        │  precheck.py  phrase scan, can only add REVIEW_REQUIRED │  validate.py  size, JSON, strict schema, grounding
        ▼                                                        ▼
                  run.py: combine ──► CaseResult (PASS | FAIL | REVIEW_REQUIRED | ERROR) ──► report.py
```

- **Packet** (`packet.py`): rule and component results, verdict, conditions, unknown reasons, flags, the evidence metadata the result cites
  (class, source title and organisation, page, location, value status, note) and the candidate text. No raw PDF text, no profile fields beyond the engine's
  own `inputs_used`, no path or profile digest, no secrets. A packet whose free text matches an email or phone pattern is refused
  (`PACKET_REFUSED`). Evidence the registry cannot resolve is refused, never invented.
- **Untrusted output** (`validate.py`): at most 20 000 characters; JSON only (one markdown fence is tolerated); closed schema with exact enums;
  each of the five dimensions once; `PASS` has no findings and `FAIL`/`REVIEW_REQUIRED` has at least one; every quoted excerpt must appear verbatim in the
  candidate text (whitespace-normalised) and every cited evidence id must be in the packet (`GROUNDING_INVALID` otherwise). Only a `COMPLETENESS` finding may omit its
  excerpt.
- **Prompt injection**: the packet, including the candidate text, is sent as one JSON document and declared data in the system prompt. A reply that
  obeys an injected instruction still has to pass the grounding checks, and the precheck is independent of the model.
- **Precheck** (`precheck.py`): a deterministic phrase scan, independent of the model. It can only lift a `PASS` to `REVIEW_REQUIRED`; it never lowers a `FAIL`,
  a `REVIEW_REQUIRED` or an `ERROR` (`run.combine`; signals are kept on an `ERROR` result but do not change its status). `evaluate_case` passes it the engine verdict
  **from the frozen packet**, read-only. Three groups of signal:

  | Family | Needs verdict | Flags |
  |---|---|---|
  | `GUARANTEE`, `OUTCOME_CLAIM`, `EQUIVALENCE`, `EXEMPTION`, `REDUCED_HOURS` | no | guarantee, job/placement/earnings/demand, equivalence, exemption and reduced-hours wording |
  | `VERDICT_CERTAINTY` | `UNKNOWN`, `CONDITIONAL` | "you are eligible", "you qualify", "you meet the requirements", "the entry rules are met", and also "you are not eligible": an open result turned into a yes or a no |
  | `VERDICT_CONTRADICTION` | `MET` | "not eligible", "ineligible", "you do not meet the requirements", "the requirements are not met", "no entry route is met" |
  | `VERDICT_CONTRADICTION` | `NOT_MET` | "you are eligible", "you qualify", "you meet the requirements" |
  | `REVIEWER_INSTRUCTION` | no (every verdict) | "ignore previous/prior/above/reviewer instructions", "answer/mark/respond PASS", "approve this explanation", "note to the reviewer", "new instructions", "system prompt", and a forged `"dimensions":` / `"outcome":` reply fragment |

  The verdict patterns target statements about the person or about the requirements as a whole. A component-level sentence ("the age requirement is met", "Requirement
  ... is NOT_MET") is deliberately not matched, because a correct `UNKNOWN` or `MET` explanation says such things. The instruction check runs over the whole text after
  Unicode NFKC, removal of invisible format characters (zero-width space), case folding and punctuation collapse, so spacing, case, line breaks and zero-width characters do
  not hide a phrase, and it is not subject to the disclaimer skip below.

  **Limits (stated, pinned by tests where possible):**
  - It is a phrase list: paraphrases ("you are sure to be accepted"), other languages and deliberate obfuscation are missed. A clean scan proves nothing.
  - Outcome families: a sentence that disclaims a prediction or says a concept is "not defined" is skipped whole, which also skips a real claim in the same sentence.
  - Verdict families: a sentence with a hedge word ("if", "cannot", "whether", "may", "unknown", "would", ...) is skipped whole, so "this cannot be decided, but you are
    eligible" is missed; for the positive patterns a negation in the same clause also skips the match, so "you are eligible, and nothing is unknown" is missed.
  - Only explicit wording is matched ("go ahead and enrol" is not). Component-level contradictions are not checked.
  - A double negation on a `MET` result ("this does not mean you are ineligible") is flagged. That only sends it to review; it decides nothing.
  - Reviewer-instruction wording is English-only and explicit; an injection that does not use those phrases is not detected here, and the model is still asked to flag it.

  No false positive was found on the 12 real pilot texts of the demo or on the P3.8 `for_eligibility` template text of those results
  (`tests/golden/test_judge_packet_real.py`). That checks the engine's own wording against these patterns; it says nothing about how a model would judge them. The judge
  model, not this scan, remains the real detector.
- **Errors** (`PROVIDER_TIMEOUT`, `PROVIDER_ERROR`, `PROVIDER_REFUSAL`, `NOT_CONFIGURED`, `OUTPUT_TOO_LARGE`, `INVALID_JSON`, `SCHEMA_INVALID`,
  `GROUNDING_INVALID`, `PACKET_REFUSED`, `INTERNAL`) become an `ERROR` result. They never become a pass and never touch the engine result.

## Judges

| Judge | Use | Network |
|---|---|---|
| `mock` (`ScriptedJudge`) | Replays canned replies from the case file. Tests the pipeline and the validators. **Says nothing about model quality.** | none |
| `anthropic` (`AnthropicJudge`) | Opt-in. One Messages API request per case over raw HTTP (`httpx`, a dev-extra dependency; the `anthropic` SDK is not a project dependency and was not installed). | yes, only with the three conditions below |

A live call sends the packet (verbatim rule text and evidence metadata from official sources) to a third party. ARCHITECTURE §19 records that reuse
rights for those sources are unconfirmed, so a live run is your decision. It happens only if all hold: `--judge anthropic`, `--allow-external`, and
`ANTHROPIC_API_KEY` in the process environment (`.env` files are not read; the key is never logged, stored or printed, and is not in `repr`). The
model id has no default (`--model`). The request carries no sampling, thinking or tool parameters, makes one attempt (no retries, 60 s timeout)
and sets no fallback model; a refusal is an `ERROR`. Prefer a judge model different from the one that wrote the explanation (self-preference
bias).

## Commands

All from the repository root, with the project interpreter.

```powershell
# offline mock run over the synthetic golden set; prints the Markdown report
.\.venv\Scripts\python.exe -B -m skillgraph.judge

# write judge_report.json and judge_report.md; exit 1 if any status differs from its stored label
.\.venv\Scripts\python.exe -B -m skillgraph.judge --out-dir docs\judge\reports --check-expected

# opt-in live judge (sends data to the provider; not run by this project's tests)
$env:ANTHROPIC_API_KEY = "<your key>"
.\.venv\Scripts\python.exe -B -m skillgraph.judge --judge anthropic --model <model-id> --allow-external --out-dir <dir>

# tests (offline; no network, credentials or paid calls)
.\.venv\Scripts\python.exe -m pytest tests/unit/test_judge_core.py tests/unit/test_judge_adapter.py tests/unit/test_judge_boundaries.py tests/golden/test_judge_packet_real.py -q
```

Exit codes: `0` ran; `1` `--check-expected` found a difference; `3` cannot run (bad file, missing model, no opt-in, no key).

## Case files and the evaluation set

`tests/fixtures/judge/golden_cases.json` (`judge-golden-synthetic-v1`) has **19 cases** over three fictional engine scenarios (`TEST/Q9001`:
MET, UNKNOWN with two reasons, CONDITIONAL): correct explanations (3), unsupported claims (2), false certainty (2), a verdict contradiction (1), incomplete reasons
(1), a lenient judge (scripted all-`PASS`) caught by the precheck floor (5: an outcome claim, false certainty on `UNKNOWN`, false certainty on `CONDITIONAL`, a contradiction on `MET`,
a reviewer-directed injection), and execution errors (5: invalid JSON, timeout, a forbidden `verdict_override` field, an ungrounded quote, a refused packet). The five
lenient-judge cases show that the deterministic floor works; their all-`PASS` dimension outcomes are scripted and inflate the `PASS` columns of the dimension table.

**Origin: `SYNTHETIC_ENGINEER_AUTHORED`.** The texts, the expected labels and the scripted replies were all written by the implementing engineer. They
are not human-review labels and not ground truth. "Agreement" in a report means only that the case status equals the label in the file; for the mock judge it
is true by construction of the file and checks that the pipeline still behaves as designed. **No accuracy, human-agreement or model-capability
figure exists or is claimed.** To measure a model, a set with independently written texts and labels from human reviewers is needed first (not created here).

A case file has `scenarios` (a packet without `case_id` and `candidate_text`) and `cases` (`scenario`, `candidate_text`, `expected`, `scripted`).

## Reports

`judge_report.json` and `judge_report.md` are byte-reproducible (sorted keys, no timestamp) and contain: the judge id; the set id, origin, size and file digest; counts by
status, by dimension and outcome, and by error kind; agreement with the stored labels with `n`; and one row per case. A report from the mock judge starts
with a banner saying it checks the pipeline only. `docs/judge/reports/` holds the report of the synthetic mock run.

## Not done / next

- The P3.8 `for_eligibility` templates now exist but no judge run has been made on them; the only text packet-built in tests is the demo wording (checked by `tests/golden/test_judge_packet_real.py`
  for packet building and precheck only; no model was called on it). The templates' text is also scanned by the precheck in that test (no verdict or instruction signal).
- No live provider run has been made. No human-labelled set exists.
- Unresolved items are untouched: Q-B, the relevance rule A-7, Module A `NO_GO`, `approved: []`.
