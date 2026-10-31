"""Command-line entry point: ``python -m skillgraph <command>`` (API_SPEC §4).

Commands are stubs until their checkpoint; stubs exit with code 2. Implemented commands exit 0 on success,
1 when the checked data fails verification and 3 when the command cannot run (bad settings, unreadable input).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from skillgraph.curation.build import build
from skillgraph.curation.config import ConfigError
from skillgraph.curation.errors import BuildError
from skillgraph.curation.overlay import OverlayError
from skillgraph.logging_setup import log_event, setup_logging
from skillgraph.provenance.manifest import MANIFEST_NAME, OVERLAY_NAME, SourceIntegrityError, verify_sources
from skillgraph.model.ids import IdError
from skillgraph.settings import SettingsError, load_settings

NOT_IMPLEMENTED_EXIT = 2
FAILED_EXIT = 1
ERROR_EXIT = 3
IMPLEMENTED = {"verify-sources", "build", "validate"}

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
        if name == "validate":
            p.add_argument("--build-id", help="data_build_id to validate (default: the newest complete build of the current code version)")
            p.add_argument("--rerun-legacy", action="store_true",
                           help="also run tools/check_legacy_baseline.py (slow); otherwise the documented baseline is quoted")
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


def _build() -> int:
    """Build the curated dataset. Exit 0 and the build manifest on stdout; 1 when the data fails a check (the full
    integrity report is printed for a SourceIntegrityError); 3 when the command cannot run. Nothing is installed on
    failure."""
    logger = setup_logging()
    try:
        settings = load_settings()
    except (SettingsError, ValidationError, OSError, UnicodeDecodeError) as exc:
        print(f"build: invalid settings: {_one_line(exc)}", file=sys.stderr)
        log_event(logger, "build.settings_error", logging.ERROR, error=type(exc).__name__)
        return ERROR_EXIT
    log_event(logger, "build.start", raw_root=str(settings.data_path("raw_dir")))
    try:
        result = build(settings)
    except SourceIntegrityError as exc:
        print(exc.report.model_dump_json(indent=2))
        print(f"build: SourceIntegrityError: {exc}", file=sys.stderr)
        log_event(logger, "build.failed", logging.ERROR, error="SourceIntegrityError", detail=str(exc))
        return FAILED_EXIT
    except (BuildError, OverlayError, IdError, ValidationError, KeyError, ValueError) as exc:
        print(f"build: {type(exc).__name__}: {_one_line(exc)}", file=sys.stderr)
        log_event(logger, "build.failed", logging.ERROR, error=type(exc).__name__, detail=_one_line(exc))
        return FAILED_EXIT
    except (ConfigError, OSError, UnicodeDecodeError) as exc:
        print(f"build: cannot run: {_one_line(exc)}", file=sys.stderr)
        log_event(logger, "build.cannot_run", logging.ERROR, error=type(exc).__name__)
        return ERROR_EXIT
    log_event(logger, "build.ok", data_build_id=result.data_build_id, reused=result.reused,
              overlays=result.manifest["overlay_classification_counts"])
    print(json.dumps(result.manifest, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _validate(build_id: str | None, rerun_legacy: bool) -> int:
    """Validate an installed curated build and write ``validation_report.json`` into it. Exit 0 when every check passes
    (registered unresolved findings are reported, not failures), 1 when a check fails, 3 when it cannot run."""
    from skillgraph.curation.config import CURATION_CODE_VERSION
    from skillgraph.curation.build import MANIFEST_OUT
    from skillgraph.curation.validate import ValidationConfigError, validate, write_report

    logger = setup_logging()
    try:
        settings = load_settings()
        curated = settings.data_path("curated_dir")
        if build_id:
            build_dir = curated / build_id
        else:
            cands = []
            for m in sorted(curated.glob(f"cb-*/{MANIFEST_OUT}")) if curated.is_dir() else []:
                data = json.loads(m.read_text(encoding="utf-8"))
                if data.get("curation_code_version") == CURATION_CODE_VERSION:
                    cands.append((data["built_at"], m.parent))
            if not cands:
                print(f"validate: no complete build of code version {CURATION_CODE_VERSION} in {curated}", file=sys.stderr)
                return ERROR_EXIT
            build_dir = max(cands)[1]
        report = validate(build_dir, settings, rerun_legacy=rerun_legacy, repo_root=Path.cwd())
        write_report(build_dir, report)
    except (SettingsError, ValidationConfigError, ConfigError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        print(f"validate: cannot run: {_one_line(exc)}", file=sys.stderr)
        log_event(logger, "validate.cannot_run", logging.ERROR, error=type(exc).__name__)
        return ERROR_EXIT
    for c in report["checks"]:
        print(f"[{c['status']}] {c['name']}: {c['detail']}")
    print(f"validate: {report['data_build_id']}: {report['checks_passed']} checks passed, {report['checks_failed']} failed; "
          f"{sum(d['matches_observation'] for d in report['known_deviations'])} registered deviation(s) unresolved; "
          f"legacy baseline: {report['legacy_baseline']['result']} (not a passing suite)")
    log_event(logger, "validate.done", logging.INFO if not report["checks_failed"] else logging.ERROR,
              data_build_id=report["data_build_id"], failed=report["checks_failed"])
    return 0 if report["checks_failed"] == 0 else FAILED_EXIT


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify-sources":
        return _verify_sources()
    if args.command == "build":
        return _build()
    if args.command == "validate":
        return _validate(args.build_id, args.rerun_legacy)
    checkpoint = COMMANDS[args.command][0]
    print(f"{args.command}: not implemented ({checkpoint})", file=sys.stderr)
    return NOT_IMPLEMENTED_EXIT
