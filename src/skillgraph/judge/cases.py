"""Case files: a dataset of (engine scenario, candidate text, expected labels, scripted mock reply).

A scenario is a packet without ``case_id`` and ``candidate_text``; several cases share one. ``expected`` are labels written by
whoever authored the file; the file states their origin and that they are not human-review labels or ground truth. The
scripted reply is used by the mock judge only; a live judge ignores it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from skillgraph.judge.mock import ScriptedJudge
from skillgraph.judge.packet import JudgePacket, PacketError, packet_from_mapping
from skillgraph.judge.run import Judge, JudgeProviderError, JudgeTimeout, evaluate_case
from skillgraph.judge.schema import CaseResult, CaseStatus, Dimension, ErrorKind

SYNTHETIC_ORIGIN = "SYNTHETIC_ENGINEER_AUTHORED"


class CasesFileError(ValueError):
    """The case file cannot be used (unreadable, malformed, inconsistent)."""


@dataclass(frozen=True)
class Case:
    case_id: str
    category: str
    description: str
    packet: JudgePacket | None
    packet_error: str | None
    expected_status: str | None
    expected_dimensions: dict[str, str]
    scripted: object  # a str reply or an exception instance


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    origin: str
    labels_note: str
    digest: str
    cases: tuple[Case, ...]

    def scripted_judge(self) -> ScriptedJudge:
        return ScriptedJudge({c.case_id: c.scripted for c in self.cases if c.scripted is not None})


def _scripted(spec: object) -> object:
    if spec is None:
        return None
    if not isinstance(spec, dict) or "kind" not in spec:
        raise CasesFileError("scripted must be an object with a kind")
    kind = spec["kind"]
    if kind == "timeout":
        return JudgeTimeout()
    if kind == "provider_error":
        return JudgeProviderError("scripted provider failure")
    if kind == "raw":
        return str(spec["text"])
    if kind == "outcomes":  # every dimension PASS unless listed
        listed = spec.get("dimensions", {})
        dims = []
        for d in Dimension:
            item = listed.get(d.value)
            if item is None:
                dims.append({"dimension": d.value, "outcome": "PASS", "findings": []})
            else:
                finding = {k: item[k] for k in ("excerpt", "evidence_ids", "rationale") if k in item}
                dims.append({"dimension": d.value, "outcome": item["outcome"], "findings": [finding]})
        return json.dumps({"dimensions": dims, **spec.get("extra", {})})
    raise CasesFileError(f"unknown scripted kind {kind!r}")


def load_cases(path: Path) -> Dataset:
    try:
        raw = path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise CasesFileError(f"cannot read {path.name}: {type(exc).__name__}") from None
    try:
        scenarios, items = doc["scenarios"], doc["cases"]
        cases = []
        for item in items:
            base = scenarios[item["scenario"]]
            exp = item.get("expected", {})
            try:
                packet, perr = packet_from_mapping({**base, "case_id": item["case_id"], "candidate_text": item["candidate_text"]}), None
            except PacketError as exc:
                packet, perr = None, str(exc)
            cases.append(Case(case_id=item["case_id"], category=item["category"], description=item["description"], packet=packet,
                              packet_error=perr, expected_status=exp.get("status"),
                              expected_dimensions=dict(exp.get("dimensions", {})), scripted=_scripted(item.get("scripted"))))
        ids = [c.case_id for c in cases]
        if len(ids) != len(set(ids)):
            raise CasesFileError("case ids must be unique")
        return Dataset(dataset_id=doc["dataset_id"], origin=doc["origin"], labels_note=doc["labels_note"],
                       digest="sha256:" + hashlib.sha256(raw).hexdigest(), cases=tuple(cases))
    except (KeyError, TypeError, AttributeError) as exc:
        raise CasesFileError(f"malformed case file: {type(exc).__name__} {exc}") from None


def run_cases(dataset: Dataset, judge: Judge) -> list[CaseResult]:
    """One result per case, in file order. A refused packet is an ERROR and never reaches the judge."""
    out: list[CaseResult] = []
    for c in dataset.cases:
        if c.packet is None:
            out.append(CaseResult(case_id=c.case_id, judge_id=judge.judge_id, status=CaseStatus.ERROR, engine_verdict=None,
                                  error_kind=ErrorKind.PACKET_REFUSED, error_detail=(c.packet_error or "")[:300]))
        else:
            out.append(evaluate_case(c.packet, judge))
    return out
