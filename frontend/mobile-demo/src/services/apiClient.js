import { baseReport } from "../data/mockData";
import { API_BASE_URL } from "./config";

let authTokenProvider = null;

export function configureApiAuth({ getToken } = {}) {
  authTokenProvider = typeof getToken === "function" ? getToken : null;
}

export async function generateTradeCheck(draft, user) {
  const data = await postJson("/trade-check", {
    user_id: user?.id,
    ticker: draft.ticker,
    trade_type: draft.tradeType,
    option_side: draft.optionSide,
    strike: Number(draft.strike || 0),
    expiration: draft.expiration,
    expiration_source: draft.expirationSource || "manual",
    premium: nullableNumber(draft.premium),
    contracts: nullableInteger(draft.contracts),
    bid: nullableNumber(draft.bid),
    ask: nullableNumber(draft.ask),
    implied_volatility: nullableNumber(draft.impliedVolatility),
    open_interest: nullableInteger(draft.openInterest),
    contract_volume: nullableInteger(draft.contractVolume),
    underlying_price: nullableNumber(draft.underlyingPrice),
    amount_at_risk: Number(draft.amountAtRisk || 0),
    timeframe: draft.timeframe,
    account_size: Number(draft.accountSize || 0),
    risk_budget_percent: riskBudgetPercent(draft),
    trade_thesis: buildTradeThesis(draft),
    option_legs: buildOptionLegs(draft)
  }, user);
  return normalizeBackendReport(data, draft);
}

export async function sendChatMessage({ user, threadId, message, currentReport, chatMode, analysisDepth = "standard", attachments = [] }) {
  return postJson("/chat", {
    user_id: user.id,
    thread_id: threadId,
    message,
    current_report: currentReport,
    user_profile: user,
    chat_mode: chatMode,
    analysis_depth: analysisDepth,
    attachments
  }, user);
}

export async function extractContractFromAttachment({ user, attachments = [] }) {
  return postJson("/extract-contract", {
    user_id: user?.id,
    attachments
  }, user);
}

export async function getMarketProviderStatus() {
  return getJson("/market/providers");
}

export async function getAiProviderStatus() {
  return getJson("/ai/providers");
}

export async function runAiSmokeCheck() {
  return getJson("/ai/smoke");
}

export async function listChatThreads(user) {
  if (!user?.id) {
    return [];
  }
  return getJson(`/chat/threads/${encodeURIComponent(user.id)}`, user);
}

export async function listChatMessages(user, threadId) {
  if (!user?.id || !threadId) {
    return [];
  }
  return getJson(`/chat/threads/${encodeURIComponent(user.id)}/${encodeURIComponent(threadId)}`, user);
}

export async function getOptionsContext(ticker) {
  if (!ticker) {
    return null;
  }
  return getJson(`/market/options-context/${encodeURIComponent(ticker.toUpperCase())}`);
}

export async function getOptionsExpirations(ticker) {
  if (!ticker) {
    return null;
  }
  return getJson(`/market/options/expirations/${encodeURIComponent(ticker.toUpperCase())}`);
}

export async function getOptionsChain({ ticker, expiration }) {
  if (!ticker) {
    return null;
  }
  const params = new URLSearchParams();
  if (expiration) params.set("expiration", expiration);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return getJson(`/market/options/chain/${encodeURIComponent(ticker.toUpperCase())}${suffix}`);
}

export async function getOptionContractContext({ ticker, expiration, strike, optionSide }) {
  if (!ticker) {
    return null;
  }
  const params = new URLSearchParams();
  if (expiration) params.set("expiration", expiration);
  if (strike) params.set("strike", String(strike));
  if (optionSide) params.set("option_side", optionSide);
  return getJson(`/market/options/contract-context/${encodeURIComponent(ticker.toUpperCase())}?${params.toString()}`);
}

export async function searchMarketSymbols(query) {
  const clean = String(query || "").trim();
  if (!clean) {
    return [];
  }
  const data = await getJson(`/market/search?q=${encodeURIComponent(clean)}`);
  return Array.isArray(data.items) ? data.items : [];
}

export async function getMarketBundle(ticker) {
  if (!ticker) {
    return { quote: null, profile: null, news: null, earnings: null, optionsContext: null };
  }
  const symbol = encodeURIComponent(ticker.toUpperCase());
  const [quote, profile, news, earnings, optionsContext] = await Promise.allSettled([
    getJson(`/market/quote/${symbol}`),
    getJson(`/market/profile/${symbol}`),
    getJson(`/market/news/${symbol}`),
    getJson(`/market/earnings/${symbol}`),
    getJson(`/market/options-context/${symbol}`)
  ]);
  return {
    quote: quote.status === "fulfilled" ? quote.value : null,
    profile: profile.status === "fulfilled" ? profile.value : null,
    news: news.status === "fulfilled" ? news.value : null,
    earnings: earnings.status === "fulfilled" ? earnings.value : null,
    optionsContext: optionsContext.status === "fulfilled" ? optionsContext.value : null
  };
}

