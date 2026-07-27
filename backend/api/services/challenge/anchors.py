"""Concept-anchor sentences per Challenge risk dimension.

Each dimension carries 3-5 short sentences stating the concepts a solid answer
should touch. Answer coverage is measured as the best cosine similarity between
the user's answer embedding and these anchors (local nomic-embed-text), with a
deterministic keyword fallback when no local embedding model is reachable.
"""

from __future__ import annotations

DIMENSIONS = ["Timing", "Breakeven", "Sizing", "Volatility", "Liquidity", "Exit"]

CONCEPT_ANCHORS: dict[str, list[str]] = {
    "Timing": [
        "The option loses value every day from theta time decay as expiration approaches.",
        "There are only a limited number of trading days left before the contract expires.",
        "The stock has to move before expiration; a correct thesis that arrives too late still loses money.",
        "Short-dated contracts decay faster than longer-dated contracts.",
    ],
    "Breakeven": [
        "The underlying must move past the breakeven price before the position makes money at expiry.",
        "Breakeven is the strike plus the premium paid for a call, or the strike minus the premium for a put.",
        "The required percentage move to breakeven measures how far the stock has to travel.",
        "Being right on direction is not enough when the move is smaller than the premium paid.",
    ],
    "Sizing": [
        "The maximum loss is the full premium paid and it should stay inside a set percent of the account.",
        "Position size is the one risk input the trader fully controls before entry.",
        "Risking too large a share of the account on one trade forces emotional decisions later.",
        "Account risk percent compares the trade's max loss against the total account size.",
    ],
    "Volatility": [
        "Implied volatility sets how much movement the option price already expects.",
        "IV crush after an event can shrink the premium even when the stock moves the right way.",
        "Buying options when implied volatility is high means paying an inflated premium.",
        "Vega exposure means the position gains or loses value as implied volatility changes.",
    ],
    "Liquidity": [
        "A wide bid-ask spread means part of the position's value is lost immediately on entry and exit.",
        "Low open interest and low volume make it hard to exit at a fair price.",
        "Slippage from a thin market is a hidden cost on top of the premium.",
    ],
    "Exit": [
        "A specific price level or condition should invalidate the trade before it is entered.",
        "An exit plan defines when to take profit and when to accept the loss.",
        "Without a predefined invalidation level, losses become emotional decisions instead of rules.",
        "Holding to expiration lets time decay erase whatever value is left.",
    ],
}
