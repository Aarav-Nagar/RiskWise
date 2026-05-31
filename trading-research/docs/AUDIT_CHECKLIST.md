# Audit Checklist

Use this when asking other people to review the project.

## Data

- Does every signal use only data available before the trade date?
- Are Yahoo Finance revisions or adjusted prices changing results?
- Are there survivorship bias issues in the chosen universe?
- Are FX, bitcoin, ETF, and equity calendars aligned correctly?

## Options Proxy

- Is Black-Scholes a fair proxy for monthly at-the-money call pricing?
- Is the fixed volatility assumption too generous or too harsh?
- Are transaction costs realistic for options?
- Should bid/ask spread and implied volatility smile be modeled?
- Should options be marked daily with changing implied volatility?

## Execution

- Are monthly rebalances executed at the open after the signal date?
- Are portfolios marked at close consistently?
- Are entry/exit costs applied?
- Are fractional shares acceptable for this research question?

## Rules

- Were the intervention rules written before the run?
- Are the rules overfit to one lucky period?
- Does the committee veto use future information anywhere?
- Are drawdown and target rules applied consistently?

## Benchmarking

- Is QQQ a fair human benchmark for an options-heavy tech/momentum period?
- Should the options agents be compared to leveraged ETFs?
- Should there be a cash benchmark and a sector ETF benchmark?

## Conclusion

The current result is interesting, but not final. The strongest claim we can make is:

> Options convexity plus pre-committed risk intervention outperformed in this one-year proxy test.

The strongest thing we cannot claim yet:

> This would make money in live trading.
