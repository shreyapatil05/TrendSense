"""Supervised short-horizon direction forecasting and temporal evaluation."""
import json
import os
from datetime import datetime, timezone

from config import EVALUATION_DIR, HISTORICAL_DIR, MODEL_DIR, SYSTEM_VERSION
from agents.feature_engineering_agent import (
    NUMERIC_FEATURES, build_live_features, build_training_dataset,
)
from evaluation.metrics import classification_metrics

LABELS = ["UP", "STABLE", "DOWN"]


def train_configured_model(run_config):
    from forecast_experiment import train_experiment
    return train_experiment(run_config)


def run_configured_forecast(run_config):
    from forecast_experiment import infer
    return infer(run_config)


def _model_path(horizon_days):
    return os.path.join(MODEL_DIR, f"trend_direction_h{horizon_days}.joblib")


def _predict_proba_complete(model, features):
    import numpy as np
    raw = model.predict_proba(features)
    result = np.zeros((len(features), len(LABELS)), dtype=float)
    for source_index, label in enumerate(model.classes_):
        result[:, LABELS.index(label)] = raw[:, source_index]
    return result


def _baseline_predictions(test):
    persistence = ["STABLE"] * len(test)
    momentum = test["change_1"].map(lambda x: "UP" if x > 0 else "DOWN" if x < 0 else "STABLE").tolist()
    moving_average = test["ma_gap_3_14"].map(
        lambda x: "UP" if x > 1.0 else "DOWN" if x < -1.0 else "STABLE"
    ).tolist()
    return {"persistence": persistence, "momentum": momentum, "moving_average": moving_average}


def train_forecasting_model(history_csv, horizon_days, random_state=42):
    try:
        import joblib
        from sklearn.ensemble import RandomForestClassifier
    except ImportError as exc:
        raise RuntimeError("scikit-learn and joblib are required. Install requirements.txt") from exc

    frame, feature_path = build_training_dataset(history_csv, horizon_days)
    dates = sorted(frame["date"].dt.normalize().unique())
    if len(dates) < 30 or len(frame) < 200:
        raise RuntimeError("At least 30 dates and 200 feature rows are required")

    fold_metrics = []
    all_actual, all_predicted = [], []
    baseline_actual = []
    baseline_predictions = {name: [] for name in ("persistence", "momentum", "moving_average")}
    cutoffs = [0.60, 0.70, 0.80]

    for fold, fraction in enumerate(cutoffs, 1):
        train_end = max(1, int(len(dates) * fraction))
        test_end = min(len(dates), train_end + max(1, int(len(dates) * 0.10)))
        train_dates = set(dates[:train_end])
        test_dates = set(dates[train_end:test_end])
        train = frame[frame["date"].dt.normalize().isin(train_dates)]
        test = frame[frame["date"].dt.normalize().isin(test_dates)]
        if train.empty or test.empty or train["target_direction"].nunique() < 2:
            continue
        model = RandomForestClassifier(
            n_estimators=300, min_samples_leaf=3, class_weight="balanced_subsample",
            random_state=random_state, n_jobs=-1,
        )
        model.fit(train[NUMERIC_FEATURES], train["target_direction"])
        predicted = model.predict(test[NUMERIC_FEATURES]).tolist()
        actual = test["target_direction"].tolist()
        metrics = classification_metrics(actual, predicted, LABELS)
        fold_metrics.append({"fold": fold, "train_end": str(max(train_dates)),
                             "test_start": str(min(test_dates)), "test_end": str(max(test_dates)),
                             "rows": len(test), "metrics": metrics})
        all_actual.extend(actual)
        all_predicted.extend(predicted)
        baseline_actual.extend(actual)
        for name, values in _baseline_predictions(test).items():
            baseline_predictions[name].extend(values)

    if not all_actual:
        raise RuntimeError("Temporal folds could not be created from the dataset")

    evaluation = {
        "horizon_days": horizon_days,
        "method": "expanding_window_walk_forward",
        "trend_sense_ml": classification_metrics(all_actual, all_predicted, LABELS),
        "baselines": {
            name: classification_metrics(baseline_actual, values, LABELS)
            for name, values in baseline_predictions.items()
        },
        "folds": fold_metrics,
        "evaluated_rows": len(all_actual),
    }

    final_model = RandomForestClassifier(
        n_estimators=500, min_samples_leaf=3, class_weight="balanced_subsample",
        random_state=random_state, n_jobs=-1,
    )
    final_model.fit(frame[NUMERIC_FEATURES], frame["target_direction"])
    importance = sorted(
        [{"feature": name, "importance": float(value)}
         for name, value in zip(NUMERIC_FEATURES, final_model.feature_importances_)],
        key=lambda x: x["importance"], reverse=True,
    )
    bundle = {
        "model": final_model, "feature_columns": NUMERIC_FEATURES,
        "horizon_days": horizon_days, "system_version": SYSTEM_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": len(frame), "date_min": frame["date"].min().isoformat(),
        "date_max": frame["date"].max().isoformat(), "feature_importance": importance,
        "evaluation": evaluation,
    }
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(bundle, _model_path(horizon_days))
    os.makedirs(EVALUATION_DIR, exist_ok=True)
    report_path = os.path.join(EVALUATION_DIR, f"historical_ml_h{horizon_days}.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump({k: v for k, v in bundle.items() if k != "model"}, handle, indent=2)
    return bundle, feature_path, report_path


def run_ml_forecasting_analysis(results, horizon_days, history_csv=None):
    history_csv = history_csv or os.path.join(HISTORICAL_DIR, "google_trends_daily.csv")
    model_path = _model_path(horizon_days)
    if not os.path.exists(history_csv) or not os.path.exists(model_path):
        reason = "Run collect_historical.py and train_models.py before ML inference"
        return [{"keyword": x.get("keyword"), "ml_forecast_status": "UNAVAILABLE",
                 "ml_forecast_warning": reason} for x in results]
    import joblib
    bundle = joblib.load(model_path)
    live = build_live_features(results, history_csv)
    if live.empty:
        return [{"keyword": x.get("keyword"), "ml_forecast_status": "UNAVAILABLE",
                 "ml_forecast_warning": "No live feature rows could be built"} for x in results]
    probabilities = _predict_proba_complete(bundle["model"], live[NUMERIC_FEATURES])
    by_keyword = {}
    for row_index, (_, row) in enumerate(live.iterrows()):
        values = {label: round(float(probabilities[row_index, index]), 4)
                  for index, label in enumerate(LABELS)}
        predicted = max(values, key=values.get)
        by_keyword[row["keyword"]] = {
            "keyword": row["keyword"], "ml_forecast_status": "READY",
            "ml_predicted_direction": predicted,
            "ml_probabilities": values,
            "ml_confidence": values[predicted],
            "ml_horizon_days": horizon_days,
            "ml_model_version": bundle["trained_at"],
            "ml_current_interest": round(float(row["current_interest"]), 3),
            "ml_top_features": bundle["feature_importance"][:5],
            "ml_forecast_method": "random_forest_classifier",
        }
    return [by_keyword.get(x.get("keyword"), {
        "keyword": x.get("keyword"), "ml_forecast_status": "UNAVAILABLE",
        "ml_forecast_warning": "Keyword lacked sufficient feature history",
    }) for x in results]
