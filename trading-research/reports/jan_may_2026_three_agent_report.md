# Three-Agent Intraday Horizon Experiment

This report compares ProbabilityAgent, TopKAgent, and RiskManagedAgent across the expanded intraday horizon ladder using technical OHLCV features only.

## Selected Model And Threshold By Horizon

```text
 horizon               model  threshold
       1 logistic_regression      0.625
       3 logistic_regression      0.700
       5 logistic_regression      0.600
      10 logistic_regression      0.625
      15 logistic_regression      0.625
      30 logistic_regression      0.625
      60 logistic_regression      0.625
     120             xgboost      0.500
     240 logistic_regression      0.675
```

## Best Ending Capital

```text
           agent  horizon  starting_capital  ending_value  profit_loss  cumulative_return  return_vs_spy   sharpe  sortino  max_drawdown  win_rate  profit_factor  number_of_trades  exposure_time  transaction_cost_dollars  slippage_dollars  best_trade  worst_trade  drawdown_penalized_return
       TopKAgent      120        1,000.0000    1,016.0050      16.0050             0.0160         0.0032   5.1963   6.3641       -0.0269    0.5178         1.0526               169         1.0000                   28.1438           11.2575      0.0084      -0.0105                    -0.0109
ProbabilityAgent      240        1,000.0000      993.6631      -6.3369            -0.0063        -0.0191  -9.1255  -2.3617       -0.0126    0.0249         0.6811                20         0.0459                    2.4833            0.9933      0.0019      -0.0039                    -0.0189
       TopKAgent      240        1,000.0000      991.1276      -8.8724            -0.0089        -0.0216  -9.1252  -2.3617       -0.0176    0.0249         0.6811                20         0.0459                    3.4672            1.3869      0.0026      -0.0055                    -0.0265
ProbabilityAgent        3        1,000.0000      991.0084      -8.9916            -0.0090        -0.0218 -15.6068  -2.3146       -0.0105    0.0037         0.2709                16         0.0119                    1.9888            0.7955      0.0012      -0.0033                    -0.0195
RiskManagedAgent      240        1,000.0000      989.5807     -10.4193            -0.0104        -0.0232 -11.1297  -2.3423       -0.0192    0.0201         0.5738                14         0.0354                    2.4309            0.9724      0.0026      -0.0057                    -0.0296
RiskManagedAgent        3        1,000.0000      989.5770     -10.4230            -0.0104        -0.0232 -13.3213  -1.8196       -0.0126    0.0037         0.3093                20         0.0110                    2.7651            1.1060      0.0017      -0.0049                    -0.0230
RiskManagedAgent        1        1,000.0000      989.4168     -10.5832            -0.0106        -0.0234 -15.4738  -2.4469       -0.0117    0.0055         0.3062                22         0.0119                    3.1474            1.2589      0.0017      -0.0044                    -0.0223
ProbabilityAgent        1        1,000.0000      989.2778     -10.7222            -0.0107        -0.0235 -21.4696  -4.6424       -0.0115    0.0091         0.2790                22         0.0219                    2.7322            1.0929      0.0012      -0.0028                    -0.0222
       TopKAgent        3        1,000.0000      987.7059     -12.2941            -0.0123        -0.0251 -15.5319  -2.3129       -0.0144    0.0037         0.2749                22         0.0119                    2.7787            1.1115      0.0017      -0.0047                    -0.0267
       TopKAgent        1        1,000.0000      985.1073     -14.8927            -0.0149        -0.0277 -21.4782  -4.6594       -0.0160    0.0091         0.2799                26         0.0219                    3.8320            1.5328      0.0017      -0.0039                    -0.0309
```

## Best Sharpe

