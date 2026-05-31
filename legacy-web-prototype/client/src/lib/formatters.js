export function formatCurrency(value, digits = 2) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  }).format(value ?? 0);
}

export function formatCompactNumber(value) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2
  }).format(value ?? 0);
}

export function formatPercent(value, digits = 2) {
  return `${((value ?? 0) * (Math.abs(value ?? 0) <= 1 ? 100 : 1)).toFixed(digits)}%`;
}
