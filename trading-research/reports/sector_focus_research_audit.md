# Sector Focus Walk-Forward Research Audit

## Experiment

- Strategy: Sector Focus Cumulative Context Agent
- Test window: 2024-05-01 through 2026-05-01
- Historical data available from: 2023-01-01
- Starting capital: $1,000
- Sectors: Information Technology, Health Care, Financials, Energy
- Rebalance frequency: monthly
- Benchmark: SPY

## Leakage Controls

- Signals are computed using dates strictly before each rebalance date.
- Rebalance orders execute at the next rebalance session open.
- Portfolio equity is marked at the close.
- Historical news and options sentiment are disabled for this walk-forward because Yahoo does not provide reliable point-in-time history for those fields.
- Saved factor rows are filtered by both `date <= signal_date` and, when present, `filing_date <= signal_date`.
- The final benchmark is cost-adjusted with entry and exit transaction costs.

## Results

| Metric | Agent | SPY |
|---|---:|---:|
| Ending value | $1,254.38 | $1,434.46 |
| Profit/Loss | $254.38 | $434.46 |
| Cumulative return | 25.44% | 43.59% |
| Excess return vs SPY | -18.15% | |
| Max drawdown | -14.37% | -19.00% |
| Daily volatility | 0.78% | 1.05% |
| Sharpe-like | 1.00 | 1.18 |
| Strategy costs | $26.12 | $2.44 |
| Strategy trades | 174 | |
| Rebalances | 25 | |

## Interpretation

The agent remained profitable and reduced drawdown relative to SPY, but it did not beat SPY over the two-year window. The strongest result is risk reduction, not return maximization. The strategy paid a meaningful cost drag from monthly turnover and gave up too much upside during strong broad-market periods.

This result is more credible than the earlier quick run because execution timing and factor availability are now stricter.

## Remaining Limitations

- Yahoo data is not a true institutional point-in-time dataset.
- Historical options and news context are neutralized rather than reconstructed from a paid archive.
- The universe is manually selected and may still introduce survivorship bias.
- The strategy is rule-based, not trained and cross-validated over many rolling regimes.
- Results should be treated as research diagnostics, not trading advice.
