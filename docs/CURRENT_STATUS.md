# Current Status

Last updated: July 7, 2026

This file is the short status source for future Codex runs. Update it after meaningful product or backend changes instead of relying on long chat history.

## Overall Status

RiskWise is a serious MVP/mockup with a real app structure, hardened backend auth paths, persistence layer, market-data adapters, refreshed Check flows, and RiskWiseAI architecture.

It is not full public-production-ready yet. The remaining production work is mostly production Clerk, secret rotation, live/delayed options-data scope decisions, hosted OCR/vision verification, and real iPhone/TestFlight execution.

## Current Estimated Readiness

| Area | Mockup Readiness | Production Readiness | Notes |
|---|---:|---:|---|
| Overall app | 89-92% | 74-80% | Core flows are test-backed and production controls are materially stronger. Still needs real service/device deployment proof. |
| Frontend | 92-95% | 80-85% | Check/Coach/Profile have the active product shape. Home now shows selected-ticker options readiness. Needs real iPhone overflow/offline/auth smoke. |
| Backend/API | 88-92% | 80-85% | FastAPI structure includes auth, ownership, readiness, rate limits, extraction, market honesty coverage, Render deployment, and Mongo readiness. Hosted Render still needs redeploy from the current release branch/config. |
| RiskWiseAI | 84-88% | 72-78% | Tool-first fallback and eval coverage are stronger. Coach now surfaces confidence, sources used, missing fields, risk flags, and watch-next context. Hosted Gemini/OpenAI and local Ollama/Qwen runtime still need deployment proof. |
| Market/options data | 72-78% | 58-65% | Free honest stack is explicit and tested. Render blueprint now targets hybrid delayed/reference mode, but full live OPRA-grade data remains out of scope without paid entitlement. |
| Auth/profile/persistence | 87-91% | 78-84% | Protected routes require Clerk JWTs in production and reject cross-user access. Mongo smoke passed, but production Clerk and secret rotation remain before serious beta. |
| Testing/CI | 85-89% | 72-78% | Backend, frontend, export, Playwright, Doctor, and EAS archive inspection have passed locally. Needs CI wiring and real-device smoke evidence. |
| TestFlight/App Store | 63-68% | 48-58% | EAS project/config/docs are present and Doctor plus archive inspection passed. Needs Apple Developer/App Store Connect, hosted URLs, production Clerk or explicit internal-dev-Clerk approval, real iPhone smoke, and build submission. |

## Active Screens

| Screen | Status | Main Remaining Work |
|---|---|---|
| Home | 89-92% demo / 76-80% production | Market/data transparency and selected-ticker options readiness smoke pass. Still needs real provider fallback-state QA. |
| Check | 88-92% demo / 74-80% production | Refreshed Check flows now emphasize real contract confirmation, honest missing-data labels, structured validation, and selected Coach context. Still needs real OCR/provider verification on device. |
| Report | 84-89% demo / 70-76% production | Report/export paths are test-backed and labels missing data honestly. Still needs more device overflow/share QA. |
| Coach | 88-92% demo / 75-80% production | Selected-check, Deep Analysis, source/confidence display, watch-next context, direct-advice refusal, and fallback evals pass. Still needs hosted/local provider proof under deployment failures. |
| Profile | 86-90% demo / 76-82% production | Profile edits, context clearing, deletion path, and auth ownership have tests. Still needs real Clerk/Mongo smoke. |
| Auth | 84-88% demo / 74-80% production | Production backend routes now require Clerk bearer tokens and ownership checks. Still needs real sign-in/sign-out/delete smoke with deployed Clerk config. |
| Search | 74-80% demo / 60-66% production | Symbol search and provider fallbacks work. Still needs more provider outage/loading UX polish. |

## Known Priorities

1. Merge the release branch to `main` or retarget Render, then redeploy so hosted `/ready` reflects the tested code and hybrid market-data mode.
2. Switch to production Clerk before external beta, or keep development Clerk only for a small internal TestFlight.
3. Rotate Mongo, Clerk, and Expo secrets because setup values were shared during configuration.
4. Run the Mongo persistence smoke against real Atlas env vars and a real Clerk session-token path.
5. Verify screenshot OCR on device only when Gemini/OpenAI vision is configured; otherwise manual-review is the correct production behavior.
6. Prove hosted/local AI provider behavior under real outage/cooldown conditions.
7. TestFlight prep requires Apple Developer/App Store Connect steps owned by the user.

## Known Constraints

- Free market data cannot honestly provide complete live OPRA-grade options data for public redistribution.
- Qwen/Ollama or LM Studio runs on the backend machine, not inside the mobile app.
- Public users need a hosted backend and hosted AI fallback or deterministic fallback.
- Do not add extra tabs unless the user explicitly reactivates them.

## Fast Commands

Backend:

```bash
cd backend
python -m pytest api/tests
python api/scripts/production_persistence_smoke.py
```

Frontend:

```bash
cd frontend/mobile-demo
npm run typecheck
npm run export:web
```

TestFlight prep:

```bash
cd frontend/mobile-demo
npm run doctor
npm run build:ios:testflight
```
