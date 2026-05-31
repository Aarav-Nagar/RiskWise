from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_data import load_intraday_prices
from quant_ta.intraday_models import load_intraday_predictions, train_intraday_models
from quant_ta.io import read_frame, write_frame


AGENTS = ("ProbabilityAgent", "TopKAgent", "RiskManagedAgent")
ML_MODELS = ("logistic_regression", "random_forest", "xgboost")


@dataclass(frozen=True)
class HorizonSignal:
    horizon: int
    model: str
    threshold: float


def _calibrate_threshold(frame: pd.DataFrame) -> float:
    best_threshold = 0.55
    best_score = -np.inf
    for threshold in np.arange(0.50, 0.76, 0.025):
        trades = frame[frame["probability"] > threshold]
        if len(trades) < 20:
            continue
        win_rate = (trades["future_return"] > 0).mean()
        average_return = trades["future_return"].mean()
        score = average_return + 0.0025 * (win_rate - 0.5)
        if score > best_score:
            best_score = score
            best_threshold = float(threshold)
    return best_threshold


def select_horizon_signals(predictions: pd.DataFrame, metrics: pd.DataFrame) -> list[HorizonSignal]:
    signals = []
    validation_metrics = metrics[(metrics["split"] == "validation") & (metrics["model"].isin(ML_MODELS))].copy()
    for horizon, group in validation_metrics.groupby("horizon"):
        best = group.sort_values(["roc_auc", "f1"], ascending=False).iloc[0]
        model = str(best["model"])
        validation_predictions = predictions[
            (predictions["split"] == "validation")
            & (predictions["horizon"] == horizon)
            & (predictions["model"] == model)
        ]
        signals.append(HorizonSignal(int(horizon), model, _calibrate_threshold(validation_predictions)))
    return signals


def _weights_for_probability_agent(step: pd.DataFrame, threshold: float, config: IntradayConfig) -> dict[str, float]:
    selected = step[step["probability"] > threshold].sort_values("probability", ascending=False)
    weights: dict[str, float] = {}
    remaining = 1.0
    for _, row in selected.iterrows():
        weight = min(config.fixed_position_size, remaining)
        if weight <= 0:
            break
        weights[str(row["ticker"])] = weight
        remaining -= weight
    return weights


def _weights_for_topk_agent(step: pd.DataFrame, threshold: float, config: IntradayConfig) -> dict[str, float]:
    selected = step[step["probability"] > threshold].sort_values("probability", ascending=False).head(config.top_k)
    if selected.empty:
        return {}
    weight = min(1.0 / len(selected), config.max_position_size)
    return {str(row["ticker"]): weight for _, row in selected.iterrows()}


def _trade_rows(
    date: pd.Timestamp,
    agent: str,
    horizon: int,
    previous_weights: dict[str, float],
    next_weights: dict[str, float],
    equity: float,
    cost_rate: float,
) -> list[dict]:
    rows = []
    tickers = set(previous_weights) | set(next_weights)
    for ticker in tickers:
        delta = next_weights.get(ticker, 0.0) - previous_weights.get(ticker, 0.0)
        if abs(delta) < 1e-12:
            continue
        rows.append(
            {
                "date": date,
                "agent": agent,
                "horizon": horizon,
                "ticker": ticker,
                "action": "BUY" if delta > 0 else "SELL",
                "weight_change": delta,
                "notional": abs(delta) * equity,
                "cost": abs(delta) * equity * cost_rate,
            }
        )
    return rows


