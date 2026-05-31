from __future__ import annotations

import json

import numpy as np
import pandas as pd

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.fundamental_technical_agent import (
    AGENT_CONFIG,
    FundamentalAgentConfig,
    _attach_benchmarks,
    _prepare_agent_panel,
    _score_cross_section,
)
from quant_ta.features import load_features
from quant_ta.fmp_fundamentals import load_fmp_fundamental_panel
from quant_ta.io import write_frame


STRATEGIES = {
    "combined_fundamental_technical": "agent_score",
    "fundamental_only": "fundamental_score",
    "technical_only": "technical_score",
    "quality_only": "quality_score",
    "growth_only": "growth_score",
}


def _prepare_scored_panel(config: ResearchConfig, agent_config: FundamentalAgentConfig) -> pd.DataFrame:
    panel = _prepare_agent_panel(config, agent_config)
    if panel.empty:
        raise RuntimeError("No fundamental+technical panel available.")
    scored = pd.concat([_score_cross_section(day) for _, day in panel.groupby("date")], ignore_index=True)
    scored["fundamental_score"] = 0.65 * scored["quality_score"] + 0.35 * scored["growth_score"]
    return scored.dropna(subset=["daily_return", "quality_score", "growth_score", "technical_score", "agent_score"])


def _prepare_fmp_scored_panel(config: ResearchConfig, agent_config: FundamentalAgentConfig) -> pd.DataFrame:
    features = load_features(config)
    fundamentals = load_fmp_fundamental_panel(config)
    fundamentals = fundamentals[fundamentals.get("error").isna() if "error" in fundamentals else fundamentals.index == fundamentals.index].copy()
    features = features[features["ticker"].isin(config.tickers)].sort_values(["ticker", "date"]).copy()
    merged = []
    for ticker, prices in features.groupby("ticker"):
        fund = fundamentals[fundamentals["ticker"] == ticker].sort_values("date")
        if fund.empty:
            continue
        merged.append(pd.merge_asof(prices.sort_values("date"), fund, on="date", by="ticker", direction="backward"))
    panel = pd.concat(merged, ignore_index=True) if merged else pd.DataFrame()
    panel = panel[panel["date"] >= pd.Timestamp(agent_config.test_start)].copy()
    panel["daily_return"] = panel.groupby("ticker")["close"].pct_change()
    scored = pd.concat([_score_cross_section(day) for _, day in panel.groupby("date")], ignore_index=True)
    scored["fundamental_score"] = 0.65 * scored["quality_score"] + 0.35 * scored["growth_score"]
    return scored.dropna(subset=["daily_return", "quality_score", "growth_score", "technical_score", "agent_score"])


def _rebalance_dates(scored: pd.DataFrame) -> list[pd.Timestamp]:
    dates = pd.Series(sorted(pd.to_datetime(scored["date"]).unique()))
    return [pd.Timestamp(date) for date in dates.groupby(dates.dt.to_period("W")).max().to_list()]


def _benchmark_returns(scored: pd.DataFrame, config: ResearchConfig) -> pd.DataFrame:
    features = load_features(config)
    dates = pd.to_datetime(scored["date"].unique())
    bench = features[features["date"].isin(dates)].copy()
    spy = bench[bench["ticker"] == config.benchmark][["date", "return_1d"]].rename(columns={"return_1d": "spy_return"})
    basket = (
        bench[bench["ticker"].isin(config.tickers)]
        .groupby("date", as_index=False)["return_1d"]
        .mean()
        .rename(columns={"return_1d": "basket_return"})
    )
    out = pd.DataFrame({"date": sorted(dates)}).merge(spy, on="date", how="left").merge(basket, on="date", how="left")
    out["spy_return"] = out["spy_return"].fillna(0)
    out["basket_return"] = out["basket_return"].fillna(0)
    return out


