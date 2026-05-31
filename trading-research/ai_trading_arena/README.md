# AI Paper-Trading Arena

This folder contains a forward-only paper-trading competition. It is designed for experiments like:

> Freeze several AI/strategy agents before tomorrow's market opens, give each `$100`, and compare who earns the most by the close.

The arena does not claim to predict prices. It creates auditable submissions and scores them later so the experiment cannot be quietly rewritten after the fact.

## Commands

Freeze agent portfolios:

```bash
python -m ai_trading_arena submit --trade-date 2026-05-15 --force
```

Score after the target day's open/close data exists:

```bash
python -m ai_trading_arena score --trade-date 2026-05-15
```

Show all scored contests:

```bash
python -m ai_trading_arena leaderboard
```

Run the market-like live paper lab:

```bash
python -m ai_trading_arena live --seconds 1800 --interval 10
```

Replay a completed intraday session as if bars were arriving live:

```bash
python -m ai_trading_arena replay-live --trade-date 2026-05-15
```

## Rules

- Starting capital: `$100`
- Long/cash only
- No leverage
- Generic agents max out at 40% per ticker and 5 holdings
- SPY benchmark is allowed to be 100% SPY
- Cost: 0.10% of invested capital
- Entry: target day open
- Exit: target day close

## Agents

- `SPY_Benchmark`: passive comparison.
- `RandomAgent`: seeded random sanity check.
- `MomentumAgent`: trend and relative-strength technical ranking.
- `MeanReversionAgent`: oversold bounce ranking with a trend filter.
- `FundamentalQualityAgent`: latest saved factor quality score, fallback to momentum.
- `BlendedAIAgent`: locked blend of saved fundamental and technical scores.
- `RiskManagedAgent`: volatility-scaled version of the blend with partial cash.
- `ITContextAgent`: information-technology specialist with catalysts, sector rotation, liquidity, and technical context.
- `HealthCareContextAgent`: health-care specialist with fundamentals, catalysts, earnings proximity, and risk context.
- `DiversifiedContextAgent`: non-tech/non-health-care sector specialist.
- `CumulativeOptionsContextAgent`: cumulative context model that also uses options-chain sentiment when available.

## Outputs

- `arena/submissions/YYYY-MM-DD.json`
- `arena/submissions/YYYY-MM-DD.csv`
- `arena/results/YYYY-MM-DD_results.csv`
- `arena/live/*_equity.csv`
- `arena/live/*_trades.csv`
