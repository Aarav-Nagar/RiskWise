from __future__ import annotations

import pandas as pd

from ai_trading_arena.context import SECTOR_MAP

from .accounting import mark_state
from .signals import ranked_momentum_score


def options_no_intervention(history, prices, state, config, scoreboard) -> dict:
    return _options_orders_from_momentum(
        history,
        prices,
        state,
        config,
        premium_fraction=0.50,
        weights={},
        reason="Options-only, no intervention: monthly ATM calls on strongest assets, max 50% premium at risk.",
    )


def options_risk_rules(history, prices, state, config, scoreboard) -> dict:
    equity = mark_state(state, prices, pd.Timestamp(prices.name) if prices.name is not None else pd.Timestamp.today())
    peak = max(float(state.get("peak_equity", config.capital)), equity)
    state["peak_equity"] = peak
    drawdown = equity / peak - 1
    if equity >= config.target:
        return {
            "weights": {"SPY": 0.60, "TLT": 0.20},
            "options": [],
            "reason": "Mechanical risk rules: 2x reached, lock gains into SPY/TLT and cash.",
        }
    if drawdown <= -0.40:
        return {
            "weights": {"SPY": 0.50},
            "options": [],
            "reason": "Mechanical risk rules: drawdown exceeded 40%, stop options and preserve capital.",
        }
    premium_fraction = 0.20 if peak >= 1.5 * config.capital else 0.35
    return _options_orders_from_momentum(
        history,
        prices,
        state,
        config,
        premium_fraction=premium_fraction,
        weights={"SPY": 0.25} if peak >= 1.5 * config.capital else {},
        reason=f"Mechanical risk rules: premium risk reduced to {premium_fraction:.0%}; peak-aware capital preservation.",
    )


def options_human_overseer(history, prices, state, config, scoreboard) -> dict:
    equity = mark_state(state, prices, pd.Timestamp(prices.name) if prices.name is not None else pd.Timestamp.today())
    peak = max(float(state.get("peak_equity", config.capital)), equity)
    state["peak_equity"] = peak
    drawdown = equity / peak - 1
    if equity >= config.target:
        return {
            "weights": {"SPY": 0.50, "TLT": 0.25, "GLD": 0.10},
            "options": [],
            "reason": "Human overseer: target reached, approve lock-in and reject new option premium.",
        }
    if drawdown <= -0.30:
        return {
            "weights": {"SPY": 0.35, "TLT": 0.35},
            "options": [],
            "reason": "Human overseer: 30% drawdown from peak, veto new options and stabilize.",
        }
    premium_fraction = 0.10 if equity >= 1.5 * config.capital else 0.25
    hedge_weights = {"SPY": 0.35} if equity >= 1.25 * config.capital else {"SPY": 0.15}
    return _options_orders_from_momentum(
        history,
        prices,
        state,
        config,
        premium_fraction=premium_fraction,
        weights=hedge_weights,
        reason=f"Human overseer: approve options but cap premium at {premium_fraction:.0%} and park capital in SPY.",
    )


def options_committee_veto(history, prices, state, config, scoreboard) -> dict:
    equity = mark_state(state, prices, pd.Timestamp(prices.name) if prices.name is not None else pd.Timestamp.today())
    qqq_trend = history["QQQ"].pct_change(63).iloc[-1] if "QQQ" in history else 0
    spy_trend = history["SPY"].pct_change(63).iloc[-1] if "SPY" in history else 0
    cross_asset_score = ranked_momentum_score(history).sort_values(ascending=False)
    risk_warning = qqq_trend < 0 or spy_trend < 0 or ("TLT" in cross_asset_score.head(3).index)
    if equity >= config.target:
        return {
            "weights": {"SPY": 0.55, "TLT": 0.20, "GLD": 0.10},
            "options": [],
            "reason": "Committee veto: 2x achieved; human risk manager locks gains.",
        }
    if risk_warning:
        return _options_orders_from_momentum(
            history,
            prices,
            state,
            config,
            premium_fraction=0.10,
            weights={"SPY": 0.35, "TLT": 0.20},
            reason="Committee veto: trend/risk agents warn risk-off, shrink options to 10%.",
        )
    return _options_orders_from_momentum(
        history,
        prices,
        state,
        config,
        premium_fraction=0.25 if equity >= 1.3 * config.capital else 0.35,
        weights={"SPY": 0.20},
        reason="Committee veto: options proposal approved with stock hedge and reduced premium.",
    )


def _options_orders_from_momentum(
    history,
    prices,
    state,
    config,
    premium_fraction: float,
    weights: dict[str, float],
    reason: str,
) -> dict:
    allowed = [
        ticker
        for ticker in history.columns
        if SECTOR_MAP.get(ticker) in {"Information Technology", "Health Care", "Financials", "Energy"} or ticker in {"SPY", "QQQ"}
    ]
    score = ranked_momentum_score(history[allowed])
    picks = score.sort_values(ascending=False).head(3)
    equity = mark_state(state, prices, pd.Timestamp(prices.name) if prices.name is not None else pd.Timestamp.today())
    stock_weight = sum(weights.values())
    allocation = min(equity * premium_fraction, equity * max(0.0, 1 - stock_weight))
    orders = [{"ticker": ticker, "allocation": allocation / len(picks), "direction": "call"} for ticker in picks.index]
    return {"weights": weights, "options": orders, "reason": reason}
