from __future__ import annotations

import pandas as pd

from quant_ta.features import add_market_relative_features


def test_spy_relative_features_align_by_date() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
            "ticker": ["SPY", "SPY", "AAPL", "AAPL"],
            "return_1d": [0.01, 0.02, 0.03, -0.01],
            "return_20d": [0.05, 0.06, 0.07, 0.01],
        }
    )
    result = add_market_relative_features(frame, "SPY")
    aapl = result[result["ticker"] == "AAPL"].sort_values("date")

    assert aapl["relative_return_1d_spy"].round(6).tolist() == [0.02, -0.03]
    assert aapl["relative_momentum_20d_spy"].round(6).tolist() == [0.02, -0.05]
