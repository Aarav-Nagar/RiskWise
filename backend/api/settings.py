from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ENV = PROJECT_ROOT / "config" / ".env"

if CONFIG_ENV.exists():
    load_dotenv(CONFIG_ENV)


class Settings:
    storage_provider = os.getenv("APP_STORAGE_PROVIDER", "demo").lower()
    mongodb_uri = os.getenv("MONGODB_URI", "")
    mongodb_database = os.getenv("MONGODB_DATABASE", "finance_app")
    clerk_secret_key = os.getenv("CLERK_SECRET_KEY", "")
    clerk_issuer = os.getenv("CLERK_ISSUER", "").rstrip("/")
    clerk_jwks_url = os.getenv("CLERK_JWKS_URL", "").strip()
    clerk_audience = os.getenv("CLERK_AUDIENCE", "").strip()
    clerk_authorized_parties = [
        item.strip()
        for item in os.getenv("CLERK_AUTHORIZED_PARTIES", "").split(",")
        if item.strip()
    ]
    clerk_jwt_leeway_seconds = int(os.getenv("CLERK_JWT_LEEWAY_SECONDS", "10"))
    llm_provider_order = [
        item.strip().lower()
        for item in os.getenv("LLM_PROVIDER_ORDER", "ollama,gemini,openai,fallback").split(",")
        if item.strip()
    ]
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_model = os.getenv("OPENAI_MODEL", "") or "gpt-5-mini"
    openai_chat_timeout_seconds = float(os.getenv("OPENAI_CHAT_TIMEOUT_SECONDS", "6.0"))
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "") or "gemini-2.5-flash"
    gemini_api_version = os.getenv("GEMINI_API_VERSION", "v1beta")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "") or "qwen2.5:7b-instruct"
    llm_request_timeout_seconds = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30.0"))
    llm_provider_cooldown_seconds = float(os.getenv("LLM_PROVIDER_COOLDOWN_SECONDS", "300"))
    llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.35"))
    llm_max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "360"))
    ollama_keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
    sentry_dsn = os.getenv("SENTRY_DSN", "")
    environment = os.getenv("APP_ENV", "development")
    allowed_cors_origins = [
        item.strip()
        for item in os.getenv(
            "FRONTEND_ALLOWED_ORIGINS",
            "http://127.0.0.1:8081,http://localhost:8081,http://127.0.0.1:8091,http://localhost:8091,http://127.0.0.1:8092,http://localhost:8092",
        ).split(",")
        if item.strip()
    ]
    market_data_provider = os.getenv("MARKET_DATA_PROVIDER", "hybrid").lower()
    fmp_api_key = os.getenv("FMP_API_KEY", "")
    alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    enable_yfinance_options = os.getenv("ENABLE_YFINANCE_OPTIONS", "true").strip().lower() in {"1", "true", "yes", "on"}
    polygon_api_key = os.getenv("POLYGON_API_KEY", "") or os.getenv("MASSIVE_API_KEY", "")
    polygon_base_url = os.getenv("POLYGON_BASE_URL", "https://api.polygon.io").rstrip("/")
    massive_base_url = os.getenv("MASSIVE_BASE_URL", "https://api.massive.com").rstrip("/")
    rate_limit_window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    rate_limit_chat = int(os.getenv("RATE_LIMIT_CHAT", "45"))
    rate_limit_trade_check = int(os.getenv("RATE_LIMIT_TRADE_CHECK", "90"))
    rate_limit_market = int(os.getenv("RATE_LIMIT_MARKET", "180"))
    market_cache_seconds = int(os.getenv("MARKET_CACHE_SECONDS", "300"))


settings = Settings()
