# Mockup Ready Plan

RiskWise is moving from a working MVP into a clean, demo-ready product mockup. The goal is not to pretend every market-data field is institutional-grade. The goal is to make every screen feel complete, every unavailable data field honest, and every core flow usable without a developer explaining it.

## Definition Of Ready

The mockup is ready when a reviewer can open the app, understand the product in under one minute, run a trade check, ask RiskWiseAI about it, edit profile preferences, and see that the app is built around risk discipline rather than trade execution.

The four production surfaces stay fixed:

- Home
- Check
- Coach
- Profile

No extra tabs should be added until these four are excellent.

## What Must Feel Complete

### Home

Home should act as the command center, not a second navigation menu.

It should show:

- selected market context
- saved or recent checks
- data provider transparency
- one clear path back into Check or Coach

It should not become a crowded portfolio dashboard yet.

### Check

Check is the main product.

It should support:

- strict ticker selection
- stock idea flow
- option contract flow
- manual or uploaded contract context
- no past expirations
- clear strike, premium, contract, account-size, and risk-rule validation
- exact max loss, breakeven, DTE, required move, and account-risk math

The report should explain:

- what looks strong
- what looks weak
- what data is missing
- what would invalidate the setup
- what the five-agent committee found

### Coach

Coach should feel like a focused AI options-risk assistant.

It should support:

- normal conversation
- concise options explanations
- selected-check context
- Deep Analysis from the plus menu
- uploaded/manual contract context
- structured cards, issue blocks, missing-data labels, and what-used notes

The model should explain facts. The backend should calculate facts.

### Profile

Profile should feel like settings, not a content page.

It should support:

- trader DNA
- risk rules
- AI memory
- coach style
- saved context
- app preferences
- password reset
- sign out
- delete account data

Every preference should either persist to the backend or clearly behave as preview-only in unsigned demo mode.

## Backend Gates

The backend should provide:

- `/ready`
- `/market/providers`
- `/trade-check`
- `/chat`
- saved checks
- profile settings
- account deletion cleanup

Every protected user route should either verify Clerk auth or clearly run in preview/dev mode. No endpoint should require the frontend to guess whether data is real, delayed, estimated, manual, or missing.

## AI Gates

RiskWiseAI is mockup-ready when:

- Qwen/Ollama can be used locally when available
- hosted Gemini/OpenAI can be used when configured
- deterministic fallback still works
- Deep Analysis always returns five agent outputs
- malformed model JSON never reaches the UI
- no answer invents live IV, Greeks, bid/ask, OI, or volume
- no answer tells the user to buy or sell

## Market Data Gates

Free data should be layered honestly:

- FMP for quote, profile, news, and earnings when available
- yfinance for delayed option chains and expirations where available
- Massive/Polygon for reference contracts where available
- Alpha Vantage for stock-level fallback
- manual or uploaded broker data as first-class context

Every Check should receive a normalized context object with:

- underlying
- company profile
- contract
- liquidity
- volatility
- greeks
- events
- risk math
- data quality

If a field is missing, the UI should say it is missing and explain why it matters.

## QA Gates

Before calling the mockup ready:

- backend tests pass
- AI eval smoke passes
- frontend typecheck passes
- Expo web export passes
- phone preview opens without framework overlays
- console has no relevant app errors
- Check can generate a report
- Coach can answer about a selected report
- Profile edits do not overflow and save in the expected mode

## Known Limits

The mockup can be excellent without promising free live OPRA-grade options data. Real live bid/ask, provider-reported Greeks, IV, volume, and open interest may still require a broker connection or paid provider.

The mockup should be honest about this instead of hiding it.

## Next Work Order

1. Keep CI green.
2. Fix any preview runtime errors.
3. Verify backend readiness locally.
4. Smoke-test Home, Check, Coach, and Profile in the phone frame.
5. Polish report visuals and agent issue cards.
6. Add stronger manual/upload contract confirmation.
7. Re-run full tests and export.
8. Push only clean source changes, not generated clutter.
