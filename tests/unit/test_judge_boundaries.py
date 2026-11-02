"""Architecture boundaries of the judge (AST scans). The judge is advisory and downstream: nothing in the engine imports it, and it
cannot reach the deterministic decision path, the overlay approvals or the data tree."""

import ast
from pathlib import Path

import pytest
import yaml

SRC = Path(__file__).resolve().parents[2] / "src" / "skillgraph"
JUDGE = SRC / "judge"
REPO = SRC.parents[1]

NETWORK_OR_PROCESS = {"httpx", "requests", "urllib", "urllib3", "http", "socket", "ssl", "aiohttp", "anthropic", "openai",
                      "subprocess", "asyncio", "smtplib", "ftplib"}
# The only skillgraph modules the judge may import. ``eligibility.evaluate`` is for result TYPES (the packet builder reads a
# result); the judge never calls ``evaluate``.
ALLOWED_SKILLGRAPH = {"skillgraph.judge", "skillgraph.model.base", "skillgraph.registry", "skillgraph.eligibility.evaluate"}


def imports(path: Path, *, top_level_only: bool = False) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = tree.body if top_level_only else list(ast.walk(tree))
    out: set[str] = set()
    for n in nodes:
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
            out |= {f"{n.module}.{a.name}" for a in n.names}
    return out


def judge_files() -> list[Path]:
    return sorted(JUDGE.glob("*.py"))


def test_the_judge_package_exists_with_the_expected_modules():
    assert {p.name for p in judge_files()} >= {"schema.py", "packet.py", "prompt.py", "precheck.py", "validate.py", "run.py",
                                              "mock.py", "anthropic_adapter.py", "cases.py", "report.py", "__main__.py"}


def test_no_other_package_imports_the_judge():
    offenders = []
    for path in SRC.rglob("*.py"):
        if JUDGE in path.parents:
            continue
        if any(m == "skillgraph.judge" or m.startswith("skillgraph.judge.") for m in imports(path)):
            offenders.append(str(path.relative_to(SRC)))
    assert offenders == []


@pytest.mark.parametrize("package", ["eligibility", "graph", "registry", "model", "curation", "provenance", "api"])
def test_the_deterministic_layers_import_no_llm_client_or_judge(package):
    for path in (SRC / package).rglob("*.py"):
        found = {m.split(".")[0] for m in imports(path)}
        assert not found & {"anthropic", "openai", "httpx", "requests"}, path.name
        assert not any(m.startswith("skillgraph.judge") for m in imports(path)), path.name


def test_the_judge_imports_only_allowed_skillgraph_modules():
    for path in judge_files():
        for m in imports(path):
            if m.startswith("skillgraph."):
                assert any(m == a or m.startswith(a + ".") for a in ALLOWED_SKILLGRAPH), (path.name, m)


def test_the_judge_never_imports_graph_paths_curation_or_settings():
    for path in judge_files():
        for m in imports(path):
            assert not m.startswith(("skillgraph.graph", "skillgraph.curation", "skillgraph.api", "skillgraph.settings",
                                     "skillgraph.provenance", "skillgraph.labour", "skillgraph.cli")), (path.name, m)


def test_only_the_opt_in_adapter_touches_the_network_and_only_lazily():
    for path in judge_files():
        top = {m.split(".")[0] for m in imports(path, top_level_only=True)}
        assert not top & NETWORK_OR_PROCESS, (path.name, top & NETWORK_OR_PROCESS)
        if path.name != "anthropic_adapter.py":
            assert not {m.split(".")[0] for m in imports(path)} & NETWORK_OR_PROCESS, path.name
    adapter = {m.split(".")[0] for m in imports(JUDGE / "anthropic_adapter.py")}
    assert adapter & NETWORK_OR_PROCESS == {"httpx"}


def test_the_judge_never_calls_the_engine_and_never_names_the_approvals_file():
    for path in judge_files():
        text = path.read_text(encoding="utf-8")
        assert "overlay_approvals" not in text, path.name
        called = {n.func.id if isinstance(n.func, ast.Name) else n.func.attr for n in ast.walk(ast.parse(text))
                  if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}
        assert not called & {"evaluate", "enumerate_paths", "build_edges", "build_inference_edges", "load", "build"}, path.name


def test_only_the_cli_and_case_loader_touch_files_and_only_the_cli_writes():
    writers = []
    for path in judge_files():
        called = {n.func.attr for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        if called & {"write_text", "write_bytes", "mkdir", "unlink", "rename", "replace", "open"}:
            writers.append(path.name)
    assert writers == ["__main__.py"]


def test_the_overlay_approvals_file_is_untouched():
    doc = yaml.safe_load((REPO / "config" / "overlay_approvals.yaml").read_text(encoding="utf-8"))
    assert doc == {"approved": []}
