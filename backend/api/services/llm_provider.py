from __future__ import annotations

import base64
import re
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI

from ..settings import settings


DATA_URL_RE = re.compile(r"^data:(?P<mime>image/[\w.+-]+);base64,(?P<data>.+)$", re.DOTALL)
PROVIDER_FAILURES: dict[str, float] = {}
PROVIDER_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


def configured_providers() -> list[dict[str, Any]]:
    providers = []
    for provider in settings.llm_provider_order:
        if provider == "gemini":
            configured = bool(settings.gemini_api_key)
            model = settings.gemini_model
        elif provider == "openai":
            configured = bool(settings.openai_api_key)
            model = settings.openai_model
        elif provider == "ollama":
            configured = bool(settings.ollama_base_url and settings.ollama_model)
            model = settings.ollama_model
        elif provider == "fallback":
            configured = True
            model = "deterministic-options-coach"
        else:
            configured = False
            model = ""
        cooling_down = provider_is_cooling_down(provider)
        diagnostics = PROVIDER_DIAGNOSTICS.get(provider, {})
        if not configured:
            status = "missing_configuration"
        elif cooling_down:
            status = "cooling_down"
        elif provider == "fallback":
            status = "available"
        elif diagnostics.get("last_success_at"):
            status = "ready"
        else:
            status = "configured_unverified"
        providers.append(
            {
                "provider": provider,
                "configured": configured,
                "model": model,
                "kind": provider_kind(provider),
                "status": status,
                "cooling_down": cooling_down,
                "cooldown_remaining_seconds": cooldown_remaining_seconds(provider),
                "last_latency_ms": diagnostics.get("last_latency_ms"),
                "last_success_at": diagnostics.get("last_success_at"),
                "last_failure_at": diagnostics.get("last_failure_at"),
                "last_error": diagnostics.get("last_error", ""),
            }
        )
    return providers


async def generate_answer(
    *,
    system_prompt: str,
    prompt: str,
    attachments: list[dict[str, Any]] | None = None,
) -> LLMResult | None:
    clean_attachments = attachments or []
    has_image_attachment = any(
        str(item.get("type") or "").startswith("image/")
        and (item.get("dataUrl") or item.get("data_url"))
        for item in clean_attachments
    )
    for provider in settings.llm_provider_order:
        if has_image_attachment and provider == "ollama":
            continue
        if provider_is_cooling_down(provider):
            continue
        started = time.monotonic()
        try:
            if provider == "gemini" and settings.gemini_api_key:
                result = await call_gemini(system_prompt, prompt, clean_attachments)
            elif provider == "openai" and settings.openai_api_key:
                result = await call_openai(system_prompt, prompt, clean_attachments)
            elif provider == "ollama" and settings.ollama_base_url and settings.ollama_model:
                result = await call_ollama(system_prompt, prompt)
            else:
                result = None
        except Exception as exc:
            mark_provider_failed(provider, exc, started)
            result = None
        if result and result.text.strip():
            PROVIDER_FAILURES.pop(provider, None)
            mark_provider_succeeded(provider, started)
            return result
    return None


def provider_is_cooling_down(provider: str) -> bool:
    failed_at = PROVIDER_FAILURES.get(provider)
    if not failed_at:
        return False
    return (time.monotonic() - failed_at) < settings.llm_provider_cooldown_seconds


def cooldown_remaining_seconds(provider: str) -> int:
    failed_at = PROVIDER_FAILURES.get(provider)
    if not failed_at:
        return 0
    remaining = settings.llm_provider_cooldown_seconds - (time.monotonic() - failed_at)
    return max(0, int(round(remaining)))


def mark_provider_failed(provider: str, exc: Exception, started: float) -> None:
    if provider != "fallback":
        PROVIDER_FAILURES[provider] = time.monotonic()
    PROVIDER_DIAGNOSTICS[provider] = {
        **PROVIDER_DIAGNOSTICS.get(provider, {}),
        "last_latency_ms": elapsed_ms(started),
        "last_failure_at": utc_now(),
        "last_error": sanitize_error(exc),
    }


def mark_provider_succeeded(provider: str, started: float) -> None:
    PROVIDER_DIAGNOSTICS[provider] = {
        **PROVIDER_DIAGNOSTICS.get(provider, {}),
        "last_latency_ms": elapsed_ms(started),
        "last_success_at": utc_now(),
        "last_error": "",
    }


def elapsed_ms(started: float) -> int:
    return int(round((time.monotonic() - started) * 1000))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def provider_kind(provider: str) -> str:
    if provider == "ollama":
        return "local"
    if provider in {"gemini", "openai"}:
        return "hosted"
    if provider == "fallback":
        return "deterministic"
    return "unknown"


def sanitize_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    if not text:
        text = exc.__class__.__name__
    text = re.sub(r"(?i)(key|token|secret|apikey|api_key)=([^&\\s]+)", r"\1=<redacted>", text)
    text = re.sub(r"(?i)(bearer\\s+)[a-z0-9._\\-]+", r"\1<redacted>", text)
    return text[:220]


