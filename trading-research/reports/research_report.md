# Mathematical Technical Analysis Research Report

## Research Question

This study evaluates whether mathematical technical-analysis features derived only from historical OHLCV data exhibit predictive utility for future stock returns across 1, 5, 20, and 30 trading-day horizons.

The framework deliberately excludes fundamentals, news, sentiment, analyst estimates, macro variables, and discretionary trading logic. Results should be interpreted as evidence about this restricted feature class, not as investment advice.

## Methodology

- Data source: Yahoo Finance daily OHLCV from `2018-01-01` through the latest downloaded session.
- Universe: 39 liquid U.S. stocks; `SPY` is used only as benchmark/relative technical reference.
- Splits: train through `2022-12-31`, validation during 2023, test from `2024-01-01` onward.
- Labels: positive forward close-to-close return for each horizon.
- Models: technical-rule baselines, logistic regression, random forest, and XGBoost when installed.
- Leakage controls: chronological splits, rolling features based only on past/current bars, and model preprocessing fit only on training rows.

## Predictive Results

Best test ROC-AUC by horizon:

```text
 horizon               model  roc_auc
       1 logistic_regression 0.509934
       5             xgboost 0.515408
      20 logistic_regression 0.553317
      30 logistic_regression 0.557255
```

## Backtest Results

Best average test Sharpe by horizon:

```text
 horizon        model   sharpe
       1 buy_and_hold 0.721619
       5 buy_and_hold 0.725450
      20 buy_and_hold 0.689851
      30 buy_and_hold 0.637710
```

## Interpretation

Any measured signal should be treated cautiously. Short-horizon equity returns are noisy and often close to statistically efficient after transaction costs. If 1D results cluster near random classification performance, that is consistent with the difficulty of extracting exploitable daily direction from price and volume alone.

Medium horizons such as 20D and 30D may show stronger technical structure when trend, volatility, and relative-momentum features persist across several weeks. However, stronger validation metrics do not necessarily imply durable tradability; the test-period backtests and transaction-cost drag are the more relevant sanity checks.

Feature importance should be interpreted as model-specific association, not causal evidence. Highly correlated indicators, overlapping rolling windows, and repeated horizon tests all increase the risk that apparent importance reflects redundant transformations of the same underlying price path.

## Limitations

- The stock universe is based on currently selected liquid names, which introduces survivorship and selection bias.
- Yahoo Finance data can contain revisions, missing values, corporate-action quirks, or ticker-specific gaps.
- Multiple horizons, indicators, models, and baselines increase the risk of false discoveries.
- Transaction costs are simplified and do not model spreads, borrow costs, taxes, liquidity, or market impact.
- A cash-only long strategy is less aggressive than a long/short strategy and avoids leverage assumptions.

## Conclusion

This framework is designed to measure whether mathematical technical indicators contain incremental predictive information under controlled experimental conditions. The appropriate conclusion depends on out-of-sample test evidence, not on isolated high-performing charts or validation-period wins.
