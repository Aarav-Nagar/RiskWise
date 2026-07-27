"""Best-effort delayed-chain rows for the alternatives engine.

Uses the existing yfinance delayed integration in services/market_data.py.
Everything here is optional context: when nothing can be fetched the engine
simply marks premium-dependent candidates as "needs_live_premium" instead of
inventing prices.
"""

from __future__ import annotations

from typing import Any

from ..market_data import yfinance_enabled, yfinance_option_chain
from ...probability import calendar_days_to_expiry
from .engine import MIN_LATER_EXPIRY_GAP_DAYS, original_trade_facts


async def gather_market_contracts(report: dict[str, Any]) -> list[dict[str, Any]]:
    facts = original_trade_facts(report)
    if not facts["ticker"] or not yfinance_enabled():
        return []
    try:
        result = yfinance_option_chain(
            facts["ticker"],
            expiration=facts["expiration"] or None,
            option_side=facts["option_side"],
            limit=200,
        )
        if not result.available:
            return []
        contracts = list(result.contracts)
        target_days = (facts["days_left"] or 0) + MIN_LATER_EXPIRY_GAP_DAYS
        later = next(
            (item for item in result.expirations if (calendar_days_to_expiry(item) or -1) >= target_days),
            None,
        )
        if later and later != facts["expiration"]:
            later_result = yfinance_option_chain(
                facts["ticker"],
                expiration=later,
                option_side=facts["option_side"],
                limit=200,
            )
            if later_result.available:
                contracts.extend(later_result.contracts)
        return contracts
    except Exception:
        return []
