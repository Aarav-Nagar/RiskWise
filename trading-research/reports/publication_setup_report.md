# Frozen Setup-Quality Intraday Study

## Abstract

This study evaluates a frozen technical setup-quality rule set for intraday U.S. equity trading. The strategy trades only high-confidence, VWAP-aligned, volume-confirmed long setups using OHLCV-derived features and model probabilities. The objective is not candle-by-candle prediction, but selective trade identification where expected movement plausibly exceeds transaction costs and slippage.

## Frozen Rule Set

- Universe: SPY, AAPL, NVDA, TSLA, AMD, MSFT.
- Horizons considered: 60m, 120m, 240m.
- Model probability must be at least 0.70.
- Absolute forward move candidate must be at least 0.20% in the research labeling layer.
- Stock and SPY must both trade above session VWAP.
- Stock and SPY must both have positive 30-minute momentum.
- 30-minute volume z-score must exceed 0.5.
- Entries are allowed only from 10:00 to 15:00.
- Maximum two selected trades per session.
- Position size is fixed at 35% of capital per trade.
- Transaction cost: 0.0500%; slippage: 0.0200% per side.

## Results

```text
         strategy  starting_capital  ending_value  profit_loss  cumulative_return  return_vs_spy  sharpe_per_trade  sortino_per_trade  max_drawdown  win_rate  profit_factor  average_trade_return  best_trade  worst_trade  number_of_trades  transaction_cost_dollars  slippage_dollars  benchmark_spy_ending_value  benchmark_spy_return  benchmark_basket_ending_value  benchmark_basket_return  bootstrap_return_ci_low  bootstrap_return_ci_high    evaluation_start      evaluation_end                                                        sample_warning
SetupQualityAgent      1,000.000000    985.349777   -14.650223          -0.014650      -0.024817               NaN                NaN      0.000000  0.000000       0.000000             -0.014650   -0.014650    -0.014650                 1                  0.350000          0.140000                1,028.339687              0.028340                   1,076.658609                 0.076659                -0.014650                 -0.014650 2026-05-04 10:08:00 2026-05-11 11:59:00 Small trade sample; treat as preliminary despite strong observed P/L.
```

## Selected Trades

```text
               date ticker  horizon   model  probability  future_return  quality_score
2026-05-06 10:37:00    AMD      240 xgboost     0.725110      -0.040458       0.412055
```

## Interpretation

The result is economically meaningful if it remains positive after costs, beats SPY and the equal-weight basket over the same evaluation timestamps, and does so with controlled drawdown. However, a small number of trades means uncertainty remains high. The bootstrap interval is included to emphasize that the observed result may be fragile.

## Limitations

- Free intraday data availability limits the study window.
- The sample is not yet long enough for strong publication-grade statistical confidence.
- The rule set is long-only and does not model bid/ask spreads directly.
- Results should be interpreted as research evidence, not trading advice.
