# Finance App

This is the main finance app workspace.

It combines the mobile app, backend API, and the trading research experiments that led to the product idea. Java practice work is kept separately in `InitialProjects/100DaysOfJava`.

## Folder map

```text
frontend/mobile-demo/      Expo React Native app
backend/api/               FastAPI backend
config/.env                local private environment file
docs/                      product, setup, and platform notes
legacy-web-prototype/      older client/server prototype kept for reference
trading-research/          experiments, agents, backtests, reports, and tests
.github/workflows/         CI and demo publishing workflows
```

## What this app is

Finance App is a decision-support tool for options risk checks. The app is meant to help a user slow down, understand a setup, save useful checks, review the risk, and ask an options-focused coach what the setup actually means.

It does not execute trades and it should not be presented as financial advice.

## Current build

- Expo mobile app shell with Clerk sign-up, sign-in, email verification, and sign-out wiring
- Risk check form
- Dynamic report screen with a collapsed contract label and setup debate
- Mongo-backed saved checks
- RiskWise Coach screen with structured options explanations
- FastAPI backend
- MongoDB Atlas storage adapter with a safe demo fallback if the connection is unavailable
- OpenAI chat adapter with a safe educational fallback if the model or key fails
- Sentry hooks for frontend/backend error monitoring

## Run the backend

```bash
cd backend
pip install -r api/requirements.txt
python -m uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

## Run the mobile demo

```bash
cd frontend/mobile-demo
npm install
npm run web
```

Keep real keys in `config/.env`. Do not commit secrets. Public Expo values live in `frontend/mobile-demo/.env`.
