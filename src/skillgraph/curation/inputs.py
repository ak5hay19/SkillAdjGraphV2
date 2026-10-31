"""Read-only access to the build inputs, and the byte-identity guard.

Every input is opened for reading only. ``snapshot`` hashes whole trees so that the build can prove, after it ran,
that no raw file, processed file or configuration file changed (TASKS P1.3/P1.4: byte-identical before and after).
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from .errors import BuildError

Row = dict[str, str]
LINE = "_line"  # 1-based CSV line number of a row (header = line 1), added to every row read


def sha256_file(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def read_csv(path: Path, required: Iterable[str] = ()) -> list[Row]:
    """Parse a CSV (UTF-8, BOM tolerated). A short or long row is an error; nothing is coerced or stripped."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in required if c not in (reader.fieldnames or [])]
            if missing:
                raise BuildError(f"{path.name}: missing column(s) {', '.join(missing)}")
            rows: list[Row] = []
            for rec in reader:
                if None in rec or any(v is None for v in rec.values()):
                    raise BuildError(f"{path.name} line {reader.line_num}: wrong number of columns")
                rows.append({**rec, LINE: str(reader.line_num)})
    except UnicodeDecodeError as exc:
        raise BuildError(f"{path.name}: not valid UTF-8: {exc}") from None
    return rows


def read_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildError(f"{path.name}: not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise BuildError(f"{path.name}: expected a JSON object")
    return data


def snapshot(roots: Iterable[Path], files: Iterable[Path] = ()) -> dict[str, str]:
    """SHA-256 of every file under ``roots`` (recursively) plus ``files``, keyed by resolved POSIX path."""
    seen: set[Path] = set()
    for root in roots:
        if root.is_dir():
            seen.update(p.resolve() for p in root.rglob("*") if p.is_file())
    for f in files:
        if f.is_file():
            seen.add(f.resolve())
    return {p.as_posix(): sha256_file(p) for p in sorted(seen)}


def diff_snapshots(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed = [f"changed: {k}" for k in before if k in after and before[k] != after[k]]
    changed += [f"removed: {k}" for k in before if k not in after]
    changed += [f"added: {k}" for k in after if k not in before]
    return sorted(changed)


def canonical_json(obj: object) -> bytes:
    """Deterministic serialisation: sorted keys, UTF-8 (no escaping of non-ASCII), LF, trailing newline."""
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
