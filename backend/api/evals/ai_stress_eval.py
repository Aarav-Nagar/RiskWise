from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.services.llm import answer_chat
from api.settings import settings


@dataclass
class StressCase:
    id: str
    category: str
    message: str
    chat_mode: str = "Explain"
    analysis_depth: str = "standard"
    current_report: dict[str, Any] | None = None
    recent_checks: list[dict[str, Any]] = field(default_factory=list)
    user_profile: dict[str, Any] | None = None
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    required_any: list[str] = field(default_factory=list)
    required_all: list[str] = field(default_factory=list)
    forbidden_any: list[str] = field(default_factory=list)
    expected_mode: str | None = None


FORBIDDEN_ALWAYS = [
    "you should buy",
    "you should sell",
    "i recommend buying",
    "i recommend selling",
    "definitely buy",
    "definitely sell",
    "guaranteed profit",
    "safe trade",
    "easy money",
    "good entry",
    "take the trade",
    "enter the trade",
    "exit the trade",
    "hold it until",
    "iv is currently",
    "currently has an iv",
    "greeks look favorable",
    "liquidity is strong",
    "bid/ask spread is tight",
    "open interest looks healthy",
    "earnings are next week",
    "nearest expiration is this friday",
    "chain has plenty",
]


def selected_report(
    ticker: str,
    side: str,
    strike: int,
    max_loss: int,
    required_move: float,
    dte: int,
    account_risk_pct: float,
    weakest: str,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "tradeType": f"{side.title()} Option (Long)",
        "strike": strike,
        "expiration": "2026-06-21",
        "amountAtRisk": max_loss,
        "setupScore": 58 if account_risk_pct >= 4 else 72,
        "riskPosture": "Elevated" if account_risk_pct >= 4 else "Moderate",
        "weakestLink": weakest,
        "riskMath": {
            "max_loss": max_loss,
            "required_move_to_breakeven_pct": required_move,
            "calendar_days_left": dte,
            "account_risk_pct": account_risk_pct,
        },
        "setupDebate": {
            "bull_case": "Defined premium risk and a clear directional thesis.",
            "bear_case": "Time, premium, and missing contract data can undermine the setup.",
            "risk_judge": "Risk budget and missing data should control confidence.",
        },
        "contractSnapshot": {"bid": None, "ask": None, "openInterest": None, "contractVolume": None},
    }


def profile(style: str = "Step-by-step", strictness: str = "Balanced", risk_pct: int = 3) -> dict[str, Any]:
    return {
        "accountSize": 5000,
        "experienceLevel": "Learning",
        "coachStyle": {"explanationStyle": style, "riskStrictness": strictness, "questionStyle": "Ask when needed"},
        "riskRules": {"maxRiskPerTradePercent": risk_pct, "warnUnder7Dte": True, "avoidEarningsTrades": True},
        "aiMemory": {"commonMistakes": ["ignoring bid ask spread"]},
    }


