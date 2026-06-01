# Roadmap

RiskWise is in active MVP development. The first goal is to make the core check and coach loop useful before adding broad finance-app features.

## v0.1: Local MVP

Status: mostly complete

- Expo mobile demo
- FastAPI backend
- local scoring engine
- basic saved checks
- profile settings prototype
- educational RiskWiseAI Coach

## v0.2: Better Check Flow

Status: in progress

- three check paths: Stock Idea, Option Contract, Screenshot
- step-by-step contract builder
- clearer contract math
- issue cards for missing evidence
- investigation language instead of prediction language

## v0.3: Profile Personalization

Status: in progress

- risk rules
- trader DNA
- AI explanation style
- common mistakes to watch
- app preferences
- saved context controls

## v0.4: Screenshot Extraction

Status: prototype

- upload screenshot
- extract ticker, strike, expiration, premium, and contracts
- let the user confirm extracted values
- show extraction confidence and missing fields

## v0.5: Real Option Chain Integration

Status: planned

- options expirations
- option chain lookup
- bid and ask
- volume and open interest
- implied volatility
- Greeks when available
- earnings date context

## v0.6: TestFlight Beta

Status: planned

- real iPhone testing
- App Store-safe wording
- privacy policy
- terms and disclaimer
- Sentry error monitoring
- backend deployment

## v1.0: Public Launch

Status: planned

- stable account system
- persistent user data
- production API hosting
- live market data integration
- polished App Store screenshots
- clear onboarding
- no trade execution

## Open Product Questions

- Which options data provider is best for the first live version?
- How much history should RiskWiseAI remember?
- Should saved checks become a journal, a scorecard, or both?
- How should uncertainty be shown without making the app look too confident?
- What features are useful enough to add without making the app crowded?
