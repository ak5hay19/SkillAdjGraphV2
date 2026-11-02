"""Curation configuration (config/curation_defaults.yaml): documented engine_use defaults, conflict groups, open
leads, title aliases. Strict: unknown keys, unknown engine_use values and malformed entries are errors."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from skillgraph.model.evidence import EngineUse
from skillgraph.model.ids import DecisionRef, OverlayId, QualificationCode

DEFAULTS_PATH = Path("config/curation_defaults.yaml")
# Bumped by hand whenever curation logic changes in a way that can change the output (ARCHITECTURE §7 principle 4).
# p1.5-1: Qualification.eligibility is now built from the structured eligibility rules (P1.5 Checkpoint C), and the
# age rows carry their verbatim text (A1). The eligibility table digest is part of the build identity.
CURATION_CODE_VERSION = "p1.5-1"

_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConfigError(Exception):
    """The curation configuration is missing or malformed."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EngineUseDefault(_Strict):
    file: _Text
    field: _Text
    only_for: tuple[_Text, ...] = ()  # facts.csv: restrict to these `field` values
    engine_use: EngineUse
    basis: _Text


class ConflictSubjectCfg(_Strict):
    entity_id: _Text
    field: _Text


class ConflictValueCfg(_Strict):
    overlay: OverlayId | None = None
    derived: Literal["sum_qf_nos_credits"] | None = None
    qualification: QualificationCode | None = None
    qp_row: dict[str, str] | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> ConflictValueCfg:
        if sum(x is not None for x in (self.overlay, self.derived, self.qp_row)) != 1:
            raise ValueError("a conflict value names exactly one of overlay, derived, qp_row")
        if self.derived and not self.qualification:
            raise ValueError("a derived value names its qualification")
        return self


class ConflictGroupCfg(_Strict):
    id: OverlayId
    overlays: tuple[OverlayId, ...] = Field(min_length=1)
    subject: ConflictSubjectCfg
    decision_ref: DecisionRef
    engine_effect: EngineUse
    values: tuple[ConflictValueCfg, ...] = Field(min_length=2)
    attach: tuple[_Text, ...] = ()

    @model_validator(mode="after")
    def _id_is_lowest(self) -> ConflictGroupCfg:
        if self.id != min(self.overlays):
            raise ValueError("a conflict id is the lowest overlay id of its group")
        return self


class OpenLeadCfg(_Strict):
    id: _Text
    status: Literal["UNRESOLVED_LEAD_SOURCE_UNAVAILABLE"]
    qualification: QualificationCode
    subject: _Text
    source_item: _Text
    reference: _Text


class TitleAliasCfg(_Strict):
    qualification: QualificationCode
    kind: Literal["qp"]
    title: _Text
    source_item: _Text
    validation_item: _Text
    location: _Text


class CurationConfig(_Strict):
    engine_use_defaults: tuple[EngineUseDefault, ...]
    conflict_groups: tuple[ConflictGroupCfg, ...]
    open_leads: tuple[OpenLeadCfg, ...]
    title_aliases: tuple[TitleAliasCfg, ...]
    pilot_qualifications: tuple[QualificationCode, ...] = Field(min_length=1)
    expected_catalogue_only: int = Field(ge=0)
    expected_overlay_rows: int | None = Field(default=None, ge=1)  # a dropped overlay row must not pass silently
    catalogue_source_item: _Text  # manifest item of the catalogue page the parsed CSV derives from

    @model_validator(mode="after")
    def _unique(self) -> CurationConfig:
        keys = [(d.file, d.field, d.only_for) for d in self.engine_use_defaults]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate engine_use default")
        ov = [o for g in self.conflict_groups for o in g.overlays]
        if len(set(ov)) != len(ov):
            raise ValueError("an overlay id belongs to at most one conflict group")
        return self

    def default_engine_use(self, file: str, field: str, discriminator: str | None = None) -> EngineUse:
        """The documented default for a source cell, or UNKNOWN (never a guess)."""
        for d in self.engine_use_defaults:
            if d.file == file and d.field == field and (not d.only_for or discriminator in d.only_for):
                return d.engine_use
        return EngineUse.UNKNOWN


def load_config(path: Path) -> tuple[CurationConfig, str]:
    """Parse the configuration; returns it with ``sha256:<hex>`` of the file bytes (part of the build id)."""
    try:
        data = path.read_bytes()
        parsed = yaml.safe_load(data.decode("utf-8"))
        return CurationConfig.model_validate(parsed), "sha256:" + hashlib.sha256(data).hexdigest()
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read curation configuration {path}: {exc}") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"curation configuration is not valid YAML: {path}: {' '.join(str(exc).split())}") from None
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ConfigError(f"{path.name}: {msg}") from None
