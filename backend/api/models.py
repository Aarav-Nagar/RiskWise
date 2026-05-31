from typing import Any

from pydantic import BaseModel, Field


class ProfilePayload(BaseModel):
    accountSize: float = Field(gt=0, default=25000)
    riskBudgetPercent: float = Field(gt=0, le=25, default=2)
    purpose: list[str] = Field(default_factory=list)
    tradeFocus: list[str] = Field(default_factory=list)
    experienceLevel: str = "Some experience"
    riskStyle: str = "Balanced"
    struggles: list[str] = Field(default_factory=list)
    reminders: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    marketCaps: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    safetyAccepted: bool = False
    aiMemory: dict[str, Any] = Field(default_factory=dict)
    riskRules: dict[str, Any] = Field(default_factory=dict)
    coachStyle: dict[str, Any] = Field(default_factory=dict)
    savedContext: dict[str, Any] = Field(default_factory=dict)
    appPreferences: dict[str, Any] = Field(default_factory=dict)


class ProfileUpdateRequest(BaseModel):
    experienceLevel: str | None = None
    riskStyle: str | None = None
    struggles: list[str] | None = None
    sectors: list[str] | None = None
    marketCaps: list[str] | None = None
    events: list[str] | None = None
    aiMemory: dict[str, Any] | None = None
    riskRules: dict[str, Any] | None = None
    coachStyle: dict[str, Any] | None = None
    savedContext: dict[str, Any] | None = None
    appPreferences: dict[str, Any] | None = None


class SignupRequest(ProfilePayload):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=6, max_length=200)


class ClerkSyncRequest(ProfilePayload):
    clerkId: str = Field(min_length=3, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=160)


class SigninRequest(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=6, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=160)


class UserResponse(ProfilePayload):
    id: str
    name: str
    email: str
    clerkId: str | None = None


class ForgotPasswordResponse(BaseModel):
    email: str
    knownAccount: bool
    message: str


class TradeCheckRequest(BaseModel):
    user_id: str | None = None
    ticker: str = Field(min_length=1, max_length=12)
    trade_type: str
    option_side: str = "call"
    strike: float = Field(ge=0)
    expiration: str
    expiration_source: str = "manual"
    premium: float | None = Field(default=None, ge=0)
    contracts: int | None = Field(default=None, ge=1, le=1000)
    bid: float | None = Field(default=None, ge=0)
    ask: float | None = Field(default=None, ge=0)
    implied_volatility: float | None = Field(default=None, ge=0)
    open_interest: int | None = Field(default=None, ge=0)
    contract_volume: int | None = Field(default=None, ge=0)
    underlying_price: float | None = Field(default=None, ge=0)
    amount_at_risk: float = Field(gt=0)
    timeframe: str
    account_size: float = Field(gt=0)


class TradeCheckResponse(BaseModel):
    id: str
    ticker: str
    trade_type: str
    title: str
    subtitle: str
    badge: str
    setup_score: int
    risk_score: float
    agent_agreement: int
    methodology_label: str
    insight: str
    strike: float
    expiration: str
    amount_at_risk: float
    timeframe: str
    checks: list[list[str]]
    agents: list[list[object]]
    scenarios: list[list[str]]
    overall_read: str
    weakest_link: str
    risk_posture: str
    decision_snapshot: dict[str, Any]
    risk_math: dict[str, Any]
    agent_docket: list[dict[str, Any]]
    agreement_map: dict[str, Any]
    questions: list[str]
    contract_label: dict[str, Any] = Field(default_factory=dict)
    setup_debate: dict[str, str] = Field(default_factory=dict)
    contract_snapshot: dict[str, Any] = Field(default_factory=dict)
    data_quality: dict[str, Any] = Field(default_factory=dict)


class SavedCheckRequest(BaseModel):
    user_id: str
    trade_check_id: str | None = None
    report: dict[str, Any]
    note: str = ""


class SavedCheckResponse(BaseModel):
    id: str
    userId: str
    tradeCheckId: str | None = None
    report: dict[str, Any]
    note: str = ""
    createdAt: str


