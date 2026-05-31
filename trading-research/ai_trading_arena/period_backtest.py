from __future__ import annotations

from dataclasses import replace

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from .agents import cumulative_options_context_agent
from .config import ArenaConfig, DEFAULT_CONFIG
from .context import SECTOR_MAP, enrich_scores_with_context
from .data import download_daily_prices, load_factor_scores, load_or_download_prices
from .data import _normalize_download


def run_frozen_options_period_backtest(
    start: str = "2026-05-01",
    end: str = "2026-05-15",
    signal_date: str = "2026-04-30",
    config: ArenaConfig = DEFAULT_CONFIG,
    refresh_data: bool = True,
    include_historical_options: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config.results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = config.arena_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    end_ts = pd.Timestamp(end)
    prices = download_daily_prices(config, end=end_ts + pd.Timedelta(days=1)) if refresh_data else load_or_download_prices(config)
    signal_ts = pd.Timestamp(signal_date)
    start_ts = pd.Timestamp(start)

    factor_scores = load_factor_scores(config, signal_ts)
    context_scores = enrich_scores_with_context(
        factor_scores,
        prices,
        signal_ts,
        config,
        include_slow_context=True,
        include_options=include_historical_options,
    )
    weights = cumulative_options_context_agent(prices, signal_ts, context_scores, config)
    if not weights:
        raise ValueError("Cumulative options/context agent produced no holdings.")

    test = prices.loc[(prices["date"] >= start_ts) & (prices["date"] <= end_ts)].copy()
    test = test.loc[test["ticker"].isin(set(weights) | {config.benchmark})]
    if test.empty:
        raise ValueError(f"No daily prices available from {start} to {end}.")

    pivot = test.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()
    open_pivot = test.pivot_table(index="date", columns="ticker", values="open", aggfunc="last").sort_index()
    first_day = pivot.index.min()
    entry_prices = open_pivot.loc[first_day].combine_first(pivot.loc[first_day])

    invested = sum(weights.values())
    entry_cost = config.starting_capital * invested * config.transaction_cost_rate
    shares = {
        ticker: (config.starting_capital * weight - config.starting_capital * weight * config.transaction_cost_rate) / float(entry_prices[ticker])
        for ticker, weight in weights.items()
        if ticker in entry_prices and pd.notna(entry_prices[ticker]) and float(entry_prices[ticker]) > 0
    }
    cash = config.starting_capital * (1 - invested)

    rows: list[dict[str, object]] = []
    for day, close_row in pivot.iterrows():
        equity = cash + sum(shares[ticker] * float(close_row[ticker]) for ticker in shares if ticker in close_row and pd.notna(close_row[ticker]))
        spy_start = float(entry_prices[config.benchmark]) if config.benchmark in entry_prices and pd.notna(entry_prices[config.benchmark]) else None
        spy_equity = None
        if spy_start and config.benchmark in close_row and pd.notna(close_row[config.benchmark]):
            spy_equity = config.starting_capital * float(close_row[config.benchmark]) / spy_start
        rows.append(
            {
                "date": day,
                "agent_equity": equity,
                "agent_return": equity / config.starting_capital - 1,
                "spy_equity": spy_equity,
                "spy_return": spy_equity / config.starting_capital - 1 if spy_equity else None,
            }
        )

    equity = pd.DataFrame(rows)
    final_day = equity["date"].max()
    final_prices = pivot.loc[final_day]
    exit_value = sum(shares[ticker] * float(final_prices[ticker]) for ticker in shares if ticker in final_prices and pd.notna(final_prices[ticker]))
    exit_cost = exit_value * config.transaction_cost_rate
    equity.loc[equity["date"] == final_day, "agent_equity"] -= exit_cost
    equity["agent_return"] = equity["agent_equity"] / config.starting_capital - 1
    equity["agent_drawdown"] = equity["agent_equity"] / equity["agent_equity"].cummax() - 1
    equity["spy_drawdown"] = equity["spy_equity"] / equity["spy_equity"].cummax() - 1

    daily_agent = equity["agent_equity"].pct_change().dropna()
    daily_spy = equity["spy_equity"].pct_change().dropna()
    summary = pd.DataFrame(
        [
            {
                "strategy": "Frozen Cumulative Options Context Agent",
                "signal_date": signal_date,
                "start": start,
                "end": end,
                "starting_capital": config.starting_capital,
                "ending_value": float(equity["agent_equity"].iloc[-1]),
                "profit_loss": float(equity["agent_equity"].iloc[-1] - config.starting_capital),
                "cumulative_return": float(equity["agent_return"].iloc[-1]),
                "spy_ending_value": float(equity["spy_equity"].iloc[-1]),
                "spy_cumulative_return": float(equity["spy_return"].iloc[-1]),
                "excess_return_vs_spy": float(equity["agent_return"].iloc[-1] - equity["spy_return"].iloc[-1]),
                "max_drawdown": float(equity["agent_drawdown"].min()),
                "spy_max_drawdown": float(equity["spy_drawdown"].min()),
                "daily_volatility": float(daily_agent.std()),
                "spy_daily_volatility": float(daily_spy.std()),
                "entry_cost": entry_cost,
                "exit_cost": exit_cost,
                "total_cost": entry_cost + exit_cost,
                "options_note": "Options sentiment set neutral; historical point-in-time options chains are unavailable from Yahoo."
                if not include_historical_options
                else "Options sentiment requested from available provider endpoint.",
            }
        ]
    )
    holdings = pd.DataFrame(
        [{"ticker": ticker, "weight": weight, "entry_price": float(entry_prices[ticker]), "shares": shares.get(ticker, 0)} for ticker, weight in weights.items()]
    )

    stem = f"options_context_{start}_{end}"
    equity.to_csv(config.results_dir / f"{stem}_equity.csv", index=False)
    summary.to_csv(config.results_dir / f"{stem}_summary.csv", index=False)
    holdings.to_csv(config.results_dir / f"{stem}_holdings.csv", index=False)
    _make_figures(equity, holdings, summary, figures_dir, stem)
    return summary, equity, holdings


def run_sector_focus_walk_forward_backtest(
    start: str = "2025-05-01",
    end: str = "2026-05-01",
    history_start: str = "2023-01-01",
    starting_capital: float = 1000.0,
    sectors: tuple[str, ...] = ("Information Technology", "Health Care", "Financials", "Energy"),
    config: ArenaConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    focused_universe = tuple(
        ticker
        for ticker in config.universe
        if ticker in {config.benchmark, "QQQ"} or SECTOR_MAP.get(ticker) in set(sectors)
    )
    focused_config = replace(
        config,
        starting_capital=starting_capital,
        universe=focused_universe,
        lookback_days=max(config.lookback_days, 1400),
    )
    focused_config.results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = focused_config.arena_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    prices = _download_range(focused_config, history_start, pd.Timestamp(end) + pd.Timedelta(days=3))
    prices = prices.loc[prices["ticker"].isin(focused_universe)].copy()
    trading_days = sorted(prices.loc[(prices["date"] >= pd.Timestamp(start)) & (prices["date"] <= pd.Timestamp(end)), "date"].unique())
    if not trading_days:
        raise ValueError("No trading days found for requested period.")

    rebalance_days = _monthly_rebalance_days(pd.Series(pd.to_datetime(trading_days)))
    accounts_cash = starting_capital
    shares: dict[str, float] = {}
    rows: list[dict[str, object]] = []
    holdings_rows: list[dict[str, object]] = []
    total_costs = 0.0
    trades = 0
    last_weights: dict[str, float] = {}

    close_pivot = prices.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()
    open_pivot = prices.pivot_table(index="date", columns="ticker", values="open", aggfunc="last").sort_index()
    spy_entry = float(open_pivot.loc[pd.Timestamp(trading_days[0]), config.benchmark])
    spy_shares = (starting_capital * (1 - focused_config.transaction_cost_rate)) / spy_entry
    spy_total_cost = starting_capital * focused_config.transaction_cost_rate

    for day in pd.to_datetime(trading_days):
        close_price_row = close_pivot.loc[day].combine_first(open_pivot.loc[day])
        open_price_row = open_pivot.loc[day].combine_first(close_pivot.loc[day])
        if day in set(rebalance_days):
            signal_candidates = prices.loc[prices["date"] < day, "date"].dropna().sort_values().unique()
            signal_date = pd.Timestamp(signal_candidates[-1])
            factor_scores = load_factor_scores(focused_config, signal_date)
            context_scores = enrich_scores_with_context(
                factor_scores,
                prices.loc[prices["date"] >= pd.Timestamp(history_start)],
                signal_date,
                focused_config,
                include_slow_context=False,
                include_options=False,
            )
            weights = cumulative_options_context_agent(prices, signal_date, context_scores, focused_config)
            last_weights = weights
            equity_before = accounts_cash + sum(
                shares.get(ticker, 0.0) * float(open_price_row[ticker])
                for ticker in shares
                if ticker in open_price_row and pd.notna(open_price_row[ticker])
            )
            tickers = set(shares) | set(weights)
            for ticker in tickers:
                price = float(open_price_row[ticker]) if ticker in open_price_row and pd.notna(open_price_row[ticker]) else None
                if not price or price <= 0:
                    continue
                current_value = shares.get(ticker, 0.0) * price
                target_value = equity_before * weights.get(ticker, 0.0)
                trade_value = target_value - current_value
                if abs(trade_value) < max(1.0, equity_before * 0.01):
                    continue
                cost = abs(trade_value) * focused_config.transaction_cost_rate
                accounts_cash -= trade_value + cost
                shares[ticker] = shares.get(ticker, 0.0) + trade_value / price
                if abs(shares[ticker]) < 1e-9:
                    shares.pop(ticker, None)
                total_costs += cost
                trades += 1
            for ticker, weight in weights.items():
                holdings_rows.append({"date": day, "signal_date": signal_date, "ticker": ticker, "target_weight": weight})

        equity = accounts_cash + sum(
            shares.get(ticker, 0.0) * float(close_price_row[ticker])
            for ticker in shares
            if ticker in close_price_row and pd.notna(close_price_row[ticker])
        )
        spy_equity = spy_shares * float(close_price_row[config.benchmark]) if config.benchmark in close_price_row else None
        rows.append(
            {
                "date": day,
                "agent_equity": equity,
                "agent_return": equity / starting_capital - 1,
                "spy_equity": spy_equity,
                "spy_return": spy_equity / starting_capital - 1 if spy_equity else None,
                "cash": accounts_cash,
                "costs": total_costs,
                "trades": trades,
                "active_positions": len(shares),
                "latest_weights": dict(last_weights),
                "execution": "rebalance_at_open_mark_at_close",
            }
        )

    equity = pd.DataFrame(rows)
    final_prices = close_pivot.loc[pd.Timestamp(trading_days[-1])]
    liquidation_value = sum(shares.get(ticker, 0.0) * float(final_prices[ticker]) for ticker in shares if ticker in final_prices and pd.notna(final_prices[ticker]))
    exit_cost = liquidation_value * focused_config.transaction_cost_rate
    total_costs += exit_cost
    equity.loc[equity.index[-1], "agent_equity"] -= exit_cost
    equity.loc[equity.index[-1], "costs"] = total_costs
    spy_exit_cost = float(close_pivot.loc[pd.Timestamp(trading_days[-1]), config.benchmark]) * spy_shares * focused_config.transaction_cost_rate
    spy_total_cost += spy_exit_cost
    equity.loc[equity.index[-1], "spy_equity"] -= spy_exit_cost
    equity["agent_return"] = equity["agent_equity"] / starting_capital - 1
    equity["agent_drawdown"] = equity["agent_equity"] / equity["agent_equity"].cummax() - 1
    equity["spy_drawdown"] = equity["spy_equity"] / equity["spy_equity"].cummax() - 1

    daily_agent = equity["agent_equity"].pct_change().dropna()
    daily_spy = equity["spy_equity"].pct_change().dropna()
    summary = pd.DataFrame(
        [
            {
                "strategy": "Sector Focus Cumulative Context Agent",
                "history_start": history_start,
                "start": start,
                "end": end,
                "starting_capital": starting_capital,
                "ending_value": float(equity["agent_equity"].iloc[-1]),
                "profit_loss": float(equity["agent_equity"].iloc[-1] - starting_capital),
                "cumulative_return": float(equity["agent_return"].iloc[-1]),
                "spy_ending_value": float(equity["spy_equity"].iloc[-1]),
                "spy_cumulative_return": float(equity["spy_return"].iloc[-1]),
                "excess_return_vs_spy": float(equity["agent_return"].iloc[-1] - equity["spy_return"].iloc[-1]),
                "max_drawdown": float(equity["agent_drawdown"].min()),
                "spy_max_drawdown": float(equity["spy_drawdown"].min()),
                "daily_volatility": float(daily_agent.std()),
                "spy_daily_volatility": float(daily_spy.std()),
                "sharpe_like": float(daily_agent.mean() / daily_agent.std() * (252**0.5)) if daily_agent.std() else 0.0,
                "spy_sharpe_like": float(daily_spy.mean() / daily_spy.std() * (252**0.5)) if daily_spy.std() else 0.0,
                "total_cost": total_costs,
                "spy_total_cost": spy_total_cost,
                "trades": trades,
                "rebalance_count": len(rebalance_days),
                "execution_model": "Monthly target weights computed from prior close; rebalance executed at next rebalance session open; portfolio marked at close.",
                "leakage_controls": "Signals use dates strictly before rebalance date; factor rows require date<=signal_date and filing_date<=signal_date when filing_date exists; news/options disabled for historical walk-forward.",
                "sectors": ", ".join(sectors),
                "options_note": "Historical options sentiment set neutral because Yahoo does not provide point-in-time historical options chains.",
            }
        ]
    )
    holdings = pd.DataFrame(holdings_rows)
    stem = f"sector_focus_{start}_{end}"
    equity.to_csv(focused_config.results_dir / f"{stem}_equity.csv", index=False)
    summary.to_csv(focused_config.results_dir / f"{stem}_summary.csv", index=False)
    holdings.to_csv(focused_config.results_dir / f"{stem}_holdings.csv", index=False)
    _make_figures(equity, _latest_holdings_for_plot(holdings), summary, figures_dir, stem)
    _make_sector_weight_figure(holdings, figures_dir, stem)
    return summary, equity, holdings


def _make_figures(equity: pd.DataFrame, holdings: pd.DataFrame, summary: pd.DataFrame, figures_dir, stem: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(equity["date"], equity["agent_equity"], label="Options/context agent", linewidth=2.2)
    ax.plot(equity["date"], equity["spy_equity"], label="SPY benchmark", linewidth=2.0)
    ax.set_title("Frozen Options/Context Agent vs SPY")
    ax.set_ylabel("Portfolio value ($)")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(figures_dir / f"{stem}_equity.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(equity["date"], equity["agent_drawdown"] * 100, label="Agent drawdown", linewidth=2.2)
    ax.plot(equity["date"], equity["spy_drawdown"] * 100, label="SPY drawdown", linewidth=2.0)
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown (%)")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(figures_dir / f"{stem}_drawdown.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(holdings["ticker"], holdings["weight"] * 100)
    ax.set_title("Frozen Holdings From Signal Date")
    ax.set_ylabel("Portfolio weight (%)")
    fig.tight_layout()
    fig.savefig(figures_dir / f"{stem}_holdings.png", dpi=160)
    plt.close(fig)


def _download_range(config: ArenaConfig, start: str, end: pd.Timestamp) -> pd.DataFrame:
    raw = yf.download(
        list(config.universe),
        start=start,
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    return _normalize_download(raw)


def _monthly_rebalance_days(days: pd.Series) -> list[pd.Timestamp]:
    frame = pd.DataFrame({"date": pd.to_datetime(days)})
    frame["month"] = frame["date"].dt.to_period("M")
    return [pd.Timestamp(value) for value in frame.groupby("month")["date"].min().tolist()]


def _latest_holdings_for_plot(holdings: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame(columns=["ticker", "weight"])
    last_date = holdings["date"].max()
    latest = holdings.loc[holdings["date"] == last_date, ["ticker", "target_weight"]].copy()
    return latest.rename(columns={"target_weight": "weight"})


def _make_sector_weight_figure(holdings: pd.DataFrame, figures_dir, stem: str) -> None:
    if holdings.empty:
        return
    frame = holdings.copy()
    frame["sector"] = frame["ticker"].map(SECTOR_MAP).fillna("Other")
    pivot = frame.pivot_table(index="date", columns="sector", values="target_weight", aggfunc="sum").fillna(0)
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot.area(ax=ax, linewidth=0)
    ax.set_title("Target Sector Weights At Rebalance")
    ax.set_ylabel("Target weight")
    fig.tight_layout()
    fig.savefig(figures_dir / f"{stem}_sector_weights.png", dpi=160)
    plt.close(fig)
