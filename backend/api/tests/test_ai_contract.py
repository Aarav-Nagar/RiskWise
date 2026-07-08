from __future__ import annotations

import sys
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.app import app
from api.settings import settings
from api.services.ai_tools import build_ai_tool_context, calculate_dte, calculate_liquidity_score, calculate_max_loss
from api.services.llm import answer_chat, extract_contract_from_uploads, should_use_fast_path

settings.llm_provider_order = ["fallback"]


def selected_trade_fixture() -> dict:
    return {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "strike": 200,
        "expiration": "2026-06-21",
        "amountAtRisk": 215,
        "setupScore": 62,
        "riskPosture": "Elevated",
        "weakestLink": "breakeven move",
        "riskMath": {
            "max_loss": 215,
            "required_move_to_breakeven_pct": 3.4,
            "calendar_days_left": 3,
            "account_risk_pct": 4.3,
        },
        "setupDebate": {
            "bull_case": "Defined premium risk and a clear upside thesis.",
            "bear_case": "Short expiration leaves little time to beat breakeven.",
            "risk_judge": "The setup depends on a fast move plus clean liquidity.",
        },
        "contractSnapshot": {"bid": None, "ask": None, "openInterest": None, "contractVolume": None},
    }


def test_llm_first_for_normal_options_questions() -> None:
    assert should_use_fast_path("What is IV crush?", "concept", None, []) is True
    assert should_use_fast_path("What is AAPL IV today?", "concept", None, []) is False
    assert should_use_fast_path("explain me again", "simplify", None, []) is True
    assert should_use_fast_path("Compare a long call and a debit spread", "strategy_explainer", None, []) is True
    assert should_use_fast_path("How much risk is too much?", "risk_math", None, []) is True


def test_low_quality_llm_answer_guard() -> None:
    from api.services.llm import has_any_term, is_low_quality_llm_answer

    assert is_low_quality_llm_answer("When a stock goes up, calls usually become more in-the-money", "concept") is True
    assert is_low_quality_llm_answer("IV crush is when event uncertainty leaves the option price after earnings, which can shrink premium even when direction is right.", "concept") is False
    assert has_any_term("What does diversification mean?", ["iv"]) is False
    assert has_any_term("What is IV crush?", ["iv"]) is True


def test_model_answer_quality_gate_rejects_textbook_voice() -> None:
    from api.services.llm import should_accept_llm_answer

    fallback = {"missing_data": [], "normalized_context": {}}
    tool_context = {"tool_results": []}
    answer = (
        "IV crush is a phenomenon where an option contract suddenly and significantly decreases in value "
        "after an earnings announcement because implied volatility changes."
    )

    assert should_accept_llm_answer(answer, fallback, "concept", "What is IV crush?", tool_context) is False


def test_model_answer_quality_gate_enforces_profile_style() -> None:
    from api.services.llm import should_accept_llm_answer

    fallback = {"missing_data": [], "normalized_context": {}}
    tool_context = {
        "tool_results": [
            {
                "name": "retrieve_profile_memory",
                "result": {
                    "status": "ok",
                    "preferred_explanation": "Quant-heavy",
                    "risk_strictness": "Strict about risk",
                },
            }
        ]
    }
    vague_answer = "A call option benefits when the stock moves higher, but it can still lose value if timing is wrong."
    specific_answer = "A call option needs the stock to beat the premium and breakeven before expiration, so max loss and DTE matter first."

    assert should_accept_llm_answer(vague_answer, fallback, "concept", "Explain calls", tool_context) is False
    assert should_accept_llm_answer(specific_answer, fallback, "concept", "Explain calls", tool_context) is True


def test_model_answer_quality_gate_rejects_bad_options_math() -> None:
    from api.services.llm import should_accept_llm_answer

    fallback = {"missing_data": [], "normalized_context": {}}
    tool_context = {"tool_results": []}
    answer = (
        "A debit spread limits your maximum profit and loss, with a breakeven at the higher strike plus premium paid. "
        "That makes the risk cleaner than a long call."
    )

    assert should_accept_llm_answer(answer, fallback, "strategy_explainer", "Compare a long call and debit spread", tool_context) is False


