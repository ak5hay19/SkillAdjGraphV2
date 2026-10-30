from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from skillgraph.settings import SettingsError, load_settings

REPO = Path(__file__).resolve().parents[2]
DEFAULT = REPO / "config" / "default.yaml"


def _write_variant(tmp_path, mutate):
    raw = yaml.safe_load(DEFAULT.read_text(encoding="utf-8"))
    mutate(raw)
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_defaults_load_from_committed_file():
    s = load_settings(DEFAULT, environ={})
    assert s.engine.nsqf_level_match is None
    assert (s.paths.max_steps_default, s.paths.max_steps_limit, s.paths.result_limit) == (3, 4, 20)
    assert s.paths.max_expansions > 0
    assert s.inference.enabled is False
    assert s.labour_market.config == Path("config/labour_market.yaml")
    assert s.data_root == Path("data")


def test_config_path_defaults_to_config_default_yaml(monkeypatch):
    monkeypatch.chdir(REPO)
    s = load_settings(environ={})
    assert s.engine.nsqf_level_match is None


def test_env_overrides_config_file(tmp_path):
    path = _write_variant(tmp_path, lambda r: r["engine"].update(nsqf_level_match="at_least"))
    s = load_settings(environ={"SKILLGRAPH_CONFIG": str(path)})
    assert s.engine.nsqf_level_match == "at_least"


def test_argument_beats_env(tmp_path):
    path = _write_variant(tmp_path, lambda r: r["engine"].update(nsqf_level_match="exact"))
    s = load_settings(path, environ={"SKILLGRAPH_CONFIG": str(tmp_path / "missing.yaml")})
    assert s.engine.nsqf_level_match == "exact"


def test_data_root_from_env_and_resolution(tmp_path):
    s = load_settings(DEFAULT, environ={"SKILLGRAPH_DATA_ROOT": str(tmp_path)})
    assert s.data_root == tmp_path
    assert s.data_path("curated_dir") == tmp_path / "curated"
    assert s.data_path("raw_dir") == tmp_path / "raw" / "2026-10-30"
    with pytest.raises(KeyError):
        s.data_path("nope")


def test_unknown_top_level_key_rejected(tmp_path):
    path = _write_variant(tmp_path, lambda r: r.update(surprise=1))
    with pytest.raises(ValidationError, match="surprise"):
        load_settings(path, environ={})


def test_unknown_nested_key_rejected(tmp_path):
    path = _write_variant(tmp_path, lambda r: r["paths"].update(max_depth=9))
    with pytest.raises(ValidationError, match="max_depth"):
        load_settings(path, environ={})


def test_missing_required_key_rejected(tmp_path):
    path = _write_variant(tmp_path, lambda r: r["engine"].pop("nsqf_level_match"))
    with pytest.raises(ValidationError, match="nsqf_level_match"):
        load_settings(path, environ={})


def test_invalid_nsqf_interpretation_rejected(tmp_path):
    path = _write_variant(tmp_path, lambda r: r["engine"].update(nsqf_level_match="roughly"))
    with pytest.raises(ValidationError):
        load_settings(path, environ={})


def test_default_steps_may_not_exceed_limit(tmp_path):
    path = _write_variant(tmp_path, lambda r: r["paths"].update(max_steps_default=5))
    with pytest.raises(ValidationError, match="max_steps_default"):
        load_settings(path, environ={})


def test_settings_are_immutable():
    s = load_settings(DEFAULT, environ={})
    with pytest.raises(ValidationError):
        s.inference.enabled = True


def test_missing_file_is_a_settings_error(tmp_path):
    with pytest.raises(SettingsError, match="not found"):
        load_settings(tmp_path / "nope.yaml", environ={})


def test_non_mapping_and_bad_yaml_are_settings_errors(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="mapping"):
        load_settings(p, environ={})
    p.write_text("a: [unclosed\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="not valid YAML"):
        load_settings(p, environ={})


def test_empty_env_var_is_rejected():
    with pytest.raises(SettingsError, match="SKILLGRAPH_DATA_ROOT"):
        load_settings(DEFAULT, environ={"SKILLGRAPH_DATA_ROOT": " "})


def test_data_root_cannot_be_set_in_file(tmp_path):
    path = _write_variant(tmp_path, lambda r: r.update(data_root="elsewhere"))
    with pytest.raises(SettingsError, match="data_root"):
        load_settings(path, environ={})


def test_companion_config_files_have_specified_defaults():
    lm = yaml.safe_load((REPO / "config" / "labour_market.yaml").read_text(encoding="utf-8"))
    assert lm["gate_decision"] == "NOT_ASSESSED"
    ov = yaml.safe_load((REPO / "config" / "overlay_approvals.yaml").read_text(encoding="utf-8"))
    assert ov == {"approved": []}


@pytest.mark.parametrize(
    "bad",
    ["/abs/place", "C:" + chr(92) + "elsewhere", chr(92) + "rooted", "../outside", "raw/../../outside"],
)
def test_data_paths_cannot_escape_data_root(tmp_path, bad):
    path = _write_variant(tmp_path, lambda r: r["data"].update(curated_dir=bad))
    with pytest.raises(ValidationError, match="relative to the data root"):
        load_settings(path, environ={})


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [("paths", "max_steps_limit", True), ("paths", "result_limit", "20"), ("paths", "max_expansions", 0),
     ("inference", "enabled", "false"), ("inference", "enabled", 0)],
)
def test_values_are_strictly_typed(tmp_path, section, key, value):
    path = _write_variant(tmp_path, lambda r: r[section].update({key: value}))
    with pytest.raises(ValidationError):
        load_settings(path, environ={})


def test_max_expansions_is_marked_provisional():
    text = DEFAULT.read_text(encoding="utf-8")
    assert "PROVISIONAL" in text
    assert "not empirically validated" in text
