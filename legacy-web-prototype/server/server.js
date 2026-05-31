import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { trackedStocks } from "./data/sp500.js";
import { appendPortfolioEntry, readPortfolioEntries } from "./utils/storage.js";
import {
  enrichPortfolioEntries,
  fetchStockDetail,
  fetchTrackedStocks
} from "./services/marketDataService.js";
import { getChatResponse } from "./services/chatService.js";

dotenv.config();

const app = express();
const port = process.env.PORT || 4000;

app.use(
  cors({
    origin: process.env.CLIENT_URL || "http://localhost:5173"
  })
);
app.use(express.json());

app.get("/api/health", (_request, response) => {
  response.json({ ok: true, trackedTickers: trackedStocks.length });
});

app.get("/api/stocks", async (_request, response) => {
  try {
    const stocks = await fetchTrackedStocks();
    response.json({ stocks, updatedAt: new Date().toISOString() });
  } catch (error) {
    response.status(500).json({
      error: "Unable to fetch stock data.",
      details: error.message
    });
  }
});

app.get("/api/stock/:ticker", async (request, response) => {
  try {
    const detail = await fetchStockDetail(request.params.ticker);
    response.json(detail);
  } catch (error) {
    response.status(500).json({
      error: `Unable to fetch detail for ${request.params.ticker}.`,
      details: error.message
    });
  }
});

app.get("/api/portfolio", async (_request, response) => {
  try {
    const entries = await readPortfolioEntries();
    const portfolio = await enrichPortfolioEntries(entries);
    response.json(portfolio);
  } catch (error) {
    response.status(500).json({
      error: "Unable to load the portfolio.",
      details: error.message
    });
  }
});

app.post("/api/portfolio", async (request, response) => {
  const { ticker, shares, buyPrice } = request.body ?? {};

  if (!ticker || !Number.isFinite(Number(shares)) || !Number.isFinite(Number(buyPrice))) {
    response.status(400).json({
      error: "ticker, shares, and buyPrice are required."
    });
    return;
  }

  const entry = {
    id: crypto.randomUUID(),
    ticker: ticker.toUpperCase(),
    shares: Number(shares),
    buyPrice: Number(buyPrice),
    createdAt: new Date().toISOString()
  };

  try {
    await appendPortfolioEntry(entry);
    const entries = await readPortfolioEntries();
    const portfolio = await enrichPortfolioEntries(entries);
    response.status(201).json(portfolio);
  } catch (error) {
    response.status(500).json({
      error: "Unable to save the portfolio entry.",
      details: error.message
    });
  }
});

app.post("/api/chat", (request, response) => {
  const message = String(request.body?.message || "").trim();

  if (!message) {
    response.status(400).json({ error: "message is required." });
    return;
  }

  response.json({
    message: getChatResponse(message)
  });
});

app.listen(port, () => {
  console.log(`Quant Market server listening on port ${port}`);
});