export async function listSavedChecks(user) {
  if (!user?.id) {
    return [];
  }
  const rows = await getJson(`/saved-checks/${encodeURIComponent(user.id)}`, user);
  return rows.map((item) => ({ ...item, report: normalizeSavedReport(item.report) }));
}

export async function saveCheck(user, report, note = "") {
  const item = await postJson("/saved-checks", {
    user_id: user.id,
    trade_check_id: report.id,
    report,
    note
  }, user);
  return { ...item, report: normalizeSavedReport(item.report) };
}

export async function getSavedCheckExport(user, savedCheckId) {
  if (!user?.id || !savedCheckId) {
    throw new Error("Select a saved Check before exporting.");
  }
  return getJson(
    `/saved-checks/${encodeURIComponent(user.id)}/${encodeURIComponent(savedCheckId)}/export`,
    user
  );
}

function normalizeBackendReport(data, draft) {
  return {
    id: data.id || `check-${Date.now()}`,
    ...baseReport,
    title: data.title || `${draft.ticker.toUpperCase()} ${draft.tradeType}`,
    subtitle: data.subtitle || `$${draft.strike} Strike - ${draft.expiration} - ${draft.timeframe}`,
    ticker: data.ticker || draft.ticker.toUpperCase(),
    tradeType: data.trade_type || draft.tradeType,
    strike: String(data.strike || draft.strike),
    expiration: data.expiration || draft.expiration,
    amountAtRisk: data.amount_at_risk || Number(draft.amountAtRisk || 0),
    timeframe: data.timeframe || draft.timeframe,
    badge: data.badge || baseReport.badge,
    setupScore: data.setup_score ?? baseReport.setupScore,
    riskScore: data.risk_score ?? baseReport.riskScore,
    agentAgreement: data.agent_agreement ?? baseReport.agentAgreement,
    checks: data.checks || baseReport.checks,
    agents: data.agents || baseReport.agents,
    scenarios: data.scenarios || baseReport.scenarios,
    methodologyLabel: data.methodology_label || "Backend educational score",
    insight: data.insight || baseReport.insight,
    overallRead: data.overall_read || "Review the trade structure before deciding",
    weakestLink: data.weakest_link || "Position sizing",
    riskPosture: data.risk_posture || "Mixed",
    decisionSnapshot: data.decision_snapshot || {},
    riskMath: data.risk_math || {},
    agentDocket: data.agent_docket || [],
    agreementMap: data.agreement_map || {},
    questions: data.questions || [],
    contractLabel: data.contract_label || {},
    setupDebate: data.setup_debate || {}
    ,
    contractSnapshot: data.contract_snapshot || {},
    dataQuality: data.data_quality || {}
  };
}

function normalizeSavedReport(report) {
  if (!report) {
    return {};
  }
  return {
    ...report,
    contractLabel: report.contractLabel || report.contract_label || {},
    setupDebate: report.setupDebate || report.setup_debate || {},
    decisionSnapshot: report.decisionSnapshot || report.decision_snapshot || {},
    riskMath: report.riskMath || report.risk_math || {},
    agentDocket: report.agentDocket || report.agent_docket || [],
    agreementMap: report.agreementMap || report.agreement_map || {},
    contractSnapshot: report.contractSnapshot || report.contract_snapshot || {},
    dataQuality: report.dataQuality || report.data_quality || {}
  };
}

async function postJson(path, body, user) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: await buildHeaders(user),
      body: JSON.stringify(body)
    });
  } catch (err) {
    throw new Error(networkErrorMessage(path));
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "The RiskWise service is unavailable."));
  }
  return data;
}

async function getJson(path, user) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers: await buildHeaders(user) });
  } catch (err) {
    throw new Error(networkErrorMessage(path));
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatApiError(data, response, "The RiskWise service is unavailable."));
  }
  return data;
}

