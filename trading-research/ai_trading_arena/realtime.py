from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

from .config import ArenaConfig, DEFAULT_CONFIG


LIVE_AGENTS = ("SPY_Live", "LiveMomentum", "LiveMeanReversion", "LiveBreakout", "LiveMeta")


@dataclass
class LiveAccount:
    agent: str
    cash: float
    positions: dict[str, float] = field(default_factory=dict)
    costs: float = 0.0
    trades: int = 0


def _normalize_intraday(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["timestamp", "ticker", "open", "high", "low", "close", "volume"])
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame = frame.stack(level=1, future_stack=True).reset_index()
    else:
        frame = frame.reset_index()
        frame["Ticker"] = "UNKNOWN"
    frame = frame.rename(
        columns={
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Ticker": "ticker",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    if "timestamp" not in frame.columns and "index" in frame.columns:
        frame = frame.rename(columns={"index": "timestamp"})
    if "ticker" not in frame.columns and "level_1" in frame.columns:
        frame = frame.rename(columns={"level_1": "ticker"})
    columns = ["timestamp", "ticker", "open", "high", "low", "close", "volume"]
    frame = frame[[column for column in columns if column in frame.columns]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.tz_localize(None)
    frame["ticker"] = frame["ticker"].astype(str)
    return frame.dropna(subset=["timestamp", "ticker", "close"]).sort_values(["timestamp", "ticker"]).reset_index(drop=True)


def fetch_intraday_snapshot(config: ArenaConfig = DEFAULT_CONFIG, period: str = "1d") -> pd.DataFrame:
    raw = yf.download(
        list(config.universe),
        period=period,
        interval="1m",
        auto_adjust=False,
        progress=False,
        threads=True,
        prepost=False,
    )
    return _normalize_intraday(raw)


def fetch_intraday_day(trade_date: str, config: ArenaConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    start = pd.Timestamp(trade_date).strftime("%Y-%m-%d")
    end = (pd.Timestamp(trade_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(
        list(config.universe),
        start=start,
        end=end,
        interval="1m",
        auto_adjust=False,
        progress=False,
        threads=True,
        prepost=False,
    )
    return _normalize_intraday(raw)


def _rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    value = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    return float(value.iloc[-1]) if len(value.dropna()) else 50.0


def _features(panel: pd.DataFrame, timestamp: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    visible = panel.loc[panel["timestamp"] <= timestamp].copy()
    for ticker, group in visible.groupby("ticker"):
        group = group.sort_values("timestamp").tail(40)
        if len(group) < 6:
            continue
        close = group["close"].astype(float)
        volume = group["volume"].astype(float)
        high20 = close.rolling(20).max().iloc[-1]
        low20 = close.rolling(20).min().iloc[-1]
        vol_std = volume.rolling(20).std().iloc[-1]
        rows.append(
            {
                "ticker": ticker,
                "price": float(close.iloc[-1]),
                "ret_1m": close.pct_change(1).iloc[-1],
                "ret_3m": close.pct_change(3).iloc[-1],
                "ret_10m": close.pct_change(10).iloc[-1] if len(close) > 10 else 0.0,
                "vol_10m": close.pct_change().rolling(10).std().iloc[-1],
                "rsi": _rsi(close),
                "range_pos": (close.iloc[-1] - low20) / (high20 - low20) if pd.notna(high20) and high20 != low20 else 0.5,
                "volume_z": (volume.iloc[-1] - volume.rolling(20).mean().iloc[-1]) / vol_std if pd.notna(vol_std) and vol_std != 0 else 0.0,
            }
        )
    return pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).fillna(0)


def _top_weights(scored: pd.DataFrame, score_col: str, exposure: float, max_names: int = 3) -> dict[str, float]:
    picks = scored.loc[scored["ticker"] != "SPY"].sort_values(score_col, ascending=False).head(max_names)
    if picks.empty:
        return {}
    return {ticker: round(exposure / len(picks), 6) for ticker in picks["ticker"]}


def live_agent_weights(panel: pd.DataFrame, timestamp: pd.Timestamp) -> dict[str, dict[str, float]]:
    feat = _features(panel, timestamp)
    if feat.empty:
        return {agent: {} for agent in LIVE_AGENTS}
    weights: dict[str, dict[str, float]] = {"SPY_Live": {"SPY": 0.99}}

    momentum = feat.copy()
    momentum["score"] = momentum["ret_10m"] + 0.5 * momentum["ret_3m"] - 0.2 * momentum["vol_10m"]
    weights["LiveMomentum"] = _top_weights(momentum, "score", 0.90)

    reversion = feat.copy()
    reversion["score"] = -reversion["ret_3m"] + (45 - reversion["rsi"]).clip(-20, 20) / 100
    weights["LiveMeanReversion"] = _top_weights(reversion, "score", 0.75)

    breakout = feat.copy()
    breakout["score"] = breakout["range_pos"] + breakout["volume_z"].clip(-2, 3) / 10 + breakout["ret_1m"]
    weights["LiveBreakout"] = _top_weights(breakout, "score", 0.80)

    meta = feat.copy()
    meta["score"] = (
        0.35 * meta["ret_10m"].rank(pct=True)
        + 0.25 * meta["range_pos"].rank(pct=True)
        + 0.20 * (-meta["ret_3m"]).rank(pct=True)
        + 0.10 * meta["volume_z"].rank(pct=True)
        - 0.20 * meta["vol_10m"].rank(pct=True)
    )
    weights["LiveMeta"] = _top_weights(meta, "score", 0.85)
    return weights


def _mark(account: LiveAccount, prices: dict[str, float]) -> float:
    return account.cash + sum(shares * prices.get(ticker, 0.0) for ticker, shares in account.positions.items())


def _rebalance(
    account: LiveAccount,
    target_weights: dict[str, float],
    prices: dict[str, float],
    cost_rate: float,
    min_trade_fraction: float = 0.15,
) -> float:
    equity = _mark(account, prices)
    if equity <= 0:
        return equity
    tickers = set(account.positions) | set(target_weights)
    for ticker in tickers:
        price = prices.get(ticker)
        if not price or price <= 0:
            continue
        current_value = account.positions.get(ticker, 0.0) * price
        target_value = equity * target_weights.get(ticker, 0.0)
        trade_value = target_value - current_value
        if abs(trade_value) < max(0.01, equity * min_trade_fraction):
            continue
        shares_delta = trade_value / price
        cost = abs(trade_value) * cost_rate
        account.cash -= trade_value + cost
        account.positions[ticker] = account.positions.get(ticker, 0.0) + shares_delta
        if abs(account.positions[ticker]) < 1e-9:
            account.positions.pop(ticker, None)
        account.costs += cost
        account.trades += 1
    return _mark(account, prices)


def simulate_live_panel(panel: pd.DataFrame, config: ArenaConfig = DEFAULT_CONFIG, label: str = "session") -> tuple[pd.DataFrame, pd.DataFrame]:
    config.live_dir.mkdir(parents=True, exist_ok=True)
    accounts = {agent: LiveAccount(agent, config.starting_capital) for agent in LIVE_AGENTS}
    equity_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []

    timestamps = sorted(panel["timestamp"].dropna().unique())
    for step, timestamp in enumerate(timestamps):
        timestamp = pd.Timestamp(timestamp)
        visible = panel.loc[panel["timestamp"] <= timestamp]
        latest = visible.sort_values("timestamp").groupby("ticker", as_index=False).tail(1)
        prices = dict(zip(latest["ticker"], latest["close"].astype(float)))
        should_rebalance = step == 0 or step % 30 == 0 or step == len(timestamps) - 1
        targets = live_agent_weights(visible, timestamp) if should_rebalance else {}
        for agent, account in accounts.items():
            before_positions = dict(account.positions)
            if should_rebalance:
                equity = _rebalance(account, targets.get(agent, {}), prices, config.transaction_cost_rate)
            else:
                equity = _mark(account, prices)
            if before_positions != account.positions:
                trade_rows.append(
                    {
                        "timestamp": timestamp,
                        "agent": agent,
                        "target_weights": targets.get(agent, {}),
                        "equity": equity,
                        "cash": account.cash,
                        "costs": account.costs,
                        "trades": account.trades,
                    }
                )
            equity_rows.append(
                {
                    "timestamp": timestamp,
                    "agent": agent,
                    "equity": _mark(account, prices),
                    "cash": account.cash,
                    "costs": account.costs,
                    "trades": account.trades,
                    "positions": dict(account.positions),
                }
            )

    equity = pd.DataFrame(equity_rows)
    trades = pd.DataFrame(trade_rows)
    equity.to_csv(config.live_dir / f"{label}_equity.csv", index=False)
    trades.to_csv(config.live_dir / f"{label}_trades.csv", index=False)
    return equity, trades


def replay_live_day(
    trade_date: str,
    config: ArenaConfig = DEFAULT_CONFIG,
    sleep_seconds: float = 0.0,
) -> pd.DataFrame:
    panel = fetch_intraday_day(trade_date, config)
    if panel.empty:
        raise ValueError(f"No intraday bars found for {trade_date}.")
    if sleep_seconds <= 0:
        equity, _ = simulate_live_panel(panel, config, label=f"replay_{trade_date}")
    else:
        equity_rows: list[pd.DataFrame] = []
        partial = pd.DataFrame()
        for timestamp in sorted(panel["timestamp"].dropna().unique()):
            partial = pd.concat([partial, panel.loc[panel["timestamp"] == timestamp]], ignore_index=True)
            equity, _ = simulate_live_panel(partial, config, label=f"replay_{trade_date}")
            equity_rows.append(equity.tail(len(LIVE_AGENTS)))
            print(_summary(equity).to_string(index=False))
            time.sleep(sleep_seconds)
        equity = pd.concat(equity_rows, ignore_index=True) if equity_rows else pd.DataFrame()
    return _summary(equity)


def run_live_poll(
    duration_seconds: int = 300,
    interval_seconds: int = 10,
    config: ArenaConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    deadline = time.time() + duration_seconds
    panel = pd.DataFrame()
    while time.time() < deadline:
        snapshot = fetch_intraday_snapshot(config)
        if not snapshot.empty:
            panel = snapshot
            equity, _ = simulate_live_panel(panel, config, label=datetime.now().strftime("live_%Y%m%d"))
            print(_summary(equity).to_string(index=False))
        else:
            print("No live intraday bars available yet.")
        time.sleep(interval_seconds)
    if panel.empty:
        return pd.DataFrame()
    equity, _ = simulate_live_panel(panel, config, label=datetime.now().strftime("live_%Y%m%d"))
    return _summary(equity)


def _summary(equity: pd.DataFrame) -> pd.DataFrame:
    if equity.empty:
        return equity
    last = equity.sort_values("timestamp").groupby("agent", as_index=False).tail(1).copy()
    last["profit_loss"] = last["equity"] - DEFAULT_CONFIG.starting_capital
    last["return"] = last["profit_loss"] / DEFAULT_CONFIG.starting_capital
    return last[["timestamp", "agent", "equity", "profit_loss", "return", "cash", "costs", "trades"]].sort_values("equity", ascending=False)
