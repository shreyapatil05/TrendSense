"""Immutable forecasts plus separate outcome records."""
import hashlib
import json
import os
from datetime import datetime, timezone

from config import CONFIGURATION_VERSION, FORECAST_DIR, SYSTEM_VERSION
from contracts import ForecastRecord
from storage.history import append_jsonl


def direction_for(item):
    if item.get("ml_forecast_status") == "READY":
        return str(item.get("ml_predicted_direction", "UNKNOWN")).upper()
    phase = str(item.get("phase", "UNKNOWN")).upper()
    if phase in {"EMERGING", "GROWTH"}: return "UP"
    if phase == "DECLINE": return "DOWN"
    if phase in {"PEAK", "STABLE"}: return "STABLE"
    return "UNKNOWN"


def persist_forecasts(results, horizon_days, forecast_timestamp=None):
    timestamp = forecast_timestamp or datetime.now(timezone.utc).isoformat()
    records = []
    for item in results:
        keyword = str(item.get("keyword", "unknown"))
        trend_id = hashlib.sha256(keyword.lower().encode()).hexdigest()[:16]
        forecast_id = hashlib.sha256(
            f"{trend_id}|{timestamp}|{horizon_days}|{SYSTEM_VERSION}".encode()
        ).hexdigest()[:24]
        sources = [name for name, value in (item.get("source_scores") or {}).items()
                   if isinstance(value, (int, float)) and value > 0]
        ml_ready = item.get("ml_forecast_status") == "READY"
        record = ForecastRecord(
            forecast_id=forecast_id,
            trend_id=trend_id,
            keyword=keyword,
            forecast_timestamp=timestamp,
            forecast_horizon_days=horizon_days,
            predicted_strength=None,
            predicted_direction=direction_for(item),
            predicted_lifecycle=str(item.get("phase", "UNKNOWN")),
            forecast_confidence=float(
                item.get("ml_confidence", 0)
                if ml_ready else float(item.get("decision_confidence", 0)) / 100.0
            ),
            decision=str(item.get("decision", "UNKNOWN")),
            evidence_snapshot={
                "source_scores": item.get("source_scores", {}),
                "details": item.get("details", {}),
                "industry_impact_score": item.get("industry_impact_score"),
                "commercial_potential_score": item.get("commercial_potential_score"),
                "semantic_relevant_evidence": item.get("semantic_relevant_evidence", []),
            },
            sources_used=sources,
            system_version=SYSTEM_VERSION,
            configuration_version=CONFIGURATION_VERSION,
            forecast_method=(
                item.get("ml_forecast_method", "random_forest_classifier")
                if ml_ready else "rule_based_fallback"
            ),
            predicted_probabilities=item.get("ml_probabilities", {}),
            model_version=item.get("ml_model_version"),
            current_interest=item.get("ml_current_interest"),
            semantic_agreement_score=item.get("semantic_agreement_score"),
        )
        records.append(record.to_dict())
    path = os.path.join(FORECAST_DIR, "forecasts.jsonl")
    append_jsonl(path, records)
    return path, records


def append_outcomes(outcomes):
    path = os.path.join(FORECAST_DIR, "outcomes.jsonl")
    append_jsonl(path, outcomes)
    return path


def read_jsonl(path):
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
