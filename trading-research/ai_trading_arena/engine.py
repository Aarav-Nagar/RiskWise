from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .agents import AGENTS, enforce_constraints
from .config import ArenaConfig, DEFAULT_CONFIG
from .context import enrich_scores_with_context
from .data import bars_for_date, latest_signal_date, load_factor_scores, load_or_download_prices, parse_trade_date


def _ensure_dirs(config: ArenaConfig) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.submissions_dir.mkdir(parents=True, exist_ok=True)
    config.results_dir.mkdir(parents=True, exist_ok=True)


def submission_paths(config: ArenaConfig, trade_date: pd.Timestamp) -> tuple[Path, Path]:
    stem = trade_date.strftime("%Y-%m-%d")
    return config.submissions_dir / f"{stem}.json", config.submissions_dir / f"{stem}.csv"


def result_path(config: ArenaConfig, trade_date: pd.Timestamp) -> Path:
    return config.results_dir / f"{trade_date.strftime('%Y-%m-%d')}_results.csv"


def build_submissions(
    trade_date_value: str | None = None,
    config: ArenaConfig = DEFAULT_CONFIG,
    force: bool = False,
    refresh_data: bool = True,
) -> pd.DataFrame:
    _ensure_dirs(config)
    trade_date = parse_trade_date(trade_date_value)
    json_path, csv_path = submission_paths(config, trade_date)
    if json_path.exists() and not force:
        return pd.read_csv(csv_path)

    prices = load_or_download_prices(config, refresh=refresh_data)
    signal_date = latest_signal_date(prices, trade_date)
    scores = load_factor_scores(config, signal_date)
    scores = enrich_scores_with_context(scores, prices, signal_date, config, include_slow_context=True, include_options=True)

    records: list[dict[str, object]] = []
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "trade_date": trade_date.strftime("%Y-%m-%d"),
        "signal_date": signal_date.strftime("%Y-%m-%d"),
        "starting_capital": config.starting_capital,
        "entry_rule": "Buy at target session open.",
        "exit_rule": "Liquidate at target session close.",
        "transaction_cost_rate": config.transaction_cost_rate,
        "agents": [],
    }
    for agent in AGENTS:
        proposed_weights = agent.build(prices, signal_date, scores, config)
        weights = proposed_weights if agent.name == "SPY_Benchmark" else enforce_constraints(proposed_weights, config)
        agent_payload = {"agent": agent.name, "description": agent.description, "weights": weights}
        payload["agents"].append(agent_payload)
        for ticker, weight in weights.items():
            records.append(
                {
                    "trade_date": trade_date.strftime("%Y-%m-%d"),
                    "signal_date": signal_date.strftime("%Y-%m-%d"),
                    "agent": agent.name,
                    "ticker": ticker,
                    "weight": weight,
                    "description": agent.description,
                }
            )

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    submissions = pd.DataFrame(records).sort_values(["agent", "weight"], ascending=[True, False])
    submissions.to_csv(csv_path, index=False)
    return submissions


def score_submissions(
    trade_date_value: str | None = None,
    config: ArenaConfig = DEFAULT_CONFIG,
    refresh_data: bool = True,
) -> pd.DataFrame:
    _ensure_dirs(config)
    trade_date = parse_trade_date(trade_date_value)
    json_path, _ = submission_paths(config, trade_date)
    if not json_path.exists():
        raise FileNotFoundError(f"No frozen submission found for {trade_date.date()}. Run submit first.")

    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    prices = load_or_download_prices(config, refresh=refresh_data)
    day = bars_for_date(prices, trade_date)
    if day.empty:
        raise ValueError(f"No open/close bars are available yet for {trade_date.date()}. Score after market data updates.")

    price_map = day.set_index("ticker")[["open", "close"]].to_dict("index")
    rows: list[dict[str, object]] = []
    for agent in payload["agents"]:
        gross_return = 0.0
        invested = 0.0
        missing: list[str] = []
        best_ticker = None
        worst_ticker = None
        best_return = -999.0
        worst_return = 999.0
        for ticker, weight in agent["weights"].items():
            bar = price_map.get(ticker)
            if not bar or pd.isna(bar["open"]) or pd.isna(bar["close"]) or float(bar["open"]) <= 0:
                missing.append(ticker)
                continue
            intraday_return = float(bar["close"]) / float(bar["open"]) - 1
            gross_return += float(weight) * intraday_return
            invested += float(weight)
            if intraday_return > best_return:
                best_return = intraday_return
                best_ticker = ticker
            if intraday_return < worst_return:
                worst_return = intraday_return
                worst_ticker = ticker

        cost_return = invested * config.transaction_cost_rate
        net_return = gross_return - cost_return
        ending_value = config.starting_capital * (1 + net_return)
        rows.append(
            {
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "agent": agent["agent"],
                "starting_capital": config.starting_capital,
                "ending_value": ending_value,
                "profit_loss": ending_value - config.starting_capital,
                "gross_return": gross_return,
                "transaction_cost_dollars": config.starting_capital * cost_return,
                "net_return": net_return,
                "invested_weight": invested,
                "cash_weight": max(0.0, 1 - invested),
                "holdings": len(agent["weights"]),
                "best_ticker": best_ticker,
                "best_ticker_return": best_return if best_ticker else None,
                "worst_ticker": worst_ticker,
                "worst_ticker_return": worst_return if worst_ticker else None,
                "missing_tickers": ",".join(missing),
            }
        )
    results = pd.DataFrame(rows).sort_values("ending_value", ascending=False)
    results.to_csv(result_path(config, trade_date), index=False)
    return results


def load_leaderboard(config: ArenaConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    _ensure_dirs(config)
    frames = [pd.read_csv(path) for path in sorted(config.results_dir.glob("*_results.csv"))]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values(["trade_date", "ending_value"], ascending=[False, False])
