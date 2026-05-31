from __future__ import annotations

import pandas as pd
import numpy as np

from quant_ta.config import CONFIG, ResearchConfig


def chronological_split(df: pd.DataFrame, config: ResearchConfig = CONFIG) -> dict[str, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(config.train_end)].copy()
    validation = df[
        (df["date"] >= pd.Timestamp(config.validation_start))
        & (df["date"] <= pd.Timestamp(config.validation_end))
    ].copy()
    test = df[df["date"] >= pd.Timestamp(config.test_start)].copy()
    return {"train": train, "validation": validation, "test": test}


def feature_columns(df: pd.DataFrame, horizons: tuple[int, ...] = CONFIG.horizons) -> list[str]:
    excluded = {
        "date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "spy_return_1d",
        "spy_return_20d",
    }
    for horizon in horizons:
        excluded.add(f"future_return_{horizon}d")
        excluded.add(f"label_{horizon}d")
    numeric = df.select_dtypes(include=["number", "bool"]).columns
    return [column for column in numeric if column not in excluded]


def horizon_dataset(df: pd.DataFrame, horizon: int, config: ResearchConfig = CONFIG) -> tuple[pd.DataFrame, list[str], str]:
    label = f"label_{horizon}d"
    data = df[(df["ticker"] != config.benchmark) & df[label].notna()].copy()
    columns = feature_columns(data, config.horizons)
    data[columns] = data[columns].replace([np.inf, -np.inf], np.nan)
    data = data.dropna(subset=[label])
    return data, columns, label
