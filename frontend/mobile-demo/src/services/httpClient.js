let authTokenProvider = null;

export function configureAuth({ getToken } = {}) {
  authTokenProvider = typeof getToken === "function" ? getToken : null;
}

export async function buildHeaders({ userId, clerkId, withJson = true } = {}) {
  const headers = {};
  if (withJson) {
    headers["Content-Type"] = "application/json";
  }
  if (userId) {
    headers["X-RiskWise-User-ID"] = userId;
  }
  if (clerkId) {
    headers["X-Clerk-User-ID"] = clerkId;
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

export function formatApiError(data, response, fallback) {
  const requestId = data.request_id || response.headers?.get?.("X-Request-ID");
  const detail = data.detail || fallback;
  return requestId ? `${detail} (${requestId})` : detail;
}
