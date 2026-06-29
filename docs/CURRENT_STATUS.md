# Current Status

Last updated: June 29, 2026

This file is the short status source for future Codex runs. Update it after meaningful product or backend changes instead of relying on long chat history.

## Overall Status

RiskWise is a serious MVP/mockup with a real app structure, hardened backend auth paths, persistence layer, market-data adapters, and RiskWiseAI architecture.

It is not full public-production-ready yet. The remaining production work is mostly real Clerk/Mongo/Sentry deployment proof, live/delayed options-data scope decisions, hosted OCR/vision verification, and real iPhone/TestFlight execution.

## Current Estimated Readiness

| Area | Mockup Readiness | Production Readiness | Notes |
|---|---:|---:|---|
| Overall app | 88-91% | 74-80% | Core flows are test-backed and production controls are materially stronger. Still needs real service/device deployment proof. |
| Frontend | 92-95% | 78-84% | Typecheck, web export, Playwright smoke, and Expo Doctor pass. Needs real iPhone overflow/offline/auth smoke. |
| Backend/API | 88-92% | 78-84% | FastAPI tests pass with Clerk bearer-token auth, ownership checks, readiness, rate limits, extraction, and market honesty coverage. Docker build is blocked only by local Docker daemon not running. |
| RiskWiseAI | 82-86% | 70-76% | Tool-first fallback and eval coverage are stronger. Hosted Gemini/OpenAI and local Ollama/Qwen runtime still need deployment proof. |
| Market/options data | 70-76% | 55-63% | Free honest stack is explicit and tested. Full live OPRA-grade data remains out of scope without paid entitlement. |
| Auth/profile/persistence | 86-90% | 76-82% | Protected routes require Clerk JWTs in production and reject cross-user access. Mongo smoke script exists but must be run with real Atlas/Clerk env. |
| Testing/CI | 84-88% | 70-76% | Backend, frontend, export, Playwright, and Doctor gates pass locally. Needs CI wiring and real-device smoke evidence. |
| TestFlight/App Store | 60-65% | 45-55% | EAS/docs/config are present and Doctor passes. Needs Apple/EAS login, hosted URLs, real iPhone smoke, and build submission. |

## Active Screens

| Screen | Status | Main Remaining Work |
|---|---|---|
| Home | 88-91% demo / 74-78% production | Market/data transparency smoke passes. Still needs sharper dashboard purpose and real fallback-state QA. |
| Check | 85-90% demo / 72-78% production | Camera/library/file upload, readable text parsing, missing-data confirmation, field validation, and smoke tests are in place. Still needs real OCR/provider verification on device. |
| Report | 84-89% demo / 70-76% production | Report/export paths are test-backed and labels missing data honestly. Still needs more device overflow/share QA. |
| Coach | 86-90% demo / 72-78% production | Selected-check, Deep Analysis, direct-advice refusal, and fallback evals pass. Still needs hosted/local provider proof under deployment failures. |
| Profile | 86-90% demo / 76-82% production | Profile edits, context clearing, deletion path, and auth ownership have tests. Still needs real Clerk/Mongo smoke. |
| Auth | 84-88% demo / 74-80% production | Production backend routes now require Clerk bearer tokens and ownership checks. Still needs real sign-in/sign-out/delete smoke with deployed Clerk config. |
| Search | 74-80% demo / 60-66% production | Symbol search and provider fallbacks work. Still needs more provider outage/loading UX polish. |

## Known Priorities

1. Run the Mongo persistence smoke against real Atlas env vars and a real Clerk session-token path.
2. Verify screenshot OCR on device only when Gemini/OpenAI vision is configured; otherwise manual-review is the correct production behavior.
3. Prove hosted/local AI provider behavior under real outage/cooldown conditions.
4. Start Docker Desktop, build `backend/api/Dockerfile`, deploy backend, and verify `/health` plus `/ready`.
5. TestFlight prep requires Apple Developer and EAS login steps owned by the user.

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
