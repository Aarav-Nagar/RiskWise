from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .market_data import (
    company_profile,
    earnings_calendar,
    market_search,
    market_quote,
    options_chain,
    options_contract_context,
    options_context,
    stock_news,
)


TICKER_RE = re.compile(r"(?<![A-Za-z])\$?([A-Z]{2,5})(?![A-Za-z])")
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
    attachment_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run deterministic app tools before the model answers.

    This is deliberately server-side rather than model-autonomous for V1. It gives
    the LLM real context and makes the response auditable, while leaving room to
    switch to provider-native function calling later.
    """

    attachment_fields = (attachment_contract or {}).get("fields") or {}
    attachment_report = report_from_attachment_contract(attachment_contract)
    report_for_tools = current_report or attachment_report
    ticker = infer_ticker(message, current_report, recent_checks) or clean_symbol(attachment_fields.get("ticker"))
    contract_query = infer_contract_query(message, current_report, recent_checks, attachment_fields)
    calls: list[ToolCall] = []

    if attachment_contract:
        calls.append(ToolCall("parse_uploaded_contract", {}, attachment_contract))

    if asks_for_saved_trade(message, mode):
        saved = get_saved_trade(recent_checks)
        if saved.get("status") == "ok":
            calls.append(ToolCall("get_saved_trade", {}, saved))

    profile_memory = retrieve_profile_memory(user_profile, mode, message)
    if profile_memory.get("status") == "ok":
        calls.append(ToolCall("retrieve_profile_memory", {}, profile_memory))

    relevant = retrieve_saved_checks(recent_checks, message, current_report)
    if relevant.get("status") == "ok":
        calls.append(ToolCall("retrieve_saved_checks", {}, relevant))

    if report_for_tools:
        calls.append(ToolCall("retrieve_selected_trade", {}, retrieve_selected_trade(report_for_tools, source="selected_check" if current_report else "uploaded_contract")))
        if current_report:
            calls.append(ToolCall("get_current_report", {}, compact_tool_report(current_report)))
        calls.append(ToolCall("calculate_max_loss", {}, calculate_max_loss(report_for_tools, user_profile)))
        calls.append(ToolCall("calculate_breakeven", {}, calculate_breakeven(report_for_tools, message)))
        calls.append(ToolCall("calculate_dte", {}, calculate_dte(report_for_tools)))
        calls.append(ToolCall("calculate_liquidity_score", {}, calculate_liquidity_score(report_for_tools)))
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

    if ticker and (report_for_tools or mode in {"trade_review", "trade_identity", "saved_trade_lookup", "attachment_needs_details"} or asks_for_options_data(message)):
        options = await options_context(ticker)
        calls.append(ToolCall("get_options_context", {"ticker": ticker}, options.model_dump()))
        if asks_for_option_chain(message, mode, report_for_tools):
            chain = await options_chain(ticker, contract_query.get("expiration"))
            calls.append(
                ToolCall(
                    "get_option_chain",
                    {"ticker": ticker, "expiration": contract_query.get("expiration")},
                    chain.model_dump(),
                )
            )
        if asks_for_contract_context(message, mode, report_for_tools, contract_query):
            contract = await options_contract_context(
                ticker,
                expiration=contract_query.get("expiration"),
                strike=contract_query.get("strike"),
                option_side=contract_query.get("option_side"),
            )
            calls.append(
                ToolCall(
                    "get_option_contract",
                    {
                        "ticker": ticker,
                        "expiration": contract_query.get("expiration"),
                        "strike": contract_query.get("strike"),
                        "option_side": contract_query.get("option_side"),
                    },
                    contract.model_dump(),
                )
            )

    if not ticker and asks_for_symbol_lookup(message):
        query = symbol_lookup_query(message)
        if query:
            search = await market_search(query)
            calls.append(ToolCall("search_ticker", {"query": query}, search.model_dump()))

    missing_data = collect_missing_data(calls, message)
    detector = detect_missing_data(report_for_tools, attachment_contract, calls, message)
    calls.append(ToolCall("detect_missing_data", {}, detector))
    missing_data = sorted(set([*missing_data, *detector.get("missing_data", [])]))
    risk_flags = collect_risk_flags(calls, message, report_for_tools)
    confidence = estimate_confidence(calls, missing_data, mode)
    context_packet = build_coach_context_packet(
        message=message,
        mode=mode,
        ticker=ticker,
        calls=calls,
        missing_data=missing_data,
        risk_flags=risk_flags,
        confidence=confidence,
        current_report=current_report,
        recent_checks=recent_checks,
        user_profile=user_profile,
        attachment_contract=attachment_contract,
    )

    return {
        "ticker": ticker,
        "tools_used": [{"name": call.name, "args": call.args} for call in calls],
        "tool_results": [{"name": call.name, "args": call.args, "result": call.result} for call in calls],
        "missing_data": missing_data,
        "risk_flags": risk_flags,
        "confidence": confidence,
        "coach_context": context_packet,
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


def clean_symbol(value: Any) -> str | None:
    symbol = re.sub(r"[^A-Za-z.]", "", str(value or "")).upper()
    if not symbol or symbol in {"CALL", "PUT", "EXP", "IV", "MID"}:
        return None
    return symbol[:8]


def report_from_attachment_contract(attachment_contract: dict[str, Any] | None) -> dict[str, Any] | None:
    fields = (attachment_contract or {}).get("fields") or {}
    if not fields:
        return None
    premium = number_from_value(fields.get("premium"))
    contracts = number_from_value(fields.get("contracts"))
    amount_at_risk = premium * contracts * 100 if premium is not None and contracts is not None else None
    side = str(fields.get("optionSide") or "").lower()
    trade_type = fields.get("tradeType") or ("Put Option (Long)" if side == "put" else "Call Option (Long)" if side == "call" else "Option")
    return {
        "ticker": clean_symbol(fields.get("ticker")),
        "tradeType": trade_type,
        "optionSide": side or None,
        "strike": fields.get("strike"),
        "expiration": fields.get("expiration"),
        "premium": fields.get("premium"),
        "contracts": fields.get("contracts"),
        "amountAtRisk": amount_at_risk,
        "contractSnapshot": {
            "bid": fields.get("bid"),
            "ask": fields.get("ask"),
            "impliedVolatility": fields.get("impliedVolatility"),
            "openInterest": fields.get("openInterest"),
            "contractVolume": fields.get("contractVolume"),
            "underlyingPrice": fields.get("underlyingPrice"),
        },
        "dataQuality": {
            "label": "uploaded_contract",
            "fields_pending": [
                *((attachment_contract or {}).get("missing_fields") or []),
                *((attachment_contract or {}).get("missing_live_fields") or []),
            ],
        },
    }


def infer_contract_query(
    message: str,
    current_report: dict[str, Any] | None,
    recent_checks: list[dict[str, Any]],
    attachment_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source: dict[str, Any] = {}
    if current_report:
        source = current_report
    elif attachment_fields:
        source = attachment_fields
    elif recent_checks:
        latest = recent_checks[0]
        maybe_report = latest.get("report") if isinstance(latest, dict) else None
        if isinstance(maybe_report, dict):
            source = maybe_report

    trade_type = str(
        source.get("tradeType")
        or source.get("trade_type")
        or source.get("optionSide")
        or source.get("option_side")
        or message
    ).lower()
    option_side = "put" if "put" in trade_type and "call" not in trade_type else "call"
    return {
        "expiration": source.get("expiration") or source.get("expiration_date") or parse_iso_date(message),
        "strike": number_from_value(source.get("strike")) or parse_labeled_number(message, ["strike", "strk"]),
        "premium": number_from_value(source.get("premium") or source.get("debit")) or parse_labeled_number(message, ["premium", "debit", "paid", "cost"]),
        "option_side": option_side,
    }


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
    return any(term in lower for term in ["news", "headline", "catalyst", "what happened"])


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


def asks_for_option_chain(message: str, mode: str, current_report: dict[str, Any] | None) -> bool:
    lower = message.lower()
    return bool(current_report) or mode in {"trade_review", "trade_identity", "saved_trade_lookup"} or any(
        term in lower
        for term in [
            "option chain",
            "chain",
            "expiration",
            "expirations",
            "contracts",
            "strikes",
            "available",
            "contract",
        ]
    )


def asks_for_contract_context(
    message: str,
    mode: str,
    current_report: dict[str, Any] | None,
    contract_query: dict[str, Any],
) -> bool:
    lower = message.lower()
    return bool(current_report) or mode in {"trade_review", "trade_identity", "saved_trade_lookup"} or bool(
        contract_query.get("strike") or contract_query.get("expiration")
    ) or any(term in lower for term in ["my contract", "this contract", "breakeven", "premium", "strike", "call", "put"])


def asks_for_symbol_lookup(message: str) -> bool:
    lower = message.lower()
    return any(term in lower for term in ["find ticker", "what ticker", "symbol for", "company ticker", "search"])


def symbol_lookup_query(message: str) -> str:
    lower = message.lower()
    for marker in ["symbol for", "ticker for", "find ticker", "search"]:
        if marker in lower:
            return message[lower.index(marker) + len(marker) :].strip(" :?.")[:40]
    return message.strip()[:40]


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


def retrieve_selected_trade(report: dict[str, Any], source: str = "selected_check") -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {"status": "missing", "message": "No selected trade report is available."}
    compact = compact_tool_report(report)
    risk_math = compact.get("riskMath") or {}
    snapshot = compact.get("contractSnapshot") or {}
    data_quality = compact.get("dataQuality") or {}
    missing = detect_missing_data(report, None, [], "").get("missing_data", [])
    pressure_points = []
    if risk_math.get("max_loss") is not None:
        pressure_points.append(f"max loss {risk_math['max_loss']}")
    if risk_math.get("required_move_to_breakeven_pct") is not None:
        pressure_points.append(f"required move {risk_math['required_move_to_breakeven_pct']}%")
    if risk_math.get("calendar_days_left") is not None:
        pressure_points.append(f"{risk_math['calendar_days_left']} DTE")
    if compact.get("weakestLink"):
        pressure_points.append(f"weakest link {compact['weakestLink']}")
    return {
        "status": "ok",
        "source": source,
        "title": report_title(report),
        "report": compact,
        "pressure_points": pressure_points,
        "missing_data": missing,
        "data_quality": {
            "label": data_quality.get("label") or data_quality.get("source") or "unknown",
            "fields_pending": data_quality.get("fields_pending") or [],
            "has_contract_snapshot": bool(snapshot),
        },
        "message": "Selected-trade retriever should be treated as the primary context for trade questions.",
    }


def retrieve_saved_checks(
    recent_checks: list[dict[str, Any]],
    message: str,
    current_report: dict[str, Any] | None,
) -> dict[str, Any]:
    if not recent_checks:
        return {"status": "missing", "message": "No saved checks available."}
    rows = []
    for item in recent_checks[:5]:
        report = item.get("report") if isinstance(item, dict) else item
        if not isinstance(report, dict):
            continue
        rows.append(
            {
                "id": item.get("id") if isinstance(item, dict) else report.get("id"),
                "title": report_title(report),
                "ticker": report.get("ticker"),
                "strategy": report.get("tradeType") or report.get("trade_type"),
                "weakest_link": report.get("weakestLink") or report.get("weakest_link"),
                "risk_posture": report.get("riskPosture") or report.get("risk_posture"),
                "relevance_score": item.get("aiRelevanceScore", 0) if isinstance(item, dict) else 0,
                "relevance_reason": item.get("aiRelevanceReason", "recent saved check") if isinstance(item, dict) else "recent saved check",
            }
        )
    if not rows:
        return {"status": "missing", "message": "Saved checks exist but none were readable."}
    selected = compact_tool_report(current_report) if current_report else None
    return {
        "status": "ok",
        "selected_report": selected,
        "matches": rows,
        "message": "Relevant saved checks ranked by ticker, strategy, topic, and recency.",
    }


def retrieve_profile_memory(user_profile: dict[str, Any] | None, mode: str, message: str) -> dict[str, Any]:
    profile = user_profile or {}
    if not profile:
        return {"status": "missing", "message": "No profile memory available."}
    ai_memory = profile.get("aiMemory") or {}
    risk_rules = profile.get("riskRules") or {}
    coach_style = profile.get("coachStyle") or {}
    preferences = profile.get("appPreferences") or {}
    style = (
        ai_memory.get("preferredExplanation")
        or ai_memory.get("preferredExplanationStyle")
        or coach_style.get("explanationStyle")
        or profile.get("preferredExplanations")
        or "Step-by-step"
    )
    question_style = coach_style.get("questionStyle") or "Ask when needed"
    strictness = coach_style.get("riskStrictness") or risk_rules.get("riskStrictness") or "Balanced"
    common_mistakes = (
        ai_memory.get("commonMistakes")
        or profile.get("struggles")
        or profile.get("commonMistakes")
        or []
    )
    sectors = ai_memory.get("sectorsToFocus") or profile.get("sectors") or []
    return {
        "status": "ok",
        "experience_level": profile.get("experienceLevel") or ai_memory.get("experience") or "Not specified",
        "risk_style": profile.get("riskStyle") or ai_memory.get("riskStyle") or "Balanced",
        "preferred_explanation": style,
        "question_style": question_style,
        "risk_strictness": strictness,
        "risk_rules": {
            "max_risk_per_trade_percent": risk_rules.get("maxRiskPerTradePercent") or risk_rules.get("maxRiskPercent") or profile.get("riskBudgetPercent"),
            "max_trades_per_week": risk_rules.get("maxTradesPerWeek"),
            "avoid_earnings_trades": risk_rules.get("avoidEarningsTrades"),
            "warn_under_7_dte": risk_rules.get("warnUnder7Dte"),
        },
        "sectors_to_focus": sectors[:6] if isinstance(sectors, list) else sectors,
        "common_mistakes": common_mistakes[:6] if isinstance(common_mistakes, list) else common_mistakes,
        "default_ai_mode": preferences.get("defaultMode"),
        "message": "Profile memory should shape tone, strictness, and follow-up questions.",
    }


def compact_tool_report(report: dict[str, Any]) -> dict[str, Any]:
    risk_math = report.get("riskMath") or report.get("risk_math") or {}
    snapshot = report.get("contractSnapshot") or report.get("contract_snapshot") or {}
    data_quality = report.get("dataQuality") or report.get("data_quality") or {}
    return {
        "ticker": report.get("ticker"),
        "tradeType": report.get("tradeType") or report.get("trade_type"),
        "optionSide": report.get("optionSide") or report.get("option_side"),
        "strike": report.get("strike"),
        "expiration": report.get("expiration"),
        "premium": report.get("premium") or report.get("debit"),
        "contracts": report.get("contracts"),
        "amountAtRisk": report.get("amountAtRisk") or report.get("amount_at_risk"),
        "setupScore": report.get("setupScore") or report.get("setup_score"),
        "riskScore": report.get("riskScore") or report.get("risk_score"),
        "weakestLink": report.get("weakestLink") or report.get("weakest_link"),
        "riskPosture": report.get("riskPosture") or report.get("risk_posture"),
        "riskMath": {
            "max_loss": risk_math.get("max_loss"),
            "breakeven": risk_math.get("breakeven") or risk_math.get("breakeven_price"),
            "required_move_to_breakeven_pct": risk_math.get("required_move_to_breakeven_pct"),
            "trading_days_left": risk_math.get("trading_days_left"),
            "calendar_days_left": risk_math.get("calendar_days_left"),
            "account_risk_pct": risk_math.get("account_risk_pct") or risk_math.get("risk_percent_of_account"),
        },
        "contractSnapshot": {
            "bid": snapshot.get("bid") or report.get("bid"),
            "ask": snapshot.get("ask") or report.get("ask"),
            "lastPrice": snapshot.get("lastPrice") or snapshot.get("last_price") or report.get("lastPrice"),
            "mark": snapshot.get("mark") or report.get("mark"),
            "impliedVolatility": snapshot.get("impliedVolatility") or snapshot.get("iv") or report.get("impliedVolatility") or report.get("implied_volatility"),
            "delta": snapshot.get("delta") or report.get("delta"),
            "gamma": snapshot.get("gamma") or report.get("gamma"),
            "theta": snapshot.get("theta") or report.get("theta"),
            "vega": snapshot.get("vega") or report.get("vega"),
            "openInterest": snapshot.get("openInterest") or report.get("openInterest") or report.get("open_interest"),
            "contractVolume": snapshot.get("contractVolume") or snapshot.get("volume") or report.get("contractVolume") or report.get("contract_volume"),
            "underlyingPrice": snapshot.get("underlyingPrice") or report.get("underlyingPrice") or report.get("underlying_price"),
        },
        "dataQuality": {
            "label": data_quality.get("label") or data_quality.get("source") or data_quality.get("status"),
            "fields_pending": data_quality.get("fields_pending") or data_quality.get("missing") or [],
            "fields_ready": data_quality.get("fields_ready") or [],
        },
    }


def calculate_max_loss(report: dict[str, Any], user_profile: dict[str, Any] | None) -> dict[str, Any]:
    risk_math = report.get("riskMath") or report.get("risk_math") or {}
    amount = report.get("amountAtRisk") or report.get("amount_at_risk") or risk_math.get("max_loss")
    premium = number_from_value(report.get("premium") or report.get("debit"))
    contracts = number_from_value(report.get("contracts"))
    trade_type = str(report.get("tradeType") or report.get("trade_type") or report.get("optionSide") or "").lower()
    account = (user_profile or {}).get("accountSize") or report.get("accountSize")
    try:
        max_loss = float(amount)
    except (TypeError, ValueError):
        max_loss = None
    formula = "Max loss comes from the report amount-at-risk."
    if max_loss is None and premium is not None and contracts is not None and ("call" in trade_type or "put" in trade_type or not trade_type):
        max_loss = premium * contracts * 100
        formula = "For a long option, max loss = premium x contracts x 100."
    try:
        account_size = float(account)
    except (TypeError, ValueError):
        account_size = None
    pct = round(max_loss / account_size * 100, 2) if max_loss is not None and account_size else None
    risk_limit = number_from_value(((user_profile or {}).get("riskRules") or {}).get("maxRiskPerTradePercent")) or number_from_value((user_profile or {}).get("riskBudgetPercent"))
    budget_status = "unknown"
    if pct is not None and risk_limit is not None:
        budget_status = "within_profile_limit" if pct <= risk_limit else "above_profile_limit"
    return {
        "status": "ok" if max_loss is not None else "missing_amount",
        "max_loss": max_loss,
        "premium": premium,
        "contracts": contracts,
        "account_size": account_size,
        "account_risk_pct": pct,
        "profile_risk_limit_pct": risk_limit,
        "budget_status": budget_status,
        "formula": formula,
    }


def calculate_breakeven(report: dict[str, Any], message: str) -> dict[str, Any]:
    risk_math = report.get("riskMath") or report.get("risk_math") or {}
    existing = number_from_value(risk_math.get("breakeven") or risk_math.get("breakeven_price"))
    if existing is not None:
        return {
            "status": "ok",
            "breakeven": round(existing, 2),
            "formula": "backend risk math",
            "source": "report",
        }
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


def calculate_dte(report: dict[str, Any]) -> dict[str, Any]:
    risk_math = report.get("riskMath") or report.get("risk_math") or {}
    calendar_days = risk_math.get("calendar_days_left") or risk_math.get("days_to_expiration")
    trading_days = risk_math.get("trading_days_left")
    expiration = report.get("expiration") or report.get("expiration_date")
    if calendar_days is None and expiration:
        parsed = parse_expiration_date(expiration)
        if parsed:
            calendar_days = max(0, (parsed - date.today()).days)
            trading_days = trading_days if trading_days is not None else estimate_trading_days(calendar_days)
            return {
                "status": "ok",
                "expiration": expiration,
                "calendar_days_left": calendar_days,
                "trading_days_left": trading_days,
                "source": "expiration_date",
                "message": "DTE was calculated from the expiration date.",
            }
        return {
            "status": "expiration_known",
            "expiration": expiration,
            "calendar_days_left": None,
            "trading_days_left": trading_days,
            "message": "Expiration is known, but DTE was not precomputed.",
        }
    return {
        "status": "ok" if calendar_days is not None or trading_days is not None else "missing_dte",
        "expiration": expiration,
        "calendar_days_left": calendar_days,
        "trading_days_left": trading_days,
        "message": "DTE comes from backend risk math when available.",
    }


def calculate_liquidity_score(report: dict[str, Any]) -> dict[str, Any]:
    snapshot = report.get("contractSnapshot") or report.get("contract_snapshot") or {}
    data_quality = report.get("dataQuality") or report.get("data_quality") or {}
    bid = number_from_value(snapshot.get("bid") or report.get("bid"))
    ask = number_from_value(snapshot.get("ask") or report.get("ask"))
    volume = number_from_value(snapshot.get("volume") or snapshot.get("contractVolume") or report.get("contract_volume"))
    open_interest = number_from_value(snapshot.get("openInterest") or report.get("open_interest"))
    missing = []
    score = 75
    width = None
    width_pct = None
    if bid is None or ask is None:
        missing.append("bid/ask")
        score -= 18
    elif bid > ask:
        score -= 30
    elif ask > 0:
        width = round(ask - bid, 4)
        width_pct = round((ask - bid) / ask * 100, 2)
        if width_pct > 20:
            score -= 20
        elif width_pct > 10:
            score -= 10
    if volume is None:
        missing.append("volume")
        score -= 10
    elif volume < 100:
        score -= 12
    if open_interest is None:
        missing.append("open interest")
        score -= 10
    elif open_interest < 500:
        score -= 10
    quality_label = data_quality.get("label") or data_quality.get("source") or "unknown"
    final_score = max(5, min(95, round(score)))
    if missing:
        label = "unknown_until_confirmed"
    elif bid is not None and ask is not None and bid > ask:
        label = "invalid_bid_ask"
    elif final_score >= 75:
        label = "healthy"
    elif final_score >= 55:
        label = "thin_or_needs_caution"
    else:
        label = "weak"
    return {
        "status": "ok" if not missing else "partial_liquidity_data",
        "score": final_score,
        "label": label,
        "bid": bid,
        "ask": ask,
        "spread_width": width,
        "spread_width_pct": width_pct,
        "volume": volume,
        "open_interest": open_interest,
        "missing": missing,
        "data_quality": quality_label,
        "message": "Liquidity score is estimated from bid/ask width, volume, and open interest only when those fields are present.",
    }


def detect_missing_data(
    report: dict[str, Any] | None,
    attachment_contract: dict[str, Any] | None,
    calls: list[ToolCall],
    message: str,
) -> dict[str, Any]:
    missing: list[str] = []
    warnings: list[str] = []
    categories: dict[str, list[str]] = {
        "contract_identity": [],
        "risk_math": [],
        "live_market_data": [],
        "profile_memory": [],
        "saved_context": [],
    }
    source = report or report_from_attachment_contract(attachment_contract) or {}
    snapshot = source.get("contractSnapshot") or source.get("contract_snapshot") or {}
    required = [
        ("ticker", source.get("ticker")),
        ("call/put side", source.get("optionSide") or source.get("option_side") or source.get("tradeType") or source.get("trade_type")),
        ("strike", source.get("strike")),
        ("expiration", source.get("expiration") or source.get("expiration_date")),
        ("premium", source.get("premium") or source.get("debit") or source.get("amountAtRisk") or source.get("amount_at_risk")),
        ("contracts", source.get("contracts")),
    ]
    for label, value in required:
        if value in (None, "", [], {}):
            categories["contract_identity" if label in {"ticker", "call/put side", "strike", "expiration"} else "risk_math"].append(label)
    live_fields = [
        ("bid/ask", (snapshot.get("bid") or source.get("bid"), snapshot.get("ask") or source.get("ask"))),
        ("current option price", snapshot.get("lastPrice") or snapshot.get("mark") or source.get("lastPrice") or source.get("mark")),
        ("implied volatility", snapshot.get("impliedVolatility") or snapshot.get("iv") or source.get("impliedVolatility") or source.get("implied_volatility")),
        ("Greeks", snapshot.get("delta") or snapshot.get("theta") or snapshot.get("gamma") or snapshot.get("vega")),
        ("open interest", snapshot.get("openInterest") or source.get("openInterest") or source.get("open_interest")),
        ("volume", snapshot.get("contractVolume") or snapshot.get("volume") or source.get("contractVolume") or source.get("contract_volume")),
        ("earnings date", source.get("earningsDate") or source.get("earnings_date")),
    ]
    for label, value in live_fields:
        is_missing = value in (None, "", [], {})
        if isinstance(value, tuple):
            is_missing = any(part in (None, "", [], {}) for part in value)
        if is_missing:
            categories["live_market_data"].append(label)
    if not any(call.name == "retrieve_profile_memory" and call.result.get("status") == "ok" for call in calls):
        categories["profile_memory"].append("profile preferences")
    if not any(call.name == "retrieve_saved_checks" and call.result.get("status") == "ok" for call in calls):
        categories["saved_context"].append("saved checks")
    for values in categories.values():
        missing.extend(values)
    if categories["live_market_data"]:
        warnings.append("Do not state live IV, Greeks, bid/ask, volume, open interest, earnings date, or current option price unless provided.")
    if categories["contract_identity"] or categories["risk_math"]:
        warnings.append("Ask for missing contract fields before treating the trade review as complete.")
    if asks_for_options_data(message) and not any(call.name == "get_options_context" for call in calls):
        warnings.append("A ticker is needed before any options-data lookup can run.")
    return {
        "status": "partial" if missing else "complete",
        "missing_data": sorted(set(item for item in missing if item)),
        "categories": {key: sorted(set(value)) for key, value in categories.items() if value},
        "warnings": warnings,
        "message": "Missing-data detector controls what Coach may claim.",
    }


def build_coach_context_packet(
    *,
    message: str,
    mode: str,
    ticker: str | None,
    calls: list[ToolCall],
    missing_data: list[str],
    risk_flags: list[str],
    confidence: float,
    current_report: dict[str, Any] | None,
    recent_checks: list[dict[str, Any]],
    user_profile: dict[str, Any] | None,
    attachment_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    tool_names = [call.name for call in calls]
    selected = next((call.result for call in calls if call.name == "retrieve_selected_trade"), {})
    saved = next((call.result for call in calls if call.name == "retrieve_saved_checks"), {})
    profile = next((call.result for call in calls if call.name == "retrieve_profile_memory"), {})
    detector = next((call.result for call in calls if call.name == "detect_missing_data"), {})
    max_loss = next((call.result for call in calls if call.name == "calculate_max_loss"), {})
    breakeven = next((call.result for call in calls if call.name == "calculate_breakeven"), {})
    dte = next((call.result for call in calls if call.name == "calculate_dte"), {})
    liquidity = next((call.result for call in calls if call.name == "calculate_liquidity_score"), {})
    market_statuses = [
        {"tool": call.name, "status": call.result.get("status"), "provider": call.result.get("provider")}
        for call in calls
        if call.name in {"get_quote", "get_options_context", "get_option_chain", "get_option_contract", "get_earnings"}
    ]
    primary_source = "selected_check" if current_report else "uploaded_contract" if attachment_contract else "saved_checks" if recent_checks else "question_only"
    return {
        "status": "ready",
        "primary_source": primary_source,
        "intent": mode,
        "ticker": ticker,
        "availability": {
            "selected_check": bool(current_report),
            "saved_checks": len(recent_checks),
            "profile_preferences": bool(user_profile),
            "uploaded_contract": bool(attachment_contract),
            "market_data_status": "partial_or_missing" if missing_data else "sufficient_for_current_answer",
            "tool_count": len(calls),
        },
        "selected_trade": selected,
        "saved_checks": (saved.get("matches") or [])[:5],
        "profile_preferences": profile if profile.get("status") == "ok" else {},
        "fact_tools": {
            "max_loss": max_loss,
            "breakeven": breakeven,
            "dte": dte,
            "liquidity": liquidity,
        },
        "missing_data": missing_data,
        "missing_categories": detector.get("categories") or {},
        "guardrails": detector.get("warnings") or [],
        "risk_flags": risk_flags,
        "confidence": confidence,
        "tools_used": tool_names,
        "answer_guidance": context_answer_guidance(primary_source, missing_data, profile, selected, mode),
        "message": "Use this packet as the compact source of truth before drafting the Coach answer.",
    }


def context_answer_guidance(
    primary_source: str,
    missing_data: list[str],
    profile: dict[str, Any],
    selected: dict[str, Any],
    mode: str,
) -> list[str]:
    guidance = []
    if primary_source in {"selected_check", "uploaded_contract"}:
        guidance.append("Answer from the attached trade before teaching generic options concepts.")
    elif primary_source == "saved_checks":
        guidance.append("Use the latest relevant saved check and say it is saved context.")
    if missing_data:
        guidance.append("Name the missing fields and avoid live-data claims for them.")
    if selected.get("pressure_points"):
        guidance.append("Mention the selected trade pressure points: " + ", ".join(selected["pressure_points"][:3]) + ".")
    if profile.get("preferred_explanation"):
        guidance.append(f"Shape the answer for {profile.get('preferred_explanation')} explanations.")
    if profile.get("risk_strictness"):
        guidance.append(f"Use a {profile.get('risk_strictness')} risk lens.")
    if mode == "trade_review":
        guidance.append("Focus on what can break the trade, not whether to take it.")
    return guidance


def collect_missing_data(calls: list[ToolCall], message: str) -> list[str]:
    missing: list[str] = []
    for call in calls:
        result = call.result
        status = str(result.get("status") or "")
        if call.name == "parse_uploaded_contract":
            missing.extend(field_label(item) for item in result.get("missing_fields") or [])
            missing.extend(field_label(item) for item in result.get("missing_live_fields") or [])
            continue
        if (
            status.startswith("requires")
            or status.startswith("missing")
            or status
            in {
                "needs_provider_key",
                "partial_market_data",
                "options_reference_ready",
                "options_provider_configured",
                "delayed_options_enabled",
            }
        ):
            if call.name in {"get_options_context", "get_option_chain", "get_option_contract"}:
                pending = result.get("fields_pending") or []
                if pending:
                    missing.extend(field_label(item) for item in pending)
                elif call.name in {"get_option_chain", "get_option_contract"} and result.get("status") in {
                    "requires_options_provider",
                    "reference_chain_ready",
                    "reference_chain_empty",
                    "reference_contract_matched",
                    "partial_contract_context",
                }:
                    missing.extend(["live premium", "bid/ask", "implied volatility", "Greeks", "volume/open interest"])
                else:
                    missing.extend(["live option chain", "implied volatility", "Greeks", "bid/ask", "contract premium"])
            elif call.name == "calculate_breakeven":
                missing.extend(str(item) for item in result.get("missing", []))
            elif call.name == "calculate_liquidity_score":
                missing.extend(str(item) for item in result.get("missing", []))
            elif call.name == "calculate_dte" and result.get("status") == "missing_dte":
                missing.append("days to expiration")
            elif call.name == "get_saved_trade":
                missing.append("saved trade check")
    if asks_for_options_data(message) and not any(call.name == "get_options_context" for call in calls):
        missing.append("ticker")
    return sorted(set(item for item in missing if item))


def field_label(value: Any) -> str:
    text = str(value or "").strip()
    labels = {
        "optionSide": "call/put side",
        "impliedVolatility": "implied volatility",
        "openInterest": "open interest",
        "contractVolume": "contract volume",
        "underlyingPrice": "underlying price",
        "real_time_opra_snapshot": "real time OPRA snapshot",
        "provider_reported_greeks": "provider reported Greeks",
    }
    if text in labels:
        return labels[text]
    text = re.sub(r"(?<!^)([A-Z])", r" \1", text).replace("_", " ").replace("-", " ")
    return " ".join(text.split()).lower()


def parse_iso_date(text: str) -> str | None:
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    return match.group(1) if match else None


def parse_expiration_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def estimate_trading_days(calendar_days: int | float | None) -> int | None:
    if calendar_days is None:
        return None
    return max(0, round(float(calendar_days) * 5 / 7))


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


def report_title(report: dict[str, Any]) -> str:
    ticker = str(report.get("ticker") or "Trade").upper()
    trade_type = str(report.get("tradeType") or report.get("trade_type") or "check")
    strike = report.get("strike")
    expiration = report.get("expiration") or report.get("expiration_date")
    pieces = [ticker, trade_type]
    if strike not in (None, ""):
        pieces.append(f"${strike}")
    if expiration:
        pieces.append(str(expiration))
    return " ".join(pieces)
