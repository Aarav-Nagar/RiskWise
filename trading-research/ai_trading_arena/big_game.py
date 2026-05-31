from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from .big_game_agents import build_big_game_agents
from .big_game_agents.accounting import execute_target, mark_state, scoreboard_snapshot, settle_options
from .config import ArenaConfig, DEFAULT_CONFIG
from .context import SECTOR_MAP
from .data import _normalize_download


@dataclass(frozen=True)
class BigGameConfig:
    start: str = "2025-05-01"
    end: str = "2026-05-01"
    history_start: str = "2023-01-01"
    capital: float = 1000.0
    target: float = 2000.0
    transaction_cost_rate: float = 0.001


def run_big_game(config: BigGameConfig = BigGameConfig(), arena_config: ArenaConfig = DEFAULT_CONFIG) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    out_dir = arena_config.results_dir
    fig_dir = arena_config.arena_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    stock_universe = tuple(
        ticker
        for ticker in arena_config.universe
        if ticker in {arena_config.benchmark, "QQQ"} or SECTOR_MAP.get(ticker) in {"Information Technology", "Health Care", "Financials", "Energy"}
    )
    cross_asset = (
        "SPY",
        "QQQ",
        "XLK",
        "XLV",
        "XLF",
        "XLE",
        "GLD",
        "TLT",
        "UUP",
        "BTC-USD",
        "EURUSD=X",
        "JPY=X",
    )
    universe = sorted(set(stock_universe) | set(cross_asset))
    prices = _download_prices(universe, config.history_start, pd.Timestamp(config.end) + pd.Timedelta(days=3))
    close = prices.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index().ffill()
    open_ = prices.pivot_table(index="date", columns="ticker", values="open", aggfunc="last").sort_index().ffill()
    days = pd.Series(close.loc[(close.index >= config.start) & (close.index <= config.end)].index)
    rebalances = _monthly_rebalance_days(days)

    agents = build_big_game_agents()
    states = {
        name: {
            "cash": config.capital,
            "shares": {},
            "option_book": [],
            "costs": 0.0,
            "trades": 0,
            "last_message": "Starting at $1,000; target is $2,000.",
        }
        for name in agents
    }

    equity_rows: list[dict[str, object]] = []
    decision_rows: list[dict[str, object]] = []
    month_end_rows: list[dict[str, object]] = []

    for idx, day in enumerate(pd.to_datetime(days)):
        open_row = open_.loc[day].combine_first(close.loc[day])
        close_row = close.loc[day].combine_first(open_.loc[day])
        is_rebalance = day in set(rebalances)
        next_day = pd.Timestamp(rebalances[min(rebalances.index(day) + 1, len(rebalances) - 1)]) if is_rebalance else None
        if is_rebalance:
            signal_candidates = close.loc[close.index < day].index
            if len(signal_candidates) == 0:
                continue
            signal_date = pd.Timestamp(signal_candidates[-1])
            scoreboard = scoreboard_snapshot(states, close_row, config)
            for name, policy in agents.items():
                state = states[name]
                if state["option_book"]:
                    settle_options(state, open_row, day, config)
                target = policy(close.loc[:signal_date], open_row, state, config, scoreboard)
                execute_target(state, target, open_row, day, next_day or day + pd.Timedelta(days=30), config)
                message = _message_for_agent(name, state, scoreboard, target)
                state["last_message"] = message
                decision_rows.append({"date": day, "agent": name, "decision": target, "message": message})

        for name, state in states.items():
            equity = mark_state(state, close_row, day)
            equity_rows.append(
                {
                    "date": day,
                    "agent": name,
                    "equity": equity,
                    "return": equity / config.capital - 1,
                    "distance_to_2x": config.target - equity,
                    "cash": state["cash"],
                    "costs": state["costs"],
                    "trades": state["trades"],
                    "message": state["last_message"],
                }
            )
        if idx == len(days) - 1 or pd.Timestamp(days.iloc[min(idx + 1, len(days) - 1)]).month != day.month:
            month_end = pd.DataFrame(equity_rows).loc[lambda frame: frame["date"] == day].sort_values("equity", ascending=False)
            month_end_rows.extend(
                {
                    "month_end": day,
                    "rank": rank + 1,
                    "agent": row["agent"],
                    "equity": row["equity"],
                    "return": row["return"],
                    "distance_to_2x": row["distance_to_2x"],
                    "message": row["message"],
                }
                for rank, row in enumerate(month_end.to_dict("records"))
            )

    equity = pd.DataFrame(equity_rows)
    monthly = pd.DataFrame(month_end_rows)
    decisions = pd.DataFrame(decision_rows)
    summary = _summary(equity, monthly, config)
    stem = "big_game_2025-05-01_2026-05-01"
    equity.to_csv(out_dir / f"{stem}_equity.csv", index=False)
    monthly.to_csv(out_dir / f"{stem}_monthly_scores.csv", index=False)
    decisions.to_csv(out_dir / f"{stem}_decisions.csv", index=False)
    summary.to_csv(out_dir / f"{stem}_summary.csv", index=False)
    _plot_big_game(equity, monthly, fig_dir, stem)
    return summary, monthly, equity


