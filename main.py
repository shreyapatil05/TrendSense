#!/usr/bin/env python3
"""TrendSense orchestration entry point."""
import argparse
import json
import os
from datetime import datetime, timezone

from agents.authenticity_agent import run_authenticity_analysis
from agents.commercial_potential import run_commercial_potential_analysis
from agents.decision_engine import run_decision_engine
from agents.explainability_engine import run_explainability_engine
from agents.industry_impact_agent import run_industry_impact_analysis
from agents.lifecycle_agent import run_lifecycle_analysis
from agents.ml_forecasting_agent import run_ml_forecasting_analysis
from agents.semantic_evidence_agent import run_semantic_evidence_analysis
from agents.evidence_validation_agent import run_evidence_validation_analysis
from agents.weak_signal_agent import run_weak_signal_detection
from config import (
    DATA_DIR, DEFAULT_FORECAST_HORIZON, FORECAST_HORIZONS_DAYS, PROCESSED_DIR,
)
from storage.forecasts import persist_forecasts
from storage.history import persist_observations

def merge_results(base, additional):
    by_keyword = {x.get("keyword"): x for x in additional if x.get("keyword")}
    return [{**x, **by_keyword.get(x.get("keyword"), {})} for x in base]

def load_latest_signals():
    if not os.path.isdir(DATA_DIR): return []
    names = sorted(n for n in os.listdir(DATA_DIR) if n.startswith("signals_") and n.endswith(".json"))
    if not names: return []
    with open(os.path.join(DATA_DIR, names[-1]), encoding="utf-8") as h: return json.load(h)

def save_json(data, prefix):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(PROCESSED_DIR, f"{prefix}_{stamp}.json")
    with open(path, "w", encoding="utf-8") as h: json.dump(data, h, indent=2, ensure_ascii=False)
    return path


def save_raw_signals(signals):
    os.makedirs(DATA_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(DATA_DIR, f"signals_{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(signals, handle, indent=2, ensure_ascii=False)
    return path

def run_pipeline(
    signals=None, use_cache=False, horizon_days=DEFAULT_FORECAST_HORIZON,
    persist=True, semantic_enabled=True,
):
    if signals is None:
        if use_cache:
            signals = load_latest_signals()
        else:
            from agents.scout_agent import run_scout
            signals = run_scout()
            print(f"Raw signals saved: {save_raw_signals(signals)}")
    if not isinstance(signals, list) or not signals: raise RuntimeError("No valid signal list was collected or loaded")
    run_time = datetime.now(timezone.utc).isoformat()
    if persist: persist_observations(signals, run_time)
    weak = run_weak_signal_detection(signals)
    lifecycle = merge_results(weak, run_lifecycle_analysis(weak))
    authentic = merge_results(lifecycle, run_authenticity_analysis(lifecycle))
    semantic = run_semantic_evidence_analysis(authentic, signals, enabled=semantic_enabled)
    with_semantic = merge_results(authentic, semantic)
    ml_results = run_ml_forecasting_analysis(with_semantic, horizon_days)
    with_ml = merge_results(with_semantic, ml_results)
    validation = run_evidence_validation_analysis(with_ml)
    validated = merge_results(with_ml, validation)
    industry = run_industry_impact_analysis(validated)
    commercial = run_commercial_potential_analysis(industry)
    decisions = run_decision_engine(commercial)
    final = run_explainability_engine(decisions)
    final_path = save_json(final, "final_results")
    if persist: persist_forecasts(final, horizon_days, run_time)
    print(f"Final results saved: {final_path}")
    return final

def print_summary(results):
    counts = {n: sum(x.get("decision") == n for x in results) for n in ("INVEST", "WAIT", "AVOID")}
    print("\nFINAL SUMMARY", counts)
    for i, x in enumerate(results[:10], 1):
        print(
            f"{i:2}. {x['keyword']:<28} {x['decision']:<6} "
            f"{x['decision_score']:.3f} {x.get('phase', 'UNKNOWN'):<8} "
            f"ML:{x.get('ml_predicted_direction', 'N/A')} "
            f"({float(x.get('ml_confidence', 0) or 0):.2f}) "
            f"Semantic:{x.get('semantic_status', 'N/A')}"
        )

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--cache", action="store_true")
    p.add_argument("--input", help="Read signals from a JSON list")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--horizon", type=int, choices=FORECAST_HORIZONS_DAYS, default=DEFAULT_FORECAST_HORIZON)
    p.add_argument("--no-semantic", action="store_true", help="Skip Hugging Face semantic analysis")
    p.add_argument("--no-persist", action="store_true")
    return p.parse_args()

if __name__ == "__main__":
    from cli_v4 import main as configured_main
    configured_main("run")
