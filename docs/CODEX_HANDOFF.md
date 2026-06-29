# Codex Handoff

Use this file as the first context file for future Codex runs. It exists to avoid rereading the entire long chat history.

## Operating Mode

Before doing RiskWise work, read `docs/CODEX_BUILDER_MODE.md`.

Use Builder Mode by default:

- concise
- execution-focused
- honest about mock vs production
- no broad feature creep
- no repeated full-project summaries unless requested

## Project

RiskWise is an educational options-risk review app. The active product is intentionally focused:

- Home
- Check
- Coach
- Profile

Older journal, arena, growth, learn, and alert ideas are not active product tabs.

## Current Architecture

- Frontend: Expo React Native app in `frontend/mobile-demo`
- Backend: FastAPI app in `backend/api`
- Auth: Clerk
- Database: MongoDB Atlas
- Market data: FMP, Massive/Polygon reference data, Alpha Vantage fallback, yfinance delayed options where enabled, manual/uploaded broker context
- AI: tool-first RiskWiseAI backend
  - local/dev: Ollama target model `qwen2.5:7b-instruct`
  - optional local lab: LM Studio can be added as an OpenAI-compatible local provider
  - hosted fallback: Gemini/OpenAI if configured
  - deterministic fallback must always work

## Product Rules

- RiskWise is educational decision support, not a trading bot.
- Do not use buy/sell/enter/exit command language.
- Do not invent live IV, Greeks, bid/ask, open interest, volume, or earnings dates.
- Label data quality honestly: full, delayed, estimated, reference-only, manual, or missing.
- Backend tools calculate max loss, breakeven, DTE, liquidity score, and data quality. The model explains, it does not calculate.

## Current Priority Order

1. Make Check reliable end to end.
2. Make screenshot/manual contract extraction real and user-confirmed.
3. Make RiskWiseAI answer selected-check and Deep Analysis questions specifically.
4. Confirm profile edits, saved checks, chat history, and uploads persist.
5. Finish TestFlight prep after local smoke tests pass.

## Fast Verification Commands

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

App Store/TestFlight:

```bash
cd frontend/mobile-demo
npm run doctor
npm run build:ios:testflight
```

The EAS commands require Expo/EAS login and Apple Developer access.

## Files To Read First

- `docs/CODEX_HANDOFF.md`
- `docs/NEXT_TASKS.md`
- `docs/CODEX_BUILDER_MODE.md`
- `docs/TOKEN_USAGE_PLAYBOOK.md`
- `docs/CURRENT_STATUS.md`
- `docs/RELEASE_CHECKLIST.md` only for release work
- `backend/api/services/llm.py` only for AI behavior work
- `backend/api/services/market_data.py` only for market data work
- `frontend/mobile-demo/src/screens/CheckScreen.js` only for Check UI/extraction work
- `frontend/mobile-demo/src/screens/ChatScreen.js` only for Coach UI work

## Files/Folders To Avoid Reading Unless Needed

- `frontend/mobile-demo/node_modules`
- `frontend/mobile-demo/dist`
- `frontend/mobile-demo/.expo`
- `backend/api/evals/results`
- `trading-research/arena/figures`
- old generated root screenshots named `riskwise-*.png`

## Known Human-Owned Steps

- Apple Developer enrollment
- App Store Connect app record
- Expo/EAS login
- hosted privacy and terms URLs
- real iPhone TestFlight smoke test
