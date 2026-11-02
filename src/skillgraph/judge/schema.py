"""Closed, strict schemas for the offline LLM-as-judge (advisory quality control; docs/judge/README.md).

The judge's output model has no field that could carry an eligibility verdict, an edge, a path, a ranking or an approval: a
model that tries to emit one is rejected by ``extra="forbid"``. The case-level status is computed here from the five
per-dimension outcomes; there is no numeric score.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import StrictStr, StringConstraints, model_validator

from skillgraph.model.base import SchemaModel


class Dimension(StrEnum):
    EVIDENCE_FAITHFULNESS = "EVIDENCE_FAITHFULNESS"  # claims supported by the supplied evidence
    VERDICT_CONSISTENCY = "VERDICT_CONSISTENCY"  # text reflects the engine's rule results and verdict
    UNCERTAINTY_HANDLING = "UNCERTAINTY_HANDLING"  # missing or conflicting evidence preserved, not guessed
    COMPLETENESS = "COMPLETENESS"  # relevant blockers, conditions and gaps are explained
    UNSUPPORTED_CLAIMS = "UNSUPPORTED_CLAIMS"  # invented eligibility, equivalence, exemption, hours, outcomes


class DimensionOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CaseStatus(StrEnum):
    """The status of one case. ``ERROR`` means the judge did not produce a usable result; it is never a pass."""

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ERROR = "ERROR"


class ErrorKind(StrEnum):
    PACKET_REFUSED = "PACKET_REFUSED"  # the input packet is malformed or matched a privacy pattern
    NOT_CONFIGURED = "NOT_CONFIGURED"  # no key, no opt-in, or the HTTP library is absent
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"  # network error, non-200 status or a truncated reply
    PROVIDER_REFUSAL = "PROVIDER_REFUSAL"  # the model declined the request
    OUTPUT_TOO_LARGE = "OUTPUT_TOO_LARGE"
    INVALID_JSON = "INVALID_JSON"
    SCHEMA_INVALID = "SCHEMA_INVALID"  # wrong shape, invalid enum value, extra field, inconsistent outcome
    GROUNDING_INVALID = "GROUNDING_INVALID"  # a quoted excerpt is not in the text, or an evidence id is not in the packet
    INTERNAL = "INTERNAL"  # an unexpected failure inside the judge component


Excerpt = Annotated[StrictStr, StringConstraints(min_length=1, max_length=400)]
Rationale = Annotated[StrictStr, StringConstraints(min_length=1, max_length=600)]


class Finding(SchemaModel):
    """One problem the judge reports. ``excerpt`` quotes the candidate text verbatim (checked); it may be ``None`` only for
    ``COMPLETENESS``, where the problem is something the text leaves out."""

    excerpt: Excerpt | None = None
    evidence_ids: tuple[StrictStr, ...] = ()  # each must be an evidence id of the packet (checked)
    rationale: Rationale


class DimensionVerdict(SchemaModel):
    dimension: Dimension
    outcome: DimensionOutcome
    findings: tuple[Finding, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> DimensionVerdict:
        if self.outcome is DimensionOutcome.PASS and self.findings:
            raise ValueError("a PASS dimension has no findings")
        if self.outcome is not DimensionOutcome.PASS and not self.findings:
            raise ValueError(f"a {self.outcome.value} dimension needs at least one finding")
        if self.dimension is not Dimension.COMPLETENESS and any(f.excerpt is None for f in self.findings):
            raise ValueError("only a COMPLETENESS finding may omit its excerpt")
        return self


class JudgeOutput(SchemaModel):
    """What the model must return: each of the five dimensions exactly once. Nothing else is accepted."""

    dimensions: tuple[DimensionVerdict, ...]

    @model_validator(mode="after")
    def _all_five_once(self) -> JudgeOutput:
        seen = [d.dimension for d in self.dimensions]
        if len(seen) != len(set(seen)) or set(seen) != set(Dimension):
            raise ValueError("dimensions must contain each of the five dimensions exactly once")
        return self


class PrecheckSignal(SchemaModel):
    """A deterministic phrase hit. It can only raise a case to ``REVIEW_REQUIRED``; it never lowers anything."""

    family: StrictStr
    phrase: StrictStr
    sentence: StrictStr


class CaseResult(SchemaModel):
    case_id: StrictStr
    judge_id: StrictStr
    status: CaseStatus
    engine_verdict: StrictStr | None  # echoed from the packet, read-only; the judge never changes it
    dimensions: tuple[DimensionVerdict, ...] = ()
    precheck: tuple[PrecheckSignal, ...] = ()
    error_kind: ErrorKind | None = None
    error_detail: StrictStr | None = None
    packet_digest: StrictStr | None = None

    @model_validator(mode="after")
    def _consistent(self) -> CaseResult:
        if (self.status is CaseStatus.ERROR) != (self.error_kind is not None):
            raise ValueError("an ERROR result has an error kind, and no other result has one")
        return self


def worst(outcomes: list[DimensionOutcome]) -> DimensionOutcome:
    """FAIL beats REVIEW_REQUIRED beats PASS. Not a score: the dimension outcomes are always kept alongside."""
    if DimensionOutcome.FAIL in outcomes:
        return DimensionOutcome.FAIL
    if DimensionOutcome.REVIEW_REQUIRED in outcomes:
        return DimensionOutcome.REVIEW_REQUIRED
    return DimensionOutcome.PASS
