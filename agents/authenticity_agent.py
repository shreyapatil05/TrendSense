import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ALL_KEYWORDS,
    DATA_DIR,
    PROCESSED_DIR
)

# AUTHENTICITY LEVELS
AUTH_LEVELS = {
    "UNKNOWN": "Insufficient independent evidence for authenticity assessment",
    "GENUINE": "Authentic trend with consistent signals across platforms",
    "LIKELY_GENUINE": "Strong indicators of authenticity, some hype possible",
    "SUSPICIOUS": "Mixed signals, possible artificial hype",
    "ARTIFICIAL_HYPE": "Clear signs of manufactured trend or viral manipulation"
}

def load_weak_signals():
    if not os.path.exists(PROCESSED_DIR):
        print(f"  [Authenticity] Processed directory not found: {PROCESSED_DIR}")
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

def assess_authenticity(signal):
    """
    Assess if a trend is genuine or artificial hype.
    """
    score = 0
    reasons = []

    if signal.get("evidence_status") == "INSUFFICIENT_DATA":
        return "UNKNOWN", "Insufficient evidence for authenticity assessment", 0, [
            "Google Trends was unavailable and no supporting source matched"
        ]

    # Factor 1: Cross-platform consistency
    sources = signal["source_scores"]
    active_sources = sum(1 for s in sources.values() if s > 0.1)
    if active_sources < 2:
        return "UNKNOWN", AUTH_LEVELS["UNKNOWN"], 0, [
            "Fewer than two independent sources provided meaningful evidence",
            "Sparse coverage is not evidence of artificial hype"
        ]

    if active_sources >= 3:
        score += 0.4
        reasons.append("Present across multiple platforms")
    elif active_sources >= 2:
        score += 0.2
        reasons.append("Present on 2+ platforms")

    # Factor 2: Gradual growth vs sudden spike
    velocity = signal["details"]["google_trends"]["velocity"]
    recent_avg = signal["details"]["google_trends"]["recent_avg"]

    if velocity > 0 and velocity < 20:  # Moderate, sustainable growth
        score += 0.3
        reasons.append("Gradual, sustainable growth")
    elif velocity > 20:  # Sudden spike
        score -= 0.3
        reasons.append("Sudden spike - possible hype")
    elif velocity < -10:  # Rapid decline
        score -= 0.2
        reasons.append("Rapid decline - fading hype")

    # Factor 3: Credible sources
    wiki_score = sources["wikipedia"]
    news_score = sources["news"]
    if wiki_score > 0.3 or news_score > 0.2:
        score += 0.2
        reasons.append("Mentioned in credible sources")
    elif wiki_score == 0 and news_score == 0:
        score -= 0.1
        reasons.append("No credible source mentions")

    # Factor 4: Interest level sustainability
    if recent_avg > 10 and velocity > -5:
        score += 0.1
        reasons.append("Sustained interest level")

    # Artificial hype requires a concrete spike pattern. A negative score by
    # itself can mean decline or incomplete editorial coverage, not manipulation.
    sudden_spike_without_credible_support = (
        velocity > 20
        and wiki_score < 0.3
        and news_score < 0.2
    )

    # Determine authenticity level
    if score >= 0.6:
        level = "GENUINE"
    elif score >= 0.3:
        level = "LIKELY_GENUINE"
    elif sudden_spike_without_credible_support and score < 0:
        level = "ARTIFICIAL_HYPE"
    else:
        level = "SUSPICIOUS"

    return level, AUTH_LEVELS[level], score, reasons

def run_authenticity_analysis(signals=None, run_config=None):
    if run_config is not None:
        from agents.configured_analysis import authenticity
        return authenticity(signals or [], run_config)
    print("\n" + "="*50)
    print("  AUTHENTICITY AGENT RUNNING")
    print("="*50)

    if signals is None:
        signals = load_weak_signals()

    if not signals:
        print("  No signals to analyse.")
        return []

    print(f"\n  Assessing authenticity for {len(signals)} trends...\n")

    authenticity_results = []

    for signal in signals:
        keyword = signal["keyword"]
        level, description, auth_score, reasons = assess_authenticity(signal)

        authenticity_results.append({
            "keyword": keyword,
            "industry": signal["industry"],
            "authenticity_level": level,
            "description": description,
            "authenticity_score": round(auth_score, 3),
            "signal_strength": signal["signal_strength"],
            "final_score": signal["final_score"],
            "evidence_status": signal.get("evidence_status", "UNKNOWN"),
            "reasons": reasons,
            "analysed_at": datetime.now().isoformat()
        })

    # Sort by authenticity score descending
    authenticity_results.sort(key=lambda x: x["authenticity_score"], reverse=True)

    print("  Authenticity analysis complete.\n")
    return authenticity_results

def print_authenticity_summary(authenticity_results):
    print("\n" + "="*50)
    print("  TREND AUTHENTICITY ANALYSIS")
    print("="*50)

    levels = ["GENUINE", "LIKELY_GENUINE", "SUSPICIOUS", "ARTIFICIAL_HYPE", "UNKNOWN"]

    for level in levels:
        items = [r for r in authenticity_results if r["authenticity_level"] == level]
        if not items:
            continue

        print(f"\n  [{level}] — {len(items)} trends")
        print("  " + "-"*48)

        for item in items[:5]:  # Show top 5 per level
            ind = "F" if item["industry"] == "fashion" else "B"
            print(
                f"  [{ind}] {item['keyword']:<28} "
                f"score: {item['authenticity_score']:.3f}  "
                f"signal: {item['signal_strength']}"
            )
            if item["reasons"]:
                print(f"       Reasons: {', '.join(item['reasons'][:2])}")

    print("\n  Top 10 most authentic:")
    print("  " + "-"*48)
    for i, item in enumerate(authenticity_results[:10], 1):
        ind = "F" if item["industry"] == "fashion" else "B"
        print(
            f"  {i:2}. [{ind}] {item['keyword']:<28} "
            f"{item['authenticity_level']:<15} {item['authenticity_score']:.3f}"
        )

# ENTRY POINT

if __name__ == "__main__":
    signals = load_weak_signals()
    authenticity_results = run_authenticity_analysis(signals)
    print_authenticity_summary(authenticity_results)

    # Save results
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(PROCESSED_DIR, f"authenticity_{timestamp}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(authenticity_results, f, indent=2, ensure_ascii=False)

    print(f"\n  Results saved to: {filepath}")
