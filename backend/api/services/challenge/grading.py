"""Two-layer Challenge grading.

Layer (a): deterministic tiered numeric check against the real risk-math
number (within 2% full credit, within 5% partial, beyond none).

Layer (b): local-embedding concept coverage — the answer is compared against
the pre-written concept anchors for its dimension using Ollama's
nomic-embed-text. When no local embedding model is reachable, a deterministic
keyword-overlap fallback keeps coverage computable offline.

A single batched LLM rubric call grades all answers together and is forced to
local Ollama only: Challenge answers are user-typed trade reasoning and must
never reach a cloud provider. If local Ollama is unavailable the response
degrades to grading_basis "concept_coverage_only" and the score is labelled a
"coverage score", never an "understanding score".
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ...probability import calendar_days_to_expiry, probability_profile
from ...settings import settings
from ..llm_provider import mark_provider_failed, mark_provider_succeeded, provider_is_cooling_down
from .anchors import CONCEPT_ANCHORS
from .embeddings import cosine, embed_texts, keyword_coverage
from .engine import challenge_verdict, dict_field, finite_number, tiered_numeric_credit

# Concept-coverage thresholds. Both are swept — never bare literals — by
# backend/api/evals/challenge_grading_eval.py over the hand-labelable fixture
# backend/api/evals/fixtures/challenge_grading_fixture.json (fixture labels are
# model-drafted and pending human review; re-run the sweep after review).
#
# COVERAGE_THRESHOLD_KEYWORD provenance: 2026-07-09 sweep on the
# keyword_overlap_fallback basis (results/challenge_grading_eval_20260709_*.md)
# scored F1 = 1.000 across the 0.15-0.20 band on the provisional labels; 0.18
# is the mid-band value.
#
# COVERAGE_THRESHOLD_EMBEDDING provenance: documented prior for nomic-embed-text
# cosine similarity — the embedding-basis sweep has NOT run yet because no local
# Ollama was reachable when the eval executed. Run challenge_grading_eval.py
# with Ollama up (it auto-detects the basis) and replace this value with the
# best-F1 threshold from that run before relying on embedding coverage.
COVERAGE_THRESHOLD_EMBEDDING = 0.55
COVERAGE_THRESHOLD_KEYWORD = 0.18
COVERAGE_PARTIAL_FACTOR = 0.8  # >= 80% of the threshold earns partial credit
# A follow-up fires only when coverage is near zero (well under partial credit).
FOLLOW_UP_COVERAGE_FACTOR = 0.5
MAX_FOLLOW_UPS = 1

FOLLOW_UP_TEMPLATES = {
    "Timing": "Your answer did not touch time decay. What happens to this option's value with each passing day, even if the stock does not move?",
    "Breakeven": "Your answer did not touch the breakeven. What price does the underlying need to reach before this position makes money at expiry?",
    "Sizing": "Your answer did not touch position size. If this premium goes to zero, what share of your account disappears?",
    "Volatility": "Your answer did not touch implied volatility. What happens to this option if IV drops after you enter?",
    "Liquidity": "Your answer did not touch liquidity. How would the bid-ask spread affect what you actually get when exiting?",
    "Exit": "Your answer did not name an exit. What specific price or condition would prove this idea wrong?",
}


async def grade_challenge(
    *,
    session: dict[str, Any],
    answers: list[dict[str, Any]],
    report: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
    prediction_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    questions = list(session.get("questions") or [])
    facts = session.get("facts") or {}
    answer_by_dimension = {
        str(item.get("dimension") or ""): str(item.get("answer") or "")
        for item in answers
        if isinstance(item, dict)
    }

    coverage_rows, coverage_basis = await coverage_for_questions(questions, answer_by_dimension)
    rubric_rows = await run_local_rubric(questions, answer_by_dimension, facts)
    grading_basis = "llm_rubric" if rubric_rows is not None else "concept_coverage_only"
    score_label = "understanding score" if grading_basis == "llm_rubric" else "coverage score"

    results: list[dict[str, Any]] = []
    question_scores: list[float] = []
    for index, question in enumerate(questions):
        dimension = str(question.get("dimension") or "")
        answer_text = answer_by_dimension.get(dimension, "")
        numeric = tiered_numeric_credit(answer_text, question.get("numeric_check"))
        coverage = coverage_rows[index]
        concept_credit = coverage["credit"]
        understanding = None
        feedback = ""
        if rubric_rows is not None:
            rubric_row = rubric_rows.get(dimension) or {}
            understanding = rubric_row.get("understanding")
            feedback = str(rubric_row.get("feedback") or "")
        concept_component = understanding if understanding is not None else concept_credit
        if numeric is not None:
            final_score = 0.5 * numeric["credit"] + 0.5 * concept_component
        else:
            final_score = concept_component
        question_scores.append(final_score)
        results.append(
            {
                "dimension": dimension,
                "question": question.get("question"),
                "answer": answer_text,
                "numeric": numeric,
                "coverage": coverage,
                "understanding": round(understanding, 4) if understanding is not None else None,
                "feedback": feedback,
                "final_score": round(final_score, 4),
            }
        )

    follow_up = pick_follow_up(results)
    lock = prediction_lock or session.get("prediction_lock") or {}
    verdict = challenge_verdict(
        question_scores,
        risk_percent_of_account=finite_number(facts.get("risk_percent_of_account")),
        profile_limit_pct=finite_number(facts.get("profile_limit_pct")),
    )
    probability = revealed_probability(report, facts)
    conviction_gap = conviction_gap_pct(lock, probability)

    return {
        "status": "ok",
        "grading_basis": grading_basis,
        "score_label": score_label,
        "coverage_basis": coverage_basis,
        "questions": results,
        "overall_score": verdict["overall_score"],
        "verdict": verdict,
        "follow_up": follow_up,
        # Revealed only now, after the full Challenge — never in the start response.
        "probability": probability,
        "prediction_lock": lock,
        "conviction_gap_pct": conviction_gap,
        "message": (
            "Graded with a local rubric plus deterministic checks."
            if grading_basis == "llm_rubric"
            else "The local rubric model was unavailable, so this is a coverage score from deterministic checks and concept coverage only."
        ),
    }


async def coverage_for_questions(
    questions: list[dict[str, Any]],
    answer_by_dimension: dict[str, str],
) -> tuple[list[dict[str, Any]], str]:
    dimensions = [str(question.get("dimension") or "") for question in questions]
    answer_texts = [answer_by_dimension.get(dimension, "") for dimension in dimensions]
    anchor_lists = [CONCEPT_ANCHORS.get(dimension, []) for dimension in dimensions]

    flat: list[str] = list(answer_texts)
    anchor_offsets: list[tuple[int, int]] = []
    for anchors in anchor_lists:
        start = len(flat)
        flat.extend(anchors)
        anchor_offsets.append((start, len(flat)))

    vectors = await embed_texts(flat) if any(text.strip() for text in answer_texts) else None
    rows: list[dict[str, Any]] = []
    if vectors is not None:
        basis = "local_embedding_nomic"
        threshold = COVERAGE_THRESHOLD_EMBEDDING
        for index in range(len(questions)):
            start, end = anchor_offsets[index]
            answer_vector = vectors[index]
            value = max((cosine(answer_vector, vectors[position]) for position in range(start, end)), default=0.0)
            if not answer_texts[index].strip():
                value = 0.0
            rows.append(coverage_row(value, threshold, basis))
    else:
        basis = "keyword_overlap_fallback"
        threshold = COVERAGE_THRESHOLD_KEYWORD
        for index in range(len(questions)):
            value = keyword_coverage(answer_texts[index], anchor_lists[index])
            rows.append(coverage_row(value, threshold, basis))
    return rows, basis


def coverage_row(value: float, threshold: float, basis: str) -> dict[str, Any]:
    if value >= threshold:
        credit = 1.0
    elif value >= threshold * COVERAGE_PARTIAL_FACTOR:
        credit = 0.5
    else:
        credit = 0.0
    return {
        "value": round(float(value), 4),
        "threshold": threshold,
        "credit": credit,
        "near_zero": value < threshold * FOLLOW_UP_COVERAGE_FACTOR,
        "basis": basis,
    }


def pick_follow_up(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """At most one templated follow-up, for the weakest near-zero-coverage answer."""
    near_zero = [row for row in results if row["coverage"]["near_zero"]]
    if not near_zero:
        return None
    weakest = min(near_zero, key=lambda row: row["coverage"]["value"])
    dimension = str(weakest["dimension"])
    return {
        "dimension": dimension,
        "question": FOLLOW_UP_TEMPLATES.get(dimension, FOLLOW_UP_TEMPLATES["Exit"]),
        "max_follow_ups": MAX_FOLLOW_UPS,
    }


async def run_local_rubric(
    questions: list[dict[str, Any]],
    answer_by_dimension: dict[str, str],
    facts: dict[str, Any],
) -> dict[str, dict[str, Any]] | None:
    """One batched rubric call, forced to local Ollama only.

    Challenge answers are user-typed trade reasoning: no cloud provider may
    ever see them, so this never routes through generate_answer's fallback
    chain. Returns None (degrade to coverage-only) when local Ollama is
    unavailable or returns an unusable rubric.
    """
    if not settings.ollama_base_url or not settings.ollama_model:
        return None
    if provider_is_cooling_down("ollama"):
        return None
    dimensions = [str(question.get("dimension") or "") for question in questions]
    payload_questions = [
        {
            "dimension": dimensions[index],
            "question": question.get("question"),
            "expected_number": (question.get("numeric_check") or {}).get("expected"),
            "answer": answer_by_dimension.get(dimensions[index], ""),
        }
        for index, question in enumerate(questions)
    ]
    system = (
        "You grade a trader's answers to risk-review questions about their own options trade. "
        "For each item, judge whether the answer shows real understanding of that risk dimension. "
        "Fluent but wrong claims get low scores. Return ONLY JSON."
    )
    prompt = json.dumps(
        {
            "trade_facts": {
                "ticker": facts.get("ticker"),
                "trading_days_left": facts.get("trading_days_left"),
                "required_move_pct": facts.get("required_move_pct"),
                "risk_percent_of_account": facts.get("risk_percent_of_account"),
                "breakeven": facts.get("breakeven"),
            },
            "items": payload_questions,
            "output_format": {
                "grades": [
                    {"dimension": "<dimension>", "understanding": "<float 0..1>", "feedback": "<one short sentence>"}
                ]
            },
        },
        ensure_ascii=True,
    )
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
            response = await client.post(
                settings.ollama_base_url.rstrip("/") + "/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "keep_alive": settings.ollama_keep_alive,
                    "options": {"temperature": 0.0, "num_predict": 500},
                },
            )
            response.raise_for_status()
            text = str((response.json().get("message") or {}).get("content") or "")
    except Exception as exc:
        mark_provider_failed("ollama", exc, started)
        return None
    rubric = parse_rubric(text, dimensions)
    if rubric is None:
        return None
    mark_provider_succeeded("ollama", started)
    return rubric


def parse_rubric(text: str, dimensions: list[str]) -> dict[str, dict[str, Any]] | None:
    """Validate the rubric strictly; a partial or malformed rubric is rejected."""
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return None
    grades = payload.get("grades") if isinstance(payload, dict) else payload
    if not isinstance(grades, list):
        return None
    parsed: dict[str, dict[str, Any]] = {}
    for row in grades:
        if not isinstance(row, dict):
            continue
        dimension = str(row.get("dimension") or "")
        understanding = finite_number(row.get("understanding"))
        if dimension in dimensions and understanding is not None and 0.0 <= understanding <= 1.0:
            parsed[dimension] = {
                "understanding": understanding,
                "feedback": str(row.get("feedback") or "")[:280],
            }
    if set(parsed) != set(dimensions):
        return None
    return parsed


def revealed_probability(report: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    structure = facts.get("structure") or {}
    if not structure:
        snapshot = dict_field(report, "contractSnapshot", "contract_snapshot")
        structure = snapshot.get("structure") if isinstance(snapshot.get("structure"), dict) else {}
    days = calendar_days_to_expiry(str(facts.get("expiration") or ""))
    return probability_profile(
        structure=structure or {},
        option_side=str(facts.get("option_side") or "call"),
        underlying_price=facts.get("underlying_price"),
        iv=facts.get("iv"),
        days_to_expiry=days,
    )


def conviction_gap_pct(prediction_lock: dict[str, Any], probability: dict[str, Any]) -> float | None:
    conviction = finite_number(prediction_lock.get("conviction_pct"))
    p_profit = finite_number(probability.get("p_profit"))
    if conviction is None or p_profit is None:
        return None
    return round(conviction - p_profit * 100, 2)
