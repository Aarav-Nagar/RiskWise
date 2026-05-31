# Options Risk Check API

FastAPI backend for the mobile demo.

This API intentionally returns educational risk-review JSON. It does not execute trades and does not return buy/sell instructions.

Development mode uses an in-memory adapter. Production is designed for Clerk auth, MongoDB Atlas, Sentry, and a routed LLM provider stack configured through environment variables.

## Run

```bash
pip install -r api/requirements.txt
uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

## Endpoints

- `GET /health`
- `GET /ready`
- `POST /auth/signup`
- `POST /auth/signin`
- `POST /auth/forgot-password`
- `POST /trade-check`
- `POST /chat`
- `GET /chat/threads/{user_id}`
- `GET /chat/threads/{user_id}/{thread_id}`

## Environment

```env
APP_STORAGE_PROVIDER=demo
MONGODB_URI=
MONGODB_DATABASE=options_risk_check
CLERK_SECRET_KEY=
LLM_PROVIDER_ORDER=gemini,openai,ollama,fallback
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
OLLAMA_BASE_URL=
OLLAMA_MODEL=
SENTRY_DSN=
```

`/ready` reports whether MongoDB is connected and which LLM providers are configured. It never returns API keys.
