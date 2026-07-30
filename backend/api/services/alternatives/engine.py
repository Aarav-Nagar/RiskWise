"""Deterministic alternatives engine.

Given an already-scored trade, generate structural alternatives (later
expiration, vertical-spread conversion, reduced size, and a "wait" baseline),
price each one with the existing scoring payoff math (long_option_metrics /
vertical_spread_metrics — never re-derived here), attach the expiry
probability profile from api.probability, and rank them with a transparent
profile-weighted fit score.

Honesty rules carried over from the rest of the backend:
- No premium is ever invented. Candidates that need a live/delayed premium the
  caller did not supply are returned with status "needs_live_premium" and no
  payoff metrics.
- Every division is guarded; a sub-score whose inputs are missing is dropped
  from the weighted sum instead of defaulting.
"""

from __future__ import annotations

import math
from typing import Any

from ...models import TradeCheckRequest
from ...probability import calendar_days_to_expiry, probability_profile, BASIS as PROBABILITY_BASIS
from ...scoring import long_option_metrics, vertical_spread_metrics

FIT_BASIS = "profile_weighted_subscores_v1"

# Base weights by stored profile riskStyle. Sub-scores that do not structurally
# apply to a candidate are removed and the remaining weights renormalized.
BASE_WEIGHTS: dict[str, dict[str, float]] = {
    "Conservative": {"risk_reduction": 0.45, "thesis_preservation": 0.15, "time_relief": 0.20, "cost_efficiency": 0.20},
    "Balanced": {"risk_reduction": 0.30, "thesis_preservation": 0.30, "time_relief": 0.20, "cost_efficiency": 0.20},
    "Aggressive": {"risk_reduction": 0.15, "thesis_preservation": 0.45, "time_relief": 0.20, "cost_efficiency": 0.20},
}
# When the original trade is already above the profile risk limit, this much
# weight moves from thesis preservation to risk reduction.
OVER_LIMIT_WEIGHT_SHIFT = 0.15
# Direction is kept but upside is capped when converting to a debit spread.
THESIS_PRESERVATION_SPREAD = 0.65
# A later expiration keeps the full directional thesis and adds time.
THESIS_PRESERVATION_LATER_EXPIRY = 1.0
MIN_LATER_EXPIRY_GAP_DAYS = 7
STRIKE_MATCH_TOLERANCE_PCT = 0.5


