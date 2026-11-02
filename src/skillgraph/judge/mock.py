"""The offline judge: replays canned replies keyed by case id. No model, no network, no credentials.

It exists to test the pipeline (packet, request, validation, combination, report) and nothing else. A result from it says
nothing about how well any model judges explanations.
"""

from __future__ import annotations

from collections.abc import Mapping

from skillgraph.judge.prompt import JudgeRequest
from skillgraph.judge.run import JudgeProviderError


class ScriptedJudge:
    judge_id = "mock-scripted"

    def __init__(self, replies: Mapping[str, str | BaseException]) -> None:
        self._replies = dict(replies)

    def complete(self, request: JudgeRequest) -> str:
        if request.case_id not in self._replies:
            raise JudgeProviderError(f"no scripted reply for case {request.case_id}")
        reply = self._replies[request.case_id]
        if isinstance(reply, BaseException):
            raise reply
        return reply
