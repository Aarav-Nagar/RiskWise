from __future__ import annotations

import json
from itertools import product

import numpy as np
import pandas as pd

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.fundamental_publication import _benchmark_returns, _prepare_fmp_scored_panel, _summarize_curve
from quant_ta.fundamental_technical_agent import AGENT_CONFIG, FundamentalAgentConfig
from quant_ta.io import write_frame


def _candidate_weights(step: float = 0.1) -> list[dict[str, float]]:
    values = np.round(np.arange(0, 1 + step, step), 6)
    weights = []
    for quality, growth, technical in product(values, repeat=3):
        total = quality + growth + technical
        if abs(total - 1.0) < 1e-9:
            weights.append({"quality": float(quality), "growth": float(growth), "technical": float(technical)})
    return weights


def _split_dates(scored: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    dates = pd.Series(sorted(pd.to_datetime(scored["date"]).unique()))
    split = pd.Timestamp(dates.iloc[int(len(dates) * 0.60)])
    return dates.min(), split


def _apply_blend(scored: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    frame = scored.copy()
    frame["blend_score"] = (
        weights["quality"] * frame["quality_score"]
        + weights["growth"] * frame["growth_score"]
        + weights["technical"] * frame["technical_score"]
    )
    return frame


def _simulate(
    scored: pd.DataFrame,
    score_column: str,
    strategy: str,
    agent_config: FundamentalAgentConfig,
    config: ResearchConfig,
    benchmarks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.Series(sorted(pd.to_datetime(scored["date"]).unique()))
    rebalance_dates = set(pd.Timestamp(date) for date in dates.groupby(dates.dt.to_period("W")).max().to_list())
    weights_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    selections = []
    current: dict[str, float] = {}
    for date in sorted(pd.to_datetime(scored["date"]).unique()):
        date = pd.Timestamp(date)
        if date in rebalance_dates:
            day = scored[scored["date"] == date].sort_values(score_column, ascending=False).head(agent_config.top_n)
            current = {ticker: 1 / len(day) for ticker in day["ticker"]} if not day.empty else {}
            selections.append(day.assign(strategy=strategy, selection_date=date))
        weights_by_date[date] = current.copy()

    equity = agent_config.initial_capital
    previous: dict[str, float] = {}
    rows = []
    for date in sorted(pd.to_datetime(scored["date"]).unique()):
        day = scored[scored["date"] == date]
        returns = day.set_index("ticker")["daily_return"].fillna(0).to_dict()
        weights = weights_by_date[pd.Timestamp(date)]
        turnover = sum(abs(weights.get(t, 0.0) - previous.get(t, 0.0)) for t in set(weights) | set(previous))
        portfolio_return = sum(weights.get(ticker, 0.0) * returns.get(ticker, 0.0) for ticker in weights)
        equity *= 1 + portfolio_return
        equity -= equity * agent_config.transaction_cost * turnover
        previous = weights
        rows.append(
            {
                "date": date,
                "strategy": strategy,
                "equity": equity,
                "portfolio_return": portfolio_return,
                "turnover": turnover,
                "holdings": json.dumps(weights),
            }
        )
    curve = pd.DataFrame(rows).merge(benchmarks, on="date", how="left")
    curve["spy_return"] = curve["spy_return"].fillna(0)
    curve["basket_return"] = curve["basket_return"].fillna(0)
    curve["spy_equity"] = agent_config.initial_capital * (1 + curve["spy_return"]).cumprod()
    curve["basket_equity"] = agent_config.initial_capital * (1 + curve["basket_return"]).cumprod()
    selections_df = pd.concat(selections, ignore_index=True) if selections else pd.DataFrame()
    return curve, selections_df


def _objective(summary: dict) -> float:
    return summary["cumulative_return"] + summary["max_drawdown"] - 0.05 * summary["average_turnover"]


def _bootstrap_ci(curve: pd.DataFrame, seed: int = 42, samples: int = 3000) -> tuple[float, float]:
    returns = curve["equity"].pct_change().dropna().to_numpy()
    if len(returns) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    boot = [np.prod(1 + rng.choice(returns, len(returns), replace=True)) - 1 for _ in range(samples)]
    return tuple(np.percentile(boot, [2.5, 97.5]))


def run_factor_blend_study(
    config: ResearchConfig = CONFIG,
    agent_config: FundamentalAgentConfig = AGENT_CONFIG,
) -> pd.DataFrame:
    config.ensure_dirs()
    scored = _prepare_fmp_scored_panel(config, agent_config)
    scored = scored.dropna(subset=["quality_score", "growth_score", "technical_score", "daily_return"])
    _, split = _split_dates(scored)
    validation = scored[scored["date"] <= split].copy()
    test = scored[scored["date"] > split].copy()
    validation_benchmarks = _benchmark_returns(validation, config)
    test_benchmarks = _benchmark_returns(test, config)

    grid_rows = []
    for weights in _candidate_weights(0.1):
        blended = _apply_blend(validation, weights)
        curve, _ = _simulate(blended, "blend_score", "validation_blend", agent_config, config, validation_benchmarks)
        summary = _summarize_curve(curve, "validation_blend", agent_config)
        grid_rows.append(weights | summary | {"objective": _objective(summary)})
    grid = pd.DataFrame(grid_rows).sort_values("objective", ascending=False)
    best_weights = grid.iloc[0][["quality", "growth", "technical"]].to_dict()

    test_curves = []
    test_selections = []
    summary_rows = []
    strategies = {
        "validation_locked_blend": ("blend_score", _apply_blend(test, best_weights)),
        "equal_weight_blend": ("equal_blend", test.assign(equal_blend=(test["quality_score"] + test["growth_score"] + test["technical_score"]) / 3)),
        "technical_only": ("technical_score", test),
        "fundamental_only": ("fundamental_score", test.assign(fundamental_score=0.65 * test["quality_score"] + 0.35 * test["growth_score"])),
    }
    for strategy, (score_column, frame) in strategies.items():
        curve, selections = _simulate(frame, score_column, strategy, agent_config, config, test_benchmarks)
        summary = _summarize_curve(curve, strategy, agent_config)
        low, high = _bootstrap_ci(curve, config.seed)
        summary["bootstrap_return_ci_low"] = low
        summary["bootstrap_return_ci_high"] = high
        summary_rows.append(summary)
        test_curves.append(curve)
        test_selections.append(selections)

    placebo_rows = []
    rng = np.random.default_rng(config.seed)
    for run in range(150):
        placebo = test.copy()
        shuffled = []
        for _, day in placebo.groupby("date"):
            day = day.copy()
            day["placebo_score"] = rng.permutation(day["blend_score"].to_numpy()) if "blend_score" in day else rng.random(len(day))
            shuffled.append(day)
        placebo = pd.concat(shuffled, ignore_index=True)
        curve, _ = _simulate(placebo, "placebo_score", f"placebo_{run}", agent_config, config, test_benchmarks)
        placebo_rows.append(_summarize_curve(curve, f"placebo_{run}", agent_config))
    placebo = pd.DataFrame(placebo_rows)
    summary = pd.DataFrame(summary_rows)
    locked_return = summary.loc[summary["strategy"] == "validation_locked_blend", "cumulative_return"].iloc[0]
    summary["placebo_p_value"] = np.nan
    summary.loc[summary["strategy"] == "validation_locked_blend", "placebo_p_value"] = (
        placebo["cumulative_return"] >= locked_return
    ).mean()
    for key, value in best_weights.items():
        summary[f"selected_{key}_weight"] = value if summary["strategy"].eq("validation_locked_blend").any() else np.nan

    write_frame(grid, config.backtest_dir / "factor_blend_validation_grid.csv")
    write_frame(summary, config.backtest_dir / "factor_blend_results.csv")
    write_frame(pd.concat(test_curves, ignore_index=True), config.backtest_dir / "factor_blend_equity.csv")
    write_frame(pd.concat(test_selections, ignore_index=True), config.backtest_dir / "factor_blend_selections.csv")
    write_frame(placebo, config.backtest_dir / "factor_blend_placebo.csv")
    _write_report(summary, grid, placebo, config)
    return summary


def _write_report(summary: pd.DataFrame, grid: pd.DataFrame, placebo: pd.DataFrame, config: ResearchConfig) -> None:
    lines = [
        "# Validation-Locked Factor Blend Study",
        "",
        "This study learns only the blend weights between quality, growth, and technical scores on validation data, freezes the weights, and evaluates them on a later holdout window. It is designed to avoid picking factor weights from the test period.",
        "",
        "## Selected Validation Weights",
        "",
        "```text",
        grid.head(10).to_string(index=False, float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Holdout Results",
        "",
        "```text",
        summary.to_string(index=False, float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Placebo Returns",
        "",
        "```text",
        placebo["cumulative_return"].describe(percentiles=[0.05, 0.5, 0.95]).to_string(float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
    ]
    (config.reports_dir / "factor_blend_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    run_factor_blend_study(CONFIG, AGENT_CONFIG)


if __name__ == "__main__":
    main()