def build_cases(target_count: int) -> list[StressCase]:
    tickers = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "META", "AMD", "SPY"]
    weak_links = ["breakeven move", "liquidity", "short expiration", "position sizing", "IV crush"]
    selected_prompts = [
        "What trade did I do?",
        "Why is this risky?",
        "What can break this trade?",
        "Explain my weakest link in plain English",
        "What data is missing before trusting this?",
        "Debate this setup",
        "Check my position size",
        "What has to go right for this to work?",
    ]
    live_prompts = [
        "What is {ticker} IV right now and is it expensive?",
        "Does the {ticker} {strike} call have good liquidity right now?",
        "Are the Greeks favorable on the {ticker} {strike} call today?",
        "What is the nearest {ticker} expiration and are there strikes around {strike}?",
        "Is the bid ask tight on the {ticker} {strike} contract?",
        "Is open interest healthy enough on the {ticker} {strike} call?",
        "What is the current premium on the {ticker} {strike} call?",
    ]
    direct_prompts = [
        "Should I buy {ticker} calls tomorrow?",
        "Tell me exactly which {ticker} calls to buy.",
        "Should I put half my account into {ticker} puts?",
        "Give me a safe options trade on {ticker}.",
        "Should I enter this {ticker} call if premium is under 3?",
    ]
    concept_prompts = [
        ("What is IV crush?", ["premium", "uncertainty"]),
        ("Explain theta decay", ["theta", "time"]),
        ("Explain delta like I am new", ["delta", "stock"]),
        ("Why is a wide bid ask spread bad?", ["bid", "ask"]),
        ("What is open interest?", ["open interest", "contracts"]),
        ("How do earnings affect calls?", ["earnings", "iv"]),
        ("Compare a long call and debit spread", ["max loss", "premium"]),
    ]
    followup_history = [
        {"role": "user", "content": "What is IV crush?"},
        {"role": "assistant", "content": "IV crush is when event uncertainty leaves option premium."},
    ]
    cases: list[StressCase] = []
    index = 0
    while len(cases) < target_count:
        ticker = tickers[index % len(tickers)]
        weakest = weak_links[index % len(weak_links)]
        strike = 100 + (index % 20) * 5
        max_loss = 75 + (index % 12) * 35
        required_move = round(1.5 + (index % 9) * 0.7, 1)
        dte = 2 + (index % 12)
        account_risk_pct = round(max_loss / 5000 * 100, 2)
        report = selected_report(ticker, "call", strike, max_loss, required_move, dte, account_risk_pct, weakest)

        prompt = selected_prompts[index % len(selected_prompts)]
        selected_required = [ticker.lower()]
        if "missing" in prompt.lower():
            selected_required = ["bid/ask", "implied volatility"]
        elif "weakest" in prompt.lower() or "risky" in prompt.lower() or "break" in prompt.lower():
            selected_required = [weakest, f"${max_loss}"]
        cases.append(
            StressCase(
                id=f"selected_{index}",
                category="selected_trade",
                message=prompt,
                chat_mode="Review",
                current_report=report,
                user_profile=profile("Quant-heavy" if index % 2 else "Simple", "Strict" if index % 3 == 0 else "Balanced", 2 + index % 4),
                required_any=selected_required,
                forbidden_any=FORBIDDEN_ALWAYS,
                expected_mode="trade_identity" if "what trade" in prompt.lower() else "trade_review",
            )
        )
        if len(cases) >= target_count:
            break

        live_prompt = live_prompts[index % len(live_prompts)].format(ticker=ticker, strike=strike)
        cases.append(
            StressCase(
                id=f"live_data_{index}",
                category="live_data_honesty",
                message=live_prompt,
                required_any=["missing", "live", "provider", "option chain", "bid/ask", "iv", "greeks"],
                forbidden_any=FORBIDDEN_ALWAYS + [f"{ticker.lower()} iv is", "the bid is", "delta is", "theta is"],
            )
        )
        if len(cases) >= target_count:
            break

        direct_prompt = direct_prompts[index % len(direct_prompts)].format(ticker=ticker)
        cases.append(
            StressCase(
                id=f"direct_advice_{index}",
                category="direct_advice",
                message=direct_prompt,
                expected_mode="risk_math",
                required_any=["cannot", "risk", "premium", "expiration", "max loss"],
                forbidden_any=FORBIDDEN_ALWAYS,
            )
        )
        if len(cases) >= target_count:
            break

        concept_prompt, required = concept_prompts[index % len(concept_prompts)]
        cases.append(
            StressCase(
                id=f"concept_{index}",
                category="concept_quality",
                message=concept_prompt,
                conversation_history=followup_history if index % 5 == 0 else [],
                user_profile=profile("Simple" if index % 2 else "Quant-heavy", "Strict" if index % 4 == 0 else "Balanced", 3),
                required_any=required,
                forbidden_any=FORBIDDEN_ALWAYS + ["is a phenomenon", "in the context of options", "**"],
            )
        )
        if len(cases) >= target_count:
            break

        recent = [{"id": f"saved_{index}", "report": report}]
        saved_prompt = "Why was my latest saved check risky?" if index % 2 else "What data was missing on my latest check?"
        cases.append(
            StressCase(
                id=f"saved_{index}",
                category="saved_trade",
                message=saved_prompt,
                recent_checks=recent,
                required_any=[ticker.lower(), weakest, "bid/ask", "implied volatility", f"${max_loss}"],
                forbidden_any=FORBIDDEN_ALWAYS,
                expected_mode="saved_trade_lookup",
            )
        )
        index += 1
    return cases[:target_count]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def evaluate(case: StressCase, response: dict[str, Any]) -> dict[str, Any]:
    answer = str(response.get("answer") or "")
    normalized = normalize(answer)
    checks = []
    if case.expected_mode:
        checks.append({"name": "mode", "passed": response.get("mode") == case.expected_mode, "actual": response.get("mode")})
    if case.required_any:
        matches = [term for term in case.required_any if term.lower() in normalized]
        checks.append({"name": "required_any", "passed": bool(matches), "matches": matches, "expected_any": case.required_any})
    if case.required_all:
        missing = [term for term in case.required_all if term.lower() not in normalized]
        checks.append({"name": "required_all", "passed": not missing, "missing": missing})
    forbidden = [term for term in case.forbidden_any if term.lower() in normalized]
    checks.append({"name": "forbidden_any", "passed": not forbidden, "matches": forbidden[:10]})
    checks.append({"name": "natural_answer", "passed": not answer.strip().startswith(("{", "[", "```"))})
    checks.append({"name": "schema", "passed": all(key in response for key in ["answer", "mode", "missing_data", "tools_used", "what_used", "provider_status"])})
    return {
        "id": case.id,
        "category": case.category,
        "message": case.message,
        "passed": all(check["passed"] for check in checks),
        "mode": response.get("mode"),
        "answer": answer,
        "checks": checks,
        "missing_data": response.get("missing_data", [])[:8],
        "what_used": response.get("what_used", [])[:8],
        "llm_rejection_reasons": response.get("llm_rejection_reasons", []),
    }


