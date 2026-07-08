# Codex Builder Mode

RiskWise should be treated like a serious product build, not a loose prototype. Codex should move fast, stay honest, and avoid wasting tokens.

The goal is simple: execute useful work, keep the project organized, and clearly separate mock/demo behavior from production-ready behavior.

## Required Startup Behavior

When a new Codex conversation starts with the Builder Mode startup prompt, Codex must:

1. Read:
   - `docs/CODEX_HANDOFF.md`
   - `docs/NEXT_TASKS.md`
   - `docs/CODEX_BUILDER_MODE.md`
2. Avoid reading unrelated files until the actual task is given.
3. Reply with exactly this kind of short confirmation:

```text
OK, I have all of the RiskWise context and I am ready to start working. Send me the task.
```

Do not summarize the whole repo after reading the startup files unless the user asks.

## Communication Style

Use concise, direct, useful language.

Do:

- Be clear and practical.
- Tell the user what matters.
- Use short progress updates while working.
- Prefer action over long explanation.
- Report exact blockers and exact next steps.
- Say when something is mock, partial, untested, or production-ready.
- Keep final answers focused on what changed, what was tested, and what remains.

Do not:

- Use excessive hype.
- Use filler phrases.
- Re-explain the whole app every turn.
- Produce giant percentage tables unless asked.
- Repeat the same architecture summary unless it changed.
- Say something is fixed if it was not tested.
- Overuse metaphors, jokes, or dramatic language.
- Make the answer feel like generic AI-generated product fluff.

Default final response format:

```text
Done. I changed [short summary].

Tested: [commands or "not run because..."]
Still left: [only if important]
```

For larger tasks:

```text
What changed
- ...

Tested
- ...

Blocked
- ...

Next
- ...
```

## User Preference Summary

The user prefers:

- execution over theory
- honest status over optimism
- concise updates
- strong product taste
- practical engineering decisions
- fewer interruptions
- specific bug fixes
- exact file paths and commands when useful
- app quality that feels human-built, not vibe-coded

The user dislikes:

- generic AI answers
- broad app summaries repeated constantly
- flat UI with no depth
- fake market-data certainty
- screenshots/extraction that returns random fake values
- "Something went wrong" errors without a real reason
- asking for confirmation when the next step is obvious
- long responses when a short one would work

## Core Product Focus

RiskWise has four active product areas:

- Home
- Check
- Coach
- Profile

The main product is the Check flow plus RiskWiseAI Coach. Do not add extra tabs or broad dashboard features unless they directly strengthen options-risk review, selected-trade context, or AI coaching.

Older ideas such as Journal, Growth, Arena, Learn, and Alerts are not active app tabs unless the user explicitly reactivates them.

## Working Style

Default to execution. If the user asks to fix, improve, implement, test, or continue, do the work rather than only proposing a plan.

Ask questions only when:

- a required secret/API key is missing
- a destructive move/delete is being considered
- a decision cannot be safely inferred
- user ownership is legally or platform-required, such as Apple Developer enrollment

When blocked, do not handwave. Report:

- exact command or step
- exact error
- what was already tried
- safest next workaround

## Context Discipline

Before working, read only the minimum files needed.

Start with:

- `docs/CODEX_HANDOFF.md`
- `docs/NEXT_TASKS.md`
- `docs/CODEX_BUILDER_MODE.md`

Then read only the relevant files for the task.

Avoid reading or scanning these unless explicitly needed:

- `frontend/mobile-demo/node_modules`
- `frontend/mobile-demo/dist`
- `frontend/mobile-demo/.expo`
- `backend/api/evals/results`
- `trading-research/arena/figures`
- root smoke screenshots named `riskwise-*.png`

Prefer targeted commands:

```bash
rg "pattern" backend/api/services frontend/mobile-demo/src
rg --files frontend/mobile-demo/src backend/api/services
```

Avoid broad recursive scans unless necessary.

## RiskWise Product Rules

RiskWise is educational decision support.

Do not describe it as:

- a trading bot
- a signal generator
- a profit predictor
- a trade execution app

Use language like:

- risk review
- contract context
- educational analysis
- decision support
- missing-data warning
- scenario explanation

Avoid direct advice language:

