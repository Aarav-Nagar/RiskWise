from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api import app as app_module
from api.app import app
from api.settings import settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_rate_limit_state():
    app_module._rate_limit_hits.clear()
    yield
    app_module._rate_limit_hits.clear()


def test_ai_smoke_is_rate_limited(monkeypatch):
    # /ai/smoke takes no auth and runs four LLM prompts per call, so an
    # unlimited endpoint is a free way to drain the provider quota.
    monkeypatch.setattr(settings, "rate_limit_ai_smoke", 2)

    assert client.get("/ai/smoke").status_code == 200
    assert client.get("/ai/smoke").status_code == 200

    limited = client.get("/ai/smoke")
    assert limited.status_code == 429, limited.text


def test_ai_providers_is_not_rate_limited(monkeypatch):
    # /ai/providers is cheap and read-only - it must not share the smoke budget,
    # since it is how you diagnose a provider after being told to slow down.
    monkeypatch.setattr(settings, "rate_limit_ai_smoke", 1)

    for _ in range(4):
        assert client.get("/ai/providers").status_code == 200


def test_rate_limited_response_is_a_clean_429(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_ai_smoke", 1)

    client.get("/ai/smoke")
    limited = client.get("/ai/smoke")

    assert limited.status_code == 429
    assert limited.headers.get("content-type", "").startswith("application/json")
    assert limited.json()


def test_health_and_ready_are_never_rate_limited(monkeypatch):
    # Render polls these; throttling them would fail the health check.
    monkeypatch.setattr(settings, "rate_limit_ai_smoke", 1)

    for _ in range(6):
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200


def test_limits_are_tracked_per_path_not_globally(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_ai_smoke", 1)

    assert client.get("/ai/smoke").status_code == 200
    assert client.get("/ai/smoke").status_code == 429
    # A different limited prefix keeps its own budget.
    assert client.get("/market/providers").status_code == 200


def test_ai_smoke_default_budget_is_tight():
    # A generous default would defeat the point; keep this honest if it changes.
    assert settings.rate_limit_ai_smoke <= 10