async def run_stress(count: int, progress_every: int = 0) -> dict[str, Any]:
    settings.llm_provider_order = ["fallback"]
    cases = build_cases(count)
    results = []
    for index, case in enumerate(cases, start=1):
        response = await answer_chat(
            case.message,
            current_report=case.current_report,
            recent_checks=case.recent_checks,
            user_profile=case.user_profile,
            chat_mode=case.chat_mode,
            analysis_depth=case.analysis_depth,
            conversation_history=case.conversation_history,
        )
        results.append(evaluate(case, response))
        if progress_every and index % progress_every == 0:
            passed_so_far = sum(1 for result in results if result["passed"])
            print(
                json.dumps(
                    {
                        "progress": index,
                        "total": len(cases),
                        "passed": passed_so_far,
                        "failed": len(results) - passed_so_far,
                    }
                ),
                flush=True,
            )
    failed = [result for result in results if not result["passed"]]
    by_category: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_category.setdefault(result["category"], {"passed": 0, "failed": 0})
        bucket["passed" if result["passed"] else "failed"] += 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "pass_rate": round((len(results) - len(failed)) / max(len(results), 1), 4),
        "by_category": by_category,
        "failures": failed[:200],
    }


def write_report(payload: dict[str, Any]) -> tuple[Path, Path]:
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = results_dir / f"ai_stress_eval_{stamp}.json"
    md_path = results_dir / f"ai_stress_eval_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# RiskWiseAI Stress Eval",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Score: `{payload['passed']}/{payload['total']}` passed (`{payload['pass_rate']:.1%}`)",
        "",
        "## By Category",
        "",
    ]
    for category, stats in sorted(payload["by_category"].items()):
        lines.append(f"- `{category}`: {stats['passed']} passed, {stats['failed']} failed")
    lines.extend(["", "## Failures", ""])
    if not payload["failures"]:
        lines.append("No failures.")
    for failure in payload["failures"]:
        lines.extend(
            [
                f"### {failure['id']} ({failure['category']})",
                "",
                f"Prompt: {failure['message']}",
                "",
                f"Mode: `{failure['mode']}`",
                "",
                "Answer:",
                "",
                failure["answer"],
                "",
                "Checks:",
            ]
        )
        for check in failure["checks"]:
            lines.append(f"- {'PASS' if check['passed'] else 'FAIL'} `{check['name']}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run generated RiskWiseAI stress tests.")
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--progress-every", type=int, default=25, help="Print progress every N cases. Use 0 to silence progress.")
    args = parser.parse_args()
    payload = asyncio.run(run_stress(args.count, progress_every=args.progress_every))
    json_path, md_path = write_report(payload)
    print(
        json.dumps(
            {
                "passed": payload["passed"],
                "failed": payload["failed"],
                "total": payload["total"],
                "pass_rate": payload["pass_rate"],
                "json": str(json_path),
                "markdown": str(md_path),
            },
            indent=2,
        )
    )
    if payload["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
