# Backend Prod — Fix Now (punch-list)

Action list keyed to the **live** `verify_production_state.py --strict` run on 2026-07-23.
Reference for full var meanings: `docs/PRODUCTION_ENVIRONMENT.md`. This file is just "do these."

Verifier `failed_required`: `live_health_reachable`, `live_hosted_llm_ready`,
`live_sentry_configured`, `live_auth_authorized_parties_configured`, and the three
`local_clerk_*_is_production` (dev Clerk) checks.

---

## 0. Redeploy the code you actually tested — do this first
Render deploys from GitHub `main`, but the market-data hardening is on a branch and still
**uncommitted locally**, so the hosted backend is NOT the code you've been testing.
1. Commit the backend market-data changes on the working branch.
2. Merge to `main` (or point Render's deploy branch at the release branch).
3. Render → Manual Deploy → Deploy latest commit.
4. Confirm the deploy's commit SHA matches your branch.

## 1. `live_hosted_llm_ready` — set a hosted LLM key  (Render → Environment)
The coach currently runs the deterministic **fallback** provider (works, but generic).
- `GEMINI_API_KEY` = key from Google AI Studio (has a free tier).  ← recommended, cheapest
- (already documented/non-secret) `LLM_PROVIDER_ORDER=gemini,openai,fallback`, `GEMINI_MODEL=gemini-2.5-flash`, `GEMINI_API_VERSION=v1beta`
- Optional second model: `OPENAI_API_KEY` (+ `OPENAI_MODEL=gpt-5-mini`).
> Priority: **recommended for beta quality**, not a crash-blocker — the fallback keeps the app working.

## 2. `live_sentry_configured` — backend crash visibility  (Render → Environment)
- `SENTRY_DSN` = DSN from a sentry.io project.
> Do the same for the **app** build later via `EXPO_PUBLIC_SENTRY_DSN` (note: Sentry's native module
> is why Expo Go had it off — it works fine in a real EAS build).

## 3. `live_auth_authorized_parties_configured` — Clerk hardening  (Render → Environment)
- `CLERK_AUTHORIZED_PARTIES` = allowed party identifiers for your app/origins.
- Confirm also present: `CLERK_ISSUER`, `CLERK_JWKS_URL`, `CLERK_SECRET_KEY`.

## 4. `live_health_reachable` — almost certainly a cold start, not a config bug
`/health` returned `ok` when hit directly; the verifier likely timed out while Render's free tier
was asleep. Before testers judge first-load: upgrade the Render tier or add an external keep-warm
ping. No env change needed.

## 5. `local_clerk_*_is_production` — only for EXTERNAL beta
You're on the **dev** Clerk instance (`pk_test_`). Fine for a small internal TestFlight. For external
beta, do the Clerk production switch (PRODUCTION_ENVIRONMENT.md §"Clerk Production Switch"):
create prod Clerk instance → `pk_live_` into EAS → prod Clerk backend values into Render → redeploy →
rebuild. Also rotate the shared Mongo/Clerk/Expo secrets at this point.

---

## Verify after changes
```bash
python scripts/verify_production_state.py --strict
```
Targets to flip green for internal beta: #0 deploy, #1, #2, #3. #5 is external-beta only.
