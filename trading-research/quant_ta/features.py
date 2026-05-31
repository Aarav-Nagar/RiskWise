from __future__ import annotations

import numpy as np
import pandas as pd

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.data import load_prices
from quant_ta.io import read_frame, write_frame


MA_WINDOWS = (5, 10, 20, 30, 50, 100, 200)
RETURN_WINDOWS = (1, 5, 10, 20, 30, 60)
VOL_WINDOWS = (5, 20, 30, 60)
ROLL_WINDOWS = (20, 60)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window, min_periods=window).mean()
    rs = _safe_divide(gain, loss)
    return 100 - (100 / (1 + rs))


def _true_range(group: pd.DataFrame) -> pd.Series:
    previous_close = group["close"].shift(1)
    ranges = pd.concat(
        [
            group["high"] - group["low"],
            (group["high"] - previous_close).abs(),
            (group["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def _rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).apply(
        lambda values: pd.Series(values).rank(pct=True).iloc[-1],
        raw=False,
    )


def _features_for_ticker(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    close = group["close"]
    high = group["high"]
    low = group["low"]
    volume = group["volume"]

    group["return_1d"] = close.pct_change()
    group["log_return"] = np.log(close).diff()

    for window in RETURN_WINDOWS:
        group[f"return_{window}d"] = close.pct_change(window)
        group[f"roc_{window}d"] = close / close.shift(window) - 1

    for window in MA_WINDOWS:
        sma = close.rolling(window, min_periods=window).mean()
        ema = close.ewm(span=window, adjust=False, min_periods=window).mean()
        group[f"sma_{window}d"] = sma
        group[f"ema_{window}d"] = ema
        group[f"price_to_sma_{window}d"] = _safe_divide(close, sma) - 1
        group[f"price_to_ema_{window}d"] = _safe_divide(close, ema) - 1
        group[f"sma_slope_{window}d"] = sma.pct_change(5)
        group[f"ema_slope_{window}d"] = ema.pct_change(5)

    group["sma_20_50_cross"] = _safe_divide(group["sma_20d"], group["sma_50d"]) - 1
    group["ema_12_26_cross"] = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    group["trend_strength_20d"] = _safe_divide(close - close.shift(20), group["atr_14d"] if "atr_14d" in group else close.rolling(20).std())

    group["rsi_14d"] = _rsi(close, 14)
    low_14 = low.rolling(14, min_periods=14).min()
    high_14 = high.rolling(14, min_periods=14).max()
    group["stochastic_14d"] = _safe_divide(close - low_14, high_14 - low_14)
    ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    group["macd"] = ema_12 - ema_26
    group["macd_signal"] = group["macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    group["macd_histogram"] = group["macd"] - group["macd_signal"]

    true_range = _true_range(group)
    group["true_range"] = true_range
    group["atr_14d"] = true_range.rolling(14, min_periods=14).mean()

    for window in VOL_WINDOWS:
        group[f"volatility_{window}d"] = group["log_return"].rolling(window, min_periods=window).std()
        group[f"momentum_z_{window}d"] = _safe_divide(
            group[f"return_{min(window, 30)}d"] - group[f"return_{min(window, 30)}d"].rolling(window, min_periods=window).mean(),
            group[f"return_{min(window, 30)}d"].rolling(window, min_periods=window).std(),
        )

    rolling_mean = close.rolling(20, min_periods=20).mean()
    rolling_std = close.rolling(20, min_periods=20).std()
    upper = rolling_mean + 2 * rolling_std
    lower = rolling_mean - 2 * rolling_std
    group["bollinger_width_20d"] = _safe_divide(upper - lower, rolling_mean)
    group["bollinger_position_20d"] = _safe_divide(close - lower, upper - lower)
    donchian_high = high.rolling(20, min_periods=20).max()
    donchian_low = low.rolling(20, min_periods=20).min()
    group["donchian_position_20d"] = _safe_divide(close - donchian_low, donchian_high - donchian_low)
    group["parkinson_volatility_20d"] = np.sqrt(
        (np.log(high / low) ** 2).rolling(20, min_periods=20).mean() / (4 * np.log(2))
    )

    for window in ROLL_WINDOWS:
        price_mean = close.rolling(window, min_periods=window).mean()
        price_std = close.rolling(window, min_periods=window).std()
        return_mean = group["return_1d"].rolling(window, min_periods=window).mean()
        return_std = group["return_1d"].rolling(window, min_periods=window).std()
        rolling_high = close.rolling(window, min_periods=window).max()
        rolling_low = close.rolling(window, min_periods=window).min()
        group[f"price_z_{window}d"] = _safe_divide(close - price_mean, price_std)
        group[f"return_z_{window}d"] = _safe_divide(group["return_1d"] - return_mean, return_std)
        group[f"skew_{window}d"] = group["return_1d"].rolling(window, min_periods=window).skew()
        group[f"kurtosis_{window}d"] = group["return_1d"].rolling(window, min_periods=window).kurt()
        group[f"drawdown_{window}d"] = close / rolling_high - 1
        group[f"distance_from_high_{window}d"] = close / rolling_high - 1
        group[f"distance_from_low_{window}d"] = close / rolling_low - 1
        group[f"price_percentile_{window}d"] = _rolling_percentile(close, window)
        group[f"return_percentile_{window}d"] = _rolling_percentile(group["return_1d"], window)

    group["volume_z_20d"] = _safe_divide(volume - volume.rolling(20, min_periods=20).mean(), volume.rolling(20, min_periods=20).std())
    group["volume_change_5d"] = volume.pct_change(5)
    group["price_volume_corr_20d"] = group["return_1d"].rolling(20, min_periods=20).corr(volume.pct_change())
    direction = np.sign(close.diff()).fillna(0)
    group["obv"] = (direction * volume).cumsum()
    group["obv_change_20d"] = group["obv"].pct_change(20)
    group["volume_adjusted_momentum_20d"] = group["return_20d"] * group["volume_z_20d"]
    return group


def add_market_relative_features(features: pd.DataFrame, benchmark: str) -> pd.DataFrame:
    df = features.copy()
    spy = df[df["ticker"] == benchmark][["date", "return_1d", "return_20d"]].rename(
        columns={"return_1d": "spy_return_1d", "return_20d": "spy_return_20d"}
    )
    df = df.merge(spy, on="date", how="left")
    df["relative_return_1d_spy"] = df["return_1d"] - df["spy_return_1d"]
    df["relative_momentum_20d_spy"] = df["return_20d"] - df["spy_return_20d"]

    pieces = []
    for _, group in df.groupby("ticker", group_keys=False):
        group = group.sort_values("date").copy()
        covariance = group["return_1d"].rolling(60, min_periods=60).cov(group["spy_return_1d"])
        variance = group["spy_return_1d"].rolling(60, min_periods=60).var()
        group["beta_60d_spy"] = covariance / variance.replace(0, np.nan)
        group["corr_60d_spy"] = group["return_1d"].rolling(60, min_periods=60).corr(group["spy_return_1d"])
        group["alpha_60d_spy"] = group["return_1d"].rolling(60, min_periods=60).mean() - group["beta_60d_spy"] * group["spy_return_1d"].rolling(60, min_periods=60).mean()
        pieces.append(group)
    return pd.concat(pieces).sort_values(["ticker", "date"]).reset_index(drop=True)


def build_features(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    prices = load_prices(config)
    features = pd.concat(
        [_features_for_ticker(group) for _, group in prices.groupby("ticker", group_keys=False)],
        ignore_index=True,
    )
    features = add_market_relative_features(features, config.benchmark)
    write_frame(features, config.processed_dir / "features.csv")
    return features


def load_features(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    path = config.processed_dir / "features.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date"])
    return build_features(config)
