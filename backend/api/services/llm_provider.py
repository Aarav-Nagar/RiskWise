from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI

from api.settings import settings


DATA_URL_RE = re.compile(r"^data:(?P<mime>image/[\w.+-]+);base64,(?P<data>.+)$", re.DOTALL)
PROVIDER_FAILURES: dict[str, float] = {}


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
        providers.append(
            {
                "provider": provider,
                "configured": configured,
                "model": model,
                "cooling_down": provider_is_cooling_down(provider),
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
    for provider in settings.llm_provider_order:
        if provider_is_cooling_down(provider):
            continue
        try:
            if provider == "gemini" and settings.gemini_api_key:
                result = await call_gemini(system_prompt, prompt, clean_attachments)
            elif provider == "openai" and settings.openai_api_key:
                result = await call_openai(system_prompt, prompt, clean_attachments)
            elif provider == "ollama" and settings.ollama_base_url and settings.ollama_model:
                result = await call_ollama(system_prompt, prompt)
            else:
                result = None
        except Exception:
            mark_provider_failed(provider)
            result = None
        if result and result.text.strip():
            PROVIDER_FAILURES.pop(provider, None)
            return result
    return None


def provider_is_cooling_down(provider: str) -> bool:
    failed_at = PROVIDER_FAILURES.get(provider)
    if not failed_at:
        return False
    return (time.monotonic() - failed_at) < settings.llm_provider_cooldown_seconds


def mark_provider_failed(provider: str) -> None:
    if provider != "fallback":
        PROVIDER_FAILURES[provider] = time.monotonic()


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
    body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": settings.llm_temperature, "num_predict": settings.llm_max_output_tokens},
    }
    async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        data = response.json()
    text = str((data.get("message") or {}).get("content") or "").strip()
    return LLMResult(text=text, provider="ollama", model=settings.ollama_model) if text else None


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
