"""Stable identifiers (ARCHITECTURE §9.1).

Every entity has an ``id`` of the form ``<kind>:<official-key>`` (the build id is ``cb-<hex>``). A slug is a lookup
key only: it is derived from an id, resolved through a ``SlugIndex``, and never parsed back into a code.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints


class IdError(ValueError):
    """A malformed identifier, or a registry violation."""


class SlugCollisionError(IdError):
    """Two different ids map to one slug (the build must fail)."""


class DuplicateIdError(IdError):
    """The same id was registered twice."""


class UnknownSlugError(IdError):
    """A slug that is not in the index."""


class IdKind(StrEnum):
    QUAL = "qual"
    NOS = "nos"
    MOD = "mod"
    NCO = "nco"
    SRC = "src"
    RULE = "rule"
    CLAIM = "claim"
    CONFLICT = "conflict"
    EV = "ev"
    CB = "cb"


# Key grammars, written from the codes present in the evidence (qualification, NOS, NCO, manifest item and overlay IDs).
QUAL_CODE = r"[A-Z]{2,6}/Q\d{4}"
NOS_CODE = r"[A-Z]{2,6}(?:/[A-Z]{2,6})?/N\d{4}"
NCO_CODE = r"\d{4}\.\d{4}"
SOURCE_KEY = r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
OVERLAY_KEY = r"OV-\d{3}"
SHA256 = r"[0-9a-f]{64}"

KEY_PATTERNS: dict[IdKind, str] = {
    IdKind.QUAL: QUAL_CODE,
    IdKind.NOS: NOS_CODE,
    IdKind.MOD: rf"{QUAL_CODE}/S\d{{1,3}}",
    IdKind.NCO: NCO_CODE,
    IdKind.SRC: SOURCE_KEY,
    IdKind.RULE: rf"{QUAL_CODE}/(?:E\d{{1,3}}|AGE)",
    IdKind.CLAIM: rf"{QUAL_CODE}/P\d{{1,3}}",
    IdKind.CONFLICT: OVERLAY_KEY,
    IdKind.EV: r"[0-9a-f]{16}",
    IdKind.CB: r"[0-9a-f]{12}",
}
_COMPILED = {k: re.compile(p) for k, p in KEY_PATTERNS.items()}
_SLUG_KINDS = {IdKind.QUAL, IdKind.NOS, IdKind.MOD, IdKind.NCO, IdKind.SRC, IdKind.EV}


def _prefix(kind: IdKind) -> str:
    return "cb-" if kind is IdKind.CB else f"{kind.value}:"


def _id_pattern(kind: IdKind) -> str:
    return rf"^{re.escape(_prefix(kind))}{KEY_PATTERNS[kind]}$"


def _typed(kind: IdKind):
    return Annotated[str, StringConstraints(pattern=_id_pattern(kind))]


# Field types for models. Format only: whether the referenced entity exists is a build/validation concern.
QualificationId = _typed(IdKind.QUAL)
NosId = _typed(IdKind.NOS)
ModuleId = _typed(IdKind.MOD)
OccupationId = _typed(IdKind.NCO)
SourceId = _typed(IdKind.SRC)
RuleId = _typed(IdKind.RULE)
ClaimId = _typed(IdKind.CLAIM)
ConflictId = _typed(IdKind.CONFLICT)
EvidenceId = _typed(IdKind.EV)
BuildId = _typed(IdKind.CB)

QualificationCode = Annotated[str, StringConstraints(pattern=rf"^{QUAL_CODE}$")]
NosCode = Annotated[str, StringConstraints(pattern=rf"^{NOS_CODE}$")]
NcoCode = Annotated[str, StringConstraints(pattern=rf"^{NCO_CODE}$")]
OverlayId = Annotated[str, StringConstraints(pattern=rf"^{OVERLAY_KEY}$")]
DecisionRef = Annotated[str, StringConstraints(pattern=r"^[AD]\d+$")]
Sha256Hex = Annotated[str, StringConstraints(pattern=rf"^{SHA256}$")]


def make_id(kind: IdKind, key: str) -> str:
    """``make_id(IdKind.QUAL, "AMH/Q0301") -> "qual:AMH/Q0301"``; raises ``IdError`` if the key is not valid."""
    if not _COMPILED[kind].fullmatch(key):
        raise IdError(f"invalid {kind.value} key: {key!r}")
    return _prefix(kind) + key


def split_id(entity_id: str) -> tuple[IdKind, str]:
    """Inverse of ``make_id``; raises ``IdError`` for anything that is not a well-formed id."""
    for kind in IdKind:
        prefix = _prefix(kind)
        if entity_id.startswith(prefix):
            key = entity_id[len(prefix) :]
            if _COMPILED[kind].fullmatch(key):
                return kind, key
            break
    raise IdError(f"not a valid identifier: {entity_id!r}")


def code_of(entity_id: str) -> str:
    """The official key behind an id (``qual:AMH/Q0301`` -> ``AMH/Q0301``)."""
    return split_id(entity_id)[1]


def slug_of(entity_id: str) -> str | None:
    """URL-safe lookup key (ARCHITECTURE §9.1), or None for kinds that have none.

    qualification, NOS and module slugs replace ``/`` by ``.``; occupation and source slugs are their key; an
    evidence slug is its id. Rule, claim, conflict and build ids have no slug.
    """
    kind, key = split_id(entity_id)
    if kind not in _SLUG_KINDS:
        return None
    if kind is IdKind.EV:
        return entity_id
    return key.replace("/", ".")


class SlugIndex:
    """Slug -> id lookup. Registering two ids under one slug raises; a slug is never parsed back into a code."""

    def __init__(self) -> None:
        self._by_slug: dict[str, str] = {}
        self._ids: set[str] = set()

    def add(self, entity_id: str, slug: str | None = None) -> str:
        """Register ``entity_id`` under ``slug`` (default: ``slug_of``) and return the slug."""
        derived = slug_of(entity_id)  # also validates the id
        slug = derived if slug is None else slug
        if slug is None:
            raise IdError(f"{entity_id} has no slug")
        if entity_id in self._ids:
            raise DuplicateIdError(f"id registered twice: {entity_id}")
        holder = self._by_slug.get(slug)
        if holder is not None:
            raise SlugCollisionError(f"slug {slug!r} is claimed by both {holder} and {entity_id}")
        self._by_slug[slug] = entity_id
        self._ids.add(entity_id)
        return slug

    def lookup(self, slug: str) -> str:
        try:
            return self._by_slug[slug]
        except KeyError:
            raise UnknownSlugError(f"unknown slug: {slug!r}") from None

    def __contains__(self, slug: object) -> bool:
        return slug in self._by_slug

    def __len__(self) -> int:
        return len(self._by_slug)
