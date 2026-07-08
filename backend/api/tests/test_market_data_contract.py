from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.app import app
from api.services import market_data


client = TestClient(app)


def test_market_search_shape_is_safe() -> None:
    response = client.get("/market/search", params={"q": "apple"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    body = response.json()
    assert body["query"] == "apple"
    assert "items" in body
    assert "api" not in str(body).lower()
    assert "secret" not in str(body).lower()


def test_market_search_finds_niche_symbols_from_local_index() -> None:
    for query, expected in [("RKLB", "RKLB"), ("SoundHound", "SOUN"), ("Reddit", "RDDT")]:
        response = client.get("/market/search", params={"q": query})

        assert response.status_code == 200
        symbols = [item["symbol"] for item in response.json()["items"]]
        assert expected in symbols


def test_market_search_ranks_exact_symbol_before_company_name_noise() -> None:
    ranked = market_data.rank_search_items(
        "ACHR",
        [
            {"symbol": "XYZ", "name": "Achr Holdings Example", "exchange": "NASDAQ"},
            {"symbol": "ACHR", "name": "Archer Aviation Inc.", "exchange": "NYSE"},
            {"symbol": "ARCH", "name": "Arch Resources", "exchange": "NYSE"},
        ],
    )

    assert ranked[0]["symbol"] == "ACHR"


def test_options_context_is_honest_about_missing_contract_feed() -> None:
    response = client.get("/market/options-context/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    pending = set(body["fields_pending"])
    assert pending.intersection({"provider_reported_greeks", "real_time_opra_snapshot", "option_chain", "live_premium"})
    assert (
        "delayed" in body["message"].lower()
        or "polygon" in body["message"].lower()
        or "tradier" in body["message"].lower()
        or "massive" in body["message"].lower()
    )


def test_market_provider_status_is_explicit_and_secret_safe() -> None:
    response = client.get("/market/providers")

    assert response.status_code == 200
    body = response.json()
    providers = {item["provider"]: item for item in body["capabilities"]}
    assert body["strategy"] == "free_honest_stack"
    assert "manual_upload" in providers
    assert "yfinance_delayed" in providers
    assert "Reference-only" in body["data_quality_labels"]
    serialized = str(body).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized


def test_options_chain_endpoint_does_not_fake_contracts() -> None:
    response = client.get("/market/options/chain/AAPL")

    assert response.status_code == 200
    body = response.json()
    if body["provider"] == "massive_polygon_reference":
        assert body["status"] in {"reference_chain_ready", "reference_chain_empty"}
        assert "premium" not in str(body["contracts"]).lower()
    elif body["provider"] == "yfinance_delayed":
        assert body["status"] == "delayed_chain_ready"
        assert "delayed" in body["message"].lower()
        assert all(contract.get("has_live_quote") is False for contract in body["contracts"][:10])
        assert all(str(contract.get("data_quality")).lower() == "delayed" for contract in body["contracts"][:10])
    else:
        assert body["status"] == "requires_options_provider"
        assert body["contracts"] == []


def test_polygon_reference_contracts_normalize_without_live_quote() -> None:
    contract = market_data.normalize_polygon_contract(
        {
            "ticker": "O:AAPL260621C00200000",
            "underlying_ticker": "AAPL",
            "contract_type": "call",
            "expiration_date": "2026-06-21",
            "strike_price": 200,
            "shares_per_contract": 100,
            "exercise_style": "american",
        }
    )

    assert contract["contract_symbol"] == "O:AAPL260621C00200000"
    assert contract["contract_type"] == "call"
    assert contract["has_live_quote"] is False


def test_trade_check_rejects_past_expiration() -> None:
    expiration = (date.today() - timedelta(days=1)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option (Long)",
            "strike": 190,
            "expiration": expiration,
            "amount_at_risk": 500,
            "timeframe": "1-2 Weeks",
            "account_size": 25000,
        },
    )

    assert response.status_code == 400
    assert "expiration" in response.json()["detail"].lower()


def test_trade_check_rejects_impossible_bid_ask() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option (Long)",
            "strike": 190,
            "expiration": expiration,
            "premium": 2.15,
            "contracts": 1,
            "bid": 2.4,
            "ask": 2.1,
            "amount_at_risk": 215,
            "timeframe": "1-2 Weeks",
            "account_size": 25000,
        },
    )

    assert response.status_code == 400
    assert "bid" in response.json()["detail"].lower()
    assert "ask" in response.json()["detail"].lower()


