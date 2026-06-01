# Changelog

## 2026-05-31

- Reworked the README around the RiskWise product story.
- Added screenshot references for Check, Investigation, Profile, and Coach screens.
- Added product vision documentation.
- Added system architecture documentation.
- Added AI agent design documentation.

## 2026-05-30

- Redesigned the Check experience around three paths: Stock Idea, Option Contract, and Screenshot.
- Added a more structured option contract flow.
- Improved ticker search fallback coverage for smaller and less famous symbols.
- Added investigation-style outputs with issue cards and agent debate.

## 2026-05-29

- Redesigned the Profile screen around trader identity, risk rules, app preferences, AI memory, and account/security sections.
- Added profile actions for clearing context, signing out, and account deletion prompts.
- Added UI tests for the Check and Profile flows.

## 2026-05-26

- Expanded RiskWiseAI backend evaluation cases.
- Added stronger options-focused response rules.
- Added structured response fields for cards, risk flags, and suggested follow-up questions.

## 2026-05-25

- Added FastAPI backend routes for trade checks, chat, saved checks, profile settings, and market context.
- Added MongoDB-ready storage with a safe local fallback.
- Added LLM provider routing for Gemini, OpenAI, Ollama, and fallback responses.
