# QA Playbook

Use this checklist before calling RiskWise mockup-ready, TestFlight-ready, or production-ready.

## Backend Checks

Run:

```bash
cd backend
python -m pytest api/tests
```

When Mongo Atlas env vars are available, also run:

```bash
cd backend/api
python scripts/production_persistence_smoke.py
```

Verify:

- `/health` returns healthy status.
- `/ready` does not leak secrets and reports auth/JWT, Sentry, AI fallback, and market-provider state.
- `/market/providers` clearly shows active, missing, delayed, estimated, manual, and reference-only sources.
- `/trade-check` returns specific validation errors for bad inputs.
- Production protected routes reject missing/invalid Clerk bearer tokens.
- Production protected routes reject cross-user access.
- `/chat` returns structured output, not raw model text.
- Deep Analysis returns five agents.
- Missing IV, Greeks, bid/ask, volume, and open interest are not invented.

## Frontend Checks

Run:

```bash
cd frontend/mobile-demo
npm run typecheck
npm run export:web
npx playwright test --config=playwright.config.cjs
npm run doctor
```

Smoke test:

- App opens to auth/welcome state.
- Sign-in screen does not show raw backend errors.
- Bottom nav has only Home, Check, Coach, Profile.
- No screen overflows at phone width.
- Check flow can complete with valid manual data.
- Report opens after valid Check.
- Coach can answer a basic options question.
- Profile settings can be edited without layout issues.

## Check Flow Test Cases

Valid long call:

- Ticker: AAPL
- Side: call
- Strike: 200
- Expiration: future date
- Premium: 2.50
- Contracts: 1
- Account size: 25000
- Max risk rule: 2%

Expected:

- Max loss: premium x contracts x 100.
- Breakeven: strike + premium for long call.
- DTE is positive.
- Account risk percent is shown.
- Missing optional data is labeled, not hidden.

Invalid cases:

- No ticker selected.
- Past expiration.
- Strike equals 0.
- Premium equals 0 for long option.
- Contracts equals 0.
- Bid greater than ask.
- Account size equals 0.

Expected:

- Field-specific error message.
- No generic "Something went wrong" unless the backend actually failed.

## Screenshot / Upload Checks

Expected behavior:

- Check flow offers camera, photo library, and file/image upload.
- No fake random extraction.
- If text is readable, extract likely fields.
- If fields are missing, show exactly what is missing.
- User confirms fields before analysis.
- If no OCR/vision provider is configured, show manual-review state instead of pretending extraction worked.

## Coach Checks

Ask:

- "Hi"
- "What is IV crush?"
- "Explain that simpler."
- "What about my selected check?"
- "Run deep analysis."
- "Should I buy this?"

Expected:

- Natural short greeting.
- Clear options explanation.
- Follow-up references prior topic.
- Selected-check answer uses report context.
- Deep Analysis shows agents, top risks, missing data, and what RiskWise used.
- Direct advice is redirected into educational risk framing.

## Profile Checks

Verify:

- Trader DNA edit persists.
- Risk rules edit persists.
- Coach style changes answer style.
- AI memory/context sections are understandable.
- Sign out works.
- Password reset path is visible.
- Delete account requires confirmation and cleans app data when backend support is configured.

## App Store / TestFlight Checks

Before TestFlight:

- App icon appears correctly.
- Splash screen appears correctly.
- Privacy policy and terms links are available.
- Camera/photo permission copy is accurate.
- Store copy avoids signals, guaranteed profit, and trade execution language.
- Real iPhone smoke test passes.
