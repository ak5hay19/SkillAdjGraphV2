"""Shared fixtures. Restricted source data never lives in Git: tests that need it skip cleanly when it is absent."""
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SYNTHETIC = Path(__file__).resolve().parent / "fixtures" / "synthetic"
EXTRACTED = Path("processed") / "extracted_2026-10-30"


@pytest.fixture(scope="session")
def synthetic_dir() -> Path:
    return SYNTHETIC


@pytest.fixture(scope="session")
def local_data() -> Path:
    """Extraction output under $SKILLGRAPH_DATA_ROOT (default: data/ in the repository); skips when absent."""
    root = os.environ.get("SKILLGRAPH_DATA_ROOT")
    base = Path(root) if root else REPO / "data"
    path = base / EXTRACTED
    if not path.is_dir():
        pytest.skip(f"local data not found: {path}")
    return path


@pytest.fixture(scope="session")
def repo_data() -> Path:
    """The repository's own data/ tree, which tools/check_legacy_baseline.py always reads; skips when absent."""
    path = REPO / "data"
    if not path.is_dir():
        pytest.skip(f"repository data tree not found: {path}")
    return path