def build_alternatives(
    *,
    report: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
    market_contracts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    original = original_trade_facts(report)
    profile_context = profile_risk_context(user_profile, original)
    weights = fit_weights(profile_context["risk_style"], profile_context["over_profile_limit"])
    candidates: list[dict[str, Any]] = []

    if original["kind"] == "long_option":
        candidates.append(later_expiration_candidate(original, market_contracts or []))
        candidates.append(vertical_spread_candidate(original, market_contracts or []))
    reduced = reduced_size_candidate(original)
    if reduced:
        candidates.append(reduced)
    candidates.append(wait_candidate(original))

    for candidate in candidates:
        candidate["fit"] = score_candidate_fit(candidate, original, weights)
    candidates.sort(key=lambda item: (-(item["fit"]["score"] if item["fit"]["score"] is not None else -1), item["type"]))

    return {
        "status": "ok",
        "fit_basis": FIT_BASIS,
        "probability_basis": PROBABILITY_BASIS,
        "original": original_summary(original),
        "profile_context": profile_context,
        "weights": weights,
        "candidates": candidates,
        "message": (
            "Alternatives are structural risk comparisons priced from the same payoff math as the original check. "
            "They are educational rewrites of the same idea, not trade recommendations."
        ),
    }


def original_trade_facts(report: dict[str, Any]) -> dict[str, Any]:
    risk_math = dict_field(report, "riskMath", "risk_math")
    snapshot = dict_field(report, "contractSnapshot", "contract_snapshot")
    structure = snapshot.get("structure") if isinstance(snapshot.get("structure"), dict) else {}
    trade_type = str(report.get("tradeType") or report.get("trade_type") or "")
    side = str(
        report.get("optionSide")
        or report.get("option_side")
        or snapshot.get("option_side")
        or snapshot.get("optionSide")
        or ("put" if "put" in trade_type.lower() else "call")
    ).lower()
    side = side if side in {"call", "put"} else "call"
    expiration = str(report.get("expiration") or snapshot.get("expiration") or "")
    days_left = positive_number(risk_math.get("calendar_days_left")) or calendar_days_to_expiry(expiration)
    contracts = int(positive_number(snapshot.get("contracts") or report.get("contracts") or risk_math.get("contracts")) or 1)
    premium = positive_number(snapshot.get("premium") or report.get("premium") or risk_math.get("premium_per_contract"))
    max_loss = positive_number(risk_math.get("max_loss") or report.get("amountAtRisk") or report.get("amount_at_risk"))
    if max_loss is None and premium is not None:
        max_loss = round(premium * contracts * 100, 2)
    return {
        "ticker": str(report.get("ticker") or "").upper(),
        "trade_type": trade_type,
        "kind": str(structure.get("kind") or ("vertical_spread" if "spread" in trade_type.lower() else "long_option")),
        "option_side": side,
        "strike": positive_number(report.get("strike") or snapshot.get("strike")),
        "expiration": expiration,
        "days_left": days_left,
        "premium": premium,
        "contracts": contracts,
        "max_loss": max_loss,
        "breakeven": finite_number(risk_math.get("breakeven") or risk_math.get("breakeven_price")),
        "risk_percent_of_account": positive_number(risk_math.get("risk_percent_of_account") or risk_math.get("account_risk_pct")),
        "underlying_price": positive_number(
            snapshot.get("underlying_price") or snapshot.get("underlyingPrice") or report.get("underlyingPrice") or report.get("underlying_price")
        ),
        "iv": positive_number(
            snapshot.get("implied_volatility") or snapshot.get("impliedVolatility") or report.get("implied_volatility") or report.get("impliedVolatility")
        ),
        "timeframe": str(report.get("timeframe") or "1-2 Weeks"),
        "structure": structure,
    }


def original_summary(original: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": original["ticker"],
        "kind": original["kind"],
        "option_side": original["option_side"],
        "strike": original["strike"],
        "expiration": original["expiration"],
        "days_left": original["days_left"],
        "premium": original["premium"],
        "contracts": original["contracts"],
        "max_loss": original["max_loss"],
        "breakeven": original["breakeven"],
        "risk_percent_of_account": original["risk_percent_of_account"],
    }


def profile_risk_context(user_profile: dict[str, Any] | None, original: dict[str, Any]) -> dict[str, Any]:
    profile = user_profile or {}
    risk_style = str(profile.get("riskStyle") or "Balanced")
    if risk_style not in BASE_WEIGHTS:
        risk_style = "Balanced"
    risk_rules = profile.get("riskRules") or {}
    # Same field precedence as services/ai_tools.py calculate_max_loss.
    limit = positive_number(risk_rules.get("maxRiskPerTradePercent")) or positive_number(profile.get("riskBudgetPercent"))
    risk_pct = original.get("risk_percent_of_account")
    over_limit = bool(limit is not None and risk_pct is not None and risk_pct > limit)
    return {
        "risk_style": risk_style,
        "max_risk_per_trade_percent": limit,
        "original_risk_percent_of_account": risk_pct,
        "over_profile_limit": over_limit,
    }


def fit_weights(risk_style: str, over_profile_limit: bool) -> dict[str, float]:
    weights = dict(BASE_WEIGHTS.get(risk_style, BASE_WEIGHTS["Balanced"]))
    if over_profile_limit:
        shift = min(OVER_LIMIT_WEIGHT_SHIFT, max(0.0, weights["thesis_preservation"] - 0.05))
        weights["thesis_preservation"] = round(weights["thesis_preservation"] - shift, 4)
        weights["risk_reduction"] = round(weights["risk_reduction"] + shift, 4)
    return weights


def later_expiration_candidate(original: dict[str, Any], market_contracts: list[dict[str, Any]]) -> dict[str, Any]:
    row = find_later_expiration_row(original, market_contracts)
    base = {
        "type": "later_expiration",
        "label": "Same contract, later expiration",
        "thesis_note": "Keeps the full directional thesis and buys more time past the current expiry pressure.",
    }
    if not row:
        return {
            **base,
            "status": "needs_live_premium",
            "metrics": {},
            "probability": probability_not_available("missing_later_expiration_premium"),
            "data_quality": {
                "premium_source": "unavailable",
                "note": "No delayed chain row with the same side/strike and a later expiration was supplied, so no premium is invented.",
            },
        }
    premium = positive_number(row.get("mid") or row.get("last") or row.get("premium"))
    quantity = original["contracts"]
    leg = {
        "action": "buy",
        "type": original["option_side"],
        "strike": row.get("strike_price") or row.get("strike"),
        "expiration": row.get("expiration_date"),
        "quantity": quantity,
        "premium": premium,
        **({"bid": row.get("bid")} if row.get("bid") is not None else {}),
        **({"ask": row.get("ask")} if row.get("ask") is not None else {}),
    }
    metrics = safe_long_option_metrics(original, leg)
    if not metrics:
        return {
            **base,
            "status": "needs_live_premium",
            "metrics": {},
            "probability": probability_not_available("later_expiration_row_not_priceable"),
            "data_quality": {"premium_source": "delayed_chain_row_invalid"},
        }
    days = calendar_days_to_expiry(str(row.get("expiration_date") or ""))
    iv = positive_number(row.get("implied_volatility")) or original["iv"]
    return {
        **base,
        "status": "ok",
        "metrics": candidate_metrics(metrics, quantity, str(row.get("expiration_date") or ""), days),
        "probability": probability_profile(
            structure=metrics,
            option_side=original["option_side"],
            underlying_price=original["underlying_price"],
            iv=iv,
            days_to_expiry=days,
        ),
        "data_quality": {
            "premium_source": "delayed_chain_mid_or_last",
            "iv_source": "later_expiration_row" if positive_number(row.get("implied_volatility")) else "original_contract",
        },
    }


def vertical_spread_candidate(original: dict[str, Any], market_contracts: list[dict[str, Any]]) -> dict[str, Any]:
    base = {
        "type": "vertical_spread",
        "label": "Convert to a vertical debit spread",
        "thesis_note": "Keeps the direction but caps the upside in exchange for a lower net debit and max loss.",
    }
    if original["premium"] is None or original["strike"] is None:
        return {
            **base,
            "status": "needs_live_premium",
            "metrics": {},
            "probability": probability_not_available("missing_original_premium_or_strike"),
            "data_quality": {"premium_source": "unavailable"},
        }
    row = find_short_leg_row(original, market_contracts)
    if not row:
        return {
            **base,
            "status": "needs_live_premium",
            "metrics": {},
            "probability": probability_not_available("missing_short_leg_premium"),
            "data_quality": {
                "premium_source": "unavailable",
                "note": "No delayed chain row exists for a further-out short strike at the same expiration, so the short-leg credit is not invented.",
            },
        }
    quantity = original["contracts"]
    legs = [
        {
            "action": "buy",
            "type": original["option_side"],
            "strike": original["strike"],
            "expiration": original["expiration"],
            "quantity": quantity,
            "premium": original["premium"],
        },
        {
            "action": "sell",
            "type": original["option_side"],
            "strike": row.get("strike_price") or row.get("strike"),
            "expiration": original["expiration"],
            "quantity": quantity,
            "premium": positive_number(row.get("mid") or row.get("last") or row.get("premium")),
        },
    ]
    metrics = safe_vertical_spread_metrics(original, legs)
    if not metrics:
        return {
            **base,
            "status": "needs_live_premium",
            "metrics": {},
            "probability": probability_not_available("spread_legs_not_priceable"),
            "data_quality": {"premium_source": "delayed_chain_row_invalid"},
        }
    return {
        **base,
        "status": "ok",
        "metrics": candidate_metrics(metrics, quantity, original["expiration"], original["days_left"]),
        "probability": probability_profile(
            structure=metrics,
            option_side=original["option_side"],
            underlying_price=original["underlying_price"],
            iv=original["iv"],
            days_to_expiry=original["days_left"],
        ),
        "data_quality": {"premium_source": "original_long_leg_plus_delayed_chain_short_leg"},
    }


def reduced_size_candidate(original: dict[str, Any]) -> dict[str, Any] | None:
    if original["contracts"] < 2:
        return None
    quantity = max(1, original["contracts"] // 2)
    base = {
        "type": "reduced_size",
        "label": f"Reduce size to {quantity} contract{'s' if quantity != 1 else ''}",
        "thesis_note": "Same structure and timing; only the amount of capital exposed changes.",
    }
    if original["kind"] == "long_option":
        if original["premium"] is None or original["strike"] is None:
            return {
                **base,
                "status": "needs_live_premium",
                "metrics": {},
                "probability": probability_not_available("missing_original_premium_or_strike"),
                "data_quality": {"premium_source": "unavailable"},
            }
        leg = {
            "action": "buy",
            "type": original["option_side"],
            "strike": original["strike"],
            "expiration": original["expiration"],
            "quantity": quantity,
            "premium": original["premium"],
        }
        metrics = safe_long_option_metrics(original, leg)
    else:
        metrics = reduced_structure_from_original(original, quantity)
    if not metrics:
        return {
            **base,
            "status": "needs_live_premium",
            "metrics": {},
            "probability": probability_not_available("original_structure_not_reproducible"),
            "data_quality": {"premium_source": "unavailable"},
        }
    return {
        **base,
        "status": "ok",
        "metrics": candidate_metrics(metrics, quantity, original["expiration"], original["days_left"]),
        "probability": probability_profile(
            structure=metrics,
            option_side=original["option_side"],
            underlying_price=original["underlying_price"],
            iv=original["iv"],
            days_to_expiry=original["days_left"],
        ),
        "data_quality": {"premium_source": "original_contract"},
    }


def reduced_structure_from_original(original: dict[str, Any], quantity: int) -> dict[str, Any] | None:
    """Scale an existing vertical-spread structure's totals to a smaller quantity.

    Per-contract numbers (breakeven, width, net debit/credit) are unchanged;
    only quantity-scaled totals move, so this stays inside the already-verified
    payoff math instead of re-deriving it.
    """
    structure = original.get("structure") or {}
    old_quantity = positive_number(structure.get("quantity"))
    max_loss = positive_number(structure.get("max_loss"))
    if not structure or old_quantity is None or max_loss is None:
        return None
    scale = quantity / old_quantity
    scaled = dict(structure)
    scaled["quantity"] = quantity
    scaled["max_loss"] = round(max_loss * scale, 2)
    if positive_number(structure.get("max_profit")) is not None:
        scaled["max_profit"] = round(float(structure["max_profit"]) * scale, 2)
    return scaled


def wait_candidate(original: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "wait",
        "label": "Wait — no position",
        "thesis_note": "The baseline every candidate competes against: zero premium at risk while the thesis is re-checked.",
        "status": "ok",
        "metrics": {
            "max_loss": 0.0,
            "max_profit": 0.0,
            "breakeven": None,
            "contracts": 0,
            "expiration": None,
            "days_to_expiry": None,
            "net_debit": 0.0,
            "capital_committed": 0.0,
        },
        "probability": probability_not_available("no_position"),
        "data_quality": {"premium_source": "not_applicable"},
    }


def candidate_metrics(structure: dict[str, Any], quantity: int, expiration: str, days: float | int | None) -> dict[str, Any]:
    max_loss = finite_number(structure.get("max_loss"))
    return {
        "kind": structure.get("kind"),
        "label": structure.get("label"),
        "max_loss": max_loss,
        "max_profit": finite_number(structure.get("max_profit")),
        "breakeven": finite_number(structure.get("breakeven")),
        "breakeven_basis": structure.get("breakeven_basis"),
        "net_debit": finite_number(structure.get("net_debit")),
        "net_credit": finite_number(structure.get("net_credit")),
        "spread_width": finite_number(structure.get("width")),
        "contracts": quantity,
        "expiration": expiration or None,
        "days_to_expiry": days,
        "capital_committed": max_loss,
        "structure": structure,
    }


def score_candidate_fit(candidate: dict[str, Any], original: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    sub_scores = applicable_sub_scores(candidate, original)
    scored = []
    total_weight = 0.0
    weighted_sum = 0.0
    for name, value in sub_scores:
        weight = weights.get(name, 0.0)
        if value is None or weight <= 0:
            scored.append({"name": name, "value": value, "weight": weight, "weighted": None, "included": False})
            continue
        scored.append({"name": name, "value": round(value, 4), "weight": weight, "weighted": round(value * weight, 4), "included": True})
        total_weight += weight
        weighted_sum += value * weight
    if total_weight <= 0:
        return {"score": None, "sub_scores": scored, "basis": FIT_BASIS, "note": "No sub-score was computable for this candidate."}
    return {
        "score": round(weighted_sum / total_weight * 100, 1),
        "sub_scores": scored,
        "basis": FIT_BASIS,
        "note": "Weighted sum of the named sub-scores, renormalized over the sub-scores that structurally apply.",
    }


def applicable_sub_scores(candidate: dict[str, Any], original: dict[str, Any]) -> list[tuple[str, float | None]]:
    candidate_type = candidate["type"]
    metrics = candidate.get("metrics") or {}
    if candidate_type == "wait":
        # Time relief is structurally meaningless with no position.
        return [
            ("risk_reduction", 1.0),
            ("thesis_preservation", 0.0),
            ("cost_efficiency", 1.0),
        ]
    if candidate_type == "reduced_size":
        # Same expiration, so a time-relief ratio does not apply.
        return [
            ("risk_reduction", risk_reduction_score(metrics, original)),
            ("thesis_preservation", safe_ratio(metrics.get("contracts"), original["contracts"])),
            ("cost_efficiency", cost_efficiency_score(metrics, original)),
        ]
    if candidate_type == "vertical_spread":
        return [
            ("risk_reduction", risk_reduction_score(metrics, original)),
            ("thesis_preservation", THESIS_PRESERVATION_SPREAD),
            ("cost_efficiency", cost_efficiency_score(metrics, original)),
        ]
    if candidate_type == "later_expiration":
        return [
            ("risk_reduction", risk_reduction_score(metrics, original)),
            ("thesis_preservation", THESIS_PRESERVATION_LATER_EXPIRY),
            ("time_relief", time_relief_score(metrics, original)),
            ("cost_efficiency", cost_efficiency_score(metrics, original)),
        ]
    return []


def risk_reduction_score(metrics: dict[str, Any], original: dict[str, Any]) -> float | None:
    ratio = safe_ratio(metrics.get("max_loss"), original.get("max_loss"))
    if ratio is None:
        return None
    return clamp01(1.0 - ratio)


def cost_efficiency_score(metrics: dict[str, Any], original: dict[str, Any]) -> float | None:
    ratio = safe_ratio(metrics.get("capital_committed"), original.get("max_loss"))
    if ratio is None:
        return None
    return clamp01(1.0 - ratio)


def time_relief_score(metrics: dict[str, Any], original: dict[str, Any]) -> float | None:
    candidate_days = positive_number(metrics.get("days_to_expiry"))
    original_days = positive_number(original.get("days_left"))
    if candidate_days is None or original_days is None or candidate_days <= 0:
        return None
    return clamp01(1.0 - original_days / candidate_days)


def find_later_expiration_row(original: dict[str, Any], market_contracts: list[dict[str, Any]]) -> dict[str, Any] | None:
    strike = original.get("strike")
    original_days = positive_number(original.get("days_left")) or 0
    if strike is None:
        return None
    matches = []
    for row in market_contracts:
        if str(row.get("contract_type") or row.get("optionSide") or "").lower() != original["option_side"]:
            continue
        row_strike = positive_number(row.get("strike_price") or row.get("strike"))
        if row_strike is None or abs(row_strike - strike) > strike * STRIKE_MATCH_TOLERANCE_PCT / 100:
            continue
        days = calendar_days_to_expiry(str(row.get("expiration_date") or ""))
        if days is None or days < original_days + MIN_LATER_EXPIRY_GAP_DAYS:
            continue
        if positive_number(row.get("mid") or row.get("last") or row.get("premium")) is None:
            continue
        matches.append((days, row))
    if not matches:
        return None
    return min(matches, key=lambda item: item[0])[1]


def find_short_leg_row(original: dict[str, Any], market_contracts: list[dict[str, Any]]) -> dict[str, Any] | None:
    strike = original.get("strike")
    if strike is None:
        return None
    long_premium = original.get("premium")
    matches = []
    for row in market_contracts:
        if str(row.get("contract_type") or row.get("optionSide") or "").lower() != original["option_side"]:
            continue
        if str(row.get("expiration_date") or "") != original["expiration"]:
            continue
        row_strike = positive_number(row.get("strike_price") or row.get("strike"))
        premium = positive_number(row.get("mid") or row.get("last") or row.get("premium"))
        if row_strike is None or premium is None:
            continue
        # The short leg must be further out-of-the-money and cheaper than the
        # long leg, otherwise the debit-spread math rejects it anyway.
        further_otm = row_strike > strike if original["option_side"] == "call" else row_strike < strike
        if not further_otm or (long_premium is not None and premium >= long_premium):
            continue
        matches.append((abs(row_strike - strike), row))
    if not matches:
        return None
    return min(matches, key=lambda item: item[0])[1]


def safe_long_option_metrics(original: dict[str, Any], leg: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return long_option_metrics(request_shim(original), leg, original["option_side"])
    except (ValueError, TypeError):
        return None


def safe_vertical_spread_metrics(original: dict[str, Any], legs: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        return vertical_spread_metrics(request_shim(original), legs, original["option_side"])
    except (ValueError, TypeError):
        return None


def request_shim(original: dict[str, Any]) -> TradeCheckRequest:
    """Minimal valid TradeCheckRequest so the scoring metric functions can run.

    Only the leg data matters for the metric functions; the request supplies
    fallbacks (premium/contracts) and passes model validation.
    """
    return TradeCheckRequest(
        ticker=original["ticker"] or "TICK",
        trade_type=original["trade_type"] or ("Put Option (Long)" if original["option_side"] == "put" else "Call Option (Long)"),
        option_side=original["option_side"],
        strike=original["strike"] or 1.0,
        expiration=original["expiration"] or "",
        premium=original["premium"],
        contracts=original["contracts"] or 1,
        amount_at_risk=original["max_loss"] or 1.0,
        timeframe=original["timeframe"],
        account_size=25000,
        underlying_price=original["underlying_price"],
        implied_volatility=original["iv"],
    )


def probability_not_available(reason: str) -> dict[str, Any]:
    return {
        "status": "not_computable" if reason != "no_position" else "not_applicable",
        "basis": PROBABILITY_BASIS,
        "p_profit": None,
        "p_max_profit": None,
        "p_max_profit_note": "",
        "p_max_loss": None,
        "inputs": {},
        "missing": [],
        "reason": reason,
    }


def dict_field(report: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = report.get(key)
        if isinstance(value, dict):
            return value
    return {}


def safe_ratio(numerator: Any, denominator: Any) -> float | None:
    top = finite_number(numerator)
    bottom = finite_number(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    return top / bottom


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def positive_number(value: Any) -> float | None:
    number = finite_number(value)
    return number if number is not None and number > 0 else None


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
