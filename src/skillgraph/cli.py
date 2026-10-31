"""Command-line entry point: ``python -m skillgraph <command>`` (API_SPEC §4).

Commands are stubs until their checkpoint; stubs exit with code 2. Implemented commands exit 0 on success,
1 when the checked data fails verification and 3 when the command cannot run (bad settings, unreadable input).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from pydantic import ValidationError

from skillgraph.logging_setup import log_event, setup_logging
from skillgraph.provenance.manifest import MANIFEST_NAME, OVERLAY_NAME, SourceIntegrityError, verify_sources
from skillgraph.settings import SettingsError, load_settings

NOT_IMPLEMENTED_EXIT = 2
FAILED_EXIT = 1
ERROR_EXIT = 3
IMPLEMENTED = {"verify-sources"}

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
        help_text = text if name in IMPLEMENTED else f"{text} (not implemented; {checkpoint})"
        p = sub.add_parser(name, help=help_text, description=text)
        if name == "report":
            p.add_argument("name", nargs="?", help="report name")
            p.add_argument("--all", action="store_true", help="write every report")
    return parser


def _one_line(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return " ".join(str(exc).split())


def _verify_sources() -> int:
    """Print the IntegrityReport as JSON on stdout; the exit code carries the verdict."""
    logger = setup_logging()
    try:
        settings = load_settings()
    except (SettingsError, ValidationError, OSError, UnicodeDecodeError) as exc:
        # Expected configuration failures only; a bug elsewhere must still surface as a traceback.
        print(f"verify-sources: invalid settings: {_one_line(exc)}", file=sys.stderr)
        log_event(logger, "verify_sources.settings_error", logging.ERROR, error=type(exc).__name__)
        return ERROR_EXIT
    raw_root = settings.data_path("raw_dir")
    log_event(logger, "verify_sources.start", raw_root=str(raw_root))
    try:
        report = verify_sources(
            raw_root / MANIFEST_NAME,
            raw_root,
            settings.data_path("extracted_dir"),
            settings.data_path("audit_dir") / OVERLAY_NAME,
        )
    except SourceIntegrityError as exc:
        # The report is never withheld: a failed or incomplete check is printed in full.
        print(exc.report.model_dump_json(indent=2))
        log_event(logger, "verify_sources.failed", logging.ERROR, error="SourceIntegrityError", detail=str(exc))
        print(f"verify-sources: SourceIntegrityError: {exc}", file=sys.stderr)
        return FAILED_EXIT
    print(report.model_dump_json(indent=2))
    log_event(logger, "verify_sources.ok", matched=report.local_files_matched, no_local_file=report.no_local_file)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify-sources":
        return _verify_sources()
    checkpoint = COMMANDS[args.command][0]
    print(f"{args.command}: not implemented ({checkpoint})", file=sys.stderr)
    return NOT_IMPLEMENTED_EXIT
