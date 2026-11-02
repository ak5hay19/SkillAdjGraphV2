"""Deterministic JSON and Markdown report: case-level rows and aggregate counts, no composite score, no timestamp.

Every aggregate is shown with the size and origin of the evaluation set. "Agreement" means the judge's case status equals the
status label stored in the case file; it is only as meaningful as that label, whose origin the report prints.
"""

from __future__ import annotations

import json
from collections import Counter

from skillgraph.judge.cases import Dataset
from skillgraph.judge.schema import CaseResult, CaseStatus, Dimension, DimensionOutcome, ErrorKind

REPORT_VERSION = "1"


def build_report(dataset: Dataset, judge_id: str, results: list[CaseResult]) -> dict[str, object]:
    by_id = {c.case_id: c for c in dataset.cases}
    rows = []
    for r in results:
        c = by_id[r.case_id]
        agrees = None if c.expected_status is None else (r.status.value == c.expected_status)
        rows.append({
            "case_id": r.case_id, "category": c.category, "engine_verdict": r.engine_verdict, "status": r.status.value,
            "dimensions": {d.dimension.value: d.outcome.value for d in r.dimensions},
            "precheck": sorted({s.family for s in r.precheck}),
            "error_kind": r.error_kind.value if r.error_kind else None, "error_detail": r.error_detail,
            "expected_status": c.expected_status, "agrees_with_expected_status": agrees,
        })
    status = Counter(r.status.value for r in results)
    dims = {d.value: Counter() for d in Dimension}
    for r in results:
        for d in r.dimensions:
            dims[d.dimension.value][d.outcome.value] += 1
    errors = Counter(r.error_kind.value for r in results if r.error_kind)
    labelled = [r for r in rows if r["expected_status"] is not None]
    return {
        "report_version": REPORT_VERSION,
        "judge_id": judge_id,
        "dataset": {"dataset_id": dataset.dataset_id, "origin": dataset.origin, "labels_note": dataset.labels_note,
                    "n_cases": len(results), "digest": dataset.digest},
        "counts": {"status": {k.value: status.get(k.value, 0) for k in CaseStatus},
                   "by_dimension": {d: {o.value: dims[d].get(o.value, 0) for o in DimensionOutcome} for d in dims},
                   "error_kinds": {k.value: errors.get(k.value, 0) for k in ErrorKind if errors.get(k.value, 0)}},
        "agreement_with_expected_status": {
            "n_labelled": len(labelled), "n_agree": sum(1 for r in labelled if r["agrees_with_expected_status"]),
            "disagreeing_case_ids": [r["case_id"] for r in labelled if not r["agrees_with_expected_status"]],
            "meaning": "Equality of the case status with the label stored in the case file; see dataset.origin and labels_note"},
        "cases": rows,
    }


def to_json(report: dict[str, object]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def to_markdown(report: dict[str, object]) -> str:
    ds, counts, agree = report["dataset"], report["counts"], report["agreement_with_expected_status"]
    mock = str(report["judge_id"]).startswith("mock")
    lines = ["# Judge evaluation report", ""]
    if mock:
        lines += ["> **MOCK JUDGE (scripted replies). This checks the pipeline only. It says nothing about how well any model "
                  "judges explanations.**", ""]
    lines += [
        f"- Judge: `{report['judge_id']}`",
        f"- Evaluation set: `{ds['dataset_id']}`, **n = {ds['n_cases']}** cases, origin **{ds['origin']}**",
        f"- Labels: {ds['labels_note']}",
        f"- Set digest: `{ds['digest']}`",
        "- This is an advisory quality-control layer. The engine's verdicts are authoritative and are not changed by it.", "",
        "## Case status counts", "", "| Status | Cases |", "|---|---|",
        *(f"| {k} | {v} |" for k, v in counts["status"].items()), "",
        "## Dimension outcomes (completed cases only)", "", "| Dimension | PASS | FAIL | REVIEW_REQUIRED |", "|---|---|---|---|",
        *(f"| {d} | {o['PASS']} | {o['FAIL']} | {o['REVIEW_REQUIRED']} |" for d, o in counts["by_dimension"].items()), ""]
    if counts["error_kinds"]:
        lines += ["## Errors by kind", "", "| Kind | Cases |", "|---|---|", *(f"| {k} | {v} |" for k, v in counts["error_kinds"].items()), ""]
    lines += ["## Agreement with the stored status labels", "",
              f"{agree['n_agree']} of {agree['n_labelled']} labelled cases have the labelled status "
              f"(labels: {ds['origin']}, not human-reviewed). {agree['meaning']}.",
              *([f"Disagreeing cases: {', '.join(agree['disagreeing_case_ids'])}."] if agree["disagreeing_case_ids"] else []), "",
              "## Cases", "", "| Case | Category | Engine verdict | Status | Expected | Dimensions not PASS | Precheck | Error |",
              "|---|---|---|---|---|---|---|---|"]
    for r in report["cases"]:
        bad = ", ".join(f"{d}={o}" for d, o in r["dimensions"].items() if o != "PASS") or "-"
        err = f"{r['error_kind']}: {r['error_detail']}" if r["error_kind"] else "-"
        lines.append(f"| {r['case_id']} | {r['category']} | {r['engine_verdict'] or '-'} | {r['status']} | "
                     f"{r['expected_status'] or '-'} | {bad} | {', '.join(r['precheck']) or '-'} | {err} |")
    return "\n".join(lines) + "\n"
