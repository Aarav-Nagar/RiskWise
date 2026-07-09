from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "mobile-demo"
DEFAULT_API_BASE_URL = "https://riskwise-api.onrender.com"


def fetch_json(url: str, timeout: float) -> tuple[int | None, dict[str, Any] | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, str(exc)
    except Exception as exc:  # noqa: BLE001 - verifier must report all deployment failures.
        return None, None, str(exc)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def env_file_keys(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def classify_clerk_key(value: str) -> str:
    if not value:
        return "missing"
    if value.startswith("pk_live_") or value.startswith("sk_live_"):
        return "production"
    if value.startswith("pk_test_") or value.startswith("sk_test_") or "accounts.dev" in value:
        return "development"
    return "unknown"


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str, required: bool = True) -> None:
    checks.append({"name": name, "passed": passed, "required": required, "detail": detail})


def verify_live_api(api_base_url: str, timeout: float, strict: bool, checks: list[dict[str, Any]]) -> None:
    endpoints = {
        "health": "/health",
        "ready": "/ready",
        "market_providers": "/market/providers",
        "ai_providers": "/ai/providers",
    }
    responses: dict[str, dict[str, Any]] = {}

    for name, path in endpoints.items():
        status, payload, error = fetch_json(f"{api_base_url.rstrip('/')}{path}", timeout)
        add_check(
            checks,
            f"live_{name}_reachable",
            status == 200 and payload is not None,
            f"status={status or 'none'} error={error or ''}".strip(),
        )
        responses[name] = {"status": status, "payload": payload or {}, "error": error}

    ready = responses["ready"]["payload"]
    storage = ready.get("storage") or {}
    market = ready.get("market_data") or {}
    auth = ready.get("auth") or {}
    llm = ready.get("llm") or []

    add_check(
        checks,
        "live_storage_mongo_ready",
        storage.get("provider") == "mongo" and storage.get("ready") is True,
        f"provider={storage.get('provider')} ready={storage.get('ready')}",
    )
    add_check(
        checks,
        "live_market_not_disabled",
        market.get("status") == "active",
        f"status={market.get('status')} strategy={market.get('strategy')}",
    )
    add_check(
        checks,
        "live_yfinance_delayed_active",
        any(provider.get("provider") == "yfinance_delayed" and provider.get("configured") for provider in market.get("providers", [])),
        "delayed yfinance provider should be configured for internal TestFlight fallback",
    )
    add_check(
        checks,
        "live_auth_configured",
        auth.get("configured") is True and auth.get("issuer_configured") is True and auth.get("jwks_configured") is True,
        f"configured={auth.get('configured')} issuer={auth.get('issuer_configured')} jwks={auth.get('jwks_configured')}",
    )

    hosted_llm_ready = any(
        provider.get("provider") != "fallback" and provider.get("status") == "available" for provider in llm
    )
    add_check(
        checks,
        "live_hosted_llm_ready",
        hosted_llm_ready,
        "strict production should have Gemini or OpenAI available; fallback-only is internal-beta only",
        required=strict,
    )
    add_check(
        checks,
        "live_sentry_configured",
        market.get("sentry_configured") is True,
        f"sentry_configured={market.get('sentry_configured')}",
        required=strict,
    )
    add_check(
        checks,
        "live_auth_authorized_parties_configured",
        auth.get("authorized_parties_configured") is True,
        f"authorized_parties_configured={auth.get('authorized_parties_configured')}",
        required=strict,
    )


def verify_local_config(strict: bool, checks: list[dict[str, Any]]) -> None:
    eas = load_json(FRONTEND / "eas.json")
    production_env = eas.get("build", {}).get("production", {}).get("env", {})
    testflight_env = eas.get("build", {}).get("testflight", {}).get("env", {})

    add_check(
        checks,
        "eas_production_api_base_url",
        production_env.get("EXPO_PUBLIC_API_BASE_URL", "").startswith("https://"),
        f"value={production_env.get('EXPO_PUBLIC_API_BASE_URL', '')}",
    )
    add_check(
        checks,
        "eas_production_clerk_guard_enabled",
        production_env.get("RISKWISE_REQUIRE_PRODUCTION_CLERK") == "true",
        f"value={production_env.get('RISKWISE_REQUIRE_PRODUCTION_CLERK', '')}",
    )
    add_check(
        checks,
        "eas_testflight_dev_clerk_labeled_internal",
        str(testflight_env.get("EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY", "")).startswith("pk_test_"),
        "testflight may use dev Clerk only for internal testing",
        required=False,
    )

    local_keys = env_file_keys(ROOT / "config" / ".env")
    local_publishable_kind = classify_clerk_key(local_keys.get("EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY", ""))
    local_secret_kind = classify_clerk_key(local_keys.get("CLERK_SECRET_KEY", ""))
    local_issuer = local_keys.get("CLERK_ISSUER", "")

    add_check(
        checks,
        "local_clerk_publishable_is_production",
        local_publishable_kind == "production",
        f"kind={local_publishable_kind}",
        required=strict,
    )
    add_check(
        checks,
        "local_clerk_secret_is_production",
        local_secret_kind == "production",
        f"kind={local_secret_kind}",
        required=strict,
    )
    add_check(
        checks,
        "local_clerk_issuer_is_not_dev",
        bool(local_issuer) and "accounts.dev" not in local_issuer,
        f"kind={'development' if 'accounts.dev' in local_issuer else 'maybe_production' if local_issuer else 'missing'}",
        required=strict,
    )

    for env_name in ("CLERK_AUTHORIZED_PARTIES", "GEMINI_API_KEY", "OPENAI_API_KEY", "SENTRY_DSN"):
        add_check(
            checks,
            f"local_{env_name.lower()}_present",
            bool(local_keys.get(env_name)),
            "present" if local_keys.get(env_name) else "missing",
            required=False,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify RiskWise deployed production state without printing secrets.")
    parser.add_argument("--api-base-url", default=os.getenv("RISKWISE_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on public App Store blockers such as fallback-only AI, missing Sentry, and dev Clerk.",
    )
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    verify_live_api(args.api_base_url, args.timeout, args.strict, checks)
    verify_local_config(args.strict, checks)

    failed_required = [check for check in checks if check["required"] and not check["passed"]]
    payload = {
        "passed": not failed_required,
        "mode": "strict" if args.strict else "internal_beta",
        "api_base_url": args.api_base_url,
        "checks": checks,
        "failed_required": [check["name"] for check in failed_required],
    }
    print(json.dumps(payload, indent=2))
    return 1 if failed_required else 0


if __name__ == "__main__":
    raise SystemExit(main())
