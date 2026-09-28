"""
Explainability Engine

Explains why the Decision Engine produced:
INVEST
WAIT
AVOID
"""

from datetime import datetime


# ============================================================
# EXPLANATION GENERATOR
# ============================================================

def generate_explanation(signal):

    keyword = signal.get(
        "keyword",
        "Unknown"
    )

    decision = signal.get(
        "decision",
        "UNKNOWN"
    )

    decision_score = float(
        signal.get(
            "decision_score",
            0
        ) or 0
    )

    weak_value = signal.get("final_score")
    industry_value = signal.get("industry_impact_score")
    financial_value = signal.get(
        "commercial_potential_score",
        signal.get("financial_validation_score")
    )
    weak_signal = float(weak_value) if weak_value is not None else None
    industry = float(industry_value) if industry_value is not None else None
    financial = float(financial_value) if financial_value is not None else None

    gt_detail = signal.get("details", {}).get("google_trends", {}) or {}
    gt_available = gt_detail.get("available", False)
    impact_details = signal.get("industry_impact_details", {}) or {}
    impact_available = industry_value is not None and impact_details.get("status") != "UNAVAILABLE"
    commercial_status = str(signal.get("validation_status", "")).upper()
    commercial_available = signal.get(
        "commercial_potential_available",
        commercial_status not in {"UNVERIFIED", ""}
    )
    commercial_confidence = signal.get("commercial_potential_confidence", "LOW")
    source_scores = signal.get("source_scores", {}) or {}
    active_sources = sum(
        1 for value in source_scores.values()
        if isinstance(value, (int, float)) and value > 0.05
    )

    authenticity = str(
        signal.get(
            "authenticity_level",
            "UNKNOWN"
        )
    ).upper()

    phase = str(
        signal.get(
            "phase",
            signal.get(
                "lifecycle_phase",
                "UNKNOWN"
            )
        )
    ).upper()

    reasons = []
    warnings = []

    if signal.get("ml_forecast_status") == "READY":
        predicted_direction = signal.get("ml_predicted_direction", "UNKNOWN")
        ml_confidence = float(signal.get("ml_confidence", 0.0) or 0.0)
        reasons.append(
            f"Historical ML model predicts {predicted_direction} "
            f"with probability {ml_confidence:.2f}."
        )
        top_features = signal.get("ml_top_features", []) or []
        if top_features:
            feature_names = ", ".join(item.get("feature", "") for item in top_features[:3])
            reasons.append(f"Most influential historical features: {feature_names}.")
    else:
        warnings.append(
            signal.get(
                "ml_forecast_warning",
                "ML forecast unavailable; decision used the documented rule-based fallback.",
            )
        )

    if signal.get("semantic_status") == "READY":
        semantic_count = int(signal.get("semantic_evidence_count", 0) or 0)
        semantic_sources = int(signal.get("semantic_source_count", 0) or 0)
        semantic_score = float(signal.get("semantic_agreement_score", 0.0) or 0.0)
        if semantic_count:
            reasons.append(
                f"Hugging Face semantic matching retained {semantic_count} relevant "
                f"items across {semantic_sources} source type(s), agreement {semantic_score:.2f}."
            )
        else:
            warnings.append("The semantic model found no evidence above the relevance threshold.")
    else:
        warnings.append(signal.get("semantic_warning", "Semantic evidence analysis unavailable."))

    warnings.extend(signal.get("evidence_validation_warnings", []) or [])


    # ========================================================
    # WEAK SIGNAL
    # ========================================================

    if weak_signal is None or signal.get("evidence_status") == "INSUFFICIENT_DATA":
        warnings.append("Weak trend score unavailable because upstream evidence was incomplete.")
    elif not gt_available:
        warnings.append("Google Trends data was unavailable; the weak score does not measure search decline.")
    elif weak_signal >= 0.70:

        reasons.append(
            f"Strong multi-source trend signal "
            f"({weak_signal:.2f})."
        )

    elif weak_signal >= 0.50:

        reasons.append(
            f"Moderate multi-source trend signal "
            f"({weak_signal:.2f})."
        )

    else:

        warnings.append(
            f"Weak trend signal "
            f"({weak_signal:.2f})."
        )


    # ========================================================
    # INDUSTRY
    # ========================================================

    impact_level = str(signal.get("industry_impact_level", signal.get("impact_level", "UNKNOWN"))).upper()
    impact_reasons = signal.get("impact_reasons", []) or []
    if industry is None or not impact_available:
        warnings.append("Industry impact is unavailable because commercial evidence was insufficient.")
    elif impact_level == "HIGH":

        reasons.append(
            f"High structural industry impact "
            f"({industry:.2f})."
        )

    elif impact_level == "MODERATE":

        reasons.append(
            f"Moderate structural industry impact "
            f"({industry:.2f})."
        )

    else:

        warnings.append(
            f"Low industry impact "
            f"({industry:.2f})."
        )

    if impact_reasons:
        reasons.extend(impact_reasons[:2])
    if signal.get("industry_impact_evidence_status") == "LIMITED":
        warnings.append("Industry impact is structural, but current source evidence is limited.")


    # ========================================================
    # FINANCIAL
    # ========================================================

    if financial is None or not commercial_available:
        warnings.append("Commercial potential is unavailable; no commercial evidence was observed.")
    elif commercial_confidence == "LOW":
        warnings.append("Commercial potential is based on limited or proxy marketplace evidence.")
    elif financial >= 0.70:

        reasons.append(
            f"Strong commercial potential signal "
            f"({financial:.2f})."
        )

    elif financial >= 0.50:

        reasons.append(
            f"Moderate commercial potential signal "
            f"({financial:.2f})."
        )

    else:

        warnings.append(
            f"Low commercial potential signal "
            f"({financial:.2f})."
        )


    # ========================================================
    # AUTHENTICITY
    # ========================================================

    if authenticity == "GENUINE":

        reasons.append(
            "Signals appear genuine."
        )

    elif authenticity == "LIKELY_GENUINE":

        reasons.append(
            "Signals are likely genuine."
        )

    elif authenticity == "SUSPICIOUS":

        warnings.append(
            "Some signals may be suspicious."
        )

    elif authenticity == "ARTIFICIAL_HYPE":

        warnings.append(
            "The trend shows signs of artificial hype."
        )


    # ========================================================
    # LIFECYCLE
    # ========================================================

    if phase == "EMERGING":

        reasons.append(
            "The trend is in the emerging phase."
        )

    elif phase == "GROWTH":

        reasons.append(
            "The trend is currently in the growth phase."
        )

    elif phase == "PEAK":

        warnings.append(
            "The trend is near its peak."
        )

    elif phase == "DECLINE":

        warnings.append(
            "The trend is currently declining."
        )

    elif phase == "STABLE":

        warnings.append(
            "The trend is stable rather than rapidly growing."
        )

    if phase == "UNKNOWN":
        warnings.append("Lifecycle phase is unknown because historical demand evidence was insufficient.")

    if authenticity == "UNKNOWN":
        warnings.append("Authenticity is unknown because independent source coverage was insufficient.")

    if active_sources < 2:
        warnings.append(
            f"Only {active_sources} source type(s) provided meaningful evidence; similar scores may reflect shared defaults."
        )


    # ========================================================
    # SUMMARY
    # ========================================================

    if decision == "INVEST":

        summary = (
            f"{keyword} is recommended for INVESTMENT "
            f"because the combined evidence is strong."
        )

    elif decision == "WAIT":

        summary = (
            f"{keyword} shows potential, but additional "
            f"evidence should be collected before investment."
        )

    elif decision == "AVOID":

        summary = (
            f"{keyword} is not recommended for immediate "
            f"investment because the combined evidence "
            f"is weak or risk factors are significant."
        )

    else:

        summary = (
            f"No clear decision could be generated "
            f"for {keyword}."
        )


    # ========================================================
    # RETURN EXPLANATION
    # ========================================================

    return {

        "keyword": keyword,

        "decision": decision,

        "decision_score": decision_score,

        "evidence_summary": {
            "active_source_count": active_sources,
            "google_trends_available": gt_available,
            "industry_impact_available": impact_available,
            "commercial_potential_available": commercial_available,
            "commercial_potential_confidence": commercial_confidence,
            "evidence_confidence": signal.get("evidence_confidence", "LOW"),
            "ml_forecast_status": signal.get("ml_forecast_status", "UNAVAILABLE"),
            "ml_predicted_direction": signal.get("ml_predicted_direction", "UNKNOWN"),
            "ml_probabilities": signal.get("ml_probabilities", {}),
            "semantic_status": signal.get("semantic_status", "UNAVAILABLE"),
            "semantic_agreement_score": signal.get("semantic_agreement_score"),
        },

        "summary": summary,

        "reasons": reasons,

        "warnings": warnings,

        "generated_at": datetime.now().isoformat(),

    }


