from __future__ import annotations

import pandas as pd

from quant_ta.backtesting import backtest_one, probabilities_to_position
from quant_ta.config import ResearchConfig


def test_probability_thresholds_map_to_long_or_cash() -> None:
    probabilities = pd.Series([0.44, 0.45, 0.50, 0.55, 0.56])
    positions = probabilities_to_position(probabilities, long_threshold=0.55, cash_threshold=0.45)
    assert positions.tolist() == [0.0, 0.0, 0.0, 0.0, 1.0]


def test_transaction_cost_applies_on_position_changes_only() -> None:
    config = ResearchConfig(transaction_cost=0.001)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4, freq="D"),
            "probability": [0.60, 0.62, 0.40, 0.70],
            "return_1d": [0.01, 0.02, -0.01, 0.03],
        }
    )
    curve = backtest_one(frame, config)

    assert curve["turnover"].tolist() == [1.0, 0.0, 1.0, 1.0]
    assert curve["transaction_cost"].tolist() == [0.001, 0.0, 0.001, 0.001]
    assert round(curve.loc[1, "strategy_return"], 6) == 0.02
