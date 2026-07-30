from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.services import llm_provider
from api.services.llm_provider import (
    GeminiEmptyResponse,
    call_gemini,
    describe_gemini_empty,
    extract_gemini_text,
    gemini_thinking_config,
)
from api.settings import settings


def test_thinking_is_disabled_by_default_on_flash():
    # The shipped default: 2.5 Flash would otherwise spend the whole output
    # budget thinking and return nothing.
    assert gemini_thinking_config("gemini-2.5-flash", 0) == {"thinkingBudget": 0}


def test_zero_budget_is_not_sent_to_models_that_require_thinking():
    # Pro rejects a zero budget with a 400, which is worse than omitting it.
    assert gemini_thinking_config("gemini-2.5-pro", 0) is None


def test_negative_budget_defers_to_gemini():
    assert gemini_thinking_config("gemini-2.5-flash", -1) is None


def test_positive_budget_is_passed_through():
    assert gemini_thinking_config("gemini-2.5-pro", 512) == {"thinkingBudget": 512}


def test_call_gemini_sends_the_thinking_budget(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Max loss stays $420."}]}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, params=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "gemini_thinking_budget", 0)

    result = asyncio.run(call_gemini("system", "prompt", []))

    assert result is not None
    assert result.provider == "gemini"
    assert result.text == "Max loss stays $420."
    assert captured["json"]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_call_gemini_raises_instead_of_falling_back_silently(monkeypatch):
    # A thinking model that burns the budget returns MAX_TOKENS with no parts.
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, params=None, json=None):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")

    with pytest.raises(GeminiEmptyResponse) as excinfo:
        asyncio.run(call_gemini("system", "prompt", []))

    assert "LLM_MAX_OUTPUT_TOKENS" in str(excinfo.value)


def test_empty_response_reasons_are_actionable():
    max_tokens = describe_gemini_empty({"candidates": [{"finishReason": "MAX_TOKENS"}]})
    assert "output budget" in max_tokens

    blocked = describe_gemini_empty({"promptFeedback": {"blockReason": "SAFETY"}})
    assert "SAFETY" in blocked

    unknown = describe_gemini_empty({})
    assert "no finish reason" in unknown


def test_extract_gemini_text_joins_parts():
    payload = {"candidates": [{"content": {"parts": [{"text": " one "}, {"text": "two"}]}}]}
    assert extract_gemini_text(payload) == "one\ntwo"


def test_empty_gemini_error_is_sanitized_for_diagnostics():
    message = llm_provider.sanitize_error(GeminiEmptyResponse("Gemini blocked the prompt (blockReason=SAFETY)."))
    assert "SAFETY" in message
