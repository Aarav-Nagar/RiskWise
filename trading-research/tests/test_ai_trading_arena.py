from __future__ import annotations

import json

import pandas as pd

from ai_trading_arena.agents import (
    cumulative_options_context_agent,
    enforce_constraints,
    healthcare_context_agent,
    information_technology_context_agent,
)
from ai_trading_arena.config import ArenaConfig
from ai_trading_arena.data import latest_signal_date, load_factor_scores
from ai_trading_arena.engine import build_submissions, score_submissions


def test_arena_constraints_prevent_leverage_and_oversized_positions() -> None:
    weights = enforce_constraints({"AAPL": 0.9, "MSFT": 0.7, "NVDA": 0.2, "AMD": 0.1}, ArenaConfig(max_holdings=3, max_position_weight=0.4))

    assert len(weights) == 3
    assert max(weights.values()) <= 0.4
    assert sum(weights.values()) <= 1.0


def test_latest_signal_date_is_strictly_before_trade_date() -> None:
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-12", "2026-05-13", "2026-05-15"]),
            "ticker": ["AAPL", "AAPL", "AAPL"],
            "open": [1, 1, 1],
            "close": [1, 1, 1],
        }
    )

    assert latest_signal_date(prices, pd.Timestamp("2026-05-15")) == pd.Timestamp("2026-05-13")


def test_spy_benchmark_is_allowed_to_be_fully_invested(tmp_path) -> None:
    config = ArenaConfig(
        arena_dir=tmp_path,
        data_dir=tmp_path / "data",
        submissions_dir=tmp_path / "submissions",
        results_dir=tmp_path / "results",
        universe=("SPY", "AAPL", "MSFT", "NVDA", "AMD", "AMZN"),
        factor_score_paths=(),
    )
    config.data_dir.mkdir(parents=True)
    dates = pd.bdate_range("2026-01-01", "2026-05-14")
    rows = []
    for ticker in config.universe:
        for i, day in enumerate(dates):
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": 100 + i,
                    "high": 101 + i,
                    "low": 99 + i,
                    "close": 100 + i,
                    "adj_close": 100 + i,
                    "volume": 1_000_000,
                }
            )
    pd.DataFrame(rows).to_csv(config.cache_path, index=False)

    submissions = build_submissions("2026-05-15", config=config, force=True, refresh_data=False)
    spy = submissions.loc[(submissions["agent"] == "SPY_Benchmark") & (submissions["ticker"] == "SPY"), "weight"].iloc[0]

    assert spy == 1.0


def test_scoring_reconciles_100_dollar_accounting(tmp_path) -> None:
    config = ArenaConfig(
        starting_capital=100,
        transaction_cost_rate=0.001,
        arena_dir=tmp_path,
        data_dir=tmp_path / "data",
        submissions_dir=tmp_path / "submissions",
        results_dir=tmp_path / "results",
    )
    config.data_dir.mkdir(parents=True)
    config.submissions_dir.mkdir(parents=True)
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-15", "2026-05-15"]),
            "ticker": ["AAPL", "MSFT"],
            "open": [100.0, 200.0],
            "high": [111.0, 202.0],
            "low": [99.0, 198.0],
            "close": [110.0, 198.0],
            "adj_close": [110.0, 198.0],
            "volume": [1_000_000, 2_000_000],
        }
    )
    prices.to_csv(config.cache_path, index=False)
    payload = {
        "trade_date": "2026-05-15",
        "agents": [
            {
                "agent": "TestAgent",
                "weights": {"AAPL": 0.5, "MSFT": 0.5},
            }
        ],
    }
    with (config.submissions_dir / "2026-05-15.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    result = score_submissions("2026-05-15", config=config, refresh_data=False).iloc[0]

    assert round(result["gross_return"], 4) == 0.045
    assert round(result["transaction_cost_dollars"], 2) == 0.10
    assert round(result["ending_value"], 2) == 104.40


def test_context_agents_respect_sector_specialization() -> None:
    config = ArenaConfig(universe=("AAPL", "MSFT", "UNH", "LLY", "JPM", "SPY"), max_holdings=3)
    dates = pd.bdate_range("2026-01-01", "2026-05-14")
    rows = []
    for ticker in config.universe:
        for i, day in enumerate(dates):
            base = 100 + i * (1.0 if ticker in {"AAPL", "MSFT"} else 0.4)
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": base,
                    "high": base + 1,
                    "low": base - 1,
                    "close": base,
                    "adj_close": base,
                    "volume": 1_000_000 + i,
                }
            )
    prices = pd.DataFrame(rows)
    scores = pd.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "UNH", "LLY", "JPM"],
            "sector": ["Information Technology", "Information Technology", "Health Care", "Health Care", "Financials"],
            "agent_score": [0.9, 0.8, 0.7, 0.6, 0.5],
            "fundamental_score": [0.7, 0.7, 0.9, 0.8, 0.6],
            "technical_score": [0.8, 0.8, 0.5, 0.5, 0.5],
            "sector_rotation_score": [0.9, 0.9, 0.8, 0.8, 0.4],
            "news_score": [0.8, 0.7, 0.9, 0.8, 0.3],
            "earnings_proximity_score": [0.5, 0.5, 0.7, 0.7, 0.5],
            "liquidity_score": [0.8, 0.8, 0.7, 0.7, 0.6],
            "liquidity_shock_score": [0.1, 0.1, 0.1, 0.1, 0.1],
            "options_sentiment_score": [0.7, 0.6, 0.5, 0.5, 0.4],
        }
    )

    it_weights = information_technology_context_agent(prices, pd.Timestamp("2026-05-15"), scores, config)
    hc_weights = healthcare_context_agent(prices, pd.Timestamp("2026-05-15"), scores, config)

    assert set(it_weights).issubset({"AAPL", "MSFT"})
    assert set(hc_weights).issubset({"UNH", "LLY"})


