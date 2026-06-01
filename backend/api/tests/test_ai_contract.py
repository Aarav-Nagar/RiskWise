from __future__ import annotations

import sys
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.app import app
from api.settings import settings
from api.services.llm import answer_chat, should_use_fast_path

settings.llm_provider_order = ["fallback"]


def test_llm_first_for_normal_options_questions() -> None:
    assert should_use_fast_path("What is IV crush?", "concept", None, []) is False
    assert should_use_fast_path("explain me again", "simplify", None, []) is False
    assert should_use_fast_path("Compare a long call and a debit spread", "strategy_explainer", None, []) is False
    assert should_use_fast_path("How much risk is too much?", "risk_math", None, []) is False


def test_low_quality_llm_answer_guard() -> None:
    from api.services.llm import has_any_term, is_low_quality_llm_answer

    assert is_low_quality_llm_answer("When a stock goes up, calls usually become more in-the-money", "concept") is True
    assert is_low_quality_llm_answer("IV crush is when event uncertainty leaves the option price after earnings, which can shrink premium even when direction is right.", "concept") is False
    assert has_any_term("What does diversification mean?", ["iv"]) is False
    assert has_any_term("What is IV crush?", ["iv"]) is True


def test_greeting_stays_natural_and_safe() -> None:
    response = asyncio.run(answer_chat("hi", user_profile={"experienceLevel": "Learning"}))
    answer = response["answer"].lower()

    assert response["mode"] == "greeting"
    assert "buy" not in answer
    assert "sell" not in answer
    assert "financial advice" not in answer


def test_followup_uses_recent_context() -> None:
    history = [
        {"role": "user", "content": "What is IV crush?"},
        {"role": "assistant", "content": "IV crush is when event uncertainty leaves the option price."},
    ]
    response = asyncio.run(answer_chat("make it way simpler", conversation_history=history))

    assert response["mode"] == "simplify"
    assert "option" in response["answer"].lower()
    assert "earnings" in response["answer"].lower() or "uncertainty" in response["answer"].lower()


def test_pushback_uses_recent_context() -> None:
    history = [
        {"role": "user", "content": "What is IV crush?"},
        {"role": "assistant", "content": "IV crush is when event uncertainty leaves the option price."},
    ]
    response = asyncio.run(answer_chat("no that still makes no sense", conversation_history=history))

    assert response["mode"] == "simplify"
    assert "iv" in response["answer"].lower() or "uncertainty" in response["answer"].lower()


def test_direct_how_question_is_not_misread_as_followup() -> None:
    response = asyncio.run(answer_chat("How do earnings affect calls?"))

    assert response["mode"] == "concept"
    assert "earnings" in response["answer"].lower() or "event" in response["answer"].lower()


def test_compare_debit_spread_answer_is_engine_controlled() -> None:
    response = asyncio.run(answer_chat("Compare a long call and a debit spread for earnings", chat_mode="Compare"))
    answer = response["answer"].lower()

    assert response["mode"] == "strategy_explainer"
    assert response["used_fallback"] is True
    assert "max loss is still the net debit" in answer
    assert "potential loss increases" not in answer


