# Skill Adjacency Graph — API Specification (v1)

**Document status:** Approved contract for the initial version, 2026-10-31. **No endpoint is implemented yet.** This document is authoritative for the HTTP contract. Enums and schemas must match `src/skillgraph/api/schemas.py` once it exists; a test checks this (`TASKS.md` P1.2, P3.10).
**Aligned with:** [`ARCHITECTURE.md`](ARCHITECTURE.md) (§§9–14, 16–17) · [`TASKS.md`](TASKS.md) (Phases 3 and 5)

About the examples: example payloads are **illustrative**.

- IDs, digests and build IDs in them are placeholders.
- Qualification facts, such as hours and levels, are taken from the existing extraction outputs for orientation only.
- Example verdicts show the *shape* of a response, not engine results.

---

## 1. Conventions

### 1.1 Base, transport, versioning

- Base path: `/api/v1`, served by FastAPI on `http://127.0.0.1:8000` for local use only. There is no authentication, because the server binds to localhost and stores no data.
- JSON over HTTP (UTF-8). `GET` is used for reads. `POST` is used only for *evaluations* whose input is a hypothetical profile. These calls are side-effect-free and never persist anything.
- Breaking changes require `/api/v2`. Additive fields are allowed within v1.
- The OpenAPI document is generated at `/api/v1/openapi.json` from the Pydantic models in `src/skillgraph/api/schemas.py`. **Those models are the source of truth; this document describes them.**

### 1.2 Identifiers

| Entity | `id` | URL `slug` |
|---|---|---|
| Qualification | `qual:AMH/Q2301` | `AMH.Q2301` (`/` replaced by `.`; lookup key only) |
| NOS unit | `nos:AMH/N0309` | `AMH.N0309` |
| Module (non-NOS, e.g. bridge) | `mod:AMH/Q2301/S1` | — |
| Occupation | `nco:8153.0103` | `8153.0103` |
| Source | `src:A5` | — |
| Eligibility rule | `rule:AMH/Q2301/E9`, `rule:AMH/Q2301/AGE` | — |
| Progression claim | `claim:AMH/Q0301/P2` | — |
| Conflict | `conflict:OV-036` | — |
| Evidence | `ev:<16 hex>` | — |
| Path | `p-<12 hex>`: `p-` plus the first 12 lowercase hex characters of the SHA-256 of the canonical JSON of exactly `{config, profile_digest, scenario, steps}` (the effective `EngineConfig`, the profile identity digest, the effective `Scenario`, the ordered step qualification codes). It excludes the build ID, `sort_by`, `limit` and `include_inference`, so these never change a path's identity. Decided 2026-11-02 and implemented in `graph/paths.py` the same day (P3.6b, amendment A-6, §4; on branch `feat/p36b-path-identity`, committed on that branch). | — |

Request bodies refer to qualifications by their **official code** (`"AMH/Q2301"`). Responses always include `id`, `code` and `slug`.

### 1.3 The `meta` block (every 2xx response)

```json
"meta": {
  "api_version": "1.0",
  "data_build_id": "cb-1a2b3c4d5e6f",
  "config_digest": "sha256:9f2c…",
  "request_id": "req-7d41c0"
}
```

`data_build_id` and `config_digest` make any screen or report traceable to the exact curated build and configuration (ARCHITECTURE §17).

### 1.4 Determinism

For the same `data_build_id`, configuration and request body, analytical responses are **identical**, except `meta.request_id`. Lists are sorted by stable keys, which each endpoint states. Responses carry no wall-clock timestamps, except `build.built_at` on the status endpoint.

### 1.5 Availability markers used in this document

| Marker | Meaning |
|---|---|
| **MUST · P5** | Required for the final demo; HTTP implemented in Phase 5; the underlying service in the phase shown |
| **SHOULD · P5** | Planned; dropped only if time runs out |
| **CONDITIONAL** | Exists only if the Module A gate decision is `GO` or `GO_REDUCED` (ARCHITECTURE §21). Otherwise it returns `MODULE_UNAVAILABLE`. |
| **FUTURE** | Not part of v1 |

### 1.6 Error envelope

All non-2xx responses use this shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request body failed validation.",
    "details": [{ "field": "profile.age_years", "issue": "must be between 14 and 80" }],
    "request_id": "req-7d41c0"
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 404 | `NOT_FOUND` | Unknown slug, NCO code or evidence ID in the path or query |
| 404 | `MODULE_UNAVAILABLE` | A CONDITIONAL endpoint was called while Module A is `NO_GO` or `NOT_ASSESSED`. `details` includes `gate_decision` and `decision_record`. |
| 422 | `VALIDATION_ERROR` | Schema or range violation (Pydantic) |
| 422 | `UNKNOWN_QUALIFICATION_CODE` | The body refers to a code that is not in the registry |
| 422 | `TARGET_NOT_EVALUABLE` | The target exists but has `coverage = CATALOGUE_ONLY` (no eligibility evidence) |
| 422 | `LIMIT_EXCEEDED` | `max_steps` > 4, more than 50 targets, more than 50 evidence IDs, or the enumeration guard tripped (ARCHITECTURE §13.1) |
| 503 | `DATA_NOT_BUILT` | No valid curated build is loaded (the app is in degraded mode, ARCHITECTURE §17) |
| 500 | `INTERNAL_ERROR` | Unexpected. The message is generic, and details are logged without profile contents. |

**A verdict of `UNKNOWN` or `NOT_MET` is a successful `200` response, not an error.**

---

## 2. Shared schemas and enums

### 2.1 Enums

| Enum | Values |
|---|---|
| `EvidenceClass` | `OFFICIAL`, `RULE_DERIVED`, `DECLARED`, `INFERENCE`, `HYPOTHETICAL`, `CONFIG` |
| `Verdict` | `MET`, `NOT_MET`, `UNKNOWN`, `CONDITIONAL`, ordered `NOT_MET < UNKNOWN < CONDITIONAL < MET` |
| `ValueStatus` | `TRANSCRIBED`, `PARSED_UNCERTAIN`, `UNRESOLVED`, `CORROBORATED`, `CONFIRMED_BY_GEOMETRY`, `CORRECTION_APPLIED` |
| `EngineUse` (from the audit overlay) | `SAFE_HARD_RULE`, `SAFE_WITH_CONSTRAINT`, `SAFE_HOURS`, `CONDITIONAL_ON_DECLARED_RELEVANCE`, `CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG`, `UNKNOWN`, `DISPLAY_ONLY`, `NOT_USED` |
| `Coverage` | `CURATED`, `CATALOGUE_ONLY` |
| `ComponentType` | `AGE_MIN`, `SCHOOL_GRADE_MIN`, `NAMED_CREDENTIAL`, `PRIOR_NSQF_LEVEL`, `EXPERIENCE_MIN_YEARS`, `UNMODELLED` |
| `UnknownReasonCode` | `INPUT_NOT_DECLARED`, `RELEVANCE_NOT_DECLARED`, `CONFIG_UNSET`, `EQUIVALENCE_UNDEFINED`, `CREDENTIAL_ORDER_UNDEFINED`, `ENROLMENT_NOT_MODELLED`, `LITERACY_NOT_MODELLED`, `NTC_NAC_CITS_NOT_MODELLED`, `DIPLOMA_YEAR_NOT_MODELLED`, `REVIEW_FLAG`, `UNCERTAIN_EXTRACTION`, `SOURCE_CONFLICT`, `OVERLAY_NOT_APPROVED`, `ENGINE_USE_UNDECIDED` |
| `ConditionKind` | `DECLARATION`, `CONFIG`, `HYPOTHETICAL` |
| `QualityFlagCode` | `UNCERTAIN_EXTRACTION`, `SOURCE_CONFLICT`, `SOURCE_UNAVAILABLE`, `NCO_TITLE_NOT_FOUND`, `TITLE_VARIANT`, `SECONDARY_COPY_BINARY_DIFFERS`, `OVERLAY_PENDING_APPROVAL`, `NUMBERING_GAP`, `SEMANTIC_AMBIGUITY`, `INFERENCE_EXPERIMENTAL`, `HYPOTHETICAL_SCENARIO`, `LICENCE_UNCONFIRMED`, `NO_OFFICIAL_REDUCTION_SOURCE`, `DEPENDS_ON_DECLARATION`, `DEPENDS_ON_CONFIG`, `SMALL_SAMPLE`, `UNCERTAINTY_NOT_ESTIMABLE`, `AGGREGATION_CONTEXT_ONLY` |
| `Severity` | `INFO`, `CAUTION`, `WARNING` |
| `NodeType` | `QUALIFICATION`, `NOS_UNIT`, `MODULE`, `OCCUPATION`, `CLAIM_TEXT` |
| `EdgeType` | `INCLUDES_NOS`, `SHARES_NOS`, `PROGRESSION_CLAIM`, `ALIGNED_TO_NCO`, `NCO_GROUP_PROXIMITY`, `TITLE_SIMILARITY`. `ELIGIBILITY_ROUTE` appears only inside path responses. |
| `NsqfLevelMatch` | `exact`, `at_least`, or `null` (unset, which makes level components `UNKNOWN`) |
| `PostSchoolCredentialType` | `UG_CERTIFICATE`, `UG_DIPLOMA`, `OTHER` |
| `IncrementalHoursPolicy` | `NONE` (default), `EXCLUDE_SHARED_NOS_CODE`, `EXCLUDE_SHARED_NOS_CODE_AND_VERSION` |
| `PathSortKey` | `OFFICIAL_HOURS` (default), `STEPS`, `ASSUMPTIONS`, `QUALITY_FLAGS`, `DOCUMENTED_OVERLAP`. The verdict class is always applied first (ARCHITECTURE §13.2). |
| `TitleVerification` | `VERIFIED_IN_SOURCE`, `NOT_FOUND`, `NOT_CHECKED` |
| `LicenceStatus` | `UNCONFIRMED`, `PERMITTED`, `RESTRICTED` |
| `BuildStatus` | `READY`, `NOT_BUILT`, `INVALID` |
| `GateDecision` | `GO`, `GO_REDUCED`, `NO_GO`, `NOT_ASSESSED` |
| `ModuleStatus` | `AVAILABLE`, `DEFERRED`, `NOT_ASSESSED` |

**`UnknownReasonCode` meanings that the name alone does not give:**

