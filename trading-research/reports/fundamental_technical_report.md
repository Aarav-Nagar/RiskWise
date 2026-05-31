# Fundamental + Technical Agent Study

This experiment combines quarterly business fundamentals with daily technical features. Fundamentals are lagged by 45 days after quarter end to reduce lookahead bias, but the data source is free yfinance and is not a true institutional point-in-time feed.

## Results

```text
                 strategy  starting_capital  ending_value  profit_loss  cumulative_return  spy_ending_value  spy_return  basket_ending_value  basket_return  return_vs_spy  return_vs_basket   sharpe  max_drawdown  average_turnover evaluation_start evaluation_end                                                                                                  point_in_time_caveat
FundamentalTechnicalAgent      1,000.000000  1,344.622117   344.622117           0.344622      1,088.830213    0.088830         1,090.958332       0.090958       0.255792          0.253664 4.760374     -0.088543          0.055738       2026-02-17     2026-05-13 Uses yfinance quarterly statements with 45-day reporting lag; not restatement-proof institutional point-in-time data.
```

## Recent Agent Selections

```text
selection_date ticker  agent_score  quality_score  growth_score  technical_score
    2026-04-24    CAT     0.530327       0.372807      0.533333         0.764103
    2026-04-24    AMD     0.745950       0.602395      0.933333         0.805128
    2026-04-24   CSCO     0.616815       0.509447      0.633333         0.764103
    2026-04-24   NVDA     0.892028       0.961201      0.933333         0.753846
    2026-04-24   AVGO     0.746248       0.655196      0.833333         0.810256
    2026-05-01   NVDA     0.858182       0.961201      0.933333         0.641026
    2026-05-01    AMD     0.744411       0.602395      0.933333         0.800000
    2026-05-01   AVGO     0.740094       0.655196      0.833333         0.789744
    2026-05-01   CSCO     0.622969       0.509447      0.633333         0.784615
    2026-05-01    CAT     0.525712       0.372807      0.533333         0.748718
    2026-05-08    AMD     0.741334       0.602395      0.933333         0.789744
    2026-05-08   NVDA     0.867412       0.961201      0.933333         0.671795
    2026-05-08   AVGO     0.724710       0.655196      0.833333         0.738462
    2026-05-08   CSCO     0.612200       0.509447      0.633333         0.748718
    2026-05-08    CRM     0.511549       0.588057      0.600000         0.323077
    2026-05-13   AVGO     0.700094       0.655196      0.833333         0.656410
    2026-05-13   CSCO     0.630661       0.509447      0.633333         0.810256
    2026-05-13   NVDA     0.879720       0.961201      0.933333         0.712821
    2026-05-13    AMD     0.741334       0.602395      0.933333         0.789744
    2026-05-13    CAT     0.514943       0.372807      0.533333         0.712821
```

## Financial Interpretation

This agent is designed for swing allocation, not intraday scalping. A valid positive result would require beating SPY and the equal-weight basket after turnover costs while keeping drawdown controlled.
