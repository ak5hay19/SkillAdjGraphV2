"""NCO-2015 occupations (ARCHITECTURE §9.2). A title is present only if it was verified in a source."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints, model_validator

from .base import SchemaModel
from .ids import EvidenceId, IdKind, NcoCode, OccupationId, split_id


class TitleVerification(StrEnum):
    VERIFIED_IN_SOURCE = "VERIFIED_IN_SOURCE"
    NOT_FOUND = "NOT_FOUND"
    NOT_CHECKED = "NOT_CHECKED"


class NcoLevels(SchemaModel):
    """Code prefixes of 1, 2, 3 and 4 digits. Pure string derivation from the code: no names, nothing looked up."""

    division: Annotated[str, StringConstraints(pattern=r"^\d$")]
    sub_division: Annotated[str, StringConstraints(pattern=r"^\d{2}$")]
    group: Annotated[str, StringConstraints(pattern=r"^\d{3}$")]
    family: Annotated[str, StringConstraints(pattern=r"^\d{4}$")]

    @classmethod
    def from_code(cls, nco_code: str) -> NcoLevels:
        digits = nco_code.split(".")[0]
        return cls(division=digits[:1], sub_division=digits[:2], group=digits[:3], family=digits[:4])


class Occupation(SchemaModel):
    id: OccupationId
    nco_code: NcoCode
    title: Annotated[str, StringConstraints(min_length=1)] | None = None
    title_verification: TitleVerification
    evidence_id: EvidenceId | None = None  # the evidence for the title (or for the failed search)
    nco_levels: NcoLevels

    @model_validator(mode="before")
    @classmethod
    def _derive_levels(cls, data: object) -> object:
        if isinstance(data, dict) and "nco_levels" not in data and isinstance(data.get("nco_code"), str):
            code = data["nco_code"]
            if len(code.split(".")[0]) >= 4:
                return {**data, "nco_levels": NcoLevels.from_code(code)}
        return data

    @model_validator(mode="after")
    def _check(self) -> Occupation:
        if split_id(self.id) != (IdKind.NCO, self.nco_code):
            raise ValueError("id must be nco:<nco_code>")
        if self.nco_levels != NcoLevels.from_code(self.nco_code):
            raise ValueError("nco_levels must be the prefixes of nco_code")
        if self.title_verification is TitleVerification.VERIFIED_IN_SOURCE:
            if self.title is None or self.evidence_id is None:
                raise ValueError("a VERIFIED_IN_SOURCE title requires the title and its evidence_id")
        elif self.title is not None:
            raise ValueError(f"title must be null when title_verification is {self.title_verification.value}")
        return self
