# App Store Listing & TestFlight Copy

Draft metadata for App Store Connect and TestFlight. Written to RiskWise positioning rules:
**educational risk review / decision support / missing-data warnings** — never signals, guaranteed
profit, buy/sell calls, or trade execution. Character limits noted; stay under them.

---

## App name (≤30 chars)
`RiskWise` — *(or)* `RiskWise: Options Risk Check` (28)

## Subtitle (≤30 chars)
`Learn options risk, not tips` (28)

## Promotional text (≤170 chars — editable anytime, no review)
Understand the real risk of an options trade before you commit — max loss, breakeven, and what data
is missing. Educational only. Not financial advice.

## Keywords (≤100 chars, comma-separated, no spaces after commas)
`options,risk,trading,education,calculator,breakeven,max loss,greeks,implied volatility,learn,finance`

## Description (≤4000 chars)
RiskWise is an educational tool that helps you understand the risk of an options trade before you
make a decision. It is decision-support software for learning — not a brokerage, not a signal
service, and not financial advice.

Enter or upload a contract, and RiskWise walks the numbers with you:

• Max loss, breakeven, and days to expiration, calculated deterministically — not guessed by an AI.
• A required-move view so you can see what the underlying has to do for the trade to work.
• A plain-language risk read from a review committee of five perspectives (a bull view, a skeptic, an
  options-risk view, a position-sizing view, and a risk manager) designed to disagree, so you see more
  than one angle.
• Honest data quality labels — Full, Delayed, Estimated, Reference-only, or Missing. If we don't have
  live data for something, we tell you instead of inventing a number.
• A coach you can ask follow-ups: IV crush, theta, spreads, bid/ask, earnings volatility, and how a
  given check breaks down.

What RiskWise does NOT do:
• It does not tell you to buy, sell, hold, enter, or exit anything.
• It does not execute trades or connect to a brokerage.
• It does not promise profits or predict the market.

Market data may be delayed, estimated, or user-provided. Options trading involves substantial risk,
including loss of the entire premium or more depending on the strategy. You are responsible for
verifying all data and suitability before making any financial decision.

RiskWise is currently in beta. Features and data sources may change.

## What's New (≤4000 chars) — for the first build
First TestFlight beta. Core flow: build or upload a contract, get max loss / breakeven / required move,
a five-perspective risk read, honest data-quality labels, and a coach for follow-up questions.

---

## App information
- **Primary category:** Finance *(alt: Education — lower review scrutiny but less discoverable; Finance
  is the honest fit. Expect extra finance-app review; the educational framing and disclaimers below are
  what carries it.)*
- **Secondary category:** Education
- **Content rights:** Uses delayed/third-party market data; no third-party copyrighted content shipped.
- **Age rating:** Likely 17+ due to "Simulated Gambling / Contests" is NOT applicable, but finance apps
  often rate 17+. Answer Apple's questionnaire honestly; there is no gambling, no user-generated content
  feeds, no unrestricted web.

## URLs
- **Privacy Policy URL (required):** host `legal/privacy.html` → paste URL here.
- **Support URL (required):** a page or mailto with a working contact.
- **Marketing URL (optional):** `legal/index.html` or a landing page.

---

## App Privacy ("nutrition label") — answers to prep
Declare what the app actually collects. Verified against code 2026-07-23 (auth models,
`store.py`, upload path in `app.py`, Sentry init in `index.js`/`app.py`):
- **Contact Info → Email address:** collected via Clerk sign-in. Linked to identity. Used for App
  Functionality (account). Not used for tracking.
- **User Content:** saved checks, chat history, and confirmed contract details. Linked to identity.
  App Functionality.
  - **Uploaded contract files:** the raw image/screenshot is **not stored** — `store.py`'s
    `compact_upload_attachments()` persists only metadata (`name`, `type`, `size`, and booleans
    `hasText`/`hasImage`). **But the file content IS transmitted** to the extraction step
    (`extract_contract_from_uploads` in `app.py`) for parsing. Today that runs the local deterministic
    fallback, so nothing leaves the backend; **the moment a hosted LLM key is configured, uploaded
    contract images are sent to that AI provider (Gemini/OpenAI).** If you ship with a hosted key,
    declare that upload content (a "Photo" / User Content) is collected and sent to a third-party
    processor — do not describe it as metadata-only.
- **Financial Info → Other Financial Info:** the profile collects self-reported `accountSize` and
  `riskBudgetPercent` (`store.py` profile fields). Linked to identity. App Functionality. Decide with
  Apple's schema whether to declare this under **Financial Info** (recommended, since account size /
  risk budget are financial details) or fold it into User Content — but it must not be left undeclared.
- **Identifiers → User ID:** account identifier. App Functionality.
- **Usage/Diagnostics:** only if Sentry is enabled in the build (crash/diagnostic data). Verified: both
  Sentry inits (`index.js`, `app.py`) run with **no `setUser` and no `send_default_pii`**, so crash data
  is **not linked to identity**. If you ship with `EXPO_PUBLIC_SENTRY_DSN` set, declare Crash Data +
  Performance/Diagnostics (not linked to identity, App Functionality). If Sentry stays off, do not declare it.
- **Tracking:** None. Do not enable ATT unless you add tracking SDKs.

---

## TestFlight

### Beta App Description
RiskWise is an educational options-risk review tool. Enter or upload a contract and it shows max loss,
breakeven, required move, a multi-perspective risk read, and honest data-quality labels, plus a coach
for follow-up questions. Educational decision support only — not financial advice, no trade execution.

### What to Test (beta testers see this)
- Create an account and sign in; sign out and back in — your profile and saved checks should persist.
- Run a stock-idea check and an options-contract check.
- Upload or manually enter contract context.
- Generate a report — confirm max loss, breakeven, DTE, required move, top risks, and missing-data
  labels all show, and nothing reads like invented data.
- Ask the Coach about your report; try Deep Analysis (five committee agents).
- Edit your Profile risk rules.
- Tell us: anything confusing, any number that looks wrong, any screen that overflows, any error text
  that isn't clear.

### Feedback email
Set a real address in App Store Connect → TestFlight → Test Information.

### App Review notes (internal — for Apple reviewer)
- RiskWise is **educational decision-support**, not a trading, brokerage, or advice app. It does not
  execute trades or connect to brokerages.
- Provide a **demo account** (email + password on the dev Clerk instance) so the reviewer can sign in
  without creating one.
- Market data is delayed/estimated and labeled as such in-app.
- First backend call may take ~30–50s if the hosting tier is asleep (cold start).

---

## Sign in with Apple note (Guideline 4.8)
If the sign-in screen exposes a third-party social login (e.g. Google) on iOS, Apple requires **Sign in
with Apple** to be offered alongside it — or disable social providers for the App Store build. Confirm
what Clerk shows before submission.
