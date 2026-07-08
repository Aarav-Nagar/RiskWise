import time
import uuid

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    ChatRequest,
    ChatFeedbackRequest,
    ChatFeedbackResponse,
    ChatMessageResponse,
    ChatResponse,
    ChatThreadResponse,
    ClerkSyncRequest,
    CompanyProfileResponse,
    ContractExtractionRequest,
    ContractExtractionResponse,
    EarningsResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MarketNewsResponse,
    MarketProviderStatusResponse,
    MarketQuoteResponse,
    MarketSearchResponse,
    OptionsContextResponse,
    OptionsAvailabilityResponse,
    ProfileUpdateRequest,
    ReadyResponse,
    SavedCheckRequest,
    SavedCheckExportResponse,
    SavedCheckResponse,
    SigninRequest,
    SignupRequest,
    TradeCheckRequest,
    TradeCheckResponse,
    UserResponse,
)
from .scoring import parse_expiration_date, score_trade_check
from .services.llm import answer_chat, extract_contract_from_uploads
from .services.check_export import build_saved_check_export
from .services.llm_provider import configured_providers
from .services.market_data import company_profile, earnings_calendar, market_provider_status, market_quote, market_search, options_chain, options_context, options_contract_context, options_expirations, stock_news
from .services.auth import auth_config_status, require_clerk_subject, require_profile_lookup_owner, require_request_user
from .services.store import clean_email, store
from .settings import settings

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.05)

app = FastAPI(
    title="Options Risk Check API",
    version="0.3.0",
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)

