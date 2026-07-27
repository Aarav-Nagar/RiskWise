"""Local embedding client for Challenge concept coverage.

Uses Ollama's nomic-embed-text (settings.ollama_embed_model) and pulls the
model automatically the first time it is missing. Challenge content is
user-typed trade reasoning, so nothing here may ever route to a cloud
provider — if the local model is unreachable the caller degrades to the
deterministic keyword fallback below.
"""

from __future__ import annotations

import math
import re

import httpx

from ...settings import settings

_MODEL_PULL_ATTEMPTED = False
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was", "be",
    "it", "its", "this", "that", "as", "at", "by", "with", "from", "before", "after", "when",
    "i", "my", "me", "you", "your", "we", "they", "will", "would", "can", "could", "should",
    "has", "have", "had", "not", "no", "so", "if", "than", "then", "there", "their", "them",
    "one", "still", "into", "out", "up", "down", "over", "means", "every",
}


async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Embed a batch of texts with the local Ollama embed model.

    Returns None when the local model is unreachable — never raises to the
    caller and never falls back to a hosted provider.
    """
    if not texts or not settings.ollama_base_url:
        return None
    base = settings.ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
            vectors = await _embed_batch(client, base, texts)
            if vectors is None and await _pull_embed_model(client, base):
                vectors = await _embed_batch(client, base, texts)
            return vectors
    except Exception:
        return None


async def _embed_batch(client: httpx.AsyncClient, base: str, texts: list[str]) -> list[list[float]] | None:
    # Newer Ollama batch endpoint first, then the legacy per-prompt endpoint.
    try:
        response = await client.post(f"{base}/api/embed", json={"model": settings.ollama_embed_model, "input": texts})
        if response.status_code == 404:
            return await _embed_legacy(client, base, texts)
        response.raise_for_status()
        embeddings = response.json().get("embeddings")
        if isinstance(embeddings, list) and len(embeddings) == len(texts):
            return [list(map(float, row)) for row in embeddings]
        return None
    except httpx.HTTPStatusError:
        return None


async def _embed_legacy(client: httpx.AsyncClient, base: str, texts: list[str]) -> list[list[float]] | None:
    vectors: list[list[float]] = []
    for text in texts:
        response = await client.post(
            f"{base}/api/embeddings",
            json={"model": settings.ollama_embed_model, "prompt": text},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        embedding = response.json().get("embedding")
        if not isinstance(embedding, list):
            return None
        vectors.append(list(map(float, embedding)))
    return vectors


async def _pull_embed_model(client: httpx.AsyncClient, base: str) -> bool:
    """Pull the embed model once per process if it is not present locally."""
    global _MODEL_PULL_ATTEMPTED
    if _MODEL_PULL_ATTEMPTED:
        return False
    _MODEL_PULL_ATTEMPTED = True
    try:
        response = await client.post(
            f"{base}/api/pull",
            json={"name": settings.ollama_embed_model, "stream": False},
            timeout=300.0,
        )
        return response.status_code == 200
    except Exception:
        return False


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def keyword_coverage(answer: str, anchors: list[str]) -> float:
    """Deterministic no-model fallback: best content-word overlap with any anchor."""
    answer_tokens = content_tokens(answer)
    if not answer_tokens:
        return 0.0
    best = 0.0
    for anchor in anchors:
        anchor_tokens = content_tokens(anchor)
        if not anchor_tokens:
            continue
        best = max(best, len(answer_tokens & anchor_tokens) / len(anchor_tokens))
    return round(best, 4)


def content_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", str(text or "").lower())
    return {word for word in words if len(word) >= 3 and word not in STOPWORDS}
