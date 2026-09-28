"""Evaluate immutable forecast/outcome pairs without temporal leakage."""
import json
from evaluation.metrics import classification_metrics, regression_metrics

def evaluate_pairs(pairs):
    eligible = [p for p in pairs if p.get("actual_direction") and p.get("predicted_direction")]
    directions = classification_metrics(
        [p["actual_direction"] for p in eligible],
        [p["predicted_direction"] for p in eligible], ["UP", "STABLE", "DOWN"])
    numeric = [p for p in eligible if p.get("actual_strength") is not None and p.get("predicted_strength") is not None]
    strength = regression_metrics([p["actual_strength"] for p in numeric], [p["predicted_strength"] for p in numeric])
    return {"evaluated_forecasts": len(eligible), "direction": directions, "strength": strength}

def write_experiment(path, experiment):
    required = {"experiment_id", "dataset_version", "date", "forecast_horizon", "features",
                "configuration", "system_version", "model", "metrics", "notes"}
    missing = required - set(experiment)
    if missing: raise ValueError(f"Missing experiment fields: {sorted(missing)}")
    with open(path, "w", encoding="utf-8") as handle: json.dump(experiment, handle, indent=2)