function networkErrorMessage(path) {
  const target = API_BASE_URL.replace(/^https?:\/\//, "");
  if (path.startsWith("/trade-check")) {
    return `RiskWise backend is offline at ${target}. Start the FastAPI server, then run the check again.`;
  }
  if (path.startsWith("/market")) {
    return `Market context is unavailable because the backend is offline at ${target}.`;
  }
  if (path.startsWith("/chat")) {
    return `RiskWiseAI is offline because the backend is not reachable at ${target}.`;
  }
  return `RiskWise backend is not reachable at ${target}.`;
}

async function buildHeaders(user) {
  const headers = { "Content-Type": "application/json" };
  if (user?.id) {
    headers["X-RiskWise-User-ID"] = user.id;
  }
  if (user?.clerkId) {
    headers["X-Clerk-User-ID"] = user.clerkId;
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

function nullableNumber(value) {
  const number = Number(String(value ?? "").replace(/[^0-9.]/g, ""));
  return Number.isFinite(number) && number > 0 ? number : null;
}

function nullableInteger(value) {
  const number = parseInt(String(value ?? "").replace(/[^0-9]/g, ""), 10);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function riskBudgetPercent(draft) {
  const accountSize = Number(draft?.accountSize || 0);
  const riskBudget = Number(draft?.riskBudget || 0);
  if (accountSize > 0 && riskBudget > 0) {
    return Math.max(0.1, Math.min(25, Math.round((riskBudget / accountSize) * 1000) / 10));
  }
  return Number(draft?.riskBudgetPercent || 2) || 2;
}

function buildTradeThesis(draft) {
  return compactObject({
    direction: cleanText(draft?.direction),
    target_price_low: nullableNumber(draft?.targetPriceLow),
    target_price_high: nullableNumber(draft?.targetPriceHigh),
    target_date: cleanText(draft?.targetDate),
    catalyst: cleanText(draft?.catalyst),
    invalidation: cleanText(draft?.invalidation),
    confidence: nullableNumber(draft?.confidence),
    maximum_loss: nullableNumber(draft?.amountAtRisk),
    intended_hold_period: cleanText(draft?.timeframe || draft?.timeHorizon)
  });
}

function buildOptionLegs(draft) {
  const type = cleanText(draft?.optionSide || (String(draft?.tradeType || "").toLowerCase().includes("put") ? "put" : "call")).toLowerCase();
  if (isSpreadStructure(draft?.structure || draft?.tradeType)) {
    return buildSpreadLegs(draft, type);
  }
  const strike = nullableNumber(draft?.strike);
  const expiration = cleanText(draft?.expiration);
  const quantity = nullableInteger(draft?.contracts);
  if (!["call", "put"].includes(type) || !strike || !expiration || !quantity) {
    return [];
  }
  return [
    compactObject({
      action: "buy",
      type,
      strike,
      expiration,
      quantity,
      bid: nullableNumber(draft?.bid),
      ask: nullableNumber(draft?.ask),
      premium: nullableNumber(draft?.premium),
      iv: nullableNumber(draft?.impliedVolatility),
      greeks: compactObject({
        delta: nullableSignedNumber(draft?.delta),
        gamma: nullableSignedNumber(draft?.gamma),
        theta: nullableSignedNumber(draft?.theta),
        vega: nullableSignedNumber(draft?.vega),
        rho: nullableSignedNumber(draft?.rho)
      })
    })
  ];
}

function buildSpreadLegs(draft, type) {
  const expiration = cleanText(draft?.expiration);
  const quantity = nullableInteger(draft?.contracts);
  const longStrike = nullableNumber(draft?.longStrike || draft?.strike);
  const shortStrike = nullableNumber(draft?.shortStrike);
  if (!["call", "put"].includes(type) || !expiration || !quantity || !longStrike || !shortStrike) {
    return [];
  }
  return [
    compactObject({
      action: "buy",
      type,
      strike: longStrike,
      expiration,
      quantity,
      bid: nullableNumber(draft?.longBid),
      ask: nullableNumber(draft?.longAsk),
      premium: nullableNumber(draft?.longPremium),
      iv: nullableNumber(draft?.impliedVolatility),
      greeks: compactObject({
        delta: nullableSignedNumber(draft?.longDelta || draft?.delta),
        gamma: nullableSignedNumber(draft?.longGamma || draft?.gamma),
        theta: nullableSignedNumber(draft?.longTheta || draft?.theta),
        vega: nullableSignedNumber(draft?.longVega || draft?.vega),
        rho: nullableSignedNumber(draft?.longRho || draft?.rho)
      })
    }),
    compactObject({
      action: "sell",
      type,
      strike: shortStrike,
      expiration,
      quantity,
      bid: nullableNumber(draft?.shortBid),
      ask: nullableNumber(draft?.shortAsk),
      premium: nullableNumber(draft?.shortPremium),
      iv: nullableNumber(draft?.impliedVolatility),
      greeks: compactObject({
        delta: nullableSignedNumber(draft?.shortDelta),
        gamma: nullableSignedNumber(draft?.shortGamma),
        theta: nullableSignedNumber(draft?.shortTheta),
        vega: nullableSignedNumber(draft?.shortVega),
        rho: nullableSignedNumber(draft?.shortRho)
      })
    })
  ];
}

function isSpreadStructure(value) {
  const lower = String(value || "").toLowerCase();
  return lower.includes("spread") || lower === "call_spread" || lower === "put_spread";
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => {
      if (item === null || item === undefined || item === "") return false;
      if (typeof item === "object" && !Array.isArray(item) && Object.keys(item).length === 0) return false;
      return true;
    })
  );
}

function cleanText(value) {
  return String(value ?? "").trim();
}

function nullableSignedNumber(value) {
  const number = Number(String(value ?? "").replace(/[^0-9.-]/g, ""));
  return Number.isFinite(number) ? number : null;
}

function formatApiError(data, response, fallback) {
  const requestId = data.request_id || response.headers?.get?.("X-Request-ID");
  const detail = data.detail || fallback;
  if (requestId) {
    return `${detail} (${requestId})`;
  }
  return detail;
}
