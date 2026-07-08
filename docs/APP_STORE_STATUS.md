# App Store Status

RiskWise is not yet public App Store ready. It is moving toward a TestFlight beta.

## Current State

- App name: RiskWise
- Bundle identifier: `com.aaravnagar.riskwise`
- Expo app folder: `frontend/mobile-demo`
- Backend folder: `backend/api`
- EAS config: `frontend/mobile-demo/eas.json`
- Privacy policy draft: `docs/PRIVACY_POLICY.md`
- Terms/disclaimer draft: `docs/TERMS_AND_DISCLAIMER.md`
- TestFlight runbook: `docs/APP_STORE_TESTFLIGHT.md`
- Release checklist: `docs/RELEASE_CHECKLIST.md`
- Production environment runbook: `docs/PRODUCTION_ENVIRONMENT.md`

## Already Prepared

- iOS bundle identifier in Expo config.
- EAS project linked as `@aaravn/riskwise`.
- App icon and splash assets exist.
- EAS build profiles exist for TestFlight and production.
- TestFlight EAS profile points at `https://riskwise-api.onrender.com`.
- Render backend is deployed and `/health` reports Mongo storage.
- Render blueprint targets hybrid market data with delayed yfinance options enabled for internal TestFlight.
- Camera/photo permission text exists for contract screenshot review.
- App Store-safe positioning is documented.
- Privacy and disclaimer drafts exist.

## Current Deployment Caveat

Render is currently deployed from GitHub `main`, while this workspace is on `codex/production-readiness-hardening`. Before TestFlight, merge the release branch to `main` or retarget Render to the release branch and redeploy so the hosted backend matches the tested code.

## Still Needed From User

- Apple Developer account.
- App Store Connect app record.
- Hosted privacy policy URL.
- Hosted terms/disclaimer URL.
- Real iPhone TestFlight smoke test.
- Final review of app copy and screenshots before public submission.
- Production Clerk keys, or approval to use current Clerk development keys for a limited internal TestFlight.
- Rotated Mongo, Clerk, and Expo secrets before serious beta.
- Optional hosted AI/market-data keys for broader beta quality.

## Commands

From `frontend/mobile-demo`:

```bash
npm run typecheck
npm run export:web
npm run doctor
npm run build:ios:testflight
npm run submit:ios:testflight
```

The build and submit commands require logged-in Expo/EAS and Apple Developer credentials.

## Store Positioning

Use:

- educational options-risk review
- decision support
- scenario explanation
- missing-data warnings
- contract context
- AI coach

Avoid:

- signals
- guaranteed profit
- beat the market
- buy/sell recommendations
- automated trading
- trade execution

## TestFlight Entry Criteria

RiskWise should not go to outside testers until:

- Check flow completes reliably.
- Report generation works for valid inputs.
- Coach does not show raw JSON or generic backend errors.
- Sign in/out works.
- Profile edits persist.
- Backend production environment is reachable.
- Privacy/terms URLs are available.
