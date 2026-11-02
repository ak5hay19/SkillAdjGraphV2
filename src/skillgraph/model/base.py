"""Shared base class and numeric types for the source-of-truth schemas."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt


class SchemaModel(BaseModel):
    """Immutable, closed models: an unknown field is an error, never silently dropped."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _plain_number(value: object) -> float:
    # A schema never coerces: strings ("12") and booleans are source-format problems for the builder to resolve.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("must be a number (bool and str are not accepted)")
    return float(value)


Number = Annotated[float, BeforeValidator(_plain_number), Field(allow_inf_nan=False)]
Hours = Annotated[Number, Field(ge=0)]
Credits = Annotated[Number, Field(ge=0)]
NsqfLevel = Annotated[Number, Field(ge=1, le=10, multiple_of=0.5)]
MinAge = Annotated[StrictInt, Field(ge=0)]
SNo = Annotated[StrictInt, Field(ge=1)]
