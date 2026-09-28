"""Historical Google Trends collector with resumable batch caching."""
import json
import os
import random
import time
from datetime import datetime, timezone

from config import (
    ALL_KEYWORDS, DEFAULT_GEO, DEFAULT_LANGUAGE, DEFAULT_TIMEZONE,
    HISTORICAL_DIR, HISTORICAL_TIMEFRAME, INDUSTRY_TAGS,
)

BATCH_SIZE = 5


def collect_configured(cfg, refresh=False, import_csv=None):
    """Collect immutable snapshots. Publish history only after complete coverage.

    Import is for auditing existing data without additional API calls. Old data
    retains its normalization batches; it is never relabeled as a fresh download.
    """
    import hashlib
    from pathlib import Path
    import pandas as pd
    from runtime_config import paths, save_json, fingerprint
    p = paths(cfg)
    keywords = cfg["keywords"]["selected"]
    p["data"].mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC")
    stamp = now.strftime("%Y%m%dT%H%M%S%f")
    if import_csv:
        frame = pd.read_csv(import_csv)
        canonical = {keyword.casefold(): keyword for keyword in keywords}
        normalized = frame.keyword.astype(str).str.casefold()
        frame = frame[normalized.isin(canonical)].copy()
        frame["keyword"] = frame.keyword.astype(str).str.casefold().map(canonical)
        frame["date"] = pd.to_datetime(frame.date, utc=True, format="mixed").dt.normalize()
        frame = frame[frame.date < now.normalize()]
        if "collected_at" in frame:
            # Legacy collectors discarded isPartial. Conservatively discard collection day.
            observed = pd.to_datetime(frame.collected_at, utc=True).dt.normalize()
            frame = frame[frame.date < observed]
        if "batch_index" not in frame:
            frame["batch_index"] = 0
        source_hash = hashlib.sha256(Path(import_csv).read_bytes()).hexdigest()
        frame["batch_signature"] = frame.batch_index.map(lambda x: fingerprint([source_hash, str(x)]))
        frame["normalization_provenance"] = "legacy_import"
    else:
        if p["history"].exists() and not refresh:
            cached = pd.read_csv(p["history"])
            if pd.to_datetime(cached.date, utc=True).max() >= now.normalize() - pd.Timedelta(days=1):
                return p["history"]
        end = now.normalize() - pd.Timedelta(days=1)
        start = end - pd.Timedelta(days=cfg["collection"]["history_days"] - 1)
        timeframe = f"{start.date()} {end.date()}"
        size = cfg["collection"]["batch_size"]
        batches = [keywords[i:i+size] for i in range(0, len(keywords), size)]
        frames, failures = [], []
        for index, batch in enumerate(batches):
            for attempt in range(cfg["collection"]["max_retries"]):
                try:
                    from pytrends.request import TrendReq
                    client = TrendReq(hl=cfg["collection"]["language"], tz=330, timeout=(10, 30))
                    client.build_payload(batch, timeframe=timeframe, geo=cfg["collection"]["country"])
                    wide = client.interest_over_time()
                    if wide.empty or any(k not in wide for k in batch):
                        raise ValueError("Missing keyword columns or empty batch")
                    if "isPartial" in wide:
                        partial = wide.isPartial.astype(str).str.lower().isin(["true", "1"])
                        wide = wide.loc[~partial]
                    for keyword in batch:
                        part = pd.DataFrame({"date": pd.to_datetime(wide.index, utc=True),
                                             "keyword": keyword, "interest": wide[keyword].to_numpy()})
                        part["batch_signature"] = fingerprint([batch, cfg["collection"]["country"]])
                        part["batch_index"] = index + 1
                        frames.append(part)
                    print(f"Historical batch {index+1}/{len(batches)} collected")
                    break
                except Exception as exc:
                    if attempt + 1 == cfg["collection"]["max_retries"]:
                        failures.append({"keywords": batch, "error": str(exc)})
                    else:
                        time.sleep(cfg["collection"]["delay_seconds"] * (attempt + 1))
            if index + 1 < len(batches):
                time.sleep(cfg["collection"]["delay_seconds"])
        save_json(p["data"] / "collection_health.json", {"failures": failures, "requested": keywords,
                                                       "collected_at": now.isoformat()})
        if failures:
            if frames:
                pd.concat(frames).to_csv(p["data"] / f"partial_{stamp}.csv", index=False)
            raise RuntimeError("Collection incomplete. Prior history preserved; see collection_health.json and retry --refresh")
        frame = pd.concat(frames, ignore_index=True)
        frame["normalization_provenance"] = "request_snapshot"
        frame["collected_at"] = now.isoformat()
    missing = sorted(set(keywords) - set(frame.keyword))
    if missing:
        raise ValueError(f"Historical data missing selected keywords: {missing}")
    frame["interest"] = pd.to_numeric(frame.interest, errors="coerce")
    frame["industry"] = cfg["industry"]
    frame["geo"] = cfg["collection"]["country"]
    frame["snapshot_id"] = stamp
    frame = frame.sort_values(["keyword", "date"]).drop_duplicates(["keyword", "date"], keep="last")
    # Weekly data must never silently become a daily forecast dataset.
    steps = frame.groupby("keyword").date.diff().dt.days.dropna()
    if not steps.empty and steps.median() > 1:
        raise ValueError("Daily data required; shorten collection.history_days. Weekly data is not interpolated.")
    snapshots = p["data"] / "snapshots"
    snapshots.mkdir(exist_ok=True)
    frame.to_csv(snapshots / f"{stamp}.csv", index=False)
    frame.to_csv(p["history"], index=False)
    save_json(p["data"] / "metadata.json", {"snapshot_id": stamp, "rows": len(frame),
              "keywords": keywords, "date_min": str(frame.date.min()), "date_max": str(frame.date.max()),
              "imported": bool(import_csv), "warning": "Request-normalized index, not sales or absolute search volume"})
    print(f"Saved {len(frame)} rows for {len(keywords)} keywords: {p['history']}")
    return p["history"]


