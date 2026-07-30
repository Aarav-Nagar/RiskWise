# iOS / TestFlight Build Runbook

Everything that does **not** need an Apple account is staged and verified (2026-07-23). This is the
exact sequence for the day you enroll. Reference: `docs/APP_STORE_TESTFLIGHT.md`,
`docs/APP_STORE_LISTING.md`, `docs/PRODUCTION_ENVIRONMENT.md`.

## Already staged & verified (no action needed)
- `app.json` iOS: bundle id `com.aaravnagar.riskwise`, buildNumber `1`, camera/photo permission
  strings, `ITSAppUsesNonExemptEncryption:false`, portrait, scheme `riskwise`. **`eas config
  --platform ios --profile testflight` resolves cleanly (exit 0).**
- App icon 1024×1024 (Expo flattens the alpha channel for the iOS icon during build).
- `eas.json` `testflight` profile: `distribution: store`, `autoIncrement: true`, env baked
  (prod API + Clerk key), `ios.simulator: false`.
- EAS project linked (`@aaravn/riskwise`); app bundles clean for iOS (verified 10.5 MB, HTTP 200).
- Scripts ready: `npm run build:ios:testflight`, `npm run submit:ios:testflight`.
- The `testflight` profile's dev Clerk key only **warns** in `validate-production-env.cjs` — so an
  internal TestFlight build succeeds as-is.

## The Apple-gated sequence (in order)
1. **Enroll** in the Apple Developer Program ($99/yr) at developer.apple.com. Approval can take a day.
2. **App Store Connect → create the app record.** Register the App ID `com.aaravnagar.riskwise`
   (Certificates, Identifiers & Profiles), then create the app: name, primary language, SKU, and the
   **Privacy Policy URL** (host `legal/privacy.html` first — see `legal/README.md`).
3. **Build** (from `frontend/mobile-demo`):
   ```bash
   npm run build:ios:testflight
   ```
   On first run EAS logs into Apple and **auto-generates the iOS distribution cert + provisioning
   profile** for you. Approve the prompts (or use an App Store Connect API key — see below for the
   fully non-interactive path).
4. **Submit:**
   ```bash
   npm run submit:ios:testflight
   ```
   Interactive submit will prompt for Apple ID / team. For non-interactive, fill
   `eas.json → submit.testflight.ios` with `appleId`, `ascAppId` (the app's numeric Apple ID),
   `appleTeamId` (10-char team id) — or reference an ASC API key.
5. **TestFlight** (App Store Connect → TestFlight): add **internal testers** (no beta review needed),
   fill **Test Information** using the "What to Test" block in `docs/APP_STORE_LISTING.md`, and provide
   a **demo account** in App Review notes. External testers need a short Beta App Review.

## Recommended: fully non-interactive (App Store Connect API key)
So build + submit never stop to prompt:
1. App Store Connect → Users and Access → Integrations → **App Store Connect API** → generate a key.
2. Download the `.p8`, note the **Key ID** and **Issuer ID**.
3. Add them to EAS (`eas credentials` or env) and reference in `submit` config. Then both commands run
   headless.

## KNOWN BLOCKER carried over from the Android build (fix before iOS build)
The `@sentry/react-native` Gradle/Xcode plugin runs a **source-map upload** task on release
builds that **hard-fails** with `error: An organization ID or slug is required` when no Sentry
org/token is configured. This killed the Android build until fixed, and the **`testflight` and
`production` profiles will fail identically**. Before building iOS, either:
- add `"SENTRY_DISABLE_AUTO_UPLOAD": "true"` to the profile's `env` in `eas.json` (quick — matches
  what the `preview` profile now does), **or**
- configure real Sentry upload: set `SENTRY_ORG`, `SENTRY_PROJECT`, and `SENTRY_AUTH_TOKEN` in the
  EAS profile env (preferred for a real release, so crashes symbolicate).

## Gating decisions before you build
- **Internal TestFlight:** current **dev Clerk** is fine (build succeeds). 
- **External beta / App Store:** switch to **production Clerk** (`pk_live_` into EAS, prod Clerk values
  into Render) — the `production` profile **fails fast** without `pk_live_`. Also rotate the shared
  Mongo/Clerk/Expo secrets at this point (`PRODUCTION_ENVIRONMENT.md §Secret Rotation`).
- **Sign in with Apple (Guideline 4.8):** if the sign-in screen exposes Google/social login on iOS,
  add Sign in with Apple or disable social providers for the App Store build.
- **Privacy Policy URL** is required in App Store Connect — host the `legal/` pages first.
