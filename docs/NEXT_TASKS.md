# Next Tasks

This is the short task queue for future Codex runs. Keep it updated instead of relying on a long chat thread.

Before starting any task, follow `docs/CODEX_BUILDER_MODE.md`.

## Highest Priority

1. **Check screenshot extraction**
   - Fake/random extraction behavior is removed from the Check flow.
   - Upload supports camera, photo library, image files, and readable TXT/CSV contract files.
   - Backend parses readable contract text first and exposes missing live fields to the app.
   - User confirmation now includes required contract fields plus missing bid/ask, IV, OI, volume, and Greeks.
   - Image uploads without hosted vision now return manual-review instead of invented fields.
   - Still verify real OCR/vision behavior only when a capable provider is configured.
   - Still run a real-device upload smoke with a live screenshot before TestFlight.

2. **Check reliability**
   - Keep the refreshed Check screens as the active source of truth.
   - Local web smoke should cover option contract, stock idea, screenshot guidance, extraction confirmation, selected-check Coach handoff, and impossible bid/ask validation.
   - No generic "Something went wrong" after valid mocked input.
   - Field-specific validation messages are in place for ticker, expiration, strike, premium, contracts, bid/ask, IV, OI, volume, account size, and risk rule.
   - Required fields: selected ticker, valid expiration, strike > 0, premium > 0 for long options, contracts >= 1.
   - Optional fields: bid, ask, IV, OI, volume.

3. **RiskWiseAI quality**
   - Keep local Qwen/Ollama for dev.
   - Add LM Studio only as a local lab provider if useful.
   - Production personal TestFlight can pass with deterministic fallback, while hosted Gemini/OpenAI remains optional unless screenshot OCR is expected.
   - Deep Analysis should return five agents, top risks, missing data, and what RiskWise used.
   - Coach now displays confidence, guarded fallback/provider status, sources used, risk flags, missing data, watch-next tables, and suggested follow-up prompts.
   - Next quality pass: verify hosted Gemini/OpenAI responses still pass the backend answer guard and preserve source/missing-data metadata.

4. **Home market context**
   - Home fetches quote, profile, news, earnings, and selected-ticker options context.
   - Options Readiness must stay honest: no live premium, IV, Greeks, bid/ask, volume, or open-interest claims unless provider data supplies them.

5. **Repo hygiene**
   - Do not scan generated folders unless explicitly needed.
   - Ignored generated folders include Expo builds/caches, Playwright reports, frontend screenshots, AI eval results, and root smoke screenshots.
   - Do not delete source, docs, research, or untracked work without checking Git status and the exact path list first.

6. **Persistence**
   - Run `cd backend/api && python scripts/production_persistence_smoke.py` against real Mongo Atlas env vars.
   - Confirm Clerk-backed user ownership with a real device session token.
   - Confirm delete-account cleanup also removes the Clerk account where dashboard policy permits.

7. **TestFlight prep**
   - Run typecheck and web export.
   - Run backend tests.
   - Run `npm run doctor`.
   - Redeploy Render from the release branch or update the Render dashboard so hosted `/ready` reports `MARKET_DATA_PROVIDER=hybrid`.
   - Use `docs/PRODUCTION_ENVIRONMENT.md` for production Clerk, secret rotation, AI provider, and market-data settings.
   - Build with `npm run build:ios:testflight` only after EAS and Apple access are ready.

## Reference Docs

- `docs/CURRENT_STATUS.md` for current percentages and blockers.
- `docs/QA_PLAYBOOK.md` for manual and automated checks.
- `docs/APP_STORE_STATUS.md` for TestFlight state.
- `docs/TOKEN_USAGE_PLAYBOOK.md` for low-token Codex workflow.

## Defer

- Extra tabs
- Portfolio dashboard
- Live brokerage connection
- Paid OPRA-grade options feed
- Heavy chart redesign until Check and Coach are stable