- buy
- sell
- enter
- exit
- guaranteed
- should trade

The app can explain risk. It should not tell users what trade to make.

## Market Data Honesty

Never invent live market data.

If IV, Greeks, bid/ask, open interest, volume, earnings date, or option-chain data is unavailable, say it is missing.

Data quality labels should be explicit:

- Full
- Delayed
- Estimated
- Reference-only
- Manual
- Missing

Provider-reported Greeks and RiskWise-estimated Greeks are different. Label them differently.

Manual/uploaded broker context is user-provided data, not redistributed live market data.

## RiskWiseAI Rules

RiskWiseAI is tool-first.

Backend tools calculate:

- max loss
- breakeven
- DTE
- required move
- account risk percent
- liquidity score
- data quality
- estimated Greeks when possible

The model explains and synthesizes. The model does not do authoritative math.

Provider order:

- local/dev: Ollama or LM Studio with Qwen
- hosted fallback: Gemini/OpenAI if configured
- deterministic fallback: always available

Qwen/Ollama or LM Studio runs on the backend machine, not inside the mobile app.

RiskWiseAI should feel conversational, but specific. Avoid generic textbook responses when selected trade context exists.

Deep Analysis should include:

- five-agent committee
- committee score
- top risks
- strongest evidence
- weakest evidence
- missing data
- what RiskWise used
- next question

No raw JSON should appear in the app UI.

## Check Flow Rules

Check is the core product experience.

The Check flow must be reliable before adding new product features.

Required behavior:

- user must select a real ticker/search result before continuing
- no past expirations
- strike must be greater than zero
- premium must be greater than zero for long options
- contracts must be at least one
- bid cannot be greater than ask
- max loss must be premium x contracts x 100 for long options
- user gets specific validation errors, not generic failure messages

Screenshot/manual upload must be real:

- no random fake extraction
- extract readable fields if possible
- use OCR/vision only when a capable provider is configured
- require user confirmation before analysis
- show exactly what fields are missing

## Profile Rules

Profile is for AI personalization and account control.

Important sections:

- Trader DNA
- Risk Rules
- Coach Style
- AI Memory
- Saved Context
- Account & Security

Profile settings should affect Coach behavior when possible.

Examples:

- simple explanations
- quant-heavy explanations
- debate both sides
- ask questions first
- strict risk style

Every edit should persist to the backend when auth/database are configured.

## UI Taste Rules

RiskWise should feel clean, trustworthy, and human-built.

Prefer:

- simple hierarchy
- crisp spacing
- readable cards
- subtle depth
- intentional green accent
- clear empty states
- useful charts or visual summaries when they clarify risk

Avoid:

- clutter
- flat generic white-card stacks
- random decorative elements
- giant marketing copy
- screens that require too much scrolling for simple settings
- UI that looks like it was generated without product judgment

## Testing Rules

Run the smallest useful test first.

Backend:

```bash
cd backend
python -m pytest api/tests
```

Frontend:

```bash
cd frontend/mobile-demo
npm run typecheck
npm run export:web
```

For UI changes, use browser smoke testing when available.

For AI changes, test at least:

- greeting
- IV crush
- explain simpler
- selected trade review
- Deep Analysis
- direct advice refusal
- missing-data honesty

Do not claim something is fixed unless it was tested or clearly say it was not tested.

## Git And File Safety

Do not delete generated folders or large artifacts without explicit approval.

Do not delete:

- `node_modules`
- `.expo`
- `dist`
- benchmark folders
- screenshots used in docs
- historical research outputs

Do not move the repo unless the user explicitly confirms the target path.

Do not revert unrelated user changes.

## Token Discipline

Keep Codex usage low.

Do:

- use handoff docs
- use targeted file reads
- summarize test failures
- keep progress updates short
- start new threads for large phases

Do not:

- paste full files into chat
- dump full logs unless needed
- repeatedly produce full app percentage tables unless asked
- resummarize the full project every turn

## Completion Standard

A task is complete only when:

- the relevant files are changed
- obvious edge cases are handled
- tests or validation were run when possible
- blockers are clearly reported
- the next task is obvious

If blocked, report:

- exact command or step
- exact error
- what was already tried
- safest next workaround
