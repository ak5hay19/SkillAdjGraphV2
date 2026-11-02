# P3.4 closeout: D-11 (mixed Core/Non-Core) and D-14 (legend wording)

**Status:** review record, 2026-11-02 (run 8). Narrow scope: two decisions of P3.4 (`TASKS.md` P3.4, `src/skillgraph/graph/edges.py`). Nothing in `ARCHITECTURE.md` or `API_SPEC.md` was edited. Q-A, Q-B and Q-C are not touched and not resolved. No P3.5 work.

## D-11: a NOS unit that the two QFs classify differently

**The question.** `SHARES_NOS` carries `core_shared_count` and `noncore_shared_count`. The two QFs print their own Core / Non-Core label per NOS-table row, and they can disagree about one shared unit. The implementation counts a unit as Core (Non-Core) only if both QFs say so, counts a disputed unit in neither, and lists it in an extra attribute `mixed_core_codes`.

**Evidence inspected (exact locations).**

| Source | What it says | Bearing |
|---|---|---|
| `API_SPEC.md:20` (§1.1) | "Breaking changes require `/api/v2`. **Additive fields are allowed within v1.**" | An added field is permitted by the contract's own versioning rule. |
| `API_SPEC.md:677` | `GraphEdge { …, attributes: object, … }` | `attributes` is typed as a free-form object, not a closed record. |
| `API_SPEC.md:681` | "`SHARES_NOS.attributes` = `{shared_codes: string[], core_shared_count: integer, noncore_shared_count: integer, version_agreement: {code: "SAME"\|"DIFFERENT"\|"NOT_STATED"}}`." | Documents four keys. It does **not** say "exactly" or "only", and no closed-record wording (`additionalProperties`, "no other fields") appears anywhere in `API_SPEC.md` (searched). |
| `API_SPEC.md:21` | The Pydantic models in `api/schemas.py` are the source of truth. | That file does not exist yet (P3.10); no typed model currently forbids the key. |
| `ARCHITECTURE.md:422` (§10.3) | `SHARES_NOS` "Carries `shared_codes[]`, `core_shared_count`, `version_agreement` … and any conflict IDs." | Silent on the disagreement case (and does not list `noncore_shared_count`, which E08 adds). |
| `ARCHITECTURE.md:285`, `:558` | OBS-01: "All shared units are labelled Non-Core"; the overlap statement template "shares 2 NOS units (both Non-Core): …". | Describes the agreeing case only. |
| Real build `cb-601c0399c999` | Every shared unit is Non-Core in every QF that lists it; `mixed_core_codes == []` on all three edges. | The disagreement path is exercised only by synthetic tests. |

**Correction to the earlier report.** Run 7 (`TASKS.md` P3.4 exceptions, `session_log.md` Run 7, the handoff note) described E08 as listing "exactly four" attributes. That overstated the text: E08 lists four and does not close the set. The accurate statement is below.

**Disposition.**
1. **No contract conflict is established.** `mixed_core_codes` is an additive field inside a free-form `attributes` object, which API_SPEC §1.1 allows within v1. The four documented keys are present, with their documented types and meanings; removing the extra key leaves exactly the documented shape (pinned by `test_d11_the_only_attribute_beyond_the_e08_four_is_mixed_core_codes_and_it_is_additive`). Under the *stricter* reading (the sentence at line 681 closes the set) it would be a conflict; the smallest contract-consistent resolution is then Option B below. The text does not support that reading, so none was applied.
2. **Why the key is retained.** The disagreement is a fact about the sources, not about the engine. Without the key, a unit labelled Core by one QF and Non-Core by the other would either be counted in one of the counts (asserting a classification no source gives) or vanish from both counts with no trace. `mixed_core_codes` names the unit and nothing more: it asserts no classification, each QF's own printed label stays readable on its `INCLUDES_NOS` edge (`attributes.core_or_noncore`, tested), and the invariant `core + noncore + len(mixed) == len(shared_codes)` is enforced by the `GraphEdge` model.
3. **Consumer rule (for P3.8 and the E08 view).** Do not derive "all shared units are Non-Core" from `noncore_shared_count` alone; test `core_shared_count == 0 and mixed_core_codes == []`. The ARCHITECTURE §10.3 overlap sentence ("both Non-Core") must not be produced when `mixed_core_codes` is non-empty.
4. **Recommended amendment (documentation only, for explicit approval; not made):** add `mixed_core_codes: string[]` (codes that the two QFs classify differently; counted in neither count) to the `SHARES_NOS.attributes` sentence at `API_SPEC.md:681`. It is not needed for compliance under §1.1, but consumers should be able to find the key in the contract.
5. **Option B (only if the owner reads line 681 as a closed set):** drop the attribute, keep the four, and report a disagreement as one `QualityFlag` on the edge (`SEMANTIC_AMBIGUITY`, severity `INFO`, message naming the codes and the two labels, `refs` = the shared code ids). Costs: the codes become message text instead of a structured list. Not implemented.