def _download_prices(tickers: list[str], start: str, end: pd.Timestamp) -> pd.DataFrame:
    raw = yf.download(tickers, start=start, end=end.strftime("%Y-%m-%d"), auto_adjust=False, progress=False, threads=True)
    return _normalize_download(raw)


def _monthly_rebalance_days(days: pd.Series) -> list[pd.Timestamp]:
    frame = pd.DataFrame({"date": pd.to_datetime(days)})
    frame["month"] = frame["date"].dt.to_period("M")
    return [pd.Timestamp(value) for value in frame.groupby("month")["date"].min().tolist()]


def _message_for_agent(name: str, state: dict, scoreboard: pd.DataFrame, decision: dict) -> str:
    leader = scoreboard.iloc[0]["agent"] if not scoreboard.empty else "none"
    if name == leader:
        return f"{name}: leading now; preserving edge. {decision.get('reason', '')}"
    return f"{name}: chasing {leader}; target remains 2x. {decision.get('reason', '')}"


def _summary(equity: pd.DataFrame, monthly: pd.DataFrame, config: BigGameConfig) -> pd.DataFrame:
    rows = []
    for agent, group in equity.groupby("agent"):
        group = group.sort_values("date")
        daily = group["equity"].pct_change().dropna()
        rows.append(
            {
                "agent": agent,
                "ending_value": float(group["equity"].iloc[-1]),
                "max_equity": float(group["equity"].max()),
                "profit_loss": float(group["equity"].iloc[-1] - config.capital),
                "return": float(group["equity"].iloc[-1] / config.capital - 1),
                "hit_2x_at_end": bool(group["equity"].iloc[-1] >= config.target),
                "ever_hit_2x": bool((group["equity"] >= config.target).any()),
                "max_drawdown": float((group["equity"] / group["equity"].cummax() - 1).min()),
                "daily_volatility": float(daily.std()) if len(daily) else 0.0,
                "sharpe_like": float(daily.mean() / daily.std() * (252**0.5)) if len(daily) and daily.std() else 0.0,
                "costs": float(group["costs"].iloc[-1]),
                "trades": int(group["trades"].iloc[-1]),
                "best_month_rank": int(monthly.loc[monthly["agent"] == agent, "rank"].min()),
            }
        )
    return pd.DataFrame(rows).sort_values("ending_value", ascending=False)


def _plot_big_game(equity: pd.DataFrame, monthly: pd.DataFrame, fig_dir, stem: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6))
    for agent, group in equity.groupby("agent"):
        ax.plot(group["date"], group["equity"], label=agent, linewidth=1.8)
    ax.axhline(2000, color="black", linestyle="--", linewidth=1, label="2x target")
    ax.set_title("Big Game Equity: Human, Normal, Options-Only, Anything Agents")
    ax.set_ylabel("Equity ($)")
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(fig_dir / f"{stem}_equity.png", dpi=160)
    plt.close(fig)

    pivot = monthly.pivot_table(index="month_end", columns="agent", values="rank", aggfunc="last")
    fig, ax = plt.subplots(figsize=(11, 5))
    for agent in pivot.columns:
        ax.plot(pivot.index, pivot[agent], marker="o", label=agent)
    ax.invert_yaxis()
    ax.set_title("Monthly Leaderboard Rank")
    ax.set_ylabel("Rank")
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(fig_dir / f"{stem}_monthly_ranks.png", dpi=160)
    plt.close(fig)
