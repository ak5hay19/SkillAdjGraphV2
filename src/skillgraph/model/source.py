"""Source documents (ARCHITECTURE §9.2): one record per MANIFEST item, metadata only."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, StrictInt, StringConstraints, model_validator

from .base import SchemaModel
from .ids import IdKind, Sha256Hex, SourceId, split_id


class LicenceStatus(StrEnum):
    UNCONFIRMED = "UNCONFIRMED"
    PERMITTED = "PERMITTED"
    RESTRICTED = "RESTRICTED"


class SourceRole(StrEnum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"


class ManifestStatus(StrEnum):
    """The ``validation_status`` values that occur in ``MANIFEST.csv`` (run 2026-10-30)."""

    PASS = "PASS"
    PASS_WITH_DISCREPANCIES = "PASS_WITH_DISCREPANCIES"
    FAIL_HTTP = "FAIL_HTTP"
    NOT_FOUND = "NOT_FOUND"


_AVAILABLE = {ManifestStatus.PASS, ManifestStatus.PASS_WITH_DISCREPANCIES}


class SourceDocument(SchemaModel):
    id: SourceId
    manifest_item_id: Annotated[str, StringConstraints(min_length=1)]
    title: Annotated[str, StringConstraints(min_length=1)]
    org: Annotated[str, StringConstraints(min_length=1)]
    url: str | None = None
    retrieved_at: AwareDatetime | None = None
    sha256: Sha256Hex | None = None  # hash of the LOCAL file; null when the item has no local file
    file_type: Literal["pdf", "html"] | None = None
    pages: StrictInt | None = None
    validation_status: ManifestStatus
    licence_status: LicenceStatus = LicenceStatus.UNCONFIRMED  # reuse rights are never assumed
    role: SourceRole  # curation metadata, not in the manifest: always stated explicitly

    @model_validator(mode="after")
    def _check(self) -> SourceDocument:
        if split_id(self.id) != (IdKind.SRC, self.manifest_item_id):
            raise ValueError("id must be src:<manifest_item_id>")
        if self.validation_status in _AVAILABLE and self.sha256 is None:
            raise ValueError(f"{self.validation_status.value} source requires the sha256 of its local file")
        if self.validation_status not in _AVAILABLE and self.sha256 is not None:
            # The manifest records a hash for the error page of C3 and D1; that is not evidence of a source.
            raise ValueError(f"{self.validation_status.value} source has no usable local file: sha256 must be null")
        if self.pages is not None and self.pages < 1:
            raise ValueError("pages must be at least 1")
        return self

    @property
    def has_local_file(self) -> bool:
        return self.sha256 is not None
