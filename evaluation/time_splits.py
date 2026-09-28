"""Date-grouped splits: future targets must precede validation origins."""
import numpy as np
from sklearn.model_selection import TimeSeriesSplit


def expanding_splits(frame, n_splits):
    dates = np.array(sorted(frame.date.unique()))
    count = min(n_splits, len(dates) - 1)
    if count < 2:
        return []
    splits = []
    for earlier, later in TimeSeriesSplit(n_splits=count).split(dates):
        valid = frame.date.isin(dates[later])
        train = frame.date.isin(dates[earlier]) & (frame.target_date < dates[later][0])
        if train.any() and valid.any():
            splits.append((np.flatnonzero(train), np.flatnonzero(valid)))
    return splits


def holdout(frame, end, test_days):
    import pandas as pd
    start = end - pd.Timedelta(days=test_days - 1)
    train = frame[(frame.date < start) & (frame.target_date < start)].copy()
    test = frame[(frame.date >= start) & (frame.target_date <= end)].copy()
    return train.reset_index(drop=True), test.reset_index(drop=True), start