def industry_for(keyword):
    if keyword in INDUSTRY_TAGS["fashion"]:
        return "fashion"
    if keyword in INDUSTRY_TAGS["beauty"]:
        return "beauty"
    return "unknown"


def _client():
    try:
        from pytrends.request import TrendReq
    except ImportError as exc:
        raise RuntimeError("pytrends is required. Run: pip install -r requirements.txt") from exc
    return TrendReq(hl=DEFAULT_LANGUAGE, tz=DEFAULT_TIMEZONE, timeout=(10, 30))


def _cache_path(batch_index, timeframe, geo):
    safe_timeframe = timeframe.replace(" ", "_")
    return os.path.join(HISTORICAL_DIR, "cache", f"batch_{batch_index:02d}_{geo}_{safe_timeframe}.json")


def collect_historical_data(
    keywords=None, timeframe=HISTORICAL_TIMEFRAME, geo=DEFAULT_GEO,
    refresh=False, delay_seconds=8, max_retries=3,
):
    keywords = list(keywords or ALL_KEYWORDS)
    os.makedirs(os.path.join(HISTORICAL_DIR, "cache"), exist_ok=True)
    all_rows = []
    batches = [keywords[i:i + BATCH_SIZE] for i in range(0, len(keywords), BATCH_SIZE)]
    trends = _client()

    for batch_index, batch in enumerate(batches, 1):
        cache_path = _cache_path(batch_index, timeframe, geo)
        if os.path.exists(cache_path) and not refresh:
            with open(cache_path, encoding="utf-8") as handle:
                all_rows.extend(json.load(handle))
            print(f"  Historical batch {batch_index}/{len(batches)} loaded from cache")
            continue

        rows = None
        for attempt in range(1, max_retries + 1):
            try:
                trends.build_payload(batch, timeframe=timeframe, geo=geo)
                frame = trends.interest_over_time()
                if frame.empty:
                    raise RuntimeError("Google Trends returned an empty frame")
                frame = frame.drop(columns=["isPartial"], errors="ignore")
                rows = []
                for date, values in frame.iterrows():
                    for keyword in batch:
                        rows.append({
                            "date": date.isoformat(),
                            "keyword": keyword,
                            "industry": industry_for(keyword),
                            "interest": float(values.get(keyword, 0.0)),
                            "geo": geo,
                            "source": "google_trends",
                            "timeframe": timeframe,
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "batch_index": batch_index,
                        })
                break
            except Exception as exc:
                if attempt == max_retries:
                    print(f"  Historical batch {batch_index} failed: {exc}")
                else:
                    wait = delay_seconds * attempt + random.uniform(1, 4)
                    print(f"  Historical batch {batch_index} retrying in {wait:.1f}s")
                    time.sleep(wait)
                    trends = _client()
        if rows is None:
            continue
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False)
        all_rows.extend(rows)
        print(f"  Historical batch {batch_index}/{len(batches)} collected")
        if batch_index < len(batches):
            time.sleep(delay_seconds + random.uniform(1, 3))

    if not all_rows:
        raise RuntimeError("No historical rows were collected")

    import pandas as pd
    frame = pd.DataFrame(all_rows)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame = frame.sort_values(["keyword", "date"]).drop_duplicates(["keyword", "date"], keep="last")
    path = os.path.join(HISTORICAL_DIR, "google_trends_daily.csv")
    os.makedirs(HISTORICAL_DIR, exist_ok=True)
    frame.to_csv(path, index=False)
    metadata = {
        "dataset_path": path,
        "rows": int(len(frame)),
        "keywords_requested": len(keywords),
        "keywords_collected": int(frame["keyword"].nunique()),
        "date_min": frame["date"].min().isoformat(),
        "date_max": frame["date"].max().isoformat(),
        "timeframe": timeframe,
        "geo": geo,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warning": "Interest is normalized by Google Trends. Within-trend temporal features are used.",
    }
    with open(os.path.join(HISTORICAL_DIR, "dataset_metadata.json"), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    return path, metadata
