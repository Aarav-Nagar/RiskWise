from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def execute_target(state: dict, target: dict, prices: pd.Series, date: pd.Timestamp, expiry_date: pd.Timestamp, config) -> None:
    rebalance_stock_book(state, target.get("weights", {}), prices, config)
    for order in target.get("options", []):
        buy_option_proxy(state, order, prices, date, expiry_date, config)


def rebalance_stock_book(state: dict, target_weights: dict[str, float], prices: pd.Series, config) -> None:
    equity = mark_state(state, prices, pd.Timestamp(prices.name) if prices.name is not None else pd.Timestamp.today())
    tickers = set(state["shares"]) | set(target_weights)
    for ticker in tickers:
        price = float(prices.get(ticker, np.nan))
        if not np.isfinite(price) or price <= 0:
            continue
        current_value = state["shares"].get(ticker, 0.0) * price
        target_value = equity * target_weights.get(ticker, 0.0)
        trade_value = target_value - current_value
        if abs(trade_value) < max(1.0, equity * 0.01):
            continue
        cost = abs(trade_value) * config.transaction_cost_rate
        state["cash"] -= trade_value + cost
        state["shares"][ticker] = state["shares"].get(ticker, 0.0) + trade_value / price
        if abs(state["shares"][ticker]) < 1e-9:
            state["shares"].pop(ticker, None)
        state["costs"] += cost
        state["trades"] += 1


def buy_option_proxy(state: dict, order: dict, prices: pd.Series, entry_date: pd.Timestamp, expiry_date: pd.Timestamp, config) -> None:
    ticker = order["ticker"]
    spot = float(prices.get(ticker, np.nan))
    if not np.isfinite(spot) or spot <= 0:
        return
    allocation = min(order["allocation"], max(0.0, state["cash"]))
    premium = bs_call_price(spot, spot, 30 / 365, 0.35)
    if premium <= 0:
        return
    cost = allocation * config.transaction_cost_rate
    contracts = (allocation - cost) / premium
    state["cash"] -= allocation
    state["costs"] += cost
    state["trades"] += 1
    state["option_book"].append(
        {
            "ticker": ticker,
            "direction": "call",
            "strike": spot,
            "premium": premium,
            "contracts": contracts,
            "entry_date": entry_date,
            "expiry_date": expiry_date,
        }
    )


def settle_options(state: dict, prices: pd.Series, date: pd.Timestamp, config) -> None:
    remaining = []
    for option in state["option_book"]:
        if date < option["expiry_date"]:
            remaining.append(option)
            continue
        spot = float(prices.get(option["ticker"], np.nan))
        if not np.isfinite(spot) or spot <= 0:
            remaining.append(option)
            continue
        payoff = max(spot - option["strike"], 0.0) * option["contracts"]
        cost = payoff * config.transaction_cost_rate
        state["cash"] += payoff - cost
        state["costs"] += cost
        state["trades"] += 1
    state["option_book"] = remaining


def mark_state(state: dict, prices: pd.Series, date: pd.Timestamp) -> float:
    stock_value = sum(
        shares * float(prices.get(ticker, 0.0))
        for ticker, shares in state["shares"].items()
        if np.isfinite(float(prices.get(ticker, np.nan)))
    )
    option_value = 0.0
    for option in state["option_book"]:
        spot = float(prices.get(option["ticker"], np.nan))
        if not np.isfinite(spot) or spot <= 0:
            continue
        option_value += bs_call_price(spot, option["strike"], max((option["expiry_date"] - date).days, 1) / 365, 0.35) * option["contracts"]
    return state["cash"] + stock_value + option_value


def bs_call_price(spot: float, strike: float, tau: float, sigma: float, rate: float = 0.04) -> float:
    if tau <= 0 or sigma <= 0:
        return max(spot - strike, 0.0)
    d1 = (np.log(spot / strike) + (rate + 0.5 * sigma**2) * tau) / (sigma * np.sqrt(tau))
    d2 = d1 - sigma * np.sqrt(tau)
    return float(spot * norm.cdf(d1) - strike * np.exp(-rate * tau) * norm.cdf(d2))


def scoreboard_snapshot(states: dict, prices: pd.Series, config) -> pd.DataFrame:
    rows = []
    for name, state in states.items():
        equity = mark_state(state, prices, pd.Timestamp(prices.name) if prices.name is not None else pd.Timestamp.today())
        rows.append({"agent": name, "equity": equity, "distance_to_2x": config.target - equity})
    return pd.DataFrame(rows).sort_values("equity", ascending=False)