def test_cumulative_options_context_agent_uses_constraints() -> None:
    config = ArenaConfig(universe=("AAPL", "MSFT", "UNH", "LLY", "JPM", "SPY"), max_holdings=3, max_position_weight=0.4)
    dates = pd.bdate_range("2026-01-01", "2026-05-14")
    rows = []
    for ticker in config.universe:
        for i, day in enumerate(dates):
            base = 100 + i
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": base,
                    "high": base + 1,
                    "low": base - 1,
                    "close": base,
                    "adj_close": base,
                    "volume": 1_000_000,
                }
            )
    prices = pd.DataFrame(rows)
    scores = pd.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "UNH", "LLY", "JPM"],
            "sector": ["Information Technology", "Information Technology", "Health Care", "Health Care", "Financials"],
            "agent_score": [0.9, 0.8, 0.7, 0.6, 0.5],
            "fundamental_score": [0.9, 0.8, 0.7, 0.6, 0.5],
            "technical_score": [0.9, 0.8, 0.7, 0.6, 0.5],
            "sector_rotation_score": [0.9, 0.8, 0.7, 0.6, 0.5],
            "news_score": [0.9, 0.8, 0.7, 0.6, 0.5],
            "earnings_proximity_score": [0.5, 0.5, 0.5, 0.5, 0.5],
            "liquidity_score": [0.8, 0.8, 0.8, 0.8, 0.8],
            "liquidity_shock_score": [0.1, 0.1, 0.1, 0.1, 0.1],
            "options_sentiment_score": [0.9, 0.8, 0.7, 0.6, 0.5],
        }
    )

    weights = cumulative_options_context_agent(prices, pd.Timestamp("2026-05-15"), scores, config)

    assert len(weights) <= 3
    assert sum(weights.values()) <= 1.0
    assert max(weights.values()) <= 0.4


def test_factor_scores_filter_future_filing_dates(tmp_path) -> None:
    path = tmp_path / "scores.csv"
    pd.DataFrame(
        {
            "date": ["2026-04-29", "2026-04-30"],
            "filing_date": ["2026-04-29", "2026-05-10"],
            "ticker": ["AAPL", "AAPL"],
            "quality_score": [0.2, 0.99],
            "growth_score": [0.2, 0.99],
            "technical_score": [0.2, 0.99],
            "fundamental_score": [0.2, 0.99],
            "agent_score": [0.2, 0.99],
        }
    ).to_csv(path, index=False)
    config = ArenaConfig(factor_score_paths=(path,))

    scores = load_factor_scores(config, pd.Timestamp("2026-04-30"))

    assert len(scores) == 1
    assert scores.iloc[0]["agent_score"] == 0.2
