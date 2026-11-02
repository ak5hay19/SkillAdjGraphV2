"""Source integrity verification (ARCHITECTURE §3 principle 3, TASKS P1.1).

Proves that the local evidence base is the one that was audited. It hashes file bytes and compares strings;
it never opens, parses or interprets a document (PDFs included), and it never modifies any input.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MANIFEST_NAME = "MANIFEST.csv"
OVERLAY_NAME = "corrections_overlay.csv"
UNRESOLVED_STATUS = "UNRESOLVED"
_SHA256 = re.compile(r"[0-9a-f]{64}")

FileStatus = Literal["MATCH", "MISMATCH", "MISSING", "UNREADABLE", "INVALID_PATH", "INVALID_HASH", "NO_LOCAL_FILE"]


class SourceIntegrityError(Exception):
    """The evidence base differs from the audited one, or integrity could not be fully checked."""

    def __init__(self, message: str, report: IntegrityReport | None = None) -> None:
        super().__init__(message)
        self.report = report


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FileCheck(_Model):
    item_id: str
    status: FileStatus
    manifest_status: str
    path: str | None = None
    expected_sha256: str | None = None
    actual_sha256: str | None = None


class ReferenceProblem(_Model):
    row: int = Field(description="1-based CSV line number, header being line 1")
    reason: str
    sha256: str | None = None
    source_file: str | None = None


class ReferenceCheck(_Model):
    file: str
    rows: int
    checked: int
    excluded_unresolved: int
    problems: list[ReferenceProblem]


class IntegrityReport(_Model):
    ok: bool
    manifest: str
    local_files_listed: int
    local_files_matched: int
    local_files_failed: int
    no_local_file: int
    files: list[FileCheck]
    extraction: list[ReferenceCheck]
    overlay: ReferenceCheck | None
    errors: list[str] = Field(description="Checks that could not run; any entry makes ok false")


def _read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name}: missing column(s) {', '.join(missing)}")
        return list(reader)


def _sha256_of(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def _relative_to_raw(manifest_path: str, raw_root: Path) -> str | None:
    """Manifest paths are recorded from the repository root (``data/raw/2026-10-30/...``); return the part below
    the raw root directory name, or None if the path does not sit under it or tries to escape it."""
    parts = PurePosixPath(manifest_path.replace("\\", "/")).parts
    if raw_root.name not in parts or ".." in parts or PurePosixPath(manifest_path).is_absolute():
        return None
    rest = parts[parts.index(raw_root.name) + 1 :]
    return "/".join(rest) if rest else None


def _check_files(entries: list[dict[str, str]], raw_root: Path) -> tuple[list[FileCheck], dict[str, set[str]]]:
    """Re-hash every local manifest file. Returns the checks and {sha256: raw-relative paths} for MATCH files;
    several paths may legitimately share one hash."""
    checks: list[FileCheck] = []
    verified: dict[str, set[str]] = defaultdict(set)
    for e in entries:
        item, status = e["item_id"], e["validation_status"]
        path, expected = e["local_relative_path"].strip(), e["sha256"].strip().lower()
        if not path:
            checks.append(FileCheck(item_id=item, status="NO_LOCAL_FILE", manifest_status=status))
            continue
        base = {"item_id": item, "manifest_status": status, "path": path, "expected_sha256": expected or None}
        rel = _relative_to_raw(path, raw_root)
        if rel is None:
            checks.append(FileCheck(status="INVALID_PATH", **base))
        elif not _SHA256.fullmatch(expected):
            checks.append(FileCheck(status="INVALID_HASH", **base))
        elif not (raw_root / rel).is_file():
            checks.append(FileCheck(status="MISSING", **base))
        else:
            try:
                actual = _sha256_of(raw_root / rel)
            except OSError:
                checks.append(FileCheck(status="UNREADABLE", **base))
                continue
            ok = actual == expected
            checks.append(FileCheck(status="MATCH" if ok else "MISMATCH", actual_sha256=actual, **base))
            if ok:
                verified[expected].add(rel)
    return checks, verified


def _check_references(
    name: str,
    rows: list[dict[str, str]],
    hash_col: str,
    file_col: str,
    verified: dict[str, set[str]],
    skip_unresolved: bool,
) -> ReferenceCheck:
    problems: list[ReferenceProblem] = []
    checked = excluded = 0
    for line, row in enumerate(rows, start=2):
        if skip_unresolved and row.get("extraction_status") == UNRESOLVED_STATUS:
            excluded += 1  # legacy test rule: an UNRESOLVED row need not carry a hash
            continue
        checked += 1
        sha, source = row[hash_col].strip().lower(), row[file_col].strip()
        if sha not in verified:
            reason = "hash is not a SHA-256" if not _SHA256.fullmatch(sha) else "hash matches no verified manifest file"
            problems.append(ReferenceProblem(row=line, reason=reason, sha256=sha or None, source_file=source or None))
        elif source.replace("\\", "/") not in verified[sha]:
            problems.append(
                ReferenceProblem(row=line, reason="source_file differs from the manifest path for this hash",
                                 sha256=sha, source_file=source or None)
            )
    return ReferenceCheck(file=name, rows=len(rows), checked=checked, excluded_unresolved=excluded, problems=problems)


def check_sources(manifest: Path, raw_root: Path, extracted_dir: Path, overlay: Path) -> IntegrityReport:
    """Run every integrity check and report the outcome. Never raises for a failed check; a check that cannot
    run is recorded in ``errors`` and makes the report not ok."""
    errors: list[str] = []
    files: list[FileCheck] = []
    verified: dict[str, set[str]] = {}
    try:
        entries = _read_csv(manifest, ("item_id", "validation_status", "local_relative_path", "sha256"))
    except (OSError, ValueError, csv.Error) as exc:
        entries = []
        errors.append(f"manifest unreadable: {exc}")
    else:
        ids: dict[str, int] = defaultdict(int)
        for e in entries:
            ids[e["item_id"]] += 1
        errors += [f"manifest item_id is duplicated: {i}" for i, n in ids.items() if n > 1]
        if not entries:
            errors.append("manifest lists no items")
        files, verified = _check_files(entries, raw_root)

    extraction: list[ReferenceCheck] = []
    csvs = sorted(extracted_dir.glob("*.csv")) if extracted_dir.is_dir() else []
    if not csvs:
        errors.append(f"no extraction CSVs found in {extracted_dir}")
    for path in csvs:
        try:
            rows = _read_csv(path, ("source_sha256", "source_file", "extraction_status"))
        except (OSError, ValueError, csv.Error) as exc:
            errors.append(f"extraction CSV unreadable: {exc}")
            continue
        if not rows:
            errors.append(f"{path.name} has no data rows: nothing to verify")
        extraction.append(_check_references(path.name, rows, "source_sha256", "source_file", verified, True))

    overlay_check: ReferenceCheck | None = None
    try:
        rows = _read_csv(overlay, ("evidence_sha256", "evidence_source_file"))
    except (OSError, ValueError, csv.Error) as exc:
        errors.append(f"overlay unreadable: {exc}")
    else:
        if not rows:
            errors.append(f"{overlay.name} has no data rows: nothing to verify")
        overlay_check = _check_references(overlay.name, rows, "evidence_sha256", "evidence_source_file", verified, False)

    local = [f for f in files if f.status != "NO_LOCAL_FILE"]
    matched = sum(f.status == "MATCH" for f in local)
    problems = sum(len(c.problems) for c in extraction) + (len(overlay_check.problems) if overlay_check else 0)
    return IntegrityReport(
        ok=not errors and matched == len(local) and problems == 0,
        manifest=str(manifest),
        local_files_listed=len(local),
        local_files_matched=matched,
        local_files_failed=len(local) - matched,
        no_local_file=len(files) - len(local),
        files=files,
        extraction=extraction,
        overlay=overlay_check,
        errors=errors,
    )


def verify_sources(
    manifest: Path, raw_root: Path, extracted_dir: Path | None = None, overlay: Path | None = None
) -> IntegrityReport:
    """Return the report if every check passed; otherwise raise ``SourceIntegrityError`` carrying the report.

    ``extracted_dir`` and ``overlay`` default to the repository layout beside ``raw_root``
    (``processed/extracted_2026-10-30`` and ``processed/audit_2026-10-30_m1s1``).
    """
    processed = raw_root.parent.parent / "processed"
    report = check_sources(
        manifest,
        raw_root,
        extracted_dir if extracted_dir is not None else processed / "extracted_2026-10-30",
        overlay if overlay is not None else processed / "audit_2026-10-30_m1s1" / OVERLAY_NAME,
    )
    if not report.ok:
        raise SourceIntegrityError(summarise(report), report)
    return report


def summarise(report: IntegrityReport) -> str:
    refs = report.extraction + ([report.overlay] if report.overlay else [])
    return (
        f"{report.local_files_failed} of {report.local_files_listed} local files failed, "
        f"{sum(len(c.problems) for c in refs)} unresolved hash/path references, "
        f"{len(report.errors)} check(s) could not run"
    )
