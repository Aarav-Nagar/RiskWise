import asyncio
import json
from datetime import date, timedelta

from fastapi.testclient import TestClient

from api.app import app
from api.services.challenge import build_challenge_session, grade_challenge
from api.services.challenge.engine import tiered_numeric_credit
from api.services.challenge.grading import parse_rubric


client = TestClient(app)

EXPIRATION = (date.today() + timedelta(days=30)).isoformat()
PROFILE = {"riskStyle": "Balanced", "riskRules": {"maxRiskPerTradePercent": 2.0}}


def challenge_report() -> dict:
    return {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "expiration": EXPIRATION,
        "riskMath": {
            "trading_days_left": 19,
            "required_move_to_breakeven_pct": 4.2,
            "risk_percent_of_account": 4.0,
            "max_loss": 1000,
            "breakeven": 105.0,
        },
        "dataQuality": {"has_iv": True, "has_liquidity": True},
        "contractLabel": {"liquidity_risk": "Mixed", "spread_pct": 6.0},
        "contractSnapshot": {
            "option_side": "call",
            "underlying_price": 100.0,
            "implied_volatility": 0.30,
            "structure": {"kind": "long_option", "breakeeven": None, "breakeven": 105.0, "primary_strike": 100.0},
        },
    }


def good_answers() -> list[dict]:
    return [
        {"dimension": "Sizing", "answer": "About 4 percent of the account is at risk; the max loss is the full premium paid and it should stay inside my percent limit."},
        {"dimension": "Liquidity", "answer": "Roughly 6 percent is lost to the wide bid ask spread, and low open interest and volume make it hard to exit at a fair price."},
        {"dimension": "Breakeven", "answer": "It needs to move about 4.2 percent past the breakeven price before the position makes money at expiry, since the premium paid must be covered."},
        {"dimension": "Volatility", "answer": "If implied volatility drops the premium shrinks even when the stock moves the right way — IV crush after an event."},
        {"dimension": "Exit", "answer": "A close below 95 is the specific price level and condition where I accept the loss; that exit plan is set before entry."},
    ]


def build_session() -> dict:
    return build_challenge_session(
        report=challenge_report(),
        user_profile=PROFILE,
        conviction_pct=80,
        direction="bullish",
        thesis_text="Product cycle drives the stock up before expiry.",
    )


def no_local_models(monkeypatch) -> None:
    async def no_embeddings(texts):
        return None

    async def no_rubric(questions, answers, facts):
        return None

    monkeypatch.setattr("api.services.challenge.grading.embed_texts", no_embeddings)
    monkeypatch.setattr("api.services.challenge.grading.run_local_rubric", no_rubric)


# --- deterministic question selection ---


def test_selects_top_four_salient_dimensions_plus_exit_last() -> None:
    started = build_session()
    questions = started["session"]["questions"]
    assert len(questions) == 5
    dimensions = [item["dimension"] for item in questions]
    # Salience from the real fields: Sizing 4% vs 2% limit -> 1.0, Liquidity Mixed -> 0.6,
    # Breakeven 4.2%/10 -> 0.42, Volatility (IV attached) -> 0.35, Timing 19 days -> 0.0 (dropped).
    assert dimensions == ["Sizing", "Liquidity", "Breakeven", "Volatility", "Exit"]
    assert dimensions[-1] == "Exit"
    assert "Timing" not in dimensions

    by_dim = {item["dimension"]: item for item in questions}
    assert by_dim["Sizing"]["numeric_check"]["expected"] == 4.0
    assert by_dim["Breakeven"]["numeric_check"]["expected"] == 4.2
    assert by_dim["Liquidity"]["numeric_check"]["expected"] == 6.0
    assert by_dim["Volatility"]["numeric_check"] is None
    assert by_dim["Exit"]["numeric_check"] is None


def test_short_dated_trade_makes_timing_salient() -> None:
    report = challenge_report()
    report["riskMath"]["trading_days_left"] = 3
    started = build_challenge_session(report=report, user_profile=PROFILE, conviction_pct=50, direction="bullish")
    dimensions = [item["dimension"] for item in started["session"]["questions"]]
    assert "Timing" in dimensions
    assert dimensions[-1] == "Exit"


def test_start_never_reveals_probability_profile() -> None:
    started = build_session()
    serialized = json.dumps(started)
    assert "p_profit" not in serialized
    assert "p_max_loss" not in serialized
    lock = started["prediction_lock"]
    assert lock["conviction_pct"] == 80
    assert lock["direction"] == "bullish"
    assert lock["underlying_at_lock"] == 100.0
    assert lock["breakeven"] == 105.0
    assert lock["locked_at"]


# --- tiered numeric credit ---


