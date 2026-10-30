"""Command-line entry point: ``python -m skillgraph <command>`` (API_SPEC §4).

Every command is a stub until its checkpoint; stubs exit with code 2.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

NOT_IMPLEMENTED_EXIT = 2

# command -> (checkpoint that implements it, help text)
COMMANDS: dict[str, tuple[str, str]] = {
    "verify-sources": ("P1.1", "re-hash raw sources against MANIFEST.csv"),
    "build": ("P1.4", "build the curated dataset"),
    "validate": ("P1.6", "validate a curated build and write the validation report"),
    "report": ("P4.6", "write analysis reports"),
    "serve": ("P5.1", "serve the API on 127.0.0.1"),
    "check-repo-hygiene": ("P6.3", "fail if restricted data is tracked by Git"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillgraph", description="Skill Adjacency Graph")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    for name, (checkpoint, text) in COMMANDS.items():
        p = sub.add_parser(name, help=f"{text} (not implemented; {checkpoint})", description=text)
        if name == "report":
            p.add_argument("name", nargs="?", help="report name")
            p.add_argument("--all", action="store_true", help="write every report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checkpoint = COMMANDS[args.command][0]
    print(f"{args.command}: not implemented ({checkpoint})", file=sys.stderr)
    return NOT_IMPLEMENTED_EXIT
