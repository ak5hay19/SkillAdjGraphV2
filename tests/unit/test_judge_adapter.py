"""The opt-in provider adapter, tested entirely offline with ``httpx.MockTransport`` (no socket, no key, no model)."""

import json
import socket

import httpx
import pytest
from test_judge_core import a_packet, dataset, outcomes

from skillgraph.judge import CaseStatus, ErrorKind, JudgeNotConfigured, JudgeProviderError, JudgeTimeout, evaluate_case
from skillgraph.judge.anthropic_adapter import API_VERSION, AnthropicJudge
from skillgraph.judge.prompt import build_request

KEY = "sk-ant-test-0000-not-a-real-key"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("an adapter test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def judge(handler, **kw) -> AnthropicJudge:
    return AnthropicJudge(model="test-model", api_key=KEY, transport=httpx.MockTransport(handler), **kw)


def ok(text: str, **extra):
    return lambda request: httpx.Response(200, json={"content": [{"type": "text", "text": text}], "stop_reason": "end_turn", **extra})


def test_a_valid_reply_gives_a_pass_through_the_whole_pipeline():
    result = evaluate_case(a_packet(), judge(ok(outcomes())))
    assert result.status is CaseStatus.PASS and result.judge_id == "anthropic:test-model"


def test_thinking_blocks_are_ignored_and_text_blocks_joined():
    body = outcomes()
    handler = lambda r: httpx.Response(200, json={"stop_reason": "end_turn", "content": [
        {"type": "thinking", "thinking": "private"}, {"type": "text", "text": body[:10]}, {"type": "text", "text": body[10:]}]})
    assert judge(handler).complete(build_request(a_packet())) == body


def test_the_request_shape_has_no_sampling_thinking_or_tool_settings_and_the_key_only_in_a_header():
    seen = {}

    def handler(request: httpx.Request):
        seen["headers"], seen["body"], seen["raw"] = request.headers, json.loads(request.content), request.content.decode()
        return httpx.Response(200, json={"content": [{"type": "text", "text": outcomes()}], "stop_reason": "end_turn"})

    req = build_request(a_packet())
    judge(handler).complete(req)
    assert seen["headers"]["x-api-key"] == KEY and seen["headers"]["anthropic-version"] == API_VERSION
    assert set(seen["body"]) == {"model", "max_tokens", "system", "messages"}
    assert seen["body"]["system"] == req.system and seen["body"]["messages"] == [{"role": "user", "content": req.user}]
    assert KEY not in seen["raw"]


def test_a_timeout_is_a_judge_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)
    assert evaluate_case(a_packet(), judge(handler)).error_kind is ErrorKind.PROVIDER_TIMEOUT
    with pytest.raises(JudgeTimeout):
        judge(handler).complete(build_request(a_packet()))


def test_a_network_error_is_a_provider_error_naming_only_the_exception_type():
    def handler(request):
        raise httpx.ConnectError("secret-host.internal refused", request=request)
    with pytest.raises(JudgeProviderError) as e:
        judge(handler).complete(build_request(a_packet()))
    assert "ConnectError" in e.value.detail and "secret-host" not in e.value.detail


def test_an_http_error_reports_status_and_error_type_never_the_body():
    handler = lambda r: httpx.Response(401, json={"error": {"type": "authentication_error", "message": f"bad key {KEY}"}})
    result = evaluate_case(a_packet(), judge(handler))
    assert result.error_kind is ErrorKind.PROVIDER_ERROR and "401 authentication_error" in result.error_detail
    assert KEY not in result.model_dump_json()


@pytest.mark.parametrize(("payload", "kind"), [
    ({"stop_reason": "refusal", "content": []}, ErrorKind.PROVIDER_REFUSAL),
    ({"stop_reason": "max_tokens", "content": [{"type": "text", "text": "{"}]}, ErrorKind.PROVIDER_ERROR),
    ({"stop_reason": "end_turn", "content": []}, ErrorKind.PROVIDER_ERROR),
    ({"stop_reason": "end_turn", "content": "x"}, ErrorKind.PROVIDER_ERROR),
])
def test_refusal_truncation_and_empty_replies_are_errors(payload, kind):
    assert evaluate_case(a_packet(), judge(lambda r: httpx.Response(200, json=payload))).error_kind is kind


def test_a_non_json_body_is_a_provider_error():
    assert evaluate_case(a_packet(), judge(lambda r: httpx.Response(200, text="<html>"))).error_kind is ErrorKind.PROVIDER_ERROR


def test_a_model_that_replies_with_a_verdict_field_is_rejected_by_the_schema():
    bad = json.loads(outcomes())
    bad["verdict"] = "MET"
    assert evaluate_case(a_packet(), judge(ok(json.dumps(bad)))).error_kind is ErrorKind.SCHEMA_INVALID


# ---- opt-in and configuration -------------------------------------------------------------------------------------------


def test_construction_needs_a_model_and_a_key():
    with pytest.raises(JudgeNotConfigured):
        AnthropicJudge(model="", api_key=KEY)
    with pytest.raises(JudgeNotConfigured):
        AnthropicJudge(model="m", api_key="")


def test_from_env_requires_the_explicit_opt_in_even_when_a_key_is_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    with pytest.raises(JudgeNotConfigured, match="opt-in"):
        AnthropicJudge.from_env(model="m", allow_external=False)
    assert AnthropicJudge.from_env(model="m", allow_external=True).judge_id == "anthropic:m"


def test_from_env_without_a_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(JudgeNotConfigured, match="ANTHROPIC_API_KEY"):
        AnthropicJudge.from_env(model="m", allow_external=True)


def test_the_key_is_not_in_the_repr_or_the_result():
    j = judge(ok(outcomes()))
    assert KEY not in repr(j) and "redacted" in repr(j)
    assert KEY not in evaluate_case(a_packet(), j).model_dump_json()


def test_a_one_dimension_reply_that_ends_with_end_turn_is_an_error_and_keeps_the_precheck_signal():
    # The shape of the first live call: HTTP 200, stop_reason end_turn (so not truncated), valid JSON, one dimension only.
    case = next(c for c in dataset().cases if c.case_id == "g08-verdict-contradiction")
    one = json.dumps({"dimensions": [{"dimension": "EVIDENCE_FAITHFULNESS", "outcome": "FAIL", "findings": [
        {"excerpt": "the age requirement is not met", "evidence_ids": ["ev:0000000000000001"], "rationale": "x"}]}]})
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"content": [{"type": "text", "text": one}], "stop_reason": "end_turn",
                                         "usage": {"input_tokens": 2289, "output_tokens": 157}})

    result = evaluate_case(case.packet, judge(handler))
    assert len(sent) == 1                                           # no retry, no repair call
    assert result.status is CaseStatus.ERROR and result.error_kind is ErrorKind.SCHEMA_INVALID
    assert "five dimensions" in result.error_detail and result.dimensions == ()
    assert {s.family for s in result.precheck} == {"VERDICT_CONTRADICTION"} and result.engine_verdict == "MET"
