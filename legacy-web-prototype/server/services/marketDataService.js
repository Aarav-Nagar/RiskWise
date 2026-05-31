import yahooFinance from "yahoo-finance2";
import { trackedStocks, stockLookup } from "../data/sp500.js";
import { calculateQuantStats } from "../utils/math.js";

yahooFinance.suppressNotices(["yahooSurvey"]);

function normalizeTickerForYahoo(ticker) {
  return ticker.toUpperCase();
}

function seedFromTicker(ticker) {
  return ticker.split("").reduce((hash, character) => hash + character.charCodeAt(0), 0);
}

function buildMockQuote(stock) {
  const seed = seedFromTicker(stock.ticker);
  const price = 90 + (seed % 320) + ((seed % 17) / 10);
  const changePercent = ((seed % 900) - 450) / 100;
  const volume = 1_000_000 + (seed % 25) * 650_000;
  const marketCap = 40_000_000_000 + (seed % 180) * 8_500_000_000;

  return {
    ticker: stock.ticker,
    name: stock.name,
    sector: stock.sector,
    price,
    changePercent,
    volume,
    marketCap,
    currency: "USD",
    source: "mock"
  };
}

function buildMockHistoricalPrices(ticker) {
  const seed = seedFromTicker(ticker);
  const base = 90 + (seed % 320);
  const direction = seed % 2 === 0 ? 1 : -1;

  return Array.from({ length: 30 }, (_, index) => {
    const trend = direction * index * 0.8;
    const seasonal = Math.sin((index + seed) / 4) * 4.2;
    const close = Number((base + trend + seasonal).toFixed(2));
    const date = new Date();
    date.setDate(date.getDate() - (29 - index));

    return {
      date: date.toISOString().slice(0, 10),
      close
    };
  });
}

function buildMockSummary(stock) {
  const seed = seedFromTicker(stock.ticker);
  const price = buildMockQuote(stock).price;

  return {
    fiftyTwoWeekHigh: Number((price * 1.18).toFixed(2)),
    fiftyTwoWeekLow: Number((price * 0.76).toFixed(2)),
    trailingPE: Number((14 + (seed % 20) * 0.9).toFixed(2)),
    beta: Number((0.75 + (seed % 9) * 0.12).toFixed(2)),
    dividendYield: Number((((seed % 7) + 1) / 100).toFixed(4)),
    targetMeanPrice: Number((price * 1.07).toFixed(2)),
    exchangeName: "NASDAQ GS"
  };
}

function extractQuoteFields(quote, fallbackMeta = {}) {
  return {
    ticker: quote.symbol,
    name: quote.longName || quote.shortName || fallbackMeta.name || quote.symbol,
    sector: quote.sector || fallbackMeta.sector || "Unknown",
    price: quote.regularMarketPrice ?? 0,
    changePercent: quote.regularMarketChangePercent ?? 0,
    volume: quote.regularMarketVolume ?? 0,
    marketCap: quote.marketCap ?? 0,
    currency: quote.currency || "USD"
  };
}

export async function fetchTrackedStocks() {
  try {
    const combinedQuote = await yahooFinance.quoteCombine(
      trackedStocks.map((stock) => normalizeTickerForYahoo(stock.ticker)).join(" ")
    );

    const quotes = trackedStocks
      .map((stock) => {
        const quote = combinedQuote[stock.ticker];
        return quote ? extractQuoteFields(quote, stock) : buildMockQuote(stock);
      })
      .sort((left, right) => left.ticker.localeCompare(right.ticker));

    return quotes;
  } catch {
    return trackedStocks
      .map((stock) => buildMockQuote(stock))
      .sort((left, right) => left.ticker.localeCompare(right.ticker));
  }
}

export async function fetchStockQuote(ticker) {
  const normalized = normalizeTickerForYahoo(ticker);
  const fallbackMeta = stockLookup.get(normalized) ?? {
    ticker: normalized,
    name: normalized,
    sector: "Unknown"
  };

  try {
    const quote = await yahooFinance.quote(normalized);
    return extractQuoteFields(quote, fallbackMeta);
  } catch {
    return buildMockQuote(fallbackMeta);
  }
}

export async function fetchHistoricalPrices(ticker) {
  const normalized = normalizeTickerForYahoo(ticker);
  try {
    const period1 = new Date();
    period1.setMonth(period1.getMonth() - 3);

    const history = await yahooFinance.historical(normalized, {
      period1,
      interval: "1d"
    });

    return history
      .map((entry) => ({
        date: new Date(entry.date).toISOString().slice(0, 10),
        close: entry.close
      }))
      .filter((entry) => Number.isFinite(entry.close))
      .slice(-30);
  } catch {
    return buildMockHistoricalPrices(normalized);
  }
}

export async function fetchStockSummary(ticker) {
  const normalized = normalizeTickerForYahoo(ticker);
  const fallbackMeta = stockLookup.get(normalized) ?? {
    ticker: normalized,
    name: normalized,
    sector: "Unknown"
  };

  try {
    const result = await yahooFinance.quoteSummary(normalized, {
      modules: ["price", "summaryDetail", "defaultKeyStatistics", "financialData"]
    });

    const summaryDetail = result.summaryDetail ?? {};
    const defaultKeyStatistics = result.defaultKeyStatistics ?? {};
    const financialData = result.financialData ?? {};
    const price = result.price ?? {};

    return {
      fiftyTwoWeekHigh: summaryDetail.fiftyTwoWeekHigh ?? null,
      fiftyTwoWeekLow: summaryDetail.fiftyTwoWeekLow ?? null,
      trailingPE: summaryDetail.trailingPE ?? defaultKeyStatistics.trailingPE ?? null,
      beta: defaultKeyStatistics.beta ?? null,
      dividendYield: summaryDetail.dividendYield ?? null,
      targetMeanPrice: financialData.targetMeanPrice ?? null,
      exchangeName: price.exchangeName ?? null
    };
  } catch {
    return buildMockSummary(fallbackMeta);
  }
}

export async function fetchStockDetail(ticker) {
  const [quote, historicalPrices, summary] = await Promise.all([
    fetchStockQuote(ticker),
    fetchHistoricalPrices(ticker),
    fetchStockSummary(ticker)
  ]);

  return {
    ...quote,
    summary,
    historicalPrices,
    quant: calculateQuantStats(historicalPrices)
  };
}

export async function enrichPortfolioEntries(entries) {
  if (!entries.length) {
    return { holdings: [], totals: { marketValue: 0, gainLoss: 0 } };
  }

  const quotes = await Promise.all(entries.map((entry) => fetchStockQuote(entry.ticker)));

  const holdings = entries.map((entry, index) => {
    const quote = quotes[index];
    const currentValue = quote.price * entry.shares;
    const costBasis = entry.buyPrice * entry.shares;
    const gainLoss = currentValue - costBasis;
    const gainLossPercent = costBasis === 0 ? 0 : gainLoss / costBasis;

    return {
      ...entry,
      name: quote.name,
      sector: quote.sector,
      currentPrice: quote.price,
      currentValue,
      gainLoss,
      gainLossPercent
    };
  });

  return {
    holdings,
    totals: {
      marketValue: holdings.reduce((sum, holding) => sum + holding.currentValue, 0),
      gainLoss: holdings.reduce((sum, holding) => sum + holding.gainLoss, 0)
    }
  };
}