def test_trade_check_rejects_spreads_without_legs_and_income_structures() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    for trade_type in ["Call Option Spread", "Put Option Spread"]:
        response = client.post(
            "/trade-check",
            json={
                "user_id": "test_user",
                "ticker": "AAPL",
                "trade_type": trade_type,
                "strike": 190,
                "expiration": expiration,
                "premium": 2.15,
                "contracts": 1,
                "amount_at_risk": 215,
                "timeframe": "1-2 Weeks",
                "account_size": 25000,
            },
        )

        assert response.status_code == 400
        assert "Spread checks require exactly two option legs" in response.json()["detail"]

    for trade_type in ["Cash Secured Put", "Covered Call"]:
        response = client.post(
            "/trade-check",
            json={
                "user_id": "test_user",
                "ticker": "AAPL",
                "trade_type": trade_type,
                "strike": 190,
                "expiration": expiration,
                "premium": 2.15,
                "contracts": 1,
                "amount_at_risk": 215,
                "timeframe": "1-2 Weeks",
                "account_size": 25000,
            },
        )

        assert response.status_code == 400
        assert "Covered calls and cash-secured puts" in response.json()["detail"]


def test_trade_check_uses_profile_risk_budget_and_medium_horizon() -> None:
    expiration = (date.today() + timedelta(days=95)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option (Long)",
            "option_side": "call",
            "strike": 205,
            "expiration": expiration,
            "premium": 2.5,
            "contracts": 1,
            "amount_at_risk": 250,
            "timeframe": "1-3 Months",
            "account_size": 25000,
            "risk_budget_percent": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision_snapshot"]["profile_risk_limit"] == 1
    assert body["risk_math"]["planned_hold_days"] == 45
    assert body["risk_math"]["dollars_until_profile_limit"] == 0


def test_trade_check_required_move_uses_underlying_to_breakeven() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option (Long)",
            "option_side": "call",
            "strike": 200,
            "expiration": expiration,
            "premium": 5,
            "contracts": 1,
            "underlying_price": 195,
            "amount_at_risk": 500,
            "timeframe": "1-2 Weeks",
            "account_size": 25000,
            "risk_budget_percent": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_math"]["breakeven"] == 205
    assert body["risk_math"]["required_move_to_breakeven_pct"] == 5.13
    assert body["risk_math"]["required_move_basis"] == "underlying_to_breakeven"


def test_trade_check_accepts_thesis_and_single_option_leg_model() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option (Long)",
            "option_side": "call",
            "strike": 200,
            "expiration": expiration,
            "premium": 5,
            "contracts": 1,
            "amount_at_risk": 500,
            "timeframe": "1-3 Months",
            "account_size": 25000,
            "risk_budget_percent": 2,
            "trade_thesis": {
                "direction": "bullish",
                "target_price_low": 205,
                "target_price_high": 215,
                "target_date": expiration,
                "catalyst": "Product event",
                "invalidation": "Close below support",
                "confidence": 62,
                "maximum_loss": 500,
                "intended_hold_period": "1-3 Months",
            },
            "option_legs": [
                {
                    "action": "buy",
                    "type": "call",
                    "strike": 200,
                    "expiration": expiration,
                    "quantity": 1,
                    "bid": 4.9,
                    "ask": 5.1,
                    "premium": 5,
                    "iv": 42,
                    "greeks": {"delta": 0.48, "theta": -0.08},
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision_snapshot"]["trade_thesis"]["direction"] == "bullish"
    assert body["decision_snapshot"]["trade_thesis"]["maximum_loss"] == 500
    assert body["contract_snapshot"]["option_legs"][0]["action"] == "buy"
    assert body["contract_snapshot"]["option_legs"][0]["greeks"]["theta"] == -0.08


def test_trade_check_scores_call_debit_spread_with_two_legs() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option Spread",
            "option_side": "call",
            "strike": 200,
            "expiration": expiration,
            "premium": 5,
            "contracts": 1,
            "amount_at_risk": 300,
            "timeframe": "1-3 Months",
            "account_size": 25000,
            "option_legs": [
                {"action": "buy", "type": "call", "strike": 200, "expiration": expiration, "quantity": 1, "premium": 5},
                {"action": "sell", "type": "call", "strike": 210, "expiration": expiration, "quantity": 1, "premium": 2},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_math"]["strategy_kind"] == "vertical_spread"
    assert body["risk_math"]["spread_width"] == 10
    assert body["risk_math"]["net_debit"] == 3
    assert body["risk_math"]["max_loss"] == 300
    assert body["risk_math"]["max_profit"] == 700
    assert body["risk_math"]["breakeven"] == 203


def test_trade_check_scores_put_debit_spread_with_downside_breakeven() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Put Option Spread",
            "option_side": "put",
            "strike": 210,
            "expiration": expiration,
            "premium": 5,
            "contracts": 1,
            "amount_at_risk": 300,
            "timeframe": "1-3 Months",
            "account_size": 25000,
            "underlying_price": 215,
            "option_legs": [
                {"action": "buy", "type": "put", "strike": 210, "expiration": expiration, "quantity": 1, "premium": 5},
                {"action": "sell", "type": "put", "strike": 200, "expiration": expiration, "quantity": 1, "premium": 2},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_math"]["strategy_kind"] == "vertical_spread"
    assert body["risk_math"]["spread_width"] == 10
    assert body["risk_math"]["net_debit"] == 3
    assert body["risk_math"]["max_loss"] == 300
    assert body["risk_math"]["max_profit"] == 700
    assert body["risk_math"]["breakeven"] == 207
    assert body["risk_math"]["required_move_to_breakeven_pct"] == 3.72
    assert body["contract_snapshot"]["structure"]["spread_orientation"] == "put_debit"


def test_trade_check_scores_call_credit_spread_with_bearish_breakeven() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option Spread",
            "option_side": "call",
            "strike": 210,
            "expiration": expiration,
            "premium": 2,
            "contracts": 1,
            "amount_at_risk": 700,
            "timeframe": "1-3 Months",
            "account_size": 25000,
            "underlying_price": 216,
            "option_legs": [
                {"action": "buy", "type": "call", "strike": 220, "expiration": expiration, "quantity": 1, "premium": 2},
                {"action": "sell", "type": "call", "strike": 210, "expiration": expiration, "quantity": 1, "premium": 5},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_math"]["strategy_kind"] == "vertical_spread"
    assert body["risk_math"]["spread_width"] == 10
    assert body["risk_math"]["net_credit"] == 3
    assert body["risk_math"]["max_loss"] == 700
    assert body["risk_math"]["max_profit"] == 300
    assert body["risk_math"]["breakeven"] == 213
    assert body["risk_math"]["required_move_to_breakeven_pct"] == 1.39
    assert body["contract_snapshot"]["structure"]["spread_orientation"] == "call_credit"


def test_trade_check_scores_put_credit_spread_with_bullish_breakeven() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Put Option Spread",
            "option_side": "put",
            "strike": 200,
            "expiration": expiration,
            "premium": 2,
            "contracts": 1,
            "amount_at_risk": 700,
            "timeframe": "1-3 Months",
            "account_size": 25000,
            "underlying_price": 194,
            "option_legs": [
                {"action": "buy", "type": "put", "strike": 190, "expiration": expiration, "quantity": 1, "premium": 2},
                {"action": "sell", "type": "put", "strike": 200, "expiration": expiration, "quantity": 1, "premium": 5},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_math"]["strategy_kind"] == "vertical_spread"
    assert body["risk_math"]["spread_width"] == 10
    assert body["risk_math"]["net_credit"] == 3
    assert body["risk_math"]["max_loss"] == 700
    assert body["risk_math"]["max_profit"] == 300
    assert body["risk_math"]["breakeven"] == 197
    assert body["risk_math"]["required_move_to_breakeven_pct"] == 1.55
    assert body["contract_snapshot"]["structure"]["spread_orientation"] == "put_credit"


def test_trade_check_returns_expiration_aware_agent_detail() -> None:
    expiration = (date.today() + timedelta(days=45)).isoformat()
    response = client.post(
        "/trade-check",
        json={
            "user_id": "test_user",
            "ticker": "AAPL",
            "trade_type": "Call Option (Long)",
            "strike": 190,
            "expiration": expiration,
            "premium": 2.5,
            "contracts": 1,
            "amount_at_risk": 250,
            "timeframe": "1-2 Weeks",
            "account_size": 25000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_math"]["calendar_days_left"] >= 0
    assert "why_it_matters" in body["agent_docket"][0]
    assert "next_question" in body["agent_docket"][0]
