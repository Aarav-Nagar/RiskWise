from __future__ import annotations

import argparse

from quant_ta.intraday_agents import run_agent_experiment
from quant_ta.intraday_backtesting import run_intraday_backtests
from quant_ta.intraday_config import INTRADAY_CONFIG
from quant_ta.intraday_data import download_intraday_prices
from quant_ta.intraday_features import build_intraday_features
from quant_ta.intraday_impact import run_intraday_impact_experiment
from quant_ta.intraday_labels import build_intraday_labeled_dataset
from quant_ta.intraday_models import train_intraday_models
from quant_ta.setup_quality import run_setup_quality_experiment


def run(command: str) -> None:
    INTRADAY_CONFIG.ensure_dirs()
    if command == "download":
        download_intraday_prices(INTRADAY_CONFIG)
    elif command == "features":
        build_intraday_features(INTRADAY_CONFIG)
        build_intraday_labeled_dataset(INTRADAY_CONFIG)
    elif command in {"train", "evaluate"}:
        train_intraday_models(INTRADAY_CONFIG)
    elif command == "backtest":
        run_intraday_backtests(INTRADAY_CONFIG)
    elif command == "agents":
        run_agent_experiment(INTRADAY_CONFIG)
    elif command == "impact":
        run_intraday_impact_experiment(INTRADAY_CONFIG)
    elif command == "setup-quality":
        run_setup_quality_experiment(INTRADAY_CONFIG)
    elif command == "all":
        download_intraday_prices(INTRADAY_CONFIG)
        build_intraday_features(INTRADAY_CONFIG)
        build_intraday_labeled_dataset(INTRADAY_CONFIG)
        train_intraday_models(INTRADAY_CONFIG)
        run_intraday_backtests(INTRADAY_CONFIG)
        run_agent_experiment(INTRADAY_CONFIG)
        run_intraday_impact_experiment(INTRADAY_CONFIG)
        run_setup_quality_experiment(INTRADAY_CONFIG)
    else:
        raise ValueError(command)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the intraday technical-pattern research pipeline.")
    parser.add_argument(
        "command",
        choices=["download", "features", "train", "evaluate", "backtest", "agents", "impact", "setup-quality", "all"],
    )
    args = parser.parse_args()
    run(args.command)


if __name__ == "__main__":
    main()
