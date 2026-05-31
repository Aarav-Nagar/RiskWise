# GitHub Education Setup Checklist

Claim these first:

1. Clerk free Pro plan.
2. MongoDB Atlas credits.
3. Doppler team plan.
4. Sentry student plan.
5. DigitalOcean credits.
6. BrowserStack or LambdaTest.
7. Namecheap, Name.com, or .TECH domain.
8. Deepnote for research notebooks.

Add these values to `.env`, then later move them to Doppler:

```env
APP_STORAGE_PROVIDER=mongo
MONGODB_URI=...
MONGODB_DATABASE=options_risk_check
CLERK_PUBLISHABLE_KEY=...
CLERK_SECRET_KEY=...
LLM_PROVIDER_ORDER=gemini,openai,fallback
GEMINI_API_KEY=...
OPENAI_API_KEY=...
SENTRY_DSN=...
```

Development mode can run with `APP_STORAGE_PROVIDER=demo`. That mode stores data only in backend memory and is not a production data store.

For deployment, use MongoDB Atlas for data, Clerk for auth, Sentry for errors, and either DigitalOcean App Platform credits or another Docker host for the FastAPI backend.
