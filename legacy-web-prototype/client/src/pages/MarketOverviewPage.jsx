import { useEffect, useMemo, useState } from "react";
import styled from "styled-components";
import api from "../lib/api.js";
import MetricCards from "../components/MetricCards.jsx";
import StockTable from "../components/StockTable.jsx";
import { Card, Header, HeaderText, Page, Subtitle, Title, Eyebrow, CardTitle } from "../components/PagePrimitives.jsx";

const Search = styled.input`
  width: min(320px, 100%);
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(6, 14, 25, 0.8);
  color: var(--text);
`;

export default function MarketOverviewPage() {
  const [stocks, setStocks] = useState([]);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("marketCap");
  const [sortDirection, setSortDirection] = useState("desc");

  useEffect(() => {
    api.get("/stocks").then((response) => setStocks(response.data.stocks));
  }, []);

  const filteredStocks = useMemo(() => {
    const query = search.toLowerCase();
    const next = stocks.filter(
      (stock) =>
        stock.ticker.toLowerCase().includes(query) || stock.name.toLowerCase().includes(query)
    );

    return [...next].sort((left, right) => {
      const leftValue = left[sortKey];
      const rightValue = right[sortKey];

      if (typeof leftValue === "string") {
        return sortDirection === "asc"
          ? leftValue.localeCompare(rightValue)
          : rightValue.localeCompare(leftValue);
      }

      return sortDirection === "asc" ? leftValue - rightValue : rightValue - leftValue;
    });
  }, [search, sortDirection, sortKey, stocks]);

  const usesFallbackData = stocks.some((stock) => stock.source === "mock");

  function handleSort(nextSortKey) {
    if (sortKey === nextSortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }

    setSortKey(nextSortKey);
    setSortDirection(nextSortKey === "ticker" || nextSortKey === "name" ? "asc" : "desc");
  }

  return (
    <Page>
      <Header>
        <HeaderText>
          <Eyebrow>Page 1</Eyebrow>
          <Title>Market Overview</Title>
          <Subtitle>
            Browse a live watchlist of large-cap S&P 500 names, sort the tape, and drill into any
            ticker for charting and server-side quant analytics.
          </Subtitle>
          {usesFallbackData ? (
            <Subtitle>
              Yahoo Finance is throttling this environment, so the backend is serving deterministic
              demo market data for the watchlist while keeping the same API shape.
            </Subtitle>
          ) : null}
        </HeaderText>

        <Search
          placeholder="Search ticker or company"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </Header>

      <MetricCards stocks={stocks} />

      <Card>
        <CardTitle>Live Stock Table</CardTitle>
        <StockTable
          stocks={filteredStocks}
          sortKey={sortKey}
          sortDirection={sortDirection}
          onSort={handleSort}
        />
      </Card>
    </Page>
  );
}
