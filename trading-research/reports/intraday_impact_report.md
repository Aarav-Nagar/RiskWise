# Intraday Impact Experiment

This experiment tunes each agent on validation performance only, then locks the chosen configuration and evaluates it on the test split. The objective is cumulative return plus max drawdown, with a small trade-count penalty.

## Selected Validation Configurations

```text
           agent  horizon               model  threshold  top_k  position_size  ending_value  cumulative_return  max_drawdown  sharpe  number_of_trades  exposure_time  objective
ProbabilityAgent       10 logistic_regression     0.7000      4         0.2500    1,002.7669             0.0028       -0.0004  8.3647                 4         0.0009     0.0023
RiskManagedAgent      240             xgboost     0.7500      2         0.5000    1,016.2495             0.0162       -0.0109 10.9833                15         0.2235     0.0051
       TopKAgent       10 logistic_regression     0.7000      2         0.5000    1,005.5293             0.0055       -0.0007  8.3642                 4         0.0009     0.0047
```

## Locked Test Results

```text
           agent  horizon  starting_capital  ending_value  profit_loss  cumulative_return  return_vs_spy   sharpe  sortino  max_drawdown  win_rate  profit_factor  number_of_trades  exposure_time  transaction_cost_dollars  slippage_dollars  best_trade  worst_trade  drawdown_penalized_return               model  threshold  top_k  position_size  validation_objective  validation_ending_value  validation_return  validation_max_drawdown  validation_trades
RiskManagedAgent      240        1,000.0000    1,002.2735       2.2735             0.0023        -0.0079   2.1170   1.1475       -0.0139    0.1042         1.0445                22         0.1989                    5.4973            2.1989      0.0024      -0.0045                    -0.0117             xgboost     0.7500      2         0.5000                0.0051               1,016.2495             0.0162                  -0.0109                 15
ProbabilityAgent       10        1,000.0000      995.6666      -4.3334            -0.0043        -0.0145 -12.8502  -2.3024       -0.0043    0.0027         0.3887                16         0.0092                    1.9953            0.7981      0.0013      -0.0016                    -0.0087 logistic_regression     0.7000      4         0.2500                0.0023               1,002.7669             0.0028                  -0.0004                  4
       TopKAgent       10        1,000.0000      991.3423      -8.6577            -0.0087        -0.0188 -12.8521  -2.3028       -0.0087    0.0027         0.3886                16         0.0092                    3.9814            1.5926      0.0026      -0.0033                    -0.0173 logistic_regression     0.7000      2         0.5000                0.0047               1,005.5293             0.0055                  -0.0007                  4
```

## Interpretation

This is a cleaner impact test than selecting the best test result by hindsight. If a selected configuration fails on test, that is evidence that the validation edge did not generalize.