- `UNCERTAIN_EXTRACTION`: the input cell is `PARSED_UNCERTAIN` or `UNRESOLVED` and has not been substantiated. It is never used for a `TRANSCRIBED` cell.
- `OVERLAY_NOT_APPROVED`: the value exists only as a pending, unapproved overlay proposal.
- `ENGINE_USE_UNDECIDED`: the requirement was parsed from a cell that is not uncertain, but its `engine_use` is `UNKNOWN`: the audit assigned it no safe use and nothing substantiates evaluating it (for example the 5-year experience of Sewing Machine Operator row 5). The component keeps its verbatim requirement and is not safe. It is resolved only by a new audit decision on that cell, never by code or configuration. `resolvable_by` is `SOURCE_REVIEW`.
- `REVIEW_FLAG`: the audit flagged the verbatim text for review (decision D4).

### 2.2 Provenance and quality objects

```text
Evidence {
  id: string                       // "ev:…"
  evidence_class: EvidenceClass
  source: SourceRef | null         // null for RULE_DERIVED/INFERENCE (see derived_from)
  page: string | null              // as printed in the extraction, e.g. "3-4"
  location: string | null          // e.g. "QF item 13", "item 9 table row 9"
  method: string | null            // e.g. "pdfplumber_table", "rule:sum", "rule:exact_nos_code_match"
  value_status: ValueStatus | null
  overlay_ids: string[]            // e.g. ["OV-019"]
  decision_refs: string[]          // audit decisions, e.g. ["D2","D3"]
  derived_from: string[]           // evidence ids (RULE_DERIVED / INFERENCE)
  note: string | null
}
SourceRef { id: string, title: string, org: string, sha256: string, licence_status: LicenceStatus, role: "PRIMARY"|"SECONDARY" }

QualityFlag { code: QualityFlagCode, severity: Severity, message: string, refs: string[] }   // refs: conflict/overlay/evidence ids

Valued<T> { value: T | null, evidence_class: EvidenceClass, evidence_id: string | null,
            value_status: ValueStatus | null, engine_use: EngineUse | null, conflict_id: string | null }

ExplanationItem { kind: string, text: string, evidence_class: EvidenceClass, evidence_ids: string[], flags: QualityFlagCode[] }
```

`DECLARED`, `CONFIG` and `HYPOTHETICAL` items are request-scoped. They appear inline (`inputs_used`, `conditions`) and have **no** stored `Evidence` record, so they cannot be fetched from E10.

### 2.3 Profile, configuration and scenario (request inputs)

```text
HypotheticalProfile {
  label: string (required, 1–80)                      // e.g. "Demo profile A (hypothetical)"; never a real person's name
  age_years: integer 14–80 | null
  school_grade_passed: integer 0–12 | null            // highest school grade PASSED
  post_school_credentials: PostSchoolCredential[] | null   // null = not declared; [] = declared none
  held_qualification_codes: string[] | null           // registry codes; null = not declared; [] = none
  external_qualifications: ExternalQualification[] | null  // outside the registry, with a DECLARED NSQF level
  declarations: TargetDeclaration[]                   // default []
}
PostSchoolCredential   { type: PostSchoolCredentialType, label: string | null }
ExternalQualification  { ref: string (^ext-[a-z0-9-]{1,20}$), label: string, nsqf_level: number 1–10 (multiple of 0.5) }
TargetDeclaration {
  target_code: string                                 // a CURATED qualification code
  relevant_experience_years: number ≥ 0 | null        // years the person declares relevant to this target
  relevant_prior_qualifications: string[] | null      // refs from external_qualifications, and registry codes (held, or not yet held: a pending qualification is relevant to THIS target only if named here); null = not supplied, [] = supplied empty (decided 2026-11-02, §4 A-7; not yet implemented)
}

EngineConfig  { nsqf_level_match: NsqfLevelMatch }   // omitted → server default (null in config/default.yaml)

Scenario {
  assume_intermediate_relevance: boolean = false      // true → path marked HYPOTHETICAL
  assumed_experience_gain_years_per_step: number 0–5 = 0   // > 0 → path marked HYPOTHETICAL
  incremental_hours_policy: IncrementalHoursPolicy = "NONE"
}
```

Validation rules, each giving `422 VALIDATION_ERROR` or `UNKNOWN_QUALIFICATION_CODE`:

- Codes must exist in the registry.
- `relevant_prior_qualifications` entries: an `ext-` ref must refer to a declared external qualification; any other entry must be a well-formed registry code, held or not yet held, and must exist in the registry (`UNKNOWN_QUALIFICATION_CODE`, checked for every declaration, §4 A-7). A known code that is neither held nor on the evaluated path has no effect, and a declaration never establishes eligibility or a feasible path. (Decided 2026-11-02; until A-7 is implemented the code still requires every entry to be a declared holding.)
- `declarations[].target_code` values must be unique.
- External `ref` values must be unique.

The profile is never stored or logged. Only its SHA-256 digest is logged.

### 2.4 Eligibility result

```text
ComponentResult {
  component_id: string                 // "rule:AMH/Q2301/E9#c1"
  type: ComponentType
  requirement_text: string             // verbatim text of the component's own source cell (canonical; see the component conventions below)
  params: object                       // stored params + "requires_relevance": true when the stored field is true (see the component conventions below)
  verdict: Verdict
  inputs_used: [{ field: string, value: any, evidence_class: "DECLARED"|"CONFIG"|"OFFICIAL"|"HYPOTHETICAL" }]
  evidence_ids: string[]
  condition: Condition | null
  unknown_reason: UnknownReason | null
}
Condition     { kind: ConditionKind, key: string, value: any, evidence_class: EvidenceClass, text: string }
UnknownReason { code: UnknownReasonCode, ref: string, text: string, resolvable_by: "PROFILE"|"CONFIG"|"SOURCE_REVIEW"|"NOT_RESOLVABLE_FROM_CURRENT_SOURCES" }
```

**Component conventions (curated rules, ARCHITECTURE §9.2, §11.2):**

- **Order and identifier.** Components follow the printed cell order (academic or skill cell first, then the experience cell), one component per cell. `component_id` is `<rule id>#c<n>` with n counting from 1; the age rule has the single component `#c1`. `component_id` and `requirement_text` are derived, not stored.
- **`requirement_text`.** The canonical input is the verbatim text of the component's own cell (the matching part of the rule's `raw_text`). Normalised presentation text may be derived from `type` and `params`, but it never replaces the source wording: for an `UNMODELLED` component, and for a component capped by `UNCERTAIN_EXTRACTION`, `ENGINE_USE_UNDECIDED` or `OVERLAY_NOT_APPROVED`, `requirement_text` is the verbatim cell text. The examples below may paraphrase for readability; they are illustrative.
- **`params` by `type`:**

  | `type` | `params` | Types |
  |---|---|---|
  | `AGE_MIN` | `min_age` | integer |
  | `SCHOOL_GRADE_MIN` | `grade`; optional `below_required_verdict` | `grade` integer 0–12; `below_required_verdict` is only `"UNKNOWN"` |
  | `NAMED_CREDENTIAL` | `credential` | a `PostSchoolCredentialType` value (`UG_CERTIFICATE`, `UG_DIPLOMA`) |
  | `PRIOR_NSQF_LEVEL` | `level` | number (stored as a float, for example `3.0`, `2.5`) |
  | `EXPERIENCE_MIN_YEARS` | `years` | number (stored as a float, for example `3.0`, `0.5`) |
  | `UNMODELLED` | none | `{}` |

- **`below_required_verdict`.** `grade` is the threshold. `below_required_verdict` names the verdict returned when the declared grade is *below* that threshold; it never changes which grades satisfy the requirement. It is absent for every row except Sewing Machine Operator row 1 ("Grade 9", decision D5, OV-005), where it is `"UNKNOWN"`. When absent, the ARCHITECTURE §11.2 rule applies (below the threshold → `NOT_MET`). No other value is defined.
- **`requires_relevance` (stored field, response projection).** The stored `Component` keeps `requires_relevance` as its own boolean field; the stored `params` never contain that key (a stored key would collide with the projection). The response views (`ComponentResult.params`, `RuleView.components[].params`) have no separate `requires_relevance` field, so the API contract projects it: the response `params` equal the stored `params` plus `"requires_relevance": true` when the stored field is true, and the key is omitted when it is false (as in the `AGE_MIN` and `UNMODELLED` examples). The examples with `"requires_relevance": true` inside `params` are this projection, not the stored shape. The model shape is unchanged.
- **`or_equivalent`.** Stored as a component field and not projected: no response view exposes it today (whether the UI needs it is a P5 question, not decided here). It changes evaluation only for `NAMED_CREDENTIAL` and `SCHOOL_GRADE_MIN` (Q-3: below the threshold or credential not held → `UNKNOWN` with `EQUIVALENCE_UNDEFINED`, never `NOT_MET`). On an `UNMODELLED` component it has no evaluation effect and does not imply that equivalence is supported (the curated data does not set it there).
- **`safe` and `unknown_reason` (stored).** `safe` says whether the engine may compute the component from a profile. The stored `unknown_reason` is the static cause when it may not. They are distinct, but in curated data `safe = false` implies a non-null `unknown_reason`, and `safe = true` implies a null one (ARCHITECTURE §9.2). The response `ComponentResult.unknown_reason` is a different, per-evaluation value: it is null whenever the verdict is not `UNKNOWN`, and dynamic causes (`INPUT_NOT_DECLARED`, `RELEVANCE_NOT_DECLARED`, `CONFIG_UNSET`, `CREDENTIAL_ORDER_UNDEFINED`, `EQUIVALENCE_UNDEFINED`) are never stored.
- **Static projection of a stored rule.** The fields of `RowResult` and `ComponentResult` that do not depend on a profile are projected from the stored rule by `project_rule` / `project_spec` (`src/skillgraph/curation/eligibility_rules.py`), in the response order: the age rule, then the rows by ascending `s_no`. A rule gives `rule_id`, `raw_text`, `engine_use`, `overlay_ids`, `flags` (a copy of the stored rule's flags; the age rule has the same keys) and, for an eligibility row only, `s_no`, plus `components`. A component gives `component_id` (`<rule id>#c<n>`), `type`, `requirement_text`, `params` (with `requires_relevance: true` only when the stored field is true) and `evidence_ids` (the one evidence record of the component's own cell). `requirement_text` is the verbatim text of the component's own cell (for the age rule, its whole `raw_text`); it is derived, never stored, and never paraphrased. Not projected: `safe`, `or_equivalent`, the stored `unknown_reason` and a component's own `engine_use`. `verdict`, `inputs_used`, `condition` and the per-evaluation `unknown_reason` come from the evaluation (P3), not from the stored rule.
- **`overlay_ids`.** On a rule or row, `overlay_ids` lists only decided overlay rows (applied or interpretation decisions). A pending, unapproved proposal is not listed there; it appears only in the `refs` of the `OVERLAY_PENDING_APPROVAL` flag.

