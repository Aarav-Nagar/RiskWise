# RiskWise Production Backend Notes

This is the production direction for the AI backend. The app should never depend on one model key working forever, so the backend now routes through providers in this order:

```env
LLM_PROVIDER_ORDER=gemini,openai,ollama,fallback
```

## What Each Provider Is For

- Gemini: fast hosted default for the mobile coach.
- OpenAI: high-quality hosted fallback when quota and billing are active.
- Ollama: local development option when you want to test without paid API calls.
- fallback: deterministic options-risk coach, always available, no network call.

The fallback is not pretending to be a full LLM. It keeps the app usable when a key is missing, quota is exhausted, or a provider is down.

If a provider fails, the backend temporarily skips it so every chat message does not wait on the same broken provider again.

## Required Production Environment

```env
APP_ENV=production
APP_STORAGE_PROVIDER=mongo
MONGODB_URI=...
MONGODB_DATABASE=finance_app

CLERK_SECRET_KEY=...

LLM_PROVIDER_ORDER=gemini,openai,fallback
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_VERSION=v1beta
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-mini
LLM_PROVIDER_COOLDOWN_SECONDS=300

SENTRY_DSN=...
```

Do not put private keys in the frontend Expo app. The frontend should only receive public values such as the Clerk publishable key and the API base URL.

## Readiness Checks

Use:

```bash
GET /health
GET /ready
```

`/health` confirms the API process is alive.

`/ready` confirms:

- storage adapter and database status
- which LLM providers are configured
- market-data provider status

`/ready` intentionally does not return secrets.

## Deploy Shape

The backend has a Dockerfile at:

```text
backend/Dockerfile
```

Any app host that supports Docker can run it. A starter `render.yaml` is included, but DigitalOcean App Platform is also a strong fit because GitHub Education gives credits.

## AI Contract

The Coach should:

- answer casual greetings naturally
- explain options, IV, Greeks, spreads, risk, and earnings volatility
- use attached RiskWise trade checks when available
- use recent conversation history for follow-up questions
- avoid direct buy/sell/hold instructions
- avoid making up live prices, option chains, IV, premiums, or earnings dates

The current tests cover the basic version of that contract.
