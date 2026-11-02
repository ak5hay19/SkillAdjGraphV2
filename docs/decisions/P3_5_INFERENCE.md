# P3.5 — Experimental inference edges: contract, implementation and open points

**Status:** implementation and review record, 2026-11-02 (run 9). Scope: `TASKS.md` P3.5 only. Nothing in `ARCHITECTURE.md` or `API_SPEC.md` was edited. Q-A, Q-B and Q-C are not touched and not resolved. No P3.6 work. D-11 and D-14 keep their run-8 status (D-11 resolved on the evidence, retained; D-14 reviewed, **not approved**); this record adds a second drafted legend entry, which is also **not approved**.

## 1. What the contract says (and where)

| Source | Text relevant to P3.5 |
|---|---|
| `TASKS.md` P3.5 deliverables | `graph/inference.py`: `NCO_GROUP_PROXIMITY` "at the 4-digit unit group, with the 3-digit level configurable". Name-normalised matching of claim text to catalogue titles "written to the review file as candidates" (examples: "Sampling Coordinator" → AMH/Q1801; "QC Executive – Sewing Line" has **no** exact match). `TITLE_SIMILARITY` "is COULD and not planned". |
| `TASKS.md` P3.5 criteria | Every inference edge has `evidence_class = INFERENCE` and `experimental = true`. Edges are off unless requested. SMO–SSMO share unit group 8153, so they get an `NCO_GROUP_PROXIMITY` edge. "The invariant test in P3.6 passes." |
| `ARCHITECTURE.md` §10.1 | `INFERENCE` examples: NCO unit-group proximity, title similarity, name-matched progression target. May it make a step feasible? **Never.** |
| `ARCHITECTURE.md` §10.3 | `NCO_GROUP_PROXIMITY`: qual ↔ qual, INFERENCE (experimental), stored, hidden by default, not used for feasibility. Invariant: inference edges can annotate a path but can never create, remove or reorder feasibility. `PROGRESSION_CLAIM`: qual → claim text, "→ qual only via reviewed inference". |
| `ARCHITECTURE.md` §13.4 | `NCO_GROUP_PROXIMITY`: two qualifications whose stated NCO codes share a unit group (4 digits) or minor group (3 digits). Measures classification proximity of the *occupations*; does **not** measure skill overlap, feasibility or mobility. Name-matched progression target: normalised text match of a claim to a catalogue title; "reviewed in `eligibility_rules_review.md`". |
| `ARCHITECTURE.md` DQ-15 | A name-based link to a catalogue code is `INFERENCE`, needs review, is never an `OFFICIAL` edge. |
| `API_SPEC.md` E08 | `include_inference` (default `false`) "Adds `NCO_GROUP_PROXIMITY` / `TITLE_SIMILARITY` edges, marked `experimental: true`"; `INFERENCE_EXPERIMENTAL` warning on every inference edge; `legend.does_not_mean` always present. `GraphEdge` fields. |
| `API_SPEC.md` §4 | `graph.build_static_edges(registry, include_inference) -> list[GraphEdge]`. |
| `API_SPEC.md` E09 (line 728, 777, 826) | `include_inference` on paths adds `inference_annotations` to steps and never changes `path_id`, verdicts or order. (Path work: P3.6 / P3.10.) |

## 2. What is **not** specified (recorded gaps)

1. **Edge attributes** of `NCO_GROUP_PROXIMITY`: E08 gives an attribute set only for `SHARES_NOS`.
2. **Confidence semantics**: none. No score, weight, distance, rank or probability is defined, so none exists in the implementation.
3. **Evidence/provenance form** of an inference edge (`evidence_ids` content).
4. **Configuration key** for the 3-digit level: "configurable" only; `config/default.yaml` has `inference.enabled` and nothing else; the E07/E08 `config` objects have no such key.
5. **Legend wording** for the inference edge (E08 gives text for `SHARES_NOS` only).
6. **Claim normalisation**: "name-normalised" with two examples; the rules are not defined. Which catalogue title field is compared is stated only as "catalogue titles".
7. **The review file**: `eligibility_rules_review.md` exists only as a generated, gitignored snapshot inside `data/curated/<build>/` (a protected tree, "not regenerated automatically"). Its format has no section for claim candidates.
8. **`TITLE_SIMILARITY`**: algorithm, tokens/embeddings, threshold, attributes — all undefined, and "not planned".
9. **Path annotations** (`inference_annotations`): need paths (P3.6).

