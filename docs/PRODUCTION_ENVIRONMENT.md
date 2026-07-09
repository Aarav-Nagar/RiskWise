# Production Environment

Last updated: July 9, 2026

This file tracks production and TestFlight environment decisions without storing secrets. Secret values must stay in vendor dashboards, EAS environment variables, or the ignored local file `config/.env`.

## Current TestFlight Decision

- Backend host: Render, `https://riskwise-api.onrender.com`
- Database: MongoDB Atlas, database `finance_app`
- Mobile build system: EAS, project `@aaravn/riskwise`
- Clerk mode: development Clerk keys are acceptable only for a limited internal TestFlight while production Clerk is being set up.
- Market data mode: `hybrid` with yfinance delayed options enabled, plus clear missing-data labels.
- AI mode: `gemini,openai,fallback`; hosted providers activate only when dashboard keys exist, and deterministic fallback remains available.

## Current Hosted Caveat

The live Render service is deployed from the current backend contract: `/market/providers` and `/ai/providers` return 200, Mongo is connected, and the market provider stack is active. `/ready` can still report `degraded` until hosted AI, Sentry, and production Clerk hardening values are configured.

## Render Environment Variables

Set these in Render for `riskwise-api`.

Non-secret values:

```text
APP_ENV=production
APP_STORAGE_PROVIDER=mongo
MONGODB_DATABASE=finance_app
LLM_PROVIDER_ORDER=gemini,openai,fallback
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_VERSION=v1beta
OPENAI_MODEL=gpt-5-mini
MARKET_DATA_PROVIDER=hybrid
ENABLE_YFINANCE_OPTIONS=true
```

Secret or dashboard-owned values:

```text
MONGODB_URI
CLERK_SECRET_KEY
CLERK_ISSUER
CLERK_JWKS_URL
CLERK_AUDIENCE
CLERK_AUTHORIZED_PARTIES
GEMINI_API_KEY
OPENAI_API_KEY
FMP_API_KEY
ALPHA_VANTAGE_API_KEY
POLYGON_API_KEY
MASSIVE_API_KEY
TRADIER_API_KEY
SENTRY_DSN
```

Only `MONGODB_URI` and Clerk backend values are required for the current internal beta path. AI and market-data provider keys improve output quality but are not required because the backend exposes explicit fallback and missing-data states.

## EAS TestFlight Environment

The `testflight` profile points to:

```text
EXPO_PUBLIC_API_BASE_URL=https://riskwise-api.onrender.com
```

For production Clerk, replace the current development publishable key with the production publishable key in EAS env or the EAS build profile:

```text
EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
```

The Clerk publishable key is client-visible. The Clerk secret key must never be placed in the Expo app.

## EAS Production Environment

The `production` profile points to:

```text
EXPO_PUBLIC_API_BASE_URL=https://riskwise-api.onrender.com
EXPO_PUBLIC_APP_ENV=production
RISKWISE_REQUIRE_PRODUCTION_CLERK=true
```

Set this value in the EAS `production` environment before an App Store build:

```text
EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
```

The production EAS build runs `scripts/validate-production-env.cjs` and fails fast if the Clerk publishable key is missing or still uses `pk_test_`.

As of July 9, 2026, the non-secret EAS production variables are also set remotely for `@aaravn/riskwise`: `EXPO_PUBLIC_API_BASE_URL`, `EXPO_PUBLIC_APP_ENV`, and `RISKWISE_REQUIRE_PRODUCTION_CLERK`. The production Clerk publishable key still must be added to EAS after a Clerk production instance exists.

## Clerk Production Switch

Recommended before inviting external beta testers:

1. Create a Clerk production instance for RiskWise.
2. Copy the production publishable key into EAS as `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY`.
3. Copy the production backend values into Render: `CLERK_SECRET_KEY`, `CLERK_ISSUER`, `CLERK_JWKS_URL`, and any audience or authorized-party restrictions.
4. Redeploy Render.
5. Rebuild TestFlight with EAS.
6. Verify `/ai/providers`, `/market/providers`, `/ready`, sign-in, sign-out, profile persistence, and check persistence.

For a small internal TestFlight, development Clerk can be used temporarily if testers understand accounts may be reset during the production switch.

## Secret Rotation Plan

Rotate these before serious beta because current values were shared during setup:

- MongoDB Atlas database user password, then update `MONGODB_URI` in Render and local `config/.env`.
- Clerk keys by switching to production Clerk, or by rotating the current development secret if development remains in use.
- Expo token in Expo account settings, then update local `config/.env`.
- Any future AI or market-data provider keys immediately after they are pasted into chat or logs.

After rotating, run:

```bash
python scripts/verify_production_state.py --strict

cd backend
python -m pytest api/tests
python api/scripts/production_persistence_smoke.py

cd ../frontend/mobile-demo
npm run typecheck
npm run doctor
npm run export:web
npm run qa:smoke
```

## Provider Recommendation

For internal TestFlight:

- Keep `MARKET_DATA_PROVIDER=hybrid`.
- Keep `ENABLE_YFINANCE_OPTIONS=true`.
- Add no paid market key until the core account, persistence, and report flows are stable.
- Keep `LLM_PROVIDER_ORDER=gemini,openai,fallback`.
- Add Gemini first if OCR/image understanding becomes important; add OpenAI later if answer quality needs a second hosted model.

For broader beta:

- Add FMP or Alpha Vantage for stock quotes, profile, news, and earnings.
- Add Polygon, Massive, or Tradier only when live option-chain, bid/ask, IV, Greeks, volume, and open interest are required.
- Keep UI copy honest: delayed, estimated, manual, and missing fields must remain visible.
