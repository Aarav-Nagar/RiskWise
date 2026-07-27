import math

import pytest

from api import probability
from api.models import TradeCheckRequest
from api.probability import (
    BASIS,
    calendar_days_to_expiry,
    normal_cdf,
    normalize_iv,
    probability_above,
    probability_profile,
)
from api.scoring import long_option_metrics, normalized_option_legs, vertical_spread_metrics


def long_call_structure(strike: float = 100.0, premium: float = 4.0) -> dict:
    return {
        "kind": "long_option",
        "breakeven": strike + premium,
        "primary_strike": strike,
    }


def long_put_structure(strike: float = 100.0, premium: float = 4.0) -> dict:
    return {
        "kind": "long_option",
        "breakeven": strike - premium,
        "primary_strike": strike,
    }


# --- probability_above: textbook Black-Scholes values ---


def test_probability_above_matches_hull_textbook_example() -> None:
    # Hull, Options Futures and Other Derivatives: S=42, K=40, r=10%, sigma=20%, T=0.5y
    # d2 = 0.6278, N(d2) = 0.7349
    p = probability_above(42, 40, iv=0.20, days_to_expiry=0.5 * 365, risk_free_rate=0.10)
    assert p == pytest.approx(0.7349, abs=1e-3)


def test_probability_above_at_the_money_zero_rate() -> None:
    # S=K=100, sigma=20%, T=1y, r=0: d2 = -sigma^2/2 / sigma = -0.10, N(-0.10) = 0.4602
    p = probability_above(100, 100, iv=0.20, days_to_expiry=365, risk_free_rate=0.0)
    assert p == pytest.approx(0.4602, abs=1e-3)


def test_normal_cdf_known_values() -> None:
    assert normal_cdf(0.0) == pytest.approx(0.5, abs=1e-9)
    assert normal_cdf(1.0) == pytest.approx(0.8413, abs=1e-4)
    assert normal_cdf(-1.96) == pytest.approx(0.0250, abs=1e-4)


def test_probability_above_nonpositive_level_is_certain() -> None:
    assert probability_above(100, 0, iv=0.3, days_to_expiry=30) == 1.0
    assert probability_above(100, -5, iv=0.3, days_to_expiry=30) == 1.0


def test_probability_above_rejects_missing_or_invalid_inputs() -> None:
    assert probability_above(100, 105, iv=None, days_to_expiry=30) is None
    assert probability_above(0, 105, iv=0.3, days_to_expiry=30) is None
    assert probability_above(100, 105, iv=0.3, days_to_expiry=0) is None
    assert probability_above(100, 105, iv=-0.3, days_to_expiry=30) is None


def test_iv_percent_and_decimal_forms_agree() -> None:
    # Matches the black_scholes_greeks convention: iv > 3 means percent form.
    as_percent = probability_above(100, 108, iv=27.5, days_to_expiry=45)
    as_decimal = probability_above(100, 108, iv=0.275, days_to_expiry=45)
    assert as_percent == pytest.approx(as_decimal, abs=1e-12)
    assert normalize_iv(27.5) == pytest.approx(0.275)
    assert normalize_iv(0.275) == pytest.approx(0.275)
    assert normalize_iv(None) is None
    assert normalize_iv(0) is None


# --- probability_profile: long options ---


def test_long_call_profile_probabilities() -> None:
    profile = probability_profile(
        structure=long_call_structure(strike=95, premium=7),
        option_side="call",
        underlying_price=100,
        iv=25,
        days_to_expiry=90,
    )
    assert profile["status"] == "ok"
    assert profile["basis"] == BASIS
    expected_profit = probability_above(100, 102, iv=25, days_to_expiry=90)
    expected_max_loss = 1 - probability_above(100, 95, iv=25, days_to_expiry=90)
    assert profile["p_profit"] == pytest.approx(expected_profit, abs=1e-4)
    assert profile["p_max_loss"] == pytest.approx(expected_max_loss, abs=1e-4)
    assert profile["p_max_profit"] is None
    assert profile["p_max_profit_note"] == "not_defined_for_long_option"
    assert profile["inputs"]["direction"] == "bullish"


def test_long_put_profile_probabilities() -> None:
    profile = probability_profile(
        structure=long_put_structure(strike=105, premium=6),
        option_side="put",
        underlying_price=100,
        iv=0.30,
        days_to_expiry=60,
    )
    assert profile["status"] == "ok"
    expected_profit = 1 - probability_above(100, 99, iv=0.30, days_to_expiry=60)
    expected_max_loss = probability_above(100, 105, iv=0.30, days_to_expiry=60)
    assert profile["p_profit"] == pytest.approx(expected_profit, abs=1e-4)
    assert profile["p_max_loss"] == pytest.approx(expected_max_loss, abs=1e-4)
    assert profile["inputs"]["direction"] == "bearish"


