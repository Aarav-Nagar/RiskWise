from fastapi.testclient import TestClient

from api.app import app
from api.services.check_export import build_saved_check_export


client = TestClient(app)


def test_saved_check_export_serializes_stored_context_without_ai() -> None:
    export = build_saved_check_export(
        {
            "id": "saved_export_example",
            "report": {
                "ticker": "AAPL",
                "tradeType": "Long Call Option",
                "strike": 190,
                "expiration": "2026-07-17",
                "prediction": {
                    "direction": "bullish",
                    "targetPrice": 205,
                    "targetDate": "2026-07-10",
                    "reason": "A product catalyst may improve sentiment.",
                    "invalidationPrice": 180,
                },
                "contractSnapshot": {
                    "option_side": "call",
                    "strike": 190,
                    "expiration": "2026-07-17",
                    "premium": 4.25,
                    "contracts": 2,
                    "bid": 4.1,
                    "ask": 4.4,
                    "spread_pct": 7.1,
                    "implied_volatility": 31.5,
                    "open_interest": 840,
                    "volume": 125,
                    "underlying_price": 194.2,
                },
                "riskMath": {"notional_premium": 850, "calendar_days_left": 27},
                "agreementMap": {
                    "agree": ["The downside is defined."],
                    "disagree": ["The spread is wider than the user's preferred range."],
                },
            },
        },
        {
            "accountSize": 25000,
            "riskBudgetPercent": 2,
            "experienceLevel": "Some experience",
            "riskStyle": "Balanced",
        },
        generated_at="2026-06-20T12:00:00+00:00",
    )

    assert export["filename"] == "riskwise-aapl-call-190-2026-07-17.md"
    assert "# RiskWise Check Export — AAPL CALL $190 2026-07-17" in export["markdown"]
    assert "Premium: $4.25 x 2 contracts = $850 total" in export["markdown"]
    assert "Verdict: Disagree — 1 of 2 disagreement points" in export["markdown"]
    assert "The spread is wider than the user's preferred range." in export["markdown"]


def test_saved_check_export_labels_missing_values_not_confirmed() -> None:
    export = build_saved_check_export(
        {"id": "saved_partial", "report": {"ticker": "MSFT", "agreementMap": {}}},
        {},
        generated_at="2026-06-20T12:00:00+00:00",
    )

    assert "Direction: not confirmed" in export["markdown"]
    assert "IV: not confirmed" in export["markdown"]
    assert "Volume / OI: not confirmed / not confirmed" in export["markdown"]
    assert "None" not in export["markdown"]
    assert "null" not in export["markdown"]


def test_saved_check_export_endpoint_requires_owned_saved_check() -> None:
    user_response = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": "clerk_export_owner",
            "name": "Export Owner",
            "email": "export-owner@example.com",
            "accountSize": 30000,
            "riskBudgetPercent": 1.5,
            "purpose": ["Reviewing decisions"],
            "tradeFocus": ["Options"],
            "experienceLevel": "Some experience",
            "riskStyle": "Balanced",
            "struggles": [],
            "reminders": [],
            "sectors": [],
            "marketCaps": [],
            "events": [],
            "safetyAccepted": True,
        },
    )
    assert user_response.status_code == 200
    user = user_response.json()
    saved_response = client.post(
        "/saved-checks",
        json={
            "user_id": user["id"],
            "trade_check_id": "check_export_endpoint",
            "report": {
                "ticker": "NVDA",
                "tradeType": "Long Put Option",
                "contractSnapshot": {"option_side": "put", "strike": 120, "expiration": "2026-08-21"},
            },
            "note": "",
        },
    )
    assert saved_response.status_code == 200
    saved = saved_response.json()

    response = client.get(f"/saved-checks/{user['id']}/{saved['id']}/export")
    assert response.status_code == 200
    assert response.json()["savedCheckId"] == saved["id"]
    assert "NVDA PUT $120 2026-08-21" in response.json()["markdown"]

    missing = client.get(f"/saved-checks/{user['id']}/saved_not_owned/export")
    assert missing.status_code == 404
