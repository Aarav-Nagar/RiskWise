# Token Usage Playbook

This file keeps RiskWise Codex runs cheaper and faster without lowering answer quality.

## Why Usage Gets Burned Quickly

- Long conversations force Codex to preserve or reconstruct a lot of context.
- Broad requests like "continue working" require repo scans, planning, editing, testing, and summaries.
- Tool outputs count as context, especially long test logs, file inventories, diffs, screenshots, and pasted specs.
- The Codex environment itself has large tool, plugin, memory, and safety instructions before project context is added.
- Memory helps continuity, but opening memory files also adds context.
- Generated files do not cost tokens by existing; they cost tokens when scanned, opened, pasted, or summarized.

## Best Default Workflow

Start new threads for major phases and begin with:

```text
Read docs/CODEX_HANDOFF.md, docs/NEXT_TASKS.md, and docs/CODEX_BUILDER_MODE.md first. Use Builder Mode. After reading them, reply only: "OK, I have all of the RiskWise context and I am ready to start working. Send me the task."
```

Use one thread per area:

- Check screen and report flow
- RiskWiseAI backend
- Market data providers
- Profile/account system
- TestFlight/App Store prep

Use `docs/CURRENT_STATUS.md` for percentages instead of asking Codex to reconstruct them from memory every time.

## How To Ask For Work Efficiently

Good:

```text
Fix Check screenshot extraction only. Edit CheckScreen.js, apiClient.js, and backend extraction code if needed. Run backend tests and frontend typecheck. Give a short summary.
```

Expensive:

```text
Make the whole app production ready and tell me percentages again.
```

## Codex File Reading Rules

Prefer:

```bash
rg "pattern" backend/api/services frontend/mobile-demo/src/screens
rg --files frontend/mobile-demo/src backend/api/services
```

Avoid:

```bash
Get-ChildItem -Recurse
cat huge files
opening generated eval result folders
dumping full test logs into chat
```

## Folders To Avoid Unless Explicitly Needed

- `frontend/mobile-demo/node_modules`
- `frontend/mobile-demo/dist`
- `frontend/mobile-demo/dist-web`
- `frontend/mobile-demo/.expo`
- `frontend/mobile-demo/playwright-report`
- `frontend/mobile-demo/test-results`
- `frontend/mobile-demo/screenshots`
- `backend/api/evals/results`
- `trading-research/arena/figures`
- root smoke screenshots named `riskwise-*.png`

## Reporting Rules

- For routine status, use 5-8 bullets.
- Only give full percentage tables when explicitly requested.
- Summarize test failures by key line, not full logs.
- Mention exact file paths changed, but do not paste full files.

## Cleanup Policy

Safe to ignore through `.gitignore`:

- build outputs
- caches
- local env files
- generated eval results
- smoke screenshots

Do not delete without explicit approval:

- `node_modules`
- `.expo`
- `dist`
- untracked source files
- newly created docs
- benchmark folders
- screenshots that may be used in docs
- historical research outputs

Before any cleanup:

1. Run `git status --short`.
2. List exact cleanup targets.
3. Remove only generated folders already ignored by `.gitignore`.
4. Never use broad recursive deletion patterns such as `Get-ChildItem -Recurse -Include`.

## Cached Tokens

Cached tokens are managed by the model/provider system, not by local repo storage. Codex cannot manually clear them from the workspace. The practical way to reduce future usage is to reduce repeated prompt/context size through short handoff docs and narrower tasks.
