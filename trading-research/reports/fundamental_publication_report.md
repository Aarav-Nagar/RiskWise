# Publication-Style Fundamental + Technical Study

## Design

This study compares a combined fundamental+technical ranking agent against ablations and placebo portfolios over the same tradable universe and dates. Fundamentals are lagged by 45 days after quarter end. The data source is free yfinance, so the study is not restatement-proof institutional point-in-time research.

Strategies tested: combined, fundamental-only, technical-only, quality-only, growth-only, SPY benchmark, equal-weight basket benchmark, and 250 cross-sectional score-shuffle placebo portfolios.

## Results

```text
                      strategy  starting_capital  ending_value  profit_loss  cumulative_return  spy_return  basket_return  return_vs_spy  return_vs_basket   sharpe   sortino  max_drawdown  average_turnover evaluation_start evaluation_end  bootstrap_return_ci_low  bootstrap_return_ci_high  placebo_p_value
combined_fundamental_technical      1,000.000000  1,344.622117   344.622117           0.344622    0.088830       0.090958       0.255792          0.253664 4.760374  9.809089     -0.088543          0.055738       2026-02-17     2026-05-13                 0.046497                  0.732908         0.000000
              fundamental_only      1,000.000000  1,257.199062   257.199062           0.257199    0.088830       0.090958       0.168369          0.166241 3.770302  8.008697     -0.124165          0.042623       2026-02-17     2026-05-13                -0.016464                  0.618443              NaN
                technical_only      1,000.000000  1,314.910809   314.910809           0.314911    0.088830       0.090958       0.226081          0.223952 5.077074 11.635443     -0.062473          0.049180       2026-02-17     2026-05-13                 0.062740                  0.639933              NaN
                  quality_only      1,000.000000  1,203.682931   203.682931           0.203683    0.088830       0.090958       0.114853          0.112725 3.371566  7.005555     -0.094033          0.036066       2026-02-17     2026-05-13                -0.034198                  0.508799              NaN
                   growth_only      1,000.000000  1,232.631482   232.631482           0.232631    0.088830       0.090958       0.143801          0.141673 3.505613  7.713827     -0.114664          0.042623       2026-02-17     2026-05-13                -0.029411                  0.578680              NaN
```

## Placebo Distribution

```text
count   250.000000
mean      0.083886
std       0.055582
min      -0.056227
5%        0.003878
50%       0.076870
95%       0.174798
max       0.240408
```

## Latest Selections

```text
                      strategy selection_date ticker  agent_score  fundamental_score  technical_score
                  quality_only     2026-05-13   AVGO     0.700094           0.717544         0.656410
                  quality_only     2026-05-13   NVDA     0.879720           0.951447         0.712821
              fundamental_only     2026-05-13    AMD     0.741334           0.718224         0.789744
                   growth_only     2026-05-13   ABBV     0.477419           0.509605         0.394872
                   growth_only     2026-05-13    AMD     0.741334           0.718224         0.789744
                   growth_only     2026-05-13   NVDA     0.879720           0.951447         0.712821
                   growth_only     2026-05-13   AVGO     0.700094           0.717544         0.656410
                  quality_only     2026-05-13    AMD     0.741334           0.718224         0.789744
                  quality_only     2026-05-13    CRM     0.453087           0.592237         0.128205
combined_fundamental_technical     2026-05-13    AMD     0.741334           0.718224         0.789744
combined_fundamental_technical     2026-05-13    CAT     0.514943           0.428991         0.712821
combined_fundamental_technical     2026-05-13   CSCO     0.630661           0.552807         0.810256
combined_fundamental_technical     2026-05-13   AVGO     0.700094           0.717544         0.656410
              fundamental_only     2026-05-13   NVDA     0.879720           0.951447         0.712821
combined_fundamental_technical     2026-05-13   NVDA     0.879720           0.951447         0.712821
                technical_only     2026-05-13   CSCO     0.630661           0.552807         0.810256
                technical_only     2026-05-13    AMD     0.741334           0.718224         0.789744
                technical_only     2026-05-13   NVDA     0.879720           0.951447         0.712821
                technical_only     2026-05-13    CAT     0.514943           0.428991         0.712821
                technical_only     2026-05-13   AVGO     0.700094           0.717544         0.656410
              fundamental_only     2026-05-13   CSCO     0.630661           0.552807         0.810256
              fundamental_only     2026-05-13    CRM     0.453087           0.592237         0.128205
              fundamental_only     2026-05-13   AVGO     0.700094           0.717544         0.656410
                  quality_only     2026-05-13    MCD     0.439050           0.513443         0.266667
                   growth_only     2026-05-13   ORCL     0.458870           0.423553         0.533333
```

## Interpretation

A publication-grade interpretation should emphasize benchmark-relative performance, ablation consistency, placebo p-value, drawdown, and the point-in-time limitation of free fundamentals.
