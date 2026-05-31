from __future__ import annotations

import pandas as pd

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.features import load_features
from quant_ta.io import read_frame, write_frame


def add_labels(features: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    pieces = []
    for _, group in features.groupby("ticker", group_keys=False):
        group = group.sort_values("date").copy()
        for horizon in horizons:
            future_return = group["close"].shift(-horizon) / group["close"] - 1
            group[f"future_return_{horizon}d"] = future_return
            group[f"label_{horizon}d"] = (future_return > 0).astype("Int64")
            group.loc[future_return.isna(), f"label_{horizon}d"] = pd.NA
        pieces.append(group)
    return pd.concat(pieces).sort_values(["ticker", "date"]).reset_index(drop=True)


def build_labeled_dataset(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    labeled = add_labels(load_features(config), config.horizons)
    write_frame(labeled, config.processed_dir / "labeled_dataset.csv")
    return labeled


def load_labeled_dataset(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    path = config.processed_dir / "labeled_dataset.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date"])
    return build_labeled_dataset(config)
