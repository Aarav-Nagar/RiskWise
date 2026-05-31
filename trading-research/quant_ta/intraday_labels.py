from __future__ import annotations

import pandas as pd

from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_features import load_intraday_features
from quant_ta.io import read_frame, write_frame


def add_intraday_labels(features: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    pieces = []
    for _, group in features.groupby("ticker"):
        group = group.sort_values("date").copy()
        for horizon in horizons:
            future_return = group["close"].shift(-horizon) / group["close"] - 1
            group[f"future_return_{horizon}m"] = future_return
            group[f"label_{horizon}m"] = (future_return > 0).astype("Int64")
            group.loc[future_return.isna(), f"label_{horizon}m"] = pd.NA
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True).sort_values(["ticker", "date"]).reset_index(drop=True)


def build_intraday_labeled_dataset(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    labeled = add_intraday_labels(load_intraday_features(config), config.horizons)
    write_frame(labeled, config.processed_dir / "labeled_dataset_1m.csv")
    return labeled


def load_intraday_labeled_dataset(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    path = config.processed_dir / "labeled_dataset_1m.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date"])
    return build_intraday_labeled_dataset(config)