# ============================================================
# RUN ENGINE
# ============================================================

def run_explainability_engine(signals, run_config=None):
    if run_config is not None:
        from agents.configured_analysis import explain
        return explain(signals, run_config)

    print("\n")
    print("=" * 60)
    print("  EXPLAINABILITY ENGINE")
    print("=" * 60)

    results = []

    for signal in signals:

        explanation = generate_explanation(
            signal
        )

        result = dict(signal)

        result["explanation"] = explanation
        result["evidence_summary"] = explanation["evidence_summary"]

        results.append(result)

        print(
            f"\n{explanation['keyword']}"
        )

        print(
            f"Decision: "
            f"{explanation['decision']}"
        )

        print(
            f"Score: "
            f"{explanation['decision_score']:.3f}"
        )

        evidence_summary = explanation["evidence_summary"]
        print(
            f"Evidence: {evidence_summary['evidence_confidence']} confidence | "
            f"{evidence_summary['active_source_count']} active source types"
        )

        print(
            f"Summary: "
            f"{explanation['summary']}"
        )

        if explanation["reasons"]:

            print("\nReasons:")

            for reason in explanation["reasons"]:

                print(
                    f"  + {reason}"
                )

        if explanation["warnings"]:

            print("\nWarnings:")

            for warning in explanation["warnings"]:

                print(
                    f"  - {warning}"
                )

    if results:
        score_signatures = [
            (
                item.get("final_score"),
                item.get("industry_impact_score"),
                item.get("commercial_potential_score", item.get("financial_validation_score")),
            )
            for item in results
        ]
        most_common_signature = max(
            set(score_signatures),
            key=score_signatures.count
        )
        convergence_ratio = score_signatures.count(most_common_signature) / len(score_signatures)
        low_evidence_count = sum(
            item.get("evidence_summary", {}).get("active_source_count", 0) < 2
            for item in results
        )
        if convergence_ratio >= 0.60 and low_evidence_count >= len(results) * 0.60:
            warning = (
                "Many trends share the same score tuple while source coverage is sparse; "
                "treat repeated values as an evidence-coverage diagnostic, not independent confirmation."
            )
            print(f"\nWARNING: {warning}")
            for item in results:
                item["explainability_run_warning"] = warning

    return results