```text

RowResult {
  rule_id: string, s_no: integer, raw_text: string,        // verbatim official row text
  engine_use: EngineUse, overlay_ids: string[],            // decided overlay rows only; pending proposals appear in flags[].refs
  verdict: Verdict, components: ComponentResult[], flags: QualityFlag[]   // flags: the stored rule's quality flags (e.g. UNCERTAIN_EXTRACTION, OVERLAY_PENDING_APPROVAL)
}

EligibilityResult {
  target: QualificationRef
  verdict: Verdict                     // AND(age, OR(rows))
  age: ComponentResult
  rows: RowResult[]                    // ordered by s_no
  decisive_rule_ids: string[]          // rows that attain the target verdict (all rows if NOT_MET)
  conditions: Condition[]              // union over decisive rows, de-duplicated, sorted by key
  unknown_reasons: UnknownReason[]
  supporting_evidence: ExplanationItem[]   // e.g. progression claims (never change the verdict)
  explanation: ExplanationItem[]
  quality_flags: QualityFlag[]
}
QualificationRef { id, code, slug, title, nsqf_level: number | null }
```

---

## 3. Endpoints

| # | Method & path | Purpose | Priority · Phase |
|---|---|---|---|
| E01 | `GET /api/v1/health` | Liveness | MUST · P5 |
| E02 | `GET /api/v1/status` | Build, validation and module availability | MUST · P5 (service P1) |
| E03 | `GET /api/v1/qualifications` | Search or list qualifications | MUST · P5 |
| E04 | `GET /api/v1/qualifications/{slug}` | Qualification detail | MUST · P5 |
| E05 | `GET /api/v1/occupations` | Search or list occupations referenced by qualifications | SHOULD · P5 |
| E06 | `GET /api/v1/occupations/{nco_code}` | Occupation detail plus labour-market context if available | SHOULD · P5 |
| E07 | `POST /api/v1/eligibility/evaluate` | Evaluate a profile against target(s) | MUST · P5 (engine P3) |
| E08 | `GET /api/v1/graph` | Static graph / adjacency for visualisation | MUST · P5 (service P3) |
| E09 | `POST /api/v1/paths/explore` | Enumerate and rank transition paths | MUST · P5 (engine P3) |
| E10 | `GET /api/v1/evidence` | Resolve evidence records | MUST · P5 |
| E11 | `GET /api/v1/conflicts` | Unresolved conflicts and leads | SHOULD · P5 |
| E12 | `GET /api/v1/sources` | Source documents (metadata only) | SHOULD · P5 |
| E13 | `GET /api/v1/labour-market/status` | Module A gate decision and availability | MUST · P5 (decision P2) |
| E14 | `GET /api/v1/labour-market/indicators` | Karnataka indicators | **CONDITIONAL** · P5 after a P2 `GO`/`GO_REDUCED` |

**FUTURE (not in v1):**

- `POST /api/v1/explanations/rephrase`: optional LLM rephrasing (ARCHITECTURE §15.6).
- Any write endpoint.
- Any endpoint that serves source files. **Raw source documents are never served.**

---

### E01 — `GET /api/v1/health`

- **Purpose:** process liveness. Never touches data.
- **Request:** none.
- **Response 200:**

```json
{ "status": "ok", "app_version": "0.1.0", "api_version": "1.0" }
```

- **Errors:** none expected (`500` only).
- **Provenance / warnings:** none.
- **Phase:** P5 (P5.1).

---

### E02 — `GET /api/v1/status`

- **Purpose:** data availability, validation status and module availability. It drives the data-status page and the global banner (journey J6).
- **Request:** none.
- **Response 200** (also returned in degraded mode, with `build.status` ≠ `READY`):

| Field | Type | Notes |
|---|---|---|
| `build.status` | `BuildStatus` | |
| `build.data_build_id` | string \| null | |
| `build.built_at` | string (ISO-8601) \| null | The only timestamp in analytical APIs |
| `build.inputs` | `{raw_run_id, extraction_run_id, overlay_audit_id, approvals_digest}` | |
| `build.overlays` | `{applied: string[], pending: string[], display_only: integer}` | e.g. pending OV-002…004 until approved |
| `counts` | `{qualifications_curated, qualifications_catalogue_only, nos_units, occupations, eligibility_rows, conflicts_open}` | |
| `validation` | `{checks_passed: integer, checks_failed: integer, known_findings: KnownFinding[]}` | `KnownFinding {id: "DQ-01", title, status, refs}`. Registered findings are unresolved data issues, reported separately from check results. They are not accepted or waived. A registered finding whose recorded values change makes a check fail (`TASKS.md` P1.6). |
| `sources_unavailable` | `[{manifest_item_id, title, reason}]` | e.g. C3 (HTTP 404), C4 (not found), D1 (HTTP 404) |
| `modules.skill_graph` | `ModuleStatus` | |
| `modules.labour_market` | `{status: ModuleStatus, gate_decision: GateDecision}` | |
| `config` | `{nsqf_level_match: NsqfLevelMatch, inference_enabled: boolean}` | Server defaults |
| `licence_notice` | string | Fixed text about unconfirmed reuse rights |
| `meta` | Meta | |

```json
{
  "build": {
    "status": "READY",
    "data_build_id": "cb-1a2b3c4d5e6f",
    "built_at": "2026-11-03T10:15:00+05:30",
    "inputs": { "raw_run_id": "2026-10-30", "extraction_run_id": "extracted_2026-10-30",
                "overlay_audit_id": "audit_2026-10-30_m1s1", "approvals_digest": "sha256:…" },
    "overlays": { "applied": ["OV-001", "OV-028"], "pending": ["OV-002", "OV-003", "OV-004", "OV-034", "OV-035"], "display_only": 14 }
  },
  "counts": { "qualifications_curated": 4, "qualifications_catalogue_only": 33, "nos_units": 22,
              "occupations": 4, "eligibility_rows": 24, "conflicts_open": 3 },
  "validation": { "checks_passed": 41, "checks_failed": 0,
    "known_findings": [
      { "id": "DQ-01", "title": "SSMO credit totals conflict (QF rows 12 vs totals 14; N2302 QF 3 vs QP 5)", "status": "UNRESOLVED_SOURCE_CONFLICT", "refs": ["conflict:OV-036"] },
      { "id": "DQ-04", "title": "NCO 3122.3551 title not found in searched sources", "status": "NOT_FOUND", "refs": ["nco:3122.3551"] } ] },
  "sources_unavailable": [ { "manifest_item_id": "C3", "title": "NQR record Specialized Sewing Machine Operator", "reason": "HTTP 404" } ],
  "modules": { "skill_graph": "AVAILABLE", "labour_market": { "status": "NOT_ASSESSED", "gate_decision": "NOT_ASSESSED" } },
  "config": { "nsqf_level_match": null, "inference_enabled": false },
  "licence_notice": "Source reuse permissions are unconfirmed; data is shown for local demonstration only.",
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-01" }
}
```

(The counts and check totals are placeholders.)

(The `build.overlays` values are illustrative and do not match the current data. `applied` lists rows classified `APPLY`, that is, approved `PROPOSED_*` rows written to a curated record: `[]` with the empty approvals file. `OV-001` and `OV-028` are `CONFIRMED_BY_GEOMETRY` and apply nothing. `display_only` is the number of rows classified `DISPLAY` (11 today), not the number whose `engine_use` is `DISPLAY_ONLY` (7). See `TASKS.md` P1.4 and `build_manifest.json`.)

- **Errors:** none besides `500`. A missing build is reported in the body (`NOT_BUILT`), not as `503`.
- **Provenance / warnings:** `known_findings`, `sources_unavailable`, `licence_notice`.
- **Phase:** service in P1 (validation report); HTTP in P5.1.

---

### E03 — `GET /api/v1/qualifications`

- **Purpose:** search and list qualifications (journey J3).
- **Query parameters:**

| Param | Type | Req. | Default | Notes |
|---|---|---|---|---|
| `q` | string (≤ 80) | no | — | Case-insensitive substring match on code, titles and aliases (e.g. QP title "Checker – Inline & Measurement") |
| `nsqf_level` | number | no | — | Exact level |
| `coverage` | `CURATED` \| `CATALOGUE_ONLY` \| `ALL` | no | `CURATED` | |
| `limit` | integer 1–100 | no | 50 | |
| `offset` | integer ≥ 0 | no | 0 | |

- **Response 200:** `{ items: QualificationSummary[], total: integer, meta }`, sorted by `code`.

```text
QualificationSummary { id, code, slug, title, coverage: Coverage, nsqf_level: Valued<number>,
                       official_hours_total: Valued<number>, min_age: Valued<integer> | null,
                       nco_codes: string[], quality_flag_count: integer }
```

```json
{
  "items": [
    { "id": "qual:AMH/Q2301", "code": "AMH/Q2301", "slug": "AMH.Q2301",
      "title": "Specialized Sewing Machine Operator", "coverage": "CURATED",
      "nsqf_level": { "value": 3.5, "evidence_class": "OFFICIAL", "evidence_id": "ev:a1b2c3d4e5f60708",
                      "value_status": "TRANSCRIBED", "engine_use": "SAFE_HARD_RULE", "conflict_id": null },
      "official_hours_total": { "value": 420, "evidence_class": "OFFICIAL", "evidence_id": "ev:b2c3d4e5f6071809",
                                "value_status": "TRANSCRIBED", "engine_use": "SAFE_HOURS", "conflict_id": null },
      "min_age": { "value": 18, "evidence_class": "OFFICIAL", "evidence_id": "ev:c3d4e5f607182930",
                   "value_status": "CONFIRMED_BY_GEOMETRY", "engine_use": "SAFE_HARD_RULE", "conflict_id": null },
      "nco_codes": ["8153.0103"], "quality_flag_count": 4 }
  ],
  "total": 1,
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-02" }
}
```

For `CATALOGUE_ONLY` items, `nsqf_level` and `official_hours_total` come from the AMHSSC catalogue (`src:A1`, `OFFICIAL`), and `min_age` is `null`.

- **Errors:** `422 VALIDATION_ERROR`; `503 DATA_NOT_BUILT`.
- **Provenance:** `Valued.evidence_id` on every fact.
- **Warnings:** `quality_flag_count` (details in E04).
- **Phase:** P5.2.

---

### E04 — `GET /api/v1/qualifications/{slug}`

- **Purpose:** the full evidence-linked view of one qualification (journeys J3 and J2 context).
- **Path parameter:** `slug`, e.g. `AMH.Q2301`.
- **Response 200:** `QualificationDetail`.

