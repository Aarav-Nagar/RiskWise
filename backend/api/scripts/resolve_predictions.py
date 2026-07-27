"""Fill saved-check resolutions from historical EOD prices once trades expire.

Walks every saved check whose prediction_lock exists and whose resolution is
still pending, and for locks whose expiration has passed pulls free yfinance
daily bars to fill:
- underlying_at_expiry: last close on/before the expiration date
- touched_breakeven: whether any daily high (bullish) / low (bearish) crossed
  the locked breakeven PRICE during the hold window. This is price touch only
  — it is deliberately not a P&L statement (time value means touching the
  breakeven price is not the same as breakeven P&L).
- hit: whether the underlying finished past the locked breakeven at expiry in
  the locked direction.

Then prints the two Brier series (user conviction vs outcome, model POP vs
outcome) from services/learning/brier.py when enough history exists.

Run:  python api/scripts/resolve_predictions.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.services.learning import brier_report
from api.services.store import store as default_store


def yfinance_daily_history(ticker: str, start: date, end: date) -> list[dict[str, Any]]:
    """Free EOD bars: [{date, high, low, close}] sorted by date."""
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return []
    try:
        frame = yf.Ticker(ticker).history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), interval="1d")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        rows.append(
            {
                "date": date.fromisoformat(str(index)[:10]),
                "high": float(row.get("High")),
                "low": float(row.get("Low")),
                "close": float(row.get("Close")),
            }
        )
    return sorted(rows, key=lambda item: item["date"])


def resolve_pending(
    store: Any = default_store,
    *,
    today: date | None = None,
    fetch_history: Callable[[str, date, date], list[dict[str, Any]]] = yfinance_daily_history,
    dry_run: bool = False,
) -> dict[str, Any]:
    current = today or date.today()
    resolved, skipped_not_expired, skipped_no_data = 0, 0, 0
    details: list[dict[str, Any]] = []
    for item in store.list_pending_resolutions():
        lock = item.get("prediction_lock") or {}
        expiration = parse_date(lock.get("expiration"))
        if expiration is None or expiration >= current:
            skipped_not_expired += 1
            continue
        ticker = str((item.get("report") or {}).get("ticker") or "").upper()
        lock_date = parse_date(str(lock.get("locked_at") or "")[:10]) or expiration - timedelta(days=45)
        bars = fetch_history(ticker, lock_date, expiration) if ticker else []
        window = [bar for bar in bars if lock_date <= bar["date"] <= expiration]
        if not window:
            skipped_no_data += 1
            details.append({"id": item.get("id"), "ticker": ticker, "status": "no_price_history"})
            continue
        resolution = build_resolution(lock, window)
        details.append({"id": item.get("id"), "ticker": ticker, "status": "resolved", **resolution})
        if not dry_run:
            store.update_saved_check_resolution(item.get("userId"), item.get("id"), resolution)
        resolved += 1
    return {
        "resolved": resolved,
        "skipped_not_expired": skipped_not_expired,
        "skipped_no_data": skipped_no_data,
        "dry_run": dry_run,
        "details": details,
    }


def build_resolution(lock: dict[str, Any], window: list[dict[str, Any]]) -> dict[str, Any]:
    breakeven = to_number(lock.get("breakeven"))
    bullish = "bear" not in str(lock.get("direction") or "").lower()
    close_at_expiry = window[-1]["close"]
    touched: bool | None = None
    hit: bool | None = None
    if breakeven is not None:
        if bullish:
            touched = any(bar["high"] >= breakeven for bar in window)
            hit = close_at_expiry > breakeven
        else:
            touched = any(bar["low"] <= breakeven for bar in window)
            hit = close_at_expiry < breakeven
    return {
        "status": "resolved",
        "underlying_at_expiry": round(close_at_expiry, 4),
        "touched_breakeven": touched,
        "hit": hit,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def to_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve expired prediction locks from EOD history and report Brier series.")
    parser.add_argument("--dry-run", action="store_true", help="Compute resolutions without writing them back.")
    args = parser.parse_args()
    summary = resolve_pending(dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, default=str))
    report = brier_report(default_store.list_resolved_checks())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
