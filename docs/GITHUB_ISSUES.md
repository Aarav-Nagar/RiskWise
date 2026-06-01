# GitHub Issue Ideas

These are planned issues that would make good GitHub tasks as the project moves from prototype to beta.

## Frontend

### Improve Check wizard UI

Make the Check flow smoother on small screens, especially ticker search, expiration selection, and contract detail entry.

### Add risk radar visualization

Create a compact visual showing sizing risk, expiration risk, volatility risk, liquidity risk, and evidence quality.

### Add saved check comparison

Let users compare two saved checks side by side to see how sizing, breakeven, expiration, and missing evidence differ.

### Add TestFlight readiness checklist

Track app icon, splash screen, privacy copy, real-device testing, and App Store-safe wording.

## Backend And Data

### Add real option chain API integration

Connect a provider that can return expirations, strikes, premium, bid/ask, volume, open interest, IV, and Greeks.

### Add IV rank and liquidity scoring

Score contracts using implied volatility context, bid/ask width, volume, and open interest when provider data is available.

### Add screenshot extraction validation

After screenshot extraction, require user confirmation and flag fields with low confidence.

### Add CI checks

Keep backend tests, frontend typecheck/export, and key UI smoke tests running on GitHub Actions.

## AI And Personalization

### Add profile-driven AI response style

Make RiskWiseAI adjust tone and depth based on the user's preferred explanation style and risk strictness.

### Improve agent disagreement display

Show where agents agree, where they disagree, and which missing data would change the review.

### Add App Store privacy policy draft

Document what data is stored, why it is stored, and how users can delete account data.

## Suggested Issue Labels

- `frontend`
- `backend`
- `ai`
- `market-data`
- `design`
- `documentation`
- `app-store`
- `good-first-issue`
