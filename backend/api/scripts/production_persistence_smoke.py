from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.services.store import MongoStore  # noqa: E402


def payload(clerk_id: str, email: str) -> SimpleNamespace:
    return SimpleNamespace(
        clerkId=clerk_id,
        name="Mongo Smoke Tester",
        email=email,
        accountSize=25000,
        riskBudgetPercent=2,
        purpose=["Production persistence proof"],
        tradeFocus=["Options"],
        experienceLevel="Learning",
        riskStyle="Balanced",
        struggles=[],
        reminders=[],
        sectors=[],
        marketCaps=[],
        events=[],
        safetyAccepted=True,
        aiMemory={},
        riskRules={},
        coachStyle={},
        savedContext={"savedChecks": True, "chatHistory": True, "uploadedScreenshots": True, "watchlist": True},
        appPreferences={},
    )


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    if not os.getenv("MONGODB_URI") or not os.getenv("MONGODB_DATABASE"):
        print("SKIP: MONGODB_URI and MONGODB_DATABASE are required for the production persistence smoke.")
        return 0

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    clerk_id = f"clerk_smoke_{suffix}"
    email = f"mongo-smoke-{suffix}@riskwise.local"
    smoke = MongoStore()

    user = smoke.sync_clerk_user(payload(clerk_id, email))
    user_id = user["id"]
    try:
        updated = smoke.update_user_profile(
            user_id,
            {
                "name": "Mongo Smoke Updated",
                "riskRules": {"maxRiskPerTrade": "1%"},
                "coachStyle": {"simple": True, "strictRisk": True},
                "aiMemory": {"experienceLevel": "Learning", "mistakes": ["oversizing"]},
            },
        )
        assert_true(updated["name"] == "Mongo Smoke Updated", "profile edit did not persist")
        assert_true(updated["riskRules"]["maxRiskPerTrade"] == "1%", "risk rules did not persist")

        report = {"id": f"check_{suffix}", "ticker": "AAPL", "riskPosture": "Mixed", "riskMath": {"max_loss": 215}}
        smoke.save_trade_check(user_id, {"ticker": "AAPL", "premium": 2.15}, report)
        saved = smoke.save_check(user_id, report["id"], report, "mongo smoke saved check")
        assert_true(saved["report"]["ticker"] == "AAPL", "saved check did not persist")

        thread_id = smoke.append_chat(
            user_id,
            None,
            "Review this uploaded contract",
            "Max loss is premium times multiplier times contracts.",
            mode="Review",
            attachments=[{"name": "contract.txt", "type": "text/plain", "text": "AAPL 200C 1/17/2099 @ 2.15"}],
        )
        assert_true(len(smoke.list_chat_messages(user_id, thread_id)) == 2, "chat messages did not persist")

        smoke.save_upload(
            user_id,
            "smoke_upload",
            [
                {
                    "name": "broker-screenshot.png",
                    "type": "image/png",
                    "source": "camera",
                    "dataUrl": "data:image/png;base64,RAW_SCREENSHOT_SHOULD_NOT_PERSIST",
                    "text": "AAPL 200C 1/17/2099 @ 2.15",
                }
            ],
            {
                "status": "ok",
                "provider": "text-parser",
                "fields": {"ticker": "AAPL", "premium": "2.15"},
                "missing_fields": [],
                "missing_live_fields": ["bid", "ask", "impliedVolatility", "openInterest", "contractVolume", "Greeks"],
            },
        )
        upload = smoke.db.uploads.find_one({"userId": user_id})
        assert_true(upload is not None, "upload metadata did not persist")
        assert_true("dataUrl" not in str(upload), "raw screenshot data was persisted")
        assert_true(upload["attachments"][0]["hasImage"] is True, "compact upload image flag missing")

        feedback = smoke.save_chat_feedback(
            SimpleNamespace(
                user_id=user_id,
                thread_id=thread_id,
                message="Bad answer?",
                answer="Prior answer",
                reason="smoke",
                expected="Better specificity",
                metadata={"source": "mongo_smoke"},
            )
        )
        assert_true(feedback["userId"] == user_id, "feedback did not persist")

        summary = smoke.context_summary(user_id)
        assert_true(summary["savedChecks"] >= 1, "context summary missed saved checks")
        assert_true(summary["chatThreads"] >= 1, "context summary missed chat threads")
        assert_true(summary["chatMessages"] >= 2, "context summary missed chat messages")
        assert_true(summary["uploadedScreenshots"] >= 1, "context summary missed upload metadata")

        deleted = smoke.delete_user(user_id)
        assert_true(deleted["deleted"] is True, "delete account did not report success")
        assert_true(smoke.find_user_by_email(email) is None, "user profile remained after delete")
        assert_true(smoke.list_saved_checks(user_id) == [], "saved checks remained after delete")
        assert_true(smoke.list_chat_threads(user_id) == [], "chat threads remained after delete")
        assert_true(smoke.db.uploads.count_documents({"userId": user_id}) == 0, "uploads remained after delete")
        assert_true(smoke.db.chat_feedback.count_documents({"userId": user_id}) == 0, "feedback remained after delete")
        assert_true(smoke.db.deletion_records.find_one({"userId": user_id}) is not None, "deletion record was not retained")
    except Exception:
        try:
            if smoke.get_user(user_id):
                smoke.delete_user(user_id)
        finally:
            raise

    print(f"PASS: Mongo persistence smoke completed for {user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
