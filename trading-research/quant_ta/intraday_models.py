from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from quant_ta.evaluation import classification_metrics
from quant_ta.intraday_config import INTRADAY_CONFIG, IntradayConfig
from quant_ta.intraday_labels import load_intraday_labeled_dataset
from quant_ta.io import read_frame, write_frame

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover
    XGBClassifier = None


def intraday_feature_columns(df: pd.DataFrame, horizons: tuple[int, ...]) -> list[str]:
    excluded = {"date", "ticker", "open", "high", "low", "close", "adj_close", "volume"}
    for horizon in horizons:
        excluded.add(f"future_return_{horizon}m")
        excluded.add(f"label_{horizon}m")
    numeric = df.select_dtypes(include=["number", "bool"]).columns
    return [column for column in numeric if column not in excluded]


def split_intraday(df: pd.DataFrame, config: IntradayConfig = INTRADAY_CONFIG) -> dict[str, pd.DataFrame]:
    test_start = pd.Timestamp(config.test_start)
    test_end = pd.Timestamp(config.test_end) + pd.Timedelta(days=1)
    if df["date"].min() < test_start and df["date"].max() >= test_start:
        pretest = df[df["date"] < test_start].copy()
        test = df[(df["date"] >= test_start) & (df["date"] < test_end)].copy()
        if not pretest.empty and not test.empty:
            validation_start = pretest["date"].quantile(0.80)
            return {
                "train": pretest[pretest["date"] < validation_start].copy(),
                "validation": pretest[pretest["date"] >= validation_start].copy(),
                "test": test,
            }

    dates = np.array(sorted(df["date"].unique()))
    train_end = dates[int(len(dates) * 0.60)]
    validation_end = dates[int(len(dates) * 0.80)]
    return {
        "train": df[df["date"] <= train_end].copy(),
        "validation": df[(df["date"] > train_end) & (df["date"] <= validation_end)].copy(),
        "test": df[df["date"] > validation_end].copy(),
    }


def _model_candidates(seed: int) -> dict[str, object]:
    models: dict[str, object] = {
        "logistic_regression": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", random_state=seed)),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=120,
                        max_depth=6,
                        min_samples_leaf=20,
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=seed,
                    ),
                ),
            ]
        ),
    }
    if XGBClassifier is not None:
        models["xgboost"] = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    XGBClassifier(
                        n_estimators=120,
                        max_depth=2,
                        learning_rate=0.05,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        eval_metric="logloss",
                        random_state=seed,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
    return models


def _predict_proba(estimator: object, x: pd.DataFrame) -> np.ndarray:
    return estimator.predict_proba(x)[:, 1]


def _baseline_probability(df: pd.DataFrame, name: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if name == "random":
        return rng.random(len(df))
    if name == "buy_and_hold":
        return np.ones(len(df))
    if name == "ema_vwap_trend":
        return np.where((df["ema_9_21_cross"] > 0) & (df["price_to_vwap"] > 0), 0.60, 0.40)
    if name == "rsi_scalp_reversal":
        return np.select([df["rsi_14m"] < 30, df["rsi_14m"] > 70], [0.63, 0.37], default=0.50)
    if name == "breakout_20m":
        return np.select([df["breakout_20m"] == 1, df["breakdown_20m"] == 1], [0.64, 0.36], default=0.50)
    if name == "candlestick_patterns":
        bullish = (df["hammer"] == 1) | (df["bullish_engulfing"] == 1)
        bearish = (df["shooting_star"] == 1) | (df["bearish_engulfing"] == 1)
        return np.select([bullish, bearish], [0.62, 0.38], default=0.50)
    raise ValueError(name)


BASELINES = ("random", "buy_and_hold", "ema_vwap_trend", "rsi_scalp_reversal", "breakout_20m", "candlestick_patterns")


def _prediction_frame(df: pd.DataFrame, horizon: int, model: str, split: str, probs: np.ndarray, label: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": df["date"].to_numpy(),
            "ticker": df["ticker"].to_numpy(),
            "horizon": horizon,
            "model": model,
            "split": split,
            "probability": probs,
            "label": df[label].astype(int).to_numpy(),
            "future_return": df[f"future_return_{horizon}m"].to_numpy(),
            "minute_return": df["minute_return"].to_numpy(),
        }
    )


def train_intraday_models(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    labeled = load_intraday_labeled_dataset(config)
    rows = []
    prediction_frames = []

    for horizon in config.horizons:
        label = f"label_{horizon}m"
        data = labeled[labeled[label].notna()].copy()
        features = intraday_feature_columns(data, config.horizons)
        data[features] = data[features].replace([np.inf, -np.inf], np.nan)
        split = split_intraday(data, config)

        for baseline in BASELINES:
            for split_name in ("validation", "test"):
                split_df = split[split_name].dropna(subset=features, how="all")
                probs = _baseline_probability(split_df, baseline, config.seed + horizon)
                row = classification_metrics(split_df[label], probs)
                row.update({"horizon": horizon, "model": baseline, "split": split_name, "kind": "baseline"})
                rows.append(row)
                prediction_frames.append(_prediction_frame(split_df, horizon, baseline, split_name, probs, label))

        x_train = split["train"].dropna(subset=features, how="all")
        x_val = split["validation"].dropna(subset=features, how="all")
        x_test = split["test"].dropna(subset=features, how="all")
        for model_name, estimator in _model_candidates(config.seed).items():
            estimator.fit(x_train[features], x_train[label].astype(int))
            model_path = config.model_dir / f"{horizon}m" / f"{model_name}.joblib"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump({"estimator": estimator, "features": features, "horizon": horizon, "model": model_name}, model_path)
            for split_name, split_df in (("validation", x_val), ("test", x_test)):
                probs = _predict_proba(estimator, split_df[features])
                row = classification_metrics(split_df[label], probs)
                row.update({"horizon": horizon, "model": model_name, "split": split_name, "kind": "ml"})
                rows.append(row)
                prediction_frames.append(_prediction_frame(split_df, horizon, model_name, split_name, probs, label))

    metrics = pd.DataFrame(rows).sort_values(["horizon", "model", "split"]).reset_index(drop=True)
    predictions = pd.concat(prediction_frames, ignore_index=True).sort_values(["horizon", "model", "split", "ticker", "date"])
    write_frame(metrics, config.metrics_dir / "classification_metrics.csv")
    write_frame(predictions, config.metrics_dir / "predictions.csv")
    return metrics


def load_intraday_predictions(config: IntradayConfig = INTRADAY_CONFIG) -> pd.DataFrame:
    path = config.metrics_dir / "predictions.csv"
    if not path.exists():
        train_intraday_models(config)
    return read_frame(path, parse_dates=["date"])
