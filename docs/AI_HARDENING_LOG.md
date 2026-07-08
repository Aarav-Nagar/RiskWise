# RiskWiseAI Hardening Log

Last updated: June 18, 2026

## Scope

Backend AI hardening focused on:

- RiskWiseAI eval coverage
- selected-check and latest-saved-check intelligence
- no-hallucination guardrails for live options data
- Profile memory and risk-rule answer shaping

The multi-agent/RAG direction was intentionally left alone.

## Strengthened Behaviors

- Coach answers "what trade did I do?" from selected Check reports.
- Coach answers "why is this risky?", "what can break this trade?", "explain my weakest link", and "what data is missing?" from actual report fields.
- Latest saved checks can answer risk and missing-data follow-ups even when no current Check report is selected.
- Every Coach answer now carries a compact context manifest covering selected check, saved checks, profile memory, recent chat, uploaded contract, market-data status, and missing-data count.
- Uploaded text contracts are parsed into the normal tool context, not treated as a separate side path.
- Uploaded contract fields can now drive ticker context, breakeven math, max-loss math, DTE, liquidity scoring, missing live-data warnings, and visible context blocks.
- Deep Analysis coverage checks the five-agent committee, missing data, and context used.
- Profile settings now affect responses for simple explanations, quant-heavy answers, strict risk style, ask-questions-first, common mistakes, max risk limit, avoid-earnings preference, and under-7-DTE warnings.
- LLM answers are rejected when they invent live IV, Greeks, bid/ask, volume, open interest, earnings dates, current prices, liquidity quality, expiration-chain detail, or direct trading instructions.
- Rejected provider/model answers now produce structured reasons such as `fabricated_live_data`, `direct_trading_instruction`, `ignored_selected_trade`, and `ignored_profile_style`.

## Annoying Issues Found And Fixed

- "Why is this risky?" was initially classified as a generic follow-up instead of using the selected report.
- "How should I think about position sizing?" was over-refused as if it were asking for a live trade pick.
- Selected-trade reviews were showing "saved trade" as a used tool even when no saved trade was used.
- "Why is this risky?" could accidentally trigger news context because of broad "why is" matching.
- Qualitative hallucinations such as "IV looks high" and "liquidity is strong" needed explicit guardrails, not only numeric hallucination checks.
- Short low-quality answers were initially hiding more useful safety reasons, so rejection diagnostics now collect multiple reasons instead of stopping early.
- Greek/open-interest phrasing like "has a 0.42 delta" and "2,400 open interest" needed separate detection from simpler "delta is" wording.
- Generated stress cases found that selected-report debate/sizing answers did not always name the actual ticker/contract.
- Contract-specific open-interest questions were too educational and did not clearly say live option-chain/provider data was missing.
- Beginner delta explanations could fall back to a generic Greeks answer instead of explaining stock/underlying sensitivity.
- Direct "Should I enter this call if premium is under..." prompts were classified as concepts before the refusal/reframe path.
- Adversarial hallucination tests found softer live-data claims such as "IV is around 32%", "bid sits at", "OI is 2400", "reports earnings tomorrow", and "mid price is about" needed explicit detection.
- Uploaded contract parsing was only used by a standalone extraction endpoint; Coach chat did not treat uploads as normal context.
- The text upload parser missed useful fields such as contracts, bid, ask, IV, open interest, volume, and underlying price.
- Missing-data labels from uploaded contracts were too backend-shaped, such as `impliedVolatility`, instead of user-facing labels like "implied volatility".
- Market-data tests expected only reference/no-provider options chains, but the backend can now return delayed yfinance chains; tests now require those contracts to be clearly labeled delayed and non-live.

## Latest Verification

- `python -m pytest api/tests/test_ai_contract.py -vv -s --tb=short` passed 66 / 66 AI contract tests. The full run completed but took about 27 minutes because `/ai/smoke` is slow in this environment.
- `python -m pytest api/tests/test_ai_contract.py -q -k "not ai_smoke_endpoint"` passed 67 / 67 selected AI contract tests.
- `python -m pytest api/tests/test_market_data_contract.py -q` passed 9 / 9 market-data contract tests.
- `LLM_PROVIDER_ORDER=fallback python api/evals/ai_quality_eval.py` passed 341 / 341 eval cases.
- `python api/evals/ai_stress_eval.py --count 500` passed 500 / 500 generated stress cases.
- `python -m py_compile api/services/llm.py api/services/ai_tools.py api/evals/ai_quality_eval.py api/evals/ai_stress_eval.py` passed.
- Latest quality eval report: `backend/api/evals/results/ai_quality_eval_20260618_214212.md`.
- Latest stress eval report: `backend/api/evals/results/ai_stress_eval_20260618_214323.md`.

## Remaining Work

- Run app-level Coach UI smoke tests when browser automation is available.
- Test the same prompt set with local Qwen/Ollama and any hosted fallback provider that is configured.
- Add production telemetry around provider rejection reasons so bad LLM answers can be measured without exposing secrets.