| Field | Type | Notes |
|---|---|---|
| `id`, `code`, `slug`, `coverage`, `nqr_code` | string | |
| `titles` | `{qf, qp, catalogue}` (strings or null) + `flags` | `TITLE_VARIANT` when they differ (DQ-05) |
| `nsqf_level`, `min_age` | `Valued` | |
| `hours` | `{theory, practical, ojt_mandatory, ojt_recommended, total}`, each `Valued<number>` | QF item 13; `engine_use = SAFE_HOURS` |
| `credits` | `Valued<number>` | Always `engine_use = NOT_USED`; `conflict_id` set for SSMO (DQ-01) |
| `nos` | `NosMembershipView[]`, sorted by `s_no` | `{nos_id or module_id, code or null, title, s_no, core_or_noncore, is_bridge, nsqf_level: Valued, version: Valued, hours: {…Valued}, credits: Valued(NOT_USED), flags}` |
| `eligibility` | `{age_rule: RuleView, rows: RuleView[]}` | `RuleView {rule_id, s_no, raw_text, components: [{type, requirement_text, params, safe}], engine_use, overlay_ids, flags}` |
| `progression_claims` | `[{id, text_verbatim, direction_label, engine_use: "DISPLAY_ONLY", resolved_target: {code, evidence_class: "INFERENCE"} or null, evidence_id}]` | Never an official edge to another code |
| `occupations` | `[{id, nco_code, title or null, title_verification, evidence_id}]` | DQ-04 → `NOT_FOUND`, `title: null` |
| `conflicts` | `ConflictView[]` (see E11) | |
| `quality_flags` | `QualityFlag[]` | |
| `sources` | `SourceRef[]` | Primary and secondary documents used |
| `meta` | Meta | |

```json
{
  "id": "qual:AMH/Q2301", "code": "AMH/Q2301", "slug": "AMH.Q2301", "coverage": "CURATED",
  "nqr_code": "QG-3.5-AP-01871-2024-V1.1-AMHSSC",
  "titles": { "qf": "Specialized Sewing Machine Operator", "qp": "Specialized Sewing Machine Operator",
              "catalogue": "Specialized Sewing Machine Operator", "flags": [] },
  "nsqf_level": { "value": 3.5, "evidence_class": "OFFICIAL", "evidence_id": "ev:a1b2c3d4e5f60708", "value_status": "TRANSCRIBED", "engine_use": "SAFE_HARD_RULE", "conflict_id": null },
  "min_age": { "value": 18, "evidence_class": "OFFICIAL", "evidence_id": "ev:c3d4e5f607182930", "value_status": "CONFIRMED_BY_GEOMETRY", "engine_use": "SAFE_HARD_RULE", "conflict_id": null },
  "hours": {
    "theory":          { "value": 150, "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "SAFE_HOURS", "conflict_id": null },
    "practical":       { "value": 270, "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "SAFE_HOURS", "conflict_id": null },
    "ojt_mandatory":   { "value": 0,   "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "SAFE_HOURS", "conflict_id": null },
    "ojt_recommended": { "value": 0,   "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "SAFE_HOURS", "conflict_id": null },
    "total":           { "value": 420, "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "SAFE_HOURS", "conflict_id": null }
  },
  "credits": { "value": 14, "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "NOT_USED", "conflict_id": "conflict:OV-036" },
  "nos": [
    { "module_id": "mod:AMH/Q2301/S1", "code": null, "title": "Introduction (Bridge Module)", "s_no": 1,
      "core_or_noncore": "Core", "is_bridge": true,
      "hours": { "total": { "value": 3, "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "SAFE_HOURS", "conflict_id": null } },
      "flags": [ { "code": "SOURCE_UNAVAILABLE", "severity": "INFO",
                   "message": "An earlier research lead compared 150 h (NQR) with 147 h + 3 h bridge (QF) for AMH/N2301; the NQR record returned HTTP 404, so the comparison was not performed.",
                   "refs": ["src:C3"] } ] },
    { "nos_id": "nos:DGT/VSQ/N0102", "code": "DGT/VSQ/N0102", "title": "Employability Skills(60 Hours)", "s_no": 7,
      "core_or_noncore": "Non-Core", "is_bridge": false,
      "nsqf_level": { "value": 3.5, "evidence_class": "OFFICIAL", "evidence_id": "ev:…", "value_status": "TRANSCRIBED", "engine_use": "DISPLAY_ONLY", "conflict_id": "conflict:OV-040" },
      "flags": [ { "code": "SOURCE_CONFLICT", "severity": "CAUTION", "message": "QF states NSQF 3.5; QP states 4. No value selected.", "refs": ["conflict:OV-040"] } ] }
  ],
  "eligibility": {
    "age_rule": { "rule_id": "rule:AMH/Q2301/AGE", "s_no": null, "raw_text": "Age: 18 years",
                  "components": [ { "type": "AGE_MIN", "requirement_text": "Age ≥ 18", "params": { "min_age": 18 }, "safe": true } ],
                  "engine_use": "SAFE_HARD_RULE", "overlay_ids": ["OV-029"], "flags": [] },
    "rows": [
      { "rule_id": "rule:AMH/Q2301/E9", "s_no": 9,
        "raw_text": "Previous relevant Qualification of NSQF Level 2.5 || 3 year relevant experience",
        "components": [
          { "type": "PRIOR_NSQF_LEVEL", "requirement_text": "Relevant prior qualification at NSQF Level 2.5 (interpretation per config)", "params": { "level": 2.5, "requires_relevance": true }, "safe": true },
          { "type": "EXPERIENCE_MIN_YEARS", "requirement_text": "≥ 3 years relevant experience", "params": { "years": 3.0, "requires_relevance": true }, "safe": true } ],
        "engine_use": "CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG", "overlay_ids": ["OV-019"], "flags": [] }
    ]
  },
  "progression_claims": [
    { "id": "claim:AMH/Q2301/P1", "text_verbatim": "Sampling Coordinator(Vertical)", "direction_label": "Vertical",
      "engine_use": "DISPLAY_ONLY", "resolved_target": null, "evidence_id": "ev:…" } ],
  "occupations": [ { "id": "nco:8153.0103", "nco_code": "8153.0103", "title": "Specialized Sewing Machine Operator",
                     "title_verification": "VERIFIED_IN_SOURCE", "evidence_id": "ev:…" } ],
  "conflicts": [ { "id": "conflict:OV-036", "subject": "credits (N2302 and totals)", "status": "UNRESOLVED_SOURCE_CONFLICT", "engine_effect": "NOT_USED" } ],
  "quality_flags": [ { "code": "NUMBERING_GAP", "severity": "INFO", "message": "Printed NOS S.No. 6 is absent; no row is missing.", "refs": ["OV-041"] } ],
  "sources": [ { "id": "src:A5", "title": "Specialized Sewing Machine Operator QF", "org": "AMHSSC", "sha256": "607d1b38…", "licence_status": "UNCONFIRMED", "role": "PRIMARY" } ],
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-03" }
}
```

(The example is abridged: other NOS rows and eligibility rows 1–8 are omitted.)

- **Errors:** `404 NOT_FOUND`; `503 DATA_NOT_BUILT`. A `CATALOGUE_ONLY` record returns `200` with `nos`, `eligibility` and `progression_claims` empty, plus the flag `INFO "Catalogue entry only; QF evidence not acquired"`.
- **Provenance:** every factual field is a `Valued` with an `evidence_id`.
- **Warnings:** see `flags`, `conflicts` and `quality_flags`.
- **Phase:** P5.2.

---

### E05 — `GET /api/v1/occupations`

- **Purpose:** list or search the NCO-2015 occupations referenced by qualifications.
- **Query:** `q` (string, optional; matches the code or a verified title), `limit` (1–100, default 50), `offset`.
- **Response 200:** `{ items: OccupationSummary[], total, meta }`, sorted by `nco_code`.

```text
OccupationSummary { id, nco_code, title: string | null, title_verification: TitleVerification,
                    nco_levels: { division: string, sub_division: string, group: string, family: string },
                    qualification_codes: string[] }
```

```json
{ "items": [
    { "id": "nco:3122.3551", "nco_code": "3122.3551", "title": null, "title_verification": "NOT_FOUND",
      "nco_levels": { "division": "3", "sub_division": "31", "group": "312", "family": "3122" },
      "qualification_codes": ["AMH/Q2101"] } ],
  "total": 1, "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-04" } }
```

`nco_levels` is `RULE_DERIVED` from the code structure. Labels for those levels are shown only if they are verified in a source.

- **Errors:** `422`; `503 DATA_NOT_BUILT`.
- **Warnings:** `NCO_TITLE_NOT_FOUND`.
- **Phase:** P5.2 (SHOULD).

---

### E06 — `GET /api/v1/occupations/{nco_code}`

- **Purpose:** occupation detail, mapped qualifications, and labour-market context (journey J5).
- **Response 200:** `OccupationSummary` + `evidence_ids` + `flags` + `labour_market`.

```text
labour_market {
  module_status: ModuleStatus, gate_decision: GateDecision,
  reason: string | null,                // when not AVAILABLE
  context_level: "DIVISION"|"SUB_DIVISION"|"GROUP" | null,
  indicators: IndicatorRow[] | null     // see E14; null unless AVAILABLE
}
```

```json
{ "id": "nco:8153.0101", "nco_code": "8153.0101", "title": "Sewing Machine Operator, General",
  "title_verification": "VERIFIED_IN_SOURCE",
  "nco_levels": { "division": "8", "sub_division": "81", "group": "815", "family": "8153" },
  "qualification_codes": ["AMH/Q0301"], "evidence_ids": ["ev:…"], "flags": [],
  "labour_market": { "module_status": "NOT_ASSESSED", "gate_decision": "NOT_ASSESSED",
                     "reason": "Labour-market feasibility gate has not been run.", "context_level": null, "indicators": null },
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-05" } }
```

- **Errors:** `404 NOT_FOUND`; `503 DATA_NOT_BUILT`. Module A being unavailable is **not** an error here.
- **Warnings:** `AGGREGATION_CONTEXT_ONLY` on any indicator joined above the 8-digit level.
- **Phase:** P5.2 (SHOULD); the `labour_market` block is populated only after a P2 `GO`/`GO_REDUCED`.

---

### E07 — `POST /api/v1/eligibility/evaluate`

- **Purpose:** evaluate a hypothetical profile against one or more targets, with full per-row and per-component reasoning (journey J2).
- **Request body:**

| Field | Type | Req. | Notes |
|---|---|---|---|
| `profile` | `HypotheticalProfile` | yes | §2.3 |
| `target_codes` | string[1–50] | yes | Must be `CURATED` (otherwise `422 TARGET_NOT_EVALUABLE`) |
| `config` | `EngineConfig` | no | Overrides the server default |

