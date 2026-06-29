from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from .ai_tools import build_ai_tool_context
from .llm_provider import configured_providers, generate_answer


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
    analysis_depth: str = "standard",
    attachments: list[dict[str, Any]] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    recent_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    clean_attachments = sanitize_attachments(attachments or [])
    attachment_contract = attachment_contract_context(clean_attachments)
    clean_history = compact_history(conversation_history or [])
    clean_recent_checks = compact_saved_checks(recent_checks or [])
    mode = classify_message(message, current_report, chat_mode, clean_attachments, clean_history, clean_recent_checks)
    tool_context = await build_ai_tool_context(
        message=message,
        mode=mode,
        current_report=current_report,
        user_profile=user_profile,
        recent_checks=clean_recent_checks,
        attachment_contract=attachment_contract,
    )
    tool_context["context_manifest"] = coach_context_manifest(
        current_report=current_report,
        user_profile=user_profile,
        recent_checks=clean_recent_checks,
        conversation_history=clean_history,
        attachments=clean_attachments,
        tool_context=tool_context,
    )
    response = build_structured_response(
        message,
        mode,
        analysis_depth,
        current_report,
        user_profile,
        clean_attachments,
        clean_history,
        clean_recent_checks,
    )
    apply_tool_context(response, tool_context)
    apply_analysis_depth(response, analysis_depth, current_report, tool_context)
    enforce_response_contract(response)

    response["provider"] = "fallback"
    response["model"] = "deterministic-options-coach"
    response["used_fallback"] = True

    apply_profile_voice(response, tool_context)

    if should_use_fast_path(message, mode, current_report, clean_attachments) and analysis_depth != "deep_analysis":
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
            rejection_reasons = llm_answer_rejection_reasons(llm_answer, response, mode, message, tool_context)
            if not rejection_reasons:
                response["answer"] = llm_answer
                response["provider"] = llm_result.provider
                response["model"] = llm_result.model
                response["used_fallback"] = False
                apply_profile_voice(response, tool_context)
                enforce_response_contract(response)
            else:
                response["llm_rejection_reasons"] = rejection_reasons
    except Exception:
        pass

    apply_profile_voice(response, tool_context)
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
        "Use RiskWise-specific language: premium, breakeven, DTE, max loss, IV, liquidity, and missing data when those are relevant. "
        "Avoid textbook openings like 'X is a phenomenon where' or broad definitions that ignore the actual question. "
        "If profile memory says simple, explain plainly. If it says quant-heavy, include one concrete metric from server facts. "
        "If it says strict risk, anchor the answer on max loss, invalidation, or missing data. "
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
    if any(
        phrase in lower
        for phrase in [
            "guarantee me",
            "safe options trade",
            "exactly which",
            "should i buy",
            "should i sell",
            "should i enter",
            "should i exit",
            "what should i buy",
            "what should i sell",
            "half my account",
            "all in",
        ]
    ):
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
    if not current_report and (lower in {"why", "how", "what", "wdym"} or lower.startswith(("what do you mean", "wdym")) or (
        lower.startswith(("why ", "how ")) and not has_direct_topic
    )):
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
    if "premium" in lower and any(phrase in lower for phrase in ["go to zero", "worthless", "expire worthless", "why can premium"]):
        return "concept"
    if has_any_term(lower, ["spy", "market", "index"]) and has_any_term(lower, ["single stock", "stock calls", "calls"]):
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
    if has_any_term(lower, ["size", "sizing", "max loss", "drawdown", "budget", "loss", "capital", "account risk", "risk percent"]):
        return "risk_math"
    if has_any_term(lower, ["what can you do", "who are you", "help"]):
        return "greeting"
    if mode_choice == "explain":
        return "general_finance"
    return "fallback"