def test_model_answer_quality_gate_rejects_live_data_hallucinations() -> None:
    from api.services.llm import llm_answer_rejection_reasons, should_accept_llm_answer

    fallback = {
        "missing_data": [
            "live option chain",
            "implied volatility",
            "Greeks",
            "bid/ask",
            "volume/open interest",
            "earnings date",
            "current stock price",
        ],
        "normalized_context": {},
    }
    tool_context = {"tool_results": []}

    unsafe_answers = [
        "AAPL IV is currently 31%, so the option looks expensive before earnings.",
        "The AAPL 200 call has a 0.42 delta, -0.09 theta, and 2,400 open interest today.",
        "AAPL is trading at $214.30 right now, with earnings on July 24, 2026.",
        "The bid is $2.10 and the ask is $2.18, so liquidity is fine.",
        "The current price is 214.30, so the contract is close to the money.",
        "The option chain shows heavy volume at the 200 strike right now.",
        "The premium is $2.35 today and the contract is cheap.",
        "IV looks high here, so you are probably overpaying.",
        "Liquidity is strong and the bid/ask spread is tight.",
        "Open interest looks healthy enough for this contract.",
        "Earnings are next week, so event risk is elevated.",
        "The Greeks look favorable for this call.",
        "The spread looks tight enough that fills should be fine.",
        "There is enough volume to avoid liquidity problems.",
        "This contract has good participation and clean pricing.",
        "I do not have live data, but the nearest expiration is this Friday.",
        "The chain has plenty of strikes around 200.",
        "Volume is high enough that execution should not be an issue.",
        "AAPL IV is around 32% here, so premium is elevated.",
        "The call has a delta around 0.42 and theta near -0.08.",
        "Bid sits at 2.10 and ask sits at 2.18, so the spread is workable.",
        "The mid price is about $2.14 and the last trade was $2.16.",
        "Open interest of 2,400 and volume of 900 contracts looks fine.",
        "OI is 2400, so participation is good.",
        "AAPL reports earnings tomorrow, so IV should be elevated.",
        "Earnings are this week and the option chain looks liquid.",
        "The spread is tight enough to trade.",
        "The option is pricing in a 4% move.",
        "The market expects a big move after earnings.",
        "IV rank is 72 and skew is steep.",
        "The expected move is about $8 this week.",
    ]

    for answer in unsafe_answers:
        assert should_accept_llm_answer(answer, fallback, "concept", "What is AAPL IV right now?", tool_context) is False
        assert "fabricated_live_data" in llm_answer_rejection_reasons(answer, fallback, "concept", "What is AAPL IV right now?", tool_context)


def test_model_answer_quality_gate_rejects_direct_trading_instructions() -> None:
    from api.services.llm import llm_answer_rejection_reasons, should_accept_llm_answer

    fallback = {"missing_data": [], "normalized_context": {}}
    tool_context = {"tool_results": []}
    unsafe_answers = [
        "You should buy NVDA calls tomorrow because momentum is strong.",
        "I recommend selling the AAPL put and entering the trade before earnings.",
        "Take the trade if the premium is under $3.00.",
        "This is a good entry, so hold it until expiration.",
    ]

    for answer in unsafe_answers:
        assert should_accept_llm_answer(answer, fallback, "risk_math", "Should I buy NVDA calls tomorrow?", tool_context) is False
        assert "direct_trading_instruction" in llm_answer_rejection_reasons(answer, fallback, "risk_math", "Should I buy NVDA calls tomorrow?", tool_context)


def test_llm_rejection_reasons_are_structured() -> None:
    from api.services.llm import llm_answer_rejection_reasons

    fallback = {
        "missing_data": ["implied volatility", "bid/ask"],
        "normalized_context": {"ticker": "AAPL", "selected_contract": {"strike": 200}},
    }
    tool_context = {"tool_results": []}
    reasons = llm_answer_rejection_reasons(
        "You should buy it. IV is currently 31% and liquidity is strong.",
        fallback,
        "trade_review",
        "Should I buy this?",
        tool_context,
    )

    assert "direct_trading_instruction" in reasons
    assert "fabricated_live_data" in reasons


def test_direct_advice_request_is_refused_and_reframed() -> None:
    response = asyncio.run(answer_chat("Should I buy NVDA calls tomorrow?"))
    answer = response["answer"].lower()

    assert response["mode"] == "risk_math"
    assert "cannot pick a live trade" in answer
    assert "ticker" in answer
    assert "premium" in answer
    assert "you should buy" not in answer


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