```json
{
  "profile": {
    "label": "Demo profile A (hypothetical)",
    "age_years": 24,
    "school_grade_passed": 10,
    "post_school_credentials": [],
    "held_qualification_codes": ["AMH/Q0301"],
    "external_qualifications": [],
    "declarations": [
      { "target_code": "AMH/Q2301", "relevant_experience_years": 3, "relevant_prior_qualifications": ["AMH/Q0301"] }
    ]
  },
  "target_codes": ["AMH/Q2301"],
  "config": { "nsqf_level_match": "exact" }
}
```

- **Response 200:** `{ results: EligibilityResult[], effective_config: EngineConfig, profile_digest: string, meta }`. `results` follows the order of `target_codes`.

```json
{
  "results": [ {
    "target": { "id": "qual:AMH/Q2301", "code": "AMH/Q2301", "slug": "AMH.Q2301", "title": "Specialized Sewing Machine Operator", "nsqf_level": 3.5 },
    "verdict": "CONDITIONAL",
    "age": { "component_id": "rule:AMH/Q2301/AGE#c1", "type": "AGE_MIN", "requirement_text": "Age ≥ 18", "params": { "min_age": 18 },
             "verdict": "MET", "inputs_used": [ { "field": "profile.age_years", "value": 24, "evidence_class": "DECLARED" } ],
             "evidence_ids": ["ev:c3d4e5f607182930"], "condition": null, "unknown_reason": null },
    "rows": [
      { "rule_id": "rule:AMH/Q2301/E9", "s_no": 9,
        "raw_text": "Previous relevant Qualification of NSQF Level 2.5 || 3 year relevant experience",
        "engine_use": "CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG", "overlay_ids": ["OV-019"], "verdict": "CONDITIONAL",
        "components": [
          { "component_id": "rule:AMH/Q2301/E9#c1", "type": "PRIOR_NSQF_LEVEL",
            "requirement_text": "Relevant prior qualification at NSQF Level 2.5 (exact)", "params": { "level": 2.5, "requires_relevance": true },
            "verdict": "CONDITIONAL",
            "inputs_used": [
              { "field": "profile.held_qualification_codes", "value": ["AMH/Q0301"], "evidence_class": "DECLARED" },
              { "field": "qual:AMH/Q0301.nsqf_level", "value": 2.5, "evidence_class": "OFFICIAL" },
              { "field": "config.nsqf_level_match", "value": "exact", "evidence_class": "CONFIG" } ],
            "evidence_ids": ["ev:…"],
            "condition": { "kind": "DECLARATION", "key": "declarations[AMH/Q2301].relevant_prior_qualifications",
                           "value": ["AMH/Q0301"], "evidence_class": "DECLARED",
                           "text": "Holds only if Sewing Machine Operator is relevant to this qualification (your declaration; not verified)." },
            "unknown_reason": null },
          { "component_id": "rule:AMH/Q2301/E9#c2", "type": "EXPERIENCE_MIN_YEARS",
            "requirement_text": "≥ 3 years relevant experience", "params": { "years": 3.0, "requires_relevance": true },
            "verdict": "CONDITIONAL",
            "inputs_used": [ { "field": "declarations[AMH/Q2301].relevant_experience_years", "value": 3, "evidence_class": "DECLARED" } ],
            "evidence_ids": ["ev:…"],
            "condition": { "kind": "DECLARATION", "key": "declarations[AMH/Q2301].relevant_experience_years", "value": 3,
                           "evidence_class": "DECLARED", "text": "Holds only if your 3 years of experience are relevant (your declaration; not verified)." },
            "unknown_reason": null } ],
        "flags": [] },
      { "rule_id": "rule:AMH/Q2301/E2", "s_no": 2, "raw_text": "Completed 1st year of 3-year diploma after 10th. || ",
        "engine_use": "UNKNOWN", "overlay_ids": ["OV-012"], "verdict": "UNKNOWN",
        "components": [
          { "component_id": "rule:AMH/Q2301/E2#c1", "type": "UNMODELLED", "requirement_text": "Completed 1st year of 3-year diploma after 10th.",
            "params": {}, "verdict": "UNKNOWN", "inputs_used": [], "evidence_ids": ["ev:…"], "condition": null,
            "unknown_reason": { "code": "DIPLOMA_YEAR_NOT_MODELLED", "ref": "rule:AMH/Q2301/E2#c1",
                                "text": "Diploma-year routes are not modelled in profiles.", "resolvable_by": "SOURCE_REVIEW" } } ],
        "flags": [ { "code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "Proposed experience value (OV-002) is not applied.", "refs": ["OV-002"] } ] }
    ],
    "decisive_rule_ids": ["rule:AMH/Q2301/E9"],
    "conditions": [
      { "kind": "CONFIG", "key": "config.nsqf_level_match", "value": "exact", "evidence_class": "CONFIG",
        "text": "Uses the interpretation that 'Level 2.5' means exactly 2.5." },
      { "kind": "DECLARATION", "key": "declarations[AMH/Q2301].relevant_experience_years", "value": 3, "evidence_class": "DECLARED", "text": "…" },
      { "kind": "DECLARATION", "key": "declarations[AMH/Q2301].relevant_prior_qualifications", "value": ["AMH/Q0301"], "evidence_class": "DECLARED", "text": "…" } ],
    "unknown_reasons": [],
    "supporting_evidence": [
      { "kind": "PROGRESSION_CLAIM", "text": "The Sewing Machine Operator QF (item 15) lists 'Specialized Sewing Machine Operator (Vertical)' as a progression. Supporting evidence only; it does not change the verdict.",
        "evidence_class": "OFFICIAL", "evidence_ids": ["ev:…"], "flags": [] } ],
    "explanation": [
      { "kind": "VERDICT_SUMMARY", "text": "Conditional: an entry route exists if your declarations hold and 'Level 2.5' is read as exactly 2.5.", "evidence_class": "RULE_DERIVED", "evidence_ids": [], "flags": ["DEPENDS_ON_DECLARATION", "DEPENDS_ON_CONFIG"] },
      { "kind": "CAVEAT", "text": "This is an eligibility reading of official documents, not a prediction of admission, employability, placement or earnings.", "evidence_class": "RULE_DERIVED", "evidence_ids": [], "flags": [] } ],
    "quality_flags": [ { "code": "DEPENDS_ON_DECLARATION", "severity": "CAUTION", "message": "Relevance is self-declared and unverified.", "refs": [] } ]
  } ],
  "effective_config": { "nsqf_level_match": "exact" },
  "profile_digest": "sha256:4be1…",
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-06" }
}
```

(The example is abridged: rows 1 and 3–8 are omitted. The verdicts are illustrative.)

- **Errors:** `422 VALIDATION_ERROR` / `UNKNOWN_QUALIFICATION_CODE` / `TARGET_NOT_EVALUABLE` / `LIMIT_EXCEEDED`; `503 DATA_NOT_BUILT`.
- **Provenance:** `evidence_ids` per component; `inputs_used[].evidence_class`; `conditions`.
- **Warnings:** `DEPENDS_ON_DECLARATION`, `DEPENDS_ON_CONFIG`, `UNCERTAIN_EXTRACTION`, `SOURCE_CONFLICT`, `OVERLAY_PENDING_APPROVAL`.
- **Invariants (tested):**
  - With `nsqf_level_match: null`, every `PRIOR_NSQF_LEVEL` component is `UNKNOWN` with `CONFIG_UNSET` whenever the profile declares at least one prior qualification. A profile that declares none gets `NOT_MET` (ARCHITECTURE §11.2).
  - Credits never appear in `inputs_used`.
- **Phase:** engine P3 (P3.2–P3.3); HTTP P5.3.

---

### E08 — `GET /api/v1/graph`

- **Purpose:** the profile-independent graph, either whole or a neighbourhood, for adjacency inspection and visualisation (journey J4). Feasibility is **not** part of this view. It needs a profile (E07 and E09).
- **Query parameters:**

| Param | Type | Req. | Default | Notes |
|---|---|---|---|---|
| `focus` | node id (e.g. `qual:AMH/Q0103`, `nco:7543.0301`) | no | — | Omitted → whole curated graph |
| `depth` | integer 1–2 | no | 1 | Hops from `focus` |
| `include_inference` | boolean | no | `false` | Adds `NCO_GROUP_PROXIMITY` / `TITLE_SIMILARITY` edges, marked `experimental: true` |
| `node_types` | comma list of `NodeType` | no | all | Filter |
| `include_catalogue_only` | boolean | no | `false` | Adds `CATALOGUE_ONLY` qualification nodes (no edges except `ALIGNED_TO_NCO` if stated in the catalogue; usually none) |

- **Response 200:** `{ nodes: GraphNode[], edges: GraphEdge[], legend: LegendEntry[], meta }`. Nodes are sorted by `id`; edges by `(type, source, target)`.

```text
GraphNode { id, type: NodeType, label: string, slug: string | null, attributes: object, flags: QualityFlag[] }
GraphEdge { id: string, type: EdgeType, source: string, target: string, directed: boolean,
            evidence_class: EvidenceClass, experimental: boolean,
            attributes: object, evidence_ids: string[], flags: QualityFlag[] }
LegendEntry { edge_type: EdgeType, evidence_class: EvidenceClass, meaning: string, does_not_mean: string }
```

`SHARES_NOS.attributes` = `{shared_codes: string[], core_shared_count: integer, noncore_shared_count: integer, version_agreement: {code: "SAME"|"DIFFERENT"|"NOT_STATED"}}`.

```json
{
  "nodes": [
    { "id": "qual:AMH/Q0103", "type": "QUALIFICATION", "label": "Inline Checker - Sewing", "slug": "AMH.Q0103", "attributes": { "nsqf_level": 3.5, "coverage": "CURATED" }, "flags": [] },
    { "id": "qual:AMH/Q2301", "type": "QUALIFICATION", "label": "Specialized Sewing Machine Operator", "slug": "AMH.Q2301", "attributes": { "nsqf_level": 3.5, "coverage": "CURATED" }, "flags": [] }
  ],
  "edges": [
    { "id": "e:SHARES_NOS:AMH/Q0103:AMH/Q2301", "type": "SHARES_NOS", "source": "qual:AMH/Q0103", "target": "qual:AMH/Q2301",
      "directed": false, "evidence_class": "RULE_DERIVED", "experimental": false,
      "attributes": { "shared_codes": ["AMH/N0309", "DGT/VSQ/N0102"], "core_shared_count": 0, "noncore_shared_count": 2,
                      "version_agreement": { "AMH/N0309": "NOT_STATED", "DGT/VSQ/N0102": "NOT_STATED" } },
      "evidence_ids": ["ev:…"],
      "flags": [ { "code": "SOURCE_CONFLICT", "severity": "INFO", "message": "DGT/VSQ/N0102 level differs between the SSMO QF and QP.", "refs": ["conflict:OV-040"] } ] }
  ],
  "legend": [
    { "edge_type": "SHARES_NOS", "evidence_class": "RULE_DERIVED",
      "meaning": "Both qualifications list the same NOS code in their official QF.",
      "does_not_mean": "Skills are equivalent, units are exempt, or people move between these roles." }
  ],
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-07" }
}
```

