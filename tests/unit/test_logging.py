import io
import json
import logging

import pytest

from skillgraph.logging_setup import (
    REDACTED,
    log_event,
    log_profile,
    new_request_id,
    profile_digest,
    request_id_var,
    setup_logging,
)

PROFILE = {"age": 24, "name": "Test Person", "qualifications": ["TEST/Q9001"]}


def _detach(logger):
    for h in list(logger.handlers):
        logger.removeHandler(h)


@pytest.fixture
def stream():
    buf = io.StringIO()
    logger = setup_logging("DEBUG", buf)
    yield buf
    _detach(logger)


def _lines(buf):
    return [json.loads(line) for line in buf.getvalue().splitlines()]


def test_emits_json_with_event_and_request_id(stream):
    token = request_id_var.set("req-abc123")
    try:
        log_event(logging.getLogger("skillgraph.test"), "thing_happened", count=3)
    finally:
        request_id_var.reset(token)
    (rec,) = _lines(stream)
    assert rec["event"] == "thing_happened"
    assert rec["request_id"] == "req-abc123"
    assert rec["count"] == 3
    assert rec["level"] == "INFO"
    assert rec["logger"] == "skillgraph.test"


def test_request_id_is_null_outside_a_request(stream):
    log_event(logging.getLogger("skillgraph"), "startup")
    assert _lines(stream)[0]["request_id"] is None


def test_new_request_id_format():
    assert new_request_id().startswith("req-")
    assert new_request_id() != new_request_id()


def test_profile_logged_only_as_digest(stream):
    log_profile(logging.getLogger("skillgraph"), "eligibility_evaluated", PROFILE)
    raw = stream.getvalue()
    (rec,) = _lines(stream)
    assert rec["profile_sha256"] == profile_digest(PROFILE)
    assert rec["profile_sha256"].startswith("sha256:")
    assert "Test Person" not in raw
    assert "TEST/Q9001" not in raw
    assert "qualifications" not in raw


def test_profile_digest_is_canonical():
    assert profile_digest({"a": 1, "b": 2}) == profile_digest({"b": 2, "a": 1})
    assert profile_digest({"a": 1}) != profile_digest({"a": 2})


def test_profile_field_and_secrets_are_redacted(stream):
    log_event(
        logging.getLogger("skillgraph"),
        "oops",
        profile=PROFILE,
        api_key="sk-secret-value",
        Authorization="Bearer abc",
        route="/x",
    )
    raw = stream.getvalue()
    rec = _lines(stream)[0]
    assert rec["profile"] == rec["api_key"] == rec["Authorization"] == REDACTED
    assert rec["route"] == "/x"
    assert "sk-secret-value" not in raw
    assert "Test Person" not in raw


def test_reserved_keys_cannot_be_overwritten(stream):
    logging.getLogger("skillgraph").info(
        "real_event", extra={"fields": {"event": "spoofed", "level": "DEBUG", "request_id": "forged"}}
    )
    rec = _lines(stream)[0]
    assert rec["event"] == "real_event"
    assert rec["level"] == "INFO"
    assert rec["request_id"] is None


def test_level_filtering_and_validation():
    buf = io.StringIO()
    logger = setup_logging("WARNING", buf)
    try:
        log_event(logger, "quiet")
        log_event(logger, "loud", logging.ERROR)
        assert [r["event"] for r in _lines(buf)] == ["loud"]
        with pytest.raises(ValueError):
            setup_logging("LOUD")
    finally:
        _detach(logger)


def test_setup_is_idempotent_and_does_not_propagate():
    a, b = io.StringIO(), io.StringIO()
    setup_logging("INFO", a)
    logger = setup_logging("INFO", b)
    try:
        assert len(logger.handlers) == 1
        assert logger.propagate is False
        log_event(logger, "once")
        assert a.getvalue() == ""
        assert b.getvalue() != ""
    finally:
        _detach(logger)


def test_nested_and_alternate_field_names_are_redacted(stream):
    log_event(
        logging.getLogger("skillgraph"),
        "nested",
        payload={"user_profile": PROFILE, "ok": 1, "items": [{"Session_Token": "abc"}, {"fine": 2}]},
        hypothetical_profile=PROFILE,
        private_key="pk",
        profile_sha256="sha256:keepme",
    )
    raw = stream.getvalue()
    rec = _lines(stream)[0]
    assert rec["payload"]["user_profile"] == REDACTED
    assert rec["payload"]["items"][0]["Session_Token"] == REDACTED
    assert rec["payload"]["items"][1] == {"fine": 2}
    assert rec["payload"]["ok"] == 1
    assert rec["hypothetical_profile"] == rec["private_key"] == REDACTED
    assert rec["profile_sha256"] == "sha256:keepme"
    for leaked in ("Test Person", "TEST/Q9001", "abc", "pk"):
        assert f'"{leaked}"' not in raw


def test_exception_logs_type_but_not_message(stream):
    try:
        raise RuntimeError("contains Test Person data")
    except RuntimeError:
        logging.getLogger("skillgraph").error("failed", exc_info=True)
    raw = stream.getvalue()
    assert _lines(stream)[0]["exc_type"] == "RuntimeError"
    assert "Test Person" not in raw