**Status of D-11:** RESOLVED ON THE EVIDENCE: retained as an additive attribute; the one documentation amendment above awaits explicit approval. Graph semantics are unchanged by this closeout.

## D-14: legend wording

**Exact strings reviewed** (the output of `skillgraph.graph.static_legend()` after this closeout; the same strings are pinned in `tests/unit/test_graph_edges.py::REVIEWED_LEGEND`):

| Edge type | Class | `meaning` | `does_not_mean` |
|---|---|---|---|
| `INCLUDES_NOS` | OFFICIAL | The qualification's official QF lists this NOS unit or module as a row of its NOS table. | The unit is separately certified, exempt from re-training, or transferable to another qualification. |
| `SHARES_NOS` | RULE_DERIVED | Both qualifications list the same NOS code in their official QF. | Skills are equivalent, units are exempt, or people move between these roles. |
| `PROGRESSION_CLAIM` | OFFICIAL | The qualification's official QF (item 15) lists this text as a progression. | That the text is linked to a qualification in this graph (any such link is an experimental inference), that anyone is eligible for it, or that people make this move. |
| `ALIGNED_TO_NCO` | OFFICIAL | The qualification's official documents state this NCO-2015 occupation code. | The qualification leads to that occupation, jobs exist in it, or qualifications sharing a code are interchangeable. |

**Comparison with the controlling contract.**
- `SHARES_NOS`: identical to the two strings in the E08 example (`API_SPEC.md:699-700`); a test reads `API_SPEC.md` and checks both strings occur in it. **Consistent, verbatim.**
- The other three: E08 supplies no text, so they cannot be "consistent with E08", only with the semantics. Checked against `ARCHITECTURE.md` §10.2 to §10.3 and against the real build's evidence for each edge type: every `INCLUDES_NOS` and `PROGRESSION_CLAIM` edge cites QF documents (sources A3, A5, B2, B4; `pdfplumber_words` / `pdfplumber_table`), and all four `ALIGNED_TO_NCO` edges cite QF tables. Direction and class match §10.3 (OFFICIAL, qualification to node).
  - `INCLUDES_NOS`: meaning matches §10.3 ("qual → nos/module", OFFICIAL) and the NOS-table rows; the disclaimer states no property of the unit. **Consistent.**
  - `ALIGNED_TO_NCO`: meaning matches §10.2/§10.3 ("NCO codes stated in QPs/QFs"); "official documents" is deliberately general (pilot evidence is QF-only). It says nothing about the code's title; title verification (e.g. DQ-04, `3122.3551` not found) is shown on the occupation, not on this edge. **Consistent.**
  - `PROGRESSION_CLAIM` `meaning`: "(item 15)" comes from §10.2 ("Progression claims (QF item 15)"); the evidence record carries no `location` text, so item 15 is not confirmed from the evidence itself. **Consistent with §10.2.**

**Discrepancy found and corrected.** The run-7 `does_not_mean` for `PROGRESSION_CLAIM` read "The text names a qualification in this graph, that anyone is eligible for it, or that people make this move." The first clause can be false: the SMO claim text "Specialized Sewing Machine Operator" is exactly SSMO's title, and DQ-15 notes that "Sampling Coordinator" matches AMH/Q1801 by name. What is true is that the *edge* states no link to a qualification (the claim goes to a `claim:` node; a name-based link is an INFERENCE, P3.5). The string was changed to the one in the table above; a test (`test_d14_a_claim_text_that_equals_a_qualification_title_…`) shows why. This changes legend text only; no edge, id, attribute or ordering changed.

**Wording checks.** No string describes an edge as proof of eligibility, employability or a guaranteed progression: "eligible", "jobs" and "move" occur only in `does_not_mean` (tested); the project's forbidden-word list ("guarantee", "will get", "eligible for job", "in demand", "declining") does not occur (tested).

**Status of D-14:** REVIEWED, NOT APPROVED. The exact wording has been inspected and is consistent with ARCHITECTURE §10.2 to §10.3, the source semantics and, for `SHARES_NOS`, E08 verbatim. Because E08 supplies no text for three of the four entries, those three strings remain drafted wording awaiting explicit owner approval. If approved, E08's `legend` example could also gain these entries (documentation only; not made).

## Unchanged

Q-A, Q-B, Q-C; D-1 to D-6 of P3.3; D-7 to D-10, D-12, D-13 of P3.4; every P3.3 golden expectation; Module A `NO_GO`; `config/overlay_approvals.yaml` (`approved: []`).
