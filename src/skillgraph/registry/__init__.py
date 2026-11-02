"""Immutable in-memory registry loaded from a curated build (P3.1)."""

from .store import (
    BuildInfo,
    BuildInvalidError,
    BuildNotFoundError,
    Registry,
    RegistryError,
    UnknownEntityError,
    load,
)

__all__ = [
    "BuildInfo",
    "BuildInvalidError",
    "BuildNotFoundError",
    "Registry",
    "RegistryError",
    "UnknownEntityError",
    "load",
]
