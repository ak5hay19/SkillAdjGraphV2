"""docs/schemas.md is generated from the models and must not drift."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_generator():
    spec = importlib.util.spec_from_file_location("gen_schema_docs", REPO / "tools" / "gen_schema_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_doc_is_up_to_date():
    gen = load_generator()
    assert (REPO / "docs" / "schemas.md").read_text(encoding="utf-8") == gen.render(), (
        "docs/schemas.md is stale: run python tools/gen_schema_docs.py"
    )


def test_generation_is_deterministic():
    gen = load_generator()
    assert gen.render() == gen.render()
