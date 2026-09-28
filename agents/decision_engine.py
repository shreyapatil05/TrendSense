"""
DECISION ENGINE
---------------
Combines the outputs of all existing agents and produces:

INVEST
WAIT
AVOID

This is a rule-based / weighted decision engine.
It does NOT use machine learning.
"""

from datetime import datetime


# ============================================================
# WEIGHTS
# ============================================================

DECISION_WEIGHTS = {
    "weak_signal": 0.30,
    "lifecycle": 0.15,
    "authenticity": 0.15,
    "industry": 0.20,
    "financial": 0.20,
}

INVEST_THRESHOLD = 0.70


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def clamp(value, minimum=0.0, maximum=1.0):
    if value is None:
        return minimum
    return max(
        minimum,
        min(maximum, float(value))
    )


def get_authenticity_score(level):

    level = str(level).upper()

    scores = {
        "GENUINE": 1.00,
        "LIKELY_GENUINE": 0.80,
        "SUSPICIOUS": 0.45,
        "ARTIFICIAL_HYPE": 0.20,
    }

    return scores.get(level, 0.50)


def get_lifecycle_score(phase):

    phase = str(phase).upper()

    scores = {
        "GROWTH": 1.00,
        "EMERGING": 0.85,
        "PEAK": 0.70,
        "STABLE": 0.55,
        "DECLINE": 0.25,
    }

    return scores.get(phase, 0.50)


# ============================================================
# DECISION SCORE
# ============================================================

def calculate_decision_score(signal):

    if signal.get("ml_forecast_status") == "READY":
        probabilities = signal.get("ml_probabilities", {}) or {}
        # Directional opportunity index derived from learned class
        # probabilities. It is not a manually weighted source score.
        score = float(probabilities.get("UP", 0.0)) + 0.5 * float(
            probabilities.get("STABLE", 0.0)
        )
        return round(clamp(score), 3)

    weak_signal = clamp(
        signal.get("final_score", 0)
    )

    industry = clamp(
        signal.get(
            "industry_impact_score",
            0
        )
    )

    financial = clamp(
        signal.get(
            "financial_validation_score",
            0
        )
    )

    authenticity = get_authenticity_score(
        signal.get(
            "authenticity_level",
            "UNKNOWN"
        )
    )

    lifecycle = get_lifecycle_score(
        signal.get(
            "phase",
            signal.get(
                "lifecycle_phase",
                "UNKNOWN"
            )
        )
    )

    score = (
        weak_signal
        * DECISION_WEIGHTS["weak_signal"]

        + lifecycle
        * DECISION_WEIGHTS["lifecycle"]

        + authenticity
        * DECISION_WEIGHTS["authenticity"]

        + industry
        * DECISION_WEIGHTS["industry"]

        + financial
        * DECISION_WEIGHTS["financial"]
    )

    return round(
        clamp(score),
        3
    )


# ============================================================
# DECISION LOGIC
# ============================================================