def test_saved_trade_why_risky_uses_latest_check_details() -> None:
    recent_checks = [{"id": "saved_1", "report": selected_trade_fixture()}]
    response = asyncio.run(answer_chat("Why was my latest saved check risky?", recent_checks=recent_checks))
    answer = response["answer"].lower()

    assert response["mode"] == "saved_trade_lookup"
    assert "aapl" in answer
    assert "breakeven move" in answer
    assert "$215" in response["answer"]
    assert "3.4%" in response["answer"]


def test_saved_trade_missing_data_uses_latest_check_details() -> None:
    recent_checks = [{"id": "saved_1", "report": selected_trade_fixture()}]
    response = asyncio.run(answer_chat("What data was missing on my latest check?", recent_checks=recent_checks))
    answer = response["answer"].lower()

    assert response["mode"] == "saved_trade_lookup"
    assert "bid/ask" in answer
    assert "implied volatility" in answer
    assert "open interest" in answer


def test_selected_trade_identity_is_not_generic_review() -> None:
    report = selected_trade_fixture() | {"strike": "190", "riskMath": {"max_loss": 180}}
    response = asyncio.run(answer_chat("What is the trade I did?", current_report=report))

    assert response["mode"] == "trade_identity"
    assert "aapl" in response["answer"].lower()
    assert "190" in response["answer"]
    assert "breakeven move" in response["answer"].lower()


def test_selected_trade_why_risky_uses_report_math() -> None:
    response = asyncio.run(answer_chat("Why is this risky?", current_report=selected_trade_fixture(), chat_mode="Review"))
    answer = response["answer"].lower()
    used = {tool["name"] for tool in response["tools_used"]}

    assert response["mode"] == "trade_review"
    assert "breakeven move" in answer
    assert "$215" in response["answer"]
    assert "3.4%" in response["answer"]
    assert "3 days" in answer
    assert "generic" not in answer
    assert "get_news" not in used
    assert "saved trade" not in response["what_used"]


def test_selected_trade_what_can_break_uses_report_math() -> None:
    response = asyncio.run(answer_chat("What can break this trade?", current_report=selected_trade_fixture(), chat_mode="Review"))
    answer = response["answer"].lower()

    assert response["mode"] == "trade_review"
    assert "breakeven move" in answer
    assert "$215" in response["answer"]
    assert "3.4%" in response["answer"]
    assert "missing liquidity/iv" in answer or "liquidity" in answer


def test_selected_trade_weakest_link_gets_plain_explanation() -> None:
    response = asyncio.run(answer_chat("Explain my weakest link in plain English", current_report=selected_trade_fixture(), chat_mode="Review"))
    answer = response["answer"].lower()

    assert response["mode"] == "trade_review"
    assert "breakeven move" in answer
    assert "stock has to move enough" in answer or "move enough" in answer
    assert "aapl" in answer


def test_selected_trade_missing_data_names_contract_fields() -> None:
    response = asyncio.run(answer_chat("What data is missing before trusting this?", current_report=selected_trade_fixture(), chat_mode="Review"))
    answer = response["answer"].lower()
    blocks = str(response["visual_blocks"]).lower()

    assert response["mode"] == "trade_review"
    assert "bid/ask" in answer
    assert "implied volatility" in answer or "iv" in answer
    assert "open interest" in answer
    assert "missing live data" in blocks


def test_selected_trade_review_surfaces_watch_next_context() -> None:
    response = asyncio.run(answer_chat("Review this setup", current_report=selected_trade_fixture(), chat_mode="Review"))
    cards = {card["label"]: card["value"] for card in response["summary_cards"]}
    blocks = {block["title"]: block for block in response["visual_blocks"] if block.get("title")}
    watch_next = str(blocks.get("Watch next", {})).lower()

    assert response["mode"] == "trade_review"
    assert cards["DTE"] == "3d"
    assert cards["Acct risk"] == "4.3%"
    assert "breakeven move" in watch_next
    assert "3.4% move needed" in watch_next
    assert "3 days left" in watch_next
    assert "bid/ask" in watch_next


