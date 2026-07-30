"""Black-Scholes N(d2)-family expiry probabilities from delayed IV.

Only expiry-defined quantities ship here: P(profit at expiry), P(max profit),
and P(max loss). "Probability of touch" is deliberately not implemented —
touching the breakeven price before expiry is not the same as the position
reaching breakeven P&L (time value), so it is cut from v1.

Every result is labeled with basis "delayed_iv_black_scholes" because the IV
input comes from the delayed yfinance chain, not a live OPRA feed. When IV is
missing the profile is returned as "not_computable" — a default volatility is
never substituted.
"""

from __future__ import annotations

import math
from datetime import date

from .scoring import parse_expiration_date

BASIS = "delayed_iv_black_scholes"
DEFAULT_RISK_FREE_RATE = 0.04
BULLISH_ORIENTATIONS = {"call_debit", "put_credit"}


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def normalize_iv(iv: float | None) -> float | None:
    """Accept IV as a decimal (0.28) or a percent (28), matching black_scholes_greeks."""
    if iv is None:
        return None
    value = float(iv)
    if value <= 0 or not math.isfinite(value):
        return None
    return value / 100 if value > 3 else value


def calendar_days_to_expiry(expiration: str, today: date | None = None) -> int | None:
    parsed = parse_expiration_date(expiration)
    if parsed is None:
        return None
    return max(0, (parsed - (today or date.today())).days)


def probability_above(
    underlying_price: float,
    level: float,
    *,
    iv: float,
    days_to_expiry: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float | None:
    """Risk-neutral P(S_T > level) at expiry: N(d2) with strike = level."""
    sigma = normalize_iv(iv)
    if sigma is None or not underlying_price or underlying_price <= 0 or days_to_expiry is None or days_to_expiry <= 0:
        return None
    if level is None:
        return None
    if level <= 0:
        return 1.0
    years = float(days_to_expiry) / 365.0
    d2 = (math.log(underlying_price / level) + (risk_free_rate - 0.5 * sigma * sigma) * years) / (sigma * math.sqrt(years))
    return normal_cdf(d2)


def probability_profile(
    *,
    structure: dict[str, object],
    option_side: str,
    underlying_price: float | None,
    iv: float | None,
    days_to_expiry: float | None,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> dict[str, object]:
    """Expiry probability profile for a scored long option or vertical spread structure.

    `structure` is the dict produced by scoring.long_option_metrics or
    scoring.vertical_spread_metrics (kind, breakeven, primary_strike,
    short_strike, spread_orientation).
    """
    missing = []
    if normalize_iv(iv) is None:
        missing.append("implied volatility")
    if not underlying_price or underlying_price <= 0:
        missing.append("underlying price")
    if days_to_expiry is None or days_to_expiry <= 0:
        missing.append("days to expiry")
    kind = str(structure.get("kind") or "")
    # Breakeven may legitimately be <= 0 (deep put: strike - premium), so only
    # require it to be a finite number; strikes must be positive.
    breakeven = to_finite_number(structure.get("breakeven"))
    long_strike = to_positive_number(structure.get("primary_strike"))
    short_strike = to_positive_number(structure.get("short_strike"))
    if kind not in {"long_option", "vertical_spread"} or breakeven is None or long_strike is None:
        missing.append("structure fields")
    elif kind == "vertical_spread" and short_strike is None:
        missing.append("structure fields")
    if missing:
        reason = "missing_iv" if "implied volatility" in missing else f"missing_{missing[0].replace(' ', '_')}"
        return not_computable(reason, missing)

    def p_above(level: float) -> float:
        value = probability_above(
            float(underlying_price),
            level,
            iv=float(iv),
            days_to_expiry=float(days_to_expiry),
            risk_free_rate=risk_free_rate,
        )
        return float(value if value is not None else 0.0)

    orientation = str(structure.get("spread_orientation") or "")
    if kind == "vertical_spread":
        bullish = orientation in BULLISH_ORIENTATIONS
    else:
        bullish = str(option_side or "").strip().lower() != "put"

    if kind == "long_option":
        p_profit = p_above(breakeven) if bullish else 1 - p_above(breakeven)
        p_max_loss = 1 - p_above(long_strike) if bullish else p_above(long_strike)
        p_max_profit = None
        p_max_profit_note = "not_defined_for_long_option"
    else:
        if bullish:
            p_profit = p_above(breakeven)
            p_max_profit = p_above(short_strike)
            p_max_loss = 1 - p_above(long_strike)
        else:
            p_profit = 1 - p_above(breakeven)
            p_max_profit = 1 - p_above(short_strike)
            p_max_loss = p_above(long_strike)
        p_max_profit = round(p_max_profit, 4)
        p_max_profit_note = ""

    return {
        "status": "ok",
        "basis": BASIS,
        "p_profit": round(p_profit, 4),
        "p_max_profit": p_max_profit,
        "p_max_profit_note": p_max_profit_note,
        "p_max_loss": round(p_max_loss, 4),
        "inputs": {
            "underlying_price": float(underlying_price),
            "iv": normalize_iv(iv),
            "days_to_expiry": float(days_to_expiry),
            "risk_free_rate": risk_free_rate,
            "structure_kind": kind,
            "direction": "bullish" if bullish else "bearish",
        },
        "missing": [],
        "reason": "",
    }


def not_computable(reason: str, missing: list[str]) -> dict[str, object]:
    return {
        "status": "not_computable",
        "basis": BASIS,
        "p_profit": None,
        "p_max_profit": None,
        "p_max_profit_note": "",
        "p_max_loss": None,
        "inputs": {},
        "missing": missing,
        "reason": reason,
    }


def to_positive_number(value: object) -> float | None:
    number = to_finite_number(value)
    return number if number is not None and number > 0 else None


def to_finite_number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