def test_tiered_numeric_credit_tiers() -> None:
    check = {"expected": 19}
    assert tiered_numeric_credit("about 19 trading days", check)["tier"] == "full"
    assert tiered_numeric_credit("19.2 days", check)["tier"] == "full"  # 1.05% off
    assert tiered_numeric_credit("maybe 18.5", check)["tier"] == "partial"  # 2.6% off
    assert tiered_numeric_credit("like 25 days", check)["tier"] == "none"
    no_number = tiered_numeric_credit("no idea honestly", check)
    assert no_number["tier"] == "no_number_in_answer"
    assert no_number["credit"] == 0.0
    assert tiered_numeric_credit("whatever", None) is None


def test_numeric_credit_guards_zero_expected() -> None:
    check = {"expected": 0}
    assert tiered_numeric_credit("0", check)["tier"] == "full"
    assert tiered_numeric_credit("0.04", check)["tier"] == "partial"
    assert tiered_numeric_credit("2", check)["tier"] == "none"


# --- grading: coverage-only degrade path (no local models) ---


def test_grading_degrades_to_coverage_only_without_ollama(monkeypatch) -> None:
    no_local_models(monkeypatch)
    started = build_session()
    result = asyncio.run(
        grade_challenge(
            session=started["session"],
            answers=good_answers(),
            report=challenge_report(),
            user_profile=PROFILE,
            prediction_lock=started["prediction_lock"],
        )
    )
    assert result["grading_basis"] == "concept_coverage_only"
    assert result["score_label"] == "coverage score"
    assert result["coverage_basis"] == "keyword_overlap_fallback"
    assert "understanding" not in result["score_label"]
    for row in result["questions"]:
        assert row["understanding"] is None
        assert 0.0 <= row["final_score"] <= 1.0
    # Good on-topic answers should clear the keyword coverage threshold.
    by_dim = {row["dimension"]: row for row in result["questions"]}
    assert by_dim["Breakeven"]["coverage"]["credit"] == 1.0
    assert by_dim["Breakeven"]["numeric"]["tier"] == "full"
    # Probability is revealed only now, and the conviction gap is computed.
    assert result["probability"]["status"] == "ok"
    assert result["probability"]["basis"] == "delayed_iv_black_scholes"
    assert result["conviction_gap_pct"] is not None


def test_grading_uses_llm_rubric_when_local_ollama_succeeds(monkeypatch) -> None:
    async def no_embeddings(texts):
        return None

    async def fake_rubric(questions, answers, facts):
        return {
            str(question["dimension"]): {"understanding": 0.9, "feedback": "Solid grasp of the risk."}
            for question in questions
        }

    monkeypatch.setattr("api.services.challenge.grading.embed_texts", no_embeddings)
    monkeypatch.setattr("api.services.challenge.grading.run_local_rubric", fake_rubric)
    started = build_session()
    result = asyncio.run(
        grade_challenge(
            session=started["session"],
            answers=good_answers(),
            report=challenge_report(),
            user_profile=PROFILE,
            prediction_lock=started["prediction_lock"],
        )
    )
    assert result["grading_basis"] == "llm_rubric"
    assert result["score_label"] == "understanding score"
    assert all(row["understanding"] == 0.9 for row in result["questions"])
    assert all(row["feedback"] for row in result["questions"])


def test_embedding_coverage_path(monkeypatch) -> None:
    async def fake_embeddings(texts):
        # Identical vectors -> cosine 1.0 for every answer/anchor pair.
        return [[1.0, 0.5, 0.25] for _ in texts]

    async def no_rubric(questions, answers, facts):
        return None

    monkeypatch.setattr("api.services.challenge.grading.embed_texts", fake_embeddings)
    monkeypatch.setattr("api.services.challenge.grading.run_local_rubric", no_rubric)
    started = build_session()
    result = asyncio.run(
        grade_challenge(
            session=started["session"],
            answers=good_answers(),
            report=challenge_report(),
            user_profile=PROFILE,
        )
    )
    assert result["coverage_basis"] == "local_embedding_nomic"
    assert all(row["coverage"]["credit"] == 1.0 for row in result["questions"])
    assert result["follow_up"] is None


# --- follow-up: max 1, only on near-zero coverage ---


def test_single_follow_up_for_weakest_near_zero_answer(monkeypatch) -> None:
    no_local_models(monkeypatch)
    started = build_session()
    answers = good_answers()
    answers[0]["answer"] = "I like turtles."  # Sizing: off-topic
    answers[3]["answer"] = "banana"  # Volatility: off-topic
    result = asyncio.run(
        grade_challenge(
            session=started["session"],
            answers=answers,
            report=challenge_report(),
            user_profile=PROFILE,
        )
    )
    follow_up = result["follow_up"]
    assert follow_up is not None
    assert follow_up["max_follow_ups"] == 1
    assert follow_up["dimension"] in {"Sizing", "Volatility"}
    assert follow_up["question"]
    # Only one follow-up, ever, no matter how many answers were empty.
    assert isinstance(follow_up, dict)


# --- verdict gate and risk-math hard cap ---


