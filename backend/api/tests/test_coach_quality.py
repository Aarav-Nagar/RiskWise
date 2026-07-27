"""Phase 1 coach-quality tests: real market context in the facts block, markdown stripping,
and the earnings-date fabrication guard. Deterministic risk numbers must stay authoritative."""
from __future__ import annotations

from datetime import date, timedelta

from api.services.llm import (
    authoritative_facts_block,
    clean_answer,
    fabricates_earnings_date,
    fabricates_missing_live_data,
    nearest_earnings_date,
)

FUTURE = (date.today() + timedelta(days=20)).isoformat()

REPORT = {
    "ticker": "AAPL",
    "strike": 230,
    "premium": 4.20,
    "contracts": 1,
    "tradeType": "long call",
    "contractSnapshot": {"impliedVolatility": 0.42},
}

FACT_TOOLS = {
    "max_loss": {"status": "ok", "max_loss": 420, "premium": 4.20, "contracts": 1, "account_risk_pct": 2.1},
    "breakeven": {"status": "ok", "breakeven": 234.2, "formula": "strike + premium"},
    "dte": {"status": "ok", "calendar_days_left": 30},
    "liquidity": {
        "status": "ok",
        "label": "healthy",
        "bid": 4.10,
        "ask": 4.30,
        "spread_width_pct": 4.65,
        "open_interest": 1200,
        "volume": 300,
    },
}


def _tool_context(*, earnings_items=None, liquidity=None):
    fact_tools = dict(FACT_TOOLS)
    if liquidity is not None:
        fact_tools["liquidity"] = liquidity
    ctx = {"coach_context": {"fact_tools": fact_tools}, "tool_results": []}
    if earnings_items is not None:
        ctx["tool_results"].append(
            {"name": "get_earnings", "result": {"status": "ok", "items": earnings_items}}
        )
    return ctx


def test_facts_block_surfaces_delayed_market_context() -> None:
    ctx = _tool_context(earnings_items=[{"date": "2020-01-15"}, {"date": FUTURE}])
    block = authoritative_facts_block(REPORT, ctx)
    # Deterministic numbers unchanged and authoritative.
    assert "Max loss: $420" in block
    assert "Breakeven: $234.20" in block
    # New, clearly-delayed market context.
    assert "Implied volatility: 42%" in block
    assert "Bid/ask: $4.10 / $4.30" in block and "4.65% wide" in block
    assert "open interest 1,200" in block and "volume 300" in block
    assert f"Next earnings: {FUTURE}" in block
    # Everything market-derived is labeled as delayed, never a live quote.
    assert "delayed" in block


def test_facts_block_omits_absent_market_context() -> None:
    bare_report = {k: v for k, v in REPORT.items() if k != "contractSnapshot"}
    ctx = _tool_context(liquidity={"status": "partial_liquidity_data", "label": "unknown_until_confirmed"})
    block = authoritative_facts_block(bare_report, ctx)
    assert "Max loss: $420" in block  # core numbers still present
    assert "Implied volatility" not in block
    assert "Bid/ask" not in block
    assert "Next earnings" not in block


def test_nearest_earnings_prefers_soonest_future() -> None:
    past = "2019-05-01"
    soon = (date.today() + timedelta(days=5)).isoformat()
    far = (date.today() + timedelta(days=90)).isoformat()
    ctx = _tool_context(earnings_items=[{"date": far}, {"date": past}, {"date": soon}])
    assert nearest_earnings_date(ctx) == soon


def test_nearest_earnings_none_when_tool_failed() -> None:
    ctx = {"tool_results": [{"name": "get_earnings", "result": {"status": "needs_provider_key"}}]}
    assert nearest_earnings_date(ctx) is None


def test_clean_answer_strips_markdown() -> None:
    raw = "# Heading\nYour **AAPL** call needs to stay *above* `234.20` before expiry."
    out = clean_answer(raw)
    assert "#" not in out
    assert "*" not in out
    assert "`" not in out
    assert "AAPL" in out and "above" in out and "234.20" in out


def test_clean_answer_leaves_snake_case_identifiers_intact() -> None:
    out = clean_answer("The max_loss stays $420 and the risk_pct is 2.1%.")
    assert "max_loss" in out and "risk_pct" in out


def test_fabricated_earnings_date_rejected_without_context() -> None:
    answer = "your call could get hurt by earnings after august 25, so watch iv into it."
    assert fabricates_earnings_date(answer, {"tool_results": []}) is True


def test_quoting_known_earnings_date_is_allowed() -> None:
    answer = f"earnings land on {FUTURE}, so expect an iv crush after."
    ctx = _tool_context(earnings_items=[{"date": FUTURE}])
    assert fabricates_earnings_date(answer, ctx) is False


def test_expiration_date_mention_not_flagged_as_earnings() -> None:
    # A real expiration date elsewhere in the answer must not trip the earnings guard.
    answer = "expiration is august 15; keep an eye on earnings volatility generally."
    assert fabricates_earnings_date(answer, {"tool_results": []}) is False


def test_earnings_percent_not_read_as_date() -> None:
    answer = "earnings may cut iv by 25% overnight."
    assert fabricates_earnings_date(answer, {"tool_results": []}) is False


# --- reconciliation: delayed values RiskWise surfaced must be quotable, not "fabrication" ---

_LIQ_KNOWN = {
    "status": "ok", "label": "healthy", "bid": 4.10, "ask": 4.35,
    "spread_width_pct": 5.75, "open_interest": 1800, "volume": 640, "implied_volatility": 0.41,
}
_ANSWER_QUOTING_MARKET = "iv is 41%, bid is $4.10, ask is $4.35, open interest is 1,800, volume is 640."


def _fallback(liquidity):
    return {
        "missing_data": ["Greeks", "company profile"],  # something is missing -> guard is active
        "normalized_context": {"coach_context": {"fact_tools": {"liquidity": liquidity}}},
    }


def test_quoting_surfaced_delayed_data_is_not_fabrication() -> None:
    fallback = _fallback(_LIQ_KNOWN)
    ctx = {"coach_context": {"fact_tools": {"liquidity": _LIQ_KNOWN}}}
    assert fabricates_missing_live_data(_ANSWER_QUOTING_MARKET, fallback, ctx) is False


def test_quoting_absent_market_data_is_still_fabrication() -> None:
    empty_liq = {"status": "partial_liquidity_data", "label": "unknown_until_confirmed"}
    fallback = _fallback(empty_liq)
    ctx = {"coach_context": {"fact_tools": {"liquidity": empty_liq}}}
    assert fabricates_missing_live_data(_ANSWER_QUOTING_MARKET, fallback, ctx) is True


def test_partial_knowledge_gates_only_absent_fields() -> None:
    # IV/bid-ask known, but volume/OI absent: quoting IV is fine, quoting volume is fabrication.
    liq = {"status": "ok", "bid": 4.10, "ask": 4.35, "implied_volatility": 0.41}
    fallback = _fallback(liq)
    ctx = {"coach_context": {"fact_tools": {"liquidity": liq}}}
    assert fabricates_missing_live_data("iv is 41% and bid is $4.10.", fallback, ctx) is False
    assert fabricates_missing_live_data("open interest is 1,800 contracts.", fallback, ctx) is True
