"""``python -m skillgraph.judge``: run a case file through a judge and write a reproducible report.

Default judge is the offline mock (scripted replies, no network). ``--judge anthropic`` is opt-in: it needs ``--model``,
``--allow-external`` and ``ANTHROPIC_API_KEY`` in the environment, and it sends each packet to a third party.
Exit codes: 0 ran; 1 ``--check-expected`` found a status that differs from its stored label; 3 cannot run.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from skillgraph.judge.anthropic_adapter import AnthropicJudge
from skillgraph.judge.cases import CasesFileError, load_cases, run_cases
from skillgraph.judge.report import build_report, to_json, to_markdown
from skillgraph.judge.run import JudgeNotConfigured

DEFAULT_CASES = Path("tests/fixtures/judge/golden_cases.json")


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m skillgraph.judge", description=__doc__)
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument("--judge", choices=("mock", "anthropic"), default="mock")
    p.add_argument("--model", help="model id for --judge anthropic (no default)")
    p.add_argument("--allow-external", action="store_true", help="permit sending packets to the provider (required for anthropic)")
    p.add_argument("--out-dir", type=Path, help="write judge_report.json and judge_report.md here (default: print Markdown)")
    p.add_argument("--check-expected", action="store_true", help="exit 1 if any case status differs from its stored label")
    args = p.parse_args(argv)
    try:
        dataset = load_cases(args.cases)
        if args.judge == "mock":
            judge = dataset.scripted_judge()
        else:
            if not args.model:
                raise JudgeNotConfigured("--model is required for --judge anthropic")
            judge = AnthropicJudge.from_env(model=args.model, allow_external=args.allow_external)
    except (CasesFileError, JudgeNotConfigured) as exc:
        print(f"cannot run: {exc}", file=sys.stderr)
        return 3
    results = run_cases(dataset, judge)
    report = build_report(dataset, judge.judge_id, results)
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "judge_report.json").write_text(to_json(report), encoding="utf-8", newline="\n")
        (args.out_dir / "judge_report.md").write_text(to_markdown(report), encoding="utf-8", newline="\n")
        print(f"wrote {args.out_dir / 'judge_report.json'} and judge_report.md")
    else:
        sys.stdout.write(to_markdown(report))
    if args.check_expected and report["agreement_with_expected_status"]["disagreeing_case_ids"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
