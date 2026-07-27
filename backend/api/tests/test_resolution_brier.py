from datetime import date, timedelta

import pytest

from api.scripts.resolve_predictions import build_resolution, resolve_pending
from api.services.learning import brier_report
from api.services.learning.brier import brier_series
from api.services.store import DemoStore


def make_store_with_lock(*, expiration: str, direction: str = "bullish", breakeven: float = 105.0) -> tuple[DemoStore, dict]:
    store = DemoStore()
    item = store.save_check(
        "user_res",
        "check_res",
        {"ticker": "AAPL", "riskMath": {"breakeven": breakeven}},
        prediction_lock={
            "conviction_pct": 70,
            "direction": direction,
            "thesis_text": "test",
            "underlying_at_lock": 100.0,
            "breakeven": breakeven,
            "expiration": expiration,
            "locked_at": (date.today() - timedelta(days=40)).isoformat() + "T00:00:00+00:00",
        },
    )
    return store, item


def bars(days_ago_range: tuple[int, int], high: float, low: float, close: float) -> list[dict]:
    start, end = days_ago_range
    return [
        {"date": date.today() - timedelta(days=offset), "high": high, "low": low, "close": close}
        for offset in range(start, end - 1, -1)
    ]


def test_resolves_expired_bullish_lock_as_hit() -> None:
    expiration = (date.today() - timedelta(days=5)).isoformat()
    store, item = make_store_with_lock(expiration=expiration)
    history = bars((30, 5), high=112.0, low=98.0, close=110.0)
    summary = resolve_pending(store, fetch_history=lambda ticker, start, end: history)
    assert summary["resolved"] == 1
    stored = store.get_saved_check("user_res", item["id"])
    resolution = stored["resolution"]
    assert resolution["status"] == "resolved"
    assert resolution["underlying_at_expiry"] == 110.0
    assert resolution["touched_breakeven"] is True
    assert resolution["hit"] is True
    assert resolution["resolved_at"]


def test_bearish_lock_touch_and_miss_are_direction_aware() -> None:
    window = [
        {"date": date.today() - timedelta(days=10), "high": 108.0, "low": 94.0, "close": 107.0},
        {"date": date.today() - timedelta(days=6), "high": 109.0, "low": 99.0, "close": 108.0},
    ]
    resolution = build_resolution(
        {"direction": "bearish", "breakeven": 95.0},
        window,
    )
    # Price dipped through the breakeven price intraday (touch) but finished above it (no hit).
    assert resolution["touched_breakeven"] is True
    assert resolution["hit"] is False


def test_unexpired_locks_are_left_pending() -> None:
    expiration = (date.today() + timedelta(days=10)).isoformat()
    store, item = make_store_with_lock(expiration=expiration)
    summary = resolve_pending(store, fetch_history=lambda ticker, start, end: [])
    assert summary["resolved"] == 0
    assert summary["skipped_not_expired"] == 1
    assert store.get_saved_check("user_res", item["id"])["resolution"]["status"] == "pending"


def test_missing_history_never_fabricates_a_resolution() -> None:
    expiration = (date.today() - timedelta(days=5)).isoformat()
    store, item = make_store_with_lock(expiration=expiration)
    summary = resolve_pending(store, fetch_history=lambda ticker, start, end: [])
    assert summary["resolved"] == 0
    assert summary["skipped_no_data"] == 1
    assert store.get_saved_check("user_res", item["id"])["resolution"]["status"] == "pending"


def test_missing_breakeven_resolves_price_but_not_hit() -> None:
    resolution = build_resolution({"direction": "bullish", "breakeven": None}, bars((10, 5), 110, 100, 105))
    assert resolution["status"] == "resolved"
    assert resolution["underlying_at_expiry"] == 105
    assert resolution["touched_breakeven"] is None
    assert resolution["hit"] is None


# --- Brier scoring ---


def resolved_item(conviction: float, pop: float, hit: bool) -> dict:
    return {
        "prediction_lock": {"conviction_pct": conviction},
        "report": {"probability": {"p_profit": pop}},
        "resolution": {"status": "resolved", "hit": hit},
    }


def test_brier_series_math_matches_hand_computation() -> None:
    pairs = [(0.7, 1.0), (0.7, 0.0), (0.2, 0.0), (0.9, 1.0)] * 3  # 12 samples
    series = brier_series(pairs, "user_conviction")
    assert series["status"] == "ok"
    # ((0.3^2 + 0.7^2 + 0.2^2 + 0.1^2) * 3) / 12 = 0.1575
    assert series["brier_score"] == pytest.approx(0.1575, abs=1e-9)
    assert series["mean_probability"] == pytest.approx(0.625, abs=1e-9)
    assert series["realized_rate"] == pytest.approx(0.5, abs=1e-9)


def test_brier_report_keeps_user_and_model_series_separate_and_surfaces_gap() -> None:
    items = [resolved_item(80, 0.65, hit=True) for _ in range(6)] + [
        resolved_item(80, 0.65, hit=False) for _ in range(6)
    ]
    report = brier_report(items)
    assert report["status"] == "ok"
    assert report["user_conviction"]["n"] == 12
    assert report["model_pop"]["n"] == 12
    assert report["user_conviction"]["brier_score"] != report["model_pop"]["brier_score"]
    gap = report["model_calibration"]
    # Model said 65% on average, realized 50% -> ran 15 points high.
    assert gap["gap_percentage_points"] == pytest.approx(15.0, abs=0.01)
    assert "15.0 percentage points high" in gap["message"]


def test_brier_report_requires_real_history() -> None:
    items = [resolved_item(70, 0.6, hit=True) for _ in range(3)]
    report = brier_report(items)
    assert report["status"] == "insufficient_history"
    assert report["user_conviction"]["status"] == "insufficient_history"
    assert report["user_conviction"]["brier_score"] is None


def test_unresolved_and_hitless_items_are_excluded() -> None:
    items = [resolved_item(70, 0.6, hit=True) for _ in range(12)]
    items.append({"prediction_lock": {"conviction_pct": 50}, "report": {}, "resolution": {"status": "pending"}})
    items.append({"prediction_lock": {"conviction_pct": 50}, "report": {}, "resolution": {"status": "resolved", "hit": None}})
    report = brier_report(items)
    assert report["user_conviction"]["n"] == 12