(The example is abridged, and the `version_agreement` values are illustrative.)

- **Errors:** `404 NOT_FOUND` (unknown `focus`); `422`; `503 DATA_NOT_BUILT`.
- **Provenance:** `evidence_class` and `evidence_ids` per edge.
- **Warnings:** `INFERENCE_EXPERIMENTAL` on every inference edge; `legend.does_not_mean` is always present.
- **Phase:** service P3 (P3.4–P3.5); HTTP P5.4.

---

### E09 — `POST /api/v1/paths/explore`

- **Purpose:** enumerate, rank and explain multi-step transition paths for a hypothetical profile (journey J1).
- **Request body:**

| Field | Type | Req. | Default | Notes |
|---|---|---|---|---|
| `profile` | `HypotheticalProfile` | yes | — | The start state |
| `target_code` | string | no | — | If given, only paths ending at this `CURATED` qualification; if omitted, all reachable qualifications |
| `max_steps` | integer 1–4 | no | 3 | > 4 → `422 LIMIT_EXCEEDED` |
| `sort_by` | `PathSortKey` | no | `OFFICIAL_HOURS` | The verdict class is always the first key |
| `limit` | integer 1–100 | no | 20 | |
| `include_blocked` | boolean | no | `false` | Adds `blocked[]` (first-step targets that are `NOT_MET`, with reasons) |
| `include_inference` | boolean | no | `false` | Adds `inference_annotations` to steps; **never changes paths or verdicts** |
| `config` | `EngineConfig` | no | server default | |
| `scenario` | `Scenario` | no | all defaults | Non-default values mark affected paths `HYPOTHETICAL` |

```json
{
  "profile": { "label": "Demo profile A (hypothetical)", "age_years": 24, "school_grade_passed": 10,
               "post_school_credentials": [], "held_qualification_codes": ["AMH/Q0301"], "external_qualifications": [],
               "declarations": [
                 { "target_code": "AMH/Q2301", "relevant_experience_years": 3, "relevant_prior_qualifications": ["AMH/Q0301"] },
                 { "target_code": "AMH/Q0103", "relevant_experience_years": 3, "relevant_prior_qualifications": ["AMH/Q0301"] } ] },
  "max_steps": 2,
  "sort_by": "OFFICIAL_HOURS",
  "include_blocked": true,
  "config": { "nsqf_level_match": "exact" },
  "scenario": { "assume_intermediate_relevance": false, "assumed_experience_gain_years_per_step": 0, "incremental_hours_policy": "NONE" }
}
```

- **Response 200:**

| Field | Type | Notes |
|---|---|---|
| `paths` | `Path[]` | Ranked; `NOT_MET` paths are never included |
| `blocked` | `[{target: QualificationRef, verdict: "NOT_MET", reasons: ExplanationItem[]}]` or `[]` | Only with `include_blocked` |
| `counts` | `{enumerated: integer, returned: integer, truncated: boolean}` | |
| `request_echo` | `{max_steps, sort_by, effective_config, scenario, target_code, profile_digest}` | |
| `meta` | Meta | |

```text
Path {
  path_id: string, rank: integer, verdict: Verdict, is_hypothetical: boolean,
  evidence_classes_present: EvidenceClass[],
  steps: PathStep[],
  totals: { steps: integer, official_hours: number, hypothetical_incremental_hours: number | null,
            assumption_count: integer, quality_flag_count: integer, documented_shared_nos: integer },
  sort_values: { verdict_rank: integer, primary: number, tie_breakers: number[] },   // tie_breakers: [assumptions, steps, quality_flags, official_hours] minus the selected key
  explanation: ExplanationItem[]
}
PathStep {
  index: integer (1-based), from_state: string[]  // codes held (declared or hypothetical) before this step
  edge_type: "ELIGIBILITY_ROUTE",
  target: QualificationRef,
  eligibility: { verdict, decisive_rule_ids, conditions, unknown_reasons },   // full detail via E07
  official_hours: { theory, practical, ojt_mandatory, ojt_recommended, total } (numbers), official_hours_evidence_id: string,
  hypothetical_incremental_hours: number | null,                              // only if the policy ≠ NONE
  evidence_backed_incremental_hours: null,                                    // always null in v1 (NO_OFFICIAL_REDUCTION_SOURCE)
  shared_nos_with_held: { codes: string[], core_count: integer } | null,
  progression_claim: { claim_id, text_verbatim } | null,                      // only if a held qualification's QF names the target exactly; display only
  inference_annotations: [{ type: EdgeType, text: string, experimental: true }] | null,
  quality_flags: QualityFlag[]
}
```

```json
{
  "paths": [
    { "path_id": "p-3c9e0a1b2d4f", "rank": 1, "verdict": "CONDITIONAL", "is_hypothetical": false,
      "evidence_classes_present": ["OFFICIAL", "RULE_DERIVED", "DECLARED", "CONFIG"],
      "steps": [
        { "index": 1, "from_state": ["AMH/Q0301"], "edge_type": "ELIGIBILITY_ROUTE",
          "target": { "id": "qual:AMH/Q2301", "code": "AMH/Q2301", "slug": "AMH.Q2301", "title": "Specialized Sewing Machine Operator", "nsqf_level": 3.5 },
          "eligibility": { "verdict": "CONDITIONAL", "decisive_rule_ids": ["rule:AMH/Q2301/E9"], "conditions": [ "…" ], "unknown_reasons": [] },
          "official_hours": { "theory": 150, "practical": 270, "ojt_mandatory": 0, "ojt_recommended": 0, "total": 420 },
          "official_hours_evidence_id": "ev:…",
          "hypothetical_incremental_hours": null, "evidence_backed_incremental_hours": null,
          "shared_nos_with_held": { "codes": [], "core_count": 0 },
          "progression_claim": { "claim_id": "claim:AMH/Q0301/P2", "text_verbatim": "Specialized Sewing Machine Operator(Vertical)" },
          "inference_annotations": null,
          "quality_flags": [ { "code": "NO_OFFICIAL_REDUCTION_SOURCE", "severity": "INFO", "message": "Full official hours shown; no source defines a reduced route.", "refs": [] } ] }
      ],
      "totals": { "steps": 1, "official_hours": 420, "hypothetical_incremental_hours": null, "assumption_count": 3, "quality_flag_count": 1, "documented_shared_nos": 0 },
      "sort_values": { "verdict_rank": 2, "primary": 420, "tie_breakers": [3, 1, 1] },
      "explanation": [
        { "kind": "PATH_SUMMARY", "text": "One step: Specialized Sewing Machine Operator (420 official notional hours). Conditional on 2 declarations and 1 configuration choice.", "evidence_class": "RULE_DERIVED", "evidence_ids": ["ev:…"], "flags": ["DEPENDS_ON_DECLARATION", "DEPENDS_ON_CONFIG"] },
        { "kind": "OVERLAP", "text": "No NOS code is shared with Sewing Machine Operator.", "evidence_class": "RULE_DERIVED", "evidence_ids": ["ev:…"], "flags": [] },
        { "kind": "CAVEAT", "text": "A path is a reading of entry rules, not a prediction of employability, placement or earnings.", "evidence_class": "RULE_DERIVED", "evidence_ids": [], "flags": [] } ] }
  ],
  "blocked": [
    { "target": { "id": "qual:AMH/Q2101", "code": "AMH/Q2101", "slug": "AMH.Q2101", "title": "Production Supervisor - Sewing", "nsqf_level": 5 },
      "verdict": "NOT_MET",
      "reasons": [ { "kind": "BLOCKED_REASON", "text": "Illustrative only: the reason text names the specific rows and components that failed.", "evidence_class": "RULE_DERIVED", "evidence_ids": [], "flags": [] } ] }
  ],
  "counts": { "enumerated": 3, "returned": 1, "truncated": false },
  "request_echo": { "max_steps": 2, "sort_by": "OFFICIAL_HOURS", "effective_config": { "nsqf_level_match": "exact" },
                    "scenario": { "assume_intermediate_relevance": false, "assumed_experience_gain_years_per_step": 0, "incremental_hours_policy": "NONE" },
                    "target_code": null, "profile_digest": "sha256:4be1…" },
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-08" }
}
```

(Illustrative: the verdicts, the counts and whether PS is `NOT_MET` or `UNKNOWN` are determined by the engine. In particular, PS may well be `UNKNOWN` because of the "or equivalent" branches; see open question Q-3.)

- **Errors:** `422 VALIDATION_ERROR` / `UNKNOWN_QUALIFICATION_CODE` / `TARGET_NOT_EVALUABLE` / `LIMIT_EXCEEDED`; `503 DATA_NOT_BUILT`.
- **Provenance:** per-step evidence IDs; `evidence_classes_present`; full component detail via E07 using the same profile.
- **Warnings:** `HYPOTHETICAL_SCENARIO` on any path affected by a non-default scenario; `INFERENCE_EXPERIMENTAL` on annotations; `NO_OFFICIAL_REDUCTION_SOURCE`.
- **Invariants (tested):**
  - Determinism.
  - `include_inference` never changes `paths[].path_id`, verdicts or order.
  - No `NOT_MET` path appears in `paths`.
  - The `paths[].totals.official_hours` sum equals the sum of the steps' `official_hours.total`.
- **Phase:** engine P3 (P3.6–P3.8); HTTP P5.4.

---

### E10 — `GET /api/v1/evidence`

- **Purpose:** resolve stored evidence records for the evidence drawer.
- **Query:** `ids`, a comma-separated list of 1–50 evidence IDs (required).
- **Response 200:** `{ items: Evidence[], missing: string[], meta }`, in request order. Unknown IDs go to `missing` and do not cause an error, unless all are unknown, in which case the response is `404`.

```json
{ "items": [
    { "id": "ev:b2c3d4e5f6071809", "evidence_class": "OFFICIAL",
      "source": { "id": "src:A5", "title": "Specialized Sewing Machine Operator QF", "org": "AMHSSC", "sha256": "607d1b38…", "licence_status": "UNCONFIRMED", "role": "PRIMARY" },
      "page": "3-4", "location": "QF Section 1, item 13 (hours total)", "method": "pdfplumber_table",
      "value_status": "TRANSCRIBED", "overlay_ids": [], "decision_refs": [], "derived_from": [], "note": null } ],
  "missing": [],
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-09" } }
```

