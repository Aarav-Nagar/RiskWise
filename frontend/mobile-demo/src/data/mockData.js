function defaultExpiration() {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export const tradeDraft = {
  user: "Alex",
  accountSize: 25000,
  riskBudget: 1250,
  ticker: "AAPL",
  tickerName: "Apple Inc.",
  tickerExchange: "NASDAQ",
  tradeType: "Call Option (Long)",
  optionSide: "call",
  strike: "190",
  expiration: defaultExpiration(),
  expirationSource: "manual",
  premium: "5.00",
  contracts: "1",
  bid: "",
  ask: "",
  impliedVolatility: "",
  openInterest: "",
  contractVolume: "",
  underlyingPrice: "",
  amountAtRisk: "500",
  timeframe: "1-2 Weeks"
};

export const baseReport = {
  badge: "Strong Setup",
  setupScore: 72,
  riskScore: 4.2,
  agentAgreement: 78,
  checks: [
    ["Trend Alignment", "good"],
    ["Volatility Context", "good"],
    ["Technical Setup", "good"],
    ["Risk / Reward", "warn"]
  ],
  agents: [
    ["Rule Coverage", 85, "good"],
    ["Evidence Completeness", 70, "good"],
    ["Unresolved Risk", 60, "risk"]
  ],
  scenarios: [
    ["Premium stress", "-52%", "-$260", "risk"],
    ["Small recovery", "+18%", "+$90", "good"],
    ["Upside sketch", "+85%", "+$425", "good"]
  ],
  contractLabel: {
    max_loss: 500,
    account_risk_pct: 2,
    breakeven: 194.25,
    days_left: 31,
    required_move_pct: 2.2,
    theta_risk: "Medium",
    iv_event_risk: "Elevated",
    difficulty: "Intermediate"
  },
  setupDebate: {
    bull_case: "The setup can be worth reviewing if price, timing, and risk budget are aligned.",
    bear_case: "The option may still need a fast enough move to outrun theta and IV changes.",
    risk_judge: "Sizing and contract timing decide whether the idea is manageable."
  },
  insight:
    "Setup quality is strong, but position size is slightly above optimal for the selected risk budget."
};
