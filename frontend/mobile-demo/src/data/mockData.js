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
