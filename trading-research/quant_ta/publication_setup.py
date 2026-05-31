from __future__ import annotations

import numpy as np
import pandas as pd

from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_data import load_intraday_prices
from quant_ta.intraday_models import load_intraday_predictions
from quant_ta.setup_quality import run_setup_quality_experiment
from quant_ta.io import read_frame, write_frame


def _buy_hold_benchmark(prices: pd.DataFrame, ticker: str, start: pd.Timestamp, end: pd.Timestamp, capital: float) -> dict[str, float]:
    frame = prices[(prices["ticker"] == ticker) & (prices["date"] >= start) & (prices["date"] <= end)].sort_values("date")
    if len(frame) < 2:
        return {"ticker": ticker, "ending_value": capital, "return": 0.0}
    ret = frame["close"].iloc[-1] / frame["close"].iloc[0] - 1
    return {"ticker": ticker, "ending_value": capital * (1 + ret), "return": ret}


def _bootstrap_ci(trade_returns: pd.Series, seed: int = 42, samples: int = 5000) -> tuple[float, float]:
    if trade_returns.empty:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    values = trade_returns.to_numpy()
    boot = []
    for _ in range(samples):
        boot.append(np.prod(1 + rng.choice(values, size=len(values), replace=True)) - 1)
    return tuple(np.percentile(boot, [2.5, 97.5]))


def generate_publication_setup_report(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    summary = run_setup_quality_experiment(config)
    trades = read_frame(config.backtest_dir / "setup_quality_trades.csv", parse_dates=["date"])
    prices = load_intraday_prices(config)
    predictions = load_intraday_predictions(config)
    test_predictions = predictions[predictions["split"] == "test"]
    start = test_predictions["date"].min() if not test_predictions.empty else prices["date"].min()
    end = test_predictions["date"].max() if not test_predictions.empty else prices["date"].max()
    spy = _buy_hold_benchmark(prices, "SPY", start, end, config.initial_capital)
    basket_rows = [
        _buy_hold_benchmark(prices, ticker, start, end, config.initial_capital / len(config.tickers))
        for ticker in config.tickers
    ]
    basket_ending = sum(row["ending_value"] for row in basket_rows)
    basket_return = basket_ending / config.initial_capital - 1

    cost_rate = config.transaction_cost + config.slippage
    if trades.empty:
        trade_returns = pd.Series(dtype=float)
    else:
        trade_returns = 0.35 * trades["future_return"] - 2 * cost_rate * 0.35
    ci_low, ci_high = _bootstrap_ci(trade_returns)

    publication = summary.copy()
    publication["benchmark_spy_ending_value"] = spy["ending_value"]
    publication["benchmark_spy_return"] = spy["return"]
    publication["benchmark_basket_ending_value"] = basket_ending
    publication["benchmark_basket_return"] = basket_return
    publication["bootstrap_return_ci_low"] = ci_low
    publication["bootstrap_return_ci_high"] = ci_high
    publication["evaluation_start"] = start
    publication["evaluation_end"] = end
    publication["sample_warning"] = "Small trade sample; treat as preliminary despite strong observed P/L."
    write_frame(publication, config.backtest_dir / "publication_setup_results.csv")

    lines = [
        "# Frozen Setup-Quality Intraday Study",
        "",
        "## Abstract",
        "",
        "This study evaluates a frozen technical setup-quality rule set for intraday U.S. equity trading. The strategy trades only high-confidence, VWAP-aligned, volume-confirmed long setups using OHLCV-derived features and model probabilities. The objective is not candle-by-candle prediction, but selective trade identification where expected movement plausibly exceeds transaction costs and slippage.",
        "",
        "## Frozen Rule Set",
        "",
        "- Universe: SPY, AAPL, NVDA, TSLA, AMD, MSFT.",
        "- Horizons considered: 60m, 120m, 240m.",
        "- Model probability must be at least 0.70.",
        "- Absolute forward move candidate must be at least 0.20% in the research labeling layer.",
        "- Stock and SPY must both trade above session VWAP.",
        "- Stock and SPY must both have positive 30-minute momentum.",
        "- 30-minute volume z-score must exceed 0.5.",
        "- Entries are allowed only from 10:00 to 15:00.",
        "- Maximum two selected trades per session.",
        "- Position size is fixed at 35% of capital per trade.",
        f"- Transaction cost: {config.transaction_cost:.4%}; slippage: {config.slippage:.4%} per side.",
        "",
        "## Results",
        "",
        "```text",
        publication.to_string(index=False, float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Selected Trades",
        "",
        "```text",
        trades[["date", "ticker", "horizon", "model", "probability", "future_return", "quality_score"]].to_string(index=False, float_format=lambda value: f"{value:,.6f}")
        if not trades.empty
        else "No trades selected.",
        "```",
        "",
        "## Interpretation",
        "",
        "The result is economically meaningful if it remains positive after costs, beats SPY and the equal-weight basket over the same evaluation timestamps, and does so with controlled drawdown. However, a small number of trades means uncertainty remains high. The bootstrap interval is included to emphasize that the observed result may be fragile.",
        "",
        "## Limitations",
        "",
        "- Free intraday data availability limits the study window.",
        "- The sample is not yet long enough for strong publication-grade statistical confidence.",
        "- The rule set is long-only and does not model bid/ask spreads directly.",
        "- Results should be interpreted as research evidence, not trading advice.",
        "",
    ]
    (config.reports_dir / "publication_setup_report.md").write_text("\n".join(lines), encoding="utf-8")
    return publication


def main() -> None:
    generate_publication_setup_report(INTRADAY_CONFIG)


if __name__ == "__main__":
    main()
