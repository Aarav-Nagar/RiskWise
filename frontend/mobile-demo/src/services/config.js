const rawBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();

if (!rawBaseUrl) {
  throw new Error(
    "EXPO_PUBLIC_API_BASE_URL is not set. Set it in your environment (e.g. .env) before starting the app - the RiskWise backend URL cannot default to localhost."
  );
}

export const API_BASE_URL = rawBaseUrl;
