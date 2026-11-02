# Judge evaluation report

> **MOCK JUDGE (scripted replies). This checks the pipeline only. It says nothing about how well any model judges explanations.**

- Judge: `mock-scripted`
- Evaluation set: `judge-golden-synthetic-v1`, **n = 19** cases, origin **SYNTHETIC_ENGINEER_AUTHORED**
- Labels: Engine scenarios use the fictional code TEST/Q9001 and are not real source values. Candidate texts and expected labels were written by the implementing engineer, and the scripted replies by the same engineer. They are NOT human-review labels and NOT ground truth; agreement with them is a pipeline regression check, not a measure of any model.
- Set digest: `sha256:eb40001ae464af728e977457712dcbe3e0a53e51992a0646d2a400829018787d`
- This is an advisory quality-control layer. The engine's verdicts are authoritative and are not changed by it.

## Case status counts

| Status | Cases |
|---|---|
| PASS | 3 |
| FAIL | 5 |
| REVIEW_REQUIRED | 6 |
| ERROR | 5 |

## Dimension outcomes (completed cases only)

| Dimension | PASS | FAIL | REVIEW_REQUIRED |
|---|---|---|---|
| EVIDENCE_FAITHFULNESS | 12 | 2 | 0 |
| VERDICT_CONSISTENCY | 12 | 2 | 0 |
| UNCERTAINTY_HANDLING | 11 | 3 | 0 |
| COMPLETENESS | 12 | 0 | 2 |
| UNSUPPORTED_CLAIMS | 12 | 2 | 0 |

## Errors by kind

| Kind | Cases |
|---|---|
| PACKET_REFUSED | 1 |
| PROVIDER_TIMEOUT | 1 |
| INVALID_JSON | 1 |
| SCHEMA_INVALID | 1 |
| GROUNDING_INVALID | 1 |

## Agreement with the stored status labels

19 of 19 labelled cases have the labelled status (labels: SYNTHETIC_ENGINEER_AUTHORED, not human-reviewed). Equality of the case status with the label stored in the case file; see dataset.origin and labels_note.

## Cases

| Case | Category | Engine verdict | Status | Expected | Dimensions not PASS | Precheck | Error |
|---|---|---|---|---|---|---|---|
| g01-correct-met | correct explanation | MET | PASS | PASS | - | - | - |
| g02-correct-unknown | correct explanation | UNKNOWN | PASS | PASS | - | - | - |
| g03-correct-conditional | correct explanation | CONDITIONAL | PASS | PASS | - | - | - |
| g04-unsupported-outcome | unsupported claim | MET | FAIL | FAIL | EVIDENCE_FAITHFULNESS=FAIL, UNSUPPORTED_CLAIMS=FAIL | GUARANTEE, OUTCOME_CLAIM | - |
| g05-equivalence-exemption | unsupported claim | UNKNOWN | FAIL | FAIL | UNCERTAINTY_HANDLING=FAIL, UNSUPPORTED_CLAIMS=FAIL | EQUIVALENCE, EXEMPTION, REDUCED_HOURS | - |
| g06-false-certainty-unknown | false certainty | UNKNOWN | FAIL | FAIL | VERDICT_CONSISTENCY=FAIL, UNCERTAINTY_HANDLING=FAIL | VERDICT_CERTAINTY | - |
| g07-false-certainty-conditional | false certainty | CONDITIONAL | FAIL | FAIL | UNCERTAINTY_HANDLING=FAIL, COMPLETENESS=REVIEW_REQUIRED | VERDICT_CERTAINTY | - |
| g08-verdict-contradiction | verdict contradiction | MET | FAIL | FAIL | EVIDENCE_FAITHFULNESS=FAIL, VERDICT_CONSISTENCY=FAIL | VERDICT_CONTRADICTION | - |
| g09-incomplete-reasons | incomplete reasons | UNKNOWN | REVIEW_REQUIRED | REVIEW_REQUIRED | COMPLETENESS=REVIEW_REQUIRED | - | - |
| g10-lenient-judge-precheck | precheck floor | MET | REVIEW_REQUIRED | REVIEW_REQUIRED | - | GUARANTEE, OUTCOME_CLAIM | - |
| g11-error-invalid-json | execution error | MET | ERROR | ERROR | - | - | INVALID_JSON: not valid JSON: Expecting value: line 1 column 1 (char 0) |
| g12-error-timeout | execution error | MET | ERROR | ERROR | - | - | PROVIDER_TIMEOUT: the provider did not answer in time |
| g13-error-verdict-field | execution error | MET | ERROR | ERROR | - | - | SCHEMA_INVALID: verdict_override: Extra inputs are not permitted |
| g14-error-ungrounded-quote | execution error | MET | ERROR | ERROR | - | - | GROUNDING_INVALID: UNSUPPORTED_CLAIMS: a quoted excerpt is not in the candidate text |
| g15-error-packet-refused | execution error | - | ERROR | ERROR | - | - | PACKET_REFUSED: packet invalid: Value error, a free-text field matches a contact-detail pattern; the packet is refused |
| g16-lenient-judge-false-certainty-unknown | precheck floor | UNKNOWN | REVIEW_REQUIRED | REVIEW_REQUIRED | - | VERDICT_CERTAINTY | - |
| g17-lenient-judge-false-certainty-conditional | precheck floor | CONDITIONAL | REVIEW_REQUIRED | REVIEW_REQUIRED | - | VERDICT_CERTAINTY | - |
| g18-lenient-judge-contradiction-met | precheck floor | MET | REVIEW_REQUIRED | REVIEW_REQUIRED | - | VERDICT_CONTRADICTION | - |
| g19-lenient-judge-injection | precheck floor | MET | REVIEW_REQUIRED | REVIEW_REQUIRED | - | REVIEWER_INSTRUCTION | - |
