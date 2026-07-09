const profile = process.env.EAS_BUILD_PROFILE || "";
const requireProductionClerk =
  process.env.RISKWISE_REQUIRE_PRODUCTION_CLERK === "true" || profile === "production";
const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || "";
const clerkPublishableKey = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY || "";

function fail(message) {
  console.error(`[RiskWise production env] ${message}`);
  process.exit(1);
}

function warn(message) {
  console.warn(`[RiskWise production env] ${message}`);
}

if (!profile && !requireProductionClerk) {
  process.exit(0);
}

if (apiBaseUrl && !apiBaseUrl.startsWith("https://")) {
  fail("EXPO_PUBLIC_API_BASE_URL must use https for EAS builds.");
}

if (requireProductionClerk) {
  if (!clerkPublishableKey) {
    fail("Production builds require EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY from EAS environment.");
  }

  if (!clerkPublishableKey.startsWith("pk_live_")) {
    fail("Production builds require a Clerk production publishable key starting with pk_live_.");
  }
}

if (profile === "testflight" && clerkPublishableKey.startsWith("pk_test_")) {
  warn("Using development Clerk for internal TestFlight only. Do not use this build for external beta.");
}
