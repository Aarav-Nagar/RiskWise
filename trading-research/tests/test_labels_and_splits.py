from __future__ import annotations

import pandas as pd

from quant_ta.config import ResearchConfig
from quant_ta.labels import add_labels
from quant_ta.splits import chronological_split


def test_forward_labels_are_shifted_without_tail_leakage() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "ticker": ["AAPL"] * 5,
            "close": [100, 101, 99, 103, 102],
        }
    )
    labeled = add_labels(frame, (2,))

    assert round(labeled.loc[0, "future_return_2d"], 6) == -0.01
    assert labeled.loc[0, "label_2d"] == 0
    assert labeled.loc[1, "label_2d"] == 1
    assert pd.isna(labeled.loc[3, "label_2d"])
    assert pd.isna(labeled.loc[4, "label_2d"])


def test_chronological_splits_do_not_overlap() -> None:
    config = ResearchConfig()
    frame = pd.DataFrame({"date": pd.date_range("2022-12-30", "2024-01-03"), "x": 1})
    split = chronological_split(frame, config)

    assert split["train"]["date"].max() <= pd.Timestamp(config.train_end)
    assert split["validation"]["date"].min() >= pd.Timestamp(config.validation_start)
    assert split["validation"]["date"].max() <= pd.Timestamp(config.validation_end)
    assert split["test"]["date"].min() >= pd.Timestamp(config.test_start)
    assert set(split["train"].index).isdisjoint(split["validation"].index)
    assert set(split["validation"].index).isdisjoint(split["test"].index)
