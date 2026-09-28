#!/usr/bin/env python3
"""Print metrics from stored mature forecast/outcome pairs."""
import json
import os
from datetime import datetime, timezone

from config import EVALUATION_DIR, FORECAST_DIR, SYSTEM_VERSION
from evaluation.backtest import evaluate_pairs, write_experiment
from storage.forecasts import read_jsonl


def main():
    forecasts = {x["forecast_id"]: x for x in read_jsonl(os.path.join(FORECAST_DIR, "forecasts.jsonl"))}
    outcomes = read_jsonl(os.path.join(FORECAST_DIR, "outcomes.jsonl"))
    pairs = [{**forecasts[x["forecast_id"]], **x} for x in outcomes if x["forecast_id"] in forecasts and x.get("evaluation_status") == "EVALUABLE"]
    if not pairs:
        print("No mature evaluable forecast/outcome pairs found.")
        print("Run main.py on different days, then run record_outcomes.py.")
        return
    report = {
        "overall": evaluate_pairs(pairs),
        "by_horizon": {
            str(horizon): evaluate_pairs(
                [pair for pair in pairs if int(pair["forecast_horizon_days"]) == horizon]
            )
            for horizon in sorted({int(pair["forecast_horizon_days"]) for pair in pairs})
        },
        "uncertain_or_unmatched_outcomes": len(outcomes) - len(pairs),
    }
    os.makedirs(EVALUATION_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(EVALUATION_DIR, f"evaluation_{stamp}.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    experiment = {
        "experiment_id": f"evaluation-{stamp}", "dataset_version": "observations-jsonl-v1",
        "date": datetime.now(timezone.utc).isoformat(), "forecast_horizon": "mixed",
        "features": "stored live ML forecast probabilities", "configuration": "stored forecast snapshots",
        "system_version": SYSTEM_VERSION, "model": "Random Forest direction classifier",
        "metrics": report, "notes": "Only mature, non-uncertain outcomes included."
    }
    write_experiment(os.path.join(EVALUATION_DIR, f"experiment_{stamp}.json"), experiment)
    print(json.dumps(report, indent=2))
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    from cli_v4 import main as configured_main
    configured_main("evaluate")
