import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";

const ChatPage = lazy(() => import("./pages/ChatPage.jsx"));
const MarketOverviewPage = lazy(() => import("./pages/MarketOverviewPage.jsx"));
const PortfolioPage = lazy(() => import("./pages/PortfolioPage.jsx"));
const StockDetailPage = lazy(() => import("./pages/StockDetailPage.jsx"));

export default function App() {
  return (
    <Suspense fallback={<div style={{ padding: 24 }}>Loading...</div>}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<MarketOverviewPage />} />
          <Route path="stocks/:ticker" element={<StockDetailPage />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