def build_structured_response(
    message: str,
    mode: str,
    analysis_depth: str,
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
        answer, cards, blocks = saved_trade_lookup_response(message, recent_checks)
    elif mode == "trade_identity" and current_report:
        answer, cards, blocks = trade_identity_response(current_report)
    elif mode == "attachment_needs_details":
        answer, cards, blocks = attachment_needs_details_response(message, attachments)
    elif mode == "simplify":
        answer, cards, blocks = simplify_response(message, conversation_history)
    elif mode == "followup":
        answer, cards, blocks = followup_response(message, conversation_history)
    elif mode == "trade_review" and current_report:
        answer, cards, blocks = report_review_response(message, current_report, attachments)
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
        "analysis_depth": analysis_depth,
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
    response["normalized_context"] = {
        "ticker": tool_context.get("ticker"),
        "missing_data": tool_context.get("missing_data", []),
        "risk_flags": tool_context.get("risk_flags", []),
        "tools_used": tool_context.get("tools_used", []),
        "coach_context": tool_context.get("coach_context") or {},
        "data_quality": normalized_data_quality(tool_results),
        "selected_contract": normalized_selected_contract(tool_results),
        "selected_trade": normalized_selected_trade(tool_results),
        "uploaded_contract": normalized_uploaded_contract(tool_results),
        "profile_memory": normalized_profile_memory(tool_results),
        "saved_check_matches": normalized_saved_check_matches(tool_results),
        "fact_tools": normalized_fact_tools(tool_results),
        "missing_categories": normalized_missing_categories(tool_results),
        "context_manifest": tool_context.get("context_manifest") or {},
    }
    response["what_used"] = human_tool_names(response["tools_used"])
    response["provider_status"] = {"providers": configured_providers(), "fallback_available": True}

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
        elif name == "parse_uploaded_contract":
            fields = result.get("fields") or {}
            status = str(result.get("status") or "unknown")
            ticker = fields.get("ticker") or "Unknown"
            missing_fields = [str(item).replace("_", " ") for item in result.get("missing_fields") or []]
            if fields:
                response["summary_cards"].append({"label": "Upload parsed", "value": str(ticker).upper(), "tone": "good"})
            elif result.get("attachments"):
                response["summary_cards"].append({"label": "Upload parsed", "value": "Needs review", "tone": "warn"})
            tool_rows.append(["Uploaded contract", f"{status}; missing {', '.join(missing_fields[:3]) or 'none flagged'}"])
            if fields:
                response["visual_blocks"].append(
                    {
                        "type": "mini_table",
                        "title": "Uploaded contract parsed",
                        "rows": [
                            ["Ticker", str(fields.get("ticker") or "Missing")],
                            ["Side", str(fields.get("optionSide") or fields.get("tradeType") or "Missing")],
                            ["Strike", dollars(fields.get("strike")) if fields.get("strike") is not None else "Missing"],
                            ["Expiration", str(fields.get("expiration") or "Missing")],
                            ["Premium", exact_dollars(fields.get("premium")) if fields.get("premium") is not None else "Missing"],
                            ["Contracts", str(fields.get("contracts") or "Missing")],
                        ],
                    }
                )
        elif name == "retrieve_saved_checks" and result.get("status") == "ok":
            matches = result.get("matches") or []
            if matches:
                response["summary_cards"].append({"label": "Memory", "value": f"{len(matches)} checks", "tone": "neutral"})
                tool_rows.append(["Relevant checks", ", ".join(str(item.get("title") or item.get("ticker") or "check") for item in matches[:2])])
        elif name == "retrieve_profile_memory" and result.get("status") == "ok":
            style = result.get("preferred_explanation") or "Step-by-step"
            strictness = result.get("risk_strictness") or result.get("risk_style") or "Balanced"
            response["summary_cards"].append({"label": "Style", "value": str(style), "tone": "neutral"})
            tool_rows.append(["Profile memory", f"{style}; {strictness} risk lens"])
            response["visual_blocks"].append(
                {
                    "type": "mini_table",
                    "title": "AI memory used",
                    "rows": [
                        ["Experience", str(result.get("experience_level") or "Not set")],
                        ["Risk style", str(result.get("risk_style") or "Balanced")],
                        ["Explanation", str(style)],
                        ["Strictness", str(strictness)],
                    ],
                }
            )
        elif name == "calculate_dte":
            dte = result.get("calendar_days_left") or result.get("trading_days_left")
            if dte is not None:
                response["summary_cards"].append({"label": "DTE", "value": f"{dte}d", "tone": "neutral"})
                tool_rows.append(["DTE", f"{dte} days via backend risk math"])
        elif name == "calculate_liquidity_score":
            score = result.get("score")
            if score is not None:
                label = str(result.get("label") or "estimated")
                response["summary_cards"].append({"label": "Liquidity", "value": f"{score}/100", "tone": "warn" if int(score) < 65 else "good"})
                detail = f"{score}/100 {label}; missing {', '.join(result.get('missing') or []) or 'none'}"
                if result.get("spread_width_pct") is not None:
                    detail += f"; spread {result['spread_width_pct']}%"
                tool_rows.append(["Liquidity score", detail])
        elif name == "retrieve_selected_trade" and result.get("status") == "ok":
            pressures = ", ".join(result.get("pressure_points") or []) or result.get("title") or "selected check"
            tool_rows.append(["Selected trade", pressures])
        elif name == "detect_missing_data":
            categories = result.get("categories") or {}
            if categories:
                response["visual_blocks"].append(
                    {
                        "type": "mini_table",
                        "title": "Missing-data detector",
                        "rows": [[label.replace("_", " ").title(), ", ".join(values[:4])] for label, values in categories.items()],
                    }
                )
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
    manifest = tool_context.get("context_manifest") or {}
    if manifest:
        response["visual_blocks"].append(
            {
                "type": "mini_table",
                "title": "Coach context available",
                "rows": context_manifest_rows(manifest),
            }
        )


def normalized_data_quality(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    ready: set[str] = set()
    missing: set[str] = set()
    providers: set[str] = set()
    for item in tool_results:
        result = item.get("result") or {}
        provider = result.get("provider")
        if provider:
            providers.add(str(provider))
        for field in result.get("fields_ready") or []:
            ready.add(str(field).replace("_", " "))
        for field in result.get("fields_pending") or result.get("missing") or []:
            missing.add(str(field).replace("_", " "))
    label = "partial" if missing else "ready" if ready else "unknown"
    return {"label": label, "ready": sorted(ready), "missing": sorted(missing), "providers": sorted(providers)}


def coach_context_manifest(
    *,
    current_report: dict[str, Any] | None,
    user_profile: dict[str, Any] | None,
    recent_checks: list[dict[str, Any]],
    conversation_history: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
    tool_context: dict[str, Any],
) -> dict[str, Any]:
    tool_results = tool_context.get("tool_results") or []
    data_quality = normalized_data_quality(tool_results)
    uploaded = normalized_uploaded_contract(tool_results)
    coach_context = tool_context.get("coach_context") or {}
    availability = coach_context.get("availability") or {}
    missing_categories = coach_context.get("missing_categories") or {}
    return {
        "selected_check": bool(current_report),
        "saved_checks": len(recent_checks),
        "profile_memory": bool(user_profile),
        "recent_chat_messages": len(conversation_history),
        "uploaded_contract": bool(uploaded.get("fields")),
        "attachments": len(attachments),
        "primary_source": coach_context.get("primary_source") or ("selected_check" if current_report else "question_only"),
        "tool_count": availability.get("tool_count") or len(tool_results),
        "market_data_status": data_quality.get("label") or "unknown",
        "missing_data": len(tool_context.get("missing_data") or []),
        "missing_categories": missing_categories,
        "guardrails": coach_context.get("guardrails") or [],
        "answer_guidance": coach_context.get("answer_guidance") or [],
    }


def context_manifest_rows(manifest: dict[str, Any]) -> list[list[str]]:
    rows = [
        ["Primary source", str(manifest.get("primary_source") or "question_only")],
        ["Selected check", "Available" if manifest.get("selected_check") else "Not selected"],
        ["Saved checks", str(manifest.get("saved_checks") or 0)],
        ["Profile memory", "Available" if manifest.get("profile_memory") else "Not set"],
        ["Recent chat", f"{manifest.get('recent_chat_messages') or 0} messages"],
        ["Uploaded contract", "Parsed" if manifest.get("uploaded_contract") else "None parsed"],
        ["Market data", str(manifest.get("market_data_status") or "unknown")],
        ["Missing data", str(manifest.get("missing_data") or 0)],
        ["Tools", str(manifest.get("tool_count") or 0)],
    ]
    guidance = manifest.get("answer_guidance") or []
    if guidance:
        rows.append(["Coach guidance", str(guidance[0])[:90]])
    return rows


def normalized_selected_trade(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in tool_results:
        if item.get("name") == "retrieve_selected_trade":
            result = item.get("result") or {}
            return {
                "status": result.get("status"),
                "source": result.get("source"),
                "title": result.get("title"),
                "pressure_points": result.get("pressure_points") or [],
                "missing_data": result.get("missing_data") or [],
                "data_quality": result.get("data_quality") or {},
                "report": result.get("report") or {},
            }
    return {}


def normalized_selected_contract(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in tool_results:
        if item.get("name") == "get_option_contract":
            result = item.get("result") or {}
            selected = result.get("selected") or {}
            return {
                "ticker": result.get("ticker") or selected.get("symbol"),
                "contract_symbol": selected.get("contract_symbol") or selected.get("ticker"),
                "expiration": selected.get("expiration") or selected.get("expiration_date"),
                "strike": selected.get("strike") or selected.get("strike_price"),
                "option_side": selected.get("optionSide") or selected.get("contract_type"),
                "moneyness": selected.get("moneynessLabel"),
                "status": result.get("status"),
            }
    return {}


def normalized_uploaded_contract(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in tool_results:
        if item.get("name") == "parse_uploaded_contract":
            result = item.get("result") or {}
            return {
                "status": result.get("status"),
                "fields": result.get("fields") or {},
                "missing_fields": result.get("missing_fields") or [],
                "confidence": result.get("confidence"),
                "provider": result.get("provider"),
            }
    return {}


def normalized_profile_memory(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in tool_results:
        if item.get("name") == "retrieve_profile_memory":
            result = item.get("result") or {}
            return {
                "experience_level": result.get("experience_level"),
                "risk_style": result.get("risk_style"),
                "preferred_explanation": result.get("preferred_explanation"),
                "question_style": result.get("question_style"),
                "risk_strictness": result.get("risk_strictness"),
                "risk_rules": result.get("risk_rules") or {},
                "common_mistakes": result.get("common_mistakes") or [],
            }
    return {}


def normalized_saved_check_matches(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in tool_results:
        if item.get("name") == "retrieve_saved_checks":
            result = item.get("result") or {}
            return (result.get("matches") or [])[:5]
    return []


def normalized_fact_tools(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    names = {
        "calculate_max_loss": "max_loss",
        "calculate_breakeven": "breakeven",
        "calculate_dte": "dte",
        "calculate_liquidity_score": "liquidity",
    }
    for item in tool_results:
        name = item.get("name")
        if name in names:
            facts[names[name]] = item.get("result") or {}
    return facts


def normalized_missing_categories(tool_results: list[dict[str, Any]]) -> dict[str, list[str]]:
    for item in tool_results:
        if item.get("name") == "detect_missing_data":
            result = item.get("result") or {}
            return result.get("categories") or {}
    return {}


def human_tool_names(tools_used: list[dict[str, Any]]) -> list[str]:
    labels = {
        "get_quote": "stock quote",
        "get_company_profile": "company profile",
        "get_earnings": "earnings calendar",
        "get_news": "news context",
        "get_options_context": "options data status",
        "get_option_chain": "option chain/reference",
        "get_option_contract": "selected contract",
        "calculate_max_loss": "max loss math",
        "calculate_breakeven": "breakeven math",
        "calculate_dte": "DTE math",
        "calculate_liquidity_score": "liquidity score",
        "retrieve_selected_trade": "selected-trade retriever",
        "detect_missing_data": "missing-data detector",
        "retrieve_saved_checks": "relevant saved checks",
        "retrieve_profile_memory": "profile memory",
        "get_saved_trade": "saved trade",
        "get_current_report": "selected check",
        "parse_uploaded_contract": "uploaded contract parser",
        "search_ticker": "ticker search",
    }
    result: list[str] = []
    for tool in tools_used:
        name = tool.get("name")
        label = labels.get(name, name)
        if label and label not in result:
            result.append(str(label))
    return result


def enforce_response_contract(response: dict[str, Any]) -> None:
    defaults: dict[str, Any] = {
        "answer": "",
        "analysis_depth": "standard",
        "mode": "fallback",
        "summary_cards": [],
        "visual_blocks": [],
        "suggested_prompts": [],
        "confidence": 0.6,
        "missing_data": [],
        "risk_flags": [],
        "tools_used": [],
        "what_used": [],
        "agent_docket": [],
        "normalized_context": {},
        "provider_status": {"providers": configured_providers(), "fallback_available": True},
        "llm_rejection_reasons": [],
    }
    for key, value in defaults.items():
        if key not in response or response[key] is None:
            response[key] = value
    response["answer"] = clean_answer(str(response.get("answer") or "I can help once I have a ticker, contract, or options question."))


def apply_analysis_depth(
    response: dict[str, Any],
    analysis_depth: str,
    current_report: dict[str, Any] | None,
    tool_context: dict[str, Any],
) -> None:
    if analysis_depth != "deep_analysis":
        return
    docket = committee_docket(current_report, tool_context)
    score = committee_score(docket)
    response["agent_docket"] = docket
    response["summary_cards"].append(
        {
            "label": "Committee",
            "value": f"{score}/100",
            "tone": "good" if score >= 75 else "warn",
        }
    )
    response["visual_blocks"].append({"type": "agent_committee", "title": "Risk committee", "agents": docket})
    top_risks = [str(item.get("weakest_evidence") or item.get("finding") or "") for item in docket if item.get("stance") != "supportive"][:3]
    response["risk_flags"] = sorted(set([*response.get("risk_flags", []), *[item for item in top_risks if item]]))
    response["visual_blocks"].append(
        {
            "type": "mini_table",
            "title": "Committee synthesis",
            "rows": [
                ["Committee score", f"{score}/100"],
                ["Strongest evidence", best_agent_finding(docket)],
                ["Weakest evidence", worst_agent_finding(docket)],
                ["Next question", best_next_question(docket)],
            ],
        }
    )
    missing = tool_context.get("missing_data", [])
    what_used = response.get("what_used") or human_tool_names(tool_context.get("tool_results") or [])
    response["visual_blocks"].append(
        {
            "type": "mini_table",
            "title": "Risk map",
            "rows": [
                ["Thesis", report_title(current_report) if current_report else "No selected check"],
                ["Max loss", dollars((current_report or {}).get("amountAtRisk") or ((current_report or {}).get("riskMath") or {}).get("max_loss")) if current_report else "Unknown"],
                ["Liquidity warning", "Missing bid/ask, volume, or open interest" if any(term in " ".join(map(str, missing)).lower() for term in ["bid", "ask", "volume", "open interest"]) else "No missing liquidity fields flagged"],
                ["Data honesty", ", ".join(missing[:4]) or "No missing fields flagged"],
            ],
        }
    )
    response["visual_blocks"].append(
        {
            "type": "mini_table",
            "title": "Scenario table",
            "rows": [
                ["Works if", best_agent_finding(docket)],
                ["Breaks if", worst_agent_finding(docket)],
                ["Before trusting", best_next_question(docket)],
            ],
        }
    )
    response["visual_blocks"].append(
        {
            "type": "mini_table",
            "title": "Beginner explanation",
            "rows": [
                ["Plain read", "The contract must beat premium, time decay, and missing data before the upside story matters."],
                ["Final verdict", "Cautious until the weakest evidence and missing live fields are confirmed."],
            ],
        }
    )
    if top_risks:
        response["visual_blocks"].append(
            {
                "type": "mini_table",
                "title": "Top risks",
                "rows": [[str(index + 1), risk] for index, risk in enumerate(top_risks)],
            }
        )
    response["visual_blocks"].append(
        {
            "type": "mini_table",
            "title": "What RiskWise used",
            "rows": [
                ["Inputs", ", ".join(what_used[:5]) or "Selected check context"],
                ["Missing live data", ", ".join([str(item) for item in missing[:6]]) or "No missing fields flagged"],
                ["Guardrail", "Backend math is used for max loss, breakeven, DTE, and data quality."],
            ],
        }
    )
    top_risk_text = "; ".join(top_risks[:2]) if top_risks else "no extra committee risks were flagged"
    missing_text = ", ".join([str(item) for item in missing[:4]]) or "no missing fields were flagged"
    used_text = ", ".join(what_used[:4]) or "the selected check context"
    if current_report:
        response["answer"] = clean_answer(
            f"Deep analysis is ready. The committee score is {score}/100. "
            f"The strongest point is {best_agent_finding(docket)}, while the biggest open issue is {worst_agent_finding(docket)}. "
            f"Top risks: {top_risk_text}. Missing data: {missing_text}. "
            f"What RiskWise used: {used_text}. Final verdict: cautious until the missing data and weakest link are confirmed."
        )
    else:
        response["answer"] = clean_answer(
            "Deep analysis needs a selected check, uploaded contract, or ticker/strike/expiration/premium context. "
            "I can still map what is missing, but I should not pretend there is a complete trade yet."
        )


def committee_docket(current_report: dict[str, Any] | None, tool_context: dict[str, Any]) -> list[dict[str, Any]]:
    report = current_report or {}
    risk_math = report.get("riskMath") or report.get("risk_math") or {}
    missing = tool_context.get("missing_data", [])
    normalized = {
        (item.get("name"), item.get("result", {}).get("status"))
        for item in (tool_context.get("tool_results") or [])
    }
    has_contract_context = any(name == "get_option_contract" for name, _ in normalized)
    has_chain_context = any(name == "get_option_chain" for name, _ in normalized)
    setup = int(report.get("setupScore") or report.get("setup_score") or 62)
    risk_pct = number_from_any(risk_math.get("account_risk_pct") or risk_math.get("risk_percent"))
    max_loss = risk_math.get("max_loss") or report.get("amountAtRisk") or report.get("amount_at_risk")
    required_move = risk_math.get("required_move_to_breakeven_pct")
    dte = risk_math.get("calendar_days_left") or risk_math.get("trading_days_left")
    weakest = str(report.get("weakestLink") or report.get("weakest_link") or "").lower()
    return [
        agent_row(
            "Structure Agent",
            clamp_score(setup + (8 if has_contract_context else 0) + (4 if required_move is not None else -10)),
            "supportive" if setup >= 75 else "cautious",
            f"Breakeven move is {required_move}% and DTE is {dte or 'unknown'}." if required_move is not None else "Breakeven move is not fully known.",
            "Strike, expiration, and payoff shape are available." if report else "No selected contract structure yet.",
            "Required move, premium, or exact moneyness is missing." if required_move is None else "Directional thesis still needs confirmation.",
            missing,
            "What exact condition invalidates the setup?",
        ),
        agent_row(
            "Volatility Agent",
            48 if any("iv" in str(item).lower() or "volatility" in str(item).lower() for item in missing) else 72,
            "weak" if any("iv" in str(item).lower() or "volatility" in str(item).lower() for item in missing) else "cautious",
            "IV, event timing, and volatility crush decide whether the premium is inflated.",
            "Event context is checked when provider data exists; no volatility claim is made without IV.",
            "Provider-reported IV or event premium is missing.",
            missing,
            "Is this before earnings or another volatility event?",
        ),
        agent_row(
            "Liquidity Agent",
            46 if any(term in " ".join(map(str, missing)).lower() for term in ["bid", "ask", "volume", "open interest"]) else 74,
            "weak" if missing else "cautious",
            "Fill quality depends on bid/ask width and participation.",
            "Contract reference data can be attached when available." if has_chain_context else "No option-chain depth is confirmed yet.",
            "Bid/ask, volume, or open interest is missing.",
            missing,
            "What is the bid, ask, volume, and open interest?",
        ),
        agent_row(
            "Sizing Agent",
            82 if risk_pct is not None and risk_pct <= 2 else 58 if risk_pct is None else 45,
            "supportive" if risk_pct is not None and risk_pct <= 2 else "cautious",
            f"Max loss is {dollars(max_loss)}." if max_loss is not None else "Max loss needs premium and contract count.",
            "Risk is inside the common 1-2% guardrail." if risk_pct is not None and risk_pct <= 2 else "Sizing needs a stricter guardrail.",
            "Account-risk percent is high or unknown.",
            missing,
            "What maximum account percent are you willing to lose?",
        ),
        agent_row(
            "Skeptic Agent",
            50 if missing or weakest else 70,
            "cautious" if not weakest else "weak",
            f"The named weak point is {weakest}." if weakest else "The thesis should survive missing-data checks before confidence rises.",
            "RiskWise can name the exact fields needed instead of guessing.",
            "Missing data can make a decent-looking setup misleading.",
            missing,
            "What evidence would prove this trade thesis wrong?",
        ),
    ]


def agent_row(agent: str, score: int, stance: str, finding: str, strongest: str, weakest: str, missing: list[str], question: str) -> dict[str, Any]:
    return {
        "agent": agent,
        "score": score,
        "stance": stance,
        "finding": finding,
        "strongest_evidence": strongest,
        "weakest_evidence": weakest,
        "missing_data": missing[:5],
        "next_question": question,
    }


def committee_score(docket: list[dict[str, Any]]) -> int:
    return round(sum(int(item.get("score") or 0) for item in docket) / max(1, len(docket)))


def best_agent_finding(docket: list[dict[str, Any]]) -> str:
    best = max(docket, key=lambda item: int(item.get("score") or 0))
    return str(best.get("strongest_evidence") or best.get("finding") or "the defined risk math")


def worst_agent_finding(docket: list[dict[str, Any]]) -> str:
    worst = min(docket, key=lambda item: int(item.get("score") or 0))
    return str(worst.get("weakest_evidence") or worst.get("finding") or "the missing contract data")


def best_next_question(docket: list[dict[str, Any]]) -> str:
    worst = min(docket, key=lambda item: int(item.get("score") or 0))
    return str(worst.get("next_question") or "What data would change this read?")


def clamp_score(value: int | float) -> int:
    return max(0, min(100, round(value)))


def number_from_any(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def report_review_response(message: str, current_report: dict[str, Any], attachments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lower = message.lower()
    title = report_title(current_report)
    risk_math = current_report.get("riskMath") or current_report.get("risk_math") or {}
    debate = current_report.get("setupDebate") or current_report.get("setup_debate") or {}
    weakest = current_report.get("weakestLink") or current_report.get("weakest_link") or "position sizing"
    posture = current_report.get("riskPosture") or current_report.get("risk_posture") or "mixed"
    setup_score = int(current_report.get("setupScore") or current_report.get("setup_score") or 60)
    required_move = risk_math.get("required_move_to_breakeven_pct")
    dte = risk_math.get("calendar_days_left") or risk_math.get("trading_days_left") or risk_math.get("days_to_expiration")
    account_risk_pct = risk_math.get("account_risk_pct") or risk_math.get("risk_percent_of_account")
    amount_at_risk = (
        risk_math.get("max_loss")
        or current_report.get("amountAtRisk")
        or current_report.get("amount_at_risk")
        or current_report.get("amountRisk")
        or current_report.get("amount_risk")
    )
    max_loss = dollars(amount_at_risk)
    attachment_note = " I also see an attachment, so I would cross-check the visible contract details against the report." if attachments else ""
    missing_fields = report_missing_contract_fields(current_report)
    if has_any_term(lower, ["missing data", "what data", "need before", "before trusting", "missing"]):
        visible_missing = ", ".join(missing_fields[:6]) or "no obvious report fields"
        answer = (
            f"For {title}, the missing pieces before trusting the read are {visible_missing}. "
            "Those fields matter because they decide whether the premium, fill quality, volatility risk, and participation are real or just assumed. "
            f"RiskWise can still use the selected check, max loss {max_loss}, and weakest link {weakest}, but it should not pretend the live contract snapshot is complete."
        )
    elif has_any_term(lower, ["weakest", "weak link", "weak point", str(weakest).lower()]):
        answer = (
            f"The weakest link is {weakest}. In plain English: the trade can be directionally right and still disappoint if the stock does not move enough, fast enough, to beat what you paid. "
            f"For {title}, the report shows max loss {max_loss}"
            f"{f', required move {required_move}%' if required_move is not None else ''}"
            f"{f', and {dte} days left' if dte is not None else ''}. "
            "That is the pressure point to understand before trusting the setup."
        )
    elif has_any_term(lower, ["debate", "bull", "bear", "argue", "case for", "case against"]):
        answer = (
            f"For {title}, the bull case is {debate.get('bull_case') or 'the directional thesis can work if price, time, and premium line up'}. "
            f"The bear case is {debate.get('bear_case') or 'time decay, IV change, and missing contract data can overwhelm the idea'}. "
            f"The risk judge view: {debate.get('risk_judge') or 'risk budget and missing data should control confidence'}. "
            f"The weak link is {weakest}, with max loss {max_loss}"
            f"{f' and {dte} days left' if dte is not None else ''}."
        )
    elif has_any_term(lower, ["position size", "position sizing", "size", "sizing", "too big", "account risk"]):
        answer = (
            f"For {title}, position size starts with max loss {max_loss}"
            f"{f', which is {float(account_risk_pct):g}% of the account' if account_risk_pct is not None else ''}. "
            f"The weak point is {weakest}. If that max loss is above the profile risk budget, the trade is too large before the upside story matters. "
            "The next check is whether the premium can go to zero without damaging the account plan."
        )
    elif has_any_term(lower, ["what has to go right", "has to go right", "needs to happen", "need to happen", "work"]):
        answer = (
            f"For {title} to work, the stock has to move enough and soon enough to beat the premium paid"
            f"{f', roughly a {required_move}% move to breakeven' if required_move is not None else ''}"
            f"{f' within {dte} days' if dte is not None else ''}. "
            f"The weak link is {weakest}, and missing live contract data such as bid/ask, IV, Greeks, volume, or open interest can still change the read."
        )
    elif has_any_term(lower, ["why", "risky", "risk", "what can go wrong", "what can break", "break this", "breaks this", "invalidate", "fail", "danger"]):
        answer = (
            f"For {title}, this is risky mainly because the weak point is {weakest}. The selected check shows max loss {max_loss}"
            f"{f', a {required_move}% required move to breakeven' if required_move is not None else ''}"
            f"{f', {dte} days left' if dte is not None else ''}"
            f"{f', and {float(account_risk_pct):g}% account risk' if account_risk_pct is not None else ''}. "
            "That means direction alone is not enough; timing, premium paid, and missing liquidity/IV data can all break the setup."
        )
    else:
        answer = (
            f"{title} looks like a {posture.lower()} risk review. The weak point is {weakest}, and the max loss shown is {max_loss}. "
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
                ["Missing data", ", ".join(missing_fields[:4]) or "None flagged"],
            ],
        },
    ]
    return answer, cards, blocks


def report_missing_contract_fields(report: dict[str, Any]) -> list[str]:
    snapshot = report.get("contractSnapshot") or report.get("contract_snapshot") or {}
    data_quality = report.get("dataQuality") or report.get("data_quality") or {}
    pending = [str(item).replace("_", " ") for item in data_quality.get("fields_pending") or []]
    checks = [
        ("live premium", snapshot.get("lastPrice") or snapshot.get("mark") or report.get("premium")),
        ("bid/ask", (snapshot.get("bid"), snapshot.get("ask"))),
        ("implied volatility", snapshot.get("impliedVolatility") or snapshot.get("iv") or report.get("impliedVolatility")),
        ("Greeks", snapshot.get("delta") or snapshot.get("theta") or snapshot.get("gamma") or snapshot.get("vega")),
        ("volume", snapshot.get("volume") or snapshot.get("contractVolume") or report.get("contractVolume")),
        ("open interest", snapshot.get("openInterest") or report.get("openInterest")),
        ("earnings date", report.get("earningsDate") or report.get("earnings_date")),
    ]
    missing = list(pending)
    for label, value in checks:
        is_missing = value in (None, "", [], {})
        if isinstance(value, tuple):
            is_missing = any(part in (None, "") for part in value)
        if is_missing and label not in missing:
            missing.append(label)
    return missing


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


def attachment_needs_details_response(message: str, attachments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    extracted = extract_attachment_contract(attachments)
    if extracted.get("ticker") and (extracted.get("strike") or extracted.get("premium") or extracted.get("expiration")):
        lower = message.lower()
        fields = [
            ["Ticker", str(extracted.get("ticker") or "Unknown")],
            ["Side", str(extracted.get("side") or "Call/put not clear")],
            ["Strike", dollars(extracted.get("strike")) if extracted.get("strike") is not None else "Missing"],
            ["Expiration", str(extracted.get("expiration") or "Missing")],
            ["Premium", exact_dollars(extracted.get("premium")) if extracted.get("premium") is not None else "Missing"],
        ]
        missing = [label for label, value in fields if value == "Missing" or "not clear" in value.lower()]
        live_missing = ["bid/ask", "current option price", "implied volatility", "Greeks", "volume", "open interest", "earnings date"]
        readable = (
            f"{extracted.get('ticker')} {extracted.get('side') or 'option'}"
            f"{' at ' + dollars(extracted.get('strike')) if extracted.get('strike') is not None else ''}"
        )
        if has_any_term(lower, ["missing data", "what data", "missing", "need before", "before trusting"]):
            answer = (
                f"From the upload I can read enough to identify {readable}. "
                f"The missing pieces are {', '.join([*missing, *live_missing][:8]).lower()}. "
                "Those are exactly the fields RiskWise should not invent, because they control fill quality, IV crush risk, liquidity, and whether the current option price is real."
            )
        else:
            answer = (
                f"I can read enough from the upload to start: {readable}. "
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


def saved_trade_lookup_response(message: str, recent_checks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lower = message.lower()
    latest = (recent_checks[0].get("report") if recent_checks and "report" in recent_checks[0] else recent_checks[0]) if recent_checks else {}
    insight = saved_checks_insight(recent_checks)
    title = report_title(latest)
    posture = latest.get("riskPosture") or latest.get("risk_posture") or "mixed"
    setup_score = latest.get("setupScore") or latest.get("setup_score") or "--"
    weakest = latest.get("weakestLink") or latest.get("weakest_link") or "not labeled yet"
    risk_math = latest.get("riskMath") or latest.get("risk_math") or {}
    max_loss = dollars(risk_math.get("max_loss") or latest.get("amountAtRisk") or latest.get("amount_at_risk"))
    required_move = risk_math.get("required_move_to_breakeven_pct")
    dte = risk_math.get("calendar_days_left") or risk_math.get("trading_days_left") or risk_math.get("days_to_expiration")
    missing_fields = report_missing_contract_fields(latest)
    if has_any_term(lower, ["pattern", "repeat", "repeated", "mistake", "usually", "history", "past"]):
        answer = (
            f"From the saved checks I can see, the repeated weak point is {insight['repeated_weakest']}. "
            f"The riskiest saved check is {insight['riskiest_title']} with max loss {dollars(insight['riskiest_loss'])}. "
            f"The last ticker analyzed was {insight['last_ticker']}. Treat this as product memory, not a trading signal."
        )
    elif has_any_term(lower, ["missing data", "what data", "missing", "need before", "before trusting"]):
        answer = (
            f"For your latest saved check, {title}, the missing pieces are {', '.join(missing_fields[:6]) or 'not clearly flagged'}. "
            f"RiskWise can still use the saved max loss {max_loss} and weakest link {weakest}, but those missing fields limit confidence."
        )
    elif has_any_term(lower, ["why", "risky", "risk", "what can go wrong", "what can break", "break this", "breaks this", "invalidate", "fail", "weakest"]):
        answer = (
            f"Your latest saved check, {title}, was risky mainly because the weak point is {weakest}. "
            f"The saved report shows max loss {max_loss}"
            f"{f', required move {required_move}%' if required_move is not None else ''}"
            f"{f', and {dte} days left' if dte is not None else ''}. "
            "That means the setup needs direction, timing, and contract quality to line up."
        )
    else:
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
            "title": "Saved-check memory",
            "rows": [
                ["Latest", title],
                ["Riskiest", insight["riskiest_title"]],
                ["Repeated weak point", insight["repeated_weakest"]],
                ["Last ticker", insight["last_ticker"]],
                ["Missing data", ", ".join(missing_fields[:4]) or "None flagged"],
            ],
        }
    ]
    return answer, cards, blocks


def saved_checks_insight(recent_checks: list[dict[str, Any]]) -> dict[str, Any]:
    reports = []
    for item in recent_checks:
        report = item.get("report") if isinstance(item, dict) else item
        if isinstance(report, dict):
            reports.append(report)
    if not reports:
        return {"riskiest_title": "No saved check", "riskiest_loss": 0, "repeated_weakest": "not enough saved history", "last_ticker": "unknown"}
    weakest_counts: dict[str, int] = {}
    riskiest = reports[0]
    riskiest_loss = -1.0
    for report in reports:
        weakest = str(report.get("weakestLink") or report.get("weakest_link") or "not labeled").lower()
        weakest_counts[weakest] = weakest_counts.get(weakest, 0) + 1
        risk_math = report.get("riskMath") or report.get("risk_math") or {}
        loss = number_from_any(risk_math.get("max_loss") or report.get("amountAtRisk") or report.get("amount_at_risk")) or 0
        if loss > riskiest_loss:
            riskiest = report
            riskiest_loss = loss
    repeated = max(weakest_counts.items(), key=lambda item: item[1])[0]
    return {
        "riskiest_title": report_title(riskiest),
        "riskiest_loss": riskiest_loss,
        "repeated_weakest": repeated,
        "last_ticker": str(reports[0].get("ticker") or "unknown").upper(),
    }


def risk_math_response(message: str, user_profile: dict[str, Any] | None, attachments: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lower = message.lower()
    account_size = float((user_profile or {}).get("accountSize") or 25000)
    risk_pct = profile_risk_limit_percent(user_profile) or 2
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
    if is_direct_trade_request(lower):
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


def is_direct_trade_request(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in [
            "guarantee",
            "safe options trade",
            "exactly which",
            "should i buy",
            "should i sell",
            "should i enter",
            "should i exit",
            "what should i buy",
            "what should i sell",
            "half my account",
            "all in",
        ]
    )


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
        if has_any_term(lower, ["right now", "today", "healthy", "enough", "contract", "call", "put"]) and re.search(r"\b[A-Z]{1,5}\b", message.upper()):
            answer = (
                "Open interest is the number of option contracts that remain open, but I should not invent whether this specific contract is healthy. "
                "For that, RiskWise needs live option-chain or provider data: open interest, today's volume, bid/ask, IV, Greeks, and the exact expiration. "
                "Without those fields, I can explain what open interest means, but not confirm liquidity on that contract."
            )
            rows = [["Known", "Open interest explains open contracts"], ["Missing", "Live option chain/provider data"], ["Do not assume", "Liquidity or fill quality"]]
        else:
            answer = (
                "Open interest is the number of option contracts that remain open. It is not the same as today's volume. Higher open interest can signal a more established contract, but it does not prove direction."
            )
            rows = [["Means", "Open contracts"], ["Different from", "Today's trading volume"], ["Use", "Liquidity context, not direction proof"]]
        title = "Open interest"
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
    elif "delta" in lower:
        answer = (
            "Delta is the option's stock-move sensitivity. In plain English, it estimates how much the option price may change when the underlying stock moves by $1. "
            "It is also a rough directional exposure clue, but it is not a win probability and it can change quickly near expiration."
        )
        title = "Delta"
        rows = [["Measures", "Option sensitivity to the stock"], ["Moves with", "Underlying price and time"], ["Risk", "Can change quickly near expiration"]]
    elif has_any_term(lower, ["vega", "greek"]):
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


def attachment_contract_context(attachments: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not attachments:
        return None
    extracted = normalize_extracted_contract(extract_attachment_contract(attachments))
    return extraction_payload(
        extracted,
        attachments,
        provider="text-parser" if is_extraction_useful(extracted) else "none",
        confidence=0.72 if is_extraction_useful(extracted) else 0.0,
        message=(
            "RiskWise extracted readable uploaded-contract text. Confirm every field before analysis."
            if is_extraction_useful(extracted)
            else "RiskWise could not read enough contract fields from this upload."
        ),
    )


def extract_attachment_contract(attachments: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(str(item.get("text") or "") for item in attachments)
    upper = text.upper()
    if not upper.strip():
        return {}
    shorthand = parse_contract_shorthand(text)
    if shorthand:
        return shorthand
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
    bid = parse_attachment_number(text, ["bid"])
    ask = parse_attachment_number(text, ["ask"])
    implied_volatility = parse_attachment_number(text, ["implied volatility", "iv"])
    open_interest = parse_attachment_number(text, ["open interest", "oi"])
    contract_volume = parse_attachment_number(text, ["contract volume", "volume"])
    underlying_price = parse_attachment_number(text, ["underlying price", "stock price", "underlying"])
    contracts = parse_attachment_number(text, ["contracts", "quantity", "qty"])
    expiration = None
    exp_match = re.search(r"(?:EXPIRATION|EXP|EXPIRES?)\D{0,12}([A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    if exp_match:
        expiration = exp_match.group(1)
    return {
        "ticker": ticker_match.group(1) if ticker_match else None,
        "side": side,
        "strike": strike,
        "premium": premium,
        "bid": bid,
        "ask": ask,
        "impliedVolatility": implied_volatility,
        "openInterest": open_interest,
        "contractVolume": contract_volume,
        "underlyingPrice": underlying_price,
        "contracts": contracts,
        "expiration": expiration,
    }


def parse_contract_shorthand(text: str) -> dict[str, Any]:
    compact = re.search(r"\b([A-Z]{1,5})(\d{2})(\d{2})(\d{2})([CP])(\d{8})\b", text.upper())
    if compact:
        strike = int(compact.group(6)) / 1000
        return {
            "ticker": compact.group(1),
            "side": "Call" if compact.group(5) == "C" else "Put",
            "strike": strike,
            "premium": parse_shorthand_premium(text),
            "bid": parse_attachment_number(text, ["bid"]),
            "ask": parse_attachment_number(text, ["ask"]),
            "impliedVolatility": parse_attachment_number(text, ["iv", "implied volatility"]),
            "openInterest": parse_attachment_number(text, ["oi", "open interest"]),
            "contractVolume": parse_attachment_number(text, ["vol", "volume"]),
            "underlyingPrice": parse_attachment_number(text, ["underlying", "stock price"]),
            "contracts": parse_attachment_number(text, ["qty", "quantity", "contracts"]) or parse_contract_quantity(text),
            "expiration": normalize_shorthand_expiration(f"20{compact.group(2)}-{compact.group(3)}-{compact.group(4)}"),
        }
    patterns = [
        r"\b([A-Z]{1,5})\s+(\d{1,4}(?:\.\d{1,2})?)\s*([CP])\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b",
        r"\b([A-Z]{1,5})\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s+(\d{1,4}(?:\.\d{1,2})?)\s*(CALL|PUT|[CP])\b",
        r"\b([A-Z]{1,5})\s+(\d{1,4}(?:\.\d{1,2})?)\s+(CALL|PUT)\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text.upper())
        if not match:
            continue
        groups = match.groups()
        ticker = groups[0]
        if "/" in groups[1] or "-" in groups[1]:
            expiration = groups[1]
            strike = groups[2]
            side_raw = groups[3]
        else:
            strike = groups[1]
            side_raw = groups[2]
            expiration = groups[3]
        return {
            "ticker": ticker,
            "side": "Call" if side_raw.startswith("C") else "Put",
            "strike": attachment_number_from_value(strike),
            "premium": parse_shorthand_premium(text),
            "bid": parse_attachment_number(text, ["bid"]),
            "ask": parse_attachment_number(text, ["ask"]),
            "impliedVolatility": parse_attachment_number(text, ["iv", "implied volatility"]),
            "openInterest": parse_attachment_number(text, ["oi", "open interest"]),
            "contractVolume": parse_attachment_number(text, ["vol", "volume"]),
            "underlyingPrice": parse_attachment_number(text, ["underlying", "stock price"]),
            "contracts": parse_attachment_number(text, ["qty", "quantity", "contracts"]) or parse_contract_quantity(text),
            "expiration": normalize_shorthand_expiration(expiration),
        }
    return {}


def parse_shorthand_premium(text: str) -> float | None:
    match = re.search(r"(?:@|MARK|MID|DEBIT|PREM(?:IUM)?)\s*\$?\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    return attachment_number_from_value(match.group(1)) if match else None


def parse_contract_quantity(text: str) -> float | None:
    match = re.search(r"\b([1-9]\d?)\s*x\b|\bx\s*([1-9]\d?)\b", text, re.IGNORECASE)
    if not match:
        return None
    return attachment_number_from_value(match.group(1) or match.group(2))


def normalize_shorthand_expiration(value: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
        return text
    match = re.match(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?$", text)
    if not match:
        return text
    month = int(match.group(1))
    day = int(match.group(2))
    raw_year = match.group(3)
    year = int(raw_year) if raw_year else date.today().year
    if year < 100:
        year += 2000
    if not raw_year and date(year, month, day) < date.today():
        year += 1
    return f"{year:04d}-{month:02d}-{day:02d}"


async def extract_contract_from_uploads(attachments: list[dict[str, Any]]) -> dict[str, Any]:
    clean = sanitize_attachments(attachments)
    text_extracted = normalize_extracted_contract(extract_attachment_contract(clean))
    if is_extraction_useful(text_extracted):
        return extraction_payload(
            text_extracted,
            clean,
            provider="text-parser",
            confidence=0.72,
            message="RiskWise extracted readable contract text. Confirm every field before analysis.",
        )

    has_image = any(item.get("dataUrl") and str(item.get("type") or "").startswith("image/") for item in clean)
    if has_image:
        prompt = (
            "Read this options contract screenshot. Return JSON only with these keys: "
            "ticker, side, strike, expiration, premium, bid, ask, impliedVolatility, openInterest, contractVolume, underlyingPrice, contracts. "
            "Use null for fields you cannot clearly read. Do not infer or guess missing fields."
        )
        try:
            result = await generate_answer(
                system_prompt=(
                    "You extract visible options contract fields from screenshots. "
                    "Return strict JSON only. Do not guess. Do not add commentary."
                ),
                prompt=prompt,
                attachments=clean,
            )
        except Exception:
            result = None
        if result and result.text:
            vision_extracted = normalize_extracted_contract(parse_extraction_json(result.text))
            if is_extraction_useful(vision_extracted):
                return extraction_payload(
                    vision_extracted,
                    clean,
                    provider=result.provider,
                    model=result.model,
                    confidence=0.82,
                    message="RiskWise read visible screenshot fields. Confirm them before analysis.",
                )

    return extraction_payload(
        {},
        clean,
        provider="none",
        confidence=0.0,
        message=(
            "RiskWise could not read enough contract fields from this upload. "
            "Enter ticker, call/put, strike, expiration, premium, and contract count manually."
        ),
    )


def parse_extraction_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def normalize_extracted_contract(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return {}
    side = data.get("side") or data.get("optionSide") or data.get("option_side")
    normalized_side = str(side).strip().lower() if side else ""
    if "call" in normalized_side:
        option_side = "call"
        trade_type = "Call Option (Long)"
    elif "put" in normalized_side:
        option_side = "put"
        trade_type = "Put Option (Long)"
    else:
        option_side = ""
        trade_type = ""
    return {
        "ticker": clean_extracted_ticker(data.get("ticker") or data.get("symbol") or data.get("underlying")),
        "optionSide": option_side or None,
        "tradeType": trade_type or None,
        "strike": normalize_optional_number(data.get("strike") or data.get("strikePrice")),
        "expiration": str(data.get("expiration") or data.get("expirationDate") or "").strip() or None,
        "premium": normalize_optional_number(data.get("premium") or data.get("mid") or data.get("debit") or data.get("cost")),
        "bid": normalize_optional_number(data.get("bid")),
        "ask": normalize_optional_number(data.get("ask")),
        "impliedVolatility": normalize_optional_number(data.get("impliedVolatility") or data.get("iv")),
        "openInterest": normalize_optional_number(data.get("openInterest") or data.get("oi")),
        "contractVolume": normalize_optional_number(data.get("contractVolume") or data.get("volume")),
        "underlyingPrice": normalize_optional_number(data.get("underlyingPrice") or data.get("stockPrice")),
        "contracts": normalize_optional_number(data.get("contracts") or data.get("quantity")),
    }


def clean_extracted_ticker(value: Any) -> str | None:
    ticker = re.sub(r"[^A-Za-z.]", "", str(value or "")).upper()
    if not ticker or ticker in {"CALL", "PUT", "EXP", "IV", "MID"}:
        return None
    return ticker[:8]


def normalize_optional_number(value: Any) -> str | None:
    number = attachment_number_from_value(value)
    if number is None:
        return None
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def is_extraction_useful(extracted: dict[str, Any]) -> bool:
    return bool(extracted.get("ticker") and (extracted.get("strike") or extracted.get("premium") or extracted.get("expiration")))


def extraction_payload(
    extracted: dict[str, Any],
    attachments: list[dict[str, Any]],
    *,
    provider: str,
    confidence: float,
    message: str,
    model: str | None = None,
) -> dict[str, Any]:
    required = ["ticker", "optionSide", "strike", "expiration", "premium", "contracts"]
    missing = [field for field in required if not extracted.get(field)]
    live_fields = ["bid", "ask", "impliedVolatility", "openInterest", "contractVolume"]
    missing_live = [field for field in live_fields if not extracted.get(field)]
    if not any(extracted.get(field) for field in ["delta", "theta", "gamma", "vega", "Greeks"]):
        missing_live.append("Greeks")
    return {
        "status": "ok" if is_extraction_useful(extracted) else "needs_manual_review",
        "fields": {key: value for key, value in extracted.items() if value not in (None, "")},
        "missing_fields": missing,
        "missing_live_fields": missing_live,
        "confidence": confidence,
        "provider": provider,
        "model": model or "",
        "message": message,
        "attachments": attachment_context_rows(attachments),
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
        "simplify",
        "followup",
        "strategy_explainer",
        "risk_math",
    }:
        return True
    if mode == "trade_review" and current_report:
        return True
    if mode == "concept" and is_high_confidence_core_concept(lower):
        return True
    return False


def is_high_confidence_core_concept(lower: str) -> bool:
    market_data_phrases = [
        "today",
        "right now",
        "current",
        "live",
        "this week",
        "for aapl",
        "for nvda",
        "for msft",
        "for tsla",
        "for spy",
        "for qqq",
    ]
    if any(phrase in lower for phrase in market_data_phrases):
        return False
    core_topics = [
        "iv crush",
        "implied volatility",
        "theta decay",
        "theta",
        "delta",
        "gamma",
        "vega",
        "rho",
        "bid ask",
        "bid-ask",
        "open interest",
        "option volume",
        "liquidity",
        "intrinsic",
        "extrinsic",
        "assignment",
        "pin risk",
        "volatility skew",
        "term structure",
    ]
    return any(topic in lower for topic in core_topics)


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
    if stripped.startswith("{") or stripped.startswith("[") or '"answer"' in stripped[:80]:
        return True
    if "```" in stripped:
        return True
    words = stripped.split()
    if mode not in {"greeting", "smalltalk"} and len(words) < 16:
        return True
    if mode not in {"greeting", "smalltalk"} and stripped[-1] not in ".!?":
        return True
    if stripped.lower() in {"i don't know.", "i am not sure.", "i can't help with that."}:
        return True
    return False


def should_accept_llm_answer(
    answer: str,
    fallback_response: dict[str, Any],
    mode: str,
    message: str,
    tool_context: dict[str, Any],
) -> bool:
    return not llm_answer_rejection_reasons(answer, fallback_response, mode, message, tool_context)


def llm_answer_rejection_reasons(
    answer: str,
    fallback_response: dict[str, Any],
    mode: str,
    message: str,
    tool_context: dict[str, Any],
) -> list[str]:
    reasons = []
    if is_low_quality_llm_answer(answer, mode):
        reasons.append("low_quality_answer")
    normalized = normalize_answer_text(answer)
    if has_textbook_voice(normalized):
        reasons.append("textbook_voice")
    if ignores_selected_trade(normalized, fallback_response, mode):
        reasons.append("ignored_selected_trade")
    if ignores_profile_style(normalized, tool_context, mode):
        reasons.append("ignored_profile_style")
    if misses_core_concept(normalized, message, mode):
        reasons.append("missed_core_concept")
    if gives_direct_trading_instruction(normalized):
        reasons.append("direct_trading_instruction")
    if has_bad_options_math(normalized):
        reasons.append("bad_options_math")
    if fabricates_missing_live_data(normalized, fallback_response):
        reasons.append("fabricated_live_data")
    return reasons


def normalize_answer_text(answer: str) -> str:
    return re.sub(r"\s+", " ", answer.lower()).strip()


def has_textbook_voice(normalized: str) -> bool:
    textbook_phrases = [
        "is a phenomenon",
        "in the context of options",
        "it is important to understand",
        "there are several factors to consider",
        "the option contract suddenly and significantly decreases",
        "as an options trader",
        "as a trader, you should",
        "in conclusion",
    ]
    if any(phrase in normalized for phrase in textbook_phrases):
        return True
    if normalized.startswith(("an option is a contract", "options are financial derivatives")):
        return True
    return False


def ignores_selected_trade(normalized: str, fallback_response: dict[str, Any], mode: str) -> bool:
    if mode not in {"trade_review", "trade_identity", "saved_trade_lookup"}:
        return False
    context = fallback_response.get("normalized_context") or {}
    selected = context.get("selected_contract") or {}
    ticker = str(context.get("ticker") or selected.get("ticker") or "").lower()
    strike = str(selected.get("strike") or "")
    if ticker and ticker not in normalized:
        return True
    if strike and strike not in normalized and mode != "saved_trade_lookup":
        return True
    if "do not see a trade" in normalized or "need the trade details" in normalized:
        return True
    return False


def ignores_profile_style(normalized: str, tool_context: dict[str, Any], mode: str) -> bool:
    if mode in {"greeting", "smalltalk"}:
        return False
    profile = profile_memory_from_tool_context(tool_context)
    if not profile:
        return False
    style = str(profile.get("preferred_explanation") or "").lower()
    strictness = str(profile.get("risk_strictness") or "").lower()
    if "quant" in style:
        metric_terms = ["max loss", "breakeven", "dte", "%", "iv", "delta", "theta", "premium"]
        if not any(term in normalized for term in metric_terms):
            return True
    if "strict" in strictness:
        strict_terms = ["max loss", "risk", "missing", "invalid", "breakeven", "size"]
        if not any(term in normalized for term in strict_terms):
            return True
    return False


def profile_memory_from_tool_context(tool_context: dict[str, Any]) -> dict[str, Any]:
    for item in tool_context.get("tool_results") or []:
        if item.get("name") == "retrieve_profile_memory":
            result = item.get("result") or {}
            return result if result.get("status") == "ok" else {}
    return {}


def misses_core_concept(normalized: str, message: str, mode: str) -> bool:
    lower = message.lower()
    if mode != "concept":
        return False
    if has_any_term(lower, ["iv", "implied", "crush"]) and not all(
        term in normalized for term in ["premium", "uncertainty"]
    ):
        return True
    if "theta" in lower and "time" not in normalized and "decay" not in normalized:
        return True
    if "delta" in lower and "stock" not in normalized and "underlying" not in normalized:
        return True
    if "liquidity" in lower and not any(term in normalized for term in ["bid", "ask", "volume", "open interest"]):
        return True
    return False


def has_bad_options_math(normalized: str) -> bool:
    bad_phrases = [
        "breakeven at the higher strike plus premium",
        "breakeven is the higher strike plus premium",
        "debit spread breakeven at the higher strike",
        "max loss is unlimited",
        "long call max loss is unlimited",
        "theta helps long calls",
    ]
    return any(phrase in normalized for phrase in bad_phrases)


def gives_direct_trading_instruction(normalized: str) -> bool:
    bad_phrases = [
        "you should buy",
        "you should sell",
        "i recommend buying",
        "i recommend selling",
        "definitely buy",
        "definitely sell",
        "enter the trade",
        "exit the trade",
        "take the trade",
        "good entry",
        "hold it until",
    ]
    return any(phrase in normalized for phrase in bad_phrases)


def fabricates_missing_live_data(normalized: str, fallback_response: dict[str, Any]) -> bool:
    missing = " ".join(str(item).lower() for item in fallback_response.get("missing_data") or [])
    if not missing:
        return False
    suspicious_claims = [
        "currently has an iv",
        "iv is currently",
        "iv currently",
        "iv is around",
        "iv is near",
        "iv is about",
        "implied volatility is",
        "implied volatility currently",
        "bid is",
        "ask is",
        "bid sits",
        "ask sits",
        "bid/ask is",
        "mid price is",
        "last trade was",
        "mark price is",
        "open interest is",
        "open interest of",
        "volume is",
        "volume of",
        "oi is",
        "delta is",
        "gamma is",
        "theta is",
        "vega is",
        "delta around",
        "theta near",
        "earnings are on",
        "earnings is on",
        "earnings date is",
        "reports earnings on",
        "reports earnings tomorrow",
        "earnings are this week",
        "earnings are tomorrow",
        "is trading at $",
        "trading at $",
        "currently trading at",
        "right now at $",
        "current price is",
        "option chain shows",
        "premium is $",
        "contract is cheap",
        "contract is expensive",
        "iv looks high",
        "iv looks low",
        "liquidity is strong",
        "liquidity looks strong",
        "bid/ask spread is tight",
        "open interest looks healthy",
        "earnings are next week",
        "greeks look favorable",
        "greeks are favorable",
        "chain is liquid",
        "nearest expiration is",
        "chain has plenty",
        "option chain looks liquid",
        "chain looks liquid",
        "execution should not be an issue",
        "fills should be fine",
        "enough volume",
        "good participation",
        "clean pricing",
        "spread is tight",
        "bid ask is tight",
        "bid-ask is tight",
        "spread is only",
        "option is pricing in",
        "market is pricing",
        "market expects",
        "expected move is",
        "iv percentile is",
        "iv rank is",
        "skew is steep",
        "term structure is inverted",
    ]
    if any(claim in normalized for claim in suspicious_claims):
        return True
    if re.search(r"\b(?:iv|implied volatility)\s+(?:is|sits|stands|runs)?\s*(?:at|around|near|about|currently)?\s*\d+(?:\.\d+)?\s*%", normalized):
        return True
    if re.search(r"\b(?:delta|gamma|theta|vega|rho)\s+(?:is|=|of|at|around|near|about)?\s*-?\d+(?:\.\d+)?", normalized):
        return True
    if re.search(r"\bhas\s+(?:a|an)\s+-?\d+(?:\.\d+)?\s+(?:delta|gamma|theta|vega|rho)\b", normalized):
        return True
    if re.search(r"\bhas\s+(?:a|an)?\s*(?:delta|gamma|theta|vega|rho)\s+(?:of|at|around|near|about)\s+-?\d+(?:\.\d+)?", normalized):
        return True
    if re.search(r"\b(?:bid|ask|mid price|mark price|last price|last trade)\s+(?:is|=|at|sits at|stands at|around|near|about|of|was)\s+\$?\d+(?:\.\d+)?", normalized):
        return True
    if re.search(r"\b(?:premium|mark|mid|last)\s+(?:is|=|at|around|near|about|of)\s+\$?\d+(?:\.\d+)?", normalized):
        return True
    if re.search(r"\b(?:current price|stock price|underlying price)\s+(?:is|=|at)\s+\$?\d+(?:\.\d+)?", normalized):
        return True
    if re.search(r"\b(?:open interest|volume|oi)\s+(?:is|=|at|around|near|about|of)\s+[\d,]+", normalized):
        return True
    if re.search(r"\b[\d,]+\s+(?:open interest|volume|oi|contracts)\b", normalized):
        return True
    if re.search(r"\b(?:earnings|earnings date|reports earnings)\s+(?:is|are|on|for)\s+[a-z]+\s+\d{1,2}", normalized):
        return True
    if re.search(r"\b(?:earnings|earnings date|reports earnings|reports)\b.*\b(?:today|tomorrow|this week|next week|monday|tuesday|wednesday|thursday|friday)\b", normalized):
        return True
    return False


def apply_profile_voice(response: dict[str, Any], tool_context: dict[str, Any]) -> None:
    profile = profile_memory_from_tool_context(tool_context)
    if not profile or response.get("mode") in {"greeting", "smalltalk"}:
        return
    answer = str(response.get("answer") or "").strip()
    if not answer:
        return
    style = str(profile.get("preferred_explanation") or "").lower()
    question_style = str(profile.get("question_style") or "").lower()
    strictness = str(profile.get("risk_strictness") or "").lower()
    common_mistakes = profile.get("common_mistakes") or []
    risk_rules = profile.get("risk_rules") or {}
    additions = []
    answer_lower = answer.lower()
    risk_limit = number_from_any(risk_rules.get("max_risk_per_trade_percent"))
    if "simple" in style and "plain version" not in answer_lower:
        additions.append("Plain version: focus on what you paid, what can vanish, and what data is still missing.")
    if "strict" in strictness and "risk" not in answer_lower:
        additions.append("RiskWise would keep the read anchored to max loss, breakeven, and what data is still missing.")
    if "quant" in style and not any(term in answer_lower for term in ["max loss", "breakeven", "dte", "%"]):
        additions.append("The sharper version is to tie the idea back to premium paid, breakeven move, DTE, and account-risk percent.")
    if risk_limit is not None and f"{risk_limit:g}%" not in answer:
        account = profile_account_size_from_tool_context(tool_context)
        budget = f", about {dollars(account * risk_limit / 100)} on this profile" if account else ""
        additions.append(f"Your saved risk limit is {risk_limit:g}% per trade{budget}.")
    if risk_rules.get("warn_under_7_dte"):
        dte = profile_dte_from_tool_context(tool_context)
        if dte is not None and dte < 7 and "under 7 dte" not in answer_lower:
            additions.append(f"Your profile says to warn under 7 DTE; this check has {dte:g} days left.")
    if risk_rules.get("avoid_earnings_trades") and "earnings" in answer_lower and "avoid earnings trades" not in answer_lower:
        additions.append("Your profile says to avoid earnings trades, so event premium and IV crush deserve extra caution.")
    if common_mistakes and response.get("mode") in {"trade_review", "risk_math", "strategy_explainer"}:
        first = str(common_mistakes[0]).strip()
        if first and first.lower() not in answer_lower:
            additions.append(f"Given your saved pattern, watch for {first.lower()} before trusting the setup.")
    if "ask" in question_style and "first" in question_style and "?" not in answer:
        additions.append("One question first: what would prove this setup wrong?")
    if additions:
        response["answer"] = clean_answer(f"{answer} {' '.join(additions)}")


def profile_risk_limit_percent(user_profile: dict[str, Any] | None) -> float | None:
    profile = user_profile or {}
    risk_rules = profile.get("riskRules") or {}
    return number_from_any(
        risk_rules.get("maxRiskPerTradePercent")
        or risk_rules.get("maxRiskPercent")
        or profile.get("riskBudgetPercent")
    )


def profile_account_size_from_tool_context(tool_context: dict[str, Any]) -> float | None:
    for item in tool_context.get("tool_results") or []:
        if item.get("name") == "calculate_max_loss":
            value = (item.get("result") or {}).get("account_size")
            parsed = number_from_any(value)
            if parsed is not None:
                return parsed
    return None


def profile_dte_from_tool_context(tool_context: dict[str, Any]) -> float | None:
    for item in tool_context.get("tool_results") or []:
        if item.get("name") == "calculate_dte":
            result = item.get("result") or {}
            for key in ("calendar_days_left", "trading_days_left"):
                parsed = number_from_any(result.get(key))
                if parsed is not None:
                    return parsed
    return None


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
