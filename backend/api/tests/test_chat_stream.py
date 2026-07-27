"""The /chat/stream SSE endpoint must reveal exactly the same guard-approved answer /chat returns,
never a different or partially-streamed one (post-validation streaming)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


def _make_user(email: str, clerk_id: str) -> dict:
    resp = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": clerk_id, "name": "Stream Tester", "email": email,
            "accountSize": 20000, "riskBudgetPercent": 2, "purpose": ["Learn"],
            "tradeFocus": ["Options"], "experienceLevel": "Learning", "riskStyle": "Balanced",
            "struggles": [], "reminders": [], "sectors": [], "marketCaps": [], "events": [],
            "safetyAccepted": True,
        },
    )
    assert resp.status_code == 200
    return resp.json()


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event is not None:
            events.append((event, data))
    return events


def test_chat_stream_reassembles_to_the_validated_answer() -> None:
    user = _make_user("stream1@example.com", "clerk_stream_1")
    payload = {"user_id": user["id"], "message": "What is theta decay?"}

    plain = client.post("/chat", json=payload)
    assert plain.status_code == 200
    expected_answer = plain.json()["answer"]
    assert expected_answer

    streamed = client.post("/chat/stream", json=payload)
    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(streamed.text)

    kinds = [e for e, _ in events]
    assert kinds[0] == "meta"
    assert kinds[-1] == "done"

    meta = events[0][1]
    assert meta.get("thread_id")
    assert "summary_cards" in meta and "provider" in meta
    assert "answer" not in meta  # the answer arrives only as validated deltas

    reassembled = "".join(d["text"] for e, d in events if e == "delta")
    assert reassembled == expected_answer  # streamed text == guard-approved /chat answer
    assert events[-1][1]["thread_id"] == meta["thread_id"]


def test_chat_stream_persists_the_turn() -> None:
    user = _make_user("stream2@example.com", "clerk_stream_2")
    streamed = client.post("/chat/stream", json={"user_id": user["id"], "message": "Explain delta simply."})
    assert streamed.status_code == 200
    thread_id = _parse_sse(streamed.text)[0][1]["thread_id"]

    threads = client.get(f"/chat/threads/{user['id']}")
    assert threads.status_code == 200
    assert any(t.get("thread_id") == thread_id or t.get("id") == thread_id for t in threads.json())
