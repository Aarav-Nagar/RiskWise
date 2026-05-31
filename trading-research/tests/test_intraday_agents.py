from __future__ import annotations

import pandas as pd

from quant_ta.intraday_agents import _weights_for_topk_agent
from quant_ta.intraday_config import IntradayConfig
from quant_ta.intraday_data import _month_range, _stockdata_chunks
from quant_ta.intraday_labels import add_intraday_labels
from quant_ta.intraday_models import split_intraday


def test_expanded_intraday_horizons_drop_unavailable_tail_rows() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01 09:30", periods=6, freq="min"),
            "ticker": ["AAPL"] * 6,
            "close": [100, 101, 102, 103, 104, 105],
        }
    )
    labeled = add_intraday_labels(frame, (1, 3, 5))

    assert labeled["label_1m"].isna().sum() == 1
    assert labeled["label_3m"].isna().sum() == 3
    assert labeled["label_5m"].isna().sum() == 5
    assert labeled.loc[0, "label_5m"] == 1


def test_topk_agent_respects_k_and_max_position_size() -> None:
    config = IntradayConfig(top_k=3, max_position_size=0.35)
    step = pd.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"],
            "probability": [0.80, 0.70, 0.60, 0.59, 0.40],
        }
    )
    weights = _weights_for_topk_agent(step, threshold=0.55, config=config)

    assert len(weights) == 3
    assert set(weights) == {"AAPL", "MSFT", "NVDA"}
    assert max(weights.values()) <= 0.35
    assert sum(weights.values()) <= 1.0


def test_intraday_split_uses_configured_test_window_when_available() -> None:
    config = IntradayConfig(test_start="2026-01-01", test_end="2026-01-03")
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-12-28", "2026-01-04", freq="h"),
            "ticker": "AAPL",
            "label_1m": 1,
        }
    )
    split = split_intraday(frame, config)

    assert split["train"]["date"].max() < pd.Timestamp("2026-01-01")
    assert split["validation"]["date"].max() < pd.Timestamp("2026-01-01")
    assert split["test"]["date"].min() >= pd.Timestamp("2026-01-01")
    assert split["test"]["date"].max() < pd.Timestamp("2026-01-04")


def test_month_range_includes_start_and_end_months() -> None:
    assert _month_range("2025-07-01", "2026-05-01") == [
        "2025-07",
        "2025-08",
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
    ]


def test_stockdata_chunks_respect_seven_day_limit() -> None:
    assert _stockdata_chunks("2026-04-14", "2026-05-01") == [
        ("2026-04-14", "2026-04-20"),
        ("2026-04-21", "2026-04-27"),
        ("2026-04-28", "2026-05-01"),
    ]
