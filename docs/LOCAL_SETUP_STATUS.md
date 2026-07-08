# Local Setup Status

Last updated: July 7, 2026

This file tracks local setup progress without storing secrets. Secret values belong only in `config/.env`, which is ignored by git.

## Configured Locally

- MongoDB Atlas connection is stored in `config/.env`.
- Mongo persistence smoke passed against Atlas.
- Clerk development keys are stored in `config/.env`.
- Clerk backend auth hardening tests pass with the local configuration.
- Expo token is stored in `config/.env`.
- EAS token verification passed for Expo account `aaravn`.
- Render backend is deployed at `https://riskwise-api.onrender.com`.
- Render `/health` returns `storage=mongo`.
- Render blueprint now targets `MARKET_DATA_PROVIDER=hybrid` with delayed yfinance options enabled for internal TestFlight.
- Atlas IP access includes `0.0.0.0/0` with the comment `Temporary Render TestFlight beta access`.
- EAS project is linked as `@aaravn/riskwise` with project ID `3e39a270-fce9-4c0c-9627-1d774b8bb09d`.
- EAS archive inspection passed for the `testflight` iOS profile.
- Backend tests pass: `python -m pytest api/tests`.
- Frontend typecheck passes: `npm run typecheck`.
- Expo Doctor passes: `npm run doctor`.
- Web export passes: `npm run export:web`.
- Playwright smoke passes: `npm run qa:smoke`.
- Mongo persistence smoke passes: `python backend/api/scripts/production_persistence_smoke.py`.
- Production environment and secret-rotation runbook exists at `docs/PRODUCTION_ENVIRONMENT.md`.

## Current Deployment Caveat

Render is deployed from GitHub `main`. This workspace is currently on `codex/production-readiness-hardening`, which contains newer backend/frontend readiness work. Before TestFlight, either merge the current branch to `main` or retarget Render to the current release branch and redeploy.

## Still Needed For TestFlight

- Apple Developer Program enrollment and App Store Connect app record.
- Production Clerk instance/keys for external beta. Current Clerk development keys are acceptable only for a limited internal TestFlight.
- Rotate Mongo, Clerk, and Expo secrets before serious beta because setup values were pasted during configuration.
- Add hosted AI and market-data provider keys only when the beta needs live quotes, OCR/image understanding, or higher-quality AI answers.
- Hosted privacy policy and terms URLs.
- EAS iOS build and real iPhone TestFlight smoke.

## Local Secret File

Expected path:

```text
config/.env
```

Current known non-secret env names in use:

```text
APP_ENV
APP_STORAGE_PROVIDER
MONGODB_URI
MONGODB_DATABASE
EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
CLERK_ISSUER
CLERK_JWKS_URL
EXPO_TOKEN
MARKET_DATA_PROVIDER
ENABLE_YFINANCE_OPTIONS
LLM_PROVIDER_ORDER
```
