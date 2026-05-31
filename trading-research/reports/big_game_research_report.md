# Big Game Research Report

## Question

Can an options-focused trading agent reach a 2x target, and can risk intervention stop it from giving the money back?

## Design

The experiment starts every agent with `$1,000`.

The target is `$2,000`.

The test period is `2025-05-01` through `2026-05-01`.

Agents are scored at each month end.

## Agents

`OptionsOnly_NoIntervention`

Buys monthly at-the-money call option proxies on the strongest momentum assets. It keeps risking capital after large wins.

`Options_RiskRules`

Uses simple mechanical rules. After reaching 2x, it moves into SPY/TLT/cash. After large drawdowns, it stops taking options risk.

`Options_HumanOverseer`

Simulates a human risk manager. The rules allow the overseer to approve, reduce, or reject new option exposure at month end.

`Options_CommitteeVeto`

Combines an options proposal with warnings from normal stock and cross-asset agents. If risk looks high or the target has been reached, it shrinks or vetoes options exposure.

Human benchmarks:

- SPY buy-and-hold
- QQQ buy-and-hold
- 60/40 portfolio

Other model benchmarks:

- Normal sector stock agent
- Cross-asset anything agent

## Results

| Agent | Ending Value | Return | Max Value | Hit 2x At End | Max Drawdown |
|---|---:|---:|---:|---|---:|
| Options_CommitteeVeto | $2,585.20 | 158.52% | $2,754.14 | Yes | -16.15% |
| Options_RiskRules | $2,493.88 | 149.39% | $2,835.82 | Yes | -23.13% |
| Options_HumanOverseer | $2,140.31 | 114.03% | $2,297.54 | Yes | -23.02% |
| Human_QQQ_BuyHold | $1,393.57 | 39.36% | $1,393.57 | No | -12.20% |
| Human_SPY_BuyHold | $1,285.03 | 28.50% | $1,285.03 | No | -9.14% |
| Anything_CrossAssetAgent | $1,266.31 | 26.63% | $1,317.59 | No | -12.34% |
| Human_60_40 | $1,144.97 | 14.50% | $1,144.97 | No | -7.34% |
| Normal_SectorStockAgent | $1,119.73 | 11.97% | $1,242.21 | No | -11.31% |
| OptionsOnly_NoIntervention | $155.01 | -84.50% | $3,755.75 | No | -95.87% |

## Main Insight

The raw options agent found the most explosive upside, but it could not keep the money.

The risk-aware options agents kept enough upside to finish above the 2x target.

The best result came from `Options_CommitteeVeto`, which mixed options opportunity generation with a risk manager that could lock gains.

## What This Does Not Prove

This does not prove that the strategy would work live.

The options engine is a proxy. It uses Black-Scholes monthly at-the-money calls because free Yahoo data does not provide clean historical option chains.

The next serious step is to test the same rules on real point-in-time option chains with bid/ask spreads.

## Bottom Line

The interesting idea is not:

> Options always win.

The interesting idea is:

> Options can create convex upside, but they need a hard risk process to survive.

## Code Map

- `ai_trading_arena/big_game.py` runs the experiment.
- `ai_trading_arena/big_game_agents/options_agents.py` contains the four options agents.
- `ai_trading_arena/big_game_agents/stock_agents.py` contains the normal stock and cross-asset agents.
- `ai_trading_arena/big_game_agents/benchmarks.py` contains the human-style benchmarks.
- `ai_trading_arena/big_game_agents/accounting.py` handles portfolio value, option proxy pricing, and trade execution.
