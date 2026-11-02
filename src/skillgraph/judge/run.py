"""Running one case: packet -> judge -> validated, combined result. It never raises for a judge or data failure.

The engine result is not an input here: only the frozen packet is. The engine verdict is echoed from the packet into the
result and nothing in this module can change it. A judge failure of any kind gives ``ERROR``, never ``PASS``.
"""

from __future__ import annotations

from typing import Protocol

from skillgraph.judge import precheck
from skillgraph.judge.packet import JudgePacket
from skillgraph.judge.prompt import JudgeRequest, build_request
from skillgraph.judge.schema import (
    CaseResult,
    CaseStatus,
    DimensionOutcome,
    ErrorKind,
    JudgeOutput,
    PrecheckSignal,
    worst,
)
from skillgraph.judge.validate import JudgeOutputError, parse_judge_output


class JudgeTimeout(Exception):
    """The provider did not answer in time."""


class JudgeProviderError(Exception):
    """The provider failed. ``kind`` is PROVIDER_ERROR (default) or PROVIDER_REFUSAL."""

    def __init__(self, detail: str, kind: ErrorKind = ErrorKind.PROVIDER_ERROR) -> None:
        super().__init__(detail)
        self.kind, self.detail = kind, detail


class JudgeNotConfigured(Exception):
    """No key, no explicit opt-in, or the HTTP library is not installed."""


class Judge(Protocol):
    """Provider-neutral: any object with an id and a text-in, text-out call. It sees only the request built from a packet."""

    judge_id: str

    def complete(self, request: JudgeRequest) -> str: ...


def combine(output: JudgeOutput, signals: tuple[PrecheckSignal, ...]) -> CaseStatus:
    """The worst dimension outcome; a precheck signal lifts PASS to REVIEW_REQUIRED and never lowers anything."""
    outcome = worst([d.outcome for d in output.dimensions])
    if signals and outcome is DimensionOutcome.PASS:
        outcome = DimensionOutcome.REVIEW_REQUIRED
    return CaseStatus(outcome.value)


def evaluate_case(packet: JudgePacket, judge: Judge) -> CaseResult:
    digest = packet.digest()
    signals = precheck.scan(packet.candidate_text, packet.verdict)  # read-only use of the engine verdict, from the frozen packet

    def error(kind: ErrorKind, detail: str) -> CaseResult:
        return CaseResult(case_id=packet.case_id, judge_id=judge.judge_id, status=CaseStatus.ERROR,
                          engine_verdict=packet.verdict, precheck=signals, error_kind=kind, error_detail=detail[:300],
                          packet_digest=digest)

    try:
        raw = judge.complete(build_request(packet))
        output = parse_judge_output(raw, packet)
    except JudgeTimeout:
        return error(ErrorKind.PROVIDER_TIMEOUT, "the provider did not answer in time")
    except JudgeProviderError as exc:
        return error(exc.kind, exc.detail)
    except JudgeNotConfigured as exc:
        return error(ErrorKind.NOT_CONFIGURED, str(exc))
    except JudgeOutputError as exc:
        return error(exc.kind, exc.detail)
    except Exception as exc:  # noqa: BLE001 - an unexpected judge failure must never escape or alter an engine result
        return error(ErrorKind.INTERNAL, f"{type(exc).__name__}")
    return CaseResult(case_id=packet.case_id, judge_id=judge.judge_id, status=combine(output, signals),
                      engine_verdict=packet.verdict, dimensions=output.dimensions, precheck=signals, packet_digest=digest)
