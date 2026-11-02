"""OPT-IN adapter: the judge call over raw HTTP to the Anthropic Messages API. Not used by the demo, the API or any test run.

Why raw HTTP: the ``anthropic`` SDK is not a project dependency and installing it needs approval. This module uses ``httpx``
(locked in the ``dev`` extra; ARCHITECTURE 15) and imports it lazily, so nothing else imports it. If the project later adopts the
official SDK, replace ``complete`` and keep the ``Judge`` protocol.

Safety:
- A live call sends the packet (verbatim rule text and evidence metadata from official sources) to a third party. It happens only
  if the caller passes ``allow_external=True`` (the CLI flag ``--allow-external``) AND ``ANTHROPIC_API_KEY`` is set in the
  process environment. ``.env`` files are not read.
- The key is never logged, echoed, stored in a result or shown by ``repr``. Error details carry the HTTP status and the API
  error type only, never the response body.
- No sampling parameter, thinking or tool setting is sent (several current models reject non-default sampling values); the
  model id has no default and must be chosen by the caller. One request, no retries: a failure is an ``ERROR`` case.
- A refusal (``stop_reason: "refusal"``) is an ``ERROR`` (PROVIDER_REFUSAL); no fallback model is configured.
"""

from __future__ import annotations

import os
from typing import Any

from skillgraph.judge.prompt import JudgeRequest
from skillgraph.judge.run import JudgeNotConfigured, JudgeProviderError, JudgeTimeout
from skillgraph.judge.schema import ErrorKind

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
ENV_KEY = "ANTHROPIC_API_KEY"
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_TOKENS = 8000  # non-streaming; leaves room for any thinking the model does before the JSON


class AnthropicJudge:
    def __init__(self, *, model: str, api_key: str, timeout_s: float = DEFAULT_TIMEOUT_S, max_tokens: int = DEFAULT_MAX_TOKENS,
                 url: str = API_URL, transport: Any = None) -> None:
        if not model or not isinstance(model, str):
            raise JudgeNotConfigured("a model id is required (there is no default)")
        if not api_key:
            raise JudgeNotConfigured(f"{ENV_KEY} is not set")
        try:
            import httpx  # noqa: F401  (lazy: only this opt-in module needs it)
        except ImportError:
            raise JudgeNotConfigured("httpx is not installed (it is in the dev extra)") from None
        self.model, self._key, self._timeout, self._max_tokens, self._url, self._transport = (
            model, api_key, timeout_s, max_tokens, url, transport)
        self.judge_id = f"anthropic:{model}"

    @classmethod
    def from_env(cls, *, model: str, allow_external: bool, **kwargs: Any) -> AnthropicJudge:
        if not allow_external:
            raise JudgeNotConfigured("an external call needs the explicit opt-in (allow_external / --allow-external)")
        return cls(model=model, api_key=os.environ.get(ENV_KEY, ""), **kwargs)

    def __repr__(self) -> str:  # the key must never appear in a log or a traceback
        return f"AnthropicJudge(model={self.model!r}, key=<redacted>)"

    def complete(self, request: JudgeRequest) -> str:
        import httpx

        body = {"model": self.model, "max_tokens": self._max_tokens, "system": request.system,
                "messages": [{"role": "user", "content": request.user}]}
        headers = {"x-api-key": self._key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(self._url, json=body, headers=headers)
        except httpx.TimeoutException:
            raise JudgeTimeout from None
        except httpx.HTTPError as exc:
            raise JudgeProviderError(f"network error: {type(exc).__name__}") from None
        if response.status_code != 200:
            err_type = ""
            try:
                err = response.json().get("error", {})
                err_type = str(err.get("type", ""))[:60] if isinstance(err, dict) else ""
            except ValueError:
                pass
            raise JudgeProviderError(f"HTTP {response.status_code} {err_type}".strip())
        try:
            data = response.json()
        except ValueError:
            raise JudgeProviderError("the response is not JSON") from None
        if not isinstance(data, dict):
            raise JudgeProviderError("the response is not an object")
        stop = data.get("stop_reason")
        if stop == "refusal":
            raise JudgeProviderError("the model declined the request", ErrorKind.PROVIDER_REFUSAL)
        if stop == "max_tokens":
            raise JudgeProviderError("the reply was cut off at max_tokens")
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise JudgeProviderError("the response has no content list")
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
        if not text:
            raise JudgeProviderError("the response has no text block")
        return text
