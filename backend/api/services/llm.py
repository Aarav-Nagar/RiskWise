from __future__ import annotations

import json
import re
from typing import Any

from api.services.ai_tools import build_ai_tool_context
from api.services.llm_provider import generate_answer


SAFETY_LINE = "Educational only. Not financial advice."

SYSTEM_PROMPT = """
You are RiskWiseAI, a calm options-risk coach for students and self-directed learners.

Style:
- Sound like a sharp human tutor in a premium chat app, not a marketing bot.
- Answer the actual message first. If the user pushes back, adapt instead of restarting.
- Be concise, concrete, and useful. Prefer 60-120 words unless the user asks for depth.
- Do not use markdown formatting, asterisks, or long textbook lists. The answer appears inside a mobile chat bubble.
- Use at most 3 short plain-language points unless the user asks for a deep explanation.
- Explain jargon in plain English, then add the options-specific detail only if it helps.
- If the user says hi or asks something casual, answer naturally.
- If the user asks a harmless non-options question, answer normally and briefly. You are allowed to be a general assistant, but your strongest domain is options risk.
- Do not sound like a compliance memo. The app already has a disclaimer in the UI.
- Ask at most one clarifying question, and only when needed.
- Do not end with generic phrases like "feel free to ask" or "it's essential to understand."

Scope:
- You can explain calls, puts, premium, strike, expiration, ITM/ATM/OTM, Greeks, IV, IV crush,
  earnings volatility, spreads, break-even, max loss, sizing, drawdowns, and trade-check reports.
- If a RiskWise report is attached, use its scores, weakest link, risk math, debate, and questions.
- Use recent chat history to understand short replies like "no", "why", "what about this", or "explain simpler".
- If files or screenshots are attached, use them only if readable from the provided content. If not,
  ask for the ticker, contract, premium, expiration, and account risk instead of inventing details.

Safety:
- Do not tell the user to buy, sell, hold, enter, exit, or size a live trade.
- For debit spreads: max loss is the net debit paid; max gain is capped at spread width minus net debit.
- Do not fabricate live option chains, IV, premiums, earnings dates, or current prices.
- If live data is needed, say exactly what data would be needed.
- Do not append a disclaimer unless the user asks for personalized trading advice.
- Treat server tool results as the source of truth when provided. If a tool says
  options data is unavailable, say what is missing instead of guessing.
"""


