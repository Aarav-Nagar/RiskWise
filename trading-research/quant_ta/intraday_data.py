from __future__ import annotations

import os
import time
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.io import read_frame, write_frame


def _normalize(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(-1):
            raw = raw.xs(ticker, axis=1, level=-1, drop_level=True)
        else:
            raw.columns = raw.columns.get_level_values(0)
    frame = raw.reset_index()
    frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
    time_col = "datetime" if "datetime" in frame.columns else frame.columns[0]
    frame = frame.rename(columns={time_col: "date"})
    if "adj_close" not in frame.columns and "close" in frame.columns:
        frame["adj_close"] = frame["close"]
    frame["ticker"] = ticker
    keep = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    frame = frame[keep].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    return frame


def _month_range(start: str, end: str) -> list[str]:
    months = pd.period_range(pd.Timestamp(start), pd.Timestamp(end), freq="M")
    return [str(month) for month in months]


def _normalize_alpha_vantage(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    frame = raw.copy()
    frame.columns = [str(column).lower().strip() for column in frame.columns]
    if "timestamp" not in frame.columns:
        return pd.DataFrame()
    frame = frame.rename(columns={"timestamp": "date"})
    frame["adj_close"] = frame["close"]
    frame["ticker"] = ticker
    keep = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    frame = frame[keep].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    return frame


def _download_alpha_vantage_month(ticker: str, month: str, config: IntradayConfig) -> pd.DataFrame:
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("ALPHAVANTAGE_API_KEY is not set.")
    cache_path = config.provider_cache_dir / "alphavantage" / f"{ticker}_{config.interval}_{month}.csv"
    if cache_path.exists():
        return read_frame(cache_path, parse_dates=["date"])

    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": ticker,
        "interval": config.interval,
        "month": month,
        "outputsize": "full",
        "datatype": "csv",
        "apikey": api_key,
    }
    response = _get_with_retries("https://www.alphavantage.co/query", params=params)
    response.raise_for_status()
    text = response.text.strip()
    if not text or text.startswith("{"):
        raise RuntimeError(f"Alpha Vantage did not return CSV data for {ticker} {month}: {text[:200]}")
    frame = _normalize_alpha_vantage(pd.read_csv(StringIO(text)), ticker)
    if frame.empty:
        raise RuntimeError(f"Alpha Vantage returned no normalized rows for {ticker} {month}.")
    write_frame(frame, cache_path)
    return frame


def _stockdata_interval(interval: str) -> str:
    return "minute" if interval in {"1m", "minute"} else interval


def _stockdata_chunks(start: str, end: str) -> list[tuple[str, str]]:
    chunks = []
    cursor = pd.Timestamp(start)
    final = pd.Timestamp(end)
    while cursor < final:
        chunk_end = min(cursor + pd.Timedelta(days=6), final)
        chunks.append((cursor.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cursor = chunk_end + pd.Timedelta(days=1)
    return chunks


def _normalize_stockdata(payload: dict, ticker: str) -> pd.DataFrame:
    rows = []
    for item in payload.get("data", []):
        values = item.get("data", {})
        if item.get("ticker", ticker).upper() != ticker.upper():
            continue
        rows.append(
            {
                "date": item.get("date"),
                "ticker": ticker,
                "open": values.get("open"),
                "high": values.get("high"),
                "low": values.get("low"),
                "close": values.get("close"),
                "adj_close": values.get("close"),
                "volume": values.get("volume"),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    return frame


def _download_stockdata_chunk(ticker: str, start: str, end: str, config: IntradayConfig) -> pd.DataFrame:
    api_key = os.getenv("STOCKDATA_API_KEY")
    if not api_key:
        raise RuntimeError("STOCKDATA_API_KEY is not set.")
    cache_path = config.provider_cache_dir / "stockdata" / f"{ticker}_{config.interval}_{start}_{end}.csv"
    if cache_path.exists():
        return read_frame(cache_path, parse_dates=["date"])
    params = {
        "api_token": api_key,
        "symbols": ticker,
        "interval": _stockdata_interval(config.interval),
        "date_from": start,
        "date_to": end,
        "sort": "asc",
        "extended_hours": "false",
    }
    response = _get_with_retries("https://api.stockdata.org/v1/data/intraday", params=params)
    response.raise_for_status()
    payload = response.json()
    if "data" not in payload:
        raise RuntimeError(f"StockData response for {ticker} {start}-{end} did not include data: {str(payload)[:200]}")
    frame = _normalize_stockdata(payload, ticker)
    if frame.empty:
        return frame
    write_frame(frame, cache_path)
    return frame


def _get_with_retries(url: str, params: dict, attempts: int = 4) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            time.sleep(2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def download_stockdata_intraday_prices(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    frames = []
    for ticker in config.tickers:
        for start, end in _stockdata_chunks(config.stockdata_start, config.stockdata_end):
            frame = _download_stockdata_chunk(ticker, start, end, config)
            if not frame.empty:
                frames.append(frame)
    if not frames:
        raise RuntimeError("StockData returned no intraday rows for the configured date range.")
    prices = clean_intraday_prices(pd.concat(frames, ignore_index=True))
    start = pd.Timestamp(config.stockdata_start)
    end = pd.Timestamp(config.stockdata_end) + pd.Timedelta(days=1)
    prices = prices[(prices["date"] >= start) & (prices["date"] < end)].copy()
    write_frame(prices, config.raw_dir / "prices_1m.csv")
    return prices


def download_alpha_vantage_intraday_prices(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    frames = []
    for ticker in config.tickers:
        for month in _month_range(config.historical_start, config.historical_end):
            frames.append(_download_alpha_vantage_month(ticker, month, config))
    prices = clean_intraday_prices(pd.concat(frames, ignore_index=True))
    start = pd.Timestamp(config.historical_start)
    end = pd.Timestamp(config.historical_end) + pd.Timedelta(days=1)
    prices = prices[(prices["date"] >= start) & (prices["date"] < end)].copy()
    write_frame(prices, config.raw_dir / "prices_1m.csv")
    return prices


def download_yahoo_intraday_prices(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    frames = []
    for ticker in config.tickers:
        raw = yf.download(ticker, period=config.period, interval=config.interval, auto_adjust=False, progress=False)
        normalized = _normalize(raw, ticker)
        if not normalized.empty:
            frames.append(normalized)
    if not frames:
        raise RuntimeError("No intraday bars were downloaded from Yahoo Finance.")
    prices = pd.concat(frames, ignore_index=True)
    prices = clean_intraday_prices(prices)
    write_frame(prices, config.raw_dir / "prices_1m.csv")
    return prices


def download_intraday_prices(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    if config.provider.lower() == "stockdata":
        return download_stockdata_intraday_prices(config)
    if config.provider.lower() == "alphavantage":
        return download_alpha_vantage_intraday_prices(config)
    if config.provider.lower() == "yahoo":
        return download_yahoo_intraday_prices(config)
    raise ValueError(f"Unknown intraday provider: {config.provider}")


def clean_intraday_prices(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["ticker"] = df["ticker"].str.upper()
    df = df.drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"])
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "ticker", "open", "high", "low", "close"])
    df = df[df["close"] > 0]
    df["volume"] = df["volume"].fillna(0)
    return df.reset_index(drop=True)


def load_intraday_prices(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    path = config.raw_dir / "prices_1m.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date"])
    return download_intraday_prices(config)
