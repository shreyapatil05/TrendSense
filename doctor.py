#!/usr/bin/env python3
"""Check whether TrendSense is ready for collection, training, and inference."""
import importlib
import os
import sys

from config import (
    FORECAST_HORIZONS_DAYS, HISTORICAL_DIR, MODEL_DIR, NEWS_API_KEY,
    SEMANTIC_MODEL_NAME, YOUTUBE_API_KEY,
)


def status(label, ok, detail=""):
    marker = "OK" if ok else "MISSING"
    print(f"{label:<34} {marker:<8} {detail}")


def main():
    print("TrendSense environment check")
    status("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0])
    for module in (
        "requests", "feedparser", "pytrends", "dotenv", "pandas", "numpy",
        "sklearn", "joblib", "sentence_transformers", "torch",
    ):
        try:
            imported = importlib.import_module(module)
            status(module, True, getattr(imported, "__version__", "installed"))
        except Exception:
            status(module, False, "run pip install -r requirements.txt")
    status("YOUTUBE_API_KEY", bool(YOUTUBE_API_KEY), "optional but recommended")
    status("NEWS_API_KEY", bool(NEWS_API_KEY), "optional but recommended")
    history = os.path.join(HISTORICAL_DIR, "google_trends_daily.csv")
    status("Historical dataset", os.path.exists(history), history)
    for horizon in FORECAST_HORIZONS_DAYS:
        model = os.path.join(MODEL_DIR, f"trend_direction_h{horizon}.joblib")
        status(f"{horizon}-day ML model", os.path.exists(model), model)
    print(f"Semantic model: {SEMANTIC_MODEL_NAME}")
    print("READY requires the historical dataset, both model files, and installed semantic dependencies.")


if __name__ == "__main__":
    from cli_v4 import main as configured_main
    configured_main("doctor")
