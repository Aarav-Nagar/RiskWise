from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.app import app
from api.services import auth as auth_service
from api.settings import settings


client = TestClient(app)


def user_payload(clerk_id: str, email: str) -> dict[str, object]:
    return {
        "clerkId": clerk_id,
        "name": "Auth Tester",
        "email": email,
        "accountSize": 25000,
        "riskBudgetPercent": 2,
        "purpose": ["Reviewing decisions"],
        "tradeFocus": ["Options"],
        "experienceLevel": "Learning",
        "riskStyle": "Balanced",
        "struggles": [],
        "reminders": [],
        "sectors": [],
        "marketCaps": [],
        "events": [],
        "safetyAccepted": True,
    }


def sync_user(clerk_id: str, email: str) -> dict[str, object]:
    response = client.post("/auth/clerk-sync", json=user_payload(clerk_id, email))
    assert response.status_code == 200
    return response.json()


def set_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://clerk.test/.well-known/jwks.json")
    monkeypatch.setattr(settings, "clerk_issuer", "https://clerk.test")
    monkeypatch.setattr(settings, "clerk_authorized_parties", [])


def set_development(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")


def token_for(monkeypatch, clerk_id: str):
    def fake_verify(token: str) -> auth_service.AuthIdentity:
        assert token == "valid-token"
        return auth_service.AuthIdentity(clerk_user_id=clerk_id, claims={"sub": clerk_id})

    monkeypatch.setattr(auth_service, "verify_clerk_session_token", fake_verify)
    return {"Authorization": "Bearer valid-token"}


def test_production_missing_token_rejected(monkeypatch):
    user = sync_user("clerk_missing_token", "auth-missing-token@example.com")
    set_production(monkeypatch)

    response = client.get(f"/saved-checks/{user['id']}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization bearer token is required."


def test_production_invalid_token_rejected(monkeypatch):
    user = sync_user("clerk_invalid_token", "auth-invalid-token@example.com")
    set_production(monkeypatch)

    def fake_verify(token: str) -> auth_service.AuthIdentity:
        raise HTTPException(status_code=401, detail="Invalid or expired Clerk session token.")

    monkeypatch.setattr(auth_service, "verify_clerk_session_token", fake_verify)
    response = client.get(f"/saved-checks/{user['id']}", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired Clerk session token."


def test_production_token_user_cannot_access_another_user(monkeypatch):
    owner = sync_user("clerk_owner_only", "auth-owner@example.com")
    sync_user("clerk_other_only", "auth-other@example.com")
    set_production(monkeypatch)
    headers = token_for(monkeypatch, "clerk_other_only")

    response = client.get(f"/saved-checks/{owner['id']}", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Authenticated user does not match this profile."


def test_production_valid_token_can_use_core_protected_routes(monkeypatch):
    user = sync_user("clerk_valid_core", "auth-valid-core@example.com")
    set_production(monkeypatch)
    headers = token_for(monkeypatch, "clerk_valid_core")

    profile = client.patch(
        f"/auth/users/{user['id']}/profile",
        json={"riskRules": {"maxRiskPerTrade": "1%"}},
        headers=headers,
    )
    assert profile.status_code == 200
    assert profile.json()["riskRules"]["maxRiskPerTrade"] == "1%"

    trade = client.post(
        "/trade-check",
        json={
            "user_id": user["id"],
            "ticker": "AAPL",
            "trade_type": "Long Call",
            "option_side": "call",
            "strike": 200,
            "expiration": "2099-01-17",
            "premium": 2.15,
            "contracts": 1,
            "amount_at_risk": 215,
            "timeframe": "Swing",
            "account_size": 25000,
        },
        headers=headers,
    )
    assert trade.status_code == 200
    report = trade.json()

    saved = client.post(
        "/saved-checks",
        json={"user_id": user["id"], "trade_check_id": report["id"], "report": report, "note": "production auth"},
        headers=headers,
    )
    assert saved.status_code == 200

    chat = client.post(
        "/chat",
        json={"user_id": user["id"], "message": "Explain the max loss on my selected check.", "current_report": report},
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["thread_id"]

    extraction = client.post(
        "/extract-contract",
        json={
            "user_id": user["id"],
            "attachments": [{"name": "contract.txt", "type": "text/plain", "text": "AAPL 200C 1/17/99 @ 2.15 Qty 1"}],
        },
        headers=headers,
    )
    assert extraction.status_code == 200
    assert extraction.json()["fields"]["ticker"] == "AAPL"

    delete = client.delete(f"/auth/users/{user['id']}", headers=headers)
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True


def test_development_mode_still_allows_without_clerk_token(monkeypatch):
    set_development(monkeypatch)
    user = sync_user("clerk_dev_no_token", "auth-dev-no-token@example.com")

    response = client.get(f"/saved-checks/{user['id']}")

    assert response.status_code == 200


def test_clerk_sync_requires_matching_session_in_production(monkeypatch):
    set_production(monkeypatch)
    headers = token_for(monkeypatch, "clerk_real_subject")

    response = client.post(
        "/auth/clerk-sync",
        json=user_payload("clerk_payload_subject", "auth-clerk-sync-mismatch@example.com"),
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Authenticated Clerk session does not match this profile."


def test_ready_accepts_deterministic_ai_fallback_for_personal_testflight(monkeypatch):
    set_production(monkeypatch)
    monkeypatch.setattr(settings, "sentry_dsn", "https://public@example.ingest.sentry.io/1")
    monkeypatch.setattr(settings, "llm_provider_order", ["fallback"])

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["market_data"]["fallback_available"] is True
    assert body["auth"]["configured"] is True
    serialized = str(body).lower()
    assert "secret" not in serialized
    assert "api_key" not in serialized