def generate_decision(
    decision_score,
    signal
):

    if signal.get("evidence_status") == "INSUFFICIENT_DATA":
        return "WAIT"

    if signal.get("ml_forecast_status") == "READY":
        predicted = str(signal.get("ml_predicted_direction", "UNKNOWN")).upper()
        probabilities = signal.get("ml_probabilities", {}) or {}
        confidence = float(signal.get("ml_confidence", 0.0) or 0.0)
        evidence = str(signal.get("evidence_validation_level", "LOW")).upper()
        authenticity = str(signal.get("authenticity_level", "UNKNOWN")).upper()
        industry = float(signal.get("industry_impact_score", 0.0) or 0.0)

        if authenticity == "ARTIFICIAL_HYPE":
            return "AVOID" if evidence != "LOW" else "WAIT"
        if predicted == "DOWN" and confidence >= 0.55:
            return "AVOID" if evidence != "LOW" else "WAIT"
        if (
            predicted == "UP"
            and float(probabilities.get("UP", 0.0)) >= 0.60
            and evidence in {"TEXT_SUPPORTED", "MEDIUM", "HIGH"}
            and industry >= 0.50
        ):
            return "INVEST"
        return "WAIT"

    phase = str(
        signal.get(
            "phase",
            signal.get(
                "lifecycle_phase",
                ""
            )
        )
    ).upper()

    authenticity = str(
        signal.get(
            "authenticity_level",
            ""
        )
    ).upper()

    weak_signal = float(
        signal.get(
            "final_score",
            0
        ) or 0
    )

    industry = float(
        signal.get(
            "industry_impact_score",
            0
        ) or 0
    )

    financial = float(
        signal.get(
            "financial_validation_score",
            0
        ) or 0
    )

    # --------------------------------------------------------
    # HARD RISK CONDITIONS
    # --------------------------------------------------------

    if authenticity == "ARTIFICIAL_HYPE":

        if decision_score < 0.75:
            return "AVOID"

    if phase == "DECLINE":

        if decision_score < 0.65:
            return "AVOID"

    if (
        financial < 0.25
        and industry < 0.35
    ):
        return "AVOID"

    # --------------------------------------------------------
    # MAIN DECISION
    # --------------------------------------------------------

    if decision_score >= INVEST_THRESHOLD:

        return "INVEST"

    elif decision_score >= 0.50:

        return "WAIT"

    else:

        return "AVOID"


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_decision_strength(
    decision_score,
    decision
):

    # Distance from the neutral point.
    distance = abs(
        decision_score - 0.50
    )

    confidence = 50 + (
        distance * 100
    )

    # Keep confidence between 50 and 100
    confidence = max(
        50,
        min(100, confidence)
    )

    # Slightly increase confidence for
    # clear decisions.
    if decision in [
        "INVEST",
        "AVOID"
    ]:
        confidence += 3

    confidence = min(
        confidence,
        100
    )

    return round(
        confidence,
        2
    )


def assess_evidence_confidence(signal):
    """Estimate evidence coverage separately from decision-score strength."""
    if signal.get("evidence_validation_level"):
        level = str(signal["evidence_validation_level"]).upper()
        score = float(signal.get("evidence_validation_score", 0.0) or 0.0) * 100
        warnings = signal.get("evidence_validation_warnings", []) or []
        reason = warnings[0] if warnings else "ML prediction supported by cross-source evidence"
        return level, score, reason
    if signal.get("evidence_status") == "INSUFFICIENT_DATA":
        return "LOW", 25.0, "Upstream evidence is explicitly incomplete"

    source_scores = signal.get("source_scores", {}) or {}
    active_sources = sum(
        1 for value in source_scores.values()
        if isinstance(value, (int, float)) and value > 0.05
    )
    marketplace_observed = sum(
        bool(signal.get(name, {}).get("observed"))
        for name in ("amazon_evidence", "myntra_evidence")
    )
    active_sources += marketplace_observed

    unknown_states = {
        str(signal.get("phase", "")).upper(),
        str(signal.get("authenticity_level", "")).upper(),
    }
    impact_available = signal.get("industry_impact_score") is not None

    if active_sources >= 4 and "UNKNOWN" not in unknown_states and impact_available:
        return "HIGH", 85.0, "Multiple independent sources support the decision"
    if active_sources >= 2 and impact_available:
        return "MEDIUM", 60.0, "Some independent evidence supports the decision"
    return "LOW", 30.0, "Decision is based on sparse or proxy evidence"


# Compatibility alias for callers using the old name. This is decision
# strength, not evidence confidence.
calculate_confidence = calculate_decision_strength


# ============================================================
# ACTION WINDOW
# ============================================================

def get_action_window(
    decision,
    phase
):

    phase = str(
        phase
    ).upper()

    if decision == "INVEST":

        if phase == "EMERGING":
            return "Act within the 1-3 day forecast horizon"

        if phase == "GROWTH":
            return "Immediate short-horizon action"

        if phase == "PEAK":
            return "Short opportunity; validate daily"

        return "Near-term validation"

    if decision == "WAIT":

        if phase == "EMERGING":
            return "Monitor for 1 day"

        if phase == "GROWTH":
            return "Monitor for 1-3 days"

        return "Re-evaluate after new signals"

    return "No immediate action"