_rate_limit_hits: dict[tuple[str, str], list[float]] = {}
_rate_limits = {
    "/chat": lambda: settings.rate_limit_chat,
    "/trade-check": lambda: settings.rate_limit_trade_check,
    "/market": lambda: settings.rate_limit_market,
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_origin_regex=None if settings.environment == "production" else r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_safety_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    limited_prefix = next((prefix for prefix in _rate_limits if request.url.path.startswith(prefix)), None)
    if limited_prefix:
        key = (rate_limit_identity(request), limited_prefix)
        now = time.monotonic()
        window = settings.rate_limit_window_seconds
        recent = [stamp for stamp in _rate_limit_hits.get(key, []) if now - stamp < window]
        limit = _rate_limits[limited_prefix]()
        if len(recent) >= limit:
            return JSONResponse(
                status_code=429,
                content=api_error("rate_limited", "Too many requests. Give RiskWise a moment, then try again.", request_id),
                headers={"X-Request-ID": request_id},
            )
        recent.append(now)
        _rate_limit_hits[key] = recent

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        sentry_sdk.set_tag("request_id", request_id)
        sentry_sdk.set_context("request", {"path": request.url.path, "method": request.method})
        sentry_sdk.capture_exception(exc)
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers["X-RiskWise-Time-Ms"] = str(int((time.perf_counter() - started) * 1000))
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
    return JSONResponse(
        status_code=exc.status_code,
        content=api_error("request_error", str(exc.detail), request_id),
        headers={"X-Request-ID": request_id},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": getattr(store, "provider", settings.storage_provider)}


@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    storage_status = store.status()
    llm_status = configured_providers()
    any_external_llm = any(
        item["configured"]
        and item["provider"] != "fallback"
        and not item.get("cooling_down")
        and item.get("status") in {"ready", "configured_unverified"}
        for item in llm_status
    )
    fallback_ready = any(item["provider"] == "fallback" and item["configured"] for item in llm_status)
    market_status = market_provider_status()
    auth_status = auth_config_status()
    auth_ready = auth_status["configured"] or settings.environment != "production"
    sentry_ready = bool(settings.sentry_dsn) or settings.environment != "production"
    ai_ready = any_external_llm or fallback_ready
    is_ready = bool(storage_status.get("ready")) and auth_ready and sentry_ready and ai_ready
    return ReadyResponse(
        status="ready" if is_ready else "degraded",
        environment=settings.environment,
        storage=storage_status,
        llm=llm_status,
        market_data={
            "status": market_status.status,
            "strategy": market_status.strategy,
            "ai_ready": ai_ready,
            "fallback_available": fallback_ready,
            "sentry_configured": sentry_ready,
            "providers": [item.model_dump() for item in market_status.capabilities],
        },
        auth=auth_status,
    )


@app.get("/ai/providers")
def ai_providers() -> dict[str, object]:
    providers = configured_providers()
    ready_provider = next(
        (
            item
            for item in providers
            if item["provider"] != "fallback"
            and item["configured"]
            and not item.get("cooling_down")
            and item.get("status") == "ready"
        ),
        None,
    )
    fallback = next((item for item in providers if item["provider"] == "fallback"), None)
    active = ready_provider or fallback
    return {
        "status": "active" if ready_provider else "fallback_ready",
        "active_provider": active["provider"] if active else "fallback",
        "active_kind": active.get("kind") if active else "deterministic",
        "provider_order": settings.llm_provider_order,
        "providers": providers,
        "fallback_available": True,
        "message": (
            "RiskWiseAI uses local/hosted providers when available, then falls back to a deterministic "
            "tool-first options coach so the app remains usable."
        ),
    }


@app.get("/ai/smoke")
async def ai_smoke() -> dict[str, object]:
    prompts = [
        ("Greeting", "hi", None, "quick"),
        ("Concept", "What is IV crush?", None, "standard"),
        ("Trade review", "What about this trade?", smoke_report(), "standard"),
        ("Deep analysis", "Run deep analysis", smoke_report(), "deep_analysis"),
    ]
    results = []
    started = time.monotonic()
    for label, prompt, report, depth in prompts:
        item_started = time.monotonic()
        response = await answer_chat(
            prompt,
            current_report=report,
            user_profile={"experienceLevel": "Some experience", "riskStyle": "Balanced"},
            chat_mode="Review" if report else "Explain",
            analysis_depth=depth,
        )
        results.append(
            {
                "label": label,
                "prompt": prompt,
                "mode": response.get("mode"),
                "analysis_depth": response.get("analysis_depth"),
                "provider": response.get("provider"),
                "model": response.get("model"),
                "used_fallback": response.get("used_fallback"),
                "latency_ms": int(round((time.monotonic() - item_started) * 1000)),
                "has_answer": bool(str(response.get("answer") or "").strip()),
                "agent_count": len(response.get("agent_docket") or []),
                "missing_data_count": len(response.get("missing_data") or []),
            }
        )
    passed = sum(1 for item in results if item["has_answer"])
    return {
        "status": "pass" if passed == len(results) else "degraded",
        "passed": passed,
        "total": len(results),
        "latency_ms": int(round((time.monotonic() - started) * 1000)),
        "providers": configured_providers(),
        "results": results,
    }


@app.post("/auth/signup", response_model=UserResponse)
def signup(request: SignupRequest) -> UserResponse:
    try:
        return UserResponse(**store.create_user(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/signin", response_model=UserResponse)
def signin(request: SigninRequest) -> UserResponse:
    try:
        return UserResponse(**store.sign_in(request.email, request.password))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/auth/clerk-sync", response_model=UserResponse)
def clerk_sync(request: ClerkSyncRequest, http_request: Request) -> UserResponse:
    require_clerk_subject(request.clerkId, http_request)
    try:
        return UserResponse(**store.sync_clerk_user(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/auth/profile-by-email", response_model=UserResponse)
def profile_by_email(email: str, http_request: Request) -> UserResponse:
    user = store.find_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No app profile exists for this Clerk account yet.")
    require_profile_lookup_owner(user, http_request)
    return UserResponse(**user)


@app.patch("/auth/users/{user_id}/profile", response_model=UserResponse)
def update_profile(user_id: str, request: ProfileUpdateRequest, http_request: Request) -> UserResponse:
    require_request_user(user_id, http_request)
    try:
        updates = request.model_dump(exclude_unset=True)
        return UserResponse(**store.update_user_profile(user_id, updates))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/auth/users/{user_id}")
def delete_user(user_id: str, http_request: Request) -> dict[str, str | bool]:
    require_request_user(user_id, http_request)
    try:
        return store.delete_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/auth/users/{user_id}/context")
def clear_user_context(user_id: str, http_request: Request) -> dict[str, str | bool]:
    require_request_user(user_id, http_request)
    try:
        return store.clear_user_context(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/auth/users/{user_id}/context-summary")
def user_context_summary(user_id: str, http_request: Request) -> dict[str, int]:
    require_request_user(user_id, http_request)
    return store.context_summary(user_id)


@app.post("/auth/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(request: ForgotPasswordRequest) -> ForgotPasswordResponse:
    email = clean_email(request.email)
    known = store.find_user_by_email(email) is not None
    return ForgotPasswordResponse(
        email=mask_email(email),
        knownAccount=known,
        message="Password reset is handled by Clerk in the app. If this address exists, Clerk can send a secure reset flow.",
    )


@app.post("/trade-check", response_model=TradeCheckResponse)
def trade_check(request: TradeCheckRequest, http_request: Request) -> TradeCheckResponse:
    require_request_user(request.user_id, http_request)
    expiration = parse_expiration_date(request.expiration)
    if expiration is None:
        raise HTTPException(status_code=400, detail="Choose a valid future expiration date.")
    try:
        response = score_trade_check(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save_trade_check(request.user_id, request.model_dump(), response.model_dump())
    return response


@app.get("/saved-checks/{user_id}", response_model=list[SavedCheckResponse])
def saved_checks(user_id: str, http_request: Request) -> list[SavedCheckResponse]:
    require_request_user(user_id, http_request)
    return [SavedCheckResponse(**item) for item in store.list_saved_checks(user_id)]


@app.post("/saved-checks", response_model=SavedCheckResponse)
def save_check(request: SavedCheckRequest, http_request: Request) -> SavedCheckResponse:
    require_request_user(request.user_id, http_request)
    item = store.save_check(request.user_id, request.trade_check_id, request.report, request.note)
    return SavedCheckResponse(**item)


@app.get("/saved-checks/{user_id}/{saved_check_id}/export", response_model=SavedCheckExportResponse)
def export_saved_check(user_id: str, saved_check_id: str, http_request: Request) -> SavedCheckExportResponse:
    require_request_user(user_id, http_request)
    item = store.get_saved_check(user_id, saved_check_id)
    if not item:
        raise HTTPException(status_code=404, detail="That saved Check was not found.")
    export = build_saved_check_export(item, store.get_user(user_id) or {})
    return SavedCheckExportResponse(**export)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    require_request_user(request.user_id, http_request)
    history = []
    if request.thread_id:
        history = store.list_chat_messages(request.user_id, request.thread_id)[-10:]
    stored_profile = store.get_user(request.user_id) or {}
    profile_context = merge_profile_context(stored_profile, request.user_profile or {})
    recent_checks = ranked_saved_checks(
        store.list_saved_checks(request.user_id),
        request.message,
        request.current_report,
    )
    coach = await answer_chat(
        request.message,
        current_report=request.current_report,
        user_profile=profile_context,
        chat_mode=request.chat_mode,
        analysis_depth=request.analysis_depth,
        attachments=request.attachments,
        conversation_history=history,
        recent_checks=recent_checks,
    )
    thread_id = store.append_chat(
        request.user_id,
        request.thread_id,
        request.message,
        coach["answer"],
        mode=request.chat_mode,
        attachments=request.attachments,
    )
    return ChatResponse(thread_id=thread_id, **coach)


@app.post("/extract-contract", response_model=ContractExtractionResponse)
async def extract_contract(request: ContractExtractionRequest, http_request: Request) -> ContractExtractionResponse:
    require_request_user(request.user_id, http_request)
    if not request.attachments:
        raise HTTPException(status_code=400, detail="Upload a contract screenshot or readable contract text first.")
    result = await extract_contract_from_uploads(request.attachments)
    store.save_upload(request.user_id, "check_extraction", request.attachments, result)
    return ContractExtractionResponse(**result)


@app.get("/chat/threads/{user_id}", response_model=list[ChatThreadResponse])
def chat_threads(user_id: str, http_request: Request) -> list[ChatThreadResponse]:
    require_request_user(user_id, http_request)
    return [ChatThreadResponse(**item) for item in store.list_chat_threads(user_id)]


@app.get("/chat/threads/{user_id}/{thread_id}", response_model=list[ChatMessageResponse])
def chat_messages(user_id: str, thread_id: str, http_request: Request) -> list[ChatMessageResponse]:
    require_request_user(user_id, http_request)
    return [ChatMessageResponse(**item) for item in store.list_chat_messages(user_id, thread_id)]


@app.post("/chat/feedback", response_model=ChatFeedbackResponse)
def chat_feedback(request: ChatFeedbackRequest, http_request: Request) -> ChatFeedbackResponse:
    require_request_user(request.user_id, http_request)
    return ChatFeedbackResponse(**store.save_chat_feedback(request))


@app.get("/market/options-context/{ticker}", response_model=OptionsContextResponse)
async def market_options_context(ticker: str) -> OptionsContextResponse:
    return await options_context(ticker)


@app.get("/market/quote/{ticker}", response_model=MarketQuoteResponse)
async def market_quote_endpoint(ticker: str) -> MarketQuoteResponse:
    return await market_quote(ticker)


@app.get("/market/search", response_model=MarketSearchResponse)
async def market_search_endpoint(q: str) -> MarketSearchResponse:
    return await market_search(q)


@app.get("/market/profile/{ticker}", response_model=CompanyProfileResponse)
async def company_profile_endpoint(ticker: str) -> CompanyProfileResponse:
    return await company_profile(ticker)


@app.get("/market/news/{ticker}", response_model=MarketNewsResponse)
async def stock_news_endpoint(ticker: str) -> MarketNewsResponse:
    return await stock_news(ticker)


@app.get("/market/earnings/{ticker}", response_model=EarningsResponse)
async def earnings_endpoint(ticker: str) -> EarningsResponse:
    return await earnings_calendar(ticker)


@app.get("/market/providers", response_model=MarketProviderStatusResponse)
def market_providers_endpoint() -> MarketProviderStatusResponse:
    return market_provider_status()


@app.get("/market/options/expirations/{ticker}", response_model=OptionsAvailabilityResponse)
async def options_expirations_endpoint(ticker: str) -> OptionsAvailabilityResponse:
    return await options_expirations(ticker)


@app.get("/market/options/chain/{ticker}", response_model=OptionsAvailabilityResponse)
async def options_chain_endpoint(ticker: str, expiration: str | None = None) -> OptionsAvailabilityResponse:
    return await options_chain(ticker, expiration)


@app.get("/market/options/contract-context/{ticker}", response_model=OptionsAvailabilityResponse)
async def options_contract_context_endpoint(
    ticker: str,
    expiration: str | None = None,
    strike: float | None = None,
    option_side: str | None = None,
) -> OptionsAvailabilityResponse:
    return await options_contract_context(ticker, expiration, strike, option_side)


def smoke_report() -> dict[str, object]:
    return {
        "id": "smoke-aapl-call",
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "optionSide": "call",
        "strike": 190,
        "expiration": "2026-07-12",
        "premium": 5,
        "contracts": 1,
        "amountAtRisk": 500,
        "setupScore": 72,
        "weakestLink": "liquidity context",
        "riskPosture": "Mixed Conviction",
        "riskMath": {
            "max_loss": 500,
            "breakeven": 195,
            "account_risk_pct": 2.0,
            "required_move_to_breakeven_pct": 2.63,
            "dte": 30,
        },
        "setupDebate": {
            "bull": "Defined max loss and manageable breakeven move.",
            "bear": "Missing bid/ask, IV, volume, and open interest.",
            "riskJudge": "Sizing fits the rule, but liquidity context is incomplete.",
        },
        "dataQuality": {
            "label": "Partial",
            "missing": ["bid/ask", "IV", "Greeks", "open interest", "volume"],
        },
    }


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}{'*' * max(2, len(name) - 2)}@{domain}" if domain else email


def rate_limit_identity(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"bearer:{auth[-24:]}"
    user_header = request.headers.get("X-RiskWise-User-ID") or request.headers.get("X-Clerk-User-ID")
    if user_header and settings.environment != "production":
        return f"user:{user_header.strip()[:80]}"
    host = request.client.host if request.client else "local"
    return f"ip:{host}"


def api_error(code: str, message: str, request_id: str) -> dict[str, str]:
    return {"code": code, "detail": message, "request_id": request_id}


def merge_profile_context(stored: dict, incoming: dict) -> dict:
    """Combine persisted profile memory with the current client snapshot."""
    merged = {key: value for key, value in stored.items() if key not in {"passwordHash", "salt"}}
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        elif value not in (None, "", [], {}):
            merged[key] = value
    return merged


def ranked_saved_checks(checks: list[dict], message: str, current_report: dict | None) -> list[dict]:
    """Prefer saved checks that match the user's ticker, strategy, topic, or selected context."""
    wanted = ticker_hints(message, current_report)
    lower_message = message.lower()
    strategy_terms = {
        "call": ["call", "long call"],
        "put": ["put", "long put"],
        "spread": ["spread", "debit", "credit", "vertical"],
        "earnings": ["earnings", "event", "iv crush"],
        "sizing": ["size", "sizing", "risk", "max loss", "drawdown"],
        "liquidity": ["bid", "ask", "volume", "open interest", "liquidity"],
    }

    def term_matches(text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)

    def score(item: dict) -> tuple[int, str]:
        report = item.get("report") if isinstance(item, dict) else {}
        report = report or {}
        ticker = str(report.get("ticker") or "").upper()
        note = str(item.get("note") or "").upper()
        searchable = " ".join(
            [
                str(report.get("tradeType") or report.get("trade_type") or ""),
                str(report.get("weakestLink") or report.get("weakest_link") or ""),
                str(report.get("riskPosture") or report.get("risk_posture") or ""),
                str(item.get("note") or ""),
            ]
        ).lower()
        relevance = 0
        if ticker and ticker in wanted:
            relevance += 10
        if any(hint and hint in note for hint in wanted):
            relevance += 4
        for topic, terms in strategy_terms.items():
            if term_matches(lower_message, terms) and term_matches(searchable, terms):
                relevance += 3
        if current_report and report.get("id") and report.get("id") == current_report.get("id"):
            relevance += 12
        return relevance, str(item.get("createdAt") or "")

    ranked = []
    for item in sorted(checks, key=score, reverse=True)[:8]:
        relevance, _ = score(item)
        copy = dict(item)
        copy["aiRelevanceScore"] = relevance
        copy["aiRelevanceReason"] = "ticker/topic match" if relevance > 0 else "recent saved check"
        ranked.append(copy)
    return ranked


def ticker_hints(message: str, current_report: dict | None) -> set[str]:
    hints: set[str] = set()
    if current_report and current_report.get("ticker"):
        hints.add(str(current_report["ticker"]).upper())
    stop = {
        "WHAT", "CALL", "PUT", "THE", "AND", "FOR", "RISK", "TRADE", "AFTER", "BEFORE",
        "WHY", "HOW", "CAN", "YOU", "ARE", "THIS", "THAT", "WITH", "FROM", "WHEN",
        "IV", "ITM", "OTM", "ATM", "AI", "DTE", "CEO", "CFO", "YOLO", "FOMO",
    }
    for token in message.replace("$", " ").replace("/", " ").split():
        clean = "".join(char for char in token if char.isalpha()).upper()
        if 2 <= len(clean) <= 5 and clean not in stop:
            hints.add(clean)
    return hints
