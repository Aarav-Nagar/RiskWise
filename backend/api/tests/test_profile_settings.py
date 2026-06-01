from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_profile_settings_are_saved_and_returned():
    email = "profile-settings@example.com"
    response = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": "clerk_profile_settings",
            "name": "Profile Tester",
            "email": email,
            "accountSize": 25000,
            "riskBudgetPercent": 2,
            "purpose": ["Learn"],
            "tradeFocus": ["Options"],
            "experienceLevel": "Learning",
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
    user = response.json()

    update = client.patch(
        f"/auth/users/{user['id']}/profile",
        json={
            "name": "Updated Tester",
            "accountSize": 40000,
            "riskBudgetPercent": 1.5,
            "experienceLevel": "Advanced",
            "riskStyle": "Conservative",
            "sectors": ["Tech", "Finance"],
            "struggles": ["Oversizing"],
            "aiMemory": {
                "experienceLevel": "Advanced",
                "riskStyle": "Conservative",
                "explanationStyle": "Quant",
                "sectors": ["Tech", "Finance"],
                "mistakes": ["Oversizing"],
            },
            "riskRules": {
                "maxRiskPerTrade": "1%",
                "maxTradesPerWeek": "2",
                "avoidEarnings": True,
                "warnShortExpiry": True,
                "warnPremiumRisk": True,
                "premiumRiskLimit": "2%",
            },
            "coachStyle": {
                "simple": False,
                "quantHeavy": True,
                "debateBothSides": True,
                "askQuestionsFirst": True,
                "strictRisk": True,
            },
            "savedContext": {
                "savedChecks": True,
                "chatHistory": False,
                "uploadedScreenshots": True,
                "watchlist": True,
            },
            "appPreferences": {
                "defaultMode": "Compare",
                "openAppTo": "Coach",
                "compactReports": False,
                "weeklyDigest": True,
                "quietHours": "After 10 PM",
            },
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["name"] == "Updated Tester"
    assert updated["accountSize"] == 40000
    assert updated["riskBudgetPercent"] == 1.5
    assert updated["aiMemory"]["explanationStyle"] == "Quant"
    assert updated["riskRules"]["avoidEarnings"] is True
    assert updated["coachStyle"]["askQuestionsFirst"] is True
    assert updated["savedContext"]["chatHistory"] is False
    assert updated["appPreferences"]["defaultMode"] == "Compare"

    lookup = client.get(f"/auth/profile-by-email?email={email}")
    assert lookup.status_code == 200
    restored = lookup.json()
    assert restored["experienceLevel"] == "Advanced"
    assert restored["sectors"] == ["Tech", "Finance"]
    assert restored["aiMemory"]["mistakes"] == ["Oversizing"]
    assert restored["appPreferences"]["compactReports"] is False


def test_clear_context_keeps_profile_but_removes_analysis_memory():
    email = "clear-context@example.com"
    response = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": "clerk_clear_context",
            "name": "Context Tester",
            "email": email,
            "accountSize": 18000,
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
            "savedContext": {
                "savedChecks": True,
                "chatHistory": True,
                "uploadedScreenshots": True,
                "watchlist": True,
            },
        },
    )
    assert response.status_code == 200
    user = response.json()

    saved = client.post(
        "/saved-checks",
        json={
            "user_id": user["id"],
            "trade_check_id": "check_clear_context",
            "report": {"ticker": "MSFT", "riskPosture": "Mixed"},
            "note": "remove me",
        },
    )
    assert saved.status_code == 200

    chat = client.post(
        "/chat",
        json={
            "user_id": user["id"],
            "message": "What is theta?",
            "thread_id": "thread_clear_context",
        },
    )
    assert chat.status_code == 200

    clear = client.delete(f"/auth/users/{user['id']}/context")
    assert clear.status_code == 200
    assert clear.json()["cleared"] is True

    lookup = client.get(f"/auth/profile-by-email?email={email}")
    assert lookup.status_code == 200
    restored = lookup.json()
    assert restored["name"] == "Context Tester"
    assert restored["savedContext"] == {
        "savedChecks": False,
        "chatHistory": False,
        "uploadedScreenshots": False,
        "watchlist": False,
    }

    saved_after = client.get(f"/saved-checks/{user['id']}")
    assert saved_after.status_code == 200
    assert saved_after.json() == []


def test_delete_user_removes_profile_and_saved_context():
    email = "delete-me@example.com"
    response = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": "clerk_delete_me",
            "name": "Delete Tester",
            "email": email,
            "accountSize": 10000,
            "riskBudgetPercent": 1,
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
        },
    )
    assert response.status_code == 200
    user = response.json()

    saved = client.post(
        "/saved-checks",
        json={
            "user_id": user["id"],
            "trade_check_id": "check_delete_me",
            "report": {"ticker": "AAPL", "riskPosture": "Mixed"},
            "note": "temporary note",
        },
    )
    assert saved.status_code == 200

    delete_response = client.delete(f"/auth/users/{user['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    lookup = client.get(f"/auth/profile-by-email?email={email}")
    assert lookup.status_code == 404

    saved_after = client.get(f"/saved-checks/{user['id']}")
    assert saved_after.status_code == 200
    assert saved_after.json() == []


def test_saved_checks_require_signed_in_profile():
    response = client.post(
        "/saved-checks",
        json={"user_id": "", "trade_check_id": "bad", "report": {"ticker": "AAPL"}, "note": ""},
    )

    assert response.status_code == 422 or response.status_code == 401
