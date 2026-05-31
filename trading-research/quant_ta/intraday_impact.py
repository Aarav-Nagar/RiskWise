from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from quant_ta.intraday_agents import AGENTS, ML_MODELS, HorizonSignal, _simulate_agent, _spy_benchmark, summarize_agent_results
from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_models import load_intraday_predictions, train_intraday_models
from quant_ta.io import read_frame, write_frame


@dataclass(frozen=True)
class ImpactCandidate:
    agent: str
    horizon: int
    model: str
    threshold: float
    top_k: int
    position_size: float


def _single_summary(equity: pd.DataFrame, trades: pd.DataFrame, config: IntradayConfig) -> dict[str, float]:
    if equity.empty:
        return {
            "ending_value": config.initial_capital,
            "cumulative_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": np.nan,
            "number_of_trades": 0,
            "objective": -np.inf,
        }
    equity = equity.sort_values("date")
    returns = equity["equity"].pct_change().fillna(0)
    cumulative = equity["equity"].iloc[-1] / config.initial_capital - 1
    max_drawdown = equity["drawdown"].min()
    sharpe = returns.mean() / returns.std() * np.sqrt(252 * 390) if returns.std() > 0 else np.nan
    trades_count = len(trades)
    exposure = float((equity["exposure"] > 0).mean())
    objective = cumulative + max_drawdown - 0.00002 * trades_count
    return {
        "ending_value": equity["equity"].iloc[-1],
        "cumulative_return": cumulative,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "number_of_trades": trades_count,
        "exposure_time": exposure,
        "objective": objective,
    }


def _candidate_config(base: IntradayConfig, candidate: ImpactCandidate) -> IntradayConfig:
    return replace(
        base,
        top_k=candidate.top_k,
        fixed_position_size=candidate.position_size,
        max_position_size=min(0.50, max(candidate.position_size, 1 / max(candidate.top_k, 1))),
        max_trades_per_day=6 if candidate.agent == "RiskManagedAgent" else base.max_trades_per_day,
        stop_loss=0.004,
        take_profit=0.010,
        max_daily_loss=0.010,
    )


