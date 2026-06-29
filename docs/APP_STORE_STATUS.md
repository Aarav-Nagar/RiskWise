# App Store Status

RiskWise is not yet public App Store ready. It is moving toward a TestFlight beta.

## Current State

- App name: RiskWise
- Bundle identifier: `com.aaravnagar.riskwise`
- Expo app folder: `frontend/mobile-demo`
- Backend folder: `backend/api`
- EAS config: `frontend/mobile-demo/eas.json`
- Privacy policy draft: `docs/PRIVACY_POLICY.md`
- Terms/disclaimer draft: `docs/TERMS_AND_DISCLAIMER.md`
- TestFlight runbook: `docs/APP_STORE_TESTFLIGHT.md`
- Release checklist: `docs/RELEASE_CHECKLIST.md`

## Already Prepared

- iOS bundle identifier in Expo config.
- App icon and splash assets exist.
- EAS build profiles exist for TestFlight and production.
- Camera/photo permission text exists for contract screenshot review.
- App Store-safe positioning is documented.
- Privacy and disclaimer drafts exist.

## Still Needed From User

- Apple Developer account.
- App Store Connect app record.
- Expo/EAS login.
- Hosted privacy policy URL.
- Hosted terms/disclaimer URL.
- Real iPhone TestFlight smoke test.
- Final review of app copy and screenshots before public submission.

## Commands

From `frontend/mobile-demo`:

```bash
npm run typecheck
npm run export:web
npm run doctor
npm run build:ios:testflight
npm run submit:ios:testflight
```

The build and submit commands require logged-in Expo/EAS and Apple Developer credentials.

## Store Positioning

Use:

- educational options-risk review
- decision support
- scenario explanation
- missing-data warnings
- contract context
- AI coach

Avoid:

- signals
- guaranteed profit
- beat the market
- buy/sell recommendations
- automated trading
- trade execution

## TestFlight Entry Criteria

RiskWise should not go to outside testers until:

- Check flow completes reliably.
- Report generation works for valid inputs.
- Coach does not show raw JSON or generic backend errors.
- Sign in/out works.
- Profile edits persist.
- Backend production environment is reachable.
- Privacy/terms URLs are available.
