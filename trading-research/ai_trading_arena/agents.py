from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .config import ArenaConfig, DEFAULT_CONFIG


Portfolio = dict[str, float]
AgentFn = Callable[[pd.DataFrame, pd.Timestamp, pd.DataFrame, ArenaConfig], Portfolio]


@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    build: AgentFn


def _safe_last(group: pd.DataFrame, column: str) -> float:
    values = group[column].dropna()
    return float(values.iloc[-1]) if not values.empty else np.nan


def technical_snapshot(prices: pd.DataFrame, signal_date: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    usable = prices.loc[prices["date"] <= signal_date].sort_values(["ticker", "date"])
    for ticker, group in usable.groupby("ticker"):
        group = group.tail(260).copy()
        close = group["close"].astype(float)
        volume = group["volume"].astype(float)
        returns = close.pct_change()
        delta = close.diff()
        gains = delta.clip(lower=0).rolling(14).mean()
        losses = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = 100 - 100 / (1 + gains / losses.replace(0, np.nan))
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        high20 = close.rolling(20).max()
        low20 = close.rolling(20).min()
        vol20 = returns.rolling(20).std()
        rows.append(
            {
                "ticker": ticker,
                "close": _safe_last(group, "close"),
                "return_5d": close.pct_change(5).iloc[-1],
                "return_20d": close.pct_change(20).iloc[-1],
                "return_60d": close.pct_change(60).iloc[-1],
                "rsi_14d": rsi.iloc[-1],
                "price_to_sma20": close.iloc[-1] / sma20.iloc[-1] - 1 if pd.notna(sma20.iloc[-1]) else np.nan,
                "price_to_sma50": close.iloc[-1] / sma50.iloc[-1] - 1 if pd.notna(sma50.iloc[-1]) else np.nan,
                "breakout_20d": close.iloc[-1] / high20.iloc[-1] - 1 if pd.notna(high20.iloc[-1]) else np.nan,
                "drawdown_20d": close.iloc[-1] / high20.iloc[-1] - 1 if pd.notna(high20.iloc[-1]) else np.nan,
                "range_position_20d": (close.iloc[-1] - low20.iloc[-1]) / (high20.iloc[-1] - low20.iloc[-1])
                if pd.notna(low20.iloc[-1]) and high20.iloc[-1] != low20.iloc[-1]
                else np.nan,
                "volatility_20d": vol20.iloc[-1],
                "volume_z_20d": (volume.iloc[-1] - volume.rolling(20).mean().iloc[-1]) / volume.rolling(20).std().iloc[-1]
                if pd.notna(volume.rolling(20).std().iloc[-1]) and volume.rolling(20).std().iloc[-1] != 0
                else np.nan,
            }
        )
    return pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan)


def enforce_constraints(raw: Portfolio, config: ArenaConfig = DEFAULT_CONFIG) -> Portfolio:
    cleaned = {ticker: max(0.0, float(weight)) for ticker, weight in raw.items() if float(weight) > 0}
    cleaned = dict(sorted(cleaned.items(), key=lambda item: item[1], reverse=True)[: config.max_holdings])
    clipped = {ticker: min(weight, config.max_position_weight) for ticker, weight in cleaned.items()}
    total = sum(clipped.values())
    if total > 1.0:
        clipped = {ticker: weight / total for ticker, weight in clipped.items()}
    return {ticker: round(weight, 6) for ticker, weight in clipped.items() if weight > 0}


def equal_weight(tickers: list[str], config: ArenaConfig, cap: float | None = None) -> Portfolio:
    tickers = tickers[: config.max_holdings]
    if not tickers:
        return {}
    total = min(1.0, cap if cap is not None else 1.0)
    weight = min(config.max_position_weight, total / len(tickers))
    return enforce_constraints({ticker: weight for ticker in tickers}, config)