def test_selected_trade_context_packet_is_source_ranked() -> None:
    profile = {
        "accountSize": 5000,
        "coachStyle": {"explanationStyle": "Simple", "riskStrictness": "Strict"},
        "riskRules": {"maxRiskPerTradePercent": 3, "warnUnder7Dte": True},
        "aiMemory": {"commonMistakes": ["overfocus on upside"]},
    }
    response = asyncio.run(answer_chat("Why is this risky?", current_report=selected_trade_fixture(), chat_mode="Review", user_profile=profile))
    context = response["normalized_context"]
    used = {tool["name"] for tool in response["tools_used"]}

    assert context["coach_context"]["primary_source"] == "selected_check"
    assert context["coach_context"]["availability"]["selected_check"] is True
    assert context["coach_context"]["availability"]["profile_preferences"] is True
    assert context["selected_trade"]["title"].startswith("AAPL")
    assert "max loss 215" in context["selected_trade"]["pressure_points"]
    assert context["fact_tools"]["max_loss"]["account_risk_pct"] == 4.3
    assert context["missing_categories"]["live_market_data"]
    assert "retrieve_selected_trade" in used
    assert "detect_missing_data" in used
    assert "selected-trade retriever" in response["what_used"]
    assert "missing-data detector" in response["what_used"]


def test_uploaded_contract_context_packet_becomes_primary_when_no_selected_check() -> None:
    attachments = [
        {
            "name": "contract.txt",
            "type": "text/plain",
            "source": "files",
            "size": 160,
            "text": "Ticker: MSFT\nType: Put\nStrike: 430\nExpiration: 2099-01-21\nPremium: 5.20\nContracts: 2",
        }
    ]
    response = asyncio.run(answer_chat("What data is missing from this uploaded contract?", attachments=attachments, chat_mode="Review"))
    context = response["normalized_context"]["coach_context"]

    assert context["primary_source"] == "uploaded_contract"
    assert context["availability"]["uploaded_contract"] is True
    assert context["fact_tools"]["max_loss"]["max_loss"] == 1040
    assert context["fact_tools"]["breakeven"]["breakeven"] == 424.8
    assert "implied volatility" in context["missing_data"]
    assert "bid/ask" in context["missing_data"]
    assert any("avoid live-data claims" in item.lower() or "missing fields" in item.lower() for item in context["answer_guidance"])


def test_contract_parser_handles_broker_shorthand_contract_text() -> None:
    response = asyncio.run(
        extract_contract_from_uploads(
            [
                {
                    "name": "ocr.txt",
                    "type": "text/plain",
                    "source": "files",
                    "text": "AAPL 200C 6/21 @ 2.15 Qty 3 Bid 2.10 Ask 2.25 OI 1234 Vol 456",
                }
            ]
        )
    )
    fields = response["fields"]

    assert response["status"] == "ok"
    assert fields["ticker"] == "AAPL"
    assert fields["optionSide"] == "call"
    assert fields["strike"] == "200"
    assert fields["expiration"].endswith("-06-21")
    assert fields["premium"] == "2.15"
    assert fields["contracts"] == "3"
    assert fields["bid"] == "2.1"
    assert fields["ask"] == "2.25"
    assert fields["openInterest"] == "1234"
    assert fields["contractVolume"] == "456"


def test_contract_parser_handles_occ_symbol_and_partial_ocr() -> None:
    response = asyncio.run(
        extract_contract_from_uploads(
            [
                {
                    "name": "occ.txt",
                    "type": "text/plain",
                    "source": "files",
                    "text": "MSFT260621P00430000 @ 5.20 x2 IV 41.5",
                }
            ]
        )
    )
    fields = response["fields"]

    assert response["status"] == "ok"
    assert fields["ticker"] == "MSFT"
    assert fields["optionSide"] == "put"
    assert fields["strike"] == "430"
    assert fields["expiration"] == "2026-06-21"
    assert fields["premium"] == "5.2"
    assert fields["contracts"] == "2"
    assert fields["impliedVolatility"] == "41.5"
    assert "bid" in response["missing_live_fields"]
    assert "ask" in response["missing_live_fields"]


def test_image_upload_without_vision_provider_goes_to_manual_review() -> None:
    previous_order = settings.llm_provider_order
    settings.llm_provider_order = ["fallback"]
    try:
        response = asyncio.run(
            extract_contract_from_uploads(
                [
                    {
                        "name": "broker-screenshot.png",
                        "type": "image/png",
                        "source": "camera",
                        "dataUrl": "data:image/png;base64,iVBORw0KGgo=",
                    }
                ]
            )
        )
    finally:
        settings.llm_provider_order = previous_order

    assert response["status"] == "needs_manual_review"
    assert response["provider"] == "none"
    assert response["fields"] == {}
    assert "Enter ticker" in response["message"]


