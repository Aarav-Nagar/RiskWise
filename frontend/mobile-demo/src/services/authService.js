import { API_BASE_URL } from "./config";

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
  const response = await fetch(`${API_BASE_URL}/auth/profile-by-email?email=${encodeURIComponent(email)}`);
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
  const response = await fetch(`${API_BASE_URL}/auth/users/${encodeURIComponent(userId)}/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-RiskWise-User-ID": userId },
    body: JSON.stringify(updates)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "Could not save profile settings."));
  }
  return data;
}

export async function clearRiskWiseContext(userId) {
  const response = await fetch(`${API_BASE_URL}/auth/users/${encodeURIComponent(userId)}/context`, {
    method: "DELETE",
    headers: { "X-RiskWise-User-ID": userId }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "Could not clear profile context."));
  }
  return data;
}

export async function deleteRiskWiseAccount(userId) {
  const response = await fetch(`${API_BASE_URL}/auth/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
    headers: { "X-RiskWise-User-ID": userId }
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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "The account service is unavailable."));
  }
  return data;
}

function formatApiError(data, response, fallback) {
  const requestId = data.request_id || response.headers?.get?.("X-Request-ID");
  const detail = data.detail || fallback;
  return requestId ? `${detail} (${requestId})` : detail;
}
