from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

from .config import ArenaConfig, DEFAULT_CONFIG


def parse_trade_date(value: str | None) -> pd.Timestamp:
    if value:
        return pd.Timestamp(value).normalize()
    today = pd.Timestamp.today(tz="America/New_York").tz_localize(None).normalize()
    return next_weekday(today + pd.Timedelta(days=1))


def next_weekday(day: pd.Timestamp) -> pd.Timestamp:
    while day.weekday() >= 5:
        day += pd.Timedelta(days=1)
    return day.normalize()


def _normalize_download(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])

    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        if frame.columns.names[0] in {"Price", None}:
            frame = frame.stack(level=1, future_stack=True).reset_index()
        else:
            frame = frame.stack(level=0, future_stack=True).reset_index()
    else:
        frame = frame.reset_index()
        frame["Ticker"] = "UNKNOWN"

    rename = {
        "Date": "date",
        "Datetime": "date",
        "Ticker": "ticker",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    frame = frame.rename(columns=rename)
    if "ticker" not in frame.columns and "level_1" in frame.columns:
        frame = frame.rename(columns={"level_1": "ticker"})
    if "adj_close" not in frame.columns:
        frame["adj_close"] = frame["close"]

    columns = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    frame = frame[[c for c in columns if c in frame.columns]]
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None).dt.normalize()
    frame["ticker"] = frame["ticker"].astype(str)
    return frame.sort_values(["ticker", "date"]).reset_index(drop=True)


def download_daily_prices(config: ArenaConfig = DEFAULT_CONFIG, end: pd.Timestamp | None = None) -> pd.DataFrame:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    end = (end or pd.Timestamp.today().normalize()) + pd.Timedelta(days=2)
    start = end - pd.Timedelta(days=config.lookback_days)
    raw = yf.download(
        list(config.universe),
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    prices = _normalize_download(raw)
    prices.to_csv(config.cache_path, index=False)
    return prices


def load_or_download_prices(config: ArenaConfig = DEFAULT_CONFIG, refresh: bool = False) -> pd.DataFrame:
    if refresh or not config.cache_path.exists():
        return download_daily_prices(config)
    prices = pd.read_csv(config.cache_path, parse_dates=["date"])
    return prices.sort_values(["ticker", "date"]).reset_index(drop=True)


def latest_signal_date(prices: pd.DataFrame, trade_date: pd.Timestamp) -> pd.Timestamp:
    available = sorted(prices.loc[prices["date"] < trade_date, "date"].dropna().unique())
    if not available:
        raise ValueError(f"No market data exists before {trade_date.date()}.")
    return pd.Timestamp(available[-1]).normalize()


def bars_for_date(prices: pd.DataFrame, trade_date: pd.Timestamp) -> pd.DataFrame:
    day = prices.loc[prices["date"] == trade_date].copy()
    return day.dropna(subset=["open", "close"])


def load_factor_scores(config: ArenaConfig = DEFAULT_CONFIG, signal_date: pd.Timestamp | None = None) -> pd.DataFrame:
    for path in config.factor_score_paths:
        if path.exists():
            scores = pd.read_csv(path)
            if "date" in scores.columns:
                scores["date"] = pd.to_datetime(scores["date"], errors="coerce")
            if "filing_date" in scores.columns:
                scores["filing_date"] = pd.to_datetime(scores["filing_date"], errors="coerce")
            if signal_date is not None and "date" in scores.columns:
                scores = scores.loc[scores["date"] <= signal_date]
            if signal_date is not None and "filing_date" in scores.columns:
                scores = scores.loc[scores["filing_date"].isna() | (scores["filing_date"] <= signal_date)]
            if scores.empty:
                continue
            scores = scores.sort_values(["ticker", "date"]).groupby("ticker", as_index=False).tail(1)
            wanted = [
                "ticker",
                "date",
                "filing_date",
                "quality_score",
                "growth_score",
                "technical_score",
                "fundamental_score",
                "agent_score",
            ]
            return scores[[c for c in wanted if c in scores.columns]].reset_index(drop=True)
    return pd.DataFrame(columns=["ticker", "quality_score", "growth_score", "technical_score", "fundamental_score", "agent_score"])
