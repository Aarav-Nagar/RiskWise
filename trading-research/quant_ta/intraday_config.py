from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from quant_ta.config import PROJECT_ROOT


@dataclass(frozen=True)
class IntradayConfig:
    provider: str = field(
        default_factory=lambda: "stockdata"
        if os.getenv("STOCKDATA_API_KEY")
        else "alphavantage"
        if os.getenv("ALPHAVANTAGE_API_KEY")
        else "yahoo"
    )
    interval: str = "1m"
    period: str = "7d"
    historical_start: str = "2025-07-01"
    historical_end: str = "2026-05-01"
    stockdata_start: str = "2026-04-14"
    stockdata_end: str = "2026-05-14"
    test_start: str = "2026-01-01"
    test_end: str = "2026-05-01"
    horizons: tuple[int, ...] = (1, 3, 5, 10, 15, 30, 60, 120, 240)
    seed: int = 42
    long_threshold: float = 0.55
    cash_threshold: float = 0.45
    transaction_cost: float = 0.0005
    slippage: float = 0.0002
    initial_capital: float = 1000.0
    top_k: int = 3
    fixed_position_size: float = 0.25
    max_position_size: float = 0.35
    stop_loss: float = 0.0035
    take_profit: float = 0.007
    max_daily_loss: float = 0.015
    max_trades_per_day: int = 10
    tickers: tuple[str, ...] = (
        "AAPL",
        "MSFT",
        "NVDA",
        "TSLA",
        "AMD",
        "AMZN",
        "META",
        "SPY",
    )
    root: Path = PROJECT_ROOT
    raw_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "intraday_raw")
    provider_cache_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "intraday_raw" / "provider_cache")
    processed_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "intraday_processed")
    model_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts" / "intraday_models")
    metrics_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts" / "intraday_metrics")
    backtest_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts" / "intraday_backtests")
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")

    def ensure_dirs(self) -> None:
        for path in (
            self.raw_dir,
            self.provider_cache_dir,
            self.processed_dir,
            self.model_dir,
            self.metrics_dir,
            self.backtest_dir,
            self.reports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


INTRADAY_CONFIG = IntradayConfig()
