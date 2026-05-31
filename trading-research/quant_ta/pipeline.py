from __future__ import annotations

import argparse

from quant_ta.backtesting import run_backtests
from quant_ta.config import CONFIG
from quant_ta.data import download_prices
from quant_ta.features import build_features
from quant_ta.labels import build_labeled_dataset
from quant_ta.models import train_models
from quant_ta.report import generate_report
from quant_ta.visualizations import generate_visualizations


def run(command: str) -> None:
    CONFIG.ensure_dirs()
    if command == "download":
        download_prices(CONFIG)
    elif command == "features":
        build_features(CONFIG)
        build_labeled_dataset(CONFIG)
    elif command == "train":
        train_models(CONFIG)
    elif command == "evaluate":
        train_models(CONFIG)
    elif command == "backtest":
        run_backtests(CONFIG)
    elif command == "visualize":
        generate_visualizations(CONFIG)
    elif command == "report":
        generate_report(CONFIG)
    elif command == "all":
        download_prices(CONFIG)
        build_features(CONFIG)
        build_labeled_dataset(CONFIG)
        train_models(CONFIG)
        run_backtests(CONFIG)
        generate_visualizations(CONFIG)
        generate_report(CONFIG)
    else:
        raise ValueError(f"Unknown command: {command}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mathematical technical-analysis research pipeline.")
    parser.add_argument(
        "command",
        choices=["download", "features", "train", "evaluate", "backtest", "visualize", "report", "all"],
        help="Pipeline stage to run.",
    )
    args = parser.parse_args()
    run(args.command)


if __name__ == "__main__":
    main()
