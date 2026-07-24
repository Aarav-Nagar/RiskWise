from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.settings import settings
from api.services import llm_provider
from api.services.llm_provider import (
    LLMResult,
    call_openrouter,
    configured_providers,
    generate_answer,
    provider_kind,
)
from api.services.llm import (
    authoritative_facts_block,
    build_llm_prompt,
    fabricates_missing_live_data,
    ignores_selected_trade,
    llm_answer_rejection_reasons,
)


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeAsyncOpenAI:
    """Records constructor kwargs and stands in for AsyncOpenAI so no network call happens."""

    last_instance: "_FakeAsyncOpenAI | None" = None
    content = "For your AAPL 230 call, max loss stays the premium and breakeven is strike plus premium."

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chat = _FakeChat(self.content)
        _FakeAsyncOpenAI.last_instance = self


# Distinct sentinels so the text-vs-vision routing assertion is unambiguous regardless of the real
# defaults (which currently point both at the same instruction-tuned model).
TEXT_MODEL = "test/text-model"
VISION_MODEL = "test/vision-model"


def _with_openrouter(monkeypatch) -> None:
    monkeypatch.setattr(llm_provider, "AsyncOpenAI", _FakeAsyncOpenAI)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(settings, "openrouter_model", TEXT_MODEL)
    monkeypatch.setattr(settings, "openrouter_vision_model", VISION_MODEL)
    monkeypatch.setattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(settings, "llm_provider_order", ["openrouter", "fallback"])
    llm_provider.PROVIDER_FAILURES.pop("openrouter", None)


def test_call_openrouter_uses_chat_completions_wire_format(monkeypatch) -> None:
    _with_openrouter(monkeypatch)

    result = asyncio.run(call_openrouter("system rules", "explain this AAPL 230 call", []))

    assert isinstance(result, LLMResult)
    assert result.provider == "openrouter"
    assert result.model == TEXT_MODEL

    client = _FakeAsyncOpenAI.last_instance
    assert client is not None
    # Routed at the OpenRouter gateway, not api.openai.com.
    assert client.kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert client.kwargs["api_key"] == "test-openrouter-key"
    # Chat Completions, not the Responses API: messages + max_tokens, never `input`.
    call = client.chat.completions.calls[0]
    assert "messages" in call
    assert "input" not in call
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["role"] == "user"
    # No image attached -> plain-string user content.
    assert call["messages"][1]["content"] == "explain this AAPL 230 call"