def _simulate_candidate(predictions: pd.DataFrame, split: str, candidate: ImpactCandidate, config: IntradayConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = predictions[
        (predictions["split"] == split)
        & (predictions["horizon"] == candidate.horizon)
        & (predictions["model"] == candidate.model)
    ].copy()
    signal = HorizonSignal(candidate.horizon, candidate.model, candidate.threshold)
    return _simulate_agent(frame, signal, candidate.agent, _candidate_config(config, candidate))


def _candidate_grid(config: IntradayConfig) -> list[ImpactCandidate]:
    horizons = tuple(h for h in config.horizons if h in {30, 60, 120, 240})
    thresholds = (0.55, 0.65, 0.75)
    candidates: list[ImpactCandidate] = []
    for agent in AGENTS:
        for horizon in horizons:
            for model in ML_MODELS:
                for threshold in thresholds:
                    if agent == "ProbabilityAgent":
                        for position_size in (0.15, 0.25):
                            candidates.append(ImpactCandidate(agent, horizon, model, threshold, 4, position_size))
                    else:
                        for top_k in (1, 3):
                            candidates.append(ImpactCandidate(agent, horizon, model, threshold, top_k, 1 / top_k))
    return candidates


def _score_candidate_fast(validation_groups: dict[tuple[int, str], pd.DataFrame], validation_date_count: int, candidate: ImpactCandidate) -> dict[str, float]:
    frame = validation_groups.get((candidate.horizon, candidate.model), pd.DataFrame()).copy()
    if frame.empty:
        return {
            "validation_signal_count": 0,
            "validation_win_rate": np.nan,
            "validation_average_forward_return": np.nan,
            "validation_exposure_proxy": 0.0,
            "objective": -np.inf,
        }
    frame = frame[frame["probability"] > candidate.threshold]
    if candidate.agent in {"TopKAgent", "RiskManagedAgent"} and not frame.empty:
        frame = frame.sort_values(["date", "probability"], ascending=[True, False]).groupby("date").head(candidate.top_k)
    if frame.empty or len(frame) < 10:
        return {
            "validation_signal_count": len(frame),
            "validation_win_rate": np.nan,
            "validation_average_forward_return": np.nan,
            "validation_exposure_proxy": 0.0,
            "objective": -np.inf,
        }
    average_forward_return = frame["future_return"].mean()
    win_rate = (frame["future_return"] > 0).mean()
    exposure_proxy = len(frame) / max(validation_date_count, 1)
    cost_penalty = 0.0007 * min(exposure_proxy, 5)
    concentration_penalty = 0.0005 if candidate.agent == "ProbabilityAgent" and candidate.position_size > 0.20 else 0.0
    risk_bonus = 0.0004 if candidate.agent == "RiskManagedAgent" else 0.0
    objective = average_forward_return + 0.002 * (win_rate - 0.5) - cost_penalty - concentration_penalty + risk_bonus
    return {
        "validation_signal_count": len(frame),
        "validation_win_rate": win_rate,
        "validation_average_forward_return": average_forward_return,
        "validation_exposure_proxy": exposure_proxy,
        "objective": objective,
    }


def select_impact_candidates(predictions: pd.DataFrame, config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    rows = []
    validation = predictions[predictions["split"] == "validation"].copy()
    validation_groups = {
        (int(horizon), str(model)): group
        for (horizon, model), group in validation.groupby(["horizon", "model"], sort=False)
    }
    validation_date_count = validation["date"].nunique()
    for candidate in _candidate_grid(config):
        row = candidate.__dict__ | _score_candidate_fast(validation_groups, validation_date_count, candidate)
        rows.append(row)
    selection = pd.DataFrame(rows)
    return selection.sort_values(["agent", "objective", "validation_signal_count"], ascending=[True, False, False]).reset_index(drop=True)


def run_intraday_impact_experiment(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    if not (config.metrics_dir / "predictions.csv").exists():
        train_intraday_models(config)
    predictions = load_intraday_predictions(config)
    validation_grid = select_impact_candidates(predictions, config)
    winners = validation_grid.groupby("agent", as_index=False).head(1).reset_index(drop=True)

    equity_frames = []
    trade_frames = []
    for _, row in winners.iterrows():
        candidate = ImpactCandidate(
            agent=str(row["agent"]),
            horizon=int(row["horizon"]),
            model=str(row["model"]),
            threshold=float(row["threshold"]),
            top_k=int(row["top_k"]),
            position_size=float(row["position_size"]),
        )
        equity, trades = _simulate_candidate(predictions, "test", candidate, config)
        equity["selected_top_k"] = candidate.top_k
        equity["selected_position_size"] = candidate.position_size
        equity_frames.append(equity)
        if not trades.empty:
            trades["selected_top_k"] = candidate.top_k
            trades["selected_position_size"] = candidate.position_size
            trade_frames.append(trades)

    test_equity = pd.concat(equity_frames, ignore_index=True)
    test_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    summary = summarize_agent_results(test_equity, test_trades, _spy_benchmark(config), config)
    summary = summary.merge(
        winners[
            [
                "agent",
                "horizon",
                "model",
                "threshold",
                "top_k",
                "position_size",
                "objective",
                "validation_signal_count",
                "validation_win_rate",
                "validation_average_forward_return",
                "validation_exposure_proxy",
            ]
        ].rename(
            columns={
                "objective": "validation_objective",
            }
        ),
        on=["agent", "horizon"],
        how="left",
    )
    summary = summary.sort_values(["ending_value", "sharpe"], ascending=False).reset_index(drop=True)

    write_frame(validation_grid, config.backtest_dir / "impact_validation_grid.csv")
    write_frame(winners, config.backtest_dir / "impact_selected_configs.csv")
    write_frame(test_equity, config.backtest_dir / "impact_agent_intraday_equity.csv")
    write_frame(test_trades, config.backtest_dir / "impact_agent_trade_log.csv")
    write_frame(summary, config.backtest_dir / "impact_agent_results.csv")
    _write_impact_report(summary, winners, config)
    return summary


def _write_impact_report(summary: pd.DataFrame, winners: pd.DataFrame, config: IntradayConfig) -> None:
    lines = [
        "# Intraday Impact Experiment",
        "",
        "This experiment tunes each agent on validation performance only, then locks the chosen configuration and evaluates it on the test split. The objective is cumulative return plus max drawdown, with a small trade-count penalty.",
        "",
        "## Selected Validation Configurations",
        "",
        "```text",
        winners.to_string(index=False, float_format=lambda value: f"{value:,.4f}"),
        "```",
        "",
        "## Locked Test Results",
        "",
        "```text",
        summary.to_string(index=False, float_format=lambda value: f"{value:,.4f}"),
        "```",
        "",
        "## Interpretation",
        "",
        "This is a cleaner impact test than selecting the best test result by hindsight. If a selected configuration fails on test, that is evidence that the validation edge did not generalize.",
        "",
    ]
    (config.reports_dir / "intraday_impact_report.md").write_text("\n".join(lines), encoding="utf-8")
