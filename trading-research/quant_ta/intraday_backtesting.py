from __future__ import annotations

import numpy as np
import pandas as pd

from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_models import load_intraday_predictions
from quant_ta.io import write_frame


def run_intraday_backtests(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    predictions = load_intraday_predictions(config)
    predictions = predictions[predictions["split"] == "test"].copy()
    curves = []
    metrics = []
    for (horizon, model, ticker), group in predictions.groupby(["horizon", "model", "ticker"]):
        group = group.sort_values("date").copy()
        group["position"] = 0.0
        group.loc[group["probability"] > config.long_threshold, "position"] = 1.0
        group["previous_position"] = group["position"].shift(1).fillna(0)
        group["turnover"] = (group["position"] - group["previous_position"]).abs()
        group["transaction_cost"] = group["turnover"] * config.transaction_cost
        group["strategy_return"] = group["previous_position"] * group["minute_return"].fillna(0) - group["transaction_cost"]
        group["equity"] = config.initial_capital * (1 + group["strategy_return"]).cumprod()
        group["drawdown"] = group["equity"] / group["equity"].cummax() - 1
        curves.append(group)

        returns = group["strategy_return"].fillna(0)
        active = returns[group["previous_position"] > 0]
        scale = np.sqrt(252 * 390)
        sharpe = returns.mean() / returns.std() * scale if returns.std() > 0 else np.nan
        metrics.append(
            {
                "horizon": horizon,
                "model": model,
                "ticker": ticker,
                "cumulative_return": group["equity"].iloc[-1] / group["equity"].iloc[0] - 1 if len(group) > 1 else 0,
                "sharpe": sharpe,
                "max_drawdown": group["drawdown"].min(),
                "win_rate": float((active > 0).mean()) if len(active) else np.nan,
                "average_return_per_trade": float(active.mean()) if len(active) else np.nan,
                "turnover": group["turnover"].sum(),
                "number_of_trades": int((group["turnover"] > 0).sum()),
                "transaction_cost_drag": group["transaction_cost"].sum(),
            }
        )

    curves_df = pd.concat(curves, ignore_index=True)
    metrics_df = pd.DataFrame(metrics).sort_values(["horizon", "model", "ticker"])
    aggregate = metrics_df.groupby(["horizon", "model"], as_index=False).mean(numeric_only=True)
    write_frame(curves_df, config.backtest_dir / "equity_curves.csv")
    write_frame(metrics_df, config.backtest_dir / "backtest_metrics.csv")
    write_frame(aggregate, config.backtest_dir / "backtest_metrics_aggregate.csv")
    return metrics_df
