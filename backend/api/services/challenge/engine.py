"""Deterministic Challenge engine: question selection, conviction lock, verdict.

Question selection never uses an LLM. Each risk dimension gets a salience
score computed from real fields on the scored trade, the top-4 most salient
dimensions are asked, and Exit is always asked last. The user's conviction is
locked before any question is shown; the model's probability profile from
api.probability is only attached to the grading response, never to the start
response, so it cannot anchor the stated conviction.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .anchors import CONCEPT_ANCHORS

# Fixed order used both for deterministic tie-breaks and for display.
SELECTABLE_DIMENSIONS = ["Timing", "Breakeven", "Sizing", "Volatility", "Liquidity"]
QUESTIONS_PER_SESSION = 5

# Tiered numeric credit (relative to the real number): replaces a flat cutoff.
NUMERIC_FULL_CREDIT_PCT = 2.0
NUMERIC_PARTIAL_CREDIT_PCT = 5.0

# Deterministic verdict gate over the 0..1 overall score.
VERDICT_PROCEED_MIN = 0.70
VERDICT_REVISE_MIN = 0.45


def build_challenge_session(
    *,
    report: dict[str, Any],
    user_profile: dict[str, Any] | None,
    conviction_pct: float,
    direction: str,
    thesis_text: str = "",
) -> dict[str, Any]:
    facts = challenge_facts(report, user_profile)
    salience = salience_scores(facts)
    questions = select_questions(salience, facts)
    prediction_lock = {
        "conviction_pct": float(conviction_pct),
        "direction": str(direction),
        "thesis_text": str(thesis_text or ""),
        "underlying_at_lock": facts["underlying_price"],
        "breakeven": facts["breakeven"],
        "expiration": facts["expiration"],
        "locked_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "status": "ok",
        "session": {
            "ticker": facts["ticker"],
            "questions": questions,
            "salience": salience,
            "facts": facts,
            "created_at": prediction_lock["locked_at"],
        },
        "prediction_lock": prediction_lock,
        "message": (
            "Conviction is locked before the questions are shown. The model's probability profile is revealed "
            "only after the full Challenge is graded, so it cannot anchor the stated conviction."
        ),
    }


def challenge_facts(report: dict[str, Any], user_profile: dict[str, Any] | None) -> dict[str, Any]:
    risk_math = dict_field(report, "riskMath", "risk_math")
    data_quality = dict_field(report, "dataQuality", "data_quality")
    contract_label = dict_field(report, "contractLabel", "contract_label")
    snapshot = dict_field(report, "contractSnapshot", "contract_snapshot")
    profile = user_profile or {}
    risk_rules = profile.get("riskRules") or {}
    # Same profile-limit precedence as services/ai_tools.py calculate_max_loss.
    profile_limit = positive_number(risk_rules.get("maxRiskPerTradePercent")) or positive_number(profile.get("riskBudgetPercent"))
    return {
        "ticker": str(report.get("ticker") or "").upper(),
        "option_side": str(snapshot.get("option_side") or snapshot.get("optionSide") or report.get("optionSide") or "call").lower(),
        "expiration": str(report.get("expiration") or snapshot.get("expiration") or ""),
        "trading_days_left": finite_number(risk_math.get("trading_days_left")),
        "required_move_pct": finite_number(risk_math.get("required_move_to_breakeven_pct")),
        "risk_percent_of_account": finite_number(risk_math.get("risk_percent_of_account") or risk_math.get("account_risk_pct")),
        "profile_limit_pct": profile_limit,
        "max_loss": finite_number(risk_math.get("max_loss")),
        "breakeven": finite_number(risk_math.get("breakeven") or risk_math.get("breakeven_price")),
        "has_iv": bool(data_quality.get("has_iv")),
        "has_liquidity": bool(data_quality.get("has_liquidity")),
        "liquidity_risk": str(contract_label.get("liquidity_risk") or "Unknown"),
        "spread_pct": finite_number(contract_label.get("spread_pct") or snapshot.get("spread_pct")),
        "underlying_price": positive_number(
            snapshot.get("underlying_price") or snapshot.get("underlyingPrice") or report.get("underlying_price") or report.get("underlyingPrice")
        ),
        "iv": positive_number(snapshot.get("implied_volatility") or snapshot.get("impliedVolatility")),
        "structure": snapshot.get("structure") if isinstance(snapshot.get("structure"), dict) else {},
        "risk_style": str(profile.get("riskStyle") or "Balanced"),
    }


def salience_scores(facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    days = facts["trading_days_left"]
    timing = clamp01((15 - days) / 15) if days is not None else 0.5
    move = facts["required_move_pct"]
    breakeven = clamp01(move / 10) if move is not None else 0.5
    risk_pct = facts["risk_percent_of_account"]
    limit = facts["profile_limit_pct"] or 2.0
    sizing = clamp01(risk_pct / (2 * limit)) if risk_pct is not None and limit > 0 else 0.5
    volatility = 0.35 if facts["has_iv"] else 0.85
    liquidity = {"Elevated": 0.9, "Mixed": 0.6, "Better": 0.2}.get(facts["liquidity_risk"], 0.7)
    return {
        "Timing": {
            "score": round(timing, 4),
            "evidence": f"{days:g} trading day(s) left" if days is not None else "trading days left unknown",
        },
        "Breakeven": {
            "score": round(breakeven, 4),
            "evidence": f"required move to breakeven is {move:g}%" if move is not None else "required breakeven move unknown",
        },
        "Sizing": {
            "score": round(sizing, 4),
            "evidence": (
                f"{risk_pct:g}% of account at risk vs a {limit:g}% profile limit"
                if risk_pct is not None
                else "account risk percent unknown"
            ),
        },
        "Volatility": {
            "score": round(volatility, 4),
            "evidence": "implied volatility is attached" if facts["has_iv"] else "no implied volatility is attached",
        },
        "Liquidity": {
            "score": round(liquidity, 4),
            "evidence": f"liquidity risk is marked {facts['liquidity_risk']}",
        },
        "Exit": {
            "score": 1.0,
            "evidence": "exit discipline is always challenged last",
        },
    }


def select_questions(salience: dict[str, dict[str, Any]], facts: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = sorted(
        SELECTABLE_DIMENSIONS,
        key=lambda dim: (-salience[dim]["score"], SELECTABLE_DIMENSIONS.index(dim)),
    )
    selected = ranked[: QUESTIONS_PER_SESSION - 1]
    questions = [question_for_dimension(dim, facts, salience[dim]) for dim in selected]
    questions.append(question_for_dimension("Exit", facts, salience["Exit"]))
    return questions


def question_for_dimension(dimension: str, facts: dict[str, Any], salience: dict[str, Any]) -> dict[str, Any]:
    ticker = facts["ticker"] or "the underlying"
    numeric_check: dict[str, Any] | None = None
    if dimension == "Timing":
        if facts["trading_days_left"] is not None:
            question = "About how many trading days does this position have left before expiration?"
            numeric_check = numeric_check_for(facts["trading_days_left"], "trading days")
        else:
            question = "What does time decay do to this position's value as expiration approaches?"
    elif dimension == "Breakeven":
        if facts["required_move_pct"] is not None:
            question = f"Roughly what percent does {ticker} need to move for this position to break even at expiry?"
            numeric_check = numeric_check_for(facts["required_move_pct"], "percent move")
        else:
            question = "Where is this position's breakeven, and why is being right on direction not automatically enough?"
    elif dimension == "Sizing":
        if facts["risk_percent_of_account"] is not None:
            question = "About what percent of your account does this trade put at risk if the premium goes to zero?"
            numeric_check = numeric_check_for(facts["risk_percent_of_account"], "percent of account")
        else:
            question = "How much of your account is at risk on this trade, and how did you decide that size?"
    elif dimension == "Volatility":
        question = "If implied volatility drops after you enter, what happens to this option's value and why?"
    elif dimension == "Liquidity":
        if facts["spread_pct"] is not None:
            question = "Roughly what percent of this option's value is lost to the bid-ask spread on a round trip?"
            numeric_check = numeric_check_for(facts["spread_pct"], "spread percent")
        else:
            question = "How would you judge whether you can exit this contract at a fair price?"
    else:  # Exit
        question = "What exact price level or condition would tell you this trade idea is wrong, and what would you do then?"
    return {
        "dimension": dimension,
        "question": question,
        "numeric_check": numeric_check,
        "salience": salience["score"],
        "evidence": salience["evidence"],
        "concept_anchor_count": len(CONCEPT_ANCHORS[dimension]),
    }


def numeric_check_for(expected: float, unit: str) -> dict[str, Any]:
    return {
        "expected": round(float(expected), 4),
        "unit": unit,
        "full_credit_within_pct": NUMERIC_FULL_CREDIT_PCT,
        "partial_credit_within_pct": NUMERIC_PARTIAL_CREDIT_PCT,
    }


def tiered_numeric_credit(answer_text: str, numeric_check: dict[str, Any] | None) -> dict[str, Any] | None:
    """Tiered credit against the real number: within 2% full, within 5% partial."""
    if not numeric_check:
        return None
    expected = finite_number(numeric_check.get("expected"))
    if expected is None:
        return None
    found = closest_number(answer_text, expected)
    if found is None:
        return {"expected": expected, "found": None, "credit": 0.0, "tier": "no_number_in_answer"}
    if expected == 0:
        error_pct = None
        distance = abs(found)
        tier = "full" if distance <= 0.02 else "partial" if distance <= 0.05 else "none"
    else:
        error_pct = abs(found - expected) / abs(expected) * 100
        tier = (
            "full"
            if error_pct <= NUMERIC_FULL_CREDIT_PCT
            else "partial"
            if error_pct <= NUMERIC_PARTIAL_CREDIT_PCT
            else "none"
        )
    credit = {"full": 1.0, "partial": 0.5, "none": 0.0}[tier]
    return {
        "expected": expected,
        "found": found,
        "error_pct": round(error_pct, 2) if error_pct is not None else None,
        "credit": credit,
        "tier": tier,
    }


def closest_number(text: str, expected: float) -> float | None:
    import re

    numbers = [float(match) for match in re.findall(r"[-+]?\d*\.?\d+", str(text or ""))]
    numbers = [value for value in numbers if math.isfinite(value)]
    if not numbers:
        return None
    return min(numbers, key=lambda value: abs(value - expected))


def challenge_verdict(
    question_scores: list[float],
    *,
    risk_percent_of_account: float | None,
    profile_limit_pct: float | None,
) -> dict[str, Any]:
    """Deterministic gate over the sub-scores, hard-capped by real risk math."""
    if question_scores:
        overall = sum(question_scores) / len(question_scores)
    else:
        overall = 0.0
    if overall >= VERDICT_PROCEED_MIN:
        verdict = "Proceed"
    elif overall >= VERDICT_REVISE_MIN:
        verdict = "Revise"
    else:
        verdict = "Reconsider"
    hard_cap_applied = False
    if (
        risk_percent_of_account is not None
        and profile_limit_pct is not None
        and risk_percent_of_account > profile_limit_pct
        and verdict == "Proceed"
    ):
        # Above the profile risk limit the verdict can never read better than Revise.
        verdict = "Revise"
        hard_cap_applied = True
    return {
        "verdict": verdict,
        "overall_score": round(overall, 4),
        "hard_cap_applied": hard_cap_applied,
        "hard_cap_reason": (
            f"risk {risk_percent_of_account:g}% of account exceeds the {profile_limit_pct:g}% profile limit"
            if hard_cap_applied
            else ""
        ),
        "gate": {"proceed_min": VERDICT_PROCEED_MIN, "revise_min": VERDICT_REVISE_MIN},
    }


def dict_field(report: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = report.get(key)
        if isinstance(value, dict):
            return value
    return {}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def positive_number(value: Any) -> float | None:
    number = finite_number(value)
    return number if number is not None and number > 0 else None


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
