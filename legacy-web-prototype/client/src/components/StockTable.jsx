import { Link } from "react-router-dom";
import styled from "styled-components";
import { formatCompactNumber, formatCurrency, formatPercent } from "../lib/formatters.js";

const Wrapper = styled.div`
  overflow: auto;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const HeadCell = styled.th`
  padding: 14px 16px;
  text-align: left;
  color: var(--muted);
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
`;

const Row = styled.tr`
  transition: 180ms ease;

  &:hover {
    background: rgba(107, 188, 255, 0.05);
  }
`;

const Cell = styled.td`
  padding: 16px;
  border-bottom: 1px solid rgba(124, 154, 193, 0.08);
`;

const Change = styled.span`
  color: ${({ value }) => (value >= 0 ? "var(--positive)" : "var(--negative)")};
  font-weight: 700;
`;

export default function StockTable({ stocks, sortKey, sortDirection, onSort }) {
  const headers = [
    { key: "ticker", label: "Ticker" },
    { key: "name", label: "Company" },
    { key: "price", label: "Price" },
    { key: "changePercent", label: "% Change" },
    { key: "volume", label: "Volume" },
    { key: "marketCap", label: "Market Cap" }
  ];

  return (
    <Wrapper>
      <Table>
        <thead>
          <tr>
            {headers.map((header) => (
              <HeadCell key={header.key} onClick={() => onSort(header.key)}>
                {header.label}
                {sortKey === header.key ? ` ${sortDirection === "asc" ? "↑" : "↓"}` : ""}
              </HeadCell>
            ))}
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock) => (
            <Row key={stock.ticker}>
              <Cell>
                <Link to={`/stocks/${stock.ticker}`}>{stock.ticker}</Link>
              </Cell>
              <Cell>{stock.name}</Cell>
              <Cell>{formatCurrency(stock.price)}</Cell>
              <Cell>
                <Change value={stock.changePercent}>{formatPercent(stock.changePercent)}</Change>
              </Cell>
              <Cell>{formatCompactNumber(stock.volume)}</Cell>
              <Cell>{formatCurrency(stock.marketCap, 0)}</Cell>
            </Row>
          ))}
        </tbody>
      </Table>
    </Wrapper>
  );
}
