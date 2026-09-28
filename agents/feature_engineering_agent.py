"""Leakage-safe time-series features for training and live inference."""
import math
import os

from config import GROUND_TRUTH_TOLERANCE, HISTORICAL_DIR

NUMERIC_FEATURES = [
    "current_interest", "change_1", "change_ratio_1", "ma_3", "ma_7", "ma_14",
    "ma_gap_3_14", "velocity_3", "acceleration", "volatility_7",
    "peak_distance_30", "day_sin", "day_cos", "industry_beauty",
]

# Configured v4 uses exact daily calendars and causal adaptive labels.
# This re-export keeps feature engineering discoverable in the original module.
from agents.window_features import build_window as build_configured_window


def _engineer_group(group):
    group = group.sort_values("date").copy()
    interest = group["interest"].astype(float)
    group["current_interest"] = interest
    group["change_1"] = interest.diff()
    group["change_ratio_1"] = interest.diff() / (interest.shift(1).abs() + 1.0)
    group["ma_3"] = interest.rolling(3, min_periods=3).mean()
    group["ma_7"] = interest.rolling(7, min_periods=7).mean()
    group["ma_14"] = interest.rolling(14, min_periods=14).mean()
    group["ma_gap_3_14"] = group["ma_3"] - group["ma_14"]
    group["velocity_3"] = (interest - interest.shift(3)) / 3.0
    group["acceleration"] = group["change_1"] - group["change_1"].shift(1)
    group["volatility_7"] = interest.rolling(7, min_periods=7).std()
    group["peak_distance_30"] = interest - interest.rolling(30, min_periods=14).max()
    weekday = group["date"].dt.dayofweek
    group["day_sin"] = weekday.map(lambda x: math.sin(2 * math.pi * x / 7))
    group["day_cos"] = weekday.map(lambda x: math.cos(2 * math.pi * x / 7))
    group["industry_beauty"] = (group["industry"].str.lower() == "beauty").astype(int)
    return group


def engineer_history(history_csv):
    import pandas as pd
    frame = pd.read_csv(history_csv)
    required = {"date", "keyword", "industry", "interest"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Historical dataset missing columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    date_steps = (
        frame.sort_values(["keyword", "date"])
        .groupby("keyword")["date"].diff().dt.total_seconds().dropna() / 86400.0
    )
    if not date_steps.empty and float(date_steps.median()) > 2.0:
        raise ValueError(
            "Historical data is not daily. Use collect_historical.py with "
            "--timeframe \"today 3-m\" for 1-day and 3-day forecasts."
        )
    engineered = pd.concat(
    [_engineer_group(group) for _, group in frame.groupby("keyword")],
    ignore_index=True,
)
    return engineered.reset_index(drop=True)


def build_training_dataset(history_csv, horizon_days, tolerance=GROUND_TRUTH_TOLERANCE):
    frame = engineer_history(history_csv)
    grouped = frame.groupby("keyword", group_keys=False)
    frame["future_interest"] = grouped["interest"].shift(-horizon_days)
    frame["future_change"] = frame["future_interest"] - frame["current_interest"]
    frame["target_direction"] = "STABLE"
    frame.loc[frame["future_change"] > tolerance, "target_direction"] = "UP"
    frame.loc[frame["future_change"] < -tolerance, "target_direction"] = "DOWN"
    frame["horizon_days"] = int(horizon_days)
    frame = frame.dropna(subset=NUMERIC_FEATURES + ["future_interest"])
    output = os.path.join(HISTORICAL_DIR, f"features_h{horizon_days}.csv")
    frame.to_csv(output, index=False)
    return frame, output


def build_live_features(results, history_csv):
    import pandas as pd
    historical = pd.read_csv(history_csv)
    historical["date"] = pd.to_datetime(historical["date"], utc=True)
    engineered = pd.concat(
    [_engineer_group(group) for _, group in historical.groupby("keyword")],
    ignore_index=True,
)
    requested = {item.get("keyword") for item in results}
    engineered = engineered[engineered["keyword"].isin(requested)]
    live = engineered.sort_values("date").groupby("keyword", as_index=False).tail(1)
    return live.dropna(subset=NUMERIC_FEATURES)