def test_image_upload_with_hosted_vision_result_returns_confirmable_fields(monkeypatch) -> None:
    from api.services import llm as llm_service
    from api.services.llm_provider import LLMResult

    async def fake_generate_answer(**kwargs):
        return LLMResult(
            text='{"ticker":"AAPL","side":"call","strike":200,"expiration":"2099-01-17","premium":2.15,"contracts":1}',
            provider="gemini",
            model="gemini-vision-test",
        )

    monkeypatch.setattr(llm_service, "generate_answer", fake_generate_answer)
    response = asyncio.run(
        extract_contract_from_uploads(
            [
                {
                    "name": "broker-screenshot.png",
                    "type": "image/png",
                    "source": "photo-library",
                    "dataUrl": "data:image/png;base64,iVBORw0KGgo=",
                }
            ]
        )
    )

    assert response["status"] == "ok"
    assert response["provider"] == "gemini"
    assert response["model"] == "gemini-vision-test"
    assert response["fields"]["ticker"] == "AAPL"
    assert response["fields"]["premium"] == "2.15"
    assert "bid" in response["missing_live_fields"]


def test_fact_tools_derive_max_loss_dte_and_liquidity_without_guessing_live_data() -> None:
    report = {
        "ticker": "MSFT",
        "tradeType": "Call Option (Long)",
        "strike": 430,
        "expiration": "2099-01-21",
        "premium": 4.25,
        "contracts": 2,
        "contractSnapshot": {"bid": 4.1, "ask": 4.4, "contractVolume": 80, "openInterest": 120},
    }
    max_loss = calculate_max_loss(report, {"accountSize": 25000, "riskRules": {"maxRiskPerTradePercent": 2}})
    dte = calculate_dte(report)
    liquidity = calculate_liquidity_score(report)

    assert max_loss["max_loss"] == 850
    assert max_loss["account_risk_pct"] == 3.4
    assert max_loss["budget_status"] == "above_profile_limit"
    assert dte["status"] == "ok"
    assert dte["source"] == "expiration_date"
    assert dte["calendar_days_left"] > 0
    assert liquidity["score"] < 75
    assert liquidity["spread_width_pct"] is not None
    assert liquidity["label"] in {"thin_or_needs_caution", "weak", "healthy"}


def test_tool_context_detector_exposes_every_major_context_source() -> None:
    profile = {
        "accountSize": 10000,
        "coachStyle": {"explanationStyle": "Quant-heavy", "riskStrictness": "Strict"},
        "riskRules": {"maxRiskPerTradePercent": 2},
    }
    recent_checks = [{"id": "saved_1", "report": selected_trade_fixture()}]
    context = asyncio.run(
        build_ai_tool_context(
            message="Explain my latest saved check and what data is missing",
            mode="saved_trade_lookup",
            current_report=None,
            user_profile=profile,
            recent_checks=recent_checks,
        )
    )

    assert context["coach_context"]["primary_source"] == "saved_checks"
    assert context["coach_context"]["availability"]["saved_checks"] == 1
    assert context["coach_context"]["availability"]["profile_preferences"] is True
    assert context["coach_context"]["saved_checks"][0]["ticker"] == "AAPL"
    assert context["coach_context"]["profile_preferences"]["risk_strictness"] == "Strict"
    assert "implied volatility" in context["missing_data"]
    assert "live_market_data" in context["coach_context"]["missing_categories"]
    assert "detect_missing_data" in [tool["name"] for tool in context["tools_used"]]


def test_saved_checks_intelligence_summarizes_patterns_and_riskiest_check() -> None:
    recent_checks = [
        {"id": "latest", "report": selected_trade_fixture()},
        {
            "id": "riskier",
            "report": selected_trade_fixture()
            | {
                "ticker": "NVDA",
                "weakestLink": "breakeven move",
                "amountAtRisk": 640,
                "riskMath": {"max_loss": 640, "required_move_to_breakeven_pct": 6.2, "calendar_days_left": 5},
            },
        },
        {
            "id": "older",
            "report": selected_trade_fixture()
            | {
                "ticker": "TSLA",
                "weakestLink": "liquidity",
                "amountAtRisk": 180,
                "riskMath": {"max_loss": 180},
            },
        },
    ]
    response = asyncio.run(answer_chat("What pattern do I keep repeating in saved checks?", recent_checks=recent_checks))
    answer = response["answer"].lower()
    blocks = str(response["visual_blocks"]).lower()

    assert response["mode"] == "saved_trade_lookup"
    assert "repeated weak point" in answer
    assert "breakeven move" in answer
    assert "riskiest saved check" in answer
    assert "$640" in response["answer"]
    assert "last ticker analyzed" in answer
    assert "saved-check memory" in blocks