# ============================================================
# MAIN DECISION ENGINE
# ============================================================

def run_decision_engine(signals, run_config=None):
    if run_config is not None:
        from agents.configured_analysis import decision
        return decision(signals, run_config)

    print("\n")
    print("=" * 60)
    print("  DECISION ENGINE")
    print("=" * 60)

    if not signals:

        print(
            "No signals received."
        )

        return []

    results = []

    for signal in signals:

        keyword = signal.get(
            "keyword",
            "Unknown"
        )

        # Calculate combined score
        decision_score = (
            calculate_decision_score(
                signal
            )
        )

        evidence_confidence, evidence_confidence_score, evidence_reason = assess_evidence_confidence(signal)

        # Generate decision
        decision = generate_decision(
            decision_score,
            signal
        )

        # A weakly supported negative recommendation is not actionable.
        if decision == "AVOID" and evidence_confidence == "LOW":
            decision = "WAIT"

        # Get lifecycle
        phase = signal.get(
            "phase",
            signal.get(
                "lifecycle_phase",
                "UNKNOWN"
            )
        )

        # Confidence
        decision_strength = (
            calculate_decision_strength(
                decision_score,
                decision
            )
        )

        # Action window
        action_window = (
            get_action_window(
                decision,
                phase
            )
        )

        # Create output
        result = dict(signal)

        result.update({

            "decision_score":
                decision_score,

            "decision":
                decision,

            "decision_confidence":
                evidence_confidence_score,

            "decision_strength":
                decision_strength,

            "evidence_confidence":
                evidence_confidence,

            "evidence_confidence_reason":
                evidence_reason,

            "decision_borderline":
                signal.get("ml_forecast_status") == "READY"
                and float(signal.get("ml_confidence", 0) or 0) < 0.60,

            "action_window":
                action_window,

            "decision_engine":
                (
                    "ml_probability_with_rule_safeguards"
                    if signal.get("ml_forecast_status") == "READY"
                    else "weighted_rule_based_fallback"
                ),

            "decision_generated_at":
                datetime.now().isoformat(),

        })

        results.append(
            result
        )

        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        print(
            f"\nKeyword: {keyword}"
        )

        print(
            f"Decision Score : "
            f"{decision_score:.3f}"
        )

        print(
            f"Decision        : "
            f"{decision}"
        )

        print(
            f"Confidence      : "
            f"{evidence_confidence} ({evidence_confidence_score:.1f}%)"
        )

    decision_counts = {}
    for item in results:
        decision_counts[item["decision"]] = decision_counts.get(item["decision"], 0) + 1

    if decision_counts.get("AVOID", 0) == len(results):
        warning = (
            "All trends were classified AVOID. This may indicate an evidence "
            "coverage problem; review source health before acting."
        )
        print(f"\nWARNING: {warning}")
        for item in results:
            item["decision_run_warning"] = warning

    if not any(item["decision"] == "INVEST" for item in results):
        highest = max(results, key=lambda item: item.get("decision_score", 0))
        highest_score = highest.get("decision_score", 0)
        if highest_score < INVEST_THRESHOLD:
            warning = (
                f"No INVEST recommendations: highest decision score is {highest_score:.3f}, "
                f"below the {INVEST_THRESHOLD:.3f} INVEST threshold."
            )
        else:
            warning = (
                f"No INVEST recommendations: {highest.get('keyword', 'top trend')} "
                f"reached {highest_score:.3f}, but a hard risk condition prevented INVEST."
            )
        print(f"\nWARNING: {warning}")
        for item in results:
            item.setdefault("decision_run_warning", warning)

    # Per-item lifecycle/action-window values are already stored in each result.
    # The old block here was incorrectly indented and printed only the last item.

    # Sort strongest first
    results.sort(
        key=lambda item:
        item.get(
            "decision_score",
            0
        ),
        reverse=True
    )

    return results
