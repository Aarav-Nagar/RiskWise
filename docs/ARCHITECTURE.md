# Architecture

RiskWise is split into a mobile frontend, a FastAPI backend, and service layers for risk math, storage, market data, and AI review.

## High-Level Flow

```text
User Input
  -> Trade Builder
  -> Risk Math Engine
  -> Issue Detection
  -> Multi-Agent Review
  -> Investigation Report
  -> Coach
```

## Frontend

The frontend lives in `frontend/mobile-demo`.

It is an Expo React Native app that currently runs as a mobile-sized web demo. The main screens are:

- Home
- Check
- Coach
- Profile

The Check screen contains three paths:

- Stock Idea
- Option Contract
- Screenshot

The Profile screen stores the user's risk rules, explanation preferences, and AI memory settings.

## Backend

The backend lives in `backend/api`.

It is a FastAPI service that exposes endpoints for:

- auth adapter routes
- trade checks
- saved checks
- chat threads
- market data context
- profile settings
- health and readiness checks

The backend is designed to run locally during development and later move to a hosted API environment.

## Risk Math Service

The risk math layer checks the parts of an options trade that can be calculated from the user's contract details:

- max loss
- account risk percentage
- days to expiration
- breakeven estimate
- premium exposure
- contract count
- missing required fields

This is intentionally separate from live prediction. Risk math should stay explainable.

## Profile And Preferences System

The profile system stores user-level context:

- risk style
- max risk per trade
- max trades per week
- preferred explanation style
- default AI mode
- common mistakes to watch
- sectors or markets of interest

These settings help RiskWise judge the same trade differently for different users.

## Multi-Agent Review Layer

The multi-agent layer turns a trade check into a debate. Each agent looks for a different failure mode:

- thesis support
- missing evidence
- contract risk
- sizing risk
- behavioral risk

The final report should show where agents agree and where the setup is uncertain.

## Saved Checks

Saved checks let the user keep a record of reviewed trades. This is useful for:

- revisiting old reasoning
- giving the Coach context
- comparing trade quality over time
- finding repeated mistakes

The current implementation supports saved-check structure. The long-term version should make this history searchable and useful.

## Future Market Data Integration

RiskWise has a market data adapter, but real options analysis needs a provider that can supply:

- option chains
- expirations
- bid and ask
- volume
- open interest
- implied volatility
- Greeks
- earnings dates

Until that integration is complete, the app should clearly label missing data instead of pretending to know it.
