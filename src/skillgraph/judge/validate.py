"""Validation of raw model output. Model output is untrusted input: size, JSON, schema, then grounding in the packet."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from skillgraph.judge.packet import JudgePacket
from skillgraph.judge.schema import ErrorKind, JudgeOutput

MAX_OUTPUT_CHARS = 20_000
_FENCE = re.compile(r"^\s*```(?:json)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


class JudgeOutputError(Exception):
    """The reply is unusable. ``kind`` says why; the detail never contains the whole reply."""

    def __init__(self, kind: ErrorKind, detail: str) -> None:
        super().__init__(detail)
        self.kind, self.detail = kind, detail


def _normalise(text: str) -> str:
    return " ".join(text.split())


def parse_judge_output(raw: object, packet: JudgePacket) -> JudgeOutput:
    """Raise ``JudgeOutputError`` unless ``raw`` is exactly one valid, grounded ``JudgeOutput``.

    One surrounding markdown fence is tolerated (models add it habitually); nothing else around the JSON is.
    """
    if not isinstance(raw, str):
        raise JudgeOutputError(ErrorKind.INVALID_JSON, f"reply is {type(raw).__name__}, not text")
    if len(raw) > MAX_OUTPUT_CHARS:
        raise JudgeOutputError(ErrorKind.OUTPUT_TOO_LARGE, f"reply has {len(raw)} characters (limit {MAX_OUTPUT_CHARS})")
    body = raw.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group(1)

    def refuse_constant(name: str) -> None:
        raise ValueError(f"non-standard JSON constant {name}")

    try:
        data = json.loads(body, parse_constant=refuse_constant)
    except ValueError as exc:
        raise JudgeOutputError(ErrorKind.INVALID_JSON, f"not valid JSON: {str(exc)[:120]}") from None
    if not isinstance(data, dict):
        raise JudgeOutputError(ErrorKind.SCHEMA_INVALID, "the JSON value is not an object")
    try:
        out = JudgeOutput.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise JudgeOutputError(ErrorKind.SCHEMA_INVALID,
                               f"{'.'.join(str(p) for p in first['loc'])}: {first['msg'][:160]}") from None

    text = _normalise(packet.candidate_text)
    for dim in out.dimensions:
        for f in dim.findings:
            if f.excerpt is not None and _normalise(f.excerpt) not in text:
                raise JudgeOutputError(ErrorKind.GROUNDING_INVALID,
                                       f"{dim.dimension.value}: a quoted excerpt is not in the candidate text")
            unknown = sorted(set(f.evidence_ids) - set(packet.evidence))
            if unknown:
                raise JudgeOutputError(ErrorKind.GROUNDING_INVALID,
                                       f"{dim.dimension.value}: evidence ids not in the packet: {unknown}")
    return out
