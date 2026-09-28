"""V4 immutable forecasts and exact-target verification, isolated from legacy logs."""
import json
import uuid
import numpy as np
import pandas as pd
from adaptive_thresholds import direction
from runtime_config import paths, save_json
from evaluation.metrics import classification_metrics, regression_metrics
from adaptive_thresholds import LABELS


def read_records(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def append_records(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, allow_nan=False) + "\n")


def persist(cfg, results):
    p = paths(cfg)
    created = pd.Timestamp.now(tz="UTC")
    rows = []
    for result in results:
        if result.get("ml_forecast_status") != "READY" or result.get("target_already_observed"):
            continue
        row = {k: v for k, v in result.items() if k not in {"raw_evidence", "reference_overlap"}}
        row.update({"forecast_id": uuid.uuid4().hex, "created_at": created.isoformat(),
                    "reference_overlap": result["reference_overlap"], "experiment_id": p["experiment_id"],
                    "threshold_settings": cfg["thresholds"], "system_version": "4.0.0"})
        rows.append(row)
    append_records(p["run"] / "forecasts.jsonl", rows)
    return len(rows)


def record(cfg):
    p = paths(cfg)
    if not p["history"].exists():
        raise ValueError("Refresh the selected history before recording outcomes")
    history = pd.read_csv(p["history"])
    history["date"] = pd.to_datetime(history.date, utc=True, format="mixed").dt.normalize()
    now = pd.Timestamp.now(tz="UTC")
    done = {x["forecast_id"] for x in read_records(p["run"] / "outcomes.jsonl")}
    result, skipped = [], []
    for forecast in read_records(p["run"] / "forecasts.jsonl"):
        if forecast["forecast_id"] in done:
            continue
        target = pd.Timestamp(forecast["target_date"])
        check_time = pd.Timestamp(forecast["created_at"]) + pd.Timedelta(days=cfg["forecast"]["verification_delay_days"])
        if now < max(target + pd.Timedelta(days=1), check_time):
            skipped.append({"forecast_id": forecast["forecast_id"], "reason": "PENDING_TARGET_OR_CHECK_TIME"})
            continue
        series = history[history.keyword == forecast["keyword"]]
        observation = series[series.date == target]
        reason = None
        if len(observation) != 1 or not np.isfinite(observation.interest.iloc[0]):
            reason = "EXACT_TARGET_OBSERVATION_UNAVAILABLE"
        elif str(observation.batch_signature.iloc[0]) != forecast["batch_signature"]:
            reason = "INCOMPATIBLE_NORMALIZATION_BATCH"
        if reason:
            skipped.append({"forecast_id": forecast["forecast_id"], "reason": reason})
            continue
        same_snapshot = str(observation.snapshot_id.iloc[0]) == forecast["snapshot_id"]
        ratio, alignment_error = 1.0, 0.0
        status = "EXACT_SNAPSHOT"
        if not same_snapshot:
            reference = pd.DataFrame(forecast["reference_overlap"])
            reference["date"] = pd.to_datetime(reference.date, utc=True)
            overlap = reference.merge(series[["date", "interest"]], on="date", suffixes=("_old", "_new"))
            overlap = overlap[(overlap.interest_old > 0) & (overlap.interest_new > 0)]
            if not cfg["evaluation"]["allow_approximate_rebasing"] or len(overlap) < cfg["evaluation"]["minimum_overlap_points"]:
                skipped.append({"forecast_id": forecast["forecast_id"], "reason": "REBASE_DISABLED_OR_INSUFFICIENT_POSITIVE_OVERLAP"})
                continue
            ratio = float(np.median(overlap.interest_new / overlap.interest_old))
            alignment_error = float(np.mean(np.abs(overlap.interest_new / ratio - overlap.interest_old)))
            status = "APPROXIMATE_REBASED"
        actual = float(observation.interest.iloc[0]) / ratio
        delta = actual - forecast["ml_current_interest"]
        label = direction(delta, forecast["threshold"])
        result.append({"forecast_id": forecast["forecast_id"], "keyword": forecast["keyword"],
             "target_date": forecast["target_date"], "recorded_at": now.isoformat(),
             "horizon_days": forecast["ml_horizon_days"], "actual_interest": actual,
             "predicted_interest": forecast["predicted_interest"], "current_interest": forecast["ml_current_interest"],
             "actual_direction": label, "predicted_direction": forecast["ml_predicted_direction"],
             "direction_match": label == forecast["ml_predicted_direction"],
             "actual_change": delta, "actual_growth_percent": 100*delta/forecast["ml_current_interest"] if forecast["ml_current_interest"] > 0 else None,
             "absolute_error": abs(actual - forecast["predicted_interest"]),
             "measurement_status": status, "rebase_factor": ratio, "overlap_alignment_mae": alignment_error,
             "warning": "Rebasing is approximate; Google sampling/revisions may affect outcomes" if not same_snapshot else None})
    append_records(p["run"] / "outcomes.jsonl", result)
    save_json(p["run"] / "outcome_pending.json", skipped)
    return {"recorded": len(result), "pending_or_incomparable": len(skipped)}


def evaluate(cfg, plots=False):
    p = paths(cfg)
    records = read_records(p["run"] / "outcomes.jsonl")
    def summary(rows):
        if not rows:
            return {"evaluated": 0, "message": "No verified outcomes yet"}
        return {"evaluated": len(rows), "direction": classification_metrics([r["actual_direction"] for r in rows], [r["predicted_direction"] for r in rows], LABELS),
                "regression": regression_metrics([r["actual_interest"] for r in rows], [r["predicted_interest"] for r in rows]),
                "naive_direction": classification_metrics([r["actual_direction"] for r in rows], ["STABLE"] * len(rows), LABELS),
                "naive_regression": regression_metrics([r["actual_interest"] for r in rows], [r["current_interest"] for r in rows])}
    report = {"experiment_id": p["experiment_id"], "overall": summary(records),
              "by_measurement_status": {s: summary([r for r in records if r["measurement_status"] == s]) for s in sorted({r["measurement_status"] for r in records})},
              "by_horizon": {str(h): summary([r for r in records if r["horizon_days"] == h]) for h in sorted({r["horizon_days"] for r in records})},
              "pending": read_records(p["run"] / "forecasts.jsonl").__len__() - len(records),
              "warning": "Legacy outcomes are excluded. Rebased outcomes are approximate and separately labeled."}
    save_json(p["run"] / "live_evaluation.json", report)
    if plots:
        from evaluation.plots import plot_live
        plot_live(records, p["run"] / "plots")
    return report
