from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any

from api.models import (
    CompanyProfileResponse,
    EarningsResponse,
    MarketNewsResponse,
    MarketQuoteResponse,
    MarketSearchResponse,
    OptionsAvailabilityResponse,
    OptionsContextResponse,
)
from api.settings import settings


READY_FIELDS = ["ticker", "provider_status", "quote", "company_profile", "earnings_calendar", "stock_news"]
PENDING_FIELDS = ["option_chain", "implied_volatility", "expiration_dates", "live_premium", "breakeven_from_real_premium"]
FMP_STABLE_BASE = "https://financialmodelingprep.com/stable"
YAHOO_RSS_BASE = "https://feeds.finance.yahoo.com/rss/2.0/headline"
_FMP_CACHE: dict[str, tuple[float, Any]] = {}
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
    if not fmp_enabled():
        return MarketQuoteResponse(
            ticker=symbol,
            status="needs_provider_key",
            provider=settings.market_data_provider or "disabled",
            message="FMP is not enabled for quotes.",
        )
    try:
        rows = fmp_get("/quote", {"symbol": symbol})
        row = first_dict(rows)
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
    except Exception as exc:
        return MarketQuoteResponse(ticker=symbol, status="unavailable", provider="financialmodelingprep", message=short_error(exc))


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
    if not fmp_enabled():
        return MarketSearchResponse(
            query=clean,
            status="local_fallback" if fallback_items else "needs_provider_key",
            provider="local_symbol_index",
            items=fallback_items,
            message="FMP is not available, so search is using the built-in symbol index.",
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
        items = []
        seen_symbols = set()
        for row in [*fallback_items, *rows]:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            name = clean_text(str(row.get("name") or ""))
            if symbol and name and symbol not in seen_symbols:
                seen_symbols.add(symbol)
                items.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "exchange": str(row.get("exchange") or row.get("exchangeFullName") or ""),
                        "sector": str(row.get("sector") or "Market"),
                    }
                )
            if len(items) >= 8:
                break
        if not items and looks_like_symbol(clean):
            symbol = clean_symbol(clean)
            items.append({"symbol": symbol, "name": f"{symbol} typed ticker", "exchange": "Verify quote", "sector": "Unverified"})
        return MarketSearchResponse(
            query=clean,
            status="ok" if items else "empty",
            provider="financialmodelingprep+local_symbol_index",
            items=items,
            message="" if rows else "FMP search returned no rows or was rate-limited, so RiskWise included local symbol matches.",
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
        message="RiskWise is ready to receive market data, but no enabled provider is active for this environment.",
    )


async def options_expirations(ticker: str) -> OptionsAvailabilityResponse:
    symbol = clean_symbol(ticker)
    quote = await market_quote(symbol)
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
    selected: dict[str, Any] = {
        "symbol": symbol,
        "expiration": expiration or "",
        "strike": strike,
        "optionSide": normalize_side(option_side),
        "source": "user_input_plus_underlying_context",
        "underlyingPrice": quote.price,
        "providerHasLiveOptionChain": False,
    }
    if quote.price and strike:
        moneyness = round((strike - quote.price) / quote.price * 100, 2)
        selected["moneynessPct"] = moneyness
        selected["moneynessLabel"] = "near the money" if abs(moneyness) <= 3 else "out of the money" if (moneyness > 0 and selected["optionSide"] == "call") or (moneyness < 0 and selected["optionSide"] == "put") else "in the money"
    return OptionsAvailabilityResponse(
        ticker=symbol,
        status="partial_contract_context",
        provider="financialmodelingprep+riskwise_estimator",
        expirations=standard_monthly_expirations(),
        contracts=[],
        selected=selected,
        quote=quote.model_dump(),
        profile=profile.model_dump(),
        earnings=[item.model_dump() for item in earnings.items],
        message=(
            "RiskWise attached real stock quote/profile/earnings context, but live premium, IV, Greeks, bid/ask, "
            "volume, and open interest still require a dedicated options-chain provider."
        ),
    )


async def gather_contract_context(symbol: str):
    quote = await market_quote(symbol)
    profile = await company_profile(symbol)
    earnings = await earnings_calendar(symbol)
    return quote, profile, earnings


def fmp_enabled() -> bool:
    return settings.market_data_provider == "fmp" and bool(settings.fmp_api_key)


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


def looks_like_symbol(query: str) -> bool:
    clean = str(query or "").strip().upper()
    return 1 <= len(clean) <= 8 and all(char.isalnum() or char in ".-" for char in clean)


def number_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
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
