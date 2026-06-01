# AI Agent Design

RiskWise uses agent roles to make the review feel like an investigation instead of a single model verdict.

The agents do not know the future. They look at the contract details, user rules, risk math, and available evidence. When data is missing, they should say what is missing.

## Bull Analyst

### What It Checks

The Bull Analyst looks for the strongest version of the user's thesis.

### Evidence It Uses

- user direction
- selected strategy
- trend or momentum context when available
- whether the contract has enough time for the thesis
- whether the breakeven move is plausible

### What It Outputs

- the best argument for the setup
- the evidence that supports it
- what would make the thesis stronger

### How It Avoids Fake Certainty

It should not say the trade will work. It should say what evidence would support the user's idea and what evidence is still missing.

## Skeptic

### What It Checks

The Skeptic looks for the cleanest reason the trade might fail.

### Evidence It Uses

- weak confirmation
- short expiration
- high breakeven
- missing liquidity
- missing IV or earnings context
- user behavior warnings from the profile

### What It Outputs

- the main objection
- the missing evidence
- the condition that would weaken or invalidate the setup

### How It Avoids Fake Certainty

It does not automatically reject every trade. It explains the failure mode and lets the user see what information would reduce that concern.

## Options Risk Agent

### What It Checks

The Options Risk Agent focuses on contract mechanics.

### Evidence It Uses

- strike
- premium
- expiration
- days to expiration
- bid/ask when available
- implied volatility when available
- option volume and open interest when available

### What It Outputs

- max loss
- estimated breakeven
- expiration pressure
- missing options-chain data
- volatility and liquidity warnings

### How It Avoids Fake Certainty

If RiskWise does not have the option chain, it should say that IV, Greeks, bid/ask, volume, and open interest are not verified.

## Sizing Judge

### What It Checks

The Sizing Judge checks whether the trade fits the user's account and rules.

### Evidence It Uses

- account size
- contracts
- premium
- max risk per trade
- max trades per week
- user's stated risk style

### What It Outputs

- account risk percentage
- whether the trade is inside the user's rule
- whether the position is small, moderate, or aggressive
- what size would be closer to the user's guardrail

### How It Avoids Fake Certainty

It does not decide whether the user should take the trade. It only explains whether the size fits the user's own risk limit.

## Risk Manager

### What It Checks

The Risk Manager looks at the whole decision.

### Evidence It Uses

- agent disagreement
- missing data
- profile memory
- repeated user mistakes
- volatility and event risk
- sizing and expiration risk

### What It Outputs

- final risk posture
- strongest concern
- what must be clarified before confidence improves
- a plain-language next question

### How It Avoids Fake Certainty

It should prefer "needs review" over confident language when the evidence is incomplete. The Risk Manager's job is discipline, not hype.

## Shared Agent Rules

All agents should follow these rules:

- do not give direct trade instructions
- do not claim live prices unless a data provider returned them
- do not hide missing data
- explain risk in plain language
- use numbers when the inputs support them
- separate contract math from market opinion
- keep the educational disclaimer visible in the product
