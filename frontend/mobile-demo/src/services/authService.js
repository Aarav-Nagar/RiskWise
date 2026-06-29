import { API_BASE_URL } from "./config";

let authTokenProvider = null;

export function configureAuthService({ getToken } = {}) {
  authTokenProvider = typeof getToken === "function" ? getToken : null;
}

export async function restoreSession() {
  return null;
}

export async function syncClerkProfile({ clerkId, email, name, profile = {} }) {
  const payload = {
    clerkId,
    name: name || profile.name || "RiskWise User",
    email,
    accountSize: Number(profile.accountSize || 25000),
    riskBudgetPercent: Number(profile.riskBudgetPercent || 2),
    purpose: profile.purpose || [],
    tradeFocus: profile.tradeFocus || [],
    experienceLevel: profile.experienceLevel || "Still learning",
    riskStyle: profile.riskStyle || "Balanced",
    struggles: profile.struggles || [],
    reminders: profile.reminders || [],
    sectors: profile.sectors || [],
    marketCaps: profile.marketCaps || [],
    events: profile.events || [],
    safetyAccepted: Boolean(profile.safetyAccepted),
    aiMemory: profile.aiMemory || {},
    riskRules: profile.riskRules || {},
    coachStyle: profile.coachStyle || {},
    savedContext: profile.savedContext || {},
    appPreferences: profile.appPreferences || {}
  };
  return postJson("/auth/clerk-sync", payload);
}

export async function lookupProfileByEmail(email) {
  const response = await safeFetch(`${API_BASE_URL}/auth/profile-by-email?email=${encodeURIComponent(email)}`, {
    headers: await buildHeaders()
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "Could not load your profile."));
  }
  return data;
}

export async function requestPasswordReset({ email }) {
  return postJson("/auth/forgot-password", { email });
}

export async function updateProfileSettings(userId, updates) {
  const response = await safeFetch(`${API_BASE_URL}/auth/users/${encodeURIComponent(userId)}/profile`, {
    method: "PATCH",
    headers: await buildHeaders(userId),
    body: JSON.stringify(updates)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "Could not save profile settings."));
  }
  return data;
}

export async function clearRiskWiseContext(userId) {
  const response = await safeFetch(`${API_BASE_URL}/auth/users/${encodeURIComponent(userId)}/context`, {
    method: "DELETE",
    headers: await buildHeaders(userId, false)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "Could not clear profile context."));
  }
  return data;
}

export async function getRiskWiseContextSummary(userId) {
  const response = await safeFetch(`${API_BASE_URL}/auth/users/${encodeURIComponent(userId)}/context-summary`, {
    headers: await buildHeaders(userId, false)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "Could not load context summary."));
  }
  return data;
}

export async function deleteRiskWiseAccount(userId) {
  const response = await safeFetch(`${API_BASE_URL}/auth/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
    headers: await buildHeaders(userId, false)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "Could not delete account data."));
  }
  return data;
}

export async function signOut() {
  return true;
}

async function postJson(path, body) {
  const response = await safeFetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: await buildHeaders(),
    body: JSON.stringify(body)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "The account service is unavailable."));
  }
  return data;
}

async function safeFetch(url, options) {
  try {
    return await fetch(url, options);
  } catch (err) {
    throw new Error("RiskWise account sync is offline. Start the backend API, or keep using preview mode while working locally.");
  }
}

async function buildHeaders(userId, withJson = true) {
  const headers = {};
  if (withJson) {
    headers["Content-Type"] = "application/json";
  }
  if (userId) {
    headers["X-RiskWise-User-ID"] = userId;
  }
  const token = await readClerkToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function readClerkToken() {
  if (!authTokenProvider) {
    return "";
  }
  try {
    return (await authTokenProvider()) || "";
  } catch (err) {
    return "";
  }
}

function formatApiError(data, response, fallback) {
  const requestId = data.request_id || response.headers?.get?.("X-Request-ID");
  const detail = data.detail || fallback;
  return requestId ? `${detail} (${requestId})` : detail;
}