## 3. What was implemented

| Item | Where | Notes |
|---|---|---|
| `NCO_GROUP_PROXIMITY` edges | `src/skillgraph/graph/inference.py` `build_inference_edges(registry, *, nco_group_digits=4)` | Pure function of the registry's stated NCO codes and `Occupation.nco_levels` prefixes. Reads no title, level, hours, credit, age, eligibility rule, labour figure or LLM (AST test). |
| `include_inference=True` hook | `graph/edges.py` `build_static_edges(registry, include_inference=False, *, nco_group_digits=4)` | Returns the unchanged static edges plus the inference edges, sorted by `(type, source, target)`. Previously raised `NotImplementedError` (D-7). |
| `GraphEdge` contract for the type | `graph/edges.py` `_check_nco_proximity` | Refuses an edge that is directed, not INFERENCE, not experimental, unflagged, mis-ordered or mis-attributed. `TITLE_SIMILARITY` keeps the generic rule only (contract undefined). |
| Legend | `inference_legend()` | One entry; **drafted, not approved**. `static_legend()` unchanged. |
| Claim → catalogue-title **candidates** | `graph/claim_candidates.py` | Not edges. `claim_title_candidates`, `normalise_name`, `render_review_section`. Writes no file. |
| Tests | `tests/unit/test_graph_inference.py` (93), `tests/golden/test_graph_inference_pilot.py` (15), `tests/integration/test_graph_inference_build.py` (4) | See `TASKS.md` P3.5 for results. One P3.4 test was replaced (§6). |

### Exact semantics of `NCO_GROUP_PROXIMITY`

