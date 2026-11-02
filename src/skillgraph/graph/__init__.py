"""Static and experimental graph edges, path enumeration and ranking (P3.4-P3.7). P3.4 provides the static edges
(``edges.py``); P3.5 the experimental inference edges (``inference.py``) and the unreviewed claim-title candidates
(``claim_candidates.py``, which are not edges). P3.6a adds the bounded path enumeration core (``paths.py``), the only graph
module that imports ``eligibility/``; ranking (P3.7) is not here."""

from .claim_candidates import (
    ClaimCandidateReport,
    ClaimTitleCandidate,
    claim_title_candidates,
    normalise_name,
    render_review_section,
)
from .edges import (
    STATIC_EDGE_TYPES,
    EdgeBuildError,
    EdgeType,
    GraphEdge,
    GraphError,
    LegendEntry,
    build_static_edges,
    static_legend,
)
from .inference import INFERENCE_EDGE_TYPES, build_inference_edges, inference_legend
from .paths import (
    IncrementalHoursPolicy,
    LimitExceededError,
    RawPath,
    RawStep,
    Scenario,
    ScenarioNotSupportedError,
    TargetNotEvaluableError,
    enumerate_paths,
)

__all__ = [
    "INFERENCE_EDGE_TYPES",
    "STATIC_EDGE_TYPES",
    "ClaimCandidateReport",
    "ClaimTitleCandidate",
    "EdgeBuildError",
    "EdgeType",
    "GraphEdge",
    "GraphError",
    "IncrementalHoursPolicy",
    "LegendEntry",
    "LimitExceededError",
    "RawPath",
    "RawStep",
    "Scenario",
    "ScenarioNotSupportedError",
    "TargetNotEvaluableError",
    "build_inference_edges",
    "build_static_edges",
    "claim_title_candidates",
    "enumerate_paths",
    "inference_legend",
    "normalise_name",
    "render_review_section",
    "static_legend",
]