async def call_openai(system_prompt: str, prompt: str, attachments: list[dict[str, Any]]) -> LLMResult | None:
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_request_timeout_seconds)
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for attachment in attachments:
        data_url = attachment.get("dataUrl") or attachment.get("data_url")
        mime = str(attachment.get("type") or "")
        if data_url and mime.startswith("image/") and len(data_url) < 1_800_000:
            content.append({"type": "input_image", "image_url": data_url})

    response = await client.responses.create(
        model=settings.openai_model,
        instructions=system_prompt,
        input=[{"role": "user", "content": content}],
        max_output_tokens=settings.llm_max_output_tokens,
    )
    text = (response.output_text or "").strip()
    return LLMResult(text=text, provider="openai", model=settings.openai_model) if text else None


async def call_gemini(system_prompt: str, prompt: str, attachments: list[dict[str, Any]]) -> LLMResult | None:
    endpoint = (
        f"https://generativelanguage.googleapis.com/{settings.gemini_api_version}/models/"
        f"{settings.gemini_model}:generateContent"
    )
    parts: list[dict[str, Any]] = [{"text": f"{system_prompt.strip()}\n\nUser context and question:\n{prompt}"}]
    for attachment in attachments:
        data_url = attachment.get("dataUrl") or attachment.get("data_url")
        parsed = parse_image_data_url(data_url)
        if parsed:
            mime_type, image_data = parsed
            parts.append({"inline_data": {"mime_type": mime_type, "data": image_data}})

    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": settings.llm_temperature,
            "maxOutputTokens": settings.llm_max_output_tokens,
        },
    }
    async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
        response = await client.post(endpoint, params={"key": settings.gemini_api_key}, json=body)
        response.raise_for_status()
        data = response.json()

    text = extract_gemini_text(data)
    return LLMResult(text=text, provider="gemini", model=settings.gemini_model) if text else None


async def call_ollama(system_prompt: str, prompt: str) -> LLMResult | None:
    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    compact_system, compact_prompt = compact_ollama_prompt(system_prompt, prompt)
    body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": compact_system},
            {"role": "user", "content": compact_prompt},
        ],
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "temperature": settings.llm_temperature,
            "num_predict": min(settings.llm_max_output_tokens, 180),
            "num_ctx": 4096,
        },
    }
    async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        data = response.json()
    text = str((data.get("message") or {}).get("content") or "").strip()
    return LLMResult(text=text, provider="ollama", model=settings.ollama_model) if text else None


def compact_ollama_prompt(system_prompt: str, prompt: str) -> tuple[str, str]:
    compact_system = (
        "You are RiskWiseAI, an educational options-risk coach. Sound like a sharp human tutor in a premium chat app. "
        "Be natural, concise, specific, and risk-first. Avoid textbook openings like 'is a phenomenon' or broad definitions. "
        "Never give direct buy/sell instructions. Do not invent live prices, IV, Greeks, bid/ask, volume, "
        "open interest, or earnings dates. Use server facts when provided and say what is missing. "
        "If profile memory asks for simple, be plain. If it asks for quant-heavy, include one server-backed metric."
    )
    sections = {
        "classification": section_between(prompt, "Internal classification:", "User selected mode:", 160),
        "mode": section_between(prompt, "Mode instruction:", "Intent instruction:", 260),
        "intent": section_between(prompt, "Intent instruction:", "User profile JSON:", 360),
        "profile": section_between(prompt, "User profile JSON:", "RiskWise report JSON:", 700),
        "report": section_between(prompt, "RiskWise report JSON:", "Attachment metadata/text:", 1100),
        "tools": section_between(prompt, "Server tool results JSON. Use this instead of guessing live data:", "Recent conversation", 1400),
        "history": section_between(prompt, "Recent conversation, oldest to newest:", "User question:", 900),
        "question": section_between(prompt, "User question:", "Return only the assistant answer.", 700),
    }
    compact_prompt = (
        f"Classification: {sections['classification']}\n"
        f"Mode: {sections['mode']}\n"
        f"Intent: {sections['intent']}\n"
        f"Profile: {sections['profile']}\n"
        f"Selected report: {sections['report']}\n"
        f"Tool facts: {sections['tools']}\n"
        f"Recent conversation: {sections['history']}\n"
        f"User question: {sections['question']}\n\n"
        "Answer in 2-4 short sentences. Prefer premium, breakeven, DTE, max loss, IV, liquidity, or missing-data language when relevant. No markdown unless asked."
    )
    return compact_system, compact_prompt


def section_between(text: str, start: str, end: str, limit: int) -> str:
    if start not in text:
        return ""
    chunk = text.split(start, 1)[1]
    if end in chunk:
        chunk = chunk.split(end, 1)[0]
    return " ".join(chunk.strip().split())[:limit]


def parse_image_data_url(data_url: str | None) -> tuple[str, str] | None:
    if not data_url or len(data_url) >= 1_800_000:
        return None
    match = DATA_URL_RE.match(data_url)
    if not match:
        return None
    image_data = match.group("data")
    try:
        base64.b64decode(image_data, validate=True)
    except Exception:
        return None
    return match.group("mime"), image_data


def extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    return "\n".join(str(part.get("text") or "").strip() for part in parts if part.get("text")).strip()
