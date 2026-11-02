"""Runs the legacy baseline checker. A pass means the documented 23 passed / 1 failed (DQ-01) result reproduced
exactly; it does NOT mean the legacy suite passes."""
import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[2] / "tools" / "check_legacy_baseline.py"

pytestmark = pytest.mark.requires_local_data


def _run(*args):
    proc = subprocess.run(
        [sys.executable, "-B", str(CHECKER), *args], capture_output=True, text=True, timeout=600
    )
    return proc, f"exit={proc.returncode}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"


def test_legacy_baseline_matches(local_data, repo_data):
    proc, out = _run()
    assert proc.returncode == 0, out
    assert "MATCH" in proc.stdout, out
    assert "NOT a passing suite" in proc.stdout, out


def test_legacy_baseline_self_test(local_data, repo_data):
    proc, out = _run("--self-test")
    assert proc.returncode == 0, out
    assert "SELF-TEST PASSED" in proc.stdout, out
