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
    EarningsResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MarketNewsResponse,
    MarketQuoteResponse,
    MarketSearchResponse,
    OptionsContextResponse,
    OptionsAvailabilityResponse,
    ProfileUpdateRequest,
    ReadyResponse,
    SavedCheckRequest,
    SavedCheckResponse,
    SigninRequest,
    SignupRequest,
    TradeCheckRequest,
    TradeCheckResponse,
    UserResponse,
)
from .scoring import parse_expiration_date, score_trade_check
from .services.llm import answer_chat
from .services.llm_provider import configured_providers
from .services.market_data import company_profile, earnings_calendar, market_quote, market_search, options_chain, options_context, options_contract_context, options_expirations, stock_news
from .services.store import clean_email, store
from .settings import settings

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.05)

app = FastAPI(title="Options Risk Check API", version="0.3.0")

_rate_limit_hits: dict[tuple[str, str], list[float]] = {}
_rate_limits = {
    "/chat": lambda: settings.rate_limit_chat,
    "/trade-check": lambda: settings.rate_limit_trade_check,
    "/market": lambda: settings.rate_limit_market,
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8081",
        "http://localhost:8081",
        "http://127.0.0.1:8091",
        "http://localhost:8091",
        "http://127.0.0.1:8092",
        "http://localhost:8092",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
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
        item["configured"] and item["provider"] != "fallback" and not item.get("cooling_down")
        for item in llm_status
    )
    is_ready = bool(storage_status.get("ready")) and any_external_llm
    return ReadyResponse(
        status="ready" if is_ready else "degraded",
        environment=settings.environment,
        storage=storage_status,
        llm=llm_status,
        market_data={
            "provider": settings.market_data_provider,
            "configured": bool(settings.fmp_api_key) if settings.market_data_provider == "fmp" else settings.market_data_provider == "disabled",
        },
    )


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
def clerk_sync(request: ClerkSyncRequest) -> UserResponse:
    try:
        return UserResponse(**store.sync_clerk_user(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/auth/profile-by-email", response_model=UserResponse)
def profile_by_email(email: str) -> UserResponse:
    user = store.find_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No app profile exists for this Clerk account yet.")
    return UserResponse(**user)


@app.patch("/auth/users/{user_id}/profile", response_model=UserResponse)
def update_profile(user_id: str, request: ProfileUpdateRequest) -> UserResponse:
    require_request_user(user_id)
    try:
        updates = request.model_dump(exclude_unset=True)
        return UserResponse(**store.update_user_profile(user_id, updates))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/auth/users/{user_id}")
def delete_user(user_id: str) -> dict[str, str | bool]:
    require_request_user(user_id)
    try:
        return store.delete_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/auth/users/{user_id}/context")
def clear_user_context(user_id: str) -> dict[str, str | bool]:
    require_request_user(user_id)
    try:
        return store.clear_user_context(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
def trade_check(request: TradeCheckRequest) -> TradeCheckResponse:
    require_user_id(request.user_id)
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
def saved_checks(user_id: str) -> list[SavedCheckResponse]:
    require_user_id(user_id)
    return [SavedCheckResponse(**item) for item in store.list_saved_checks(user_id)]


@app.post("/saved-checks", response_model=SavedCheckResponse)
def save_check(request: SavedCheckRequest) -> SavedCheckResponse:
    require_user_id(request.user_id)
    item = store.save_check(request.user_id, request.trade_check_id, request.report, request.note)
    return SavedCheckResponse(**item)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    require_user_id(request.user_id)
    history = []
    if request.thread_id:
        history = store.list_chat_messages(request.user_id, request.thread_id)[-10:]
    recent_checks = store.list_saved_checks(request.user_id)[:5]
    coach = await answer_chat(
        request.message,
        current_report=request.current_report,
        user_profile=request.user_profile,
        chat_mode=request.chat_mode,
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


@app.get("/chat/threads/{user_id}", response_model=list[ChatThreadResponse])
def chat_threads(user_id: str) -> list[ChatThreadResponse]:
    require_user_id(user_id)
    return [ChatThreadResponse(**item) for item in store.list_chat_threads(user_id)]


@app.get("/chat/threads/{user_id}/{thread_id}", response_model=list[ChatMessageResponse])
def chat_messages(user_id: str, thread_id: str) -> list[ChatMessageResponse]:
    require_user_id(user_id)
    return [ChatMessageResponse(**item) for item in store.list_chat_messages(user_id, thread_id)]


@app.post("/chat/feedback", response_model=ChatFeedbackResponse)
def chat_feedback(request: ChatFeedbackRequest) -> ChatFeedbackResponse:
    require_user_id(request.user_id)
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


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}{'*' * max(2, len(name) - 2)}@{domain}" if domain else email


def require_user_id(user_id: str | None) -> None:
    if not user_id or len(str(user_id).strip()) < 3:
        raise HTTPException(status_code=401, detail="A signed-in RiskWise profile is required for this action.")


def require_request_user(user_id: str | None) -> None:
    require_user_id(user_id)
    if settings.environment == "production":
        # The deployed app must send a signed user id header from the authenticated client.
        # Full Clerk JWT validation is handled at the edge/native auth layer in the next deployment pass.
        pass


def rate_limit_identity(request: Request) -> str:
    user_header = request.headers.get("X-RiskWise-User-ID") or request.headers.get("X-Clerk-User-ID")
    auth = request.headers.get("Authorization", "")
    if user_header:
        return f"user:{user_header.strip()[:80]}"
    if auth.startswith("Bearer "):
        return f"bearer:{auth[-24:]}"
    host = request.client.host if request.client else "local"
    return f"ip:{host}"


def api_error(code: str, message: str, request_id: str) -> dict[str, str]:
    return {"code": code, "detail": message, "request_id": request_id}
