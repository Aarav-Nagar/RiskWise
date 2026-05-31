import { formatCompactNumber, formatCurrency, formatPercent } from "../lib/formatters.js";
import { Card, CardTitle, Grid, MetricLabel, MetricValue } from "./PagePrimitives.jsx";

export default function MetricCards({ stocks = [] }) {
  const gainers = stocks.filter((stock) => stock.changePercent > 0).length;
  const losers = stocks.filter((stock) => stock.changePercent < 0).length;
  const totalVolume = stocks.reduce((sum, stock) => sum + (stock.volume || 0), 0);
  const totalMarketCap = stocks.reduce((sum, stock) => sum + (stock.marketCap || 0), 0);
  const avgChange =
    stocks.length === 0
      ? 0
      : stocks.reduce((sum, stock) => sum + (stock.changePercent || 0), 0) / stocks.length;

  const cards = [
    {
      title: "Average Move",
      value: formatPercent(avgChange),
      label: "Mean daily change across tracked names"
    },
    {
      title: "Breadth",
      value: `${gainers}/${losers}`,
      label: "Gainers vs. decliners"
    },
    {
      title: "Combined Volume",
      value: formatCompactNumber(totalVolume),
      label: "Shares traded today"
    },
    {
      title: "Tracked Market Cap",
      value: formatCurrency(totalMarketCap, 0),
      label: "Aggregate capitalization"
    }
  ];

  return (
    <Grid columns={4}>
      {cards.map((card) => (
        <Card key={card.title}>
          <CardTitle>{card.title}</CardTitle>
          <MetricValue>{card.value}</MetricValue>
          <MetricLabel>{card.label}</MetricLabel>
        </Card>
      ))}
    </Grid>
  );
}
