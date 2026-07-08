from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


NOT_CONFIRMED = "not confirmed"


def build_saved_check_export(
    saved_check: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
    *,
    generated_at: str | None = None,
) -> dict[str, str]:
    """Serialize an existing saved Check for review in an external AI tool."""
    report = saved_check.get("report") or {}
    profile = user_profile or {}
    generated = generated_at or datetime.now(timezone.utc).isoformat()

    prediction = _mapping(report, "prediction", "prediction_context")
    contract = _mapping(report, "contractSnapshot", "contract_snapshot")
    risk_math = _mapping(report, "riskMath", "risk_math")
    contract_label = _mapping(report, "contractLabel", "contract_label")
    agreement = _mapping(report, "agreementMap", "agreement_map")
    decision = _mapping(report, "decisionSnapshot", "decision_snapshot")

    ticker = str(_first(report, "ticker") or NOT_CONFIRMED).upper()
    side = str(
        _coalesce(
            _first(contract, "option_side", "optionSide"),
            _first(decision, "option_side", "optionSide"),
            _option_side_from_trade_type(_first(report, "tradeType", "trade_type")),
            NOT_CONFIRMED,
        )
    ).lower()
    strike = _coalesce(_first(contract, "strike"), _first(report, "strike"))
    expiration = _coalesce(_first(contract, "expiration"), _first(report, "expiration"))
    premium = _coalesce(
        _first(contract, "premium"),
        _first(decision, "premium"),
        _first(contract_label, "premium"),
    )
    contracts = _coalesce(
        _first(contract, "contracts"),
        _first(decision, "contracts"),
        _first(risk_math, "contracts"),
    )
    total_premium = _coalesce(
        _first(risk_math, "notional_premium", "notionalPremium"),
        _first(risk_math, "max_loss", "maxLoss"),
    )
    dte = _coalesce(
        _first(risk_math, "calendar_days_left", "calendarDaysLeft", "dte"),
        _first(contract_label, "days_left", "daysLeft"),
    )
    bid = _first(contract, "bid")
    ask = _first(contract, "ask")
    spread = _coalesce(
        _first(contract, "spread_pct", "spreadPct"),
        _first(contract_label, "spread_pct", "spreadPct"),
    )
    implied_volatility = _first(contract, "implied_volatility", "impliedVolatility")
    volume = _first(contract, "volume", "contract_volume", "contractVolume")
    open_interest = _first(contract, "open_interest", "openInterest")
    underlying = _first(contract, "underlying_price", "underlyingPrice")

    agree_points = _string_list(_first(agreement, "agree"))
    disagree_points = _string_list(_first(agreement, "disagree"))
    reviewed_points = len(agree_points) + len(disagree_points)
    stored_verdict = _first(agreement, "verdict")
    verdict = str(stored_verdict) if stored_verdict else ("Disagree" if disagree_points else "Agree" if agree_points else "Not confirmed")
    disagreement_summary = (
        f"{len(disagree_points)} of {reviewed_points} disagreement points"
        if reviewed_points
        else "disagreement points not available"
    )
    disagreement_lines = (
        "\n".join(f"- {point}" for point in disagree_points)
        if disagree_points
        else "- Disagreement details: not confirmed"
    )

    direction = _coalesce(
        _first(prediction, "direction"),
        _first(report, "predictionDirection", "prediction_direction"),
    )
    target_price = _coalesce(
        _first(prediction, "target_price", "targetPrice"),
        _first(report, "targetPrice", "target_price"),
    )
    target_date = _coalesce(
        _first(prediction, "target_date", "targetDate"),
        _first(report, "targetDate", "target_date"),
    )
    reason = _coalesce(
        _first(prediction, "reason", "thesis"),
        _first(report, "predictionReason", "prediction_reason"),
    )
    invalidation = _coalesce(
        _first(prediction, "invalidation_price", "invalidationPrice"),
        _first(report, "invalidationPrice", "invalidation_price"),
    )

    account_size = _coalesce(
        _first(profile, "accountSize", "account_size"),
        _first(report, "accountSize", "account_size"),
    )
    risk_limit = _coalesce(
        _first(profile, "riskBudgetPercent", "risk_budget_percent"),
        _first(decision, "profile_risk_limit", "profileRiskLimit"),
    )
    experience = _first(profile, "experienceLevel", "experience_level")
    risk_style = _first(profile, "riskStyle", "risk_style")

    contract_name = f"{ticker} {_title_value(side)}"
    header = " ".join(
        part
        for part in [ticker, side.upper() if side != NOT_CONFIRMED else NOT_CONFIRMED, _money(strike), str(expiration or NOT_CONFIRMED)]
        if part
    )
    markdown = f"""# RiskWise Check Export — {header}
Generated {generated} from a saved Check in RiskWise.

## My Prediction
- Direction: {_plain(direction)}
- Target price: {_money(target_price)} (target date: {_plain(target_date)})
- Reason: {_plain(reason)}
- Invalidation price: {_money(invalidation)} — the price that would prove this prediction wrong

## The Contract I'm Considering
- {contract_name}, strike {_money(strike)}, expiration {_plain(expiration)} ({_plain(dte)} DTE)
- Premium: {_money(premium)} x {_plain(contracts)} contracts = {_money(total_premium)} total
- Underlying price at time of check: {_money(underlying)}
- Bid/Ask: {_money(bid)} / {_money(ask)} (spread: {_percent(spread)})
- IV: {_percent(implied_volatility)}
- Volume / OI: {_plain(volume)} / {_plain(open_interest)}

## What RiskWise Found
Verdict: {verdict} — {disagreement_summary}

{disagreement_lines}

Account context: account size {_money(account_size)}, stated max risk per trade {_percent(risk_limit)}, experience level {_plain(experience)}, stated risk style {_plain(risk_style)}.

## Questions I'd like a second opinion on
1. Given my stated reason, does this expiration realistically give the thesis enough room to play out, independent of the math above?
2. Is there a structure (different strike, spread, etc.) that would express this same prediction with a better risk/reward than what I have here?
3. What's the single biggest blind spot in my reasoning that I'm not seeing?

---
*This export is for educational discussion purposes. RiskWise is not a broker or financial advisor and does not execute trades.*
"""
    filename_parts = ["riskwise", _slug(ticker), _slug(side), _slug(strike), _slug(expiration)]
    filename = "-".join(part for part in filename_parts if part) + ".md"
    return {
        "savedCheckId": str(saved_check.get("id") or ""),
        "generatedAt": generated,
        "filename": filename,
        "markdown": markdown,
    }