- **Errors:** `422 VALIDATION_ERROR` (no IDs, more than 50 → `LIMIT_EXCEEDED`); `404 NOT_FOUND` (all unknown); `503 DATA_NOT_BUILT`.
- **Provenance:** this endpoint *is* the provenance. No source text beyond short official values is returned, and **no source file is served**.
- **Phase:** P5.5.

---

### E11 — `GET /api/v1/conflicts`

- **Purpose:** list open conflicts and unverifiable leads (the data-steward view).
- **Query:** `qualification_code` (optional filter).
- **Response 200:** `{ items: ConflictView[], meta }`, sorted by `id`.

```text
ConflictView { id, subject: string, entity_ids: string[], status: "UNRESOLVED_SOURCE_CONFLICT"|"UNRESOLVED_LEAD_SOURCE_UNAVAILABLE",
               values: [{ value: any, evidence_id: string, source_title: string }],
               decision_ref: string | null, engine_effect: "NOT_USED"|"DISPLAY_ONLY"|"UNKNOWN_IF_USED", note: string }
```

```json
{ "items": [
    { "id": "conflict:OV-040", "subject": "NSQF level of DGT/VSQ/N0102 within AMH/Q2301",
      "entity_ids": ["qual:AMH/Q2301", "nos:DGT/VSQ/N0102"], "status": "UNRESOLVED_SOURCE_CONFLICT",
      "values": [ { "value": 3.5, "evidence_id": "ev:…", "source_title": "Specialized Sewing Machine Operator QF" },
                  { "value": 4,   "evidence_id": "ev:…", "source_title": "Specialized Sewing Machine Operator QP" } ],
      "decision_ref": null, "engine_effect": "DISPLAY_ONLY", "note": "No value selected." } ],
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-10" } }
```

- **Errors:** `422` (unknown code); `503 DATA_NOT_BUILT`.
- **Phase:** P5.5 (SHOULD). The data is built in P1.4.

---

### E12 — `GET /api/v1/sources`

- **Purpose:** list source documents, as metadata only.
- **Response 200:** `{ items: SourceView[], meta }`, sorted by `manifest_item_id`.

```text
SourceView { id, manifest_item_id, title, org, url, retrieved_at, sha256 | null, file_type | null,
             validation_status, licence_status, role, available: boolean, unavailable_reason: string | null }
```

- **Errors:** `503 DATA_NOT_BUILT`.
- **Warnings:** `LICENCE_UNCONFIRMED` on every item until confirmed; `SOURCE_UNAVAILABLE` for C3, C4 and D1.
- **Phase:** P5.5 (SHOULD).

---

### E13 — `GET /api/v1/labour-market/status`

- **Purpose:** always-available report of the Module A gate decision (ARCHITECTURE §21). The UI uses it to decide between showing indicators and showing "deferred".
- **Response 200:**

```json
{
  "module_status": "DEFERRED",
  "gate_decision": "NO_GO",
  "decided_on": "2026-11-05",
  "criteria": [
    { "id": "FG-1", "name": "Access", "result": "PASS", "note": "…" },
    { "id": "FG-5", "name": "Sample adequacy", "result": "FAIL", "note": "…" }
  ],
  "decision_record": "docs/decisions/MODULE_A_GATE.md",
  "available_indicators": [],
  "meta": { "api_version": "1.0", "data_build_id": "cb-1a2b3c4d5e6f", "config_digest": "sha256:…", "request_id": "req-11" }
}
```

(Illustrative. Before Phase 2 completes, `gate_decision` is `NOT_ASSESSED`, `criteria` is `[]` and `decided_on` is `null`.)

- **Errors:** none besides `500`. The response does not depend on the curated build.
- **Phase:** P5.6 (reads the `config/labour_market.yaml` written in P2.5).

---

### E14 — `GET /api/v1/labour-market/indicators` — **CONDITIONAL**

- **Availability:** only when `gate_decision ∈ {GO, GO_REDUCED}`. Otherwise it returns `404 MODULE_UNAVAILABLE`, with `details: [{"field": "gate_decision", "issue": "NO_GO"}, {"field": "decision_record", "issue": "docs/decisions/MODULE_A_GATE.md"}]`.
- **Purpose:** Karnataka indicators at the supported NCO aggregation level.
- **Query:**

| Param | Type | Req. | Notes |
|---|---|---|---|
| `indicator` | string, from `available_indicators` (E13) | yes | e.g. `employment_share` |
| `nco_code` | string | no | Any length; the server truncates it to the supported level and returns `AGGREGATION_CONTEXT_ONLY` |
| `round` | string | no | e.g. a PLFS round label; the default is the latest available |

- **Response 200:** `{ indicator: IndicatorDefinition, rows: IndicatorRow[], meta }`.

```text
IndicatorDefinition { id, name, definition: string, unit: string, activity_status_basis: "USUAL_PS_SS"|"CWS",
                      population: string, source: SourceRef, method_note: string }
IndicatorRow { geography: "Karnataka", round: string, nco_level: "DIVISION"|"SUB_DIVISION"|"GROUP",
               nco_group_code: string, nco_group_title: string | null,
               estimate: number | null, ci_low: number | null, ci_high: number | null,
               unweighted_n: integer, rse: number | null,
               suppressed: boolean, suppression_reason: "SMALL_SAMPLE"|"HIGH_RSE"|null,
               evidence_class: "OFFICIAL"|"RULE_DERIVED", evidence_ids: string[], flags: QualityFlag[] }
```

`OFFICIAL` is used for figures copied from a published table. `RULE_DERIVED` is used for estimates computed from microdata with documented weights. Joining a row to a qualification is always flagged `AGGREGATION_CONTEXT_ONLY`, with class `INFERENCE`, in E06 and the UI. No `"declining"` or `"in demand"` label is returned by v1. Trend labels, if added, follow ARCHITECTURE §14.4 and are a FUTURE extension.

- **Errors:** `404 MODULE_UNAVAILABLE`; `422 VALIDATION_ERROR` (unknown indicator); `503 DATA_NOT_BUILT`.
- **Phase:** P5.6, only after P2.5 records `GO`/`GO_REDUCED` and P2.6 builds the indicator tables. **Example payloads are deliberately omitted: no labour-market data has been verified.**

---

## 4. Internal Python service interfaces (not HTTP)

Module-to-module communication uses plain Python. The API routers, CLI and analysis reports all call the same façade, so their numbers agree.

```python
# src/skillgraph/services.py — façade (Phase 3; API wiring in Phase 5)
class SkillGraphService:
    def __init__(self, registry: Registry, settings: Settings): ...
    def status(self) -> DataStatus                                              # E02
    def search_qualifications(self, q: str | None, nsqf_level: float | None,
                              coverage: Coverage | Literal["ALL"], limit: int, offset: int) -> Page[QualificationSummary]   # E03
    def get_qualification(self, code: str) -> QualificationDetail               # E04; raises NotFoundError
    def search_occupations(self, q: str | None, limit: int, offset: int) -> Page[OccupationSummary]   # E05
    def get_occupation(self, nco_code: str) -> OccupationDetail                 # E06
    def evaluate_eligibility(self, profile: HypotheticalProfile, target_codes: list[str],
                             config: EngineConfig | None) -> EligibilityResponse  # E07
    def graph(self, focus: str | None, depth: int, include_inference: bool,
              node_types: set[NodeType] | None, include_catalogue_only: bool) -> GraphView   # E08
    def explore_paths(self, request: PathRequest) -> PathResponse               # E09
    def get_evidence(self, ids: list[str]) -> EvidenceBatch                     # E10
    def list_conflicts(self, qualification_code: str | None) -> list[ConflictView]   # E11
    def list_sources(self) -> list[SourceView]                                  # E12
    def labour_market_status(self) -> LabourMarketStatus                        # E13
    def labour_market_indicators(self, indicator: str, nco_code: str | None,
                                 round: str | None) -> IndicatorTable           # E14; raises ModuleUnavailableError

# Pure engine functions (no I/O, no global state)
eligibility.logic.and_(*v: Verdict) -> Verdict          # min over NOT_MET < UNKNOWN < CONDITIONAL < MET
eligibility.logic.or_(*v: Verdict) -> Verdict           # max
eligibility.evaluate(spec: EligibilitySpec, state: ProfileState, config: EngineConfig,
                     registry: Registry) -> EligibilityResult
eligibility.identity_profile_digest(state: ProfileState) -> str         # amendment A-6 (P3.6b): "sha256:" + 64 lowercase hex
graph.build_static_edges(registry: Registry, include_inference: bool) -> list[GraphEdge]
graph.enumerate_paths(state: ProfileState, registry: Registry, config: EngineConfig,
                      scenario: Scenario, max_steps: int, target_code: str | None,
                      *, max_expansions: int, max_steps_limit: int,
                      profile_digest: str) -> list[RawPath]   # keyword-only: amendments A-1 and A-6, see below (profile_digest: P3.6b)
graph.rank(paths: list[RawPath], sort_by: PathSortKey) -> list[Path]
explain.for_eligibility(result: EligibilityResult, registry: Registry) -> list[ExplanationItem]
explain.for_path(path: RawPath, registry: Registry) -> list[ExplanationItem]

# Build-time
provenance.verify_sources(manifest: Path, raw_root: Path) -> IntegrityReport   # raises SourceIntegrityError
curation.build(settings: Settings) -> BuildResult                               # writes data/curated/<build_id>/
curation.validate(build_dir: Path) -> ValidationReport
registry.load(build_dir: Path) -> Registry
labour.gate.record_decision(...) -> GateRecord                                   # Phase 2
```

**Amendments for P3.6a (documentation only, 2026-11-02; the code is not written yet). Items A-1 and A-5 are approved; the open items they point to (O-n) are listed in `TASKS.md` P3.6 and are not approved.**

