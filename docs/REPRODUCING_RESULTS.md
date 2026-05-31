# Reproducing The Results

These steps are meant for someone checking the work from a fresh clone.

## 1. Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run Tests

```bash
python -m pytest
```

Current local result:

```text
17 passed
```

## 3. Re-run The Big Game

```bash
python -m ai_trading_arena big-game --start 2025-05-01 --end 2026-05-01 --history-start 2023-01-01 --capital 1000 --target 2000
```

Expected leading result from the current run:

```text
Options_CommitteeVeto ending value around $2,585
OptionsOnly_NoIntervention ending value around $155
```

Numbers may move a little if Yahoo Finance revises historical adjusted data.

## 4. Re-run The Sector Walk-Forward

```bash
python -m ai_trading_arena sector-period --start 2024-05-01 --end 2026-05-01 --history-start 2023-01-01 --capital 1000
```

Expected broad result:

```text
Sector model profitable, but below SPY.
```

## 5. Check Artifacts

Important result files:

- `arena/results/big_game_2025-05-01_2026-05-01_summary.csv`
- `arena/results/big_game_2025-05-01_2026-05-01_monthly_scores.csv`
- `arena/results/sector_focus_2024-05-01_2026-05-01_summary.csv`

Important charts:

- `arena/figures/big_game_2025-05-01_2026-05-01_equity.png`
- `arena/figures/big_game_2025-05-01_2026-05-01_monthly_ranks.png`
- `arena/figures/sector_focus_2024-05-01_2026-05-01_equity.png`

## 6. Run Local Validation Helper

```bash
python scripts/validate_research.py
```

This checks tests, key artifacts, and common secret leaks.
