const financeKnowledgeBase = [
  {
    patterns: [/\bp\/e\b/i, /\bpe ratio\b/i, /\bprice[-\s]to[-\s]earnings\b/i],
    answer:
      "The P/E ratio compares a company's stock price to its earnings per share. A higher P/E often means investors expect stronger future growth, while a lower P/E can signal slower growth or a cheaper valuation."
  },
  {
    patterns: [/\bimplied volatility\b/i, /\biv\b/i],
    answer:
      "Implied volatility is the market's estimate of how much a stock could move in the future, derived from options prices. Higher implied volatility usually means options are more expensive because traders expect bigger swings."
  },
  {
    patterns: [/\bsharpe ratio\b/i],
    answer:
      "The Sharpe ratio measures return per unit of risk. It is usually calculated as portfolio return minus the risk-free rate, divided by portfolio volatility. Higher is generally better because it means more return for each unit of risk."
  },
  {
    patterns: [/\bbeta\b/i],
    answer:
      "Beta estimates how sensitive a stock is to broad market moves. A beta above 1 means the stock tends to move more than the market, below 1 means it tends to move less, and a negative beta would imply the opposite direction."
  },
  {
    patterns: [/\bmoving average\b/i, /\bma crossover\b/i, /\bmomentum\b/i],
    answer:
      "A moving average smooths price data over a lookback window. Traders often compare a short-term average like the 10-day MA to a longer one like the 30-day MA. When the short average rises above the long average, that is often read as bullish momentum."
  }
];

export function getChatResponse(message) {
  const match = financeKnowledgeBase.find((entry) =>
    entry.patterns.some((pattern) => pattern.test(message))
  );

  if (match) {
    return match.answer;
  }

  return "I can help with finance basics like P/E ratio, beta, implied volatility, moving averages, momentum, and the Sharpe ratio. Try asking about one of those concepts.";
}