def test_call_openrouter_switches_to_multipart_content_for_images(monkeypatch) -> None:
    _with_openrouter(monkeypatch)
    attachment = {
        "type": "image/png",
        "dataUrl": "data:image/png;base64,iVBORw0KGgo=",
    }

    result = asyncio.run(call_openrouter("system rules", "read this screenshot", [attachment]))

    call = _FakeAsyncOpenAI.last_instance.chat.completions.calls[0]
    content = call["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "read this screenshot"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    # Image requests route to the vision model, not the text-only reasoning model.
    assert call["model"] == VISION_MODEL
    assert result.model == VISION_MODEL


def test_generate_answer_routes_to_openrouter_first(monkeypatch) -> None:
    _with_openrouter(monkeypatch)

    result = asyncio.run(
        generate_answer(system_prompt="system rules", prompt="explain this AAPL 230 call")
    )

    assert result is not None
    assert result.provider == "openrouter"
    assert "230 call" in result.text


def test_configured_providers_reports_openrouter_as_hosted(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(settings, "openrouter_model", TEXT_MODEL)
    monkeypatch.setattr(settings, "llm_provider_order", ["openrouter", "fallback"])

    providers = {item["provider"]: item for item in configured_providers()}

    assert "openrouter" in providers
    assert providers["openrouter"]["configured"] is True
    assert providers["openrouter"]["kind"] == "hosted"
    assert providers["openrouter"]["model"] == TEXT_MODEL
    assert provider_kind("openrouter") == "hosted"


# --- Guard normalization fix (ignores_selected_trade) ---------------------------------------------


def _trade_fallback(ticker: str, strike) -> dict:
    return {
        "missing_data": [],
        "normalized_context": {
            "ticker": ticker,
            "selected_contract": {"strike": strike},
        },
    }


def test_guard_matches_float_strike_against_integer_text() -> None:
    # Stored as 230.0; answer says "230" -> must NOT be treated as ignoring the trade.
    fallback = _trade_fallback("AAPL", 230.0)
    answer = "your aapl 230 call needs the stock above breakeven before expiration"
    assert ignores_selected_trade(answer, fallback, "trade_review") is False


def test_guard_does_not_require_ticker_literal_when_strike_present() -> None:
    # Mentions the strike but omits the ticker literal -> still on-topic, not rejected.
    fallback = _trade_fallback("AAPL", 230)
    answer = "the 230 call loses its full premium if the move never happens by expiration"
    assert ignores_selected_trade(answer, fallback, "trade_review") is False


def test_guard_rejects_answer_referencing_neither_ticker_nor_strike() -> None:
    fallback = _trade_fallback("AAPL", 230.0)
    answer = "options can lose value quickly when volatility drops after an event"
    assert ignores_selected_trade(answer, fallback, "trade_review") is True
    reasons = llm_answer_rejection_reasons(answer, fallback, "trade_review", "why is this risky?", {"tool_results": []})
    assert "ignored_selected_trade" in reasons


def test_guard_rejects_explicit_no_trade_disclaimer() -> None:
    fallback = _trade_fallback("AAPL", 230.0)
    answer = "i do not see a trade attached, so share the ticker, strike, and premium"
    assert ignores_selected_trade(answer, fallback, "trade_review") is True


def test_guard_strike_match_is_bounded_not_substring() -> None:
    # A strike of 230 must not be considered "mentioned" just because 2300 appears.
    fallback = _trade_fallback("", 230)
    answer = "there were 2300 contracts of open interest across the chain"
    assert ignores_selected_trade(answer, fallback, "trade_review") is True


# --- Authoritative-facts prompt block (deterministic numbers stay authoritative) ------------------


def _tool_context_with_facts() -> dict:
    return {
        "missing_data": ["bid/ask", "implied volatility", "open interest"],
        "coach_context": {
            "ticker": "AAPL",
            "missing_data": ["bid/ask", "implied volatility", "open interest"],
            "fact_tools": {
                "max_loss": {
                    "status": "ok",
                    "max_loss": 420,
                    "premium": 4.20,
                    "contracts": 1,
                    "account_risk_pct": 4.2,
                },
                "breakeven": {"status": "ok", "breakeven": 234.2, "formula": "strike + premium"},
                "dte": {"status": "ok", "calendar_days_left": 30},
                "liquidity": {"status": "missing_contract", "label": None},
            },
        },
    }


def test_authoritative_facts_block_pins_deterministic_numbers() -> None:
    report = {"ticker": "AAPL", "tradeType": "Call Option (Long)", "strike": 230, "premium": 4.20, "contracts": 1}
    block = authoritative_facts_block(report, _tool_context_with_facts())

    assert "AUTHORITATIVE NUMBERS" in block
    assert "quote exactly, never recompute" in block
    assert "Max loss: $420" in block
    assert "Breakeven: $234.20" in block
    assert "Premium paid: $4.20" in block
    assert "30 calendar days" in block
    # Missing live data must be named so the model does not invent it.
    assert "do not invent it" in block
    assert "implied volatility" in block


def test_authoritative_facts_block_empty_without_a_trade() -> None:
    # Concept questions carry no selected trade -> no facts block (nothing to pin).
    empty = {"coach_context": {"fact_tools": {}}, "missing_data": []}
    assert authoritative_facts_block(None, empty) == ""


# --- Fabrication guard must not false-reject an authoritative premium -----------------------------


def _fabrication_fallback(premium) -> dict:
    return {
        "missing_data": ["bid/ask", "implied volatility", "open interest"],
        "normalized_context": {
            "selected_contract": {"strike": 230.0, "premium": premium},
            "coach_context": {
                "fact_tools": {
                    "max_loss": {"status": "ok", "max_loss": 420, "premium": premium},
                    "breakeven": {"status": "ok", "breakeven": 234.2, "premium": premium},
                }
            },
        },
    }


def test_quoting_a_known_premium_is_not_flagged_as_fabrication() -> None:
    # Premium is user-entered, so "the premium is $4.20" is authoritative even though IV/bid-ask are missing.
    fallback = _fabrication_fallback(4.20)
    answer = "the premium is $4.20 and that whole amount is your max loss on this long call"
    assert fabricates_missing_live_data(answer, fallback) is False


def test_fabricated_premium_is_still_flagged_when_premium_unknown() -> None:
    # No premium was provided -> the model has no business asserting one.
    fallback = _fabrication_fallback(None)
    answer = "the premium is $4.20 based on the current chain"
    assert fabricates_missing_live_data(answer, fallback) is True


def test_fabricated_live_iv_is_still_flagged_even_with_known_premium() -> None:
    # Loosening the premium check must not weaken the genuine live-data guards.
    fallback = _fabrication_fallback(4.20)
    answer = "implied volatility is 38% right now so the contract is cheap here"
    assert fabricates_missing_live_data(answer, fallback) is True


def test_build_llm_prompt_puts_facts_block_first() -> None:
    report = {"ticker": "AAPL", "tradeType": "Call Option (Long)", "strike": 230, "premium": 4.20, "contracts": 1}
    prompt = build_llm_prompt(
        "Why is this risky?",
        "trade_review",
        report,
        None,
        "Review",
        [],
        [],
        [],
        _tool_context_with_facts(),
    )
    assert prompt.startswith("AUTHORITATIVE NUMBERS")
    # The full tool context is still serialized later for completeness.
    assert "Server tool results JSON" in prompt