def test_selected_trade_debate_names_actual_contract() -> None:
    response = asyncio.run(answer_chat("Debate this setup", current_report=selected_trade_fixture(), chat_mode="Review"))
    answer = response["answer"].lower()

    assert response["mode"] == "trade_review"
    assert "aapl" in answer
    assert "bull case" in answer
    assert "bear case" in answer
    assert "$215" in response["answer"]


def test_selected_trade_position_size_names_actual_contract() -> None:
    response = asyncio.run(answer_chat("Check my position size", current_report=selected_trade_fixture(), chat_mode="Review"))
    answer = response["answer"].lower()

    assert response["mode"] == "trade_review"
    assert "aapl" in answer
    assert "$215" in response["answer"]
    assert "4.3%" in response["answer"]


def test_selected_trade_working_conditions_are_report_specific() -> None:
    response = asyncio.run(answer_chat("What has to go right for this to work?", current_report=selected_trade_fixture(), chat_mode="Review"))
    answer = response["answer"].lower()

    assert response["mode"] == "trade_review"
    assert "aapl" in answer
    assert "3.4%" in response["answer"]
    assert "3 days" in answer


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


def test_uploaded_contract_becomes_normalized_context_and_tools() -> None:
    response = asyncio.run(
        answer_chat(
            "Review this uploaded contract and tell me what is missing",
            attachments=[
                {
                    "name": "contract.txt",
                    "type": "text/plain",
                    "source": "files",
                    "size": 180,
                    "text": "Ticker: AAPL\nType: Call\nStrike: 200\nExpiration: 2026-06-21\nPremium: 2.15\nContracts: 2\nBid: 2.10\nAsk: 2.25",
                }
            ],
        )
    )
    context = response["normalized_context"]
    used = {tool["name"] for tool in response["tools_used"]}
    blocks = str(response["visual_blocks"]).lower()

    assert context["uploaded_contract"]["fields"]["ticker"] == "AAPL"
    assert context["ticker"] == "AAPL"
    assert context["context_manifest"]["uploaded_contract"] is True
    assert context["context_manifest"]["attachments"] == 1
    assert context["context_manifest"]["missing_data"] >= 1
    assert "parse_uploaded_contract" in used
    assert "calculate_breakeven" in used
    assert "calculate_max_loss" in used
    assert "uploaded contract parsed" in blocks
    assert "implied volatility" in response["missing_data"]
    assert "greeks" in [item.lower() for item in response["missing_data"]]


def test_context_manifest_tracks_core_context_sources() -> None:
    profile = {
        "experienceLevel": "Learning",
        "coachStyle": {"explanationStyle": "Simple", "riskStrictness": "Strict"},
        "riskRules": {"maxRiskPerTradePercent": 3},
    }
    history = [
        {"role": "user", "content": "What is IV crush?"},
        {"role": "assistant", "content": "IV crush is when event premium deflates."},
    ]
    recent_checks = [{"id": "saved_1", "report": selected_trade_fixture()}]
    response = asyncio.run(
        answer_chat(
            "Why is this risky?",
            current_report=selected_trade_fixture(),
            user_profile=profile,
            conversation_history=history,
            recent_checks=recent_checks,
            chat_mode="Review",
        )
    )
    manifest = response["normalized_context"]["context_manifest"]
    blocks = str(response["visual_blocks"]).lower()

    assert manifest["selected_check"] is True
    assert manifest["saved_checks"] == 1
    assert manifest["profile_memory"] is True
    assert manifest["recent_chat_messages"] == 2
    assert "coach context available" in blocks


def test_tool_context_creates_visible_context_block() -> None:
    response = asyncio.run(answer_chat("What is AAPL IV right now and what data do you need?"))
    blocks = str(response["visual_blocks"]).lower()

    assert response["tools_used"]
    assert "context riskwise used" in blocks
    assert "options data" in blocks
    assert "missing live data" in blocks


def test_learning_phrase_does_not_become_single_letter_ticker() -> None:
    response = asyncio.run(answer_chat("I am learning. Pull the AMZN option chain for this Friday"))

    assert response["normalized_context"]["ticker"] == "AMZN"
    assert "for i," not in response["answer"].lower()