async def answer_chat(
    message: str,
    current_report: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    chat_mode: str = "Explain",
    attachments: list[dict[str, Any]] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    recent_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    clean_attachments = sanitize_attachments(attachments or [])
    clean_history = compact_history(conversation_history or [])
    clean_recent_checks = compact_saved_checks(recent_checks or [])
    mode = classify_message(message, current_report, chat_mode, clean_attachments, clean_history, clean_recent_checks)
    tool_context = await build_ai_tool_context(
        message=message,
        mode=mode,
        current_report=current_report,
        user_profile=user_profile,
        recent_checks=clean_recent_checks,
    )
    response = build_structured_response(
        message,
        mode,
        current_report,
        user_profile,
        clean_attachments,
        clean_history,
        clean_recent_checks,
    )
    apply_tool_context(response, tool_context)

    response["provider"] = "fallback"
    response["model"] = "deterministic-options-coach"
    response["used_fallback"] = True

    if should_use_fast_path(message, mode, current_report, clean_attachments):
        return response

    try:
        prompt = build_llm_prompt(
            message,
            mode,
            current_report,
            user_profile,
            chat_mode,
            clean_attachments,
            clean_history,
            clean_recent_checks,
            tool_context,
        )
        llm_result = await generate_answer(system_prompt=SYSTEM_PROMPT, prompt=prompt, attachments=clean_attachments)
        if llm_result and llm_result.text:
            llm_answer = clean_answer(llm_result.text)
            if not is_low_quality_llm_answer(llm_answer, mode):
                response["answer"] = llm_answer
                response["provider"] = llm_result.provider
                response["model"] = llm_result.model
                response["used_fallback"] = False
    except Exception:
        pass

    return response


def build_llm_prompt(
    message: str,
    mode: str,
    current_report: dict[str, Any] | None,
    user_profile: dict[str, Any] | None,
    chat_mode: str,
    attachments: list[dict[str, Any]],
    conversation_history: list[dict[str, Any]],
    recent_checks: list[dict[str, Any]],
    tool_context: dict[str, Any] | None = None,
) -> str:
    report_context = json.dumps(compact_report(current_report), ensure_ascii=True)[:6000]
    profile_context = json.dumps(compact_profile(user_profile), ensure_ascii=True)[:2000]
    attachment_context = json.dumps(attachment_text_context(attachments), ensure_ascii=True)[:3000]
    history_context = json.dumps(conversation_history, ensure_ascii=True)[:4500]
    recent_checks_context = json.dumps(recent_checks, ensure_ascii=True)[:4500]
    tool_context_json = json.dumps(tool_context or {}, ensure_ascii=True)[:7000]
    mode_instruction = {
        "Explain": "Teach the concept clearly. Use a simple example if useful.",
        "Review": "Evaluate the attached trade-check context. Focus on risk, missing information, and what could go wrong.",
        "Compare": "Compare choices side by side. Be balanced and avoid declaring a winner.",
    }.get(chat_mode, "Answer clearly and cautiously.")
    intent_instruction = {
        "simplify": (
            "The user is asking for the same idea again. Do not restart with a generic options definition. "
            "Use the recent conversation to identify the topic, then explain it in a different, simpler way."
        ),
        "followup": (
            "This is a short follow-up. Resolve what 'why', 'how', 'that', or 'again' refers to from history, "
            "then answer that specific point."
        ),
        "uncertain": (
            "The user is unsure. Give them a useful next step or 2-3 concrete paths instead of a broad lesson."
        ),
        "concept": "Answer the concept directly, then add one options-risk insight that a beginner might miss.",
        "general_finance": "Answer the finance or investing concept normally, then connect it lightly to risk discipline if useful.",
        "risk_math": "Explain the risk math in dollars first, then percent of account, then what data is missing.",
        "strategy_explainer": "Compare payoff, max loss, time decay, volatility exposure, and the trade-off. Do not declare one best.",
        "trade_review": "Use the selected report or saved check. If live option data is missing, say what exact fields would be needed.",
        "missing_trade_context": "Ask for the minimum fields needed to evaluate the trade. Do not invent a trade.",
        "smalltalk": "Answer naturally and briefly, like a normal assistant.",
        "greeting": "Greet the user briefly and say what you can help with.",
    }.get(mode, "Answer naturally and stay inside the educational options-risk scope.")

    return (
        f"Internal classification: {mode}\n"
        f"User selected mode: {chat_mode}\n"
        f"Mode instruction: {mode_instruction}\n\n"
        f"Intent instruction: {intent_instruction}\n\n"
        f"User profile JSON:\n{profile_context}\n\n"
        f"RiskWise report JSON:\n{report_context}\n\n"
        f"Attachment metadata/text:\n{attachment_context}\n\n"
        f"Recent saved checks, newest first:\n{recent_checks_context}\n\n"
        f"Server tool results JSON. Use this instead of guessing live data:\n{tool_context_json}\n\n"
        f"Recent conversation, oldest to newest:\n{history_context}\n\n"
        f"User question:\n{message}\n\n"
        "Return only the assistant answer. Be natural. Keep it mobile-short. Do not repeat prior answers unless the user asks. "
        "Do not use markdown bullets, bold, headings, or numbered outlines unless the user explicitly asks for a list."
    )


def classify_message(
    message: str,
    current_report: dict[str, Any] | None,
    chat_mode: str = "Explain",
    attachments: list[dict[str, Any]] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    recent_checks: list[dict[str, Any]] | None = None,
) -> str:
    lower = message.lower().strip()
    mode_choice = (chat_mode or "Explain").lower()
    if any(phrase in lower for phrase in ["guarantee me", "safe options trade", "exactly which", "should i buy", "should i sell", "half my account", "all in"]):
        return "risk_math"
    if any(phrase in lower for phrase in ["what option did i buy", "what did i buy", "what did i trade last"]):
        return "missing_trade_context"
    if lower in {"hi", "hello", "hey", "yo"} or lower.startswith(("hi ", "hello ", "hey ")):
        return "greeting"
    if lower in {"no", "nah", "nope", "nvm", "never mind", "ok", "okay", "cool", "thanks", "thank you"}:
        return "smalltalk"
    if lower in {"idk", "i don't know", "i dont know", "not sure", "not really", "you tell me", "anything"}:
        return "uncertain"
    simplify_phrases = [
        "simpler",
        "make it simple",
        "make it way simple",
        "explain like",
        "i don't get",
        "i dont get",
        "confusing",
        "what do you mean",
        "makes no sense",
        "still don't understand",
        "still dont understand",
    ]
    if any(phrase in lower for phrase in simplify_phrases) or lower in {"simple", "simplify"}:
        return "simplify"
    if conversation_history and lower.startswith(("no ", "nah ", "nope ")):
        return "simplify"
    if asks_about_trade_identity(lower):
        if current_report:
            return "trade_identity"
        if recent_checks:
            return "saved_trade_lookup"
        return "missing_trade_context"
    if asks_about_existing_trade(lower):
        if current_report:
            return "trade_review"
        if recent_checks:
            return "saved_trade_lookup"
        return "missing_trade_context"
    direct_topic_words = [
        "iv",
        "implied",
        "volatility",
        "crush",
        "earnings",
        "theta",
        "delta",
        "gamma",
        "vega",
        "rho",
        "greek",
        "call",
        "put",
        "strike",
        "premium",
        "expiration",
        "breakeven",
        "spread",
        "straddle",
        "strangle",
        "calendar",
        "condor",
        "butterfly",
        "covered",
        "cash-secured",
        "protective",
        "assignment",
        "exercise",
        "bid",
        "ask",
        "liquidity",
        "weekly",
        "weeklies",
        "short-dated",
        "event",
        "events",
        "volume",
        "open interest",
        "pin",
        "skew",
        "smile",
        "term structure",
        "intrinsic",
        "extrinsic",
        "charm",
        "color",
        "vanna",
        "vomma",
        "volga",
        "parity",
        "max pain",
        "risk",
        "size",
        "sizing",
        "position",
        "drawdown",
        "reward",
        "box",
        "ratio",
        "market",
        "stock",
        "spy",
    ]
    has_direct_topic = has_any_term(lower, direct_topic_words)
    if lower in {"why", "how", "what", "wdym"} or lower.startswith(("what do you mean", "wdym")) or (
        lower.startswith(("why ", "how ")) and not has_direct_topic
    ):
        return "followup"
    if attachments:
        return "trade_review" if current_report else "attachment_needs_details"
    if mode_choice == "review":
        return "trade_review" if current_report else "missing_trade_context"
    if mode_choice == "compare":
        return "strategy_explainer"
    if current_report and has_any_term(lower, ["latest", "check", "report", "trade", "weakest", "risky", "risk", "debate", "setup", "label"]):
        return "trade_review"
    if "bid ask" in lower or "bid-ask" in lower or ("bid" in lower and "ask" in lower):
        return "concept"
    if "assignment" in lower:
        return "concept"
    if "exercising" in lower or "exercised" in lower:
        return "concept"
    if has_any_term(lower, ["pin risk", "pinning", "pinned", "charm", "color", "vanna", "vomma", "volga", "skew", "smile", "term structure", "open interest", "intrinsic", "extrinsic", "exercise", "gamma", "rho", "delta", "vega", "max pain", "parity"]):
        return "concept"
    if has_any_term(lower, ["max loss", "risk reward", "all in", "stop loss", "stop losses", "under 7 days", "short dated", "short-dated", "position size", "sizing", "drawdown"]):
        return "risk_math"
    if has_any_term(lower, ["risk", "account"]) and (has_any_term(lower, ["premium", "dollar"]) or "$" in lower):
        return "risk_math"
    if has_any_term(lower, ["breakeven", "break-even"]):
        return "concept"
    if has_any_term(
        lower,
        [
            "spread",
            "straddle",
            "strangle",
            "covered call",
            "cash-secured",
            "protective put",
            "iron condor",
            "condor",
            "butterfly",
            "calendar",
            "box",
            "diagonal",
            "collar",
            "ratio",
            "cash secured",
            "debit",
            "credit",
            "long call",
            "long put",
            "compare",
        ],
    ):
        return "strategy_explainer"
    if has_any_term(lower, ["iv", "implied", "volatility", "crush", "earnings", "theta", "delta", "gamma", "vega", "rho", "charm", "color", "vanna", "vomma", "volga", "greek", "max pain", "parity", "volume", "open interest"]):
        return "concept"
    if has_any_term(lower, ["call", "put", "strike", "premium", "expiration", "breakeven", "break-even", "itm", "otm", "atm", "liquidity", "bid", "ask", "option", "options", "event", "events"]):
        return "concept"
    if has_any_term(lower, ["size", "sizing", "risk", "max loss", "drawdown", "budget", "loss", "capital"]):
        return "risk_math"
    if has_any_term(lower, ["what can you do", "who are you", "help"]):
        return "greeting"
    if mode_choice == "explain":
        return "general_finance"
    return "fallback"


def build_structured_response(
    message: str,
    mode: str,
    current_report: dict[str, Any] | None,
    user_profile: dict[str, Any] | None,
    attachments: list[dict[str, Any]],
    conversation_history: list[dict[str, Any]],
    recent_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    if mode == "greeting":
        answer = "Hey. Send me an options question, a contract screenshot, or a trade check and I will help you break down the risk."
        cards = [{"label": "Best use", "value": "Options risk", "tone": "good"}]
        blocks: list[dict[str, Any]] = []
    elif mode == "smalltalk":
        answer = "Got it. What do you want to look at next?"
        cards = []
        blocks = []
    elif mode == "uncertain":
        answer, cards, blocks = uncertain_response(conversation_history, current_report, recent_checks)
    elif mode == "missing_trade_context":
        answer, cards, blocks = missing_trade_context_response()
    elif mode == "saved_trade_lookup":
        answer, cards, blocks = saved_trade_lookup_response(recent_checks)
    elif mode == "trade_identity" and current_report:
        answer, cards, blocks = trade_identity_response(current_report)
    elif mode == "attachment_needs_details":
        answer, cards, blocks = attachment_needs_details_response(attachments)
    elif mode == "simplify":
        answer, cards, blocks = simplify_response(message, conversation_history)
    elif mode == "followup":
        answer, cards, blocks = followup_response(message, conversation_history)
    elif mode == "trade_review" and current_report:
        answer, cards, blocks = report_review_response(current_report, attachments)
    elif mode == "risk_math":
        answer, cards, blocks = risk_math_response(message, user_profile, attachments)
    elif mode == "strategy_explainer":
        answer, cards, blocks = strategy_response(message)
    elif mode == "concept":
        answer, cards, blocks = concept_response(message, attachments)
    elif mode == "general_finance":
        answer, cards, blocks = general_finance_response(message)
    else:
        answer = (
            "I can help with options concepts, risk math, strategy comparisons, and RiskWise trade checks. "
            "For a specific contract, I need ticker, strike, expiration, premium, and amount at risk."
        )
        cards = [{"label": "Best use", "value": "Options risk", "tone": "good"}]
        blocks = []

    if attachments:
        cards.append({"label": "Attachment", "value": attachment_source_summary(attachments), "tone": "good"})
        blocks.append(
            {
                "type": "mini_table",
                "title": "Attachment context",
                "rows": attachment_context_rows(attachments),
            }
        )

    return {
        "answer": clean_answer(answer),
        "mode": mode,
        "summary_cards": cards,
        "visual_blocks": blocks,
        "suggested_prompts": suggested_prompts(current_report),
    }


def apply_tool_context(response: dict[str, Any], tool_context: dict[str, Any]) -> None:
    response["confidence"] = tool_context.get("confidence", 0.6)
    response["missing_data"] = tool_context.get("missing_data", [])
    response["risk_flags"] = tool_context.get("risk_flags", [])
    response["tools_used"] = tool_context.get("tools_used", [])

    tool_results = tool_context.get("tool_results") or []
    tool_rows: list[list[str]] = []
    for item in tool_results:
        name = item.get("name")
        result = item.get("result") or {}
        if name == "get_quote" and result.get("status") == "ok":
            price = result.get("price")
            change = result.get("changePercentage")
            if price is not None:
                response["summary_cards"].append(
                    {
                        "label": f"{result.get('ticker', 'Quote')} stock",
                        "value": f"${float(price):,.2f}",
                        "tone": "neutral",
                    }
                )
            if change is not None:
                response["summary_cards"].append(
                    {
                        "label": "Today",
                        "value": f"{float(change):+.2f}%",
                        "tone": "good" if float(change) >= 0 else "risk",
                    }
                )
            tool_rows.append(["Stock quote", f"{result.get('ticker', '')} {dollars(price)}"])
        elif name == "get_earnings" and result.get("items"):
            next_event = result["items"][0]
            response["summary_cards"].append({"label": "Earnings", "value": next_event.get("date", "Available"), "tone": "warn"})
            tool_rows.append(["Earnings", str(next_event.get("date") or "Available")])
        elif name == "calculate_breakeven" and result.get("status") == "ok":
            response["summary_cards"] = [card for card in response["summary_cards"] if card.get("label") != "Breakeven"]
            response["summary_cards"].append({"label": "Breakeven", "value": f"${float(result['breakeven']):,.2f}", "tone": "neutral"})
            tool_rows.append(["Breakeven", f"${float(result['breakeven']):,.2f} via {result.get('formula', 'contract math')}"])
        elif name == "calculate_max_loss" and result.get("status") == "ok":
            if result.get("max_loss") is not None:
                response["summary_cards"] = [card for card in response["summary_cards"] if card.get("label") != "Max loss"]
                response["summary_cards"].append({"label": "Max loss", "value": dollars(result.get("max_loss")), "tone": "risk"})
            if result.get("account_risk_pct") is not None:
                response["summary_cards"].append({"label": "Acct risk", "value": f"{float(result['account_risk_pct']):.2f}%", "tone": "warn"})
            if result.get("max_loss") is not None:
                tool_rows.append(["Max loss", f"{dollars(result.get('max_loss'))} / {result.get('account_risk_pct', 'unknown')}% of account"])
        elif name == "get_options_context":
            status = str(result.get("status") or "unknown")
            provider = str(result.get("provider") or "none")
            pending = ", ".join((result.get("fields_pending") or [])[:3])
            detail = f"{provider}: {status}"
            if pending:
                detail += f"; missing {pending}"
            tool_rows.append(["Options data", detail])
        elif name == "get_option_chain":
            status = str(result.get("status") or "unknown")
            expirations = result.get("expirations") or []
            contracts = result.get("contracts") or []
            if expirations:
                response["summary_cards"].append({"label": "Expirations", "value": str(len(expirations)), "tone": "neutral"})
            if contracts:
                response["summary_cards"].append({"label": "Contracts", "value": str(len(contracts)), "tone": "good"})
            tool_rows.append(
                [
                    "Option chain",
                    f"{status}; {len(expirations)} expirations; {len(contracts)} reference contracts",
                ]
            )
            if contracts:
                closest_rows = []
                for contract in contracts[:3]:
                    closest_rows.append(
                        [
                            str(contract.get("contract_type") or "contract").title(),
                            f"{contract.get('expiration_date', 'exp ?')} ${contract.get('strike_price', '?')} {contract.get('moneynessLabel', '')}".strip(),
                        ]
                    )
                response["visual_blocks"].append({"type": "mini_table", "title": "Nearby reference contracts", "rows": closest_rows})
        elif name == "get_option_contract":
            selected = result.get("selected") or {}
            status = str(result.get("status") or "unknown")
            contract_symbol = selected.get("contract_symbol") or selected.get("ticker") or "User-entered contract"
            strike = selected.get("strike") or selected.get("strike_price")
            expiration = selected.get("expiration") or selected.get("expiration_date")
            side = selected.get("optionSide") or selected.get("contract_type") or "option"
            response["summary_cards"].append({"label": "Contract", "value": str(side).title(), "tone": "neutral"})
            if selected.get("moneynessLabel"):
                response["summary_cards"].append({"label": "Moneyness", "value": str(selected["moneynessLabel"]).title(), "tone": "warn" if "out" in str(selected["moneynessLabel"]) else "good"})
            tool_rows.append(["Matched contract", f"{contract_symbol}: {expiration or 'exp ?'} ${strike or '?'} ({status})"])
            response["visual_blocks"].append(
                {
                    "type": "mini_table",
                    "title": "Selected contract context",
                    "rows": [
                        ["Ticker", str(result.get("ticker") or selected.get("symbol") or "")],
                        ["Contract", f"{str(side).title()} ${strike or '?'}"],
                        ["Expiration", str(expiration or "Unknown")],
                        ["Underlying", exact_dollars(selected.get("underlyingPrice")) if selected.get("underlyingPrice") is not None else "Quote unavailable"],
                    ],
                }
            )
        elif name == "get_saved_trade" and result.get("status") == "ok":
            report = result.get("report") or {}
            tool_rows.append(["Saved check", report_title(report)])
        elif name == "search_ticker" and result.get("items"):
            matches = result.get("items") or []
            response["summary_cards"].append({"label": "Ticker matches", "value": str(len(matches)), "tone": "good"})
            tool_rows.append(["Ticker search", ", ".join(item.get("symbol", "") for item in matches[:4])])
        elif name == "get_current_report":
            tool_rows.append(["Selected check", report_title(result)])

    if response.get("mode") in {"general_finance", "concept"} and tool_context.get("ticker"):
        ticker = str(tool_context["ticker"]).upper()
        used_names = {item.get("name") for item in tool_results}
        if "get_news" in used_names:
            response["answer"] = clean_answer(
                f"News can make {ticker} options riskier because the stock can gap, implied volatility can change, and bid/ask spreads can widen. "
                "A headline is not enough by itself; the contract still needs premium, expiration, strike, IV, and liquidity checked."
            )
        elif "get_company_profile" in used_names:
            response["answer"] = clean_answer(
                f"For {ticker}, sector context matters because options react to both the company's move and the broader group it trades with. "
                "That helps frame risk, but the final contract review still depends on premium, expiration, strike, IV, and liquidity."
            )
        elif "get_option_contract" in used_names:
            response["answer"] = clean_answer(
                f"For {ticker}, I can attach the selected contract reference and stock context, but live contract pricing is still the missing piece. "
                "That means strike, expiration, and moneyness can be reviewed, while exact premium, IV, Greeks, bid/ask, volume, and open interest should stay user-confirmed or provider-backed."
            )
        elif "get_option_chain" in used_names or "get_options_context" in used_names:
            response["answer"] = clean_answer(
                f"For {ticker}, I can use option-reference context when available, but live option snapshots are still the limiting factor. "
                "The sharp version needs premium, IV, Greeks, bid/ask, volume, open interest, and the exact expiration chain. Without those, I can review structure and missing risk, but not pretend to know the contract price."
            )
        elif "get_quote" in used_names:
            response["answer"] = clean_answer(
                f"For {ticker}, I can use stock-level context, but not live contract-level options data yet. "
                "A stock move can help or hurt an option, but it does not decide the option by itself because premium, time left, IV, and bid/ask matter too."
            )

    missing = response.get("missing_data") or []
    if tool_rows:
        response["visual_blocks"].append(
            {
                "type": "mini_table",
                "title": "Context RiskWise used",
                "rows": tool_rows[:6],
            }
        )
    if missing:
        response["visual_blocks"].append(
            {
                "type": "mini_table",
                "title": "Missing live data",
                "rows": [[item, "Needed for a sharper answer"] for item in missing[:5]],
            }
        )


def report_review_response(current_report: dict[str, Any], attachments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    risk_math = current_report.get("riskMath") or current_report.get("risk_math") or {}
    debate = current_report.get("setupDebate") or current_report.get("setup_debate") or {}
    weakest = current_report.get("weakestLink") or current_report.get("weakest_link") or "position sizing"
    posture = current_report.get("riskPosture") or current_report.get("risk_posture") or "mixed"
    setup_score = int(current_report.get("setupScore") or current_report.get("setup_score") or 60)
    required_move = risk_math.get("required_move_to_breakeven_pct")
    amount_at_risk = (
        risk_math.get("max_loss")
        or current_report.get("amountAtRisk")
        or current_report.get("amount_at_risk")
        or current_report.get("amountRisk")
        or current_report.get("amount_risk")
    )
    max_loss = dollars(amount_at_risk)
    attachment_note = " I also see an attachment, so I would cross-check the visible contract details against the report." if attachments else ""
    answer = (
        f"This looks like a {posture.lower()} risk review. The weak point is {weakest}, and the max loss shown is {max_loss}. "
        f"The setup score matters less than whether the required move, time left, and premium risk all fit your account plan.{attachment_note}\n\n"
        "A good next question is not 'is this right?' but 'what has to go right for this contract to work, and what breaks the thesis first?'"
    )
    cards = [
        {"label": "Weakest link", "value": str(weakest), "tone": "warn"},
        {"label": "Max loss", "value": max_loss, "tone": "risk"},
        {"label": "Breakeven move", "value": f"{required_move}%" if required_move is not None else "Unknown", "tone": "neutral"},
    ]
    blocks = [
        {"type": "score_bar", "title": "Setup Quality", "value": setup_score, "tone": "good" if setup_score >= 75 else "warn"},
        {
            "type": "mini_table",
            "title": "Debate summary",
            "rows": [
                ["Bull case", debate.get("bull_case") or "Price, timing, and structure all need to line up."],
                ["Bear case", debate.get("bear_case") or "Time decay, IV changes, and required move can offset the thesis."],
                ["Risk judge", debate.get("risk_judge") or "Risk budget should control the decision, not confidence."],
            ],
        },
    ]
    return answer, cards, blocks


def general_finance_response(message: str) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lower = message.lower()
    if has_any_term(lower, ["diversification", "diversify"]):
        answer = (
            "Diversification means spreading risk across more than one asset, sector, or strategy so one bad outcome does not dominate the whole portfolio. "
            "The point is not to make every position win. The point is to avoid depending on a single stock, event, or idea being right."
        )
        title = "Diversification"
        rows = [["Means", "Spread exposure"], ["Helps with", "Single-position risk"], ["Does not remove", "Market risk"]]
    else:
        answer = (
            "That is a broader investing question, so I would frame it through risk first: what can go wrong, how much of the account is exposed, "
            "and whether one decision can damage the whole plan. If you give me the ticker, trade, or concept, I can make it more specific."
        )
        title = "Risk lens"
        rows = [["First question", "What can go wrong?"], ["Second", "How much is exposed?"], ["Third", "What data is missing?"]]
    return answer, [{"label": "Topic", "value": title, "tone": "neutral"}], [{"type": "mini_table", "title": title, "rows": rows}]


def trade_identity_response(current_report: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    title = report_title(current_report)
    risk_math = current_report.get("riskMath") or current_report.get("risk_math") or {}
    amount_at_risk = current_report.get("amountAtRisk") or current_report.get("amount_at_risk") or risk_math.get("max_loss")
    setup_score = current_report.get("setupScore") or current_report.get("setup_score") or "--"
    posture = current_report.get("riskPosture") or current_report.get("risk_posture") or "mixed"
    weakest = current_report.get("weakestLink") or current_report.get("weakest_link") or "not labeled yet"
    answer = (
        f"The trade attached here is {title}. The app has it marked as {str(posture).lower()} risk with a setup score of {setup_score}. "
        f"The main weak point is {weakest}, and the amount-at-risk/max-loss anchor is {dollars(amount_at_risk)}.\n\n"
        "I can explain what that contract means, debate the setup, or show what has to go right for it to work."
    )
    cards = [
        {"label": "Selected trade", "value": title, "tone": "good"},
        {"label": "Risk posture", "value": str(posture), "tone": "warn"},
        {"label": "Risk anchor", "value": dollars(amount_at_risk), "tone": "risk"},
    ]
    blocks = [
        {
            "type": "mini_table",
            "title": "Trade context",
            "rows": [
                ["Setup score", str(setup_score)],
                ["Weakest link", str(weakest)],
                ["Best next ask", "Explain the risk or compare structure"],
            ],
        }
    ]
    return answer, cards, blocks


def uncertain_response(
    conversation_history: list[dict[str, Any]],
    current_report: dict[str, Any] | None,
    recent_checks: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    if current_report:
        title = report_title(current_report)
        return (
            f"No problem. I can start with the trade that is attached: {title}. I can explain what it is, what has to go right, or what the main risk is.",
            [{"label": "Attached", "value": title, "tone": "good"}],
            [{"type": "mini_table", "title": "Good next questions", "rows": [["1", "What is this trade?"], ["2", "What can go wrong?"], ["3", "Is the risk too large?"]]}],
        )
    if recent_checks:
        title = report_title(recent_checks[0].get("report") or recent_checks[0])
        return (
            f"No problem. The easiest place to start is your latest saved check: {title}. I can explain that trade, compare it to another structure, or break down the risk.",
            [{"label": "Latest saved", "value": title, "tone": "good"}],
            [{"type": "mini_table", "title": "Pick a lane", "rows": [["Explain", "What the contract means"], ["Review", "What makes it risky"], ["Compare", "Alternative structures"]]}],
        )
    if conversation_history:
        return (
            "No problem. Give me one thing to anchor on: a ticker, a contract screenshot, or a question like 'what is IV crush?' Then I can be specific instead of guessing.",
            [{"label": "Needed", "value": "Ticker or contract", "tone": "warn"}],
            [],
        )
    return (
        "No problem. Start with either a concept question, a contract screenshot, or a saved trade check. I will keep the explanation risk-first and plain English.",
        [{"label": "Best start", "value": "Contract screenshot", "tone": "good"}],
        [],
    )


def missing_trade_context_response() -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    answer = (
        "I do not see a trade attached to this chat yet. Tap Trade context to select a saved check, or send the contract details: ticker, call/put, strike, expiration, premium, and amount at risk.\n\n"
        "Once I have that, I can tell you what the trade is and what risk is doing the most damage."
    )
    cards = [{"label": "Trade context", "value": "Missing", "tone": "warn"}]
    blocks = [
        {
            "type": "mini_table",
            "title": "Details I need",
            "rows": [["Ticker", "AAPL, NVDA, etc."], ["Contract", "Call/put, strike, expiration"], ["Risk", "Premium or amount at risk"]],
        }
    ]
    return answer, cards, blocks


def attachment_needs_details_response(attachments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    extracted = extract_attachment_contract(attachments)
    if extracted.get("ticker") and (extracted.get("strike") or extracted.get("premium") or extracted.get("expiration")):
        fields = [
            ["Ticker", str(extracted.get("ticker") or "Unknown")],
            ["Side", str(extracted.get("side") or "Call/put not clear")],
            ["Strike", dollars(extracted.get("strike")) if extracted.get("strike") is not None else "Missing"],
            ["Expiration", str(extracted.get("expiration") or "Missing")],
            ["Premium", exact_dollars(extracted.get("premium")) if extracted.get("premium") is not None else "Missing"],
        ]
        missing = [label for label, value in fields if value == "Missing" or "not clear" in value.lower()]
        answer = (
            f"I can read enough from the upload to start: {extracted.get('ticker')} {extracted.get('side') or 'option'}"
            f"{' at ' + dollars(extracted.get('strike')) if extracted.get('strike') is not None else ''}. "
            "The important part is still risk math: premium paid, contracts, expiration, bid/ask, and whether the event/IV setup can shrink the option price."
        )
        if missing:
            answer += f" I still need {', '.join(missing[:3]).lower()} before treating this as a full review."
        cards = [
            {"label": "Upload read", "value": str(extracted.get("ticker")).upper(), "tone": "good"},
            {"label": "Missing", "value": str(len(missing)), "tone": "warn" if missing else "good"},
        ]
        blocks = [{"type": "mini_table", "title": "Extracted contract", "rows": fields}]
        return answer, cards, blocks

    names = ", ".join(str(item.get("name") or "attachment") for item in attachments[:2]) or "your upload"
    answer = (
        f"I see {names}. If the vision model is available, I can read the contract screenshot directly. If not, I need the key contract fields typed out: "
        "ticker, call/put, strike, expiration, premium, and amount at risk.\n\n"
        "Once I have those, I can explain the contract and point out the biggest risk pressure."
    )
    cards = [{"label": "Upload received", "value": str(len(attachments)), "tone": "good"}]
    blocks = [
        {
            "type": "mini_table",
            "title": "Contract fields",
            "rows": [["Ticker", "Underlying stock"], ["Strike/expiration", "Contract definition"], ["Premium", "Max-loss anchor"]],
        }
    ]
    return answer, cards, blocks


def saved_trade_lookup_response(recent_checks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    latest = (recent_checks[0].get("report") if recent_checks and "report" in recent_checks[0] else recent_checks[0]) if recent_checks else {}
    title = report_title(latest)
    posture = latest.get("riskPosture") or latest.get("risk_posture") or "mixed"
    setup_score = latest.get("setupScore") or latest.get("setup_score") or "--"
    weakest = latest.get("weakestLink") or latest.get("weakest_link") or "not labeled yet"
    risk_math = latest.get("riskMath") or latest.get("risk_math") or {}
    max_loss = dollars(risk_math.get("max_loss") or latest.get("amountAtRisk") or latest.get("amount_at_risk"))
    answer = (
        f"The latest saved trade check I can see is {title}. It is labeled {str(posture).lower()} risk, with a setup score of {setup_score}. "
        f"The weak point is {weakest}, and the max-loss anchor shown is {max_loss}.\n\n"
        "If this is the trade you mean, ask me to explain it, debate it, or simplify the risk."
    )
    cards = [
        {"label": "Latest check", "value": title, "tone": "good"},
        {"label": "Risk posture", "value": str(posture), "tone": "warn"},
        {"label": "Max loss", "value": max_loss, "tone": "risk"},
    ]
    blocks = [
        {
            "type": "mini_table",
            "title": "Snapshot",
            "rows": [["Setup score", str(setup_score)], ["Weakest link", str(weakest)], ["Question", "Is this the trade you meant?"]],
        }
    ]
    return answer, cards, blocks


def risk_math_response(message: str, user_profile: dict[str, Any] | None, attachments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lower = message.lower()
    account_size = float((user_profile or {}).get("accountSize") or 25000)
    risk_pct = float((user_profile or {}).get("riskBudgetPercent") or 2)
    parsed_numbers = [float(item.replace(",", "")) for item in re.findall(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", message)]
    parsed_answer = ""
    if len(parsed_numbers) >= 2:
        account_guess = max(parsed_numbers)
        risk_guess = min(parsed_numbers)
        if account_guess > 0 and risk_guess > 0:
            parsed_pct = risk_guess / account_guess * 100
            parsed_answer = (
                f"Using the numbers in your message, ${risk_guess:,.0f} on a ${account_guess:,.0f} account is about {parsed_pct:.1f}% of the account. "
                "For a long option, that premium is the max-loss anchor because it can go to zero. "
            )
    budget = account_size * risk_pct / 100
    if "guarantee" in lower or "safe options trade" in lower or "exactly which" in lower or "should i" in lower or "half my account" in lower:
        answer = (
            "I cannot pick a live trade or guarantee a safe options outcome. The useful move is to turn it into a risk check: ticker, strike, expiration, premium, account size, max loss, and event risk. "
            "If the premium loss would damage the account, the setup fails the risk test before direction even matters."
        )
    elif "stop loss" in lower or "stop losses" in lower:
        answer = (
            "Stop losses can fail on options because the contract can gap, liquidity can disappear, and the bid/ask spread can widen. "
            "That means the exit price you expect may not be the price you actually get, especially around earnings or fast markets."
        )
    elif "drawdown" in lower:
        answer = (
            "A drawdown matters because the math gets harder after losses. A 30% loss needs about a 43% gain just to recover. "
            "For options, repeated premium losses can compound quickly, so risk control is not just emotional discipline; it protects the ability to keep playing."
        )
    elif "position size" in lower or "sizing" in lower:
        answer = (
            "Position sizing for options starts with premium at risk, not upside. If the premium can go to zero, ask what percent of the account disappears in that case. "
            "Then compare that to your risk budget before caring about the possible win."
        )
    else:
        answer = parsed_answer or (
        f"Start with the amount that can disappear. With a ${account_size:,.0f} account and a {risk_pct:g}% risk budget, "
        f"one full-risk idea is about {dollars(budget)}. For long options, the premium can go to zero, so the premium is the real max-loss anchor. "
        )
        answer += "The cleanest review is: max loss, percent of account, breakeven move, days left, and whether IV can fall after the event."
    if attachments:
        answer += " If your upload has the premium or contract screen, I can use those details when they are readable."
    cards = [
        {"label": "Profile budget", "value": dollars(budget), "tone": "good"},
        {"label": "Risk rule", "value": f"{risk_pct:g}% max", "tone": "neutral"},
    ]
    blocks = [
        {
            "type": "mini_table",
            "title": "Position-size checklist",
            "rows": [
                ["1", "Premium at risk should be known before upside."],
                ["2", "Breakeven should be realistic for the time left."],
                ["3", "Event IV can make a correct direction still lose."],
            ],
        }
    ]
    return answer, cards, blocks


def strategy_response(message: str) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lower = message.lower()
    if "covered call" in lower and ("cash-secured" in lower or "secured put" in lower):
        answer = (
            "A covered call starts with owning shares, then selling a call to collect premium. It can add income, but it caps upside and does not protect much if the stock falls.\n\n"
            "A cash-secured put starts with cash, then selling a put. You collect premium, but you may be assigned shares at the strike. Both are income-style strategies, but one starts from owning shares and the other starts from being willing to buy shares."
        )
        title = "Covered call vs cash-secured put"
        rows = [["Covered call", "Own shares, sell call, cap upside"], ["Cash-secured put", "Hold cash, sell put, assignment possible"], ["Shared risk", "Stock downside still matters"]]
    elif "credit spread" in lower:
        answer = (
            "A credit spread collects premium upfront by selling one option and buying another option farther away as protection. Max gain is the credit received. "
            "Max loss is the spread width minus the credit.\n\n"
            "The risk is that the stock moves through the short strike. Around earnings, gaps can make that happen fast."
        )
        title = "Credit spread"
        rows = [["Max gain", "Credit received"], ["Max loss", "Spread width - credit"], ["Main risk", "Move through the short strike"]]
    elif "put debit spread" in lower or ("long put" in lower and "spread" in lower):
        answer = (
            "A long put is the cleaner downside bet: max loss is the premium, and downside payoff can keep growing as the stock falls. "
            "But it pays full price for time and IV.\n\n"
            "A put debit spread buys a higher-strike put and sells a lower-strike put. Max loss is the net debit paid, max gain is capped, and the cost is usually lower than a long put."
        )
        title = "Long put vs put debit spread"
        rows = [["Long put", "Open downside payoff, higher premium"], ["Put debit spread", "Capped payoff, lower net debit"], ["Trade-off", "Lower cost versus capped downside gain"]]
    elif "box" in lower:
        answer = (
            "A box spread combines a bull call spread and a bear put spread with the same strikes and expiration. In theory, it creates a fixed payoff like a synthetic loan. "
            "In practice, commissions, bid/ask spreads, early assignment, and margin rules can make it dangerous for small accounts."
        )
        title = "Box spread"
        rows = [["Structure", "Bull call spread + bear put spread"], ["Theory", "Fixed payoff"], ["Real risk", "Execution, assignment, and margin"]]
    elif "diagonal" in lower:
        answer = (
            "A diagonal spread uses different strikes and different expirations. It mixes a directional view with time-decay and volatility exposure, so it is less clean than a simple vertical spread.\n\n"
            "The main risk is that the short leg and long leg react differently to price movement, IV changes, and time decay."
        )
        title = "Diagonal spread"
        rows = [["Structure", "Different strikes and expirations"], ["Exposure", "Direction, theta, and IV"], ["Risk", "Legs do not move together"]]
    elif "calendar" in lower:
        answer = (
            "A calendar spread uses the same strike but different expirations. Usually, you sell the nearer-term option and buy the later-term option. "
            "The idea is to benefit from faster decay in the short option while keeping longer-dated exposure.\n\n"
            "The risk is that the stock moves too far away from the strike, or volatility changes hit the long and short legs differently."
        )
        title = "Calendar spread"
        rows = [["Structure", "Same strike, different expirations"], ["Main exposure", "Time decay and volatility term structure"], ["Risk", "Large move away from the strike"]]
    elif "iron condor" in lower or "condor" in lower:
        answer = (
            "An iron condor is a defined-risk range trade. It sells an out-of-the-money call spread and an out-of-the-money put spread. "
            "It tends to benefit if the stock stays inside the expected range and implied volatility falls.\n\n"
            "The danger is a large move through either side of the range, especially around earnings or news."
        )
        title = "Iron condor"
        rows = [["Structure", "Short call spread plus short put spread"], ["Helps when", "Stock stays range-bound"], ["Risk", "Large breakout or gap move"]]
    elif "butterfly" in lower:
        answer = (
            "A butterfly is a defined-risk structure built around a target price. It usually profits most if the stock finishes near the middle strike. "
            "It is cheaper than a simple long option, but the payoff zone is narrower.\n\n"
            "The main risk is being right on direction but wrong on the exact landing area."
        )
        title = "Butterfly"
        rows = [["Best case", "Stock finishes near middle strike"], ["Trade-off", "Cheap structure, narrow payoff zone"], ["Risk", "Move is too small or too large"]]
    elif "covered call" in lower:
        answer = (
            "A covered call means owning shares and selling a call against them. The call premium can add income, but it caps upside above the call strike. "
            "It is not a free-money strategy because the shares can still fall.\n\n"
            "The main trade-off is premium income now versus giving up some upside later."
        )
        title = "Covered call"
        rows = [["Requires", "Owning shares"], ["Benefit", "Collect call premium"], ["Risk", "Stock downside and capped upside"]]
    elif "cash-secured" in lower or "cash secured" in lower or "secured put" in lower:
        answer = (
            "A cash-secured put means selling a put while keeping enough cash to buy the shares if assigned. The premium is the income, but the stock can still fall far below the strike.\n\n"
            "The clean way to view it: you are being paid to accept possible stock ownership at the strike."
        )
        title = "Cash-secured put"
        rows = [["Requires", "Cash to buy shares"], ["Benefit", "Collect put premium"], ["Risk", "Stock falls below strike"]]
    elif "protective put" in lower:
        answer = (
            "A protective put is insurance on shares you already own. You buy a put so the downside is limited below the strike, but you pay premium for that protection.\n\n"
            "The trade-off is simple: less downside risk, but lower net return if the protection is not needed."
        )
        title = "Protective put"
        rows = [["Requires", "Owning shares"], ["Benefit", "Downside protection"], ["Cost", "Put premium"]]
    elif "collar" in lower:
        answer = (
            "A collar combines shares, a protective put, and a covered call. The put limits downside below one strike, while the call helps fund that protection but caps upside. "
            "It is a risk-control structure, not a pure upside bet."
        )
        title = "Collar"
        rows = [["Own", "Shares"], ["Buy", "Protective put"], ["Sell", "Covered call"], ["Trade-off", "Limit downside and cap upside"]]
    elif "ratio" in lower:
        answer = (
            "A ratio spread uses an uneven number of long and short options. It can look cheap because the shorts help fund the trade, but the extra short contracts can create ugly tail risk. "
            "The key danger is being exposed to a move that is larger than the structure can absorb."
        )
        title = "Ratio spread"
        rows = [["Structure", "Uneven long and short legs"], ["Appeal", "Lower upfront cost"], ["Danger", "Tail risk from extra shorts"]]
    elif "debit" in lower or "vertical" in lower or "spread" in lower:
        answer = (
            "For an earnings trade, a long call is the cleaner upside bet: one contract, max loss is the premium, and upside is open-ended. "
            "The problem is that it pays full price for time and implied volatility, so IV crush can hurt even if direction is right.\n\n"
            "A call debit spread buys one call and sells a higher-strike call. Max loss is still the net debit paid, but max gain is capped. "
            "The trade-off is lower cost and lower breakeven pressure versus giving up the huge upside tail."
        )
        title = "Long call vs debit spread"
        rows = [
            ["Long call", "Open-ended upside, highest premium sensitivity"],
            ["Debit spread", "Capped upside, lower net premium"],
            ["Earnings risk", "Both can still lose from IV crush"],
            ["Key question", "Is capped upside worth lower breakeven pressure?"],
        ]
    elif "straddle" in lower or "strangle" in lower:
        answer = (
            "Straddles and strangles are volatility structures. They usually need a large move, IV expansion, or both. "
            "Around earnings, the hard part is that IV can drop right after the event."
        )
        title = "Volatility structures"
        rows = [["Straddle", "Same strike call and put"], ["Strangle", "Different out-of-money strikes"], ["Risk", "Paying too much premium before IV crush"]]
    else:
        answer = (
            "The structure decides which risk you are accepting: direction, time decay, volatility change, capped payoff, or assignment risk. "
            "Two options on the same ticker can behave completely differently if the expiration, strike, or premium is different."
        )
        title = "Structure lens"
        rows = [["Direction", "Calls/puts depend on price movement"], ["Time", "Shorter expirations decay faster"], ["Volatility", "IV changes can dominate premium"]]
    cards = [{"label": "Comparison", "value": title, "tone": "good"}]
    blocks = [{"type": "mini_table", "title": title, "rows": rows}]
    return answer, cards, blocks


def concept_response(message: str, attachments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lower = message.lower()
    if "bid ask" in lower or "bid-ask" in lower or ("bid" in lower and "ask" in lower):
        answer = (
            "The bid/ask spread is the gap between what buyers are offering and what sellers are asking. In options, a wide spread is a liquidity warning. "
            "Even if the trade idea is right, a bad fill can make the risk/reward worse immediately."
        )
        title = "Bid/ask spread"
        rows = [["Bid", "Approximate price buyers pay"], ["Ask", "Approximate price sellers want"], ["Risk", "Wide spread means worse fills"]]
    elif "assignment" in lower:
        answer = (
            "Assignment risk means an option seller may be required to deliver on the contract. Short calls can require selling shares; short puts can require buying shares. "
            "Risk usually rises near expiration, around dividends, and when the option is in the money."
        )
        title = "Assignment risk"
        rows = [["Short call", "May have to sell shares"], ["Short put", "May have to buy shares"], ["Watch", "ITM options near expiration"]]
    elif "pin risk" in lower or "pinning" in lower or "pinned" in lower:
        answer = (
            "Pin risk happens near expiration when the stock sits very close to a strike. Small late moves can flip whether an option finishes in or out of the money, "
            "which makes assignment and next-day share exposure uncertain for short options."
        )
        title = "Pin risk"
        rows = [["When", "Near expiration"], ["Where", "Stock near strike"], ["Main issue", "Assignment uncertainty"]]
    elif "skew" in lower or "smile" in lower:
        answer = (
            "Volatility skew means options at different strikes can have different implied volatility. A smile is a related pattern where OTM calls and puts may both price richer than ATM options. "
            "This matters because two contracts on the same stock can be expensive for different reasons."
        )
        title = "Volatility skew"
        rows = [["Compares", "IV across strikes"], ["Why it matters", "Some strikes are relatively expensive"], ["Risk lens", "Do not compare premium alone"]]
    elif "term structure" in lower:
        answer = (
            "IV term structure compares implied volatility across expirations. Before an event, the near expiration can be priced much richer than later expirations because the event risk is concentrated there."
        )
        title = "IV term structure"
        rows = [["Compares", "IV across expirations"], ["Event effect", "Near-term IV can jump"], ["Risk lens", "Expiration choice changes the trade"]]
    elif "open interest" in lower:
        answer = (
            "Open interest is the number of option contracts that remain open. It is not the same as today's volume. Higher open interest can signal a more established contract, but it does not prove direction."
        )
        title = "Open interest"
        rows = [["Means", "Open contracts"], ["Different from", "Today's trading volume"], ["Use", "Liquidity context, not direction proof"]]
    elif "volume" in lower and "volatility" not in lower:
        answer = (
            "Option volume is how many contracts traded today. High volume can help liquidity and price discovery, but by itself it does not say whether calls or puts are smart."
        )
        title = "Option volume"
        rows = [["Means", "Contracts traded today"], ["Useful for", "Liquidity check"], ["Limit", "Not a signal by itself"]]
    elif "liquidity" in lower:
        answer = (
            "Option liquidity is about how easy it is to get a fair fill. The main clues are tight bid/ask spreads, decent volume, and enough open interest. Poor liquidity can turn a decent idea into a bad execution."
        )
        title = "Liquidity"
        rows = [["Good sign", "Tight bid/ask"], ["Also check", "Volume and open interest"], ["Risk", "Slippage and bad fills"]]
    elif "intrinsic" in lower or "extrinsic" in lower:
        answer = (
            "Intrinsic value is the value an option would have if exercised right now. Extrinsic value is the extra time and volatility value on top of that. "
            "IV crush and theta mainly attack extrinsic value."
        )
        title = "Intrinsic vs extrinsic"
        rows = [["Intrinsic", "Real in-the-money value"], ["Extrinsic", "Time and volatility value"], ["Main risk", "Extrinsic can decay fast"]]
    elif "exercise" in lower or "exercising" in lower or "exercised" in lower:
        answer = (
            "Exercising means using the option contract. For a call, that means buying shares at the strike; for a put, selling shares at the strike. "
            "Assignment is the other side: the short option holder is forced to fulfill the contract."
        )
        title = "Exercise"
        rows = [["Long call", "Can buy shares at strike"], ["Long put", "Can sell shares at strike"], ["Other side", "Short option can be assigned"]]
    elif "rho" in lower:
        answer = (
            "Rho measures how much an option's price may change when interest rates move. For most short-term retail options, rho is usually less important than delta, theta, and vega. "
            "It matters more for longer-dated options."
        )
        title = "Rho"
        rows = [["Measures", "Interest-rate sensitivity"], ["Usually small", "Short-dated options"], ["More relevant", "Longer expirations"]]
    elif "charm" in lower:
        answer = (
            "Charm measures how an option's delta changes as time passes, assuming the stock price is otherwise unchanged. Traders sometimes call it delta decay. "
            "It matters most near expiration because exposure can shift even if the stock barely moves."
        )
        title = "Charm"
        rows = [["Measures", "Delta change from time passing"], ["Also called", "Delta decay"], ["Watch", "Near-expiration contracts"]]
    elif "color" in lower:
        answer = (
            "Color measures how gamma changes as time passes. Gamma shows how quickly delta can change; color asks how that gamma exposure decays or intensifies over time. "
            "It is a second-order risk detail, mostly relevant near expiration or for portfolios with large gamma exposure."
        )
        title = "Color"
        rows = [["Measures", "Gamma change from time"], ["Related to", "Delta and gamma exposure"], ["Most relevant", "Near expiration or large books"]]
    elif "vanna" in lower:
        answer = (
            "Vanna connects delta and implied volatility. It describes how delta can change when IV changes, and also how vega can change as the stock moves. "
            "It is a second-order Greek, so it is usually a refinement after delta, theta, and vega."
        )
        title = "Vanna"
        rows = [["Links", "Delta and IV"], ["Useful for", "Volatility-sensitive positions"], ["Priority", "Second-order Greek"]]
    elif "vomma" in lower or "volga" in lower:
        answer = (
            "Vomma, also called volga, measures how vega changes when implied volatility changes. It matters most for trades that are very sensitive to volatility expansion or collapse."
        )
        title = "Vomma / volga"
        rows = [["Measures", "Vega sensitivity to IV"], ["Matters for", "Volatility-heavy trades"], ["Risk lens", "IV moves can accelerate"]]
    elif "max pain" in lower:
        answer = (
            "Max pain is the strike where the largest amount of listed option value would expire worthless for option buyers, based on open interest. "
            "It is sometimes used as a positioning clue, but it is not a reliable prediction tool by itself."
        )
        title = "Max pain"
        rows = [["Uses", "Open interest by strike"], ["Claims", "Where buyers lose most premium"], ["Limit", "Not a standalone forecast"]]
    elif "parity" in lower:
        answer = (
            "Put-call parity is the pricing relationship between a call, a put, the stock, and the strike for the same expiration. "
            "In plain English: calls and puts cannot drift too far from each other without creating an arbitrage-like mismatch."
        )
        title = "Put-call parity"
        rows = [["Compares", "Call, put, stock, strike"], ["Requires", "Same strike and expiration"], ["Use", "Pricing sanity check"]]
    elif "theta" in lower:
        answer = (
            "Theta is the rent you pay for holding an option. Every day that passes usually takes a little value out of a long call or put, "
            "especially near expiration. That means the stock can move sideways and the option can still lose value."
        )
        title = "Theta decay"
        rows = [["Hurts", "Long calls and long puts"], ["Speeds up", "Near expiration"], ["Watch", "Contracts held through quiet price action"]]
    elif has_any_term(lower, ["iv", "implied", "crush", "volatility"]):
        answer = (
            "IV crush is when the option gets cheaper because uncertainty disappears. Before earnings, traders pay extra premium because a big move is possible. "
            "After earnings, that mystery is gone, so the extra premium can deflate. That is why a call can lose money even if the stock goes up a little."
        )
        title = "IV crush"
        rows = [["Before event", "Premium can be inflated"], ["After event", "Uncertainty falls"], ["Risk", "Direction can be right but premium still drops"]]
    elif "earnings" in lower:
        answer = (
            "Earnings can affect calls in two opposite ways. A strong move up can help the call, but the option may also lose extra premium after the event "
            "because implied volatility drops. The key question is whether the stock move is big enough to beat both the premium paid and the post-earnings IV crush."
        )
        title = "Earnings and calls"
        rows = [["Can help", "Stock moves up enough"], ["Can hurt", "IV drops after the event"], ["Main test", "Move size versus premium and time left"]]
    elif "gamma" in lower:
        answer = (
            "Gamma shows how fast delta changes. Near expiration, gamma can get intense because a small stock move can quickly change how sensitive the option is. "
            "That is why short-dated options can feel calm one minute and violent the next."
        )
        title = "Gamma"
        rows = [["Measures", "Delta acceleration"], ["Biggest near", "Expiration and ATM strikes"], ["Risk", "Small stock moves can change exposure fast"]]
    elif has_any_term(lower, ["delta", "vega", "greek"]):
        answer = "Greeks are the contract dashboard. They tell you how the option reacts to price, time, and volatility."
        title = "Greeks"
        rows = [["Delta", "Price sensitivity"], ["Gamma", "Delta acceleration"], ["Theta", "Time decay"], ["Vega", "IV sensitivity"]]
    elif "weekly" in lower or "weeklies" in lower or "under 7 days" in lower:
        answer = (
            "Weekly options are risky because there is very little time for the thesis to work. Theta decay is faster, gamma can jump near the strike, "
            "and a small delay or bad fill can matter more than it would on a longer-dated contract."
        )
        title = "Weekly options"
        rows = [["Main pressure", "Fast theta decay"], ["Extra pressure", "Higher gamma near expiration"], ["Risk", "Less time to recover from being early"]]
    elif "event" in lower and "premium" in lower:
        answer = (
            "Options can get expensive before big events because uncertainty is priced into the premium. Traders pay for the chance of a large move. "
            "Once the event passes, that uncertainty can disappear and the option can deflate even if the direction was partly right."
        )
        title = "Event premium"
        rows = [["Before event", "Uncertainty raises premium"], ["After event", "IV can fall"], ["Risk", "Move must beat the premium paid"]]
    elif "breakeven" in lower or "break-even" in lower:
        answer = (
            "Breakeven is the stock price where the option finally covers what you paid. For a long call, it is strike plus premium. "
            "For a long put, it is strike minus premium. Before expiration, IV and theta can still make the option act differently."
        )
        title = "Breakeven"
        rows = [["Long call", "Strike + premium"], ["Long put", "Strike - premium"], ["Reality check", "Breakeven ignores early IV/theta changes"]]
    elif "premium" in lower:
        answer = (
            "Premium is the price of the option contract. For a long option, it is also the max-loss anchor because the contract can expire worthless. "
            "Premium is affected by stock price, strike, time left, implied volatility, and interest/dividend assumptions."
        )
        title = "Premium"
        rows = [["Means", "Option price"], ["Long option risk", "Premium can go to zero"], ["Moves with", "Price, time, IV, strike"]]
    elif "strike" in lower:
        answer = (
            "The strike is the price level the option is built around. For calls, lower strikes are usually more expensive and more stock-like. "
            "For puts, higher strikes are usually more expensive. The strike also controls moneyness: ITM, ATM, or OTM."
        )
        title = "Strike price"
        rows = [["Call", "Right to buy at strike"], ["Put", "Right to sell at strike"], ["Risk lens", "Far OTM needs a bigger move"]]
    elif "expiration" in lower:
        answer = (
            "Expiration is the deadline. Short expirations can move fast but decay quickly; longer expirations cost more but give the thesis more time. "
            "Near expiration, theta and gamma usually become more intense."
        )
        title = "Expiration"
        rows = [["Short-dated", "Cheaper, faster decay"], ["Longer-dated", "More time, higher premium"], ["Watch", "Theta and gamma near expiry"]]
    elif "itm" in lower or "otm" in lower or "atm" in lower or "moneyness" in lower:
        answer = (
            "Moneyness describes where the strike sits relative to the stock price. ITM options already have intrinsic value, ATM options sit near the stock price, "
            "and OTM options need a move before they have intrinsic value."
        )
        title = "Moneyness"
        rows = [["ITM", "Already has intrinsic value"], ["ATM", "Near current stock price"], ["OTM", "Needs a move to gain intrinsic value"]]
    elif "call" in lower and "put" not in lower:
        answer = (
            "A call option benefits when the stock moves up enough, fast enough. For a long call, max loss is the premium paid. "
            "The contract still has to overcome time decay, implied volatility changes, and the breakeven price."
        )
        title = "Call option"
        rows = [["Benefits from", "Stock moving up"], ["Max loss", "Premium paid"], ["Watch", "Theta, IV, breakeven"]]
    elif "put" in lower and "call" not in lower:
        answer = (
            "A put option benefits when the stock moves down enough, fast enough. For a long put, max loss is the premium paid. "
            "The contract still has to overcome time decay, implied volatility changes, and the breakeven price."
        )
        title = "Put option"
        rows = [["Benefits from", "Stock moving down"], ["Max loss", "Premium paid"], ["Watch", "Theta, IV, breakeven"]]
    else:
        answer = (
            "An option is a bet on movement, timing, and volatility at the same time. A call generally benefits from the stock going up; a put generally benefits from it going down. "
            "The premium is what you pay for that chance, and for a long option that premium is the amount that can go to zero."
        )
        title = "Option basics"
        rows = [["Call", "Benefits from upside"], ["Put", "Benefits from downside"], ["Premium", "Max loss for a long option"]]
    if attachments:
        answer += " I see an attachment on this message; if it contains contract details, the key fields are ticker, strike, expiration, premium, and bid/ask."
    cards = [
        {"label": "Concept", "value": title, "tone": "good"},
        {"label": "Risk lens", "value": "Premium first", "tone": "neutral"},
    ]
    blocks = [{"type": "mini_table", "title": title, "rows": rows}]
    return answer, cards, blocks


def simplify_response(message: str, conversation_history: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    topic = infer_topic(message, conversation_history)
    if topic == "iv":
        answer = (
            "Think of IV like air inside the option price. Before earnings, the option is puffed up because a big move might happen. "
            "After earnings, that air comes out. So even if the stock moves the right way, the option can still drop if the move was not big enough."
        )
        title = "IV crush, simpler"
        rows = [["Before", "Premium is inflated"], ["After", "Uncertainty drops"], ["Problem", "Right direction may still not be enough"]]
    elif topic == "theta":
        answer = (
            "Theta is basically a daily timer. If the stock does not move enough soon enough, the option slowly loses value just because time passed."
        )
        title = "Theta, simpler"
        rows = [["Meaning", "Time decay"], ["Hurts", "Long options"], ["Worse when", "Expiration is close"]]
    elif topic == "spread":
        answer = (
            "A long call is like paying more for unlimited upside. A debit spread is like paying less, but agreeing to cap the upside. "
            "So the trade-off is freedom versus controlled risk."
        )
        title = "Spread, simpler"
        rows = [["Long call", "More upside, more premium risk"], ["Debit spread", "Less premium, capped upside"], ["Main idea", "Pay less, cap more"]]
    elif topic == "risk":
        answer = (
            "Risk first means asking: if this goes wrong, how much money disappears? For long options, that number is usually the premium paid."
        )
        title = "Risk, simpler"
        rows = [["First question", "What can I lose?"], ["Long option", "Premium can go to zero"], ["Good check", "Does that fit the account?"]]
    else:
        answer = (
            "Simplest version: options are not just about being right on direction. You also have to be right enough, fast enough, and not overpay for the contract."
        )
        title = "Options, simpler"
        rows = [["Direction", "Stock move"], ["Time", "How soon it moves"], ["Premium", "What you paid"]]
    return answer, [{"label": "Simplified", "value": title, "tone": "good"}], [{"type": "mini_table", "title": title, "rows": rows}]


def followup_response(message: str, conversation_history: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    topic = infer_topic(message, conversation_history)
    if topic == "iv":
        answer = (
            "Because the option price includes two things: the stock move and the market's expectation of future movement. "
            "After earnings, that expectation often drops hard. If that drop is bigger than the benefit from the stock move, the option loses value."
        )
    elif topic == "theta":
        answer = (
            "Because an option has an expiration date. Every day with no useful move leaves less time for the contract to become profitable, so buyers usually pay a time-decay cost."
        )
    elif topic == "spread":
        answer = (
            "Because spreads trade some upside away in exchange for lower cost and cleaner max loss. They can be useful when the stock thesis is moderate instead of explosive."
        )
    elif topic == "risk":
        answer = (
            "Because options can look cheap per contract but expensive relative to account size. The right lens is not only percent gain; it is dollars at risk if the premium goes to zero."
        )
    else:
        answer = "Because options combine direction, timing, volatility, and price paid. Missing any one of those can make a correct idea still lose money."
    return answer, [], []


def infer_topic(message: str, conversation_history: list[dict[str, Any]]) -> str:
    text = " ".join([message] + [str(item.get("content") or "") for item in conversation_history[-6:]]).lower()
    if has_any_term(text, ["iv", "implied volatility", "volatility", "crush", "earnings"]):
        return "iv"
    if has_any_term(text, ["theta", "time decay", "expiration", "decay"]):
        return "theta"
    if has_any_term(text, ["spread", "debit", "credit", "long call", "long put", "straddle", "strangle"]):
        return "spread"
    if has_any_term(text, ["risk", "loss", "premium", "budget", "position size", "sizing"]):
        return "risk"
    return "general"


def sanitize_attachments(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = []
    for item in attachments[:4]:
        name = str(item.get("name") or "attachment")[:120]
        mime = str(item.get("type") or "")[:80]
        source = str(item.get("source") or "file")[:40]
        size = int(item.get("size") or 0)
        text = str(item.get("text") or "")[:4000]
        data_url = str(item.get("dataUrl") or item.get("data_url") or "")
        clean_item = {"name": name, "type": mime, "source": source, "size": size}
        if text:
            clean_item["text"] = text
        if data_url.startswith("data:image/") and len(data_url) < 1_800_000:
            clean_item["dataUrl"] = data_url
        clean.append(clean_item)
    return clean


def attachment_text_context(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": item.get("name"),
            "type": item.get("type"),
            "source": item.get("source"),
            "size": item.get("size"),
            "text": item.get("text", "")[:1500],
            "imageIncluded": bool(item.get("dataUrl")),
        }
        for item in attachments
    ]


def attachment_source_summary(attachments: list[dict[str, Any]]) -> str:
    sources = [str(item.get("source") or "file").replace("_", " ").title() for item in attachments]
    if not sources:
        return "None"
    unique = []
    for source in sources:
        if source not in unique:
            unique.append(source)
    return ", ".join(unique[:2])


def attachment_context_rows(attachments: list[dict[str, Any]]) -> list[list[str]]:
    rows = []
    for item in attachments[:4]:
        kind = "Image" if str(item.get("type") or "").startswith("image/") else "File"
        source = str(item.get("source") or "file").replace("_", " ").title()
        readable = "Text readable" if item.get("text") else ("Image included" if item.get("dataUrl") else "Metadata only")
        rows.append([str(item.get("name") or kind)[:28], f"{source}; {readable}"])
    return rows or [["Attachment", "No readable context"]]


def extract_attachment_contract(attachments: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(str(item.get("text") or "") for item in attachments)
    upper = text.upper()
    if not upper.strip():
        return {}
    labeled_ticker = re.search(r"\b(?:TICKER|SYMBOL|UNDERLYING)\s*(?:IS|=|:)?\s*\$?([A-Z]{1,5})\b", upper)
    ticker_match = labeled_ticker or re.search(r"(?<![A-Z])\$?([A-Z]{1,5})(?:\s+(?:CALL|PUT)|\s+\$?\d{1,4}(?:\.\d{1,2})?)", upper)
    side = None
    if re.search(r"\bCALL\b", upper):
        side = "Call"
    elif re.search(r"\bPUT\b", upper):
        side = "Put"
    strike = parse_attachment_number(text, ["strike", "strk"])
    premium = parse_attachment_number(text, ["premium", "mid", "debit", "paid", "cost"])
    if premium is None:
        premium_match = re.search(r"(?:PREMIUM|MID|DEBIT|COST|PAID)\D{0,12}([0-9]+(?:\.[0-9]+)?)", upper)
        premium = attachment_number_from_value(premium_match.group(1)) if premium_match else None
    expiration = None
    exp_match = re.search(r"(?:EXPIRATION|EXP|EXPIRES?)\D{0,12}([A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    if exp_match:
        expiration = exp_match.group(1)
    return {
        "ticker": ticker_match.group(1) if ticker_match else None,
        "side": side,
        "strike": strike,
        "premium": premium,
        "expiration": expiration,
    }


def parse_attachment_number(text: str, labels: list[str]) -> float | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*(?:is|=|:)?\s*\$?\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if match:
            return attachment_number_from_value(match.group(1))
    if labels[0] in {"strike", "strk"}:
        match = re.search(r"\b(?:CALL|PUT)\s+\$?\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if match:
            return attachment_number_from_value(match.group(1))
    return None


def attachment_number_from_value(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def compact_profile(user_profile: dict[str, Any] | None) -> dict[str, Any]:
    if not user_profile:
        return {}
    keys = [
        "accountSize",
        "riskBudgetPercent",
        "experienceLevel",
        "riskStyle",
        "tradeFocus",
        "struggles",
        "sectors",
        "marketCaps",
        "aiMemory",
        "riskRules",
        "coachStyle",
        "savedContext",
    ]
    return {key: user_profile.get(key) for key in keys if key in user_profile}


def compact_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {}
    keys = [
        "ticker",
        "tradeType",
        "strike",
        "expiration",
        "amountAtRisk",
        "timeframe",
        "setupScore",
        "riskScore",
        "overallRead",
        "weakestLink",
        "riskPosture",
        "riskMath",
        "contractLabel",
        "setupDebate",
        "questions",
    ]
    return {key: report.get(key) for key in keys if key in report}


def should_use_fast_path(
    message: str,
    mode: str,
    current_report: dict[str, Any] | None,
    attachments: list[dict[str, Any]],
) -> bool:
    lower = message.lower().strip()
    has_image = any(str(item.get("type") or "").startswith("image/") and item.get("dataUrl") for item in attachments)
    if has_image:
        return False
    if mode == "attachment_needs_details":
        return True
    if mode in {
        "greeting",
        "smalltalk",
        "missing_trade_context",
        "saved_trade_lookup",
        "trade_identity",
    }:
        return True
    return False


def compact_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for item in messages[-10:]:
        content = " ".join(str(item.get("content") or "").split())
        if not content:
            continue
        compact.append(
            {
                "role": item.get("role", "user"),
                "content": content[:700],
                "mode": item.get("mode"),
                "attachments": [
                    {"name": attachment.get("name"), "type": attachment.get("type")}
                    for attachment in (item.get("attachments") or [])[:3]
                ],
            }
        )
    return compact


def compact_saved_checks(saved_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for item in saved_checks[:5]:
        report = item.get("report") or item
        if not isinstance(report, dict):
            continue
        compact.append(
            {
                "id": item.get("id") or report.get("id"),
                "createdAt": item.get("createdAt") or report.get("createdAt"),
                "note": str(item.get("note") or "")[:400],
                "report": compact_report(report),
            }
        )
    return compact


def asks_about_existing_trade(lower: str) -> bool:
    trade_terms = ["trade", "check", "contract", "position", "setup"]
    ownership_terms = ["i did", "my", "latest", "last", "saved", "attached", "selected", "the one"]
    if any(term in lower for term in trade_terms) and any(term in lower for term in ownership_terms):
        return True
    return lower in {
        "what is the trade",
        "what trade",
        "what did i do",
        "what is this",
        "explain this",
        "explain my trade",
    }


def asks_about_trade_identity(lower: str) -> bool:
    identity_phrases = [
        "what is the trade",
        "what trade",
        "what did i do",
        "which trade",
        "what is my trade",
        "what position",
        "what contract",
    ]
    return any(phrase in lower for phrase in identity_phrases)


def is_known_concept_prompt(message: str) -> bool:
    lower = message.lower()
    known_terms = [
        "iv",
        "implied",
        "volatility",
        "crush",
        "earnings",
        "theta",
        "delta",
        "gamma",
        "vega",
        "rho",
        "charm",
        "color",
        "vanna",
        "vomma",
        "volga",
        "greek",
        "max pain",
        "parity",
        "breakeven",
        "break-even",
        "premium",
        "strike",
        "expiration",
        "call",
        "put",
        "assignment",
        "exercise",
        "box",
        "diagonal",
        "bid",
        "ask",
        "liquidity",
        "volume",
        "open interest",
        "pin",
        "skew",
        "smile",
        "term structure",
        "intrinsic",
        "extrinsic",
        "itm",
        "otm",
        "atm",
    ]
    return has_any_term(lower, known_terms)


def has_any_term(text: str, terms: list[str]) -> bool:
    normalized = text.lower()
    for term in terms:
        clean = term.lower().strip()
        if not clean:
            continue
        if " " in clean or "-" in clean:
            if clean in normalized:
                return True
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(clean)}(?![a-z0-9])", normalized):
            return True
    return False


def report_title(report: dict[str, Any]) -> str:
    ticker = report.get("ticker") or "Trade"
    trade_type = report.get("tradeType") or report.get("trade_type") or "check"
    strike = report.get("strike")
    expiration = report.get("expiration")
    pieces = [str(ticker).upper(), str(trade_type)]
    if strike not in (None, ""):
        pieces.append(f"${strike}")
    if expiration:
        pieces.append(str(expiration))
    return " ".join(pieces)


def clean_answer(answer: str) -> str:
    text = answer.strip()
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?m)^\s*[\*\u2022]\s+", "- ", text)
    text = re.sub(r"(?m)^\s*-\s{2,}", "- ", text)
    endings = [
        "Educational only. Not financial advice.",
        "This is educational only, not financial advice.",
        "Not financial advice.",
    ]
    for ending in endings:
        if text.endswith(ending):
            text = text[: -len(ending)].strip()
    generic_endings = [
        "If you have any questions or need further clarification, feel free to ask!",
        "If you'd like to discuss any of these points further or have questions about Greeks, feel free to ask!",
        "Feel free to ask!",
    ]
    for ending in generic_endings:
        text = text.replace(ending, "").strip()
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if len(paragraphs) > 3:
        text = "\n\n".join(paragraphs[:3])
    words = text.split()
    if len(words) > 180:
        text = " ".join(words[:180]).rstrip(" ,;:") + "."
    return text


def is_low_quality_llm_answer(answer: str, mode: str) -> bool:
    stripped = answer.strip()
    if not stripped:
        return True
    words = stripped.split()
    if mode not in {"greeting", "smalltalk"} and len(words) < 16:
        return True
    if mode not in {"greeting", "smalltalk"} and stripped[-1] not in ".!?":
        return True
    if stripped.lower() in {"i don't know.", "i am not sure.", "i can't help with that."}:
        return True
    return False


def dollars(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return f"${number:,.0f}"


def exact_dollars(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return f"${number:,.2f}"


def suggested_prompts(current_report: dict[str, Any] | None = None) -> list[str]:
    if current_report:
        weakest = current_report.get("weakestLink") or current_report.get("weakest_link") or "the weakest link"
        return [
            "Debate this setup",
            f"Explain {weakest} in plain English",
            "What can break this trade?",
            "Explain the contract label",
            "Check my position size",
        ]
    return [
        "Explain IV crush",
        "What is theta decay?",
        "Compare a long call and a debit spread",
        "How do earnings affect calls?",
        "What makes a contract risky?",
    ]
