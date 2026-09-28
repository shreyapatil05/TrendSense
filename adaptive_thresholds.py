"""Causal labels: threshold at t uses only changes already observed by t."""
import numpy as np
import pandas as pd

LABELS = ["UP", "STABLE", "DOWN"]


def robust_scale(values, method="mad", percentile=0.75):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return np.nan
    if method == "percentile":
        return float(np.quantile(np.abs(values), percentile))
    if method == "zscore":
        return float(np.std(values))
    iqr = float(np.quantile(values, .75) - np.quantile(values, .25))
    if method == "iqr":
        return iqr
    mad = float(np.median(np.abs(values - np.median(values))))
    return mad if mad > 0 else iqr


def rolling_band(interest, horizon, settings):
    changes = interest.diff(horizon)
    # Minimum observations is a numerical feasibility requirement, not a direction cutoff.
    required = min(settings["lookback_days"], max(3, horizon + 1))
    band = changes.rolling(settings["lookback_days"], min_periods=required).apply(
        lambda x: robust_scale(x, settings["method"], settings["percentile"]), raw=True)
    return band * settings["multiplier"]


def direction(delta, band):
    if band is None or not np.isfinite(band) or band <= 0:
        return "UNKNOWN"
    return "UP" if delta > band else "DOWN" if delta < -band else "STABLE"


def tune_policy(actual, probabilities):
    """Binary F1 cutoff from OOF predictions; no economic profitability claim."""
    from sklearn.metrics import f1_score
    result = {}
    actual = np.asarray(actual)
    for i, label in enumerate(LABELS):
        if label == "STABLE":
            continue
        positive = actual == label
        if not positive.any() or positive.all():
            result[label] = None
            continue
        candidates = np.unique(probabilities[:, i])
        ranked = [(float(f1_score(positive, probabilities[:, i] >= c, zero_division=0)), float(c))
                  for c in candidates]
        result[label] = max(ranked)[1]  # Prefer the stricter cutoff when F1 ties.
    return result