def random_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    tickers = [ticker for ticker in config.universe if ticker != config.benchmark]
    seed = int(hashlib.sha256(str(signal_date.date()).encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    choices = list(rng.choice(tickers, size=min(config.max_holdings, len(tickers)), replace=False))
    raw_weights = rng.random(len(choices))
    raw_weights = raw_weights / raw_weights.sum()
    return enforce_constraints(dict(zip(choices, raw_weights)), config)


def spy_benchmark(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    return {config.benchmark: 1.0}


def momentum_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    snap = technical_snapshot(prices, signal_date)
    snap = snap.loc[snap["ticker"] != config.benchmark].dropna(subset=["return_20d", "return_60d", "volatility_20d"])
    snap["score"] = snap["return_20d"] + 0.5 * snap["return_60d"] - 0.35 * snap["volatility_20d"]
    picks = snap.sort_values("score", ascending=False)["ticker"].head(config.max_holdings).tolist()
    return equal_weight(picks, config)


def mean_reversion_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    snap = technical_snapshot(prices, signal_date)
    snap = snap.loc[snap["ticker"] != config.benchmark].dropna(subset=["return_5d", "rsi_14d", "price_to_sma50"])
    snap = snap.loc[snap["price_to_sma50"] > -0.08]
    snap["score"] = -snap["return_5d"] + (45 - snap["rsi_14d"]).clip(lower=-20, upper=20) / 100
    picks = snap.sort_values("score", ascending=False)["ticker"].head(config.max_holdings).tolist()
    return equal_weight(picks, config, cap=0.85)


def fundamental_quality_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    if scores.empty or "fundamental_score" not in scores.columns:
        return momentum_agent(prices, signal_date, scores, config)
    usable = scores.loc[scores["ticker"] != config.benchmark].copy()
    usable = usable.loc[usable["ticker"].isin(config.universe)]
    usable["score"] = usable.get("fundamental_score", 0).fillna(0)
    picks = usable.sort_values("score", ascending=False)["ticker"].head(config.max_holdings).tolist()
    return equal_weight(picks, config)


def blended_ai_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    snap = technical_snapshot(prices, signal_date)
    merged = snap.merge(scores, on="ticker", how="left")
    merged = merged.loc[merged["ticker"] != config.benchmark].copy()
    merged = merged.loc[merged["ticker"].isin(config.universe)]
    for column in ["agent_score", "fundamental_score", "technical_score"]:
        if column not in merged:
            merged[column] = np.nan
    merged["fallback_technical"] = (
        merged["return_20d"].rank(pct=True)
        + merged["return_60d"].rank(pct=True)
        - merged["volatility_20d"].rank(pct=True)
        + merged["range_position_20d"].rank(pct=True)
    )
    merged["score"] = (
        0.55 * merged["agent_score"].fillna(merged["fallback_technical"])
        + 0.25 * merged["fundamental_score"].fillna(merged["fallback_technical"])
        + 0.20 * merged["technical_score"].fillna(merged["fallback_technical"])
    )
    picks = merged.sort_values("score", ascending=False)["ticker"].head(config.max_holdings).tolist()
    return equal_weight(picks, config)


def risk_managed_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    snap = technical_snapshot(prices, signal_date)
    merged = snap.merge(scores, on="ticker", how="left")
    merged = merged.loc[merged["ticker"] != config.benchmark].dropna(subset=["volatility_20d"]).copy()
    merged = merged.loc[merged["ticker"].isin(config.universe)]
    merged["base_score"] = merged.get("agent_score", pd.Series(index=merged.index, dtype=float)).fillna(
        merged["return_20d"].rank(pct=True) + merged["return_60d"].rank(pct=True)
    )
    picks = merged.sort_values("base_score", ascending=False).head(4)
    if picks.empty:
        return {}
    inv_vol = 1 / picks["volatility_20d"].clip(lower=0.005)
    weights = inv_vol / inv_vol.sum()
    exposure = 0.85 if float(picks["volatility_20d"].mean()) < 0.035 else 0.60
    raw = dict(zip(picks["ticker"], weights * exposure))
    return enforce_constraints(raw, config)


def meta_consensus_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    """Blend sub-agent votes, technical regime, factor scores, and risk into one portfolio."""
    full_snap = technical_snapshot(prices, signal_date)
    full_snap = full_snap.loc[full_snap["ticker"].isin(config.universe)].copy()
    snap = full_snap.loc[full_snap["ticker"] != config.benchmark].copy()
    if snap.empty:
        return {config.benchmark: 0.5}

    sub_agents = [momentum_agent, mean_reversion_agent, fundamental_quality_agent, blended_ai_agent, risk_managed_agent]
    vote_rows: list[dict[str, float | str]] = []
    for builder in sub_agents:
        for ticker, weight in builder(prices, signal_date, scores, config).items():
            if ticker != config.benchmark:
                vote_rows.append({"ticker": ticker, "vote_weight": weight})
    votes = pd.DataFrame(vote_rows)
    if votes.empty:
        return {config.benchmark: 0.5}
    vote_score = votes.groupby("ticker", as_index=False).agg(vote_count=("ticker", "size"), vote_weight=("vote_weight", "sum"))

    merged = snap.merge(vote_score, on="ticker", how="left").merge(scores, on="ticker", how="left")
    merged[["vote_count", "vote_weight"]] = merged[["vote_count", "vote_weight"]].fillna(0)
    for column in ["agent_score", "fundamental_score", "technical_score"]:
        if column not in merged:
            merged[column] = np.nan

    merged["trend_rank"] = (merged["return_20d"].fillna(0) + 0.5 * merged["return_60d"].fillna(0)).rank(pct=True)
    merged["reversion_rank"] = (-merged["return_5d"].fillna(0) + (50 - merged["rsi_14d"].fillna(50)).clip(-25, 25) / 100).rank(pct=True)
    merged["risk_penalty"] = merged["volatility_20d"].fillna(merged["volatility_20d"].median()).rank(pct=True)
    merged["consensus_rank"] = (merged["vote_count"] + merged["vote_weight"]).rank(pct=True)
    merged["factor_rank"] = (
        merged["agent_score"].fillna(0.5) + merged["fundamental_score"].fillna(0.5) + merged["technical_score"].fillna(0.5)
    ).rank(pct=True)

    spy = full_snap.loc[full_snap["ticker"] == config.benchmark]
    market_risk_off = False
    if not spy.empty:
        market_risk_off = bool(spy["return_5d"].iloc[0] < -0.02 or spy["price_to_sma20"].iloc[0] < -0.01)

    merged["score"] = (
        0.30 * merged["consensus_rank"]
        + 0.25 * merged["factor_rank"]
        + 0.20 * merged["trend_rank"]
        + 0.15 * merged["reversion_rank"]
        - 0.20 * merged["risk_penalty"]
    )
    picks = merged.sort_values("score", ascending=False).head(5).copy()
    if picks.empty:
        return {config.benchmark: 0.5}

    inv_vol = 1 / picks["volatility_20d"].fillna(picks["volatility_20d"].median()).clip(lower=0.006)
    weights = inv_vol / inv_vol.sum()
    exposure = 0.75 if market_risk_off else 0.90
    raw = dict(zip(picks["ticker"], weights * exposure))
    return enforce_constraints(raw, config)


def _contextual_rank_frame(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> pd.DataFrame:
    snap = technical_snapshot(prices, signal_date)
    merged = snap.merge(scores, on="ticker", how="left")
    merged = merged.loc[merged["ticker"].isin(config.universe)].copy()
    for column in [
        "agent_score",
        "fundamental_score",
        "technical_score",
        "sector_rotation_score",
        "news_score",
        "earnings_proximity_score",
        "liquidity_score",
        "liquidity_shock_score",
        "options_sentiment_score",
    ]:
        if column not in merged:
            merged[column] = 0.5
        merged[column] = merged[column].fillna(0.5)
    if "sector" not in merged:
        merged["sector"] = "Other"
    merged["trend_rank"] = (merged["return_20d"].fillna(0) + 0.5 * merged["return_60d"].fillna(0)).rank(pct=True)
    merged["reversion_rank"] = (-merged["return_5d"].fillna(0) + (50 - merged["rsi_14d"].fillna(50)).clip(-25, 25) / 100).rank(pct=True)
    merged["risk_rank"] = merged["volatility_20d"].fillna(merged["volatility_20d"].median()).rank(pct=True)
    merged["context_score"] = (
        0.25 * merged["sector_rotation_score"]
        + 0.20 * merged["news_score"]
        + 0.15 * merged["earnings_proximity_score"]
        + 0.15 * merged["liquidity_score"]
        - 0.10 * merged["liquidity_shock_score"]
        + 0.15 * merged["options_sentiment_score"]
    )
    return merged.replace([np.inf, -np.inf], np.nan).fillna(0.5)


def information_technology_context_agent(
    prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig
) -> Portfolio:
    merged = _contextual_rank_frame(prices, signal_date, scores, config)
    merged = merged.loc[merged["sector"].isin(["Information Technology", "Communication Services"])]
    merged = merged.loc[merged["ticker"] != config.benchmark].copy()
    if merged.empty:
        return {}
    merged["score"] = (
        0.30 * merged["trend_rank"]
        + 0.25 * merged["context_score"]
        + 0.20 * merged["agent_score"]
        + 0.15 * merged["technical_score"]
        - 0.20 * merged["risk_rank"]
    )
    picks = merged.sort_values("score", ascending=False).head(5)
    return equal_weight(picks["ticker"].tolist(), config, cap=0.90)


def healthcare_context_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    merged = _contextual_rank_frame(prices, signal_date, scores, config)
    merged = merged.loc[merged["sector"] == "Health Care"].copy()
    if merged.empty:
        return {}
    merged["score"] = (
        0.25 * merged["fundamental_score"]
        + 0.25 * merged["context_score"]
        + 0.20 * merged["reversion_rank"]
        + 0.15 * merged["trend_rank"]
        - 0.15 * merged["risk_rank"]
    )
    picks = merged.sort_values("score", ascending=False).head(5)
    return equal_weight(picks["ticker"].tolist(), config, cap=0.85)


def diversified_context_agent(prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig) -> Portfolio:
    merged = _contextual_rank_frame(prices, signal_date, scores, config)
    excluded = ["Information Technology", "Communication Services", "Health Care", "Benchmark"]
    merged = merged.loc[~merged["sector"].isin(excluded)].copy()
    if merged.empty:
        return {}
    merged["score"] = (
        0.25 * merged["context_score"]
        + 0.20 * merged["fundamental_score"]
        + 0.20 * merged["reversion_rank"]
        + 0.15 * merged["trend_rank"]
        + 0.10 * merged["sector_rotation_score"]
        - 0.15 * merged["risk_rank"]
    )
    picks = merged.sort_values("score", ascending=False).head(5)
    return equal_weight(picks["ticker"].tolist(), config, cap=0.85)


def cumulative_options_context_agent(
    prices: pd.DataFrame, signal_date: pd.Timestamp, scores: pd.DataFrame, config: ArenaConfig
) -> Portfolio:
    merged = _contextual_rank_frame(prices, signal_date, scores, config)
    merged = merged.loc[merged["ticker"] != config.benchmark].copy()
    if merged.empty:
        return {}
    merged["score"] = (
        0.20 * merged["agent_score"]
        + 0.18 * merged["fundamental_score"]
        + 0.17 * merged["technical_score"]
        + 0.18 * merged["context_score"]
        + 0.12 * merged["options_sentiment_score"]
        + 0.10 * merged["trend_rank"]
        + 0.05 * merged["reversion_rank"]
        - 0.18 * merged["risk_rank"]
    )
    picks = merged.sort_values("score", ascending=False).head(5).copy()
    inv_vol = 1 / picks["volatility_20d"].fillna(picks["volatility_20d"].median()).clip(lower=0.006)
    weights = inv_vol / inv_vol.sum() * 0.90
    return enforce_constraints(dict(zip(picks["ticker"], weights)), config)


AGENTS: tuple[Agent, ...] = (
    Agent("SPY_Benchmark", "Passive 100% SPY benchmark.", spy_benchmark),
    Agent("RandomAgent", "Seeded random long-only portfolio sanity check.", random_agent),
    Agent("MomentumAgent", "Trend and relative-strength technical portfolio.", momentum_agent),
    Agent("MeanReversionAgent", "Oversold bounce portfolio with trend filter.", mean_reversion_agent),
    Agent("FundamentalQualityAgent", "Uses latest saved fundamental quality ranks, fallback to momentum.", fundamental_quality_agent),
    Agent("BlendedAIAgent", "Rule-locked blend of saved fundamental and technical scores.", blended_ai_agent),
    Agent("RiskManagedAgent", "Volatility-scaled blend with partial cash during higher risk.", risk_managed_agent),
    Agent("MetaConsensusAgent", "Ensemble of sub-agent votes, factor ranks, technical regime, and volatility risk.", meta_consensus_agent),
    Agent("ITContextAgent", "Information-technology specialist using catalysts, sector rotation, liquidity, and technical context.", information_technology_context_agent),
    Agent("HealthCareContextAgent", "Health-care specialist using fundamentals, catalysts, earnings proximity, and risk context.", healthcare_context_agent),
    Agent("DiversifiedContextAgent", "Non-tech/non-health-care sector specialist using cross-sector context.", diversified_context_agent),
    Agent("CumulativeOptionsContextAgent", "Cumulative context model with options sentiment when option chains are available.", cumulative_options_context_agent),
)
