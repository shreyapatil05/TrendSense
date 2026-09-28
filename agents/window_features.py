"""Calendar-aligned features shared by training and inference in v4."""
import numpy as np
import pandas as pd
from adaptive_thresholds import rolling_band, direction

FEATURES = ["interest", "lag1", "lag3", "lag7", "mean3", "mean7", "mean14", "std7",
            "change1", "change3", "gap3_14", "relative_change1", "relative_change3",
            "relative_trend7", "relative_gap3_14", "rolling_z7", "day_sin", "day_cos"]


def build_window(history_path, cfg):
    frame = pd.read_csv(history_path)
    selected = cfg["keywords"]["selected"]
    frame = frame[frame.keyword.isin(selected)].copy()
    if frame.empty:
        raise ValueError("No history for selected keywords; collect or import first")
    frame["date"] = pd.to_datetime(frame.date, utc=True, format="mixed").dt.normalize()
    frame["interest"] = pd.to_numeric(frame.interest, errors="coerce")
    if frame.duplicated(["keyword", "date"]).any():
        raise ValueError("Duplicate keyword/date rows: select a single snapshot")
    today = pd.Timestamp.now(tz="UTC").normalize()
    desired = cfg["window"]["end_date"]
    end = min(frame.date.max(), today - pd.Timedelta(days=1)) if desired == "latest_complete" else pd.to_datetime(desired, utc=True).normalize()
    if end >= today:
        raise ValueError("Window must end before today's incomplete observation")
    start = end - pd.Timedelta(days=cfg["window"]["analysis_days"] - 1)
    warmup = start - pd.Timedelta(days=cfg["window"]["feature_warmup_days"])
    h = cfg["forecast"]["horizon_days"]
    groups, coverage = [], {}
    for keyword in selected:
        original = frame[(frame.keyword == keyword) & (frame.date >= warmup) & (frame.date <= end)]
        g = original.set_index("date").reindex(pd.date_range(warmup, end, tz="UTC"))
        g.index.name = "date"
        x = g.interest
        g["keyword"] = keyword
        g["lag1"], g["lag3"], g["lag7"] = x.shift(1), x.shift(3), x.shift(7)
        # Most recent observation on the same weekday as the FUTURE target.
        g["seasonal_naive_interest"] = x.shift((-h) % 7)
        for n in (3, 7, 14):
            g[f"mean{n}"] = x.rolling(n).mean()
        g["std7"] = x.rolling(7).std()
        g["change1"], g["change3"] = x.diff(), x.diff(3)
        g["gap3_14"] = g.mean3 - g.mean14
        # Relative features are comparable across independently-normalized
        # Google Trends batches and across high/low-volume keywords.
        g["relative_change1"] = g.change1 / (g.lag1.abs() + 1.0)
        g["relative_change3"] = g.change3 / (g.lag3.abs() + 1.0)
        g["relative_trend7"] = (x - g.lag7) / (g.lag7.abs() + 1.0)
        g["relative_gap3_14"] = g.gap3_14 / (g.mean14.abs() + 1.0)
        g["rolling_z7"] = (x - g.mean7) / (g.std7.fillna(0).abs() + 1.0)
        g["day_sin"] = np.sin(2 * np.pi * g.index.dayofweek / 7)
        g["day_cos"] = np.cos(2 * np.pi * g.index.dayofweek / 7)
        g["band"] = rolling_band(x, h, cfg["thresholds"])
        g["future_interest"] = x.shift(-h)
        g["target_date"] = g.index + pd.Timedelta(days=h)
        g["delta"] = g.future_interest - x
        g["label"] = [direction(d, b) if np.isfinite(d) else "UNKNOWN" for d, b in zip(g.delta, g.band)]
        g = g.reset_index()
        visible = g[g.date >= start]
        coverage[keyword] = {"observed_days": int(visible.interest.notna().sum()),
                             "missing_days": int(visible.interest.isna().sum()),
                             "zero_days": int((visible.interest == 0).sum())}
        groups.append(g)
    all_rows = pd.concat(groups, ignore_index=True)
    window = all_rows[all_rows.date >= start].copy()
    features = window.dropna(subset=FEATURES)
    labeled = features[(features.target_date <= end) & features.future_interest.notna() & (features.label != "UNKNOWN")].copy()
    live = features[features.date == end].copy()
    return window, labeled.reset_index(drop=True), live.reset_index(drop=True), end, coverage
