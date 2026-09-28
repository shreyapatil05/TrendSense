import json
import os
import sys
from datetime import datetime
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ALL_KEYWORDS,
    DATA_DIR,
    PROCESSED_DIR
)

# LIFECYCLE PHASES
PHASES = {
    "EMERGING": "Early stage, gaining initial traction",
    "GROWTH": "Rapidly increasing popularity",
    "PEAK": "At maximum popularity, stable or slight decline",
    "DECLINE": "Losing popularity, fading away",
    "STABLE": "Consistent but not trending significantly"
}

# THRESHOLDS
VELOCITY_HIGH = 15
VELOCITY_MEDIUM = 5
INTEREST_HIGH = 50
INTEREST_LOW = 10

def load_weak_signals():
    if not os.path.exists(PROCESSED_DIR):
        print(f"  [Lifecycle] Processed directory not found: {PROCESSED_DIR}")
        return []

    files = [
        f for f in os.listdir(PROCESSED_DIR)
        if f.startswith("weak_signals_") and f.endswith(".json")
    ]

    if not files:
        print("  No weak signal files found. Run weak_signal_agent.py first.")
        return []

    latest_file = sorted(files)[-1]
    filepath = os.path.join(PROCESSED_DIR, latest_file)

    with open(filepath, "r", encoding="utf-8") as f:
        signals = json.load(f)

    print(f"  Loaded {len(signals)} weak signals from {latest_file}")
    return signals

def determine_lifecycle_phase(signal):
    """
    Determine the lifecycle phase based on trend data.
    """
    gt_detail = signal["details"]["google_trends"]
    if not gt_detail.get("available", False):
        return "UNKNOWN", "Insufficient evidence to determine lifecycle phase"
    observations = int(gt_detail.get("observations", 0) or 0)
    acceleration = gt_detail.get("acceleration")
    previous_avg = gt_detail.get("previous_avg")
    if observations < 3 or acceleration is None or previous_avg is None:
        return "UNKNOWN", "Insufficient historical demand windows for lifecycle classification"

    velocity = float(gt_detail.get("velocity", 0) or 0)
    recent_avg = float(gt_detail.get("recent_avg", 0) or 0)
    historical_avg = float(gt_detail.get("historical_avg", recent_avg) or 0)
    acceleration = float(acceleration)
    rising = bool(gt_detail.get("rising", False))

    if historical_avg <= 0 and recent_avg <= 0:
        return "UNKNOWN", "No measurable search demand was observed"

    # Emerging: low baseline with early positive momentum.
    if historical_avg < INTEREST_LOW and velocity > 0 and acceleration >= 0:
        return "EMERGING", PHASES["EMERGING"]

    # Growth: positive velocity confirmed by acceleration.
    if velocity >= VELOCITY_MEDIUM and acceleration > 0 and rising:
        return "GROWTH", PHASES["GROWTH"]

    # Peak: high demand with momentum flattening or turning down.
    if recent_avg >= INTEREST_HIGH and velocity >= -VELOCITY_MEDIUM and acceleration <= 0:
        return "PEAK", PHASES["PEAK"]

    # Decline: negative momentum confirmed by non-positive acceleration.
    if velocity < -VELOCITY_MEDIUM and acceleration <= 0:
        return "DECLINE", PHASES["DECLINE"]

    # Stable is only valid when both demand windows and momentum are flat.
    if abs(velocity) < VELOCITY_MEDIUM and abs(acceleration) <= 2:
        return "STABLE", PHASES["STABLE"]

    return "UNKNOWN", "Demand and momentum are mixed; lifecycle phase is unresolved"

def run_lifecycle_analysis(signals=None, run_config=None):
    if run_config is not None:
        from agents.configured_analysis import lifecycle
        return lifecycle(signals or [], run_config)
    print("\n" + "="*50)
    print("  LIFECYCLE AGENT RUNNING")
    print("="*50)

    if signals is None:
        signals = load_weak_signals()

    if not signals:
        print("  No signals to analyse.")
        return []

    print(f"\n  Analysing lifecycle for {len(signals)} trends...\n")

    lifecycle_results = []

    for signal in signals:
        keyword = signal["keyword"]
        phase, description = determine_lifecycle_phase(signal)

        lifecycle_results.append({
            "keyword": keyword,
            "industry": signal["industry"],
            "phase": phase,
            "description": description,
            "signal_strength": signal["signal_strength"],
            "final_score": signal["final_score"],
            "velocity": signal["details"]["google_trends"]["velocity"],
            "recent_interest": signal["details"]["google_trends"]["recent_avg"],
            "historical_interest": signal["details"]["google_trends"].get("historical_avg"),
            "previous_interest": signal["details"]["google_trends"].get("previous_avg"),
            "acceleration": signal["details"]["google_trends"].get("acceleration"),
            "observations": signal["details"]["google_trends"].get("observations", 0),
            "analysed_at": datetime.now().isoformat()
        })

    # Sort by phase priority: Growth > Peak > Emerging > Stable > Decline
    phase_order = {"GROWTH": 0, "PEAK": 1, "EMERGING": 2, "STABLE": 3, "DECLINE": 4, "UNKNOWN": 5}
    lifecycle_results.sort(key=lambda x: (phase_order.get(x["phase"], 6), -(x["final_score"] or 0)))

    print("  Lifecycle analysis complete.\n")
    return lifecycle_results

def print_lifecycle_summary(lifecycle_results):
    print("\n" + "="*50)
    print("  TREND LIFECYCLE ANALYSIS")
    print("="*50)

    phases = ["GROWTH", "PEAK", "EMERGING", "STABLE", "DECLINE", "UNKNOWN"]

    for phase in phases:
        items = [r for r in lifecycle_results if r["phase"] == phase]
        if not items:
            continue

        print(f"\n  [{phase}] — {len(items)} trends")
        print("  " + "-"*48)

        for item in items[:5]:  # Show top 5 per phase
            ind = "F" if item["industry"] == "fashion" else "B"
            print(
                f"  [{ind}] {item['keyword']:<28} "
                f"score: {item['final_score']:.3f}  "
                f"vel: {item['velocity']:>6.1f}"
            ) if item["final_score"] is not None else print(
                f"  [{ind}] {item['keyword']:<28} "
                "score: unavailable  "
                f"vel: {item['velocity']:>6.1f}"
            )

    print("\n  Top 10 overall by score:")
    print("  " + "-"*48)
    for i, item in enumerate(lifecycle_results[:10], 1):
        ind = "F" if item["industry"] == "fashion" else "B"
        print(
            f"  {i:2}. [{ind}] {item['keyword']:<28} "
            f"{item['phase']:<8} "
            f"{item['final_score']:.3f}"
        ) if item["final_score"] is not None else print(
            f"  {i:2}. [{ind}] {item['keyword']:<28} "
            f"{item['phase']:<8} unavailable"
        )

# ENTRY POINT

if __name__ == "__main__":
    signals = load_weak_signals()
    lifecycle_results = run_lifecycle_analysis(signals)
    print_lifecycle_summary(lifecycle_results)

    # Save results
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(PROCESSED_DIR, f"lifecycle_{timestamp}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(lifecycle_results, f, indent=2, ensure_ascii=False)

    print(f"\n  Results saved to: {filepath}")
