"""Validated settings loaded from YAML (ARCHITECTURE §17).

The only environment variables are ``SKILLGRAPH_CONFIG`` and ``SKILLGRAPH_DATA_ROOT``.
Relative paths resolve against the current working directory. Unknown keys are rejected.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

ENV_CONFIG = "SKILLGRAPH_CONFIG"
ENV_DATA_ROOT = "SKILLGRAPH_DATA_ROOT"
DEFAULT_CONFIG = Path("config/default.yaml")
DEFAULT_DATA_ROOT = Path("data")


class SettingsError(Exception):
    """The settings file or environment could not be read."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataPaths(_Strict):
    """Paths relative to the data root."""

    raw_dir: Path
    extracted_dir: Path
    audit_dir: Path
    acquisition_dir: Path = Path("processed/acquisition_2026-10-30")  # the catalogue CSV (P1.4)
    curated_dir: Path
    outputs_dir: Path
    labour_dir: Path

    @field_validator("*")
    @classmethod
    def _stay_under_data_root(cls, value: Path) -> Path:
        # An absolute path would silently replace the data root when joined; ".." would escape it.
        if value.is_absolute() or value.drive or value.root or ".." in value.parts:
            raise ValueError(f"must be relative to the data root and stay inside it: {value}")
        return value


class EngineSettings(_Strict):
    # No default: an unset interpretation must stay UNKNOWN, never silently exact/at_least.
    nsqf_level_match: Literal["exact", "at_least"] | None


class PathSettings(_Strict):
    max_steps_default: int = Field(strict=True, ge=1)
    max_steps_limit: int = Field(strict=True, ge=1)
    result_limit: int = Field(strict=True, ge=1)
    max_expansions: int = Field(strict=True, ge=1)

    @model_validator(mode="after")
    def _default_within_limit(self) -> PathSettings:
        if self.max_steps_default > self.max_steps_limit:
            raise ValueError("paths.max_steps_default must not exceed paths.max_steps_limit")
        return self


class InferenceSettings(_Strict):
    enabled: StrictBool


class LabourMarketSettings(_Strict):
    config: Path


class Settings(_Strict):
    data_root: Path
    data: DataPaths
    engine: EngineSettings
    paths: PathSettings
    inference: InferenceSettings
    labour_market: LabourMarketSettings

    def data_path(self, name: str) -> Path:
        """Resolve one ``data.*`` path against the data root, e.g. ``data_path("curated_dir")``."""
        if name not in DataPaths.model_fields:
            raise KeyError(name)
        return self.data_root / getattr(self.data, name)


def _env_path(environ: Mapping[str, str], name: str) -> Path | None:
    value = environ.get(name)
    if value is None:
        return None
    if not value.strip():
        raise SettingsError(f"{name} is set but empty")
    return Path(value)


def load_settings(
    config_path: Path | str | None = None,
    data_root: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load settings. Precedence: explicit argument, then environment, then the default."""
    env = os.environ if environ is None else environ
    path = Path(config_path) if config_path else _env_path(env, ENV_CONFIG) or DEFAULT_CONFIG
    root = Path(data_root) if data_root else _env_path(env, ENV_DATA_ROOT) or DEFAULT_DATA_ROOT

    try:
        with path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except FileNotFoundError:
        raise SettingsError(f"settings file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise SettingsError(f"settings file is not valid YAML: {path}: {exc}") from None
    if not isinstance(raw, dict):
        raise SettingsError(f"settings file must contain a mapping: {path}")
    if "data_root" in raw:
        raise SettingsError("data_root is set by SKILLGRAPH_DATA_ROOT, not in the settings file")

    return Settings.model_validate({**raw, "data_root": root})
