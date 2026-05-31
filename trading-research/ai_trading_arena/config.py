from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ArenaConfig:
    """Configuration for the $100 next-session paper-trading arena."""

    starting_capital: float = 100.0
    transaction_cost_rate: float = 0.001
    max_position_weight: float = 0.40
    max_holdings: int = 5
    lookback_days: int = 420
    benchmark: str = "SPY"
    universe: tuple[str, ...] = (
        "AAPL",
        "MSFT",
        "NVDA",
        "AMD",
        "AMZN",
        "META",
        "TSLA",
        "GOOGL",
        "PLTR",
        "AVGO",
        "COST",
        "WMT",
        "MCD",
        "NKE",
        "PG",
        "PEP",
        "KO",
        "JPM",
        "BAC",
        "V",
        "MA",
        "XOM",
        "UNH",
        "LLY",
        "JNJ",
        "MRK",
        "ABBV",
        "PFE",
        "SPY",
        "QQQ",
    )
    arena_dir: Path = Path("arena")
    data_dir: Path = Path("arena/data")
    submissions_dir: Path = Path("arena/submissions")
    results_dir: Path = Path("arena/results")
    live_dir: Path = Path("arena/live")
    factor_score_paths: tuple[Path, ...] = field(
        default_factory=lambda: (
            Path("data/processed/fundamental_publication_fmp_scored_panel.csv"),
            Path("data/processed/fundamental_publication_scored_panel.csv"),
            Path("data/processed/fundamental_technical_scored_panel.csv"),
        )
    )

    @property
    def cache_path(self) -> Path:
        return self.data_dir / "daily_prices.csv"


DEFAULT_CONFIG = ArenaConfig()
