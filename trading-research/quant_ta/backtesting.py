from __future__ import annotations

import numpy as np
import pandas as pd

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.io import write_frame
from quant_ta.models import load_predictions


def probabilities_to_position(probabilities: pd.Series, long_threshold: float, cash_threshold: float) -> pd.Series:
    positions = pd.Series(0.0, index=probabilities.index)
    positions[probabilities > long_threshold] = 1.0
    positions[probabilities < cash_threshold] = 0.0
    return positions


def backtest_one(group: pd.DataFrame, config: ResearchConfig = CONFIG) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    group["position"] = probabilities_to_position(group["probability"], config.long_threshold, config.cash_threshold)
    group["previous_position"] = group["position"].shift(1).fillna(0)
    group["turnover"] = (group["position"] - group["previous_position"]).abs()
    group["transaction_cost"] = group["turnover"] * config.transaction_cost
    group["strategy_return"] = group["previous_position"] * group["return_1d"].fillna(0) - group["transaction_cost"]
    group["benchmark_return"] = group["return_1d"].fillna(0)
    group["equity"] = config.initial_capital * (1 + group["strategy_return"]).cumprod()
    group["benchmark_equity"] = config.initial_capital * (1 + group["benchmark_return"]).cumprod()
    group["drawdown"] = group["equity"] / group["equity"].cummax() - 1
    return group


def performance_metrics(curve: pd.DataFrame) -> dict[str, float]:
    returns = curve["strategy_return"].fillna(0)
    active_returns = returns[curve["previous_position"] > 0]
    years = max((curve["date"].max() - curve["date"].min()).days / 365.25, 1 / 252)
    cumulative_return = curve["equity"].iloc[-1] / curve["equity"].iloc[0] - 1 if len(curve) > 1 else 0
    annualized_return = (1 + cumulative_return) ** (1 / years) - 1
    annualized_volatility = returns.std() * np.sqrt(252)
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else np.nan
    trade_count = int((curve["turnover"] > 0).sum())
    return {
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe": sharpe,
        "max_drawdown": curve["drawdown"].min(),
        "win_rate": float((active_returns > 0).mean()) if len(active_returns) else np.nan,
        "average_return_per_trade": float(active_returns.mean()) if len(active_returns) else np.nan,
        "volatility_adjusted_return": annualized_return / annualized_volatility if annualized_volatility > 0 else np.nan,
        "turnover": curve["turnover"].sum(),
        "number_of_trades": trade_count,
        "transaction_cost_drag": curve["transaction_cost"].sum(),
    }


def run_backtests(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    predictions = load_predictions(config)
    predictions = predictions[predictions["split"] == "test"].copy()
    curves = []
    metrics = []
    for (horizon, model, ticker), group in predictions.groupby(["horizon", "model", "ticker"]):
        curve = backtest_one(group, config)
        curves.append(curve)
        row = performance_metrics(curve)
        row.update({"horizon": horizon, "model": model, "ticker": ticker})
        metrics.append(row)

    curves_df = pd.concat(curves).reset_index(drop=True) if curves else pd.DataFrame()
    metrics_df = pd.DataFrame(metrics).sort_values(["horizon", "model", "ticker"]).reset_index(drop=True)
    write_frame(curves_df, config.backtest_dir / "equity_curves.csv")
    write_frame(metrics_df, config.backtest_dir / "backtest_metrics.csv")
    aggregate = metrics_df.groupby(["horizon", "model"], as_index=False).mean(numeric_only=True)
    write_frame(aggregate, config.backtest_dir / "backtest_metrics_aggregate.csv")
    return metrics_df
