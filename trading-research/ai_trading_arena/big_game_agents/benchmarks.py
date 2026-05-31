from __future__ import annotations


def _static_weights(weights: dict[str, float]):
    def policy(history, prices, state, config, scoreboard) -> dict:
        return {"weights": weights, "reason": "Static human-style benchmark."}

    return policy


human_spy_buy_hold = _static_weights({"SPY": 1.0})
human_qqq_buy_hold = _static_weights({"QQQ": 1.0})
human_60_40 = _static_weights({"SPY": 0.60, "TLT": 0.40})
