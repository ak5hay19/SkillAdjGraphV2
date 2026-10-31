"""Registered source conflicts and leads (ARCHITECTURE §9.2, §8.6).

A conflict never holds a chosen value: there is no field for one, and the only statuses are unresolved ones.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import StrictFloat, StrictInt, StrictStr, model_validator

from .base import SchemaModel
from .evidence import SAFE_USES, EngineUse
from .ids import ConflictId, DecisionRef, EvidenceId, IdKind, OverlayId, split_id


class ConflictStatus(StrEnum):
    UNRESOLVED_SOURCE_CONFLICT = "UNRESOLVED_SOURCE_CONFLICT"
    UNRESOLVED_LEAD_SOURCE_UNAVAILABLE = "UNRESOLVED_LEAD_SOURCE_UNAVAILABLE"


class ConflictSubject(SchemaModel):
    entity_id: str  # any valid entity id, e.g. qual:AMH/Q2301 or nos:DGT/VSQ/N0102
    field: str

    @model_validator(mode="after")
    def _entity_id_is_valid(self) -> ConflictSubject:
        split_id(self.entity_id)
        return self


class ConflictValue(SchemaModel):
    value: StrictStr | StrictInt | StrictFloat  # as printed by one source
    evidence_id: EvidenceId


class Conflict(SchemaModel):
    id: ConflictId
    subject: ConflictSubject
    values: list[ConflictValue]
    status: ConflictStatus
    overlay_ids: list[OverlayId]  # the conflict group; the id is the lowest of them (ARCHITECTURE §9.1)
    decision_ref: DecisionRef | None = None
    engine_effect: EngineUse

    @model_validator(mode="after")
    def _check(self) -> Conflict:
        if not self.overlay_ids or self.id != f"{IdKind.CONFLICT.value}:{min(self.overlay_ids)}":
            raise ValueError("id must be conflict:<lowest overlay id of the group>, and the group must not be empty")
        if len(set(self.overlay_ids)) != len(self.overlay_ids):
            raise ValueError("overlay_ids must be distinct")
        distinct = {(type(v.value) is str, v.value) for v in self.values}
        if self.status is ConflictStatus.UNRESOLVED_SOURCE_CONFLICT and len(distinct) < 2:
            raise ValueError("a source conflict needs at least two different recorded values")
        if self.status is ConflictStatus.UNRESOLVED_LEAD_SOURCE_UNAVAILABLE and len(distinct) > 1:
            raise ValueError("a lead whose source is unavailable holds no conflicting local value")
        if self.engine_effect in SAFE_USES:
            raise ValueError("a conflicted value cannot have a safe engine_effect")
        return self
