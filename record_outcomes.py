#!/usr/bin/env python3
"""Attach later observations to mature forecasts without changing predictions."""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone

from config import FORECAST_DIR, GROUND_TRUTH_TOLERANCE, PROCESSED_DIR
from storage.forecasts import append_outcomes, read_jsonl
from evaluation.ground_truth import direction


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_results(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def latest_results_path():
    if not os.path.isdir(PROCESSED_DIR):
        return None
    files = sorted(
        name for name in os.listdir(PROCESSED_DIR)
        if name.startswith("final_results_") and name.endswith(".json")
    )
    return os.path.join(PROCESSED_DIR, files[-1]) if files else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", help="Later final_results JSON; defaults to newest file")
    parser.add_argument("--as-of", help="ISO timestamp for reproducible tests; default is now UTC")
    args = parser.parse_args()
    now = parse_time(args.as_of) if args.as_of else datetime.now(timezone.utc)
    forecasts = read_jsonl(os.path.join(FORECAST_DIR, "forecasts.jsonl"))
    recorded = {x["forecast_id"] for x in read_jsonl(os.path.join(FORECAST_DIR, "outcomes.jsonl"))}
    results_path = args.results or latest_results_path()
    if not results_path:
        raise RuntimeError("No final results file found. Run main.py first.")
    actual_by_keyword = {x.get("keyword"): x for x in load_results(results_path)}
    outcomes = []

    for forecast in forecasts:
        mature_at = parse_time(forecast["forecast_timestamp"]) + timedelta(days=int(forecast["forecast_horizon_days"]))
        if forecast["forecast_id"] in recorded or now < mature_at:
            continue
        actual = actual_by_keyword.get(forecast["keyword"])
        if not actual:
            continue
        starting_interest = forecast.get("current_interest")
        actual_interest = actual.get("ml_current_interest")
        if starting_interest is None or actual_interest is None:
            actual_direction = "UNKNOWN"
        else:
            actual_direction = direction(
                float(starting_interest), float(actual_interest),
                tolerance=GROUND_TRUTH_TOLERANCE,
            )
        active_sources = sum(
            isinstance(v, (int, float)) and v > 0.05
            for v in (actual.get("source_scores") or {}).values()
        )
        if actual_direction == "UNKNOWN" or active_sources < 2:
            actual_outcome = "UNCERTAIN"
        elif actual_direction == "UP":
            actual_outcome = "STRENGTHENED"
        elif actual_direction == "DOWN":
            actual_outcome = "WEAKENED"
        else:
            actual_outcome = "UNCHANGED"
        outcomes.append({
            "forecast_id": forecast["forecast_id"],
            "outcome_timestamp": now.isoformat(),
            "actual_strength": actual_interest,
            "actual_lifecycle": actual.get("phase", "UNKNOWN"),
            "actual_direction": actual_direction,
            "actual_outcome": actual_outcome,
            "forecast_error": None,
            "evaluation_status": "EVALUABLE" if actual_outcome != "UNCERTAIN" and actual_direction != "UNKNOWN" else "UNCERTAIN",
            "sources_used_for_outcome": active_sources,
        })
    if outcomes:
        append_outcomes(outcomes)
    print(f"Results source: {results_path}")
    print(f"Recorded {len(outcomes)} mature outcomes.")
    if not outcomes:
        print("No unrecorded forecasts have reached their 1-day or 3-day horizon yet.")


if __name__ == "__main__":
    from cli_v4 import main as configured_main
    configured_main("record")