- **Meaning:** the official documents of qualification A and qualification B state NCO-2015 codes (the `ALIGNED_TO_NCO` relationships) that begin with the same 4 digits (default) or 3 digits (configured). It is a statement about the *classification of the occupations*, nothing more.
- **It is not:** skill overlap, equivalence, exemption, eligibility, a progression, mobility, employability or labour demand. It is never read by `evaluate`, never creates, removes or reorders a path, and never changes a verdict.
- **Shape:** undirected; stored once with `source < target`; id `e:NCO_GROUP_PROXIMITY:<A key>:<B key>`; `evidence_class = INFERENCE`; `experimental = true`; one `INFERENCE_EXPERIMENTAL` flag (severity `INFO`).
- **Attributes (D-16):** `group_digits` (3 or 4), `shared_groups` (ascending), `codes_by_qualification` (the stated codes in a shared group, per qualification). No score of any kind.
- **Provenance (D-17):** `evidence_ids` = the evidence ids of those stated codes (OFFICIAL cells, the same ids the `ALIGNED_TO_NCO` edges cite).
- **Membership:** all qualifications that state a code (as D-7, whatever the `coverage`; the real build's catalogue-only records state none).

### Decisions (continuing D-1 … D-14)

**Settled implementation choices (narrow, derived from the contract text; reversible; for review):**

| ID | Decision |
|---|---|
| D-15 | One edge per unordered pair of distinct qualifications sharing ≥ 1 group at the configured level (several shared groups → one edge listing them); two codes of one qualification never make a self-edge. |
| D-16 | Attributes `group_digits`, `shared_groups`, `codes_by_qualification` — the smallest set that makes the edge traceable and checkable. |
| D-17 | Provenance = evidence ids of the stated codes behind the edge. |
| D-18 | Identity and order as D-13 (`e:<TYPE>:<source key>:<target key>`, sorted `(type, source, target)`, deterministic, record-order independent). |
| D-19 | Invalid input is reported, never repaired (as D-9): null stated code, code with no occupation record, code with no/unresolved evidence, a code stated twice by one qualification → `EdgeBuildError` listing all problems. Invalid `nco_group_digits` → `ValueError`. |
| D-20 | The level is the keyword `nco_group_digits` (4 default, or 3). **No settings key was invented** (see §4). `INFERENCE_EXPERIMENTAL` flag on every edge (E08 "Warnings"), severity `INFO` (E08 gives none). |
| D-21 | Claim normalisation (the narrowest reading that reproduces the two examples): remove the claim's **own** trailing `(<direction_label>)`; NFKC; case-fold; reduce to the sequence of letters/digits (every other character separates tokens). Exact equality of the normalised strings against the normalised **catalogue** title; no similarity, stemming or synonym handling. |
| D-22 | Ambiguity and self-reference are reported, never resolved: all equal-name titles are candidates (`candidate_count` > 1, none preferred); a claim equal to its own qualification's title is kept and marked `target_is_source`; unmatched claims are listed. The catalogue title has no evidence id in the registry, so a candidate cites the claim's evidence id only. |
| D-23 | Candidates are returned and renderable as a Markdown section; **no file is written**. The build's `eligibility_rules_review.md` is in the protected `data/` tree and is a generated snapshot, so it is neither edited nor regenerated. |

**Unresolved policy questions (not decided here):**

| ID | Question | Minimal proposed resolution |
|---|---|---|
| Q-D | Is the D-21 normalisation acceptable? In particular punctuation-as-separator creates a candidate the contract did not anticipate (observation below: "Sewing Machine Operator-Knits" → AMH/Q0305). | Approve D-21 as is, or restrict to case/whitespace/dash variants (a one-line change to `_TOKENS`). |
| Q-E | Where should claim candidates live as a reviewed artefact (TASKS: "the review file")? | Either approve `docs/decisions/P3_5_INFERENCE.md` §5 as the review location, or name a file outside `data/` that the builder/`validate` regenerates. |
| Q-F | Config key for the 3-digit level. | Add `inference.nco_group_digits` (4 or 3) to `config/default.yaml`/`InferenceSettings` with its settings test, wired by P3.10. Not done: it would touch settings tests and the E07/E08 `config` shape, which the contract does not define. |
| Q-G | Approve the drafted `NCO_GROUP_PROXIMITY` attributes (D-16) and legend wording; amend E08 with them (documentation-only, like the D-11 proposal). | Add one line under `API_SPEC.md:681` for `NCO_GROUP_PROXIMITY.attributes` and the legend entry. |
| Q-H | Should `build_static_edges` keep its name now that it can return experimental edges? | Keep (API_SPEC §4 fixes the name and `include_inference` parameter). |

## 4. Why `nco_group_digits` is a keyword and not a setting

`TASKS.md` says only "configurable"; `config/default.yaml` has `inference: {enabled: false}`; `settings.py` rejects unknown keys; E07's and E08's `config` carry `inference_enabled` but no level. Adding a key means choosing its name, its place in the API `config` object and a settings test — a contract decision, not an implementation detail. The function parameter satisfies "configurable" without that.

## 5. Observations on the real build `cb-601c0399c999` (validated `PASSED`; read through the registry; not decisions)

**`NCO_GROUP_PROXIMITY`** — exactly one edge at either level:

| Edge | Level | Shared | Codes |
|---|---|---|---|
| `e:NCO_GROUP_PROXIMITY:AMH/Q0301:AMH/Q2301` (SMO ↔ SSMO) | 4 digits | `8153` | `8153.0101` / `8153.0103` |
| the same edge | 3 digits | `815` | same |

IC states `7543.0301` and PS `3122.3551`; neither shares a 3- or 4-digit group with another pilot, and the 33 catalogue-only records state no code. With inference requested the build has 41 edges: the 40 static ones unchanged plus this one. SMO ↔ SSMO has **no** `SHARES_NOS` edge (OBS-01), so the inference edge is the only relationship drawn between them — which is why the legend and the flag matter.

**Claim → catalogue-title candidates** (D-21; unreviewed; nothing here is a decision or an official link):

| Claim | Claim text (verbatim) | Candidate | Catalogue title | Note |
|---|---|---|---|---|
| `claim:AMH/Q0301/P1` | Sewing Machine Operator-Knits(Horizontal) | `qual:AMH/Q0305` | Sewing Machine Operator Knits | **not anticipated by the contract** (punctuation rule, Q-D); catalogue-only record |
| `claim:AMH/Q0301/P2` | Specialized Sewing Machine Operator(Vertical) | `qual:AMH/Q2301` | Specialized Sewing Machine Operator | equals SSMO's title (the SMO → SSMO claim; D-5 / DQ-15) |
| `claim:AMH/Q2301/P1` | Sampling Coordinator(Vertical) | `qual:AMH/Q1801` | Sampling Coordinator | the contract's own example |

No exact match: `claim:AMH/Q0103/P1` ("QC Executive - Sewing Line"), `claim:AMH/Q2101/P1` ("QC Executive - Sewing Line (Horizontal)"), `claim:AMH/Q2101/P2` ("Production Manager (Vertical)"). The first two reproduce the contract's "no exact match" example.

A candidate is not an edge: the model still refuses a `PROGRESSION_CLAIM` edge to a qualification, `ProgressionClaim.resolved_target` stays `null` everywhere, and nothing reads the candidates.

## 6. Existing test replaced

`tests/unit/test_graph_edges.py::test_inference_edges_are_not_built_here_and_asking_for_them_is_an_error_not_a_silent_omission` asserted the P3.4 behaviour that `include_inference=True` raises `NotImplementedError("… P3.5")`. D-7 stated that this was the behaviour *until P3.5*; P3.5 is the deliverable that replaces it, so the assertion was replaced by `test_static_edges_are_off_by_default_free_of_inference_and_unchanged_when_inference_is_requested`, which keeps every other check (default and `False` equal, static types only, nothing experimental by default) and adds that requesting inference leaves the static edges unchanged. No other existing test was edited.

## 7. Acceptance criteria (TASKS P3.5)

| # | Criterion | Result |
|---|---|---|
| 1 | Every inference edge has `evidence_class = INFERENCE` and `experimental = true` | **PASS** (enforced by `GraphEdge`; asserted for synthetic cases and the real build) |
| 2 | The edges are off unless they are requested | **PASS** |
| 3 | SMO–SSMO share unit group 8153 → an `NCO_GROUP_PROXIMITY` edge | **PASS** (real build; group read independently from the occupation records) |
| 4 | The invariant test in P3.6 passes | **PROVISIONAL** — P3.6 does not exist. What can be shown now is shown: static edges are byte-equal with inference on; building inference edges changes no registry record and none of 480 eligibility results (40 profiles × 3 level settings × 4 pilots), and a registry with no stated NCO codes (hence no inference edge) gives identical results. Path-set/order invariance needs P3.6. |
| D1 | Deliverable: `NCO_GROUP_PROXIMITY`, 4-digit, 3-digit configurable | **PASS** (configurable by parameter; settings key is Q-F) |
| D2 | Deliverable: name-normalised claim → catalogue-title candidates "written to the review file" | **PROVISIONAL** — implemented as returned/renderable candidates (D-21 to D-23) and recorded in §5; no file is written (Q-D, Q-E) |
| D3 | `TITLE_SIMILARITY` | **Not built** (COULD, "not planned"; contract undefined) |

## 8. Not done, on purpose

`TITLE_SIMILARITY`; `inference_annotations` on path steps (needs paths: P3.6 / P3.10); the API-level `INFERENCE_EXPERIMENTAL` response warning and `legend` assembly (P3.10 / P5.4); any node assembly or `focus` filter (D-7); any settings key; any edit of the protected `data/` tree, `ARCHITECTURE.md`, `API_SPEC.md`, `config/overlay_approvals.yaml` or `config/labour_market.yaml`.
