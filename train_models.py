#!/usr/bin/env python3
"""Build features, train both horizon models, and print temporal metrics."""
import argparse
import json
import os

from agents.ml_forecasting_agent import train_forecasting_model
from config import FORECAST_HORIZONS_DAYS, HISTORICAL_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", default=os.path.join(HISTORICAL_DIR, "google_trends_daily.csv"))
    parser.add_argument("--horizon", type=int, choices=FORECAST_HORIZONS_DAYS)
    args = parser.parse_args()
    horizons = [args.horizon] if args.horizon else list(FORECAST_HORIZONS_DAYS)
    for horizon in horizons:
        bundle, feature_path, report_path = train_forecasting_model(args.history, horizon)
        metrics = bundle["evaluation"]
        print(f"\nHorizon: {horizon} day(s)")
        print(f"Training rows: {bundle['training_rows']}")
        print(f"Feature dataset: {feature_path}")
        print(f"Evaluation report: {report_path}")
        print(json.dumps({
            "TrendSense_ML": metrics["trend_sense_ml"],
            "Baselines": metrics["baselines"],
        }, indent=2))


if __name__ == "__main__":
    from cli_v4 import main as configured_main
    configured_main("train")
