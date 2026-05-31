from __future__ import annotations

from ai_trading_arena.context import SECTOR_MAP

from .signals import ranked_momentum_score


def normal_sector_stock(history, prices, state, config, scoreboard) -> dict:
    allowed = [
        ticker
        for ticker in history.columns
        if SECTOR_MAP.get(ticker) in {"Information Technology", "Health Care", "Financials", "Energy"} or ticker == "QQQ"
    ]
    score = ranked_momentum_score(history[allowed])
    picks = score.sort_values(ascending=False).head(5)
    return {"weights": {ticker: 0.90 / len(picks) for ticker in picks.index}, "reason": "Monthly sector momentum with cash buffer."}


def anything_cross_asset(history, prices, state, config, scoreboard) -> dict:
    score = ranked_momentum_score(history)
    winners = score.sort_values(ascending=False).head(5)
    weights = {ticker: 0.95 / len(winners) for ticker in winners.index}
    return {"weights": weights, "reason": "Cross-asset relative strength: stocks, ETFs, bonds, gold, dollar, FX, crypto."}
