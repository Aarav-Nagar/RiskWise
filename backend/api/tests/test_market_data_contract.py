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
            "amount_at_risk": 500,
            "timeframe": "1-2 Weeks",
            "account_size": 25000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_math"]["calendar_days_left"] >= 0
    assert "why_it_matters" in body["agent_docket"][0]
    assert "next_question" in body["agent_docket"][0]
