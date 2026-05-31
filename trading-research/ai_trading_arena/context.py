from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from .config import ArenaConfig, DEFAULT_CONFIG


SECTOR_MAP: dict[str, str] = {
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "NVDA": "Information Technology",
    "AMD": "Information Technology",
    "AVGO": "Information Technology",
    "PLTR": "Information Technology",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "COST": "Consumer Staples",
    "WMT": "Consumer Staples",
    "PG": "Consumer Staples",
    "PEP": "Consumer Staples",
    "KO": "Consumer Staples",
    "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary",
    "JPM": "Financials",
    "BAC": "Financials",
    "V": "Financials",
    "MA": "Financials",
    "XOM": "Energy",
    "UNH": "Health Care",
    "LLY": "Health Care",
    "JNJ": "Health Care",
    "MRK": "Health Care",
    "ABBV": "Health Care",
    "PFE": "Health Care",
    "SPY": "Benchmark",
    "QQQ": "Information Technology",
}

SECTOR_ETFS: dict[str, str] = {
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Financials": "XLF",
    "Energy": "XLE",
    "Communication Services": "XLC",
}


def _rank01(series: pd.Series) -> pd.Series:
    return series.rank(pct=True).fillna(0.5)


def _sector_rotation_scores(signal_date: pd.Timestamp) -> dict[str, float]:
    tickers = sorted(set(SECTOR_ETFS.values()) | {"SPY"})
    start = signal_date - pd.Timedelta(days=120)
    try:
        raw = yf.download(
            tickers,
            start=start.strftime("%Y-%m-%d"),
            end=(signal_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception:
        return {sector: 0.5 for sector in SECTOR_ETFS}
    if raw.empty:
        return {sector: 0.5 for sector in SECTOR_ETFS}
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
    returns = close.pct_change(20).dropna()
    if returns.empty or "SPY" not in returns.columns:
        return {sector: 0.5 for sector in SECTOR_ETFS}
    latest = returns.iloc[-1]
    relative = latest.drop(labels=["SPY"], errors="ignore") - latest.get("SPY", 0.0)
    ranked = _rank01(relative)
    return {sector: float(ranked.get(etf, 0.5)) for sector, etf in SECTOR_ETFS.items()}


def _liquidity_context(prices: pd.DataFrame, signal_date: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    usable = prices.loc[prices["date"] <= signal_date].copy()
    for ticker, group in usable.groupby("ticker"):
        group = group.sort_values("date").tail(60)
        if len(group) < 20:
            continue
        volume = group["volume"].astype(float)
        close = group["close"].astype(float)
        volume_std = volume.rolling(20).std().iloc[-1]
        volume_z = (volume.iloc[-1] - volume.rolling(20).mean().iloc[-1]) / volume_std if volume_std and not np.isnan(volume_std) else 0.0
        dollar_volume = float((close.iloc[-1] * volume.iloc[-1]) / 1_000_000)
        rows.append(
            {
                "ticker": ticker,
                "liquidity_score": float(np.clip(_sigmoid(volume_z), 0, 1)),
                "liquidity_shock_score": float(np.clip(abs(volume_z) / 4, 0, 1)),
                "dollar_volume_millions": dollar_volume,
            }
        )
    return pd.DataFrame(rows)


def _sigmoid(value: float) -> float:
    return 1 / (1 + np.exp(-value))


def _news_score(ticker: str, signal_date: pd.Timestamp) -> tuple[float, int]:
    try:
        news = yf.Ticker(ticker).news or []
    except Exception:
        return 0.5, 0
    if not news:
        return 0.5, 0
    end = signal_date + pd.Timedelta(days=1)
    count = 0
    positive = 0
    negative = 0
    pos_words = ("beat", "raises", "upgrade", "record", "growth", "approval", "wins", "surge", "strong")
    neg_words = ("miss", "cut", "downgrade", "probe", "lawsuit", "delay", "fall", "weak", "warning")
    for item in news[:20]:
        provider_time = item.get("providerPublishTime") or item.get("content", {}).get("pubDate")
        if isinstance(provider_time, int):
            published = pd.Timestamp(datetime.fromtimestamp(provider_time, tz=timezone.utc)).tz_localize(None)
        else:
            published = pd.to_datetime(provider_time, errors="coerce")
            if pd.isna(published):
                continue
            published = published.tz_localize(None) if published.tzinfo else published
        if published > end:
            continue
        title = str(item.get("title") or item.get("content", {}).get("title") or "").lower()
        count += 1
        positive += int(any(word in title for word in pos_words))
        negative += int(any(word in title for word in neg_words))
    if count == 0:
        return 0.5, 0
    raw = 0.5 + 0.12 * (positive - negative)
    return float(np.clip(raw, 0, 1)), count


def _earnings_score(ticker: str, signal_date: pd.Timestamp) -> tuple[float, float]:
    try:
        calendar = yf.Ticker(ticker).calendar
    except Exception:
        return 0.5, np.nan
    if calendar is None or len(calendar) == 0:
        return 0.5, np.nan
    dates: list[pd.Timestamp] = []
    if isinstance(calendar, dict):
        value = calendar.get("Earnings Date") or calendar.get("EarningsDate")
        if isinstance(value, (list, tuple)):
            dates = [pd.to_datetime(v, errors="coerce") for v in value]
        else:
            dates = [pd.to_datetime(value, errors="coerce")]
    elif isinstance(calendar, pd.DataFrame):
        flat = calendar.stack().reset_index(drop=True)
        dates = [pd.to_datetime(value, errors="coerce") for value in flat if "earn" in str(value).lower() or pd.notna(pd.to_datetime(value, errors="coerce"))]
    clean = [date.tz_localize(None) if getattr(date, "tzinfo", None) else date for date in dates if pd.notna(date)]
    if not clean:
        return 0.5, np.nan
    days = min(abs((date.normalize() - signal_date.normalize()).days) for date in clean)
    proximity = float(np.clip(1 - days / 21, 0, 1))
    return proximity, float(days)


def _options_score(ticker: str) -> dict[str, float | str]:
    try:
        ticker_obj = yf.Ticker(ticker)
        expirations = ticker_obj.options
        if not expirations:
            return {"options_sentiment_score": 0.5, "put_call_oi_ratio": np.nan, "iv_skew": np.nan, "options_expiration": ""}
        expiration = expirations[0]
        chain = ticker_obj.option_chain(expiration)
    except Exception:
        return {"options_sentiment_score": 0.5, "put_call_oi_ratio": np.nan, "iv_skew": np.nan, "options_expiration": ""}
    calls = chain.calls
    puts = chain.puts
    call_oi = float(calls.get("openInterest", pd.Series(dtype=float)).fillna(0).sum())
    put_oi = float(puts.get("openInterest", pd.Series(dtype=float)).fillna(0).sum())
    ratio = put_oi / call_oi if call_oi > 0 else np.nan
    call_iv = float(calls.get("impliedVolatility", pd.Series(dtype=float)).replace(0, np.nan).median())
    put_iv = float(puts.get("impliedVolatility", pd.Series(dtype=float)).replace(0, np.nan).median())
    skew = put_iv - call_iv if pd.notna(call_iv) and pd.notna(put_iv) else np.nan
    sentiment = 0.5
    if pd.notna(ratio):
        sentiment += float(np.clip((1.0 - ratio) / 2, -0.25, 0.25))
    if pd.notna(skew):
        sentiment -= float(np.clip(skew, -0.15, 0.15))
    return {
        "options_sentiment_score": float(np.clip(sentiment, 0, 1)),
        "put_call_oi_ratio": ratio,
        "iv_skew": skew,
        "options_expiration": expiration,
    }


def build_context_panel(
    prices: pd.DataFrame,
    signal_date: pd.Timestamp,
    config: ArenaConfig = DEFAULT_CONFIG,
    include_slow_context: bool = True,
    include_options: bool = False,
) -> pd.DataFrame:
    liquidity = _liquidity_context(prices, signal_date)
    rotation = _sector_rotation_scores(signal_date)
    records: list[dict[str, object]] = []
    for ticker in config.universe:
        if ticker in {"SPY", "QQQ"}:
            continue
        sector = SECTOR_MAP.get(ticker, "Other")
        news_score, news_count = (0.5, 0)
        earnings_score, earnings_days = (0.5, np.nan)
        if include_slow_context:
            news_score, news_count = _news_score(ticker, signal_date)
            earnings_score, earnings_days = _earnings_score(ticker, signal_date)
        options = _options_score(ticker) if include_options else {
            "options_sentiment_score": 0.5,
            "put_call_oi_ratio": np.nan,
            "iv_skew": np.nan,
            "options_expiration": "",
        }
        records.append(
            {
                "ticker": ticker,
                "sector": sector,
                "sector_rotation_score": rotation.get(sector, 0.5),
                "news_score": news_score,
                "news_count": news_count,
                "earnings_proximity_score": earnings_score,
                "days_to_or_from_earnings": earnings_days,
                **options,
            }
        )
    panel = pd.DataFrame(records)
    if not liquidity.empty:
        panel = panel.merge(liquidity, on="ticker", how="left")
    for column in [
        "sector_rotation_score",
        "news_score",
        "earnings_proximity_score",
        "options_sentiment_score",
        "liquidity_score",
        "liquidity_shock_score",
    ]:
        if column in panel:
            panel[column] = panel[column].fillna(0.5)
    return panel


def enrich_scores_with_context(
    scores: pd.DataFrame,
    prices: pd.DataFrame,
    signal_date: pd.Timestamp,
    config: ArenaConfig = DEFAULT_CONFIG,
    include_slow_context: bool = True,
    include_options: bool = True,
) -> pd.DataFrame:
    context = build_context_panel(prices, signal_date, config, include_slow_context, include_options)
    if scores.empty:
        return context
    existing = [column for column in context.columns if column in scores.columns and column != "ticker"]
    base = scores.drop(columns=existing, errors="ignore")
    return base.merge(context, on="ticker", how="outer")
