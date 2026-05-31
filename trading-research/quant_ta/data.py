from __future__ import annotations

import pandas as pd
import yfinance as yf

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.io import read_frame, write_frame


PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


def _normalize_download(raw: pd.DataFrame, tickers: tuple[str, ...]) -> pd.DataFrame:
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no rows.")

    frames: list[pd.DataFrame] = []
    if isinstance(raw.columns, pd.MultiIndex):
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(-1):
                continue
            one = raw.xs(ticker, axis=1, level=-1, drop_level=True).copy()
            one["ticker"] = ticker
            frames.append(one)
    else:
        one = raw.copy()
        one["ticker"] = tickers[0]
        frames.append(one)

    df = pd.concat(frames).reset_index()
    df.columns = [str(col).lower().replace(" ", "_") for col in df.columns]
    if "date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "date"})
    if "adj_close" not in df.columns and "close" in df.columns:
        df["adj_close"] = df["close"]
    df = df[["date", "ticker", *PRICE_COLUMNS]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def download_prices(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    raw = yf.download(
        tickers=list(config.all_tickers),
        start=config.start_date,
        auto_adjust=False,
        group_by="column",
        progress=False,
        threads=True,
    )
    prices = _normalize_download(raw, config.all_tickers)
    prices = clean_prices(prices)
    write_frame(prices, config.raw_dir / "prices.csv")
    return prices


def clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["ticker"] = df["ticker"].str.upper()
    df = df.drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"])
    for column in PRICE_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "ticker", "close", "high", "low"])
    df["volume"] = df["volume"].fillna(0)
    df = df[df["close"] > 0]
    return df.reset_index(drop=True)


def load_prices(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    path = config.raw_dir / "prices.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date"])
    return download_prices(config)