```text
           agent  horizon  starting_capital  ending_value  profit_loss  cumulative_return  return_vs_spy   sharpe  sortino  max_drawdown  win_rate  profit_factor  number_of_trades  exposure_time  transaction_cost_dollars  slippage_dollars  best_trade  worst_trade  drawdown_penalized_return
       TopKAgent      120        1,000.0000    1,016.0050      16.0050             0.0160         0.0032   5.1963   6.3641       -0.0269    0.5178         1.0526               169         1.0000                   28.1438           11.2575      0.0084      -0.0105                    -0.0109
ProbabilityAgent      120        1,000.0000      974.3705     -25.6295            -0.0256        -0.0384  -7.6494  -8.0081       -0.0513    0.5009         0.9233               246         1.0000                   30.0490           12.0196      0.0053      -0.0148                    -0.0770
       TopKAgent      240        1,000.0000      991.1276      -8.8724            -0.0089        -0.0216  -9.1252  -2.3617       -0.0176    0.0249         0.6811                20         0.0459                    3.4672            1.3869      0.0026      -0.0055                    -0.0265
ProbabilityAgent      240        1,000.0000      993.6631      -6.3369            -0.0063        -0.0191  -9.1255  -2.3617       -0.0126    0.0249         0.6811                20         0.0459                    2.4833            0.9933      0.0019      -0.0039                    -0.0189
RiskManagedAgent      240        1,000.0000      989.5807     -10.4193            -0.0104        -0.0232 -11.1297  -2.3423       -0.0192    0.0201         0.5738                14         0.0354                    2.4309            0.9724      0.0026      -0.0057                    -0.0296
RiskManagedAgent        3        1,000.0000      989.5770     -10.4230            -0.0104        -0.0232 -13.3213  -1.8196       -0.0126    0.0037         0.3093                20         0.0110                    2.7651            1.1060      0.0017      -0.0049                    -0.0230
RiskManagedAgent        1        1,000.0000      989.4168     -10.5832            -0.0106        -0.0234 -15.4738  -2.4469       -0.0117    0.0055         0.3062                22         0.0119                    3.1474            1.2589      0.0017      -0.0044                    -0.0223
       TopKAgent        3        1,000.0000      987.7059     -12.2941            -0.0123        -0.0251 -15.5319  -2.3129       -0.0144    0.0037         0.2749                22         0.0119                    2.7787            1.1115      0.0017      -0.0047                    -0.0267
ProbabilityAgent        3        1,000.0000      991.0084      -8.9916            -0.0090        -0.0218 -15.6068  -2.3146       -0.0105    0.0037         0.2709                16         0.0119                    1.9888            0.7955      0.0012      -0.0033                    -0.0195
RiskManagedAgent      120        1,000.0000      968.1549     -31.8451            -0.0318        -0.0446 -17.8038  -5.3957       -0.0351    0.0346         0.5193                56         0.0804                    9.1297            3.6519      0.0031      -0.0105                    -0.0670
```

## Best Drawdown-Penalized Return

```text
           agent  horizon  starting_capital  ending_value  profit_loss  cumulative_return  return_vs_spy   sharpe  sortino  max_drawdown  win_rate  profit_factor  number_of_trades  exposure_time  transaction_cost_dollars  slippage_dollars  best_trade  worst_trade  drawdown_penalized_return
       TopKAgent      120        1,000.0000    1,016.0050      16.0050             0.0160         0.0032   5.1963   6.3641       -0.0269    0.5178         1.0526               169         1.0000                   28.1438           11.2575      0.0084      -0.0105                    -0.0109
ProbabilityAgent      240        1,000.0000      993.6631      -6.3369            -0.0063        -0.0191  -9.1255  -2.3617       -0.0126    0.0249         0.6811                20         0.0459                    2.4833            0.9933      0.0019      -0.0039                    -0.0189
ProbabilityAgent        3        1,000.0000      991.0084      -8.9916            -0.0090        -0.0218 -15.6068  -2.3146       -0.0105    0.0037         0.2709                16         0.0119                    1.9888            0.7955      0.0012      -0.0033                    -0.0195
ProbabilityAgent        1        1,000.0000      989.2778     -10.7222            -0.0107        -0.0235 -21.4696  -4.6424       -0.0115    0.0091         0.2790                22         0.0219                    2.7322            1.0929      0.0012      -0.0028                    -0.0222
RiskManagedAgent        1        1,000.0000      989.4168     -10.5832            -0.0106        -0.0234 -15.4738  -2.4469       -0.0117    0.0055         0.3062                22         0.0119                    3.1474            1.2589      0.0017      -0.0044                    -0.0223
RiskManagedAgent        3        1,000.0000      989.5770     -10.4230            -0.0104        -0.0232 -13.3213  -1.8196       -0.0126    0.0037         0.3093                20         0.0110                    2.7651            1.1060      0.0017      -0.0049                    -0.0230
       TopKAgent      240        1,000.0000      991.1276      -8.8724            -0.0089        -0.0216  -9.1252  -2.3617       -0.0176    0.0249         0.6811                20         0.0459                    3.4672            1.3869      0.0026      -0.0055                    -0.0265
       TopKAgent        3        1,000.0000      987.7059     -12.2941            -0.0123        -0.0251 -15.5319  -2.3129       -0.0144    0.0037         0.2749                22         0.0119                    2.7787            1.1115      0.0017      -0.0047                    -0.0267
RiskManagedAgent      240        1,000.0000      989.5807     -10.4193            -0.0104        -0.0232 -11.1297  -2.3423       -0.0192    0.0201         0.5738                14         0.0354                    2.4309            0.9724      0.0026      -0.0057                    -0.0296
ProbabilityAgent       15        1,000.0000      984.6805     -15.3195            -0.0153        -0.0281 -22.9218  -8.7577       -0.0153    0.0165         0.4213                74         0.0532                    9.1857            3.6743      0.0024      -0.0026                    -0.0306
```

## Caveat

This run uses the available free Yahoo recent-window 1-minute data unless a historical intraday provider key is configured. It is a smoke-test implementation of the agent framework, not the full Jan-May 2026 historical experiment.
