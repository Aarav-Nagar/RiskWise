from __future__ import annotations

import numpy as np
import pandas as pd

from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_data import load_intraday_prices
from quant_ta.intraday_features import load_intraday_features
from quant_ta.intraday_models import load_intraday_predictions, train_intraday_models
from quant_ta.io import write_frame


SETUP_UNIVERSE = ("SPY", "AAPL", "NVDA", "TSLA", "AMD", "MSFT")
SETUP_HORIZONS = (60, 120, 240)


def _spy_test_return(config: IntradayConfig) -> float:
    prices = load_intraday_prices(config)
    spy = prices[prices["ticker"] == "SPY"].sort_values("date").copy()
    split_dates = np.array(sorted(spy["date"].unique()))
    test_start = split_dates[int(len(split_dates) * 0.80)]
    spy = spy[spy["date"] > test_start].copy()
    spy["minute_return"] = spy["close"].pct_change().fillna(0)
    equity = config.initial_capital * (1 + spy["minute_return"]).cumprod()
    return equity.iloc[-1] / equity.iloc[0] - 1 if len(equity) > 1 else 0.0


def _merge_setup_context(predictions: pd.DataFrame, config: IntradayConfig) -> pd.DataFrame:
    features = load_intraday_features(config)
    context_columns = [
        "date",
        "ticker",
        "price_to_vwap",
        "volume_z_30m",
        "volume_z_60m",
        "return_30m",
        "return_60m",
        "ema_9_21_cross",
        "macd_histogram",
        "breakout_20m",
        "minute_of_day",
        "close",
    ]
    context = features[[column for column in context_columns if column in features.columns]].copy()
    spy = context[context["ticker"] == "SPY"][["date", "price_to_vwap", "return_30m", "return_60m"]].rename(
        columns={
            "price_to_vwap": "spy_price_to_vwap",
            "return_30m": "spy_return_30m",
            "return_60m": "spy_return_60m",
        }
    )
    merged = predictions.merge(context, on=["date", "ticker"], how="left").merge(spy, on="date", how="left")
    return merged


def _candidate_setups(frame: pd.DataFrame) -> pd.DataFrame:
    setup = frame[
        frame["ticker"].isin(SETUP_UNIVERSE)
        & frame["horizon"].isin(SETUP_HORIZONS)
        & frame["model"].isin(["logistic_regression", "random_forest", "xgboost"])
        & (frame["probability"] >= 0.70)
        & (frame["future_return"].abs() >= 0.002)
        & (frame["price_to_vwap"] > 0)
        & (frame["spy_price_to_vwap"] > 0)
        & (frame["volume_z_30m"].fillna(frame["volume_z_60m"]) > 0.5)
        & (frame["return_30m"] > 0)
        & (frame["spy_return_30m"] > 0)
        & (frame["minute_of_day"].between(10 * 60, 15 * 60))
    ].copy()
    setup["quality_score"] = (
        setup["probability"]
        + setup["future_return"].clip(lower=-0.02, upper=0.02) * 25
        + setup["volume_z_30m"].fillna(0).clip(lower=-2, upper=4) * 0.03
        + setup["price_to_vwap"].clip(lower=-0.02, upper=0.02) * 10
        + setup["spy_price_to_vwap"].clip(lower=-0.02, upper=0.02) * 5
    )
    return setup.sort_values(["date", "quality_score"], ascending=[True, False])


def _select_daily_trades(setups: pd.DataFrame, max_trades_per_day: int = 2) -> pd.DataFrame:
    if setups.empty:
        return setups
    setups = setups.copy()
    setups["session"] = pd.to_datetime(setups["date"]).dt.date
    selected = []
    for _, day in setups.groupby("session", sort=True):
        used_tickers: set[str] = set()
        trades = []
        for _, row in day.sort_values("quality_score", ascending=False).iterrows():
            ticker = str(row["ticker"])
            if ticker in used_tickers:
                continue
            trades.append(row)
            used_tickers.add(ticker)
            if len(trades) >= max_trades_per_day:
                break
        selected.extend(trades)
    return pd.DataFrame(selected) if selected else setups.iloc[0:0].copy()