def _simulate_agent(signal_frame: pd.DataFrame, signal: HorizonSignal, agent: str, config: IntradayConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    cost_rate = config.transaction_cost + config.slippage
    weights: dict[str, float] = {}
    entry_equity: dict[str, float] = {}
    equity = config.initial_capital
    peak = equity
    day_start_equity = equity
    trades_today = 0
    current_day = None
    halted_for_day = False
    equity_rows = []
    trade_rows = []

    for date, step in signal_frame.groupby("date", sort=True):
        date = pd.Timestamp(date)
        day = date.date()
        if current_day != day:
            current_day = day
            day_start_equity = equity
            trades_today = 0
            halted_for_day = False

        returns = step.set_index("ticker")["minute_return"].fillna(0).to_dict()
        portfolio_return = sum(weights.get(ticker, 0.0) * float(returns.get(ticker, 0.0)) for ticker in weights)
        equity *= 1 + portfolio_return

        if agent == "ProbabilityAgent":
            desired = _weights_for_probability_agent(step, signal.threshold, config)
        else:
            desired = _weights_for_topk_agent(step, signal.threshold, config)

        if agent == "RiskManagedAgent":
            daily_loss = equity / day_start_equity - 1 if day_start_equity else 0
            if daily_loss <= -config.max_daily_loss:
                halted_for_day = True
            for ticker in list(weights):
                entry = entry_equity.get(ticker, equity)
                trade_return = equity / entry - 1 if entry else 0
                if trade_return <= -config.stop_loss or trade_return >= config.take_profit:
                    desired.pop(ticker, None)
            if halted_for_day or trades_today >= config.max_trades_per_day:
                desired = {}
            desired = {ticker: min(weight, config.max_position_size) for ticker, weight in desired.items()}

        if date.hour == 15 and date.minute >= 55:
            desired = {}

        turnover = sum(abs(desired.get(ticker, 0.0) - weights.get(ticker, 0.0)) for ticker in set(desired) | set(weights))
        cost = turnover * cost_rate * equity
        if turnover > 0:
            trade_rows.extend(_trade_rows(date, agent, signal.horizon, weights, desired, equity, cost_rate))
            trades_today += int(turnover > 0)
        equity -= cost

        for ticker in desired:
            if ticker not in weights or weights.get(ticker, 0.0) == 0:
                entry_equity[ticker] = equity
        for ticker in list(entry_equity):
            if ticker not in desired:
                entry_equity.pop(ticker, None)
        weights = desired
        peak = max(peak, equity)
        equity_rows.append(
            {
                "date": date,
                "agent": agent,
                "horizon": signal.horizon,
                "model": signal.model,
                "threshold": signal.threshold,
                "equity": equity,
                "cash_weight": max(0.0, 1 - sum(weights.values())),
                "exposure": sum(weights.values()),
                "minute_return": portfolio_return,
                "cost": cost,
                "drawdown": equity / peak - 1,
            }
        )

    return pd.DataFrame(equity_rows), pd.DataFrame(trade_rows)


def _spy_benchmark(config: IntradayConfig) -> pd.DataFrame:
    prices = load_intraday_prices(config)
    spy = prices[prices["ticker"] == "SPY"].sort_values("date").copy()
    test_start = pd.Timestamp(config.test_start)
    test_end = pd.Timestamp(config.test_end) + pd.Timedelta(days=1)
    if spy["date"].min() < test_start and spy["date"].max() >= test_start:
        test_spy = spy[(spy["date"] >= test_start) & (spy["date"] < test_end)].copy()
        if not test_spy.empty:
            spy = test_spy
            spy["minute_return"] = spy["close"].pct_change().fillna(0)
            spy["equity"] = config.initial_capital * (1 + spy["minute_return"]).cumprod()
            return spy[["date", "equity", "minute_return"]]
    split_dates = np.array(sorted(spy["date"].unique()))
    test_start = split_dates[int(len(split_dates) * 0.80)]
    spy = spy[spy["date"] > test_start].copy()
    spy["minute_return"] = spy["close"].pct_change().fillna(0)
    spy["equity"] = config.initial_capital * (1 + spy["minute_return"]).cumprod()
    return spy[["date", "equity", "minute_return"]]


def _sortino(returns: pd.Series) -> float:
    downside = returns[returns < 0].std()
    return returns.mean() / downside * np.sqrt(252 * 390) if downside and downside > 0 else np.nan


def _profit_factor(returns: pd.Series) -> float:
    gains = returns[returns > 0].sum()
    losses = returns[returns < 0].sum()
    return gains / abs(losses) if losses < 0 else np.nan


def summarize_agent_results(equity: pd.DataFrame, trades: pd.DataFrame, spy: pd.DataFrame, config: IntradayConfig) -> pd.DataFrame:
    spy_return = spy["equity"].iloc[-1] / spy["equity"].iloc[0] - 1 if len(spy) > 1 else 0.0
    rows = []
    for (agent, horizon), group in equity.groupby(["agent", "horizon"]):
        group = group.sort_values("date")
        returns = group["equity"].pct_change().fillna(0)
        trade_group = trades[(trades["agent"] == agent) & (trades["horizon"] == horizon)] if not trades.empty else pd.DataFrame()
        ending = group["equity"].iloc[-1]
        cumulative = ending / config.initial_capital - 1
        rows.append(
            {
                "agent": agent,
                "horizon": horizon,
                "starting_capital": config.initial_capital,
                "ending_value": ending,
                "profit_loss": ending - config.initial_capital,
                "cumulative_return": cumulative,
                "return_vs_spy": cumulative - spy_return,
                "sharpe": returns.mean() / returns.std() * np.sqrt(252 * 390) if returns.std() > 0 else np.nan,
                "sortino": _sortino(returns),
                "max_drawdown": group["drawdown"].min(),
                "win_rate": float((returns > 0).mean()),
                "profit_factor": _profit_factor(returns),
                "number_of_trades": len(trade_group),
                "exposure_time": float((group["exposure"] > 0).mean()),
                "transaction_cost_dollars": group["cost"].sum() * config.transaction_cost / (config.transaction_cost + config.slippage),
                "slippage_dollars": group["cost"].sum() * config.slippage / (config.transaction_cost + config.slippage),
                "best_trade": returns.max(),
                "worst_trade": returns.min(),
                "drawdown_penalized_return": cumulative + group["drawdown"].min(),
            }
        )
    return pd.DataFrame(rows).sort_values(["ending_value", "sharpe"], ascending=False).reset_index(drop=True)


def write_agent_report(summary: pd.DataFrame, signals: list[HorizonSignal], config: IntradayConfig) -> None:
    best_capital = summary.sort_values("ending_value", ascending=False).head(10)
    best_sharpe = summary.sort_values("sharpe", ascending=False).head(10)
    best_penalized = summary.sort_values("drawdown_penalized_return", ascending=False).head(10)
    signal_table = pd.DataFrame([signal.__dict__ for signal in signals])
    lines = [
        "# Three-Agent Intraday Horizon Experiment",
        "",
        "This report compares ProbabilityAgent, TopKAgent, and RiskManagedAgent across the expanded intraday horizon ladder using technical OHLCV features only.",
        "",
        "## Selected Model And Threshold By Horizon",
        "",
        "```text",
        signal_table.to_string(index=False),
        "```",
        "",
        "## Best Ending Capital",
        "",
        "```text",
        best_capital.to_string(index=False, float_format=lambda value: f"{value:,.4f}"),
        "```",
        "",
        "## Best Sharpe",
        "",
        "```text",
        best_sharpe.to_string(index=False, float_format=lambda value: f"{value:,.4f}"),
        "```",
        "",
        "## Best Drawdown-Penalized Return",
        "",
        "```text",
        best_penalized.to_string(index=False, float_format=lambda value: f"{value:,.4f}"),
        "```",
        "",
        "## Caveat",
        "",
        "This run uses the available free Yahoo recent-window 1-minute data unless a historical intraday provider key is configured. It is a smoke-test implementation of the agent framework, not the full Jan-May 2026 historical experiment.",
        "",
    ]
    (config.reports_dir / "jan_may_2026_three_agent_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_agent_experiment(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    if not (config.metrics_dir / "classification_metrics.csv").exists():
        train_intraday_models(config)
    metrics = read_frame(config.metrics_dir / "classification_metrics.csv")
    predictions = load_intraday_predictions(config)
    signals = select_horizon_signals(predictions, metrics)
    equity_frames = []
    trade_frames = []
    for signal in signals:
        signal_frame = predictions[
            (predictions["split"] == "test")
            & (predictions["horizon"] == signal.horizon)
            & (predictions["model"] == signal.model)
        ].copy()
        for agent in AGENTS:
            equity, trades = _simulate_agent(signal_frame, signal, agent, config)
            equity_frames.append(equity)
            if not trades.empty:
                trade_frames.append(trades)

    equity = pd.concat(equity_frames, ignore_index=True)
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    spy = _spy_benchmark(config)
    summary = summarize_agent_results(equity, trades, spy, config)
    daily = equity.copy()
    daily["session"] = pd.to_datetime(daily["date"]).dt.date
    daily = daily.sort_values("date").groupby(["agent", "horizon", "session"], as_index=False).tail(1)

    write_frame(summary, config.backtest_dir / "agent_horizon_results.csv")
    write_frame(summary, config.backtest_dir / "agent_vs_spy_summary.csv")
    write_frame(equity, config.backtest_dir / "agent_intraday_equity.csv")
    write_frame(daily, config.backtest_dir / "agent_daily_equity.csv")
    write_frame(trades, config.backtest_dir / "agent_trade_log.csv")
    write_agent_report(summary, signals, config)
    return summary
