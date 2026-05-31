export const trackedStocks = [
  { ticker: "AAPL", name: "Apple", sector: "Technology" },
  { ticker: "MSFT", name: "Microsoft", sector: "Technology" },
  { ticker: "NVDA", name: "NVIDIA", sector: "Technology" },
  { ticker: "AMZN", name: "Amazon", sector: "Consumer Discretionary" },
  { ticker: "GOOGL", name: "Alphabet", sector: "Communication Services" },
  { ticker: "META", name: "Meta Platforms", sector: "Communication Services" },
  { ticker: "TSLA", name: "Tesla", sector: "Consumer Discretionary" },
  { ticker: "BRK-B", name: "Berkshire Hathaway", sector: "Financials" },
  { ticker: "JPM", name: "JPMorgan Chase", sector: "Financials" },
  { ticker: "V", name: "Visa", sector: "Financials" },
  { ticker: "LLY", name: "Eli Lilly", sector: "Health Care" },
  { ticker: "UNH", name: "UnitedHealth Group", sector: "Health Care" },
  { ticker: "XOM", name: "Exxon Mobil", sector: "Energy" },
  { ticker: "JNJ", name: "Johnson & Johnson", sector: "Health Care" },
  { ticker: "PG", name: "Procter & Gamble", sector: "Consumer Staples" },
  { ticker: "MA", name: "Mastercard", sector: "Financials" },
  { ticker: "HD", name: "Home Depot", sector: "Consumer Discretionary" },
  { ticker: "AVGO", name: "Broadcom", sector: "Technology" },
  { ticker: "COST", name: "Costco", sector: "Consumer Staples" },
  { ticker: "ABBV", name: "AbbVie", sector: "Health Care" },
  { ticker: "KO", name: "Coca-Cola", sector: "Consumer Staples" },
  { ticker: "PEP", name: "PepsiCo", sector: "Consumer Staples" },
  { ticker: "MRK", name: "Merck", sector: "Health Care" },
  { ticker: "BAC", name: "Bank of America", sector: "Financials" }
];

export const stockLookup = new Map(
  trackedStocks.map((stock) => [stock.ticker.toUpperCase(), stock])
);