def test_deep_put_with_nonpositive_breakeven_has_zero_profit_probability() -> None:
    # strike 5, premium 6 -> breakeven -1: profit at expiry is impossible, not "missing data"
    profile = probability_profile(
        structure=long_put_structure(strike=5, premium=6),
        option_side="put",
        underlying_price=5,
        iv=0.9,
        days_to_expiry=30,
    )
    assert profile["status"] == "ok"
    assert profile["p_profit"] == 0.0


def test_long_option_profile_from_scoring_structure() -> None:
    request = TradeCheckRequest(
        ticker="AAPL",
        trade_type="Call Option (Long)",
        option_side="call",
        strike=190,
        expiration="2027-01-15",
        premium=5.0,
        contracts=1,
        amount_at_risk=500,
        timeframe="1-2 Weeks",
        account_size=25000,
        underlying_price=192.0,
        implied_volatility=0.31,
    )
    leg = normalized_option_legs(request)[0]
    structure = long_option_metrics(request, leg, "call")
    profile = probability_profile(
        structure=structure,
        option_side="call",
        underlying_price=192.0,
        iv=0.31,
        days_to_expiry=120,
    )
    assert profile["status"] == "ok"
    assert 0.0 < profile["p_profit"] < 1.0
    assert 0.0 < profile["p_max_loss"] < 1.0


# --- probability_profile: vertical spreads ---


def spread_request(trade_type: str, option_side: str, legs: list[dict]) -> TradeCheckRequest:
    return TradeCheckRequest(
        ticker="MSFT",
        trade_type=trade_type,
        option_side=option_side,
        strike=legs[0]["strike"],
        expiration="2027-01-15",
        amount_at_risk=200,
        timeframe="1-3 Months",
        account_size=25000,
        option_legs=legs,
    )


def test_call_debit_spread_profile_orders_probabilities() -> None:
    legs = [
        {"action": "buy", "type": "call", "strike": 100, "expiration": "2027-01-15", "quantity": 1, "premium": 5.0},
        {"action": "sell", "type": "call", "strike": 110, "expiration": "2027-01-15", "quantity": 1, "premium": 3.0},
    ]
    request = spread_request("Call Spread", "call", legs)
    structure = vertical_spread_metrics(request, [dict(leg) for leg in legs], "call")
    profile = probability_profile(
        structure=structure,
        option_side="call",
        underlying_price=101,
        iv=0.28,
        days_to_expiry=75,
    )
    assert profile["status"] == "ok"
    # Breakeven (102) sits between the strikes, so:
    # P(max profit: S>110) <= P(profit: S>102) <= P(not max loss: S>100)
    assert profile["p_max_profit"] <= profile["p_profit"] <= 1 - profile["p_max_loss"]
    expected_profit = probability_above(101, 102, iv=0.28, days_to_expiry=75)
    expected_max_profit = probability_above(101, 110, iv=0.28, days_to_expiry=75)
    expected_max_loss = 1 - probability_above(101, 100, iv=0.28, days_to_expiry=75)
    assert profile["p_profit"] == pytest.approx(expected_profit, abs=1e-4)
    assert profile["p_max_profit"] == pytest.approx(expected_max_profit, abs=1e-4)
    assert profile["p_max_loss"] == pytest.approx(expected_max_loss, abs=1e-4)


def test_put_credit_spread_profile_is_bullish() -> None:
    legs = [
        {"action": "sell", "type": "put", "strike": 100, "expiration": "2027-01-15", "quantity": 1, "premium": 4.0},
        {"action": "buy", "type": "put", "strike": 90, "expiration": "2027-01-15", "quantity": 1, "premium": 1.5},
    ]
    request = spread_request("Put Spread", "put", legs)
    structure = vertical_spread_metrics(request, [dict(leg) for leg in legs], "put")
    assert structure["spread_orientation"] == "put_credit"
    profile = probability_profile(
        structure=structure,
        option_side="put",
        underlying_price=103,
        iv=0.35,
        days_to_expiry=45,
    )
    assert profile["status"] == "ok"
    assert profile["inputs"]["direction"] == "bullish"
    # Breakeven = 100 - 2.5 = 97.5; max profit above short strike 100; max loss below long strike 90.
    expected_profit = probability_above(103, 97.5, iv=0.35, days_to_expiry=45)
    expected_max_profit = probability_above(103, 100, iv=0.35, days_to_expiry=45)
    expected_max_loss = 1 - probability_above(103, 90, iv=0.35, days_to_expiry=45)
    assert profile["p_profit"] == pytest.approx(expected_profit, abs=1e-4)
    assert profile["p_max_profit"] == pytest.approx(expected_max_profit, abs=1e-4)
    assert profile["p_max_loss"] == pytest.approx(expected_max_loss, abs=1e-4)