- **A-1 `enumerate_paths` limits.** `max_expansions` and `max_steps_limit` are required, keyword-only parameters with **no default** in `graph/`. The caller (the façade, or a test) supplies `Settings.paths.max_expansions` and `Settings.paths.max_steps_limit`, which `settings.py` has already validated. `graph/` never imports `settings` (ARCHITECTURE §6.2). `max_steps_limit` is the hard limit on `max_steps` (4 in `config/default.yaml`) and `max_expansions` is the budget of the expansion guard (ARCHITECTURE §13.1). The six positional parameters are unchanged. `max_steps = 3` is the E09 request default (`Settings.paths.max_steps_default`), not a default of this function. Decided 2026-11-02 (TASKS.md P3.6 O-1, O-2) and implemented in `graph/paths.py`: the guard estimate is `n ** max_steps`, `n` being the `CURATED` qualifications not held, refused (`LimitExceededError`) only if strictly greater than `max_expansions`, computed before any eligibility evaluation; a `max_steps` or limit that is not an `int` (or is a `bool`) raises `TypeError`, a value below 1 raises `ValueError`, and `max_steps > max_steps_limit` raises `LimitExceededError`; all of this is checked before enumeration.
- **A-5 `RawPath`, minimum for P3.6a.** `RawPath { steps: RawStep[1..max_steps], verdict: Verdict }`, where `verdict = and_(step verdicts)` (ARCHITECTURE §13.1). `RawStep { index: integer (1-based), from_state: string[], target_code: string, eligibility: EligibilityResult }`. `from_state` has the meaning it has in E09 `PathStep`, and `eligibility` is the step's full `EligibilityResult` (the E09 `{verdict, decisive_rule_ids, conditions, unknown_reasons}` projection is a later presentation step). Nothing else is part of `RawPath` in P3.6a. Fields kept for the stage that TASKS.md assigns them to: `rank` and `sort_values` (P3.7), `explanation` (P3.8), `hypothetical_incremental_hours` (P3.9), `is_hypothetical` and the `HYPOTHETICAL_SCENARIO` flag (P3.6, scenario handling), `inference_annotations` (P3.6 invariant, P3.10), `path_id` (P3.6b, amendment A-6; *added to `RawPath` on 2026-11-02, the other fields are still not present*). Fields with **no stage assigned** in `TASKS.md` yet: `totals`, the step's `official_hours`, `shared_nos_with_held`, `progression_claim`, `quality_flags` and `evidence_classes_present` (O-5).
- **Holding origin (A-2).** A hypothetically completed qualification is a holding with origin `EvidenceClass.HYPOTHETICAL`; every holding from the profile has origin `EvidenceClass.DECLARED`. Both values already exist in `EvidenceClass` (§2.1) and `HYPOTHETICAL` is already an allowed `inputs_used.evidence_class` (§2.4), so no enum is added. This is an internal engine field (`HeldQualification.origin`, default `DECLARED`, so existing calls are unchanged); the HTTP `HypotheticalProfile` schema is not changed and cannot carry it. It reaches `eligibility.evaluate` through an additive keyword-only argument `hypothetical_codes` (default empty; registry codes that are not declared holdings and not the target), implemented 2026-11-02 (TASKS.md P3.6 O-7); `ProfileState` is not changed and the profile is never mutated. Non-default scenarios are rejected by `enumerate_paths` with `ScenarioNotSupportedError` in P3.6a (internal limitation; E09 as written accepts them, UNRESOLVED, O-8).

**Amendments decided 2026-11-02 for P3.6b and the eligibility contract. Status: A-6 (path identity) is IMPLEMENTED (2026-11-02, committed on branch `feat/p36b-path-identity`; results in `TASKS.md` P3.6). A-7 (relevance of a pending qualification) is NOT implemented: it remains documentation only. Nothing else in P3.6b is implemented. The required tests are listed in `TASKS.md` P3.6, A-6 and A-7.**

- **A-6 Path identity (decided 2026-11-02; IMPLEMENTED 2026-11-02 in P3.6b: `eligibility/evaluate.py` `identity_profile_digest`, `graph/paths.py` `_path_id`, `RawPath.path_id`, `enumerate_paths(..., profile_digest)`; committed on branch `feat/p36b-path-identity`).**
  - **Profile identity digest.** `eligibility.identity_profile_digest(state: ProfileState) -> str` is a new helper. `logging_setup.profile_digest` (a digest of the raw mapping, used for logging) is **not** changed and keeps its behaviour and tests. The new digest is computed from the validated `ProfileState`, never from the raw request body: `"sha256:"` plus the lowercase hex SHA-256 of the UTF-8 bytes of `json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, the models serialised with `model_dump(mode="json")`. Numbers are already canonical (`3` and `3.0` both serialise as `3.0`; `age_years` and `school_grade_passed` are strict integers).
  - **Projection.** `age_years`; `school_grade_passed`; `post_school_credentials` (the `type` of each credential, sorted, **duplicates kept**); `held_qualification_codes` (sorted); `external_qualifications` (`{ref, nsqf_level}`, sorted by `ref`); `declarations` (sorted by `target_code`, each `{target_code, relevant_experience_years, relevant_prior_qualifications}` with the last sorted). `null` (not declared) and `[]` (declared none) stay distinct for every nullable field.
  - **Why only those fields are normalised (verified 2026-11-02).** Codes, external refs and relevant qualifications are validated as unique and the evaluator sorts them; permuting them leaves the serialised result byte-identical (`test_repeated_evaluation_is_identical_and_independent_of_declaration_order`). `declarations` have unique `target_code` keys and are looked up by key; permuting them leaves the result identical. Credential order is irrelevant (sorted by the evaluator; swapped order gives an identical result). **Duplicate credential types are not removed:** they never change a verdict, but `inputs_used` echoes the declared credentials, so a duplicate changes the serialised `EligibilityResult` (checked with and without `or_equivalent`), and two profiles that produce different results must not share an identity.
  - **Excluded as display-only.** `ProfileState.label`, `PostSchoolCredential.label` and `ExternalQualification.label`: nothing in `src/` reads them (only their definitions and a docstring mention them), so they cannot reach a verdict, a condition or an `inputs_used` entry. *(Implementation note, 2026-11-02: the engine's `ProfileState` carries no `label` field; the profile `label` is request metadata of the HTTP schema. So the code excludes the two nested labels, and the request `label` is excluded by never reaching `ProfileState`.)*
  - **Path ID.** `path_id = "p-" + sha256_hex(canonical_json(payload))[:12]` (lowercase hex; the same canonical JSON rules), where `payload` is exactly `{"config": <effective EngineConfig>, "profile_digest": <the digest above>, "scenario": <effective Scenario>, "steps": [<ordered step target codes>]}`. `EngineConfig` is `{nsqf_level_match}` (`null` when unset) and `Scenario` is its three fields; both are canonical when serialised with `model_dump(mode="json")`. Excluded: the build ID, `sort_by`, `limit`, `include_inference`, `max_steps`, `target_code`, and any ranking or display setting. If a configurable setting can ever change path or eligibility semantics, it must be added to this payload in the same change; the known case is Q-B `undecided_level_use`, which is fixed at `COMPARE` in `enumerate_paths` and is not part of `EngineConfig`. A path ID identifies a query, not a result: the same ID can carry different verdicts under another build (`meta.data_build_id`).
  - **`enumerate_paths(..., profile_digest: str)`** is a required, keyword-only parameter with no default: the identity digest of the same `state`, supplied by the caller (the façade or a test). `graph/` neither imports `logging_setup` nor computes the digest. It must match `^sha256:[0-9a-f]{64}$`; a non-`str` raises `TypeError` and any other string `ValueError`, before enumeration. Two paths with the same `path_id` in one result raise `GraphError`. `RawPath` gains `path_id` in P3.6b (done, 2026-11-02). **Known caller obligation (review 2026-11-02, not a new rule):** `enumerate_paths` checks only the *format* of `profile_digest`; it does not, and by this contract cannot, check that the digest was computed from the `state` it is given, so a digest taken from a different profile yields well-formed IDs that do not identify this query. Both callers in `src/` (`api/demo_app.py`, `api/demo_explore.py`) pass `identity_profile_digest` of the very `ProfileState` they enumerate. Whether to enforce this is an open item (`TASKS.md` P3.6 O-9), not decided.
- **A-7 Relevance of a pending qualification, "Option C" (decided 2026-11-02; NOT implemented).** The rule is in §2.3 above and `ARCHITECTURE.md` §13.1; this bullet fixes the rules and the boundaries.
  - **Rules.** (1) A pending (hypothetically completed) registry qualification is relevant to a target only if that target's `relevant_prior_qualifications` explicitly names it. (2) An unnamed one that satisfies a `PRIOR_NSQF_LEVEL` component gives `UNKNOWN(RELEVANCE_NOT_DECLARED)`, never `NOT_MET`, even when the list is explicitly `[]`; `null` (not supplied) also gives `UNKNOWN`. (3) A named one that affects an assessment contributes both a `DECLARATION` condition and a `HYPOTHETICAL` condition; the component is `CONDITIONAL`, never `MET` on that basis alone. (4) `Path.is_hypothetical` is true if any evaluated step's `EligibilityResult` carries a `HYPOTHETICAL` condition (in addition to the existing scenario rule); a path is not hypothetical merely because it has several steps. (5) A known pending code that is not on the evaluated path has no effect, and a declaration never establishes eligibility or a feasible path. (6) `resolvable_by = PROFILE` for `RELEVANCE_NOT_DECLARED` is accurate under this rule: the person resolves it by naming the code.
  - **Validation boundary and errors (existing contracts only).** The shape of an entry is checked by `ProfileState` (an `ext-` ref must be a declared external qualification; any other entry must be a well-formed qualification code): a violation is `422 VALIDATION_ERROR`. Registry membership is checked where the registry is available, in the way held codes already are: `eligibility.evaluate` resolves every non-`ext-` entry of **every** declaration in `state`, not only the evaluated target's, before it evaluates any rule, and `graph.enumerate_paths` does the same before its first evaluation. A typo is therefore rejected even if its target is never evaluated or no candidate exists. A code that is not in the registry raises the existing `UnknownEntityError`, which the façade maps to the existing `422 UNKNOWN_QUALIFICATION_CODE` (§1.6; the mapping itself belongs to P3.10 / P5.1). No new error type is introduced.
  - **Not decided here:** `assumed_experience_gain_years_per_step`; non-default scenarios and the E09 departure; the `HYPOTHETICAL_SCENARIO` flag wording and severity; inference annotations and E08 wording; Q-A, Q-B (still `COMPARE`, PROVISIONAL) and Q-C.

CLI entry point (`python -m skillgraph <command>`): `verify-sources`, `build`, `validate`, `report [--all | <name>]`, `serve`, `check-repo-hygiene`. See `TASKS.md` for the phase each command is introduced in.

---

## 5. Traceability

| Endpoint | ARCHITECTURE section | TASKS checkpoint(s) |
|---|---|---|
| E01 health | §17 | P5.1 |
| E02 status | §7, §8.6, §17, §21 | P1.6, P5.1 |
| E03 / E04 qualifications | §9, §12 | P1.4, P5.2 |
| E05 / E06 occupations | §9, §5, §14 | P1.4, P5.2, (P2.6) |
| E07 eligibility | §11 | P3.2, P3.3, P5.3 |
| E08 graph | §10 | P3.4, P3.5, P5.4 |
| E09 paths | §12, §13 | P3.6–P3.8, P5.4 |
| E10 evidence | §9.2, §19 | P1.4, P5.5 |
| E11 conflicts | §8.6 | P1.4, P5.5 |
| E12 sources | §8.3, §19 | P1.1, P5.5 |
| E13 / E14 labour market | §14, §21 | P2.5, P2.6, P5.6 |