def test_known_iv_concept_is_engine_controlled() -> None:
    response = asyncio.run(answer_chat("What is IV crush and why can direction be right but still lose?"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert response["used_fallback"] is True
    assert "direction can be right" in answer or "stock goes up" in answer


def test_iv_question_with_risk_word_stays_iv_concept() -> None:
    response = asyncio.run(answer_chat("Explain IV crush like I am deciding whether an earnings call option is risky"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "iv" in answer or "implied volatility" in answer
    assert "profile budget" not in str(response["summary_cards"]).lower()


def test_calendar_spread_has_specific_strategy_answer() -> None:
    response = asyncio.run(answer_chat("Explain a calendar spread", chat_mode="Explain"))
    answer = response["answer"].lower()

    assert response["mode"] == "strategy_explainer"
    assert "same strike" in answer
    assert "different expirations" in answer


def test_credit_spread_not_explained_as_debit_spread() -> None:
    response = asyncio.run(answer_chat("Explain a credit spread", chat_mode="Explain"))
    answer = response["answer"].lower()

    assert response["mode"] == "strategy_explainer"
    assert "credit received" in answer
    assert "spread width minus the credit" in answer
    assert "call debit spread" not in answer


def test_put_debit_spread_not_explained_as_call_spread() -> None:
    response = asyncio.run(answer_chat("Compare a put debit spread and a long put", chat_mode="Compare"))
    answer = response["answer"].lower()

    assert response["mode"] == "strategy_explainer"
    assert "put debit spread" in answer
    assert "higher-strike put" in answer
    assert "higher-strike call" not in answer


def test_bid_ask_spread_is_liquidity_concept() -> None:
    response = asyncio.run(answer_chat("What is bid ask spread in options?"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "liquidity" in answer
    assert "bad fill" in answer


def test_assignment_risk_is_not_position_sizing() -> None:
    response = asyncio.run(answer_chat("What is assignment risk?"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "option seller" in answer
    assert "risk budget" not in answer


def test_rho_has_specific_greek_answer() -> None:
    response = asyncio.run(answer_chat("What is rho?"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "interest-rate" in answer or "interest rate" in answer
    assert "option is a bet" not in answer


def test_charm_is_delta_decay_not_volatility_skew() -> None:
    response = asyncio.run(answer_chat("What is charm in options?"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "delta" in answer
    assert "time passes" in answer
    assert "higher implied volatility" not in answer


def test_color_is_gamma_time_decay_not_generic_moneyness() -> None:
    response = asyncio.run(answer_chat("What is color in options?"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "gamma" in answer
    assert "time" in answer
    assert "in-the-money" not in answer


def test_pin_risk_is_assignment_uncertainty_not_generic_risk_math() -> None:
    response = asyncio.run(answer_chat("Explain pin risk near expiration"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "near expiration" in answer
    assert "assignment" in answer
    assert "risk budget" not in answer


def test_open_interest_and_volume_are_not_direction_claims() -> None:
    oi = asyncio.run(answer_chat("What is open interest?"))
    volume = asyncio.run(answer_chat("What is option volume?"))

    assert oi["mode"] == "concept"
    assert "contracts" in oi["answer"].lower()
    assert "remain open" in oi["answer"].lower()
    assert "does not prove direction" in oi["answer"].lower()
    assert volume["mode"] == "concept"
    assert "contracts traded today" in volume["answer"].lower()
    assert "does not say whether calls or puts are smart" in volume["answer"].lower()


def test_max_pain_and_put_call_parity_are_specific() -> None:
    max_pain = asyncio.run(answer_chat("What is max pain in options?"))
    parity = asyncio.run(answer_chat("What is put-call parity?"))

    assert max_pain["mode"] == "concept"
    assert "open interest" in max_pain["answer"].lower()
    assert "not a reliable prediction" in max_pain["answer"].lower()
    assert parity["mode"] == "concept"
    assert "pricing relationship" in parity["answer"].lower()
    assert "same strike and expiration" in str(parity["visual_blocks"]).lower()


def test_call_and_put_questions_get_specific_answers() -> None:
    call = asyncio.run(answer_chat("What is a call option?"))
    put = asyncio.run(answer_chat("What is a put option?"))

    assert call["mode"] == "concept"
    assert put["mode"] == "concept"
    assert "stock moves up" in call["answer"].lower()
    assert "stock moves down" in put["answer"].lower()
    assert "option is a bet" not in call["answer"].lower()
    assert "option is a bet" not in put["answer"].lower()


def test_covered_call_vs_cash_secured_put_is_comparative() -> None:
    response = asyncio.run(answer_chat("Compare a covered call and a cash-secured put", chat_mode="Compare"))
    answer = response["answer"].lower()

    assert response["mode"] == "strategy_explainer"
    assert "owning shares" in answer
    assert "assigned shares" in answer
    assert "cash-secured put" in response["visual_blocks"][0]["title"].lower()


def test_box_and_diagonal_spreads_are_not_debit_spread_defaults() -> None:
    box = asyncio.run(answer_chat("Explain a box spread"))
    diagonal = asyncio.run(answer_chat("Explain a diagonal spread"))

    assert box["mode"] == "strategy_explainer"
    assert "bull call spread" in box["answer"].lower()
    assert "synthetic loan" in box["answer"].lower()
    assert "long call is the cleaner upside bet" not in box["answer"].lower()
    assert diagonal["mode"] == "strategy_explainer"
    assert "different strikes and different expirations" in diagonal["answer"].lower()
    assert "long call is the cleaner upside bet" not in diagonal["answer"].lower()


def test_uncertain_reply_does_not_become_generic_lesson() -> None:
    response = asyncio.run(answer_chat("idk"))

    assert response["mode"] == "uncertain"
    assert "contract" in response["answer"].lower() or "concept" in response["answer"].lower()
    assert "an option is a bet" not in response["answer"].lower()


def test_general_finance_question_does_not_become_options_definition() -> None:
    response = asyncio.run(answer_chat("What does diversification mean?"))
    answer = response["answer"].lower()

    assert response["mode"] == "general_finance"
    assert "spread" in answer
    assert "risk" in answer
    assert "an option is a bet" not in answer


def test_missing_trade_context_is_explicit() -> None:
    response = asyncio.run(answer_chat("What is the trade I did?"))

    assert response["mode"] == "missing_trade_context"
    assert "do not see a trade attached" in response["answer"].lower()
    assert "ticker" in response["answer"].lower()


def test_saved_trade_lookup_uses_recent_saved_check() -> None:
    recent_checks = [
        {
            "id": "saved_1",
            "report": {
                "ticker": "NVDA",
                "tradeType": "Call Option (Long)",
                "strike": "140",
                "expiration": "Jun 21, 2026",
                "riskPosture": "Elevated",
                "setupScore": 68,
                "weakestLink": "IV crush",
                "riskMath": {"max_loss": 250},
            },
        }
    ]
    response = asyncio.run(answer_chat("What is the trade I did?", recent_checks=recent_checks))

    assert response["mode"] == "saved_trade_lookup"
    assert "nvda" in response["answer"].lower()
    assert "iv crush" in response["answer"].lower()
    assert response["summary_cards"]


def test_selected_trade_identity_is_not_generic_review() -> None:
    report = {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "strike": "190",
        "expiration": "Jun 21, 2026",
        "riskPosture": "Moderate",
        "setupScore": 72,
        "weakestLink": "breakeven move",
        "riskMath": {"max_loss": 180},
    }
    response = asyncio.run(answer_chat("What is the trade I did?", current_report=report))

    assert response["mode"] == "trade_identity"
    assert "aapl" in response["answer"].lower()
    assert "190" in response["answer"]
    assert "breakeven move" in response["answer"].lower()


def test_review_mode_without_trade_asks_for_context() -> None:
    response = asyncio.run(answer_chat("Is this good?", chat_mode="Review"))

    assert response["mode"] == "missing_trade_context"
    assert "ticker" in response["answer"].lower()


def test_non_image_attachment_gets_contract_field_request() -> None:
    response = asyncio.run(
        answer_chat(
            "Review this",
            attachments=[{"name": "contract.txt", "type": "text/plain", "size": 200, "text": "AAPL call"}],
        )
    )

    assert response["mode"] == "attachment_needs_details"
    assert "ticker" in response["answer"].lower()
    assert "premium" in response["answer"].lower()


def test_readable_attachment_extracts_contract_details() -> None:
    response = asyncio.run(
        answer_chat(
            "Review this uploaded contract",
            attachments=[
                {
                    "name": "contract.txt",
                    "type": "text/plain",
                    "source": "files",
                    "size": 160,
                    "text": "Ticker: AAPL\nType: Call\nStrike: 200\nExpiration: Jun 21, 2026\nPremium: 2.15",
                }
            ],
        )
    )
    answer = response["answer"].lower()

    assert response["mode"] == "attachment_needs_details"
    assert "aapl" in answer
    assert "$200" in str(response["visual_blocks"])
    assert "$2.15" in str(response["visual_blocks"])
    assert any(card["label"] == "Attachment" for card in response["summary_cards"])


def test_tool_context_creates_visible_context_block() -> None:
    response = asyncio.run(answer_chat("What is AAPL IV right now and what data do you need?"))
    blocks = str(response["visual_blocks"]).lower()

    assert response["tools_used"]
    assert "context riskwise used" in blocks
    assert "options data" in blocks
    assert "missing live data" in blocks


def test_trade_review_uses_attached_report() -> None:
    report = {
        "risk_posture": "Elevated",
        "weakest_link": "position sizing",
        "setup_score": 62,
        "risk_math": {"max_loss": 300, "required_move_to_breakeven_pct": 4.2},
    }
    response = asyncio.run(answer_chat("Explain my latest check", current_report=report, chat_mode="Review"))

    assert response["mode"] == "trade_review"
    assert "position sizing" in response["answer"].lower()
    assert response["summary_cards"]
    assert response["visual_blocks"]


def test_ready_endpoint_never_exposes_secrets() -> None:
    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert "storage" in body
    assert "llm" in body
    serialized = str(body).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized
