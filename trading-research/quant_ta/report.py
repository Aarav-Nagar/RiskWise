from __future__ import annotations

import pandas as pd

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.io import read_frame


def _best_rows(metrics: pd.DataFrame, value: str) -> pd.DataFrame:
    if metrics.empty or value not in metrics:
        return pd.DataFrame()
    idx = metrics.groupby("horizon")[value].idxmax()
    return metrics.loc[idx, ["horizon", "model", value]].sort_values("horizon")


def generate_report(config: ResearchConfig = CONFIG) -> str:
    config.ensure_dirs()
    metrics_path = config.metrics_dir / "classification_metrics.csv"
    backtest_path = config.backtest_dir / "backtest_metrics_aggregate.csv"
    metrics = read_frame(metrics_path) if metrics_path.exists() else pd.DataFrame()
    backtests = read_frame(backtest_path) if backtest_path.exists() else pd.DataFrame()
    test_metrics = metrics[metrics["split"] == "test"].copy() if not metrics.empty else pd.DataFrame()

    best_auc = _best_rows(test_metrics, "roc_auc")
    best_sharpe = _best_rows(backtests, "sharpe")

    lines = [
        "# Mathematical Technical Analysis Research Report",
        "",
        "## Research Question",
        "",
        "This study evaluates whether mathematical technical-analysis features derived only from historical OHLCV data exhibit predictive utility for future stock returns across 1, 5, 20, and 30 trading-day horizons.",
        "",
        "The framework deliberately excludes fundamentals, news, sentiment, analyst estimates, macro variables, and discretionary trading logic. Results should be interpreted as evidence about this restricted feature class, not as investment advice.",
        "",
        "## Methodology",
        "",
        f"- Data source: Yahoo Finance daily OHLCV from `{config.start_date}` through the latest downloaded session.",
        f"- Universe: {len(config.tickers)} liquid U.S. stocks; `{config.benchmark}` is used only as benchmark/relative technical reference.",
        f"- Splits: train through `{config.train_end}`, validation during 2023, test from `{config.test_start}` onward.",
        "- Labels: positive forward close-to-close return for each horizon.",
        "- Models: technical-rule baselines, logistic regression, random forest, and XGBoost when installed.",
        "- Leakage controls: chronological splits, rolling features based only on past/current bars, and model preprocessing fit only on training rows.",
        "",
        "## Predictive Results",
        "",
    ]

    if best_auc.empty:
        lines.append("No classification metrics were available when this report was generated.")
    else:
        lines.append("Best test ROC-AUC by horizon:")
        lines.append("")
        lines.append("```text")
        lines.append(best_auc.to_string(index=False))
        lines.append("```")

    lines.extend(["", "## Backtest Results", ""])
    if best_sharpe.empty:
        lines.append("No backtest metrics were available when this report was generated.")
    else:
        lines.append("Best average test Sharpe by horizon:")
        lines.append("")
        lines.append("```text")
        lines.append(best_sharpe.to_string(index=False))
        lines.append("```")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Any measured signal should be treated cautiously. Short-horizon equity returns are noisy and often close to statistically efficient after transaction costs. If 1D results cluster near random classification performance, that is consistent with the difficulty of extracting exploitable daily direction from price and volume alone.",
            "",
            "Medium horizons such as 20D and 30D may show stronger technical structure when trend, volatility, and relative-momentum features persist across several weeks. However, stronger validation metrics do not necessarily imply durable tradability; the test-period backtests and transaction-cost drag are the more relevant sanity checks.",
            "",
            "Feature importance should be interpreted as model-specific association, not causal evidence. Highly correlated indicators, overlapping rolling windows, and repeated horizon tests all increase the risk that apparent importance reflects redundant transformations of the same underlying price path.",
            "",
            "## Limitations",
            "",
            "- The stock universe is based on currently selected liquid names, which introduces survivorship and selection bias.",
            "- Yahoo Finance data can contain revisions, missing values, corporate-action quirks, or ticker-specific gaps.",
            "- Multiple horizons, indicators, models, and baselines increase the risk of false discoveries.",
            "- Transaction costs are simplified and do not model spreads, borrow costs, taxes, liquidity, or market impact.",
            "- A cash-only long strategy is less aggressive than a long/short strategy and avoids leverage assumptions.",
            "",
            "## Conclusion",
            "",
            "This framework is designed to measure whether mathematical technical indicators contain incremental predictive information under controlled experimental conditions. The appropriate conclusion depends on out-of-sample test evidence, not on isolated high-performing charts or validation-period wins.",
            "",
        ]
    )

    report = "\n".join(lines)
    path = config.reports_dir / "research_report.md"
    path.write_text(report, encoding="utf-8")
    return report
