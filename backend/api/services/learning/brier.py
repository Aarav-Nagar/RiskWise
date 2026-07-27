"""Brier scoring over resolved prediction locks.

Two separate series, reported separately and never blended:
- user conviction (prediction_lock.conviction_pct / 100) vs realized outcome
- model POP (the api.probability p_profit captured on the saved report) vs
  realized outcome

The gap between the model's average stated probability and the realized hit
rate is surfaced directly, e.g. "the model's probability display has run 12.0
percentage points high against realized outcomes." This only means something
with real usage history, so anything under MIN_HISTORY resolved checks is
reported as insufficient_history rather than pretending to be a calibration
read.
"""

from __future__ import annotations

import math
from typing import Any

MIN_HISTORY = 10


def brier_report(resolved_checks: list[dict[str, Any]]) -> dict[str, Any]:
    user_pairs: list[tuple[float, float]] = []
    model_pairs: list[tuple[float, float]] = []
    for item in resolved_checks:
        resolution = item.get("resolution") or {}
        if resolution.get("status") != "resolved" or resolution.get("hit") is None:
            continue
        outcome = 1.0 if resolution.get("hit") else 0.0
        conviction = finite_number((item.get("prediction_lock") or {}).get("conviction_pct"))
        if conviction is not None and 0 <= conviction <= 100:
            user_pairs.append((conviction / 100.0, outcome))
        pop = model_pop(item)
        if pop is not None and 0.0 <= pop <= 1.0:
            model_pairs.append((pop, outcome))

    user_series = brier_series(user_pairs, "user_conviction")
    model_series = brier_series(model_pairs, "model_pop")
    calibration = model_calibration(model_series)
    return {
        "status": "ok" if user_series["status"] == "ok" or model_series["status"] == "ok" else "insufficient_history",
        "min_history": MIN_HISTORY,
        "user_conviction": user_series,
        "model_pop": model_series,
        "model_calibration": calibration,
        "message": calibration.get("message")
        or "Not enough resolved prediction locks yet for a meaningful Brier comparison.",
    }


def brier_series(pairs: list[tuple[float, float]], name: str) -> dict[str, Any]:
    if len(pairs) < MIN_HISTORY:
        return {
            "name": name,
            "status": "insufficient_history",
            "n": len(pairs),
            "brier_score": None,
            "mean_probability": None,
            "realized_rate": None,
        }
    n = len(pairs)
    brier = sum((probability - outcome) ** 2 for probability, outcome in pairs) / n
    return {
        "name": name,
        "status": "ok",
        "n": n,
        "brier_score": round(brier, 4),
        "mean_probability": round(sum(probability for probability, _ in pairs) / n, 4),
        "realized_rate": round(sum(outcome for _, outcome in pairs) / n, 4),
    }


def model_calibration(model_series: dict[str, Any]) -> dict[str, Any]:
    if model_series["status"] != "ok":
        return {"status": "insufficient_history", "gap_percentage_points": None, "message": ""}
    gap = (model_series["mean_probability"] - model_series["realized_rate"]) * 100
    direction = "high" if gap > 0 else "low"
    return {
        "status": "ok",
        "gap_percentage_points": round(gap, 2),
        "message": (
            f"The model's probability display has run {abs(round(gap, 1))} percentage points {direction} "
            f"against realized outcomes over {model_series['n']} resolved checks."
        ),
    }


def model_pop(item: dict[str, Any]) -> float | None:
    """Model POP at lock time: report.probability.p_profit (saved with the check),
    with prediction_lock.model_pop accepted as an explicit override."""
    report = item.get("report") or {}
    probability = report.get("probability") if isinstance(report.get("probability"), dict) else {}
    pop = finite_number(probability.get("p_profit"))
    if pop is None:
        pop = finite_number((item.get("prediction_lock") or {}).get("model_pop"))
    return pop


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
