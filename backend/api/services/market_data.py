from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from importlib import import_module
from typing import Any

from ..models import (
    CompanyProfileResponse,
    EarningsResponse,
    MarketNewsResponse,
    MarketProviderCapability,
    MarketProviderStatusResponse,
    MarketQuoteResponse,
    MarketSearchResponse,
    OptionsAvailabilityResponse,
    OptionsContextResponse,
)
from ..settings import settings


READY_FIELDS = ["ticker", "provider_status", "quote", "company_profile", "earnings_calendar", "stock_news"]
OPTIONS_REFERENCE_FIELDS = ["option_contract_reference", "expiration_dates", "strike_ladder", "contract_symbols"]
OPTIONS_LIVE_PENDING_FIELDS = ["live_premium", "bid_ask", "implied_volatility", "greeks", "liquidity_snapshot", "breakeven_from_real_premium"]
PENDING_FIELDS = ["option_chain", "implied_volatility", "expiration_dates", "live_premium", "breakeven_from_real_premium"]
FMP_STABLE_BASE = "https://financialmodelingprep.com/stable"
YAHOO_RSS_BASE = "https://feeds.finance.yahoo.com/rss/2.0/headline"
ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
_FMP_CACHE: dict[str, tuple[float, Any]] = {}
_POLYGON_CACHE: dict[str, tuple[float, Any]] = {}
_YFINANCE_IMPORT_ERROR: str | None | bool = False
FALLBACK_SYMBOLS = [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "exchange": "NYSE Arca", "sector": "ETF"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "exchange": "NASDAQ", "sector": "ETF"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "exchange": "NYSE Arca", "sector": "ETF"},
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "AMD", "name": "Advanced Micro Devices Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ", "sector": "Consumer"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. Class A", "exchange": "NASDAQ", "sector": "Communication"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "exchange": "NASDAQ", "sector": "Consumer"},
    {"symbol": "PLTR", "name": "Palantir Technologies Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "AVGO", "name": "Broadcom Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "ARM", "name": "Arm Holdings plc", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "SMCI", "name": "Super Micro Computer Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "MU", "name": "Micron Technology Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "QCOM", "name": "Qualcomm Incorporated", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "ORCL", "name": "Oracle Corporation", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "CRM", "name": "Salesforce Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "SNOW", "name": "Snowflake Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "MDB", "name": "MongoDB Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "NET", "name": "Cloudflare Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "CRWD", "name": "CrowdStrike Holdings Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "DDOG", "name": "Datadog Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "OKTA", "name": "Okta Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "TTD", "name": "The Trade Desk Inc.", "exchange": "NASDAQ", "sector": "Communication"},
    {"symbol": "SHOP", "name": "Shopify Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "UBER", "name": "Uber Technologies Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "ABNB", "name": "Airbnb Inc.", "exchange": "NASDAQ", "sector": "Consumer"},
    {"symbol": "RDDT", "name": "Reddit Inc.", "exchange": "NYSE", "sector": "Communication"},
    {"symbol": "RBLX", "name": "Roblox Corporation", "exchange": "NYSE", "sector": "Communication"},
    {"symbol": "ROKU", "name": "Roku Inc.", "exchange": "NASDAQ", "sector": "Communication"},
    {"symbol": "DIS", "name": "The Walt Disney Company", "exchange": "NYSE", "sector": "Communication"},
    {"symbol": "NFLX", "name": "Netflix Inc.", "exchange": "NASDAQ", "sector": "Communication"},
    {"symbol": "HOOD", "name": "Robinhood Markets Inc.", "exchange": "NASDAQ", "sector": "Finance"},
    {"symbol": "COIN", "name": "Coinbase Global Inc.", "exchange": "NASDAQ", "sector": "Finance"},
    {"symbol": "SOFI", "name": "SoFi Technologies Inc.", "exchange": "NASDAQ", "sector": "Finance"},
    {"symbol": "AFRM", "name": "Affirm Holdings Inc.", "exchange": "NASDAQ", "sector": "Finance"},
    {"symbol": "UPST", "name": "Upstart Holdings Inc.", "exchange": "NASDAQ", "sector": "Finance"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "exchange": "NYSE", "sector": "Finance"},
    {"symbol": "BAC", "name": "Bank of America Corporation", "exchange": "NYSE", "sector": "Finance"},
    {"symbol": "GS", "name": "The Goldman Sachs Group Inc.", "exchange": "NYSE", "sector": "Finance"},
    {"symbol": "V", "name": "Visa Inc.", "exchange": "NYSE", "sector": "Finance"},
    {"symbol": "MA", "name": "Mastercard Incorporated", "exchange": "NYSE", "sector": "Finance"},
    {"symbol": "LLY", "name": "Eli Lilly and Company", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "UNH", "name": "UnitedHealth Group Incorporated", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "MRNA", "name": "Moderna Inc.", "exchange": "NASDAQ", "sector": "Healthcare"},
    {"symbol": "HIMS", "name": "Hims & Hers Health Inc.", "exchange": "NYSE", "sector": "Healthcare"},
    {"symbol": "VKTX", "name": "Viking Therapeutics Inc.", "exchange": "NASDAQ", "sector": "Healthcare"},
    {"symbol": "XOM", "name": "Exxon Mobil Corporation", "exchange": "NYSE", "sector": "Energy"},
    {"symbol": "CVX", "name": "Chevron Corporation", "exchange": "NYSE", "sector": "Energy"},
    {"symbol": "OXY", "name": "Occidental Petroleum Corporation", "exchange": "NYSE", "sector": "Energy"},
    {"symbol": "RIVN", "name": "Rivian Automotive Inc.", "exchange": "NASDAQ", "sector": "Consumer"},
    {"symbol": "LCID", "name": "Lucid Group Inc.", "exchange": "NASDAQ", "sector": "Consumer"},
    {"symbol": "NIO", "name": "NIO Inc.", "exchange": "NYSE", "sector": "Consumer"},
    {"symbol": "ACHR", "name": "Archer Aviation Inc.", "exchange": "NYSE", "sector": "Industrials"},
    {"symbol": "JOBY", "name": "Joby Aviation Inc.", "exchange": "NYSE", "sector": "Industrials"},
    {"symbol": "RKLB", "name": "Rocket Lab USA Inc.", "exchange": "NASDAQ", "sector": "Industrials"},
    {"symbol": "LUNR", "name": "Intuitive Machines Inc.", "exchange": "NASDAQ", "sector": "Industrials"},
    {"symbol": "ASTS", "name": "AST SpaceMobile Inc.", "exchange": "NASDAQ", "sector": "Communication"},
    {"symbol": "IONQ", "name": "IonQ Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "QBTS", "name": "D-Wave Quantum Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "RGTI", "name": "Rigetti Computing Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "SOUN", "name": "SoundHound AI Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "BBAI", "name": "BigBear.ai Holdings Inc.", "exchange": "NYSE", "sector": "Technology"},
    {"symbol": "NBIS", "name": "Nebius Group N.V.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "RXRX", "name": "Recursion Pharmaceuticals Inc.", "exchange": "NASDAQ", "sector": "Healthcare"},
    {"symbol": "TEM", "name": "Tempus AI Inc.", "exchange": "NASDAQ", "sector": "Healthcare"},
    {"symbol": "SMR", "name": "NuScale Power Corporation", "exchange": "NYSE", "sector": "Energy"},
    {"symbol": "OKLO", "name": "Oklo Inc.", "exchange": "NYSE", "sector": "Energy"},
    {"symbol": "MSTR", "name": "Strategy Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"symbol": "MARA", "name": "MARA Holdings Inc.", "exchange": "NASDAQ", "sector": "Crypto Equity"},
    {"symbol": "RIOT", "name": "Riot Platforms Inc.", "exchange": "NASDAQ", "sector": "Crypto Equity"},
    {"symbol": "GME", "name": "GameStop Corp.", "exchange": "NYSE", "sector": "Consumer"},
    {"symbol": "AMC", "name": "AMC Entertainment Holdings Inc.", "exchange": "NYSE", "sector": "Consumer"},
    {"symbol": "BRK.B", "name": "Berkshire Hathaway Inc. Class B", "exchange": "NYSE", "sector": "Finance"},
]


async def market_quote(ticker: str) -> MarketQuoteResponse:
    symbol = clean_symbol(ticker)
    if fmp_enabled():
        try:
            rows = fmp_get("/quote", {"symbol": symbol})
            row = first_dict(rows)
            if row:
                return MarketQuoteResponse(
                    ticker=symbol,
                    status="ok",
                    provider="financialmodelingprep",
                    name=str(row.get("name") or symbol),
                    price=number_or_none(row.get("price")),
                    change=number_or_none(row.get("change")),
                    changePercentage=number_or_none(row.get("changePercentage")),
                    volume=number_or_none(row.get("volume")),
                    dayLow=number_or_none(row.get("dayLow")),
                    dayHigh=number_or_none(row.get("dayHigh")),
                    yearLow=number_or_none(row.get("yearLow")),
                    yearHigh=number_or_none(row.get("yearHigh")),
                    marketCap=number_or_none(row.get("marketCap")),
                )
        except Exception:
            pass
    if alpha_enabled():
        try:
            row = alpha_global_quote(symbol)
            if row:
                pct_raw = str(row.get("10. change percent") or "").replace("%", "")
                return MarketQuoteResponse(
                    ticker=symbol,
                    status="ok",
                    provider="alpha_vantage",
                    name=symbol,
                    price=number_or_none(row.get("05. price")),
                    change=number_or_none(row.get("09. change")),
                    changePercentage=number_or_none(pct_raw),
                    volume=number_or_none(row.get("06. volume")),
                    dayLow=number_or_none(row.get("04. low")),
                    dayHigh=number_or_none(row.get("03. high")),
                    message="Alpha Vantage stock quote fallback. This is stock-level data, not an options chain.",
                )
        except Exception as exc:
            return MarketQuoteResponse(ticker=symbol, status="unavailable", provider="alpha_vantage", message=short_error(exc))
    return MarketQuoteResponse(
        ticker=symbol,
        status="needs_provider_key",
        provider=settings.market_data_provider or "disabled",
        message="No stock quote provider is configured. Add FMP or Alpha Vantage for stock-level quotes.",
    )


async def company_profile(ticker: str) -> CompanyProfileResponse:
    symbol = clean_symbol(ticker)
    if not fmp_enabled():
        return CompanyProfileResponse(ticker=symbol, status="needs_provider_key", provider=settings.market_data_provider or "disabled")
    try:
        rows = fmp_get("/profile", {"symbol": symbol})
        row = first_dict(rows)
        return CompanyProfileResponse(
            ticker=symbol,
            status="ok",
            provider="financialmodelingprep",
            companyName=str(row.get("companyName") or row.get("company_name") or row.get("name") or symbol),
            sector=str(row.get("sector") or ""),
            industry=str(row.get("industry") or ""),
            beta=number_or_none(row.get("beta")),
            marketCap=number_or_none(row.get("marketCap")),
            website=str(row.get("website") or ""),
            image=str(row.get("image") or ""),
            description=str(row.get("description") or "")[:600],
        )
    except Exception as exc:
        return CompanyProfileResponse(ticker=symbol, status="unavailable", provider="financialmodelingprep", message=short_error(exc))


async def stock_news(ticker: str) -> MarketNewsResponse:
    symbol = clean_symbol(ticker)
    if fmp_enabled():
        try:
            rows = fmp_get("/news/stock", {"symbols": symbol, "limit": "5"})
            items = [normalize_fmp_news_item(row) for row in rows[:5] if isinstance(row, dict)]
            if items:
                return MarketNewsResponse(ticker=symbol, status="ok", provider="financialmodelingprep", items=items)
        except Exception:
            pass
    try:
        items = yahoo_rss_news(symbol)
        return MarketNewsResponse(
            ticker=symbol,
            status="ok" if items else "empty",
            provider="yahoo_finance_rss",
            items=items,
            message="FMP stock news is not available on this key, so RiskWise is using Yahoo Finance RSS headlines.",
        )
    except Exception as exc:
        return MarketNewsResponse(ticker=symbol, status="unavailable", provider="yahoo_finance_rss", message=short_error(exc))


async def market_search(query: str) -> MarketSearchResponse:
    clean = query.strip()[:40]
    if len(clean) < 1:
        return MarketSearchResponse(query=clean, status="empty", provider=settings.market_data_provider or "disabled", items=[])
    fallback_items = local_symbol_search(clean)
    polygon_items = polygon_ticker_search(clean) if polygon_enabled() else []
    if not fmp_enabled():
        items = rank_search_items(clean, [*fallback_items, *polygon_items])
        return MarketSearchResponse(
            query=clean,
            status="ok" if items else "needs_provider_key",
            provider="massive_polygon_reference+local_symbol_index" if polygon_items else "local_symbol_index",
            items=items,
            message="FMP is not available, so search is using Massive/Polygon ticker reference plus the built-in symbol index.",
        )
    try:
        rows = []
        paths = ["/search-symbol", "/search-name"] if clean.isalnum() else ["/search-name", "/search-symbol"]
        for path in paths:
            for exchange in ("", "NASDAQ", "NYSE", "AMEX"):
                try:
                    params = {"query": clean, "limit": "10"}
                    if exchange:
                        params["exchange"] = exchange
                    next_rows = fmp_get(path, params)
                except Exception:
                    next_rows = []
                if isinstance(next_rows, list):
                    rows.extend(next_rows)
        items = rank_search_items(clean, [*fallback_items, *polygon_items, *rows])
        if not items and looks_like_symbol(clean):
            symbol = clean_symbol(clean)
            items.append({"symbol": symbol, "name": f"{symbol} typed ticker", "exchange": "Verify quote", "sector": "Unverified"})
        return MarketSearchResponse(
            query=clean,
            status="ok" if items else "empty",
            provider="financialmodelingprep+massive_polygon_reference+local_symbol_index" if polygon_items else "financialmodelingprep+local_symbol_index",
            items=items,
            message="" if rows or polygon_items else "Provider search returned no rows or was rate-limited, so RiskWise included local symbol matches.",
        )
    except Exception as exc:
        return MarketSearchResponse(
            query=clean,
            status="local_fallback" if fallback_items else "unavailable",
            provider="local_symbol_index",
            items=fallback_items,
            message=short_error(exc),
        )


async def earnings_calendar(ticker: str) -> EarningsResponse:
    symbol = clean_symbol(ticker)
    if not fmp_enabled():
        return EarningsResponse(ticker=symbol, status="needs_provider_key", provider=settings.market_data_provider or "disabled")
    try:
        rows = fmp_get("/earnings", {"symbol": symbol, "limit": "5"})
        items = [
            {
                "date": str(row.get("date") or ""),
                "epsActual": number_or_none(row.get("epsActual")),
                "epsEstimated": number_or_none(row.get("epsEstimated")),
                "revenueActual": number_or_none(row.get("revenueActual")),
                "revenueEstimated": number_or_none(row.get("revenueEstimated")),
            }
            for row in rows[:8]
            if isinstance(row, dict)
        ]
        return EarningsResponse(ticker=symbol, status="ok", provider="financialmodelingprep", items=items)
    except Exception as exc:
        return EarningsResponse(ticker=symbol, status="unavailable", provider="financialmodelingprep", message=short_error(exc))


async def options_context(ticker: str) -> OptionsContextResponse:
    symbol = clean_symbol(ticker)
    provider = settings.market_data_provider or "disabled"
    if yfinance_enabled():
        return OptionsContextResponse(
            ticker=symbol,
            status="delayed_options_enabled",
            provider="yfinance_delayed",
            fields_ready=READY_FIELDS + ["delayed_option_chain", "expiration_dates", "delayed_bid_ask", "delayed_implied_volatility", "delayed_volume_open_interest"],
            fields_pending=["provider_reported_greeks", "real_time_opra_snapshot"],
            message=(
                "Delayed yfinance options are enabled. RiskWise can try to read expirations, bid/ask, IV, volume, and open interest, "
                "but these are delayed/free-source values, not live OPRA data. Greeks are estimated only when enough inputs exist."
            ),
        )
    if polygon_enabled():
        expirations, _contracts = polygon_option_reference(symbol, limit=10)
        status = "options_reference_ready" if expirations else "options_provider_configured"
        return OptionsContextResponse(
            ticker=symbol,
            status=status,
            provider="massive_polygon_reference",
            fields_ready=READY_FIELDS + OPTIONS_REFERENCE_FIELDS,
            fields_pending=OPTIONS_LIVE_PENDING_FIELDS,
            message=(
                "Massive/Polygon option-contract reference is enabled, so RiskWise can attach real expirations, strikes, "
                "and contract symbols. Your current key does not expose live option snapshots in this environment, so live "
                "premium, IV, Greeks, bid/ask, volume, and open interest still stay marked as missing instead of being guessed."
            ),
        )
    if fmp_enabled():
        return OptionsContextResponse(
            ticker=symbol,
            status="partial_market_data",
            provider="financialmodelingprep",
            fields_ready=READY_FIELDS,
            fields_pending=PENDING_FIELDS,
            message=(
                "FMP quote, company profile, and earnings calendar data are enabled. Stock headlines use Yahoo Finance RSS "
                "when FMP news is unavailable. Live option chains, IV, Greeks, and real premiums still require Tradier or Polygon."
            ),
        )

    return OptionsContextResponse(
        ticker=symbol,
        status="needs_provider_key",
        provider=provider,
        fields_ready=["ticker", "provider_status"],
        fields_pending=READY_FIELDS + PENDING_FIELDS,
        message=(
            "RiskWise is ready to receive stock-level market data, but no enabled provider is active for this environment. "
            "Live option chains, IV, Greeks, and real premiums still require a dedicated options feed such as Tradier or Polygon."
        ),
    )


async def options_expirations(ticker: str) -> OptionsAvailabilityResponse:
    symbol = clean_symbol(ticker)
    quote = await market_quote(symbol)
    if polygon_enabled():
        expirations, contracts = polygon_option_reference(symbol, limit=1000)
        if expirations:
            return OptionsAvailabilityResponse(
                ticker=symbol,
                status="reference_expirations_ready",
                provider="massive_polygon_reference",
                expirations=expirations[:16],
                contracts=contracts[:30],
                quote=quote.model_dump(),
                message=(
                    "These are real option expiration dates from the Massive/Polygon contract reference feed. "
                    "Live premium, IV, Greeks, and liquidity still require an option snapshot entitlement."
                ),
            )
    if yfinance_enabled():
        expirations, contracts = yfinance_option_chain(symbol, limit=30)
        if expirations:
            return OptionsAvailabilityResponse(
                ticker=symbol,
                status="delayed_expirations_ready",
                provider="yfinance_delayed",
                expirations=expirations[:16],
                contracts=contracts[:30],
                quote=quote.model_dump(),
                message="Delayed yfinance expirations are available. Treat them as delayed reference data, not live OPRA.",
            )
    return OptionsAvailabilityResponse(
        ticker=symbol,
        status="estimated_calendar",
        provider="riskwise_standard_monthly_calendar",
        expirations=standard_monthly_expirations(),
        quote=quote.model_dump(),
        message=(
            "RiskWise can show standard monthly option expiration dates for planning, but these are calendar estimates. "
            "A dedicated options feed is still required before treating expirations or contracts as live market data."
        ),
    )


async def options_chain(ticker: str, expiration: str | None = None) -> OptionsAvailabilityResponse:
    symbol = clean_symbol(ticker)
    quote, profile, earnings = await gather_contract_context(symbol)
    if polygon_enabled():
        expirations, contracts = polygon_option_reference(symbol, expiration=expiration, limit=250)
        contracts = enrich_reference_contracts(contracts, quote.price)
        status = "reference_chain_ready" if contracts else "reference_chain_empty"
        return OptionsAvailabilityResponse(
            ticker=symbol,
            status=status,
            provider="massive_polygon_reference",
            expirations=expirations[:16] if expirations else standard_monthly_expirations(),
            contracts=contracts[:120],
            quote=quote.model_dump(),
            profile=profile.model_dump(),
            earnings=[item.model_dump() for item in earnings.items],
            message=(
                "RiskWise attached real option contract references from Massive/Polygon. This is not a live quote chain: "
                "premium, bid/ask, IV, Greeks, volume, and open interest are unavailable on the current entitlement and remain user-confirmed fields."
            ),
        )
    if yfinance_enabled():
        _ = yfinance_option_chain(symbol, expiration=expiration, limit=140)
    return OptionsAvailabilityResponse(
        ticker=symbol,
        status="requires_options_provider",
        provider="tradier_or_polygon_required",
        expirations=standard_monthly_expirations(),
        contracts=[],
        quote=quote.model_dump(),
        profile=profile.model_dump(),
        earnings=[item.model_dump() for item in earnings.items],
        message=(
            "Live option chains need a dedicated options provider such as Tradier or Polygon. "
            "Quote, company profile, earnings context, and estimated monthly expirations are attached for review."
        ),
    )


async def options_contract_context(
    ticker: str,
    expiration: str | None = None,
    strike: float | None = None,
    option_side: str | None = None,
) -> OptionsAvailabilityResponse:
    symbol = clean_symbol(ticker)
    quote, profile, earnings = await gather_contract_context(symbol)
    option_type = normalize_side(option_side)
    selected_contract: dict[str, Any] = {}
    expiration_rows: list[str] = []
    contracts: list[dict[str, Any]] = []
    if polygon_enabled():
        expiration_rows, contracts = polygon_option_reference(symbol, expiration=expiration, option_type=option_type, limit=250)
        contracts = enrich_reference_contracts(contracts, quote.price)
        selected_contract = choose_contract_reference(contracts, expiration, strike, option_type)
    elif yfinance_enabled():
        expiration_rows, contracts = yfinance_option_chain(symbol, expiration=expiration, option_side=option_type, limit=120)
        contracts = attach_estimated_greeks(contracts, quote.price)
        selected_contract = choose_yfinance_contract(contracts, expiration, strike, option_type)
    selected: dict[str, Any] = {
        "symbol": symbol,
        "expiration": expiration or "",
        "strike": strike,
        "optionSide": option_type,
        "source": str(selected_contract.get("source") or ("polygon_reference_plus_underlying_context" if selected_contract else "user_input_plus_underlying_context")),
        "underlyingPrice": quote.price,
        "providerHasLiveOptionChain": bool(selected_contract),
        "providerHasLivePremium": False,
    }
    if selected_contract:
        selected.update(selected_contract)
        selected["strike"] = selected_contract.get("strike_price") or selected.get("strike")
        selected["expiration"] = selected_contract.get("expiration_date") or selected.get("expiration")
    if quote.price and strike:
        moneyness = round((strike - quote.price) / quote.price * 100, 2)
        selected["moneynessPct"] = moneyness
        selected["moneynessLabel"] = moneyness_label(moneyness, selected["optionSide"])
    return OptionsAvailabilityResponse(
        ticker=symbol,
        status="reference_contract_matched" if selected_contract else "partial_contract_context",
        provider=(
            "massive_polygon_reference+financialmodelingprep"
            if polygon_enabled()
            else "yfinance_delayed+financialmodelingprep"
            if yfinance_enabled()
            else "financialmodelingprep+riskwise_estimator"
        ),
        expirations=expiration_rows[:16] if expiration_rows else standard_monthly_expirations(),
        contracts=contracts[:30],
        selected=selected,
        quote=quote.model_dump(),
        profile=profile.model_dump(),
        earnings=[item.model_dump() for item in earnings.items],
        message=(
            "RiskWise matched the requested contract against real Massive/Polygon option-reference data, but live premium, IV, "
            "Greeks, bid/ask, volume, and open interest are not available on the current entitlement."
            if selected_contract
            else "RiskWise attached real stock quote/profile/earnings context, but live premium, IV, Greeks, bid/ask, volume, and open interest still require an options snapshot entitlement."
        ),
    )


async def gather_contract_context(symbol: str):
    quote = await market_quote(symbol)
    profile = await company_profile(symbol)
    earnings = await earnings_calendar(symbol)
    return quote, profile, earnings


def market_provider_status() -> MarketProviderStatusResponse:
    yfinance_error = yfinance_import_error() if settings.enable_yfinance_options else ""
    yfinance_status = "active" if yfinance_enabled() else "dependency_error" if yfinance_error else "disabled"
    yfinance_missing = [] if yfinance_enabled() else [yfinance_error or "Enable delayed yfinance options fallback"]
    capabilities = [
        MarketProviderCapability(
            provider="financialmodelingprep",
            configured=bool(settings.fmp_api_key),
            status="active" if fmp_enabled() else "missing_key_or_disabled",
            fields=["quote", "company_profile", "stock_news", "earnings"],
            missing=[] if fmp_enabled() else ["FMP credentials or fmp/hybrid market mode"],
            notes="Best current stock-level source for RiskWise. Free-plan quota can be limited.",
        ),
        MarketProviderCapability(
            provider="massive_polygon_reference",
            configured=bool(settings.polygon_api_key),
            status="active" if polygon_enabled() else "missing_key_or_disabled",
            fields=["option_contract_reference", "expiration_dates", "strike_ladder", "contract_symbols"],
            missing=[] if polygon_enabled() else ["Massive/Polygon credentials or massive/polygon/hybrid market mode"],
            notes="Reference contracts only unless the key has live snapshot entitlements.",
        ),
        MarketProviderCapability(
            provider="yfinance_delayed",
            configured=settings.enable_yfinance_options,
            status=yfinance_status,
            fields=["delayed_expirations", "delayed_chain", "bid_ask", "implied_volatility", "volume", "open_interest"],
            missing=yfinance_missing,
            notes="No-key delayed fallback. Useful for MVP context, not live OPRA redistribution.",
        ),
        MarketProviderCapability(
            provider="alpha_vantage",
            configured=bool(settings.alpha_vantage_api_key),
            status="active" if alpha_enabled() else "missing_key_or_disabled",
            fields=["stock_quote_fallback"],
            missing=[] if alpha_enabled() else ["Alpha Vantage credentials"],
            notes="Stock-level fallback only. Not used as the primary options source.",
        ),
        MarketProviderCapability(
            provider="manual_upload",
            configured=True,
            status="active",
            fields=["user_confirmed_contract", "broker_screenshot_metadata", "pasted_contract_text"],
            missing=["OCR/vision extraction"],
            notes="Best legal workaround for real contract context: the user supplies their own broker data.",
        ),
    ]
    active = [item.provider for item in capabilities if item.status == "active"]
    return MarketProviderStatusResponse(
        status="active" if active else "degraded",
        strategy="free_honest_stack",
        capabilities=capabilities,
        data_quality_labels=["Full", "Delayed", "Estimated", "Manual", "Reference-only", "Missing"],
        message=(
            "RiskWise prefers real provider data when configured, labels delayed/estimated/manual fields, "
            "and never invents missing IV, Greeks, bid/ask, volume, or open interest."
        ),
    )


def fmp_enabled() -> bool:
    return settings.market_data_provider in {"fmp", "polygon", "massive", "hybrid"} and bool(settings.fmp_api_key)


def polygon_enabled() -> bool:
    return settings.market_data_provider in {"polygon", "massive", "hybrid"} and bool(settings.polygon_api_key)


def alpha_enabled() -> bool:
    return bool(settings.alpha_vantage_api_key)


def yfinance_enabled() -> bool:
    return bool(settings.enable_yfinance_options) and not yfinance_import_error()


def yfinance_import_error() -> str:
    global _YFINANCE_IMPORT_ERROR
    if _YFINANCE_IMPORT_ERROR is False:
        try:
            import_module("yfinance")
            _YFINANCE_IMPORT_ERROR = None
        except Exception as exc:
            text = " ".join(str(exc).split()) or exc.__class__.__name__
            _YFINANCE_IMPORT_ERROR = f"yfinance import failed: {text[:180]}"
    return str(_YFINANCE_IMPORT_ERROR or "")


def alpha_global_quote(symbol: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": settings.alpha_vantage_api_key})
    request = urllib.request.Request(f"{ALPHA_VANTAGE_BASE}?{query}", headers={"User-Agent": "RiskWise-dev/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    row = data.get("Global Quote") if isinstance(data, dict) else None
    return row if isinstance(row, dict) else {}


def yfinance_option_chain(
    symbol: str,
    *,
    expiration: str | None = None,
    option_side: str | None = None,
    limit: int = 120,
) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return [], []
    try:
        ticker = yf.Ticker(symbol)
        expirations = list(getattr(ticker, "options", []) or [])
        if not expirations:
            return [], []
        selected_expiration = expiration if expiration in expirations else expirations[0]
        chain = ticker.option_chain(selected_expiration)
    except Exception:
        return [], []
    rows: list[dict[str, Any]] = []
    for side_name, frame in [("call", getattr(chain, "calls", None)), ("put", getattr(chain, "puts", None))]:
        if option_side and side_name != option_side:
            continue
        if frame is None:
            continue
        records = frame.head(max(1, min(limit, 500))).to_dict("records")
        for row in records:
            strike = number_or_none(row.get("strike"))
            bid = number_or_none(row.get("bid"))
            ask = number_or_none(row.get("ask"))
            last = number_or_none(row.get("lastPrice"))
            iv = number_or_none(row.get("impliedVolatility"))
            rows.append(
                {
                    "contract_symbol": str(row.get("contractSymbol") or ""),
                    "ticker": str(row.get("contractSymbol") or ""),
                    "underlying_ticker": symbol,
                    "contract_type": side_name,
                    "optionSide": side_name,
                    "expiration_date": selected_expiration,
                    "strike_price": strike,
                    "strike": strike,
                    "last": last,
                    "bid": bid,
                    "ask": ask,
                    "mid": mid_price(bid, ask, last),
                    "implied_volatility": iv,
                    "open_interest": int(number_or_none(row.get("openInterest")) or 0),
                    "volume": int(number_or_none(row.get("volume")) or 0),
                    "shares_per_contract": 100,
                    "source": "yfinance_delayed",
                    "has_live_quote": False,
                    "data_quality": "Delayed",
                }
            )
    return expirations, rows[:limit]


def attach_estimated_greeks(contracts: list[dict[str, Any]], underlying_price: float | None) -> list[dict[str, Any]]:
    if not underlying_price:
        return contracts
    today = date.today()
    for contract in contracts:
        strike = number_or_none(contract.get("strike_price") or contract.get("strike"))
        iv = number_or_none(contract.get("implied_volatility"))
        expiration = parse_date_value(contract.get("expiration_date"))
        if not strike or not iv or not expiration:
            continue
        days = max(1, (expiration - today).days)
        greeks = black_scholes_greeks(
            underlying=float(underlying_price),
            strike=float(strike),
            days=days,
            iv=iv,
            option_side=str(contract.get("contract_type") or "call"),
        )
        if greeks:
            contract["estimated_greeks"] = greeks
            contract["greeks_source"] = "riskwise_black_scholes_estimate"
    return contracts


def black_scholes_greeks(underlying: float, strike: float, days: int, iv: float, option_side: str) -> dict[str, float]:
    sigma = iv / 100 if iv > 3 else iv
    if underlying <= 0 or strike <= 0 or sigma <= 0:
        return {}
    t = max(days / 365.0, 1 / 365)
    r = 0.04
    d1 = (math.log(underlying / strike) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    pdf = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
    cdf = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    if option_side == "put":
        delta = cdf(d1) - 1
        theta = (-(underlying * pdf * sigma) / (2 * math.sqrt(t)) + r * strike * math.exp(-r * t) * cdf(-d2)) / 365
    else:
        delta = cdf(d1)
        theta = (-(underlying * pdf * sigma) / (2 * math.sqrt(t)) - r * strike * math.exp(-r * t) * cdf(d2)) / 365
    gamma = pdf / (underlying * sigma * math.sqrt(t))
    vega = underlying * pdf * math.sqrt(t) / 100
    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 4),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
    }


def choose_yfinance_contract(
    contracts: list[dict[str, Any]],
    expiration: str | None,
    strike: float | None,
    option_type: str,
) -> dict[str, Any]:
    candidates = [
        row
        for row in contracts
        if (not expiration or row.get("expiration_date") == expiration)
        and (not option_type or row.get("contract_type") == option_type)
    ]
    if not candidates:
        return {}
    if strike is None:
        return candidates[0]
    return min(candidates, key=lambda row: abs(float(row.get("strike_price") or 0) - strike))


def mid_price(bid: float | None, ask: float | None, last: float | None) -> float | None:
    if bid is not None and ask is not None and ask >= bid and ask > 0:
        return round((bid + ask) / 2, 4)
    return last


def parse_date_value(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def standard_monthly_expirations(today: date | None = None, count: int = 8) -> list[str]:
    current = today or date.today()
    expirations: list[str] = []
    month_cursor = date(current.year, current.month, 1)
    while len(expirations) < count:
        third_friday = nth_weekday(month_cursor.year, month_cursor.month, weekday=4, n=3)
        if third_friday >= current:
            expirations.append(third_friday.isoformat())
        next_month = month_cursor.month + 1
        next_year = month_cursor.year + (1 if next_month == 13 else 0)
        month_cursor = date(next_year, 1 if next_month == 13 else next_month, 1)
    return expirations


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + (n - 1) * 7)


def normalize_side(option_side: str | None) -> str:
    clean = str(option_side or "").strip().lower()
    return clean if clean in {"call", "put"} else "call"


def polygon_option_reference(
    symbol: str,
    *,
    expiration: str | None = None,
    option_type: str | None = None,
    limit: int = 250,
) -> tuple[list[str], list[dict[str, Any]]]:
    params = {"underlying_ticker": clean_symbol(symbol), "limit": str(min(max(limit, 1), 1000))}
    if expiration:
        params["expiration_date"] = expiration
    else:
        params["expiration_date.gte"] = date.today().isoformat()
    if option_type in {"call", "put"}:
        params["contract_type"] = option_type
    try:
        data = polygon_get("/v3/reference/options/contracts", params)
    except Exception:
        return [], []
    rows = data.get("results") if isinstance(data, dict) else []
    contracts = [normalize_polygon_contract(row) for row in rows if isinstance(row, dict)]
    expirations = sorted({str(row.get("expiration_date") or "") for row in contracts if row.get("expiration_date")})
    return expirations, contracts


def polygon_ticker_search(query: str) -> list[dict[str, str]]:
    clean = query.strip()
    if not clean:
        return []
    params = {
        "market": "stocks",
        "active": "true",
        "limit": "20",
        "search": clean,
    }
    try:
        data = polygon_get("/v3/reference/tickers", params)
    except Exception:
        return []
    rows = data.get("results") if isinstance(data, dict) else []
    items: list[dict[str, str]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("ticker") or "").strip().upper()
        name = clean_text(str(row.get("name") or ""))
        if not symbol or not name:
            continue
        items.append(
            {
                "symbol": symbol,
                "name": name,
                "exchange": str(row.get("primary_exchange") or row.get("locale") or ""),
                "sector": "Market",
            }
        )
    return items


def normalize_polygon_contract(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_symbol": str(row.get("ticker") or ""),
        "ticker": str(row.get("ticker") or ""),
        "underlying_ticker": str(row.get("underlying_ticker") or ""),
        "contract_type": str(row.get("contract_type") or ""),
        "optionSide": str(row.get("contract_type") or ""),
        "expiration_date": str(row.get("expiration_date") or ""),
        "strike_price": number_or_none(row.get("strike_price")),
        "exercise_style": str(row.get("exercise_style") or ""),
        "shares_per_contract": int(number_or_none(row.get("shares_per_contract")) or 100),
        "primary_exchange": str(row.get("primary_exchange") or ""),
        "source": "massive_polygon_reference",
        "has_live_quote": False,
    }


def enrich_reference_contracts(contracts: list[dict[str, Any]], underlying_price: float | None) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for contract in contracts:
        grouped[str(contract.get("expiration_date") or "")].append(contract)
    enriched: list[dict[str, Any]] = []
    for expiration, rows in grouped.items():
        rows.sort(key=lambda row: abs(float(row.get("strike_price") or 0) - float(underlying_price or row.get("strike_price") or 0)))
        enriched.extend(rows)
    for contract in enriched:
        strike = contract.get("strike_price")
        side = contract.get("contract_type") or "call"
        if underlying_price and strike:
            moneyness = round((float(strike) - underlying_price) / underlying_price * 100, 2)
            contract["moneynessPct"] = moneyness
            contract["moneynessLabel"] = moneyness_label(moneyness, side)
    return enriched


def choose_contract_reference(
    contracts: list[dict[str, Any]],
    expiration: str | None,
    strike: float | None,
    option_type: str,
) -> dict[str, Any]:
    candidates = [
        contract
        for contract in contracts
        if (not expiration or contract.get("expiration_date") == expiration)
        and (not option_type or contract.get("contract_type") == option_type)
    ]
    if not candidates:
        return {}
    if strike is None:
        return candidates[0]
    return min(candidates, key=lambda contract: abs(float(contract.get("strike_price") or 0) - strike))


def moneyness_label(moneyness: float, option_side: str) -> str:
    if abs(moneyness) <= 3:
        return "near the money"
    out_of_money = (moneyness > 0 and option_side == "call") or (moneyness < 0 and option_side == "put")
    return "out of the money" if out_of_money else "in the money"


def fmp_get(path: str, params: dict[str, str]) -> Any:
    cache_key = json.dumps([path, sorted(params.items())], sort_keys=True)
    now = time.monotonic()
    cached = _FMP_CACHE.get(cache_key)
    if cached and now - cached[0] <= settings.market_cache_seconds:
        return cached[1]
    query = {**params, "apikey": settings.fmp_api_key}
    url = f"{FMP_STABLE_BASE}{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": "RiskWise-dev/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            _FMP_CACHE[cache_key] = (now, data)
            return data
    except Exception:
        if cached:
            return cached[1]
        raise


def polygon_get(path: str, params: dict[str, str]) -> Any:
    cache_key = json.dumps(["polygon", path, sorted(params.items())], sort_keys=True)
    now = time.monotonic()
    cached = _POLYGON_CACHE.get(cache_key)
    if cached and now - cached[0] <= settings.market_cache_seconds:
        return cached[1]
    query = {**params, "apiKey": settings.polygon_api_key}
    base = settings.massive_base_url or settings.polygon_base_url or "https://api.massive.com"
    url = f"{base}{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": "RiskWise-dev/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            _POLYGON_CACHE[cache_key] = (now, data)
            return data
    except Exception:
        if cached:
            return cached[1]
        raise


def yahoo_rss_news(symbol: str) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"s": symbol, "region": "US", "lang": "en-US"})
    request = urllib.request.Request(f"{YAHOO_RSS_BASE}?{query}", headers={"User-Agent": "RiskWise-dev/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8", errors="replace")
        root = ET.fromstring(payload)
    items = []
    for item in root.findall("./channel/item")[:5]:
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        items.append(
            {
                "title": clean_text(title),
                "source": "Yahoo Finance",
                "url": url,
                "publishedAt": (item.findtext("pubDate") or "").strip(),
                "summary": clean_text((item.findtext("description") or "").strip()),
                "image": "",
            }
        )
    return items


def normalize_fmp_news_item(row: dict[str, Any]) -> dict[str, str]:
    return {
        "title": clean_text(str(row.get("title") or "")),
        "source": str(row.get("site") or row.get("publisher") or "Financial Modeling Prep"),
        "url": str(row.get("url") or ""),
        "publishedAt": str(row.get("publishedDate") or row.get("date") or ""),
        "summary": clean_text(str(row.get("text") or row.get("summary") or ""))[:400],
        "image": str(row.get("image") or ""),
    }


def first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, dict):
        return value
    return {}


def clean_symbol(ticker: str) -> str:
    return ticker.strip().upper()[:12]


def local_symbol_search(query: str) -> list[dict[str, str]]:
    clean = " ".join(str(query or "").replace("-", " ").replace(".", " ").split()).lower()
    raw_symbol = str(query or "").strip().upper()
    ranked = []
    for item in FALLBACK_SYMBOLS:
        symbol = item["symbol"].upper()
        searchable_symbol = symbol.replace(".", " ").lower()
        name = item["name"].lower()
        sector = item.get("sector", "").lower()
        score = 0
        if raw_symbol == symbol:
            score += 80
        if symbol.startswith(raw_symbol) and raw_symbol:
            score += 36
        if clean and clean in searchable_symbol:
            score += 24
        if clean and clean in name:
            score += 30
        for token in [part for part in clean.split() if len(part) >= 2]:
            if token in name:
                score += 8
            if token in sector:
                score += 4
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda row: (-row[0], row[1]["symbol"]))
    return [dict(item) for _, item in ranked[:8]]


def rank_search_items(query: str, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    clean = " ".join(str(query or "").replace("-", " ").replace(".", " ").split()).lower()
    raw_symbol = str(query or "").strip().upper()
    seen_symbols: set[str] = set()
    ranked: list[tuple[int, dict[str, str]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "").strip().upper()
        name = clean_text(str(row.get("name") or row.get("companyName") or ""))
        if not symbol or not name or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        searchable_symbol = symbol.replace(".", " ").lower()
        searchable_name = name.lower()
        exchange = str(row.get("exchange") or row.get("exchangeFullName") or row.get("primary_exchange") or "")
        score = 0
        if raw_symbol == symbol:
            score += 120
        if raw_symbol and symbol.startswith(raw_symbol):
            score += 55
        if clean and clean in searchable_symbol:
            score += 40
        if clean and clean in searchable_name:
            score += 45
        for token in [part for part in clean.split() if len(part) >= 2]:
            if token in searchable_name:
                score += 12
            if token in searchable_symbol:
                score += 10
        if exchange.upper() in {"NASDAQ", "NYSE", "XNYS", "XNAS", "AMEX", "ARCX"}:
            score += 3
        ranked.append(
            (
                score,
                {
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "sector": str(row.get("sector") or "Market"),
                },
            )
        )
    ranked.sort(key=lambda item: (-item[0], item[1]["symbol"]))
    return [item for _score, item in ranked[:8]]


def looks_like_symbol(query: str) -> bool:
    clean = str(query or "").strip().upper()
    return 1 <= len(clean) <= 8 and all(char.isalnum() or char in ".-" for char in clean)


def number_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def clean_text(value: str) -> str:
    text = str(value or "")
    if "â" in text or "Â" in text:
        try:
            text = text.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": "-",
        "\u2013": "-",
        "\u00a0": " ",
        "Â": "",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return " ".join(text.split())


def short_error(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {str(exc)[:180]}"