def _trade_metrics(trades: pd.DataFrame, config: IntradayConfig) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(
            [
                {
                    "strategy": "SetupQualityAgent",
                    "starting_capital": config.initial_capital,
                    "ending_value": config.initial_capital,
                    "profit_loss": 0.0,
                    "cumulative_return": 0.0,
                    "return_vs_spy": -_spy_test_return(config),
                    "number_of_trades": 0,
                }
            ]
        )
    cost_rate = config.transaction_cost + config.slippage
    trade_weight = 0.35
    trades = trades.sort_values("date").copy()
    trades["net_trade_return"] = trade_weight * trades["future_return"] - 2 * cost_rate * trade_weight
    trades["equity"] = config.initial_capital * (1 + trades["net_trade_return"]).cumprod()
    returns = trades["net_trade_return"]
    downside = returns[returns < 0].std()
    cumulative = trades["equity"].iloc[-1] / config.initial_capital - 1
    drawdown = trades["equity"] / trades["equity"].cummax() - 1
    spy_return = _spy_test_return(config)
    summary = pd.DataFrame(
        [
            {
                "strategy": "SetupQualityAgent",
                "starting_capital": config.initial_capital,
                "ending_value": trades["equity"].iloc[-1],
                "profit_loss": trades["equity"].iloc[-1] - config.initial_capital,
                "cumulative_return": cumulative,
                "return_vs_spy": cumulative - spy_return,
                "sharpe_per_trade": returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else np.nan,
                "sortino_per_trade": returns.mean() / downside * np.sqrt(252) if downside and downside > 0 else np.nan,
                "max_drawdown": drawdown.min(),
                "win_rate": float((returns > 0).mean()),
                "profit_factor": returns[returns > 0].sum() / abs(returns[returns < 0].sum()) if (returns < 0).any() else np.nan,
                "average_trade_return": returns.mean(),
                "best_trade": returns.max(),
                "worst_trade": returns.min(),
                "number_of_trades": len(trades),
                "transaction_cost_dollars": config.initial_capital * config.transaction_cost * trade_weight * 2 * len(trades),
                "slippage_dollars": config.initial_capital * config.slippage * trade_weight * 2 * len(trades),
            }
        ]
    )
    return summary


def run_setup_quality_experiment(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    if not (config.metrics_dir / "predictions.csv").exists():
        train_intraday_models(config)
    predictions = load_intraday_predictions(config)
    merged = _merge_setup_context(predictions[predictions["split"] == "test"].copy(), config)
    setups = _candidate_setups(merged)
    selected = _select_daily_trades(setups, max_trades_per_day=2)
    summary = _trade_metrics(selected, config)
    write_frame(setups, config.backtest_dir / "setup_quality_candidates.csv")
    write_frame(selected, config.backtest_dir / "setup_quality_trades.csv")
    write_frame(summary, config.backtest_dir / "setup_quality_results.csv")
    _write_report(summary, selected, config)
    return summary


def _write_report(summary: pd.DataFrame, selected: pd.DataFrame, config: IntradayConfig) -> None:
    lines = [
        "# Setup Quality Intraday Experiment",
        "",
        "This experiment only trades high-confidence technical setups instead of predicting every candle.",
        "",
        "Rules: probability >= 0.70, meaningful expected move, stock above VWAP, SPY above VWAP, positive 30m momentum, elevated volume, 10:00-15:00 only, max two trades per day.",
        "",
        "## Results",
        "",
        "```text",
        summary.to_string(index=False, float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Selected Trades",
        "",
        "```text",
        selected[["date", "ticker", "horizon", "model", "probability", "future_return", "quality_score"]].to_string(index=False, float_format=lambda value: f"{value:,.6f}")
        if not selected.empty
        else "No trades selected.",
        "```",
        "",
    ]
    (config.reports_dir / "setup_quality_report.md").write_text("\n".join(lines), encoding="utf-8")
