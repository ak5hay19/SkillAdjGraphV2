"""JSON-lines logging to stderr (ARCHITECTURE §17).

Profile contents are never logged, only the SHA-256 digest of the canonical profile JSON.
Field names that look like secrets are redacted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

LOGGER_NAME = "skillgraph"
REDACTED = "[REDACTED]"
_SECRET_MARKERS = (
    "secret", "token", "password", "passwd", "api_key", "apikey", "private_key",
    "authorization", "cookie", "credential", "bearer",
)
# Any field whose name contains "profile" is withheld; the digest field is the one allowed form.
_PROFILE_MARKER = "profile"
_ALLOWED_FIELDS = ("profile_sha256",)

request_id_var: ContextVar[str | None] = ContextVar("skillgraph_request_id", default=None)


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex[:6]}"


def profile_digest(profile: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical (sorted, compact) profile JSON, as ``sha256:<hex>``."""
    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_sensitive(key: Any) -> bool:
    lowered = str(key).lower()
    if lowered in _ALLOWED_FIELDS:
        return False
    return _PROFILE_MARKER in lowered or any(m in lowered for m in _SECRET_MARKERS)


def _redact(value: Any) -> Any:
    """Redact sensitive keys at every depth of nested mappings and sequences."""
    if isinstance(value, Mapping):
        return {k: REDACTED if _is_sensitive(k) else _redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            for key, value in _redact(fields).items():
                payload.setdefault(key, value)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", stream: TextIO | None = None) -> logging.Logger:
    """Configure the ``skillgraph`` logger. Idempotent: replaces any earlier handler."""
    resolved = logging.getLevelNamesMapping().get(level.upper()) if isinstance(level, str) else None
    if resolved is None:
        raise ValueError(f"unknown log level: {level!r}")
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(resolved)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, event, extra={"fields": fields})


def log_profile(logger: logging.Logger, event: str, profile: Mapping[str, Any], **fields: Any) -> None:
    """Log that a profile was handled, recording only its digest."""
    log_event(logger, event, profile_sha256=profile_digest(profile), **fields)
