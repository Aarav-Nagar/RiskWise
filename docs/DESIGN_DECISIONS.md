# Design Decisions

RiskWise started as a research idea, but the app is being designed as a decision-support tool. This file explains the choices behind the product so the repo shows more than just code.

## Why RiskWise Is Not A Trading Bot

RiskWise is not meant to place trades or tell someone what to buy or sell. The goal is to help a user slow down before making a risky decision.

Options can look simple from the outside, but one contract can involve direction, time, volatility, liquidity, and position sizing all at once. A trading bot would hide too much of that process. RiskWise should do the opposite: show the assumptions, the risk, and the missing information.

## Why The App Focuses On Options Risk

The earlier options-agent experiments showed an important lesson: options can create large upside very quickly, but unmanaged risk can destroy those gains just as fast.

That changed the direction of the app. Instead of trying to predict stock prices, RiskWise focuses on questions like:

- How much can this contract lose?
- What move is needed to break even?
- Is the position too large for the account?
- Is expiration too close?
- What information is missing before this check is trustworthy?

That feels more useful and more honest than pretending the app knows the future.

## Why The App Uses A Check Flow

The check flow exists because many bad trades happen too quickly. A user sees a setup, gets excited, and skips the boring questions.

RiskWise turns those questions into steps:

- ticker
- direction
- structure
- expiration
- strike and premium
- contracts and sizing

The point is not to make the app slower for no reason. The point is to make the user prove that the setup has enough information to review.

## Why There Are Three Check Paths

RiskWise supports three starting points because users do not always arrive with the same level of detail.

**Stock Idea** is for the early stage. The user has a ticker and an outlook, but not a contract. RiskWise can slow the idea down and suggest what kind of structure would need to be reviewed next.

**Option Contract** is for users who already know the ticker, strike, expiration, premium, and size. This path goes straight into contract math and issue detection.

**Screenshot** is for the realistic case where a user is looking at a broker screen. The app should eventually extract the contract details, then ask the user to confirm them before analysis.

These paths keep the app flexible without adding extra tabs.

## Why The App Uses Investigation Language

RiskWise should not sound like it is predicting the market.

Words like "signal," "prediction," and "trade alert" can make the app feel more certain than it really is. The product uses words like "check," "investigation," "evidence," "missing context," and "needs review" because those words better match what the app can honestly do.

The app can calculate risk and organize reasoning. It cannot know the future.

## Why RiskWiseAI Exists

RiskWiseAI is an explainer and coach, not a signal generator.

The user should be able to ask normal questions like "What is IV crush?" or specific questions like "Why is this contract risky?" The AI should explain the trade in plain language, use numbers when useful, and ask for missing information when the setup is incomplete.

The AI should not sound like a hype machine. It should be calm, direct, and risk-aware.

## Why Profile Memory Matters

Different users need different coaching.

One user may want simple explanations. Another may want formulas and stricter risk comments. Someone else may already know options basics but struggle with oversizing or chasing entries.

That is why the profile stores things like:

- experience level
- risk style
- explanation style
- sectors of interest
- common mistakes to watch
- max risk per trade

These settings should change how RiskWiseAI responds. If a user chooses "strict about risk," the AI should lead with sizing and downside. If a user chooses "step-by-step," the AI should explain slowly and clearly.

## Why The UI Uses Green And White

RiskWise uses a green and white visual style because the app is supposed to feel calm, careful, and trustworthy.

The goal is not to make trading feel like a game. Bright red and dark neon screens can make risk feel exciting. RiskWise should do the opposite. The interface should make the user feel like they are reviewing a decision, not chasing a scoreboard.

## Why Missing Data Is Shown Instead Of Hidden

One of the easiest ways to make a finance app look smarter than it is would be to hide missing data.

RiskWise should not do that.

If the app does not know implied volatility, bid/ask spread, open interest, option volume, earnings date, or the live option chain, it should say so. Missing data is part of the risk review.

This is especially important for options because the stock price alone is not enough. A call can lose money even if the stock goes up if the premium, timing, or volatility setup is bad.

## Why The App Starts Simple

The app could eventually include portfolios, live news, alerts, option chains, and dashboards. Those features are useful, but they can also make the product feel crowded.

The first version should focus on the core loop:

1. Check a trade.
2. Understand the risk.
3. Ask RiskWiseAI questions.
4. Save useful context in the profile.

That is enough to test whether the product is actually helpful before adding more screens.

## Current Tradeoffs

Some parts of RiskWise are still experimental.

The scoring system is useful for structure and education, but it is not the same as a live institutional options model. It needs real options-chain data before it can fully evaluate implied volatility, Greeks, liquidity, and pricing.

There is also a balance between clarity and complexity. A professional options model could show many advanced metrics, but a normal user may not know what to do with them. RiskWise should show enough math to be useful without burying the user.

The App Store direction also matters. The app needs to be careful about wording, disclaimers, privacy, and financial claims. It should be clear that this is educational decision support, not financial advice.

## Next Design Questions

The biggest open questions are:

- Which live options provider should power contract data?
- How much user context should RiskWiseAI remember?
- How should confidence and uncertainty be shown without making fake certainty?
- Should the app focus more on beginners, active options traders, or students learning finance?
- How should saved checks become useful feedback instead of just a history list?

These are product questions as much as technical questions. The code should keep improving, but the app only works if the design stays honest about risk.
