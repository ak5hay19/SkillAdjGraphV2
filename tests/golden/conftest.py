"""Golden tests run over the real curated build and the real extraction tables (skipped when absent)."""
import json

import pytest

from skillgraph.curation.config import CURATION_CODE_VERSION
from skillgraph.curation.validate import load_inputs
from skillgraph.settings import load_settings

pytestmark = pytest.mark.requires_local_data


@pytest.fixture(scope="session")
def settings(local_data, repo_data):
    return load_settings()


@pytest.fixture(scope="session")
def build_dir(settings):
    curated = settings.data_path("curated_dir")
    found = []
    for m in curated.glob("cb-*/build_manifest.json") if curated.is_dir() else []:
        data = json.loads(m.read_text(encoding="utf-8"))
        if data.get("curation_code_version") == CURATION_CODE_VERSION:
            found.append((data["built_at"], m.parent))
    if not found:
        pytest.skip(f"no installed curated build of code version {CURATION_CODE_VERSION}; run the build command first")
    return max(found)[1]


@pytest.fixture(scope="session")
def real_inputs(build_dir, settings):
    return load_inputs(build_dir, settings)