def test_verdict_hard_capped_at_revise_when_over_profile_limit(monkeypatch) -> None:
    async def no_embeddings(texts):
        return None

    async def perfect_rubric(questions, answers, facts):
        return {str(q["dimension"]): {"understanding": 1.0, "feedback": "Perfect."} for q in questions}

    monkeypatch.setattr("api.services.challenge.grading.embed_texts", no_embeddings)
    monkeypatch.setattr("api.services.challenge.grading.run_local_rubric", perfect_rubric)
    started = build_session()
    answers = [
        {"dimension": item["dimension"], "answer": f"exactly {(item.get('numeric_check') or {}).get('expected', '')} as computed"}
        for item in started["session"]["questions"]
    ]
    result = asyncio.run(
        grade_challenge(
            session=started["session"],
            answers=answers,
            report=challenge_report(),
            user_profile=PROFILE,
        )
    )
    # 4% risk vs 2% limit: even perfect grading can never read better than Revise.
    assert result["verdict"]["overall_score"] >= 0.7
    assert result["verdict"]["verdict"] == "Revise"
    assert result["verdict"]["hard_cap_applied"] is True
    assert "exceeds" in result["verdict"]["hard_cap_reason"]


def test_verdict_proceed_allowed_when_within_profile_limit(monkeypatch) -> None:
    async def no_embeddings(texts):
        return None

    async def perfect_rubric(questions, answers, facts):
        return {str(q["dimension"]): {"understanding": 1.0, "feedback": "Perfect."} for q in questions}

    monkeypatch.setattr("api.services.challenge.grading.embed_texts", no_embeddings)
    monkeypatch.setattr("api.services.challenge.grading.run_local_rubric", perfect_rubric)
    report = challenge_report()
    report["riskMath"]["risk_percent_of_account"] = 1.5
    started = build_challenge_session(report=report, user_profile=PROFILE, conviction_pct=60, direction="bullish")
    answers = [
        {"dimension": item["dimension"], "answer": f"exactly {(item.get('numeric_check') or {}).get('expected', '')} as computed"}
        for item in started["session"]["questions"]
    ]
    result = asyncio.run(
        grade_challenge(session=started["session"], answers=answers, report=report, user_profile=PROFILE)
    )
    assert result["verdict"]["verdict"] == "Proceed"
    assert result["verdict"]["hard_cap_applied"] is False


# --- rubric parsing is strict ---


def test_parse_rubric_rejects_partial_or_invalid_output() -> None:
    dimensions = ["Sizing", "Exit"]
    valid = json.dumps(
        {
            "grades": [
                {"dimension": "Sizing", "understanding": 0.8, "feedback": "ok"},
                {"dimension": "Exit", "understanding": 0.4, "feedback": "vague"},
            ]
        }
    )
    parsed = parse_rubric(valid, dimensions)
    assert parsed is not None
    assert parsed["Sizing"]["understanding"] == 0.8

    missing_dimension = json.dumps({"grades": [{"dimension": "Sizing", "understanding": 0.8, "feedback": "ok"}]})
    assert parse_rubric(missing_dimension, dimensions) is None

    out_of_range = json.dumps(
        {
            "grades": [
                {"dimension": "Sizing", "understanding": 1.8, "feedback": "ok"},
                {"dimension": "Exit", "understanding": 0.4, "feedback": "ok"},
            ]
        }
    )
    assert parse_rubric(out_of_range, dimensions) is None
    assert parse_rubric("not json at all", dimensions) is None


# --- endpoints ---


def make_user(clerk_id: str, email: str) -> dict:
    response = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": clerk_id,
            "name": "Challenge Tester",
            "email": email,
            "accountSize": 25000,
            "riskBudgetPercent": 2,
            "riskStyle": "Balanced",
            "experienceLevel": "Some experience",
            "purpose": [],
            "tradeFocus": [],
            "struggles": [],
            "reminders": [],
            "sectors": [],
            "marketCaps": [],
            "events": [],
            "safetyAccepted": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_challenge_endpoints_roundtrip(monkeypatch) -> None:
    no_local_models(monkeypatch)
    user = make_user("clerk_challenge", "challenge-tester@example.com")

    start = client.post(
        "/challenge/start",
        json={
            "user_id": user["id"],
            "report": challenge_report(),
            "conviction_pct": 70,
            "direction": "bullish",
            "thesis_text": "Momentum into the product event.",
        },
    )
    assert start.status_code == 200
    started = start.json()
    assert len(started["session"]["questions"]) == 5
    assert "p_profit" not in json.dumps(started), "start must not reveal the probability profile"

    grade = client.post(
        "/challenge/grade",
        json={
            "user_id": user["id"],
            "report": challenge_report(),
            "session": started["session"],
            "answers": good_answers(),
            "prediction_lock": started["prediction_lock"],
        },
    )
    assert grade.status_code == 200
    graded = grade.json()
    assert graded["grading_basis"] == "concept_coverage_only"
    assert graded["score_label"] == "coverage score"
    assert graded["probability"]["basis"] == "delayed_iv_black_scholes"
    assert graded["verdict"]["verdict"] in {"Proceed", "Revise", "Reconsider"}
    assert graded["prediction_lock"]["conviction_pct"] == 70