def test_selected_trade_runs_contract_context_tools() -> None:
    report = {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "strike": 200,
        "expiration": "2026-06-21",
        "amountAtRisk": 215,
        "riskMath": {"max_loss": 215},
    }
    response = asyncio.run(answer_chat("Review this contract", current_report=report, chat_mode="Review"))
    used = {tool["name"] for tool in response["tools_used"]}
    blocks = str(response["visual_blocks"]).lower()

    assert "get_option_chain" in used
    assert "get_option_contract" in used
    assert "selected contract context" in blocks
    assert "missing live data" in blocks


def test_deep_analysis_returns_five_agent_committee() -> None:
    report = {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "strike": 200,
        "expiration": "2026-06-21",
        "amountAtRisk": 215,
        "setupScore": 72,
        "weakestLink": "liquidity",
        "riskMath": {"max_loss": 215, "required_move_to_breakeven_pct": 3.4, "account_risk_pct": 0.86},
    }
    response = asyncio.run(answer_chat("Run deep analysis", current_report=report, chat_mode="Review", analysis_depth="deep_analysis"))

    assert response["analysis_depth"] == "deep_analysis"
    assert len(response["agent_docket"]) == 5
    assert {item["agent"] for item in response["agent_docket"]} == {
        "Structure Agent",
        "Volatility Agent",
        "Liquidity Agent",
        "Sizing Agent",
        "Skeptic Agent",
    }
    assert any(block["type"] == "agent_committee" for block in response["visual_blocks"])


def test_deep_analysis_names_missing_data_and_what_was_used() -> None:
    report = {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "strike": 200,
        "expiration": "2026-06-21",
        "amountAtRisk": 215,
        "setupScore": 72,
        "weakestLink": "liquidity",
        "riskMath": {"max_loss": 215, "required_move_to_breakeven_pct": 3.4},
    }
    response = asyncio.run(answer_chat("Run deep analysis", current_report=report, chat_mode="Review", analysis_depth="deep_analysis"))
    blocks = str(response["visual_blocks"]).lower()

    assert response["what_used"]
    assert "committee synthesis" in blocks
    assert "missing live data" in blocks
    assert "bid/ask" in blocks or "implied volatility" in blocks


def test_deep_analysis_contains_risk_map_scenarios_and_beginner_verdict() -> None:
    response = asyncio.run(answer_chat("Run deep analysis", current_report=selected_trade_fixture(), chat_mode="Review", analysis_depth="deep_analysis"))
    blocks = str(response["visual_blocks"]).lower()
    answer = response["answer"].lower()

    assert "risk map" in blocks
    assert "scenario table" in blocks
    assert "beginner explanation" in blocks
    assert "final verdict" in blocks
    assert "cautious" in answer
    assert len(response["agent_docket"]) == 5


def test_profile_simple_style_shapes_coach_answer() -> None:
    profile = {
        "experienceLevel": "Learning",
        "coachStyle": {"explanationStyle": "Simple", "riskStrictness": "Balanced"},
        "riskRules": {"maxRiskPerTradePercent": 3},
    }
    response = asyncio.run(answer_chat("Explain theta decay", user_profile=profile))
    answer = response["answer"].lower()

    assert response["normalized_context"]["profile_memory"]["preferred_explanation"] == "Simple"
    assert "plain version" in answer
    assert "3%" in answer


def test_profile_quant_and_strict_risk_style_shape_answer() -> None:
    profile = {
        "accountSize": 5000,
        "coachStyle": {"explanationStyle": "Quant-heavy", "riskStrictness": "Strict"},
        "riskRules": {"maxRiskPerTradePercent": 4},
        "aiMemory": {"commonMistakes": ["chasing weekly earnings calls"]},
    }
    response = asyncio.run(answer_chat("How should I think about position sizing?", user_profile=profile))
    answer = response["answer"].lower()

    assert response["mode"] == "risk_math"
    assert "cannot pick a live trade" not in answer
    assert "4%" in answer
    assert "$200" in answer
    assert "chasing weekly earnings calls" in answer


def test_profile_ask_questions_first_adds_one_question() -> None:
    profile = {
        "coachStyle": {
            "explanationStyle": "Step-by-step",
            "questionStyle": "Ask questions first",
            "riskStrictness": "Balanced",
        }
    }
    response = asyncio.run(answer_chat("Compare a long call and a debit spread", chat_mode="Compare", user_profile=profile))
    answer = response["answer"]

    assert response["normalized_context"]["profile_memory"]["question_style"] == "Ask questions first"
    assert answer.count("?") == 1


