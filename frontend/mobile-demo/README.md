# RiskWise Mobile Demo

Clickable Expo React Native prototype for the RiskWise options-risk app.

This version is intentionally narrow. It focuses on account setup, options risk checks, saved checks, structured reports, and the RiskWise Coach. Older journal, growth, arena, lesson, and alert screens have been removed from the active product so the app feels simpler and more agentic.

## Run

Start the API first:

```bash
cd ../../backend
pip install -r api/requirements.txt
uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Then run the mobile preview:

```bash
npm install
npm run export:web
npm run web
```

Open the Expo web URL in a browser. The app renders inside a phone-sized frame so the layout can be reviewed from a laptop.

## Main Navigation

- Home: account snapshot, simple RiskWise workflow, and recent saved checks.
- Search: ticker entry plus sector, market-cap, and event focus.
- Check: the raised center action for running an educational options risk check.
- Coach: options-focused LLM assistant with structured cards and risk explanations.
- Profile: account settings and sign out.

The Report screen opens after a check is generated. It is part of the Check flow, not a permanent bottom tab.

## Current Behavior

- First open starts at a premium account/sign-in flow.
- Users can create a Clerk account, verify email, sign in, request a reset, and sign out.
- Profile answers are synced to the API and stored in MongoDB Atlas when available.
- Check This Trade generates a dynamic decision brief with risk math, a collapsed contract label, setup debate, agent docket, agreement map, and pre-action questions.
- Save Check stores the current report through the API and MongoDB-backed saved checks collection.
- Coach sends educational options questions to the API and renders summary cards, score bars, and mini tables.
- The first-run disclaimer frames the app as educational risk review only.

## Notes

- The backend is required for account, report, and coach flows.
- No trade execution is included.
- Language is framed as educational risk/context, not financial advice.