def _attach_precomputed_benchmarks(curve: pd.DataFrame, benchmarks: pd.DataFrame, agent_config: FundamentalAgentConfig) -> pd.DataFrame:
    out = curve.merge(benchmarks, on="date", how="left")
    out["spy_return"] = out["spy_return"].fillna(0)
    out["basket_return"] = out["basket_return"].fillna(0)
    out["spy_equity"] = agent_config.initial_capital * (1 + out["spy_return"]).cumprod()
    out["basket_equity"] = agent_config.initial_capital * (1 + out["basket_return"]).cumprod()
    return out


def _simulate_topn(
    scored: pd.DataFrame,
    score_column: str,
    strategy: str,
    agent_config: FundamentalAgentConfig,
    config: ResearchConfig,
    benchmarks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rebalance_dates = set(_rebalance_dates(scored))
    weights_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    selections = []
    weights: dict[str, float] = {}
    for date in sorted(pd.to_datetime(scored["date"]).unique()):
        date = pd.Timestamp(date)
        if date in rebalance_dates:
            day = scored[scored["date"] == date].sort_values(score_column, ascending=False).head(agent_config.top_n)
            weights = {ticker: 1 / len(day) for ticker in day["ticker"]} if not day.empty else {}
            selections.append(day.assign(strategy=strategy, selection_date=date))
        weights_by_date[date] = weights.copy()

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
    curve = _attach_precomputed_benchmarks(pd.DataFrame(rows), benchmarks, agent_config)
    selections_df = pd.concat(selections, ignore_index=True) if selections else pd.DataFrame()
    return curve, selections_df


def _summarize_curve(curve: pd.DataFrame, strategy: str, agent_config: FundamentalAgentConfig) -> dict:
    returns = curve["equity"].pct_change().fillna(0)
    cumulative = curve["equity"].iloc[-1] / agent_config.initial_capital - 1
    spy_return = curve["spy_equity"].iloc[-1] / agent_config.initial_capital - 1
    basket_return = curve["basket_equity"].iloc[-1] / agent_config.initial_capital - 1
    drawdown = curve["equity"] / curve["equity"].cummax() - 1
    downside = returns[returns < 0].std()
    return {
        "strategy": strategy,
        "starting_capital": agent_config.initial_capital,
        "ending_value": curve["equity"].iloc[-1],
        "profit_loss": curve["equity"].iloc[-1] - agent_config.initial_capital,
        "cumulative_return": cumulative,
        "spy_return": spy_return,
        "basket_return": basket_return,
        "return_vs_spy": cumulative - spy_return,
        "return_vs_basket": cumulative - basket_return,
        "sharpe": returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else np.nan,
        "sortino": returns.mean() / downside * np.sqrt(252) if downside and downside > 0 else np.nan,
        "max_drawdown": drawdown.min(),
        "average_turnover": curve["turnover"].mean(),
        "evaluation_start": curve["date"].min(),
        "evaluation_end": curve["date"].max(),
    }


def _bootstrap_return_ci(curve: pd.DataFrame, seed: int = 42, samples: int = 5000) -> tuple[float, float]:
    returns = curve["equity"].pct_change().dropna().to_numpy()
    if len(returns) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    boot = [np.prod(1 + rng.choice(returns, size=len(returns), replace=True)) - 1 for _ in range(samples)]
    return tuple(np.percentile(boot, [2.5, 97.5]))


def _placebo_distribution(
    scored: pd.DataFrame,
    agent_config: FundamentalAgentConfig,
    config: ResearchConfig,
    benchmarks: pd.DataFrame,
    runs: int = 100,
) -> pd.DataFrame:
    rng = np.random.default_rng(config.seed)
    rows = []
    base = scored.copy()
    for run in range(runs):
        shuffled = []
        for _, day in base.groupby("date"):
            day = day.copy()
            day["placebo_score"] = rng.permutation(day["agent_score"].to_numpy())
            shuffled.append(day)
        placebo = pd.concat(shuffled, ignore_index=True)
        curve, _ = _simulate_topn(placebo, "placebo_score", f"placebo_{run}", agent_config, config, benchmarks)
        rows.append(_summarize_curve(curve, f"placebo_{run}", agent_config))
    return pd.DataFrame(rows)


def run_fundamental_publication_study(
    config: ResearchConfig = CONFIG,
    agent_config: FundamentalAgentConfig = AGENT_CONFIG,
    source: str = "yfinance",
) -> pd.DataFrame:
    config.ensure_dirs()
    scored = _prepare_fmp_scored_panel(config, agent_config) if source == "fmp" else _prepare_scored_panel(config, agent_config)
    benchmarks = _benchmark_returns(scored, config)
    curves = []
    selections = []
    summaries = []
    for strategy, score_column in STRATEGIES.items():
        curve, selected = _simulate_topn(scored, score_column, strategy, agent_config, config, benchmarks)
        low, high = _bootstrap_return_ci(curve, config.seed)
        summary = _summarize_curve(curve, strategy, agent_config)
        summary["bootstrap_return_ci_low"] = low
        summary["bootstrap_return_ci_high"] = high
        summaries.append(summary)
        curves.append(curve)
        selections.append(selected)

    placebo = _placebo_distribution(scored, agent_config, config, benchmarks)
    summary_df = pd.DataFrame(summaries)
    combined_return = summary_df.loc[summary_df["strategy"] == "combined_fundamental_technical", "cumulative_return"].iloc[0]
    summary_df["placebo_p_value"] = np.nan
    summary_df.loc[summary_df["strategy"] == "combined_fundamental_technical", "placebo_p_value"] = (
        (placebo["cumulative_return"] >= combined_return).mean()
    )

    all_curves = pd.concat(curves, ignore_index=True)
    all_selections = pd.concat(selections, ignore_index=True)
    prefix = f"fundamental_publication_{source}"
    write_frame(scored, config.processed_dir / f"{prefix}_scored_panel.csv")
    write_frame(all_curves, config.backtest_dir / f"{prefix}_equity.csv")
    write_frame(all_selections, config.backtest_dir / f"{prefix}_selections.csv")
    write_frame(summary_df, config.backtest_dir / f"{prefix}_results.csv")
    write_frame(placebo, config.backtest_dir / f"{prefix}_placebo.csv")
    _write_report(summary_df, placebo, all_selections, config, source)
    return summary_df


def _write_report(summary: pd.DataFrame, placebo: pd.DataFrame, selections: pd.DataFrame, config: ResearchConfig, source: str) -> None:
    latest = selections.sort_values("selection_date").tail(25)
    placebo_stats = placebo["cumulative_return"].describe(percentiles=[0.05, 0.5, 0.95])
    lines = [
        "# Publication-Style Fundamental + Technical Study",
        "",
        "## Design",
        "",
        f"This study compares a combined fundamental+technical ranking agent against ablations and placebo portfolios over the same tradable universe and dates. Fundamental source: {source}. FMP uses filing/accepted dates from the provider when available; free data remains limited to the latest statement history.",
        "",
        "Strategies tested: combined, fundamental-only, technical-only, quality-only, growth-only, SPY benchmark, equal-weight basket benchmark, and 250 cross-sectional score-shuffle placebo portfolios.",
        "",
        "## Results",
        "",
        "```text",
        summary.to_string(index=False, float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Placebo Distribution",
        "",
        "```text",
        placebo_stats.to_string(float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Latest Selections",
        "",
        "```text",
        latest[["strategy", "selection_date", "ticker", "agent_score", "fundamental_score", "technical_score"]].to_string(index=False, float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Interpretation",
        "",
        "A publication-grade interpretation should emphasize benchmark-relative performance, ablation consistency, placebo p-value, drawdown, and the point-in-time limitation of free fundamentals.",
        "",
    ]
    (config.reports_dir / f"fundamental_publication_{source}_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    import os

    run_fundamental_publication_study(CONFIG, AGENT_CONFIG, source="fmp" if os.getenv("FMP_API_KEY") else "yfinance")


if __name__ == "__main__":
    main()
