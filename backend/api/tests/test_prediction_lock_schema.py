from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def make_user(clerk_id: str, email: str) -> dict:
    response = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": clerk_id,
            "name": "Prediction Lock Tester",
            "email": email,
            "accountSize": 25000,
            "riskBudgetPercent": 2,
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
    assert response.status_code == 200
    return response.json()


def sample_report() -> dict:
    return {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "riskMath": {"max_loss": 425, "breakeven": 194.25, "trading_days_left": 19},
    }


def test_saved_check_persists_prediction_lock_and_pending_resolution() -> None:
    user = make_user("clerk_lock_owner", "lock-owner@example.com")
    response = client.post(
        "/saved-checks",
        json={
            "user_id": user["id"],
            "trade_check_id": "check_lock_1",
            "report": sample_report(),
            "note": "conviction test",
            "prediction_lock": {
                "conviction_pct": 65,
                "direction": "bullish",
                "thesis_text": "Product cycle should lift the stock before expiry.",
                "underlying_at_lock": 190.4,
                "breakeven": 194.25,
                "expiration": "2026-08-21",
            },
        },
    )
    assert response.status_code == 200
    saved = response.json()
    lock = saved["prediction_lock"]
    assert lock["conviction_pct"] == 65
    assert lock["direction"] == "bullish"
    assert lock["underlying_at_lock"] == 190.4
    assert lock["breakeven"] == 194.25
    assert lock["expiration"] == "2026-08-21"
    assert lock["locked_at"], "locked_at should be stamped server-side when omitted"

    resolution = saved["resolution"]
    assert resolution["status"] == "pending"
    assert resolution["underlying_at_expiry"] is None
    assert resolution["touched_breakeven"] is None
    assert resolution["hit"] is None
    assert resolution["resolved_at"] is None

    listed = client.get(f"/saved-checks/{user['id']}")
    assert listed.status_code == 200
    stored = next(item for item in listed.json() if item["id"] == saved["id"])
    assert stored["prediction_lock"]["conviction_pct"] == 65
    assert stored["resolution"]["status"] == "pending"


def test_saved_check_without_prediction_lock_keeps_fields_null() -> None:
    user = make_user("clerk_lock_optional", "lock-optional@example.com")
    response = client.post(
        "/saved-checks",
        json={
            "user_id": user["id"],
            "trade_check_id": None,
            "report": sample_report(),
            "note": "",
        },
    )
    assert response.status_code == 200
    saved = response.json()
    assert saved["prediction_lock"] is None
    assert saved["resolution"] is None


def test_saved_check_client_locked_at_is_preserved() -> None:
    user = make_user("clerk_lock_stamp", "lock-stamp@example.com")
    response = client.post(
        "/saved-checks",
        json={
            "user_id": user["id"],
            "report": sample_report(),
            "prediction_lock": {
                "conviction_pct": 40,
                "direction": "bearish",
                "expiration": "2026-09-18",
                "locked_at": "2026-07-01T10:00:00+00:00",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["prediction_lock"]["locked_at"] == "2026-07-01T10:00:00+00:00"


def test_prediction_lock_conviction_must_stay_within_bounds() -> None:
    user = make_user("clerk_lock_bounds", "lock-bounds@example.com")
    for bad_conviction in (-5, 130):
        response = client.post(
            "/saved-checks",
            json={
                "user_id": user["id"],
                "report": sample_report(),
                "prediction_lock": {
                    "conviction_pct": bad_conviction,
                    "direction": "bullish",
                    "expiration": "2026-08-21",
                },
            },
        )
        assert response.status_code == 422
