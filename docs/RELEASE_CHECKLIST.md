# Release Checklist

This checklist is for getting RiskWise to a TestFlight-ready beta. It is intentionally practical: every item should either make the app safer, easier to review, or easier to debug.

## Environment

- Quick verifier: `python scripts/verify_production_state.py` for internal beta readiness, and `python scripts/verify_production_state.py --strict` for public App Store blockers.
- GitHub Actions verifier: run **Production State Check** manually from the Actions tab. Use `strict=false` for internal beta and `strict=true` before external beta or App Store submission.
- `MONGODB_URI` points to the production Atlas cluster.
- `MONGODB_DATABASE` is set to the production database name.
- `CLERK_SECRET_KEY` and `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` are configured.
- `CLERK_ISSUER` or `CLERK_JWKS_URL` is configured for backend JWT verification.
- `CLERK_AUTHORIZED_PARTIES` is set for the deployed Expo/web origins when applicable.
- `FRONTEND_ALLOWED_ORIGINS` is strict in production. Do not rely on localhost regex in `APP_ENV=production`.
- `FMP_API_KEY` is configured for quote, profile, news, and earnings context.
- `MASSIVE_API_KEY` or `POLYGON_API_KEY` is configured for options contract references.
- `ALPHA_VANTAGE_API_KEY` is configured as a stock quote fallback.
- `ENABLE_YFINANCE_OPTIONS` is set deliberately. Use `true` only when delayed yfinance options are acceptable for the environment.
- `SENTRY_DSN` is configured.
- No `.env` or secret values are committed.

## Backend Gates

- `GET /health` returns `ok`.
- `GET /ready` returns storage, auth, Sentry, LLM, and market-provider readiness without leaking secrets.
- `GET /market/providers` clearly shows active, missing, delayed, estimated, manual, and reference-only data sources.
- User routes require a signed-in RiskWise profile.
- Protected backend calls send `Authorization: Bearer <Clerk session token>`.
- Production user routes verify Clerk JWTs and reject cross-user profile access.
- Mongo indexes are created for users, saved checks, trade checks, chat threads, chat messages, feedback, uploads, and deletion records.
- Account deletion removes RiskWise app data and records deletion status.
- Rate limits are active for `/chat`, `/trade-check`, and `/market/*`.
- Docker backend starts cleanly from `backend/api/Dockerfile`.
- Optional Mongo proof: `cd backend/api && python scripts/production_persistence_smoke.py` passes when Atlas env vars are set.

## Check Flow Gates

- A ticker must be selected before continuing.
- Past expirations are rejected.
- Strike must be greater than zero.
- Premium must be greater than zero for long options.
- Contract count must be at least one.
- Bid cannot be greater than ask.
- Max loss is computed from premium x contracts x 100 when contract details are present.
- Report shows max loss, breakeven, DTE, required move, top risks, missing data, and agent committee summary.
- Reports label data quality as Full, Delayed, Estimated, Manual, Reference-only, or Missing.

## Coach Gates

- Coach can answer a greeting naturally.
- Coach can explain IV crush, theta, Greeks, spreads, bid/ask, and earnings volatility.
- Coach can use a selected check.
- Deep Analysis returns five committee agents.
- No raw JSON appears in the UI.
- Missing IV, Greeks, bid/ask, volume, and open interest are shown as missing instead of invented.
- The model never overrides backend math for max loss, breakeven, DTE, or data quality.

## Frontend Gates

- Bottom navigation has only Home, Check, Coach, and Profile.
- No screen overflows at a phone-sized viewport.
- Backend offline errors are specific and actionable.
- Upload menu offers Take Photo, Photo Library, Files, and Deep Analysis.
- Profile edits persist after refresh/sign-in.
- Password reset path is visible.
- Delete account path is visible and requires confirmation.

## App Store / TestFlight

- App icon and splash screen are set.
- `frontend/mobile-demo/app.json` has the iOS bundle identifier, build number, and permission strings.
- `frontend/mobile-demo/eas.json` has `testflight` and `production` iOS store build profiles.
- Privacy policy is drafted in `docs/PRIVACY_POLICY.md` and a hosted URL is available.
- Terms/disclaimer is drafted in `docs/TERMS_AND_DISCLAIMER.md` and a hosted URL is available.
- TestFlight runbook is drafted in `docs/APP_STORE_TESTFLIGHT.md`.
- Store copy avoids trade signals, guaranteed profit, and trade execution language.
- Educational decision-support wording is used consistently.
- If third-party social login is exposed on iOS, Sign in with Apple is added or those social providers are disabled for App Store review.
- EAS build succeeds.
- Real iPhone smoke test is complete.
