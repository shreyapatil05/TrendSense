"""Append-only JSONL observation store."""
import hashlib
import json
import os
from datetime import datetime, timezone

from config import DEFAULT_GEO, DEFAULT_LANGUAGE, HISTORY_DIR
from contracts import ObservationRecord

SOURCE_RELIABILITY = {
    "google_trends": 0.90, "youtube_shorts": 0.70,
    "newsapi": 0.75, "rss_feed": 0.70,
    "wikipedia_pageviews": 0.65, "google_autocomplete": 0.60,
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def persist_observations(signals, run_timestamp=None):
    timestamp = run_timestamp or _utc_now()
    records = []
    for index, signal in enumerate(signals):
        source = str(signal.get("source", "unknown"))
        if source == "scout_health":
            continue
        keyword = str(signal.get("keyword") or signal.get("page") or "unknown")
        trend_id = hashlib.sha256(keyword.lower().encode()).hexdigest()[:16]
        observed_at = str(signal.get("timestamp") or signal.get("published_at") or timestamp)
        observation_id = hashlib.sha256(
            f"{trend_id}|{source}|{observed_at}|{index}".encode()
        ).hexdigest()[:24]
        normalized = {k: signal.get(k) for k in (
            "velocity", "recent_avg", "historical_avg", "previous_avg",
            "acceleration", "mentions", "views", "engagement"
        ) if k in signal}
        record = ObservationRecord(
            observation_id, trend_id, keyword,
            str(signal.get("industry") or signal.get("domain") or "unknown"),
            source, source, str(signal.get("geo") or DEFAULT_GEO),
            str(signal.get("language") or DEFAULT_LANGUAGE), observed_at,
            dict(signal), normalized, SOURCE_RELIABILITY.get(source, 0.50),
            {"collector": "scout_agent", "stored_at": timestamp},
            list(signal.get("warnings", [])),
        )
        records.append(record.to_dict())
    path = os.path.join(HISTORY_DIR, "observations.jsonl")
    append_jsonl(path, records)
    return path, records
