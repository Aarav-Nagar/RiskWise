from __future__ import annotations

import argparse
import sys

import pandas as pd

from .config import DEFAULT_CONFIG
from .big_game import BigGameConfig, run_big_game
from .engine import build_submissions, load_leaderboard, score_submissions, submission_paths
from .period_backtest import run_frozen_options_period_backtest, run_sector_focus_walk_forward_backtest
from .realtime import replay_live_day, run_live_poll


def _print_money_table(frame: pd.DataFrame) -> None:
    if frame.empty:
        print("No rows.")
        return
    with pd.option_context("display.max_rows", 100, "display.width", 140):
        print(frame.to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the forward AI paper-trading arena.")
    sub = parser.add_subparsers(dest="command", required=True)

    submit = sub.add_parser("submit", help="Freeze agent portfolios before a target trading day.")
    submit.add_argument("--trade-date", help="Target trading day, YYYY-MM-DD. Defaults to next weekday.")
    submit.add_argument("--force", action="store_true", help="Overwrite an existing frozen submission.")
    submit.add_argument("--no-refresh", action="store_true", help="Use cached Yahoo data.")

    score = sub.add_parser("score", help="Score a frozen target day using open-to-close returns.")
    score.add_argument("--trade-date", help="Target trading day, YYYY-MM-DD. Defaults to next weekday.")
    score.add_argument("--no-refresh", action="store_true", help="Use cached Yahoo data.")

    run = sub.add_parser("run", help="Submit, then score if target-day bars already exist.")
    run.add_argument("--trade-date", help="Target trading day, YYYY-MM-DD. Defaults to next weekday.")
    run.add_argument("--force", action="store_true", help="Overwrite an existing frozen submission.")

    sub.add_parser("leaderboard", help="Show all scored arena results.")

    live = sub.add_parser("live", help="Poll current intraday bars and update live paper agents.")
    live.add_argument("--seconds", type=int, default=300, help="Total runtime in seconds.")
    live.add_argument("--interval", type=int, default=10, help="Polling interval in seconds.")

    replay = sub.add_parser("replay-live", help="Replay a historical intraday day as if it were live.")
    replay.add_argument("--trade-date", required=True, help="Day to replay, YYYY-MM-DD.")
    replay.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between replayed bars.")

    period = sub.add_parser("options-period", help="Backtest frozen cumulative options/context agent over a date range.")
    period.add_argument("--start", default="2026-05-01")
    period.add_argument("--end", default="2026-05-15")
    period.add_argument("--signal-date", default="2026-04-30")
    period.add_argument("--no-refresh", action="store_true")
    period.add_argument("--use-provider-options", action="store_true", help="Use provider options endpoint if available; may not be historical point-in-time.")

    sector_period = sub.add_parser("sector-period", help="Run sector-focused one-year cumulative context walk-forward test.")
    sector_period.add_argument("--start", default="2025-05-01")
    sector_period.add_argument("--end", default="2026-05-01")
    sector_period.add_argument("--history-start", default="2023-01-01")
    sector_period.add_argument("--capital", type=float, default=1000.0)

    big_game = sub.add_parser("big-game", help="Run human vs normal vs options-only vs anything one-year competition.")
    big_game.add_argument("--start", default="2025-05-01")
    big_game.add_argument("--end", default="2026-05-01")
    big_game.add_argument("--history-start", default="2023-01-01")
    big_game.add_argument("--capital", type=float, default=1000.0)
    big_game.add_argument("--target", type=float, default=2000.0)

    args = parser.parse_args(argv)

    if args.command == "submit":
        submissions = build_submissions(args.trade_date, force=args.force, refresh_data=not args.no_refresh)
        json_path, csv_path = submission_paths(DEFAULT_CONFIG, pd.Timestamp(submissions["trade_date"].iloc[0]))
        print(f"Frozen submission saved: {json_path}")
        print(f"CSV saved: {csv_path}")
        _print_money_table(submissions[["trade_date", "signal_date", "agent", "ticker", "weight"]])
        return 0

    if args.command == "score":
        try:
            results = score_submissions(args.trade_date, refresh_data=not args.no_refresh)
        except Exception as exc:
            print(f"Scoring not available: {exc}")
            return 0
        _print_money_table(
            results[
                [
                    "trade_date",
                    "agent",
                    "ending_value",
                    "profit_loss",
                    "net_return",
                    "invested_weight",
                    "transaction_cost_dollars",
                    "best_ticker",
                    "worst_ticker",
                ]
            ]
        )
        return 0

    if args.command == "run":
        submissions = build_submissions(args.trade_date, force=args.force, refresh_data=True)
        print("Submission frozen.")
        try:
            results = score_submissions(str(submissions["trade_date"].iloc[0]), refresh_data=True)
        except Exception as exc:
            print(f"Scoring not available yet: {exc}")
            return 0
        _print_money_table(results)
        return 0

    if args.command == "leaderboard":
        board = load_leaderboard()
        _print_money_table(board)
        return 0

    if args.command == "live":
        board = run_live_poll(duration_seconds=args.seconds, interval_seconds=args.interval)
        _print_money_table(board)
        return 0

    if args.command == "replay-live":
        board = replay_live_day(args.trade_date, sleep_seconds=args.sleep)
        _print_money_table(board)
        return 0

    if args.command == "options-period":
        summary, equity, holdings = run_frozen_options_period_backtest(
            start=args.start,
            end=args.end,
            signal_date=args.signal_date,
            refresh_data=not args.no_refresh,
            include_historical_options=args.use_provider_options,
        )
        print("Holdings:")
        _print_money_table(holdings)
        print("\nSummary:")
        _print_money_table(summary)
        return 0

    if args.command == "sector-period":
        summary, equity, holdings = run_sector_focus_walk_forward_backtest(
            start=args.start,
            end=args.end,
            history_start=args.history_start,
            starting_capital=args.capital,
        )
        print("Latest holdings:")
        latest = holdings.loc[holdings["date"] == holdings["date"].max()] if not holdings.empty else holdings
        _print_money_table(latest)
        print("\nSummary:")
        _print_money_table(summary)
        return 0

    if args.command == "big-game":
        summary, monthly, equity = run_big_game(
            BigGameConfig(
                start=args.start,
                end=args.end,
                history_start=args.history_start,
                capital=args.capital,
                target=args.target,
            )
        )
        print("Summary:")
        _print_money_table(summary)
        print("\nMonthly scores:")
        _print_money_table(monthly)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
