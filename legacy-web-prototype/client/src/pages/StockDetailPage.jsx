import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../lib/api.js";
import { formatCurrency, formatPercent } from "../lib/formatters.js";
import StockChart from "../components/StockChart.jsx";
import {
  Card,
  CardTitle,
  Eyebrow,
  Grid,
  Header,
  HeaderText,
  MetricLabel,
  MetricValue,
  Page,
  Subtitle,
  Title
} from "../components/PagePrimitives.jsx";

function StatCard({ title, value, label }) {
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      <MetricValue>{value}</MetricValue>
      <MetricLabel>{label}</MetricLabel>
    </Card>
  );
}

export default function StockDetailPage() {
  const { ticker } = useParams();
  const [stock, setStock] = useState(null);

  useEffect(() => {
    api.get(`/stock/${ticker}`).then((response) => setStock(response.data));
  }, [ticker]);

  if (!stock) {
    return <Page>Loading {ticker}...</Page>;
  }

  const summary = stock.summary || {};
  const quant = stock.quant || {};

  return (
    <Page>
      <Header>
        <HeaderText>
          <Eyebrow>Stock Detail</Eyebrow>
          <Title>
            {stock.ticker} · {stock.name}
          </Title>
          <Subtitle>
            Exchange: {summary.exchangeName || "N/A"} · Current price {formatCurrency(stock.price)}
            {" · "}
            Today {formatPercent(stock.changePercent)}
          </Subtitle>
          {stock.source === "mock" ? (
            <Subtitle>
              This ticker is currently using backend fallback data because the live Yahoo feed was
              unavailable for this request.
            </Subtitle>
          ) : null}
        </HeaderText>
      </Header>

      <Card>
        <CardTitle>30-Day Price Chart</CardTitle>
        <StockChart data={stock.historicalPrices} />
      </Card>

      <Grid columns={4}>
        <StatCard
          title="52W High"
          value={formatCurrency(summary.fiftyTwoWeekHigh)}
          label="Server-fetched summary detail"
        />
        <StatCard
          title="52W Low"
          value={formatCurrency(summary.fiftyTwoWeekLow)}
          label="Trailing one-year range floor"
        />
        <StatCard
          title="P/E Ratio"
          value={summary.trailingPE?.toFixed?.(2) ?? "N/A"}
          label="Trailing price to earnings"
        />
        <StatCard
          title="Beta"
          value={summary.beta?.toFixed?.(2) ?? "N/A"}
          label="Sensitivity versus the market"
        />
      </Grid>

      <Grid columns={4}>
        <StatCard
          title="Dividend Yield"
          value={summary.dividendYield != null ? formatPercent(summary.dividendYield) : "N/A"}
          label="Annual dividend yield"
        />
        <StatCard
          title="10-Day MA"
          value={quant.movingAverage10 != null ? formatCurrency(quant.movingAverage10) : "N/A"}
          label="Short-term moving average"
        />
        <StatCard
          title="30-Day MA"
          value={quant.movingAverage30 != null ? formatCurrency(quant.movingAverage30) : "N/A"}
          label="Longer trend anchor"
        />
        <StatCard
          title="Std Dev"
          value={quant.dailyReturnStdDev != null ? formatPercent(quant.dailyReturnStdDev, 3) : "N/A"}
          label="Daily return volatility"
        />
      </Grid>

      <Card>
        <CardTitle>Momentum Signal</CardTitle>
        <MetricValue>{quant.momentum || "N/A"}</MetricValue>
        <MetricLabel>
          Based on the crossover between the latest 10-day and 30-day moving averages.
        </MetricLabel>
      </Card>
    </Page>
  );
}
