from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.evaluation import classification_metrics
from quant_ta.io import read_frame, write_frame
from quant_ta.labels import load_labeled_dataset
from quant_ta.splits import chronological_split, horizon_dataset

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - depends on optional local installation
    XGBClassifier = None


@dataclass
class TrainedModel:
    name: str
    horizon: int
    estimator: object
    features: list[str]
    validation_metrics: dict[str, float]


def _model_grid(seed: int) -> dict[str, list[object]]:
    models: dict[str, list[object]] = {
        "logistic_regression": [
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                    ("model", LogisticRegression(C=c, max_iter=2000, class_weight="balanced", random_state=seed)),
                ]
            )
            for c in (0.1, 1.0, 3.0)
        ],
        "random_forest": [
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    (
                        "model",
                        RandomForestClassifier(
                            n_estimators=250,
                            max_depth=depth,
                            min_samples_leaf=leaf,
                            class_weight="balanced_subsample",
                            n_jobs=-1,
                            random_state=seed,
                        ),
                    ),
                ]
            )
            for depth in (4, 7, None)
            for leaf in (10, 25)
        ],
    }
    if XGBClassifier is not None:
        models["xgboost"] = [
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    (
                        "model",
                        XGBClassifier(
                            n_estimators=estimators,
                            max_depth=depth,
                            learning_rate=rate,
                            subsample=0.85,
                            colsample_bytree=0.85,
                            eval_metric="logloss",
                            random_state=seed,
                            n_jobs=-1,
                        ),
                    ),
                ]
            )
            for estimators in (150, 300)
            for depth in (2, 3)
            for rate in (0.03, 0.08)
        ]
    return models


def _predict_proba(estimator: object, x: pd.DataFrame) -> np.ndarray:
    if hasattr(estimator, "predict_proba"):
        return estimator.predict_proba(x)[:, 1]
    return np.asarray(estimator.predict(x), dtype=float)


def _baseline_probabilities(df: pd.DataFrame, name: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if name == "random":
        return rng.random(len(df))
    if name == "buy_and_hold":
        return np.ones(len(df))
    if name == "sma_crossover":
        return np.where(df["sma_20_50_cross"] > 0, 0.60, 0.40)
    if name == "ema_crossover":
        return np.where(df["ema_12_26_cross"] > 0, 0.60, 0.40)
    if name == "rsi_mean_reversion":
        return np.select([df["rsi_14d"] < 30, df["rsi_14d"] > 70], [0.65, 0.35], default=0.50)
    if name == "macd_trend":
        return np.where(df["macd_histogram"] > 0, 0.60, 0.40)
    if name == "bollinger_mean_reversion":
        return np.select([df["bollinger_position_20d"] < 0.2, df["bollinger_position_20d"] > 0.8], [0.65, 0.35], default=0.50)
    raise ValueError(f"Unknown baseline: {name}")


BASELINES = (
    "random",
    "buy_and_hold",
    "sma_crossover",
    "ema_crossover",
    "rsi_mean_reversion",
    "macd_trend",
    "bollinger_mean_reversion",
)


def train_models(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    labeled = load_labeled_dataset(config)
    metrics: list[dict] = []
    predictions: list[pd.DataFrame] = []

    for horizon in config.horizons:
        data, columns, label = horizon_dataset(labeled, horizon, config)
        split = chronological_split(data, config)
        train = split["train"].dropna(subset=columns, how="all")
        validation = split["validation"].dropna(subset=columns, how="all")
        test = split["test"].dropna(subset=columns, how="all")

        for baseline in BASELINES:
            for split_name, split_df in (("validation", validation), ("test", test)):
                probs = _baseline_probabilities(split_df, baseline, config.seed + horizon)
                row = classification_metrics(split_df[label], probs)
                row.update({"horizon": horizon, "model": baseline, "split": split_name, "kind": "baseline"})
                metrics.append(row)
                predictions.append(_prediction_frame(split_df, horizon, baseline, split_name, probs, label))

        x_train, y_train = train[columns], train[label].astype(int)
        x_validation, y_validation = validation[columns], validation[label].astype(int)
        x_test, y_test = test[columns], test[label].astype(int)

        for model_name, candidates in _model_grid(config.seed).items():
            best = None
            best_metrics = None
            best_score = -np.inf
            for candidate in candidates:
                candidate.fit(x_train, y_train)
                probs = _predict_proba(candidate, x_validation)
                candidate_metrics = classification_metrics(y_validation, probs)
                score = candidate_metrics["roc_auc"]
                if np.isnan(score):
                    score = candidate_metrics["f1"]
                if score > best_score:
                    best = candidate
                    best_metrics = candidate_metrics
                    best_score = score

            assert best is not None and best_metrics is not None
            model_path = config.model_dir / f"{horizon}d" / f"{model_name}.joblib"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump({"estimator": best, "features": columns, "horizon": horizon, "model": model_name}, model_path)

            validation_probs = _predict_proba(best, x_validation)
            test_probs = _predict_proba(best, x_test)
            for split_name, split_df, y, probs in (
                ("validation", validation, y_validation, validation_probs),
                ("test", test, y_test, test_probs),
            ):
                row = classification_metrics(y, probs)
                row.update({"horizon": horizon, "model": model_name, "split": split_name, "kind": "ml"})
                metrics.append(row)
                predictions.append(_prediction_frame(split_df, horizon, model_name, split_name, probs, label))

    metrics_df = pd.DataFrame(metrics).sort_values(["horizon", "model", "split"]).reset_index(drop=True)
    predictions_df = pd.concat(predictions).sort_values(["horizon", "model", "split", "ticker", "date"])
    write_frame(metrics_df, config.metrics_dir / "classification_metrics.csv")
    write_frame(predictions_df, config.metrics_dir / "predictions.csv")
    return metrics_df


def _prediction_frame(df: pd.DataFrame, horizon: int, model: str, split: str, probabilities: np.ndarray, label: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": df["date"].to_numpy(),
            "ticker": df["ticker"].to_numpy(),
            "horizon": horizon,
            "model": model,
            "split": split,
            "probability": probabilities,
            "label": df[label].astype(int).to_numpy(),
            "future_return": df[f"future_return_{horizon}d"].to_numpy(),
            "return_1d": df["return_1d"].to_numpy(),
        }
    )


def load_predictions(config: ResearchConfig = CONFIG) -> pd.DataFrame:
    path = config.metrics_dir / "predictions.csv"
    if not path.exists():
        train_models(config)
    return read_frame(path, parse_dates=["date"])
