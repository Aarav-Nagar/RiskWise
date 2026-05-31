# Publication-Style Fundamental + Technical Study

## Design

This study compares a combined fundamental+technical ranking agent against ablations and placebo portfolios over the same tradable universe and dates. Fundamental source: fmp. FMP uses filing/accepted dates from the provider when available; free data remains limited to the latest statement history.

Strategies tested: combined, fundamental-only, technical-only, quality-only, growth-only, SPY benchmark, equal-weight basket benchmark, and 250 cross-sectional score-shuffle placebo portfolios.

## Results

```text
                      strategy  starting_capital  ending_value  profit_loss  cumulative_return  spy_return  basket_return  return_vs_spy  return_vs_basket   sharpe  sortino  max_drawdown  average_turnover evaluation_start evaluation_end  bootstrap_return_ci_low  bootstrap_return_ci_high  placebo_p_value
combined_fundamental_technical      1,000.000000  1,080.306602    80.306602           0.080307    0.070923       0.082364       0.009384         -0.002057 1.776090 2.338943     -0.060036          0.140123       2026-02-26     2026-05-13                -0.116686                  0.301002         0.480000
              fundamental_only      1,000.000000  1,066.710408    66.710408           0.066710    0.070923       0.082364      -0.004212         -0.015654 1.493849 2.084562     -0.060036          0.132716       2026-02-26     2026-05-13                -0.127956                  0.285269              NaN
                technical_only      1,000.000000  1,224.802885   224.802885           0.224803    0.070923       0.082364       0.153880          0.142439 3.555859 6.161467     -0.060036          0.103086       2026-02-26     2026-05-13                -0.038935                  0.574214              NaN
                  quality_only      1,000.000000  1,036.078054    36.078054           0.036078    0.070923       0.082364      -0.034845         -0.046286 0.891581 1.193603     -0.060036          0.117901       2026-02-26     2026-05-13                -0.148458                  0.246169              NaN
                   growth_only      1,000.000000  1,147.440304   147.440304           0.147440    0.070923       0.082364       0.076518          0.065076 2.716475 4.149858     -0.060036          0.132716       2026-02-26     2026-05-13                -0.080931                  0.429770              NaN
```

## Placebo Distribution

```text
count   250.000000
mean      0.081729
std       0.048282
min      -0.032823
5%        0.009982
50%       0.078694
95%       0.163983
max       0.201679
```

## Latest Selections

```text
                      strategy selection_date ticker  agent_score  fundamental_score  technical_score
                   growth_only     2026-05-13   NVDA     0.880040           0.957341         0.700000
                   growth_only     2026-05-13   PLTR     0.705817           0.952894         0.128571
                   growth_only     2026-05-13    AMD     0.771941           0.764468         0.785714
              fundamental_only     2026-05-13   META     0.607900           0.766882         0.235714
combined_fundamental_technical     2026-05-13  GOOGL     0.778257           0.790096         0.750000
              fundamental_only     2026-05-13  GOOGL     0.778257           0.790096         0.750000
                   growth_only     2026-05-13  GOOGL     0.778257           0.790096         0.750000
              fundamental_only     2026-05-13   PLTR     0.705817           0.952894         0.128571
                technical_only     2026-05-13    UNH     0.493578           0.351224         0.828571
                technical_only     2026-05-13   INTC     0.489167           0.349405         0.807143
                technical_only     2026-05-13   AMZN     0.628221           0.549438         0.807143
                technical_only     2026-05-13    AMD     0.771941           0.764468         0.785714
                technical_only     2026-05-13  GOOGL     0.778257           0.790096         0.750000
combined_fundamental_technical     2026-05-13   NVDA     0.880040           0.957341         0.700000
              fundamental_only     2026-05-13   NVDA     0.880040           0.957341         0.700000
combined_fundamental_technical     2026-05-13   PLTR     0.705817           0.952894         0.128571
              fundamental_only     2026-05-13    AMD     0.771941           0.764468         0.785714
                  quality_only     2026-05-13   NVDA     0.880040           0.957341         0.700000
                  quality_only     2026-05-13   PLTR     0.705817           0.952894         0.128571
                  quality_only     2026-05-13  GOOGL     0.778257           0.790096         0.750000
                  quality_only     2026-05-13   MSFT     0.641729           0.739600         0.414286
                  quality_only     2026-05-13   META     0.607900           0.766882         0.235714
combined_fundamental_technical     2026-05-13    AMD     0.771941           0.764468         0.785714
combined_fundamental_technical     2026-05-13   AAPL     0.686349           0.678175         0.707143
                   growth_only     2026-05-13   META     0.607900           0.766882         0.235714
```

## Interpretation

A publication-grade interpretation should emphasize benchmark-relative performance, ablation consistency, placebo p-value, drawdown, and the point-in-time limitation of free fundamentals.