def _mapping(source: dict[str, Any], *keys: str) -> dict[str, Any]:
    value = _first(source, *keys)
    return value if isinstance(value, dict) else {}


def _first(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            return value
    return None


def _coalesce(*values: Any) -> Any:
    return next((value for value in values if value is not None and value != ""), None)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _plain(value: Any) -> str:
    if value is None or value == "":
        return NOT_CONFIRMED
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _money(value: Any) -> str:
    if value is None or value == "":
        return NOT_CONFIRMED
    if isinstance(value, (int, float)):
        return f"${value:,.2f}".rstrip("0").rstrip(".")
    clean = str(value).strip()
    return clean if clean.startswith("$") else f"${clean}"


def _percent(value: Any) -> str:
    if value is None or value == "":
        return NOT_CONFIRMED
    if isinstance(value, float):
        return f"{value:g}%"
    clean = str(value).strip()
    return clean if clean.endswith("%") else f"{clean}%"


def _title_value(value: str) -> str:
    return value.title() if value != NOT_CONFIRMED else NOT_CONFIRMED


def _option_side_from_trade_type(value: Any) -> str | None:
    clean = str(value or "").lower()
    if "put" in clean:
        return "put"
    if "call" in clean:
        return "call"
    return None


def _slug(value: Any) -> str:
    if value is None or value == "":
        return ""
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