def test_profile_strict_style_shapes_selected_trade_review() -> None:
    profile = {
        "accountSize": 5000,
        "coachStyle": {"explanationStyle": "Quant-heavy", "riskStrictness": "Strict"},
        "riskRules": {"maxRiskPerTradePercent": 2},
        "aiMemory": {"commonMistakes": ["ignoring bid ask spread"]},
    }
    response = asyncio.run(answer_chat("Why is this risky?", current_report=selected_trade_fixture(), chat_mode="Review", user_profile=profile))
    answer = response["answer"].lower()

    assert response["mode"] == "trade_review"
    assert "2%" in answer
    assert "$100" in answer
    assert "ignoring bid ask spread" in answer
    assert "4.3% account risk" in answer


def test_profile_simple_style_shapes_selected_trade_missing_data() -> None:
    profile = {
        "experienceLevel": "Learning",
        "coachStyle": {"explanationStyle": "Simple", "riskStrictness": "Balanced"},
        "riskRules": {"maxRiskPerTradePercent": 3},
    }
    response = asyncio.run(answer_chat("What data is missing before trusting this?", current_report=selected_trade_fixture(), chat_mode="Review", user_profile=profile))
    answer = response["answer"].lower()

    assert "plain version" in answer
    assert "bid/ask" in answer
    assert "implied volatility" in answer
    assert "3%" in answer


def test_profile_warn_under_7_dte_shapes_selected_trade_review() -> None:
    profile = {
        "coachStyle": {"explanationStyle": "Step-by-step", "riskStrictness": "Balanced"},
        "riskRules": {"warnUnder7Dte": True, "maxRiskPerTradePercent": 3},
    }
    response = asyncio.run(answer_chat("Why is this risky?", current_report=selected_trade_fixture(), chat_mode="Review", user_profile=profile))
    answer = response["answer"].lower()

    assert "under 7 dte" in answer or "under 7 days" in answer
    assert "3 days left" in answer


def test_profile_avoid_earnings_trades_shapes_event_answer() -> None:
    profile = {
        "coachStyle": {"explanationStyle": "Simple", "riskStrictness": "Strict"},
        "riskRules": {"avoidEarningsTrades": True, "maxRiskPerTradePercent": 3},
    }
    response = asyncio.run(answer_chat("How do earnings affect calls?", user_profile=profile))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "earnings" in answer
    assert "avoid earnings trades" in answer


def test_delta_explanation_stays_beginner_specific() -> None:
    response = asyncio.run(answer_chat("Explain delta like I am new"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "delta" in answer
    assert "stock" in answer or "underlying" in answer
    assert "probability" in answer


def test_contract_specific_open_interest_refuses_live_guess() -> None:
    response = asyncio.run(answer_chat("Is open interest healthy enough on the META 125 call?"))
    answer = response["answer"].lower()

    assert response["mode"] == "concept"
    assert "live option-chain" in answer or "provider data" in answer
    assert "open interest" in answer
    assert "not confirm liquidity" in answer or "should not invent" in answer


def test_should_i_enter_contract_is_direct_advice_refusal() -> None:
    response = asyncio.run(answer_chat("Should I enter this AMZN call if premium is under 3?"))
    answer = response["answer"].lower()

    assert response["mode"] == "risk_math"
    assert "cannot pick a live trade" in answer
    assert "premium" in answer
    assert "max loss" in answer or "risk" in answer


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


def test_ai_provider_diagnostics_are_explicit_and_secret_safe() -> None:
    client = TestClient(app)
    response = client.get("/ai/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["fallback_available"] is True
    assert "provider_order" in body
    assert body["providers"]
    first = body["providers"][0]
    assert "provider" in first
    assert "kind" in first
    assert "status" in first
    assert "cooldown_remaining_seconds" in first
    serialized = str(body).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized


def test_ai_smoke_endpoint_runs_core_modes() -> None:
    client = TestClient(app)
    response = client.get("/ai/smoke")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["passed"] == body["total"]
    labels = {item["label"] for item in body["results"]}
    assert {"Greeting", "Concept", "Trade review", "Deep analysis"}.issubset(labels)
    deep = next(item for item in body["results"] if item["label"] == "Deep analysis")
    assert deep["agent_count"] == 5
    serialized = str(body).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized
