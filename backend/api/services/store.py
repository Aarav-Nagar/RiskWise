from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from api.settings import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def clean_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    next_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), next_salt.encode("utf-8"), 120_000)
    return digest.hex(), next_salt


def profile_from_signup(payload: Any) -> dict[str, Any]:
    return {
        "accountSize": float(payload.accountSize),
        "riskBudgetPercent": float(payload.riskBudgetPercent),
        "purpose": payload.purpose,
        "tradeFocus": payload.tradeFocus,
        "experienceLevel": payload.experienceLevel,
        "riskStyle": payload.riskStyle,
        "struggles": payload.struggles,
        "reminders": payload.reminders,
        "sectors": payload.sectors,
        "marketCaps": payload.marketCaps,
        "events": payload.events,
        "safetyAccepted": bool(payload.safetyAccepted),
        "aiMemory": getattr(payload, "aiMemory", {}) or {},
        "riskRules": getattr(payload, "riskRules", {}) or {},
        "coachStyle": getattr(payload, "coachStyle", {}) or {},
        "savedContext": getattr(payload, "savedContext", {}) or {},
        "appPreferences": getattr(payload, "appPreferences", {}) or {},
    }


class DemoStore:
    """Development-only in-memory store. No user data is persisted to disk."""

    provider = "demo"

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.users_by_email: dict[str, str] = {}
        self.trade_checks: dict[str, dict[str, Any]] = {}
        self.saved_checks_by_user: dict[str, list[dict[str, Any]]] = {}
        self.chat_threads: dict[str, dict[str, Any]] = {}
        self.chat_messages: dict[str, list[dict[str, Any]]] = {}
        self.chat_feedback: list[dict[str, Any]] = []

    def create_user(self, payload: Any) -> dict[str, Any]:
        email = clean_email(payload.email)
        if email in self.users_by_email:
            raise ValueError("An account with this email already exists.")
        password_hash, salt = hash_password(payload.password)
        user = {
            "id": make_id("user"),
            "name": payload.name.strip(),
            "email": email,
            **profile_from_signup(payload),
            "createdAt": utc_now(),
        }
        self.users[user["id"]] = {**user, "passwordHash": password_hash, "salt": salt}
        self.users_by_email[email] = user["id"]
        return user

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        user_id = self.users_by_email.get(clean_email(email))
        if not user_id:
            raise ValueError("Email or password did not match an account.")
        record = self.users[user_id]
        password_hash, _salt = hash_password(password, record["salt"])
        if password_hash != record["passwordHash"]:
            raise ValueError("Email or password did not match an account.")
        return public_user(record)

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        user_id = self.users_by_email.get(clean_email(email))
        return public_user(self.users[user_id]) if user_id else None

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        record = self.users.get(user_id)
        return public_user(record) if record else None

    def update_user_profile(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        if user_id not in self.users:
            raise ValueError("User profile was not found.")
        safe_updates = profile_update_fields(updates)
        self.users[user_id].update(safe_updates)
        self.users[user_id]["updatedAt"] = utc_now()
        return public_user(self.users[user_id])

    def delete_user(self, user_id: str) -> dict[str, Any]:
        record = self.users.pop(user_id, None)
        if not record:
            raise ValueError("User profile was not found.")
        email = record.get("email")
        if email:
            self.users_by_email.pop(email, None)
        self.saved_checks_by_user.pop(user_id, None)
        self.trade_checks = {key: value for key, value in self.trade_checks.items() if value.get("userId") != user_id}
        owned_threads = [thread_id for thread_id, row in self.chat_threads.items() if row.get("userId") == user_id]
        for thread_id in owned_threads:
            self.chat_threads.pop(thread_id, None)
            self.chat_messages.pop(thread_id, None)
        self.chat_feedback = [row for row in self.chat_feedback if row.get("userId") != user_id]
        return {"deleted": True, "userId": user_id, "deletedAt": utc_now()}

    def clear_user_context(self, user_id: str) -> dict[str, Any]:
        if user_id not in self.users:
            raise ValueError("User profile was not found.")
        self.saved_checks_by_user.pop(user_id, None)
        self.trade_checks = {key: value for key, value in self.trade_checks.items() if value.get("userId") != user_id}
        owned_threads = [thread_id for thread_id, row in self.chat_threads.items() if row.get("userId") == user_id]
        for thread_id in owned_threads:
            self.chat_threads.pop(thread_id, None)
            self.chat_messages.pop(thread_id, None)
        self.chat_feedback = [row for row in self.chat_feedback if row.get("userId") != user_id]
        self.users[user_id]["savedContext"] = {
            "savedChecks": False,
            "chatHistory": False,
            "uploadedScreenshots": False,
            "watchlist": False,
        }
        self.users[user_id]["updatedAt"] = utc_now()
        return {"cleared": True, "userId": user_id, "clearedAt": utc_now()}

    def sync_clerk_user(self, payload: Any) -> dict[str, Any]:
        email = clean_email(payload.email)
        existing = self.find_user_by_email(email)
        profile = {
            "clerkId": payload.clerkId,
            "name": payload.name.strip(),
            "email": email,
            **profile_from_signup(payload),
        }
        if existing:
            record = self.users[existing["id"]]
            record.update(profile)
            return public_user(record)
        user = {"id": make_id("user"), **profile, "createdAt": utc_now()}
        self.users[user["id"]] = user
        self.users_by_email[email] = user["id"]
        return public_user(user)

    def save_trade_check(self, user_id: str | None, request: dict[str, Any], response: dict[str, Any]) -> None:
        self.trade_checks[response["id"]] = {
            "id": response["id"],
            "userId": user_id,
            "request": request,
            "response": response,
            "createdAt": utc_now(),
        }

    def save_check(self, user_id: str, trade_check_id: str | None, report: dict[str, Any], note: str = "") -> dict[str, Any]:
        item = {
            "id": make_id("saved"),
            "userId": user_id,
            "tradeCheckId": trade_check_id,
            "report": report,
            "note": note,
            "createdAt": utc_now(),
        }
        self.saved_checks_by_user.setdefault(user_id, []).insert(0, item)
        return item

    def list_saved_checks(self, user_id: str) -> list[dict[str, Any]]:
        return self.saved_checks_by_user.get(user_id, [])

    def append_chat(
        self,
        user_id: str,
        thread_id: str | None,
        user_message: str,
        assistant_message: str,
        *,
        mode: str = "Explain",
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        next_thread_id = thread_id or make_id("thread")
        now = utc_now()
        thread = self.chat_threads.setdefault(
            next_thread_id,
            {"id": next_thread_id, "userId": user_id, "title": chat_title(user_message), "mode": mode, "createdAt": now, "messageCount": 0},
        )
        thread["updatedAt"] = now
        thread["mode"] = mode
        thread["messageCount"] = int(thread.get("messageCount") or 0) + 2
        self.chat_messages.setdefault(next_thread_id, []).extend(
            [
                {
                    "id": make_id("msg"),
                    "threadId": next_thread_id,
                    "userId": user_id,
                    "role": "user",
                    "content": user_message,
                    "mode": mode,
                    "attachments": attachments or [],
                    "createdAt": utc_now(),
                },
                {
                    "id": make_id("msg"),
                    "threadId": next_thread_id,
                    "userId": user_id,
                    "role": "assistant",
                    "content": assistant_message,
                    "mode": mode,
                    "attachments": [],
                    "createdAt": utc_now(),
                },
            ]
        )
        return next_thread_id

    def list_chat_threads(self, user_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.chat_threads.values() if row.get("userId") == user_id]
        return sorted(rows, key=lambda row: row.get("updatedAt") or row.get("createdAt") or "", reverse=True)[:20]

    def list_chat_messages(self, user_id: str, thread_id: str) -> list[dict[str, Any]]:
        thread = self.chat_threads.get(thread_id)
        if not thread or thread.get("userId") != user_id:
            return []
        return self.chat_messages.get(thread_id, [])

    def save_chat_feedback(self, payload: Any) -> dict[str, Any]:
        item = {
            "id": make_id("feedback"),
            "userId": payload.user_id,
            "threadId": payload.thread_id,
            "message": payload.message,
            "answer": payload.answer,
            "reason": payload.reason,
            "expected": payload.expected,
            "metadata": payload.metadata,
            "createdAt": utc_now(),
        }
        self.chat_feedback.append(item)
        return item

    def status(self) -> dict[str, Any]:
        return {"provider": self.provider, "ready": True, "database": "memory"}


class MongoStore(DemoStore):
    """MongoDB Atlas storage adapter with the same interface as DemoStore."""

    provider = "mongo"

    def __init__(self) -> None:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is required when APP_STORAGE_PROVIDER=mongo.")
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise RuntimeError("Install pymongo to use MongoDB storage.") from exc
        self.client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
        )
        self.db = self.client[settings.mongodb_database]
        self.client.admin.command("ping")
        self.db.users.create_index("email", unique=True)
        self.db.users.create_index("clerkId", unique=True, sparse=True)
        self.db.chat_threads.create_index([("userId", 1), ("updatedAt", -1)])
        self.db.chat_messages.create_index([("threadId", 1), ("createdAt", 1)])
        self.db.saved_checks.create_index([("userId", 1), ("createdAt", -1)])
        self.db.chat_feedback.create_index([("userId", 1), ("createdAt", -1)])

    def create_user(self, payload: Any) -> dict[str, Any]:
        email = clean_email(payload.email)
        if self.db.users.find_one({"email": email}):
            raise ValueError("An account with this email already exists.")
        password_hash, salt = hash_password(payload.password)
        user = {
            "id": make_id("user"),
            "name": payload.name.strip(),
            "email": email,
            **profile_from_signup(payload),
            "createdAt": utc_now(),
            "passwordHash": password_hash,
            "salt": salt,
        }
        self.db.users.insert_one(user)
        return public_user(user)

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        record = self.db.users.find_one({"email": clean_email(email)})
        if not record:
            raise ValueError("Email or password did not match an account.")
        password_hash, _salt = hash_password(password, record["salt"])
        if password_hash != record["passwordHash"]:
            raise ValueError("Email or password did not match an account.")
        return public_user(record)

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        record = self.db.users.find_one({"email": clean_email(email)})
        return public_user(record) if record else None

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        record = self.db.users.find_one({"id": user_id})
        return public_user(record) if record else None

    def update_user_profile(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        from pymongo import ReturnDocument

        safe_updates = profile_update_fields(updates)
        safe_updates["updatedAt"] = utc_now()
        result = self.db.users.find_one_and_update(
            {"id": user_id},
            {"$set": safe_updates},
            return_document=ReturnDocument.AFTER,
        )
        if not result:
            raise ValueError("User profile was not found.")
        return public_user(result)

    def delete_user(self, user_id: str) -> dict[str, Any]:
        record = self.db.users.find_one_and_delete({"id": user_id})
        if not record:
            raise ValueError("User profile was not found.")
        self.db.saved_checks.delete_many({"userId": user_id})
        self.db.trade_checks.delete_many({"userId": user_id})
        thread_ids = [row["id"] for row in self.db.chat_threads.find({"userId": user_id}, {"id": 1})]
        self.db.chat_threads.delete_many({"userId": user_id})
        self.db.chat_messages.delete_many({"userId": user_id})
        if thread_ids:
            self.db.chat_messages.delete_many({"threadId": {"$in": thread_ids}})
        self.db.chat_feedback.delete_many({"userId": user_id})
        return {"deleted": True, "userId": user_id, "deletedAt": utc_now()}

    def clear_user_context(self, user_id: str) -> dict[str, Any]:
        from pymongo import ReturnDocument

        if not self.db.users.find_one({"id": user_id}, {"id": 1}):
            raise ValueError("User profile was not found.")
        self.db.saved_checks.delete_many({"userId": user_id})
        self.db.trade_checks.delete_many({"userId": user_id})
        thread_ids = [row["id"] for row in self.db.chat_threads.find({"userId": user_id}, {"id": 1})]
        self.db.chat_threads.delete_many({"userId": user_id})
        self.db.chat_messages.delete_many({"userId": user_id})
        if thread_ids:
            self.db.chat_messages.delete_many({"threadId": {"$in": thread_ids}})
        self.db.chat_feedback.delete_many({"userId": user_id})
        self.db.users.find_one_and_update(
            {"id": user_id},
            {
                "$set": {
                    "savedContext": {
                        "savedChecks": False,
                        "chatHistory": False,
                        "uploadedScreenshots": False,
                        "watchlist": False,
                    },
                    "updatedAt": utc_now(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return {"cleared": True, "userId": user_id, "clearedAt": utc_now()}

    def sync_clerk_user(self, payload: Any) -> dict[str, Any]:
        email = clean_email(payload.email)
        profile = {
            "clerkId": payload.clerkId,
            "name": payload.name.strip(),
            "email": email,
            **profile_from_signup(payload),
            "updatedAt": utc_now(),
        }
        existing = self.db.users.find_one({"$or": [{"email": email}, {"clerkId": payload.clerkId}]})
        if existing:
            self.db.users.update_one({"id": existing["id"]}, {"$set": profile})
            existing.update(profile)
            return public_user(existing)
        user = {"id": make_id("user"), **profile, "createdAt": utc_now()}
        self.db.users.insert_one(user)
        return public_user(user)

    def save_trade_check(self, user_id: str | None, request: dict[str, Any], response: dict[str, Any]) -> None:
        self.db.trade_checks.insert_one(
            {"id": response["id"], "userId": user_id, "request": request, "response": response, "createdAt": utc_now()}
        )

    def save_check(self, user_id: str, trade_check_id: str | None, report: dict[str, Any], note: str = "") -> dict[str, Any]:
        item = {
            "id": make_id("saved"),
            "userId": user_id,
            "tradeCheckId": trade_check_id,
            "report": report,
            "note": note,
            "createdAt": utc_now(),
        }
        self.db.saved_checks.insert_one(item)
        return public_document(item)

    def list_saved_checks(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.db.saved_checks.find({"userId": user_id}).sort("createdAt", -1).limit(10)
        return [public_document(row) for row in rows]

    def append_chat(
        self,
        user_id: str,
        thread_id: str | None,
        user_message: str,
        assistant_message: str,
        *,
        mode: str = "Explain",
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        next_thread_id = thread_id or make_id("thread")
        now = utc_now()
        self.db.chat_threads.update_one(
            {"id": next_thread_id},
            {
                "$setOnInsert": {"id": next_thread_id, "userId": user_id, "title": chat_title(user_message), "createdAt": now},
                "$set": {"updatedAt": now, "mode": mode},
                "$inc": {"messageCount": 2},
            },
            upsert=True,
        )
        self.db.chat_messages.insert_many(
            [
                {
                    "id": make_id("msg"),
                    "threadId": next_thread_id,
                    "userId": user_id,
                    "role": "user",
                    "content": user_message,
                    "mode": mode,
                    "attachments": attachments or [],
                    "createdAt": utc_now(),
                },
                {
                    "id": make_id("msg"),
                    "threadId": next_thread_id,
                    "userId": user_id,
                    "role": "assistant",
                    "content": assistant_message,
                    "mode": mode,
                    "attachments": [],
                    "createdAt": utc_now(),
                },
            ]
        )
        return next_thread_id

    def list_chat_threads(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.db.chat_threads.find({"userId": user_id}).sort("updatedAt", -1).limit(20)
        return [public_document(row) for row in rows]

    def list_chat_messages(self, user_id: str, thread_id: str) -> list[dict[str, Any]]:
        thread = self.db.chat_threads.find_one({"id": thread_id, "userId": user_id})
        if not thread:
            return []
        rows = self.db.chat_messages.find({"threadId": thread_id, "userId": user_id}).sort("createdAt", 1)
        return [public_document(row) for row in rows]

    def save_chat_feedback(self, payload: Any) -> dict[str, Any]:
        item = {
            "id": make_id("feedback"),
            "userId": payload.user_id,
            "threadId": payload.thread_id,
            "message": payload.message,
            "answer": payload.answer,
            "reason": payload.reason,
            "expected": payload.expected,
            "metadata": payload.metadata,
            "createdAt": utc_now(),
        }
        self.db.chat_feedback.insert_one(item)
        return public_document(item)

    def status(self) -> dict[str, Any]:
        try:
            self.client.admin.command("ping")
            ready = True
            message = "connected"
        except Exception as exc:
            ready = False
            message = exc.__class__.__name__
        return {"provider": self.provider, "ready": ready, "database": settings.mongodb_database, "message": message}


def public_user(record: dict[str, Any]) -> dict[str, Any]:
    private_keys = {"passwordHash", "salt"}
    return {key: value for key, value in record.items() if key not in private_keys and key != "_id"}


def public_document(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "_id"}


def profile_update_fields(updates: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "experienceLevel",
        "name",
        "accountSize",
        "riskBudgetPercent",
        "purpose",
        "tradeFocus",
        "riskStyle",
        "struggles",
        "reminders",
        "sectors",
        "marketCaps",
        "events",
        "safetyAccepted",
        "aiMemory",
        "riskRules",
        "coachStyle",
        "savedContext",
        "appPreferences",
    }
    return {key: value for key, value in updates.items() if key in allowed}


def chat_title(message: str) -> str:
    clean = " ".join((message or "Options question").strip().split())
    if len(clean) <= 44:
        return clean or "Options question"
    return f"{clean[:43].rstrip()}..."


def build_store() -> DemoStore:
    if settings.storage_provider == "mongo":
        try:
            return MongoStore()
        except Exception as exc:
            print(f"MongoDB storage unavailable; using demo store for this run. Reason: {exc}")
            fallback = DemoStore()
            fallback.provider = "demo-fallback"
            return fallback
    return DemoStore()


store = build_store()