class ChatRequest(BaseModel):
    user_id: str
    thread_id: str | None = None
    message: str = Field(min_length=1, max_length=1200)
    current_report: dict[str, Any] | None = None
    user_profile: dict[str, Any] | None = None
    chat_mode: str = "Explain"
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    mode: str = "fallback"
    summary_cards: list[dict[str, Any]] = Field(default_factory=list)
    visual_blocks: list[dict[str, Any]] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)
    confidence: float = 0.6
    missing_data: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    tools_used: list[dict[str, Any]] = Field(default_factory=list)
    provider: str = "fallback"
    model: str = "deterministic-options-coach"
    used_fallback: bool = True


class ChatFeedbackRequest(BaseModel):
    user_id: str
    thread_id: str | None = None
    message: str = Field(min_length=1, max_length=1200)
    answer: str = Field(min_length=1, max_length=4000)
    reason: str = Field(default="bad_answer", max_length=120)
    expected: str = Field(default="", max_length=1200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatFeedbackResponse(BaseModel):
    id: str
    userId: str
    threadId: str | None = None
    reason: str
    createdAt: str


class ChatThreadResponse(BaseModel):
    id: str
    userId: str
    title: str
    mode: str = "Explain"
    messageCount: int = 0
    updatedAt: str | None = None
    createdAt: str


class ChatMessageResponse(BaseModel):
    id: str
    threadId: str
    userId: str
    role: str
    content: str
    mode: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    createdAt: str


class OptionsContextResponse(BaseModel):
    ticker: str
    status: str
    provider: str
    fields_ready: list[str] = Field(default_factory=list)
    fields_pending: list[str] = Field(default_factory=list)
    message: str


class MarketQuoteResponse(BaseModel):
    ticker: str
    status: str
    provider: str
    name: str = ""
    price: float | None = None
    change: float | None = None
    changePercentage: float | None = None
    volume: float | None = None
    dayLow: float | None = None
    dayHigh: float | None = None
    yearLow: float | None = None
    yearHigh: float | None = None
    marketCap: float | None = None
    message: str = ""


class CompanyProfileResponse(BaseModel):
    ticker: str
    status: str
    provider: str
    companyName: str = ""
    sector: str = ""
    industry: str = ""
    beta: float | None = None
    marketCap: float | None = None
    website: str = ""
    image: str = ""
    description: str = ""
    message: str = ""


class MarketNewsItem(BaseModel):
    title: str
    source: str
    url: str
    publishedAt: str = ""
    summary: str = ""
    image: str = ""


class MarketNewsResponse(BaseModel):
    ticker: str
    status: str
    provider: str
    items: list[MarketNewsItem] = Field(default_factory=list)
    message: str = ""


class MarketSearchItem(BaseModel):
    symbol: str
    name: str
    exchange: str = ""
    sector: str = "Market"


class MarketSearchResponse(BaseModel):
    query: str
    status: str
    provider: str
    items: list[MarketSearchItem] = Field(default_factory=list)
    message: str = ""


class EarningsItem(BaseModel):
    date: str
    epsActual: float | None = None
    epsEstimated: float | None = None
    revenueActual: float | None = None
    revenueEstimated: float | None = None


class EarningsResponse(BaseModel):
    ticker: str
    status: str
    provider: str
    items: list[EarningsItem] = Field(default_factory=list)
    message: str = ""


class OptionsAvailabilityResponse(BaseModel):
    ticker: str
    status: str
    provider: str
    expirations: list[str] = Field(default_factory=list)
    contracts: list[dict[str, Any]] = Field(default_factory=list)
    selected: dict[str, Any] = Field(default_factory=dict)
    quote: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    earnings: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class ProviderStatus(BaseModel):
    provider: str
    configured: bool
    model: str = ""
    cooling_down: bool = False


class ReadyResponse(BaseModel):
    status: str
    environment: str
    storage: dict[str, Any]
    llm: list[ProviderStatus]
    market_data: dict[str, Any]
