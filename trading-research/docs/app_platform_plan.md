# Options Risk Check Platform Plan

This app should be a risk-review companion, not a stock-picking product.

## Product Shape

- Mobile app: Expo React Native.
- Backend: FastAPI.
- Auth: Clerk in production, demo adapter in development.
- Database: MongoDB Atlas in production, in-memory demo adapter in development.
- LLM: provider wrapper that can use OpenAI later, with safe demo responses now.
- Monitoring: Sentry hooks on the backend first, frontend later.
- Secrets: Doppler or environment variables, never committed.

## Data Model

- users: Clerk identity plus public profile fields.
- profiles: account size, risk budget, sectors, event focus, behavior reminders.
- trade_checks: submitted trade idea plus generated decision brief.
- agent_outputs: structured agent docket for setup, options risk, behavior, market context, and risk manager.
- journal_entries: saved checks, status, tags, notes, outcome fields.
- chat_threads and chat_messages: user questions and educational assistant responses.

## Agent Output Direction

The report should be dynamic and visual:

- Risk Brief: short overall read and weakest link.
- Decision Snapshot: setup, options structure, risk used, disagreement.
- Risk Math: max loss, half-premium drawdown, breakeven move, days left.
- Agent Docket: compact evidence cards with scores.
- Agreement Map: where reviewers agree and disagree.
- Questions Before Acting: journal-style prompts, not trading commands.

## GitHub Education Resources

- Clerk: real auth and password reset.
- MongoDB Atlas: cloud database.
- DigitalOcean: backend hosting.
- Doppler: secrets.
- Sentry: error tracking.
- BrowserStack or LambdaTest: mobile QA.
- GitHub Pages: public web demo.
- GitHub Actions: CI and deploy.
- Namecheap/Name.com/.TECH: domain.
- Deepnote: research notebooks and model reports.
