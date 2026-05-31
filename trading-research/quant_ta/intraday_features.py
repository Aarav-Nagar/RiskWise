from __future__ import annotations

import numpy as np
import pandas as pd

from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_data import load_intraday_prices
from quant_ta.io import read_frame, write_frame


def _safe_divide(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window, min_periods=window).mean()
    rs = _safe_divide(gain, loss)
    return 100 - 100 / (1 + rs)


def _intraday_for_ticker(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    open_ = group["open"]
    high = group["high"]
    low = group["low"]
    close = group["close"]
    volume = group["volume"]
    body = close - open_
    body_abs = body.abs()
    candle_range = (high - low).replace(0, np.nan)
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low

    group["minute_return"] = close.pct_change()
    group["log_return"] = np.log(close).diff()
    for window in (3, 5, 10, 15, 30, 60):
        group[f"return_{window}m"] = close.pct_change(window)
        group[f"volatility_{window}m"] = group["log_return"].rolling(window, min_periods=window).std()
        group[f"volume_z_{window}m"] = _safe_divide(volume - volume.rolling(window, min_periods=window).mean(), volume.rolling(window, min_periods=window).std())

    for window in (5, 10, 20, 50):
        sma = close.rolling(window, min_periods=window).mean()
        ema = close.ewm(span=window, adjust=False, min_periods=window).mean()
        group[f"sma_{window}m"] = sma
        group[f"ema_{window}m"] = ema
        group[f"price_to_sma_{window}m"] = _safe_divide(close, sma) - 1
        group[f"price_to_ema_{window}m"] = _safe_divide(close, ema) - 1

    group["ema_9_21_cross"] = _safe_divide(group["ema_9m"] if "ema_9m" in group else close.ewm(span=9).mean(), close.ewm(span=21).mean()) - 1
    ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    group["macd"] = ema_12 - ema_26
    group["macd_signal"] = group["macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    group["macd_histogram"] = group["macd"] - group["macd_signal"]
    group["rsi_14m"] = _rsi(close, 14)
    low_14 = low.rolling(14, min_periods=14).min()
    high_14 = high.rolling(14, min_periods=14).max()
    group["stochastic_14m"] = _safe_divide(close - low_14, high_14 - low_14)

    true_range = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    group["true_range"] = true_range
    group["atr_14m"] = true_range.rolling(14, min_periods=14).mean()

    rolling_mean = close.rolling(20, min_periods=20).mean()
    rolling_std = close.rolling(20, min_periods=20).std()
    upper = rolling_mean + 2 * rolling_std
    lower = rolling_mean - 2 * rolling_std
    group["bollinger_position_20m"] = _safe_divide(close - lower, upper - lower)
    group["bollinger_width_20m"] = _safe_divide(upper - lower, rolling_mean)

    group["candle_body_pct"] = _safe_divide(body_abs, candle_range)
    group["upper_wick_pct"] = _safe_divide(upper_wick, candle_range)
    group["lower_wick_pct"] = _safe_divide(lower_wick, candle_range)
    group["is_green"] = (body > 0).astype(int)
    group["doji"] = (group["candle_body_pct"] < 0.1).astype(int)
    group["hammer"] = ((group["lower_wick_pct"] > 0.55) & (group["upper_wick_pct"] < 0.2) & (group["candle_body_pct"] < 0.35)).astype(int)
    group["shooting_star"] = ((group["upper_wick_pct"] > 0.55) & (group["lower_wick_pct"] < 0.2) & (group["candle_body_pct"] < 0.35)).astype(int)
    previous_open = open_.shift(1)
    previous_close = close.shift(1)
    previous_body = previous_close - previous_open
    group["bullish_engulfing"] = ((previous_body < 0) & (body > 0) & (open_ <= previous_close) & (close >= previous_open)).astype(int)
    group["bearish_engulfing"] = ((previous_body > 0) & (body < 0) & (open_ >= previous_close) & (close <= previous_open)).astype(int)
    group["inside_bar"] = ((high < high.shift(1)) & (low > low.shift(1))).astype(int)
    group["breakout_20m"] = (close > high.shift(1).rolling(20, min_periods=20).max()).astype(int)
    group["breakdown_20m"] = (close < low.shift(1).rolling(20, min_periods=20).min()).astype(int)
    group["vwap_session"] = (close * volume).groupby(group["date"].dt.date).cumsum() / volume.groupby(group["date"].dt.date).cumsum().replace(0, np.nan)
    group["price_to_vwap"] = _safe_divide(close, group["vwap_session"]) - 1
    group["minute_of_day"] = group["date"].dt.hour * 60 + group["date"].dt.minute
    group["open_30m"] = (group["minute_of_day"] < 10 * 60).astype(int)
    group["close_30m"] = (group["minute_of_day"] >= 15 * 60 + 30).astype(int)
    return group


def build_intraday_features(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    prices = load_intraday_prices(config)
    features = pd.concat([_intraday_for_ticker(group) for _, group in prices.groupby("ticker")], ignore_index=True)
    write_frame(features, config.processed_dir / "features_1m.csv")
    return features


def load_intraday_features(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    path = config.processed_dir / "features_1m.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date"])
    return build_intraday_features(config)
