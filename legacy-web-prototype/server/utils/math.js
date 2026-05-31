export function average(values) {
  if (!values.length) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function standardDeviation(values) {
  if (values.length <= 1) {
    return 0;
  }

  const mean = average(values);
  const variance = average(values.map((value) => (value - mean) ** 2));
  return Math.sqrt(variance);
}

export function movingAverage(values, window) {
  if (values.length < window) {
    return null;
  }

  return average(values.slice(-window));
}

export function calculateDailyReturns(prices) {
  const returns = [];

  for (let index = 1; index < prices.length; index += 1) {
    const previous = prices[index - 1];
    const current = prices[index];

    if (previous === 0 || previous == null || current == null) {
      continue;
    }

    returns.push((current - previous) / previous);
  }

  return returns;
}

export function calculateQuantStats(priceSeries) {
  const closes = priceSeries
    .map((entry) => Number(entry.close))
    .filter((value) => Number.isFinite(value));

  const ma10 = movingAverage(closes, 10);
  const ma30 = movingAverage(closes, 30);
  const returns = calculateDailyReturns(closes);
  const dailyStdDev = standardDeviation(returns);
  const rollingAverage30 = ma30 ?? average(closes);

  let momentum = "Neutral";
  if (ma10 != null && ma30 != null) {
    if (ma10 > ma30) {
      momentum = "Bullish crossover";
    } else if (ma10 < ma30) {
      momentum = "Bearish crossover";
    }
  }

  return {
    rollingAverage30,
    movingAverage10: ma10,
    movingAverage30: ma30,
    dailyReturnStdDev: dailyStdDev,
    momentum,
    sampleSize: closes.length
  };
}
