from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd
import requests

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.io import read_frame, write_frame


FMP_BASE = "https://financialmodelingprep.com/stable"


def _fmp_get(endpoint: str, symbol: str, api_key: str, limit: int = 5) -> list[dict]:
    params = {"symbol": symbol, "period": "quarter", "limit": limit, "apikey": api_key}
    for attempt in range(4):
        response = requests.get(f"{FMP_BASE}/{endpoint}", params=params, timeout=45)
        if response.status_code == 200:
            payload = response.json()
            return payload if isinstance(payload, list) else []
        time.sleep(1.5 * (attempt + 1))
    response.raise_for_status()
    return []


def _records_by_date(records: list[dict]) -> dict[str, dict]:
    return {str(row.get("date")): row for row in records if row.get("date")}


def build_fmp_fundamental_panel(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise RuntimeError("FMP_API_KEY is not set.")
    config.ensure_dirs()
    rows = []
    for ticker in config.tickers:
        try:
            income = _records_by_date(_fmp_get("income-statement", ticker, api_key))
            balance = _records_by_date(_fmp_get("balance-sheet-statement", ticker, api_key))
            cashflow = _records_by_date(_fmp_get("cash-flow-statement", ticker, api_key))
            for date, inc in income.items():
                bal = balance.get(date, {})
                cf = cashflow.get(date, {})
                revenue = inc.get("revenue")
                net_income = inc.get("netIncome")
                assets = bal.get("totalAssets")
                debt = bal.get("totalDebt")
                equity = bal.get("totalStockholdersEquity")
                fcf = cf.get("freeCashFlow")
                rows.append(
                    {
                        "ticker": ticker,
                        "period_end": pd.to_datetime(date),
                        "date": pd.to_datetime(inc.get("acceptedDate") or inc.get("filingDate") or date),
                        "filing_date": pd.to_datetime(inc.get("filingDate") or date),
                        "revenue": revenue,
                        "net_income": net_income,
                        "ebitda": inc.get("ebitda"),
                        "free_cash_flow": fcf,
                        "operating_cash_flow": cf.get("operatingCashFlow"),
                        "total_assets": assets,
                        "total_debt": debt,
                        "stockholder_equity": equity,
                        "net_margin": net_income / revenue if revenue and revenue > 0 else np.nan,
                        "fcf_margin": fcf / revenue if revenue and revenue > 0 else np.nan,
                        "roa": net_income / assets if assets and assets > 0 else np.nan,
                        "roe": net_income / equity if equity and equity > 0 else np.nan,
                        "debt_to_assets": debt / assets if assets and assets > 0 else np.nan,
                    }
                )
        except Exception as error:
            rows.append({"ticker": ticker, "error": str(error)})
    panel = pd.DataFrame(rows).sort_values(["ticker", "date"])
    for column in ("revenue", "net_income"):
        panel[f"{column}_yoy"] = panel.groupby("ticker")[column].pct_change(4)
    panel = panel.rename(columns={"revenue_yoy": "revenue_yoy", "net_income_yoy": "net_income_yoy"})
    write_frame(panel, config.processed_dir / "fmp_fundamental_panel.csv")
    return panel


def load_fmp_fundamental_panel(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    path = config.processed_dir / "fmp_fundamental_panel.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date", "period_end", "filing_date"])
    return build_fmp_fundamental_panel(config)
