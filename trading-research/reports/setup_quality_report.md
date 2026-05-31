# Setup Quality Intraday Experiment

This experiment only trades high-confidence technical setups instead of predicting every candle.

Rules: probability >= 0.70, meaningful expected move, stock above VWAP, SPY above VWAP, positive 30m momentum, elevated volume, 10:00-15:00 only, max two trades per day.

## Results

```text
         strategy  starting_capital  ending_value  profit_loss  cumulative_return  return_vs_spy  sharpe_per_trade  sortino_per_trade  max_drawdown  win_rate  profit_factor  average_trade_return  best_trade  worst_trade  number_of_trades  transaction_cost_dollars  slippage_dollars
SetupQualityAgent      1,000.000000    985.349777   -14.650223          -0.014650      -0.024817               NaN                NaN      0.000000  0.000000       0.000000             -0.014650   -0.014650    -0.014650                 1                  0.350000          0.140000
```

## Selected Trades

```text
               date ticker  horizon   model  probability  future_return  quality_score
2026-05-06 10:37:00    AMD      240 xgboost     0.725110      -0.040458       0.412055
```
