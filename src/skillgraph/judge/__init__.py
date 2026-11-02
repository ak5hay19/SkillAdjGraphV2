"""Offline LLM-as-judge: an advisory quality check on explanations of the deterministic engine's results.

Downstream of the engine and never imported by it. It cannot decide or change eligibility, edges, paths, ranking, path ids
or overlay approvals. See docs/judge/README.md.
"""

from skillgraph.judge.packet import JudgePacket, PacketError, build_packet, packet_from_mapping
from skillgraph.judge.run import Judge, JudgeNotConfigured, JudgeProviderError, JudgeTimeout, evaluate_case
from skillgraph.judge.schema import CaseResult, CaseStatus, Dimension, DimensionOutcome, ErrorKind, JudgeOutput

__all__ = [
    "CaseResult", "CaseStatus", "Dimension", "DimensionOutcome", "ErrorKind", "Judge", "JudgeNotConfigured", "JudgeOutput",
    "JudgePacket", "JudgeProviderError", "JudgeTimeout", "PacketError", "build_packet", "evaluate_case", "packet_from_mapping",
]
