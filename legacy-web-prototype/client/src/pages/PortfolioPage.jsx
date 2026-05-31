import { useEffect, useState } from "react";
import styled from "styled-components";
import api from "../lib/api.js";
import { formatCurrency, formatPercent } from "../lib/formatters.js";
import PortfolioPie from "../components/PortfolioPie.jsx";
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

const Form = styled.form`
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;

  @media (max-width: 860px) {
    grid-template-columns: 1fr;
  }
`;

const Input = styled.input`
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(6, 14, 25, 0.8);
  color: var(--text);
`;

const Button = styled.button`
  padding: 14px 16px;
  border: 0;
  border-radius: 16px;
  color: #08111f;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  font-weight: 800;
  cursor: pointer;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const Row = styled.tr`
  border-bottom: 1px solid rgba(124, 154, 193, 0.08);
`;

const Cell = styled.td`
  padding: 14px 10px;
`;

const Change = styled.span`
  color: ${({ value }) => (value >= 0 ? "var(--positive)" : "var(--negative)")};
  font-weight: 700;
`;

function SummaryCard({ title, value, label }) {
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      <MetricValue>{value}</MetricValue>
      <MetricLabel>{label}</MetricLabel>
    </Card>
  );
}

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState({ holdings: [], totals: { marketValue: 0, gainLoss: 0 } });
  const [form, setForm] = useState({ ticker: "", shares: "", buyPrice: "" });

  async function loadPortfolio() {
    const response = await api.get("/portfolio");
    setPortfolio(response.data);
  }

  useEffect(() => {
    loadPortfolio();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const response = await api.post("/portfolio", {
      ticker: form.ticker,
      shares: Number(form.shares),
      buyPrice: Number(form.buyPrice)
    });

    setPortfolio(response.data);
    setForm({ ticker: "", shares: "", buyPrice: "" });
  }

  return (
    <Page>
      <Header>
        <HeaderText>
          <Eyebrow>Page 3</Eyebrow>
          <Title>Portfolio Tracker</Title>
          <Subtitle>
            Add holdings to local storage, then let the backend calculate current value, gain/loss,
            and sector allocation from live quotes.
          </Subtitle>
        </HeaderText>
      </Header>

      <Grid columns={3}>
        <SummaryCard
          title="Portfolio Value"
          value={formatCurrency(portfolio.totals.marketValue)}
          label="Marked to live market prices"
        />
        <SummaryCard
          title="Total Gain / Loss"
          value={formatCurrency(portfolio.totals.gainLoss)}
          label="Unrealized P&L across all holdings"
        />
        <SummaryCard
          title="Holdings"
          value={String(portfolio.holdings.length)}
          label="Tracked positions in your local book"
        />
      </Grid>

      <Card>
        <CardTitle>Add Position</CardTitle>
        <Form onSubmit={handleSubmit}>
          <Input
            placeholder="Ticker"
            value={form.ticker}
            onChange={(event) => setForm((current) => ({ ...current, ticker: event.target.value.toUpperCase() }))}
          />
          <Input
            placeholder="Shares"
            type="number"
            step="0.01"
            value={form.shares}
            onChange={(event) => setForm((current) => ({ ...current, shares: event.target.value }))}
          />
          <Input
            placeholder="Buy price"
            type="number"
            step="0.01"
            value={form.buyPrice}
            onChange={(event) => setForm((current) => ({ ...current, buyPrice: event.target.value }))}
          />
          <Button type="submit">Save Entry</Button>
        </Form>
      </Card>

      <Grid columns={2}>
        <Card>
          <CardTitle>Portfolio Allocation by Sector</CardTitle>
          <PortfolioPie holdings={portfolio.holdings} />
        </Card>

        <Card>
          <CardTitle>Holdings Breakdown</CardTitle>
          <div style={{ overflow: "auto" }}>
            <Table>
              <thead>
                <tr>
                  <Cell>Ticker</Cell>
                  <Cell>Shares</Cell>
                  <Cell>Current Value</Cell>
                  <Cell>Gain/Loss</Cell>
                  <Cell>Gain/Loss %</Cell>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((holding) => (
                  <Row key={holding.id}>
                    <Cell>{holding.ticker}</Cell>
                    <Cell>{holding.shares}</Cell>
                    <Cell>{formatCurrency(holding.currentValue)}</Cell>
                    <Cell>
                      <Change value={holding.gainLoss}>{formatCurrency(holding.gainLoss)}</Change>
                    </Cell>
                    <Cell>
                      <Change value={holding.gainLossPercent}>
                        {formatPercent(holding.gainLossPercent)}
                      </Change>
                    </Cell>
                  </Row>
                ))}
              </tbody>
            </Table>
          </div>
        </Card>
      </Grid>
    </Page>
  );
}