def test_call_credit_spread_profile_is_bearish() -> None:
    legs = [
        {"action": "sell", "type": "call", "strike": 100, "expiration": "2027-01-15", "quantity": 1, "premium": 4.0},
        {"action": "buy", "type": "call", "strike": 110, "expiration": "2027-01-15", "quantity": 1, "premium": 1.5},
    ]
    request = spread_request("Call Spread", "call", legs)
    structure = vertical_spread_metrics(request, [dict(leg) for leg in legs], "call")
    assert structure["spread_orientation"] == "call_credit"
    profile = probability_profile(
        structure=structure,
        option_side="call",
        underlying_price=99,
        iv=0.32,
        days_to_expiry=50,
    )
    assert profile["status"] == "ok"
    assert profile["inputs"]["direction"] == "bearish"
    # Breakeven = 100 + 2.5 = 102.5; max profit below short strike 100; max loss above long strike 110.
    expected_profit = 1 - probability_above(99, 102.5, iv=0.32, days_to_expiry=50)
    expected_max_profit = 1 - probability_above(99, 100, iv=0.32, days_to_expiry=50)
    expected_max_loss = probability_above(99, 110, iv=0.32, days_to_expiry=50)
    assert profile["p_profit"] == pytest.approx(expected_profit, abs=1e-4)
    assert profile["p_max_profit"] == pytest.approx(expected_max_profit, abs=1e-4)
    assert profile["p_max_loss"] == pytest.approx(expected_max_loss, abs=1e-4)


def test_put_debit_spread_profile_is_bearish() -> None:
    legs = [
        {"action": "buy", "type": "put", "strike": 100, "expiration": "2027-01-15", "quantity": 1, "premium": 5.0},
        {"action": "sell", "type": "put", "strike": 90, "expiration": "2027-01-15", "quantity": 1, "premium": 2.0},
    ]
    request = spread_request("Put Spread", "put", legs)
    structure = vertical_spread_metrics(request, [dict(leg) for leg in legs], "put")
    assert structure["spread_orientation"] == "put_debit"
    profile = probability_profile(
        structure=structure,
        option_side="put",
        underlying_price=98,
        iv=0.4,
        days_to_expiry=60,
    )
    assert profile["status"] == "ok"
    assert profile["inputs"]["direction"] == "bearish"
    # Breakeven = 100 - 3 = 97; max profit below short strike 90; max loss above long strike 100.
    expected_profit = 1 - probability_above(98, 97, iv=0.4, days_to_expiry=60)
    expected_max_profit = 1 - probability_above(98, 90, iv=0.4, days_to_expiry=60)
    expected_max_loss = probability_above(98, 100, iv=0.4, days_to_expiry=60)
    assert profile["p_profit"] == pytest.approx(expected_profit, abs=1e-4)
    assert profile["p_max_profit"] == pytest.approx(expected_max_profit, abs=1e-4)
    assert profile["p_max_loss"] == pytest.approx(expected_max_loss, abs=1e-4)


# --- not computable: never a default volatility ---


def test_missing_iv_is_not_computable_with_no_default_volatility() -> None:
    profile = probability_profile(
        structure=long_call_structure(),
        option_side="call",
        underlying_price=100,
        iv=None,
        days_to_expiry=30,
    )
    assert profile["status"] == "not_computable"
    assert profile["reason"] == "missing_iv"
    assert "implied volatility" in profile["missing"]
    assert profile["basis"] == BASIS
    assert profile["p_profit"] is None
    assert profile["p_max_profit"] is None
    assert profile["p_max_loss"] is None


def test_missing_underlying_or_expired_is_not_computable() -> None:
    no_underlying = probability_profile(
        structure=long_call_structure(),
        option_side="call",
        underlying_price=None,
        iv=0.3,
        days_to_expiry=30,
    )
    assert no_underlying["status"] == "not_computable"
    assert "underlying price" in no_underlying["missing"]

    expired = probability_profile(
        structure=long_call_structure(),
        option_side="call",
        underlying_price=100,
        iv=0.3,
        days_to_expiry=0,
    )
    assert expired["status"] == "not_computable"
    assert "days to expiry" in expired["missing"]


def test_incomplete_structure_is_not_computable() -> None:
    profile = probability_profile(
        structure={"kind": "vertical_spread", "breakeven": 102, "primary_strike": 100},
        option_side="call",
        underlying_price=100,
        iv=0.3,
        days_to_expiry=30,
    )
    assert profile["status"] == "not_computable"
    assert "structure fields" in profile["missing"]


# --- v1 scope guard ---


def test_no_probability_of_touch_ships_in_v1() -> None:
    exported = [name for name in dir(probability) if "touch" in name.lower()]
    assert exported == [], "probability-of-touch is cut from v1 (breakeven price touch != breakeven P&L)"


def test_calendar_days_to_expiry_helper() -> None:
    from datetime import date, timedelta

    future = (date.today() + timedelta(days=45)).isoformat()
    assert calendar_days_to_expiry(future) == 45
    assert calendar_days_to_expiry("not-a-date") is None
    past = (date.today() - timedelta(days=3)).isoformat()
    assert calendar_days_to_expiry(past) is None
