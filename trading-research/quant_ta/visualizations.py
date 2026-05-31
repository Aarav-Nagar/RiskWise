from __future__ import annotations

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import RocCurveDisplay

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.features import load_features
from quant_ta.io import read_frame
from quant_ta.models import load_predictions


plt.style.use("seaborn-v0_8-whitegrid")


def _save(fig: plt.Figure, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_correlation_heatmap(config: ResearchConfig = CONFIG) -> None:
    features = load_features(config)
    numeric = features.select_dtypes(include=["number"]).drop(
        columns=[col for col in features.columns if col.startswith("future_return_") or col.startswith("label_")],
        errors="ignore",
    )
    corr = numeric.corr().abs()
    top = corr.mean().sort_values(ascending=False).head(25).index
    fig, ax = plt.subplots(figsize=(12, 10))
    image = ax.imshow(corr.loc[top, top], cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(len(top)), top, rotation=90, fontsize=7)
    ax.set_yticks(range(len(top)), top, fontsize=7)
    ax.set_title("Technical Feature Correlation Heatmap")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    _save(fig, config.figures_dir / "feature_correlation_heatmap.png")


def plot_prediction_histograms(config: ResearchConfig = CONFIG) -> None:
    predictions = load_predictions(config)
    for horizon, group in predictions[predictions["split"] == "test"].groupby("horizon"):
        fig, ax = plt.subplots(figsize=(10, 6))
        for model, model_group in group.groupby("model"):
            ax.hist(model_group["probability"], bins=30, alpha=0.35, label=model, density=True)
        ax.axvline(config.long_threshold, color="#1b9e77", linestyle="--", linewidth=1)
        ax.axvline(config.cash_threshold, color="#d95f02", linestyle="--", linewidth=1)
        ax.set_title(f"Prediction Confidence Distribution - {horizon}D Horizon")
        ax.set_xlabel("Predicted probability of positive forward return")
        ax.set_ylabel("Density")
        ax.legend(fontsize=7, ncols=2)
        _save(fig, config.figures_dir / f"prediction_histogram_{horizon}d.png")


def plot_roc_curves(config: ResearchConfig = CONFIG) -> None:
    predictions = load_predictions(config)
    for horizon, group in predictions[predictions["split"] == "test"].groupby("horizon"):
        fig, ax = plt.subplots(figsize=(8, 7))
        for model, model_group in group.groupby("model"):
            if model_group["label"].nunique() < 2:
                continue
            RocCurveDisplay.from_predictions(
                model_group["label"].astype(int),
                model_group["probability"],
                name=model,
                ax=ax,
                linewidth=1.3,
            )
        ax.set_title(f"ROC Curves - {horizon}D Horizon")
        _save(fig, config.figures_dir / f"roc_curves_{horizon}d.png")


def plot_equity_and_drawdowns(config: ResearchConfig = CONFIG) -> None:
    path = config.backtest_dir / "equity_curves.csv"
    if not path.exists():
        return
    curves = read_frame(path, parse_dates=["date"])
    for horizon, group in curves.groupby("horizon"):
        aggregate = group.groupby(["date", "model"], as_index=False)[["equity", "drawdown"]].mean()
        fig, ax = plt.subplots(figsize=(12, 7))
        for model, model_group in aggregate.groupby("model"):
            ax.plot(model_group["date"], model_group["equity"], label=model, linewidth=1.4)
        ax.set_title(f"Average Test Equity Curves - {horizon}D Horizon")
        ax.set_ylabel("Equity, initial capital = 1.0")
        ax.legend(fontsize=7, ncols=2)
        _save(fig, config.figures_dir / f"equity_curves_{horizon}d.png")

        fig, ax = plt.subplots(figsize=(12, 6))
        for model, model_group in aggregate.groupby("model"):
            ax.plot(model_group["date"], model_group["drawdown"], label=model, linewidth=1.2)
        ax.set_title(f"Average Drawdowns - {horizon}D Horizon")
        ax.set_ylabel("Drawdown")
        ax.legend(fontsize=7, ncols=2)
        _save(fig, config.figures_dir / f"drawdowns_{horizon}d.png")


def plot_horizon_comparisons(config: ResearchConfig = CONFIG) -> None:
    metrics_path = config.metrics_dir / "classification_metrics.csv"
    backtest_path = config.backtest_dir / "backtest_metrics_aggregate.csv"
    if metrics_path.exists():
        metrics = read_frame(metrics_path)
        test = metrics[metrics["split"] == "test"]
        fig, ax = plt.subplots(figsize=(12, 6))
        pivot = test.pivot_table(index="horizon", columns="model", values="roc_auc", aggfunc="mean")
        pivot.plot(kind="bar", ax=ax)
        ax.set_title("Test ROC-AUC by Horizon")
        ax.set_ylabel("ROC-AUC")
        ax.axhline(0.5, color="black", linewidth=1, linestyle="--")
        ax.legend(fontsize=7, ncols=2)
        _save(fig, config.figures_dir / "horizon_roc_auc_comparison.png")
    if backtest_path.exists():
        backtests = read_frame(backtest_path)
        fig, ax = plt.subplots(figsize=(12, 6))
        pivot = backtests.pivot_table(index="horizon", columns="model", values="sharpe", aggfunc="mean")
        pivot.plot(kind="bar", ax=ax)
        ax.set_title("Average Test Sharpe by Horizon")
        ax.set_ylabel("Sharpe ratio")
        ax.axhline(0, color="black", linewidth=1)
        ax.legend(fontsize=7, ncols=2)
        _save(fig, config.figures_dir / "horizon_sharpe_comparison.png")


def plot_feature_importance(config: ResearchConfig = CONFIG) -> None:
    for horizon_dir in config.model_dir.glob("*d"):
        horizon = horizon_dir.name
        for model_path in horizon_dir.glob("*.joblib"):
            model_bundle = joblib.load(model_path)
            estimator = model_bundle["estimator"]
            features = model_bundle["features"]
            model = estimator.named_steps.get("model", estimator) if hasattr(estimator, "named_steps") else estimator
            values = getattr(model, "feature_importances_", None)
            if values is None and hasattr(model, "coef_"):
                values = np.abs(model.coef_).ravel()
            if values is None:
                continue
            order = np.argsort(values)[-20:]
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.barh(np.array(features)[order], np.array(values)[order])
            ax.set_title(f"Feature Importance - {model_path.stem} {horizon}")
            _save(fig, config.figures_dir / f"feature_importance_{model_path.stem}_{horizon}.png")


def plot_volatility_regimes(config: ResearchConfig = CONFIG) -> None:
    features = load_features(config)
    spy = features[features["ticker"] == config.benchmark].sort_values("date")
    if spy.empty or "volatility_20d" not in spy:
        return
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(spy["date"], spy["volatility_20d"] * np.sqrt(252), color="#1f77b4", linewidth=1.5)
    ax.set_title("SPY 20D Annualized Volatility Regime")
    ax.set_ylabel("Annualized volatility")
    _save(fig, config.figures_dir / "volatility_regime_spy.png")


def generate_visualizations(config: ResearchConfig = CONFIG) -> None:
    config.ensure_dirs()
    plot_correlation_heatmap(config)
    plot_prediction_histograms(config)
    plot_roc_curves(config)
    plot_equity_and_drawdowns(config)
    plot_horizon_comparisons(config)
    plot_feature_importance(config)
    plot_volatility_regimes(config)
