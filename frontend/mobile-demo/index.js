import { registerRootComponent } from "expo";
import { ClerkProvider } from "@clerk/clerk-expo";
import { tokenCache } from "@clerk/clerk-expo/token-cache";
import * as Sentry from "@sentry/react-native";

import App from "./src/App";

const publishableKey = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY;
const sentryDsn = process.env.EXPO_PUBLIC_SENTRY_DSN;

if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: "development",
    tracesSampleRate: 0.1
  });
}

function Root() {
  if (!publishableKey) {
    console.warn("Clerk publishable key is missing. Running RiskWise in unsigned preview mode.");
    return <App />;
  }

  return (
    <ClerkProvider publishableKey={publishableKey} tokenCache={tokenCache}>
      <App />
    </ClerkProvider>
  );
}

registerRootComponent(sentryDsn ? Sentry.wrap(Root) : Root);
