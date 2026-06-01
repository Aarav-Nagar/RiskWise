from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from api.services.market_data import (
    company_profile,
    earnings_calendar,
    market_quote,
    options_context,
    stock_news,
)


TICKER_RE = re.compile(r"(?<![A-Za-z])\$?([A-Z]{1,5})(?![A-Za-z])")
MONEY_RE = re.compile(r"\$?\s*([0-9]+(?:\.[0-9]+)?)")


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


async def build_ai_tool_context(
    *,
    message: str,
    mode: str,
    current_report: dict[str, Any] | None,
    user_profile: dict[str, Any] | None,
    recent_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run deterministic app tools before the model answers.

    This is deliberately server-side rather than model-autonomous for V1. It gives
    the LLM real context and makes the response auditable, while leaving room to
    switch to provider-native function calling later.
    """

    ticker = infer_ticker(message, current_report, recent_checks)
    calls: list[ToolCall] = []

    if asks_for_saved_trade(message, mode):
        saved = get_saved_trade(recent_checks)
        calls.append(ToolCall("get_saved_trade", {}, saved))

    if current_report:
        calls.append(ToolCall("get_current_report", {}, compact_tool_report(current_report)))
        calls.append(ToolCall("calculate_max_loss", {}, calculate_max_loss(current_report, user_profile)))
        calls.append(ToolCall("calculate_breakeven", {}, calculate_breakeven(current_report, message)))
    elif asks_for_risk_math(message):
        calls.append(ToolCall("calculate_max_loss", {}, calculate_max_loss({}, user_profile)))
        parsed_breakeven = calculate_breakeven({}, message)
        if parsed_breakeven.get("status") == "ok":
            calls.append(ToolCall("calculate_breakeven", {}, parsed_breakeven))

    if ticker and asks_for_market_context(message):
        quote = await market_quote(ticker)
        calls.append(ToolCall("get_quote", {"ticker": ticker}, quote.model_dump()))

    if ticker and asks_for_profile(message):
        profile = await company_profile(ticker)
        calls.append(ToolCall("get_company_profile", {"ticker": ticker}, profile.model_dump()))

    if ticker and asks_for_earnings(message):
        earnings = await earnings_calendar(ticker)
        calls.append(ToolCall("get_earnings", {"ticker": ticker}, earnings.model_dump()))

    if ticker and asks_for_news(message):
        news = await stock_news(ticker)
        calls.append(ToolCall("get_news", {"ticker": ticker}, news.model_dump()))

    if ticker and asks_for_options_data(message):
        options = await options_context(ticker)
        calls.append(ToolCall("get_options_context", {"ticker": ticker}, options.model_dump()))

    missing_data = collect_missing_data(calls, message)
    risk_flags = collect_risk_flags(calls, message, current_report)
    confidence = estimate_confidence(calls, missing_data, mode)

    return {
        "ticker": ticker,
        "tools_used": [{"name": call.name, "args": call.args} for call in calls],
        "tool_results": [{"name": call.name, "args": call.args, "result": call.result} for call in calls],
        "missing_data": missing_data,
        "risk_flags": risk_flags,
        "confidence": confidence,
    }


def infer_ticker(
    message: str,
    current_report: dict[str, Any] | None,
    recent_checks: list[dict[str, Any]],
) -> str | None:
    if current_report and current_report.get("ticker"):
        return str(current_report["ticker"]).upper()[:8]
    stop_words = {
        "IV",
        "ITM",
        "OTM",
        "ATM",
        "ETF",
        "AI",
        "US",
        "CEO",
        "CFO",
        "YOLO",
        "FOMO",
        "THE",
        "AND",
        "FOR",
        "PUT",
        "CALL",
    }
    for match in TICKER_RE.finditer(message):
        symbol = match.group(1).upper()
        if symbol not in stop_words:
            return symbol
    for item in recent_checks[:1]:
        report = item.get("report") if isinstance(item, dict) else None
        if isinstance(report, dict) and report.get("ticker"):
            return str(report["ticker"]).upper()[:8]
    return None


def asks_for_saved_trade(message: str, mode: str) -> bool:
    lower = message.lower()
    return mode in {"saved_trade_lookup", "trade_identity", "trade_review"} or any(
        phrase in lower for phrase in ["my trade", "latest check", "saved check", "what trade", "trade i did"]
    )


def asks_for_risk_math(message: str) -> bool:
    lower = message.lower()
    return any(term in lower for term in ["risk", "max loss", "breakeven", "break-even", "position size", "sizing", "%", "$"])


def asks_for_market_context(message: str) -> bool:
    lower = message.lower()
    return asks_for_options_data(message) or any(
        term in lower for term in ["price", "quote", "stock", "underlying", "market", "current", "move", "up", "down"]
    )


def asks_for_profile(message: str) -> bool:
    lower = message.lower()
    return any(term in lower for term in ["sector", "industry", "company", "profile", "beta", "market cap"])


def asks_for_earnings(message: str) -> bool:
    lower = message.lower()
    return any(term in lower for term in ["earnings", "event", "report date", "eps", "revenue"])


def asks_for_news(message: str) -> bool:
    lower = message.lower()
    return any(term in lower for term in ["news", "headline", "catalyst", "why is", "what happened"])


def asks_for_options_data(message: str) -> bool:
    lower = message.lower()
    return any(
        term in lower
        for term in [
            "option chain",
            "chain",
            "iv",
            "implied volatility",
            "greeks",
            "delta",
            "gamma",
            "theta",
            "vega",
            "premium",
            "bid",
            "ask",
            "expiration",
            "contract",
        ]
    )


def get_saved_trade(recent_checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not recent_checks:
        return {"status": "missing", "message": "No saved trade checks are available for this user."}
    latest = recent_checks[0]
    report = latest.get("report") if isinstance(latest, dict) else latest
    return {
        "status": "ok",
        "saved_check_id": latest.get("id") if isinstance(latest, dict) else None,
        "report": compact_tool_report(report or {}),
        "createdAt": latest.get("createdAt") if isinstance(latest, dict) else None,
    }


def compact_tool_report(report: dict[str, Any]) -> dict[str, Any]:
    risk_math = report.get("riskMath") or report.get("risk_math") or {}
    return {
        "ticker": report.get("ticker"),
        "tradeType": report.get("tradeType") or report.get("trade_type"),
        "strike": report.get("strike"),
        "expiration": report.get("expiration"),
        "amountAtRisk": report.get("amountAtRisk") or report.get("amount_at_risk"),
        "setupScore": report.get("setupScore") or report.get("setup_score"),
        "riskScore": report.get("riskScore") or report.get("risk_score"),
        "weakestLink": report.get("weakestLink") or report.get("weakest_link"),
        "riskPosture": report.get("riskPosture") or report.get("risk_posture"),
        "riskMath": {
            "max_loss": risk_math.get("max_loss"),
            "required_move_to_breakeven_pct": risk_math.get("required_move_to_breakeven_pct"),
            "trading_days_left": risk_math.get("trading_days_left"),
        },
    }


def calculate_max_loss(report: dict[str, Any], user_profile: dict[str, Any] | None) -> dict[str, Any]:
    risk_math = report.get("riskMath") or report.get("risk_math") or {}
    amount = report.get("amountAtRisk") or report.get("amount_at_risk") or risk_math.get("max_loss")
    account = (user_profile or {}).get("accountSize") or report.get("accountSize")
    try:
        max_loss = float(amount)
    except (TypeError, ValueError):
        max_loss = None
    try:
        account_size = float(account)
    except (TypeError, ValueError):
        account_size = None
    pct = round(max_loss / account_size * 100, 2) if max_loss is not None and account_size else None
    return {
        "status": "ok" if max_loss is not None else "missing_amount",
        "max_loss": max_loss,
        "account_size": account_size,
        "account_risk_pct": pct,
        "formula": "For a long option, max loss is the premium or amount at risk.",
    }


def calculate_breakeven(report: dict[str, Any], message: str) -> dict[str, Any]:
    trade_type = str(report.get("tradeType") or report.get("trade_type") or message).lower()
    strike = number_from_value(report.get("strike"))
    premium = number_from_value(report.get("premium") or report.get("debit"))
    if strike is None:
        strike = parse_labeled_number(message, ["strike", "strk"])
    if premium is None:
        premium = parse_labeled_number(message, ["premium", "debit", "paid", "cost"])
    if strike is None or premium is None:
        return {
            "status": "missing_fields",
            "missing": [field for field, value in [("strike", strike), ("premium", premium)] if value is None],
            "formula": "Long call breakeven = strike + premium. Long put breakeven = strike - premium.",
        }
    if "put" in trade_type and "call" not in trade_type:
        breakeven = strike - premium
        formula = "strike - premium"
    else:
        breakeven = strike + premium
        formula = "strike + premium"
    return {
        "status": "ok",
        "breakeven": round(breakeven, 2),
        "strike": strike,
        "premium": premium,
        "formula": formula,
    }


def collect_missing_data(calls: list[ToolCall], message: str) -> list[str]:
    missing: list[str] = []
    for call in calls:
        result = call.result
        status = str(result.get("status") or "")
        if status.startswith("requires") or status.startswith("missing") or status in {"needs_provider_key", "partial_market_data", "options_reference_ready", "options_provider_configured"}:
            if call.name == "get_options_context":
                pending = result.get("fields_pending") or []
                if pending:
                    missing.extend(str(item).replace("_", " ") for item in pending)
                else:
                    missing.extend(["live option chain", "implied volatility", "Greeks", "bid/ask", "contract premium"])
            elif call.name == "calculate_breakeven":
                missing.extend(str(item) for item in result.get("missing", []))
            elif call.name == "get_saved_trade":
                missing.append("saved trade check")
    if asks_for_options_data(message) and not any(call.name == "get_options_context" for call in calls):
        missing.append("ticker")
    return sorted(set(item for item in missing if item))


def collect_risk_flags(calls: list[ToolCall], message: str, current_report: dict[str, Any] | None) -> list[str]:
    flags: list[str] = []
    lower = message.lower()
    if any(term in lower for term in ["earnings", "iv crush", "event"]):
        flags.append("event_volatility")
    if any(term in lower for term in ["0dte", "same day", "weekly", "under 7 days", "short dated"]):
        flags.append("short_expiration")
    if any(term in lower for term in ["all in", "yolo", "full port", "double"]):
        flags.append("oversizing_language")
    for call in calls:
        if call.name == "calculate_max_loss":
            pct = call.result.get("account_risk_pct")
            if isinstance(pct, (int, float)) and pct >= 10:
                flags.append("large_account_risk")
    if current_report:
        weakest = str(current_report.get("weakestLink") or current_report.get("weakest_link") or "").lower()
        if weakest:
            flags.append(f"weakest_link:{weakest.replace(' ', '_')}")
    return sorted(set(flags))


def estimate_confidence(calls: list[ToolCall], missing_data: list[str], mode: str) -> float:
    if mode in {"greeting", "smalltalk"}:
        return 0.8
    confidence = 0.72
    if any(call.name in {"get_current_report", "get_saved_trade"} and call.result.get("status") != "missing" for call in calls):
        confidence += 0.1
    if any(call.name == "get_quote" and call.result.get("status") == "ok" for call in calls):
        confidence += 0.06
    if missing_data:
        confidence -= min(0.3, 0.06 * len(missing_data))
    return max(0.25, min(0.92, round(confidence, 2)))


def parse_labeled_number(text: str, labels: list[str]) -> float | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*(?:is|=|:)?\s*\$?\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if match:
            return number_from_value(match.group(1))
    numbers = [number_from_value(match.group(1)) for match in MONEY_RE.finditer(text)]
    numbers = [value for value in numbers if value is not None]
    if labels[0] in {"strike", "strk"} and numbers:
        return max(numbers)
    if labels[0] in {"premium", "debit", "paid", "cost"} and len(numbers) >= 2:
        return min(numbers)
    return None


def number_from_value(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
