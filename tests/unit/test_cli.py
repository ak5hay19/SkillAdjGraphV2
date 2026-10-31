import subprocess
import sys

import pytest

from skillgraph import __version__
from skillgraph.cli import COMMANDS, IMPLEMENTED, main

STUBS = [c for c in COMMANDS if c not in IMPLEMENTED]


def test_version():
    assert __version__ == "0.1.0"


def test_six_commands_registered():
    assert set(COMMANDS) == {"verify-sources", "build", "validate", "report", "serve", "check-repo-hygiene"}


@pytest.mark.parametrize("command", STUBS)
def test_each_stub_exits_2_naming_its_checkpoint(command, capsys):
    assert main([command]) == 2
    assert f"not implemented ({COMMANDS[command][0]})" in capsys.readouterr().err


def test_report_accepts_all_flag(capsys):
    assert main(["report", "--all"]) == 2
    assert "P4.6" in capsys.readouterr().err


def test_help_lists_every_command():
    out = subprocess.run([sys.executable, "-m", "skillgraph", "--help"], capture_output=True, text=True)
    assert out.returncode == 0
    for name in COMMANDS:
        assert name in out.stdout


def test_module_entry_exit_code():
    out = subprocess.run([sys.executable, "-m", "skillgraph", "validate"], capture_output=True, text=True)
    assert out.returncode == 2
    assert "P1.6" in out.stderr
