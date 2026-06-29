# App Store And TestFlight Plan

RiskWise can be prepared for TestFlight from this repo, but the final upload requires an Apple Developer account and an Expo/EAS login. This document keeps the release path explicit so the app can move from mockup to beta without guessing.

## Current Release Target

- App name: RiskWise
- Bundle identifier: `com.aaravnagar.riskwise`
- Version: `0.1.0`
- iOS build number: `1`
- Release channel: TestFlight beta first
- Product positioning: educational options-risk review, not trading signals or trade execution

## What Is Already Configured

- Expo app metadata in `frontend/mobile-demo/app.json`
- App icon, adaptive icon, favicon, and splash assets
- EAS build profiles in `frontend/mobile-demo/eas.json`
- iOS camera/photo permission text for contract screenshot review
- Privacy policy draft in `docs/PRIVACY_POLICY.md`
- Terms and disclaimer draft in `docs/TERMS_AND_DISCLAIMER.md`
- Release checklist in `docs/RELEASE_CHECKLIST.md`

## Required Before First TestFlight Upload

1. Create or use an Apple Developer account.
2. Log in to Expo/EAS locally:

   ```bash
   npx eas-cli login
   ```

3. Confirm the bundle identifier `com.aaravnagar.riskwise` is available in Apple Developer.
4. Host the privacy policy and terms somewhere public before public App Store submission.
5. Confirm production backend URL and environment variables are set.
6. Run the full local verification set:

   ```bash
   cd backend
   python -m pytest api/tests

   cd ../frontend/mobile-demo
   npm run typecheck
   npm run export:web
   ```

7. Build the iOS TestFlight artifact:

   ```bash
   cd frontend/mobile-demo
   npm run build:ios:testflight
   ```

8. Submit the build:

   ```bash
   npm run submit:ios:testflight
   ```

## App Store Safety Rules

Use language like:

- educational risk review
- decision support
- contract context
- missing-data warning
- risk and scenario explanation

Avoid language like:

- guaranteed profit
- signals
- buy this
- sell this
- beat the market
- execute trades

## Manual TestFlight Smoke Test

Run this on a real iPhone before inviting outside testers:

- Create account
- Sign in
- Reset password path is visible
- Run a stock idea check
- Run an option contract check
- Upload or manually enter contract context
- Generate a report
- Ask Coach about the report
- Run Deep Analysis
- Edit Profile risk rules
- Sign out and sign back in
- Confirm saved checks/profile settings persist

## Remaining Human-Owned Steps

Codex can prepare config, code, docs, and tests. Aarav must still own:

- Apple Developer enrollment
- App Store Connect app record
- EAS account login
- final TestFlight submission approval
- real iPhone testing
- final privacy/terms legal review
