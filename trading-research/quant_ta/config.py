from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ResearchConfig:
    start_date: str = "2018-01-01"
    train_end: str = "2022-12-31"
    validation_start: str = "2023-01-01"
    validation_end: str = "2023-12-31"
    test_start: str = "2024-01-01"
    benchmark: str = "SPY"
    horizons: tuple[int, ...] = (1, 5, 20, 30)
    seed: int = 42
    long_threshold: float = 0.55
    cash_threshold: float = 0.45
    transaction_cost: float = 0.001
    initial_capital: float = 1.0
    tickers: tuple[str, ...] = (
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "TSLA",
        "JPM",
        "XOM",
        "GOOGL",
        "AMD",
        "NFLX",
        "COST",
        "AVGO",
        "WMT",
        "BAC",
        "KO",
        "PLTR",
        "DIS",
        "INTC",
        "UNH",
        "V",
        "MA",
        "HD",
        "PG",
        "JNJ",
        "LLY",
        "PEP",
        "MRK",
        "ABBV",
        "ORCL",
        "CRM",
        "CSCO",
        "CVX",
        "NKE",
        "MCD",
        "GE",
        "CAT",
        "BA",
        "QCOM",
    )
    root: Path = PROJECT_ROOT
    raw_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw")
    processed_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed")
    model_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts" / "models")
    metrics_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts" / "metrics")
    backtest_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts" / "backtests")
    figures_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts" / "figures")
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")

    @property
    def all_tickers(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.tickers, self.benchmark)))

    def ensure_dirs(self) -> None:
        for path in (
            self.raw_dir,
            self.processed_dir,
            self.model_dir,
            self.metrics_dir,
            self.backtest_dir,
            self.figures_dir,
            self.reports_dir,
            self.root / "notebooks",
        ):
            path.mkdir(parents=True, exist_ok=True)


CONFIG = ResearchConfig()
