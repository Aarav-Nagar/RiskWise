# Changelog

## 2026-06-29

- Hardened production backend auth around Clerk session JWTs, bearer-token verification, and per-user ownership checks.
- Wired the Expo frontend API clients to attach Clerk `getToken()` bearer tokens for protected Check, Coach, saved-check, profile, context, and account-deletion calls.
- Added production readiness reporting for auth, storage, Sentry, AI provider/fallback state, and free honest market-data provider state.
- Added Docker backend packaging under `backend/api/Dockerfile`.
- Added a Mongo Atlas persistence smoke script covering profile edits, trade checks, saved checks, chat history, upload metadata, feedback, account deletion cleanup, and deletion-record retention.
- Expanded tests for missing/invalid tokens, cross-user access, valid protected flows, manual image-review fallback, hosted vision extraction, AI deterministic fallback readiness, and impossible bid/ask rejection.
- Updated release, QA, TestFlight, backend production, and current-status docs with honest readiness percentages and remaining real-device/deployment gates.
- Verified locally with `python -m pytest api/tests -q`, `npm run typecheck`, `npm run export:web`, `npx playwright test --config=playwright.config.cjs --reporter=line`, and `npm run doctor`.
- Remaining production gates: run Mongo smoke with real Atlas env vars, run real Clerk session-token smoke on device, start Docker Desktop and build/deploy the backend image, verify Sentry on the deployed backend, and complete real iPhone TestFlight smoke.

## 2026-05-31

- Reworked the README around the RiskWise product story.
- Added screenshot references for Check, Investigation, Profile, and Coach screens.
- Added product vision documentation.
- Added system architecture documentation.
- Added AI agent design documentation.

## 2026-05-30

- Redesigned the Check experience around three paths: Stock Idea, Option Contract, and Screenshot.
- Added a more structured option contract flow.
- Improved ticker search fallback coverage for smaller and less famous symbols.
- Added investigation-style outputs with issue cards and agent debate.

## 2026-05-29

- Redesigned the Profile screen around trader identity, risk rules, app preferences, AI memory, and account/security sections.
- Added profile actions for clearing context, signing out, and account deletion prompts.
- Added UI tests for the Check and Profile flows.

## 2026-05-26

- Expanded RiskWiseAI backend evaluation cases.
- Added stronger options-focused response rules.
- Added structured response fields for cards, risk flags, and suggested follow-up questions.

## 2026-05-25

- Added FastAPI backend routes for trade checks, chat, saved checks, profile settings, and market context.
- Added MongoDB-ready storage with a safe local fallback.
- Added LLM provider routing for Gemini, OpenAI, Ollama, and fallback responses.
