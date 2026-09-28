"""Validate ML predictions against independent and semantic evidence."""


def run_evidence_validation_analysis(results, run_config=None):
    if run_config is not None:
        from agents.configured_analysis import evidence
        return evidence(results, run_config)
    validated = []
    for item in results:
        source_scores = item.get("source_scores") or {}
        active_sources = sum(
            isinstance(value, (int, float)) and value > 0.05
            for value in source_scores.values()
        )
        semantic_sources = int(item.get("semantic_source_count", 0) or 0)
        semantic_score = float(item.get("semantic_agreement_score", 0) or 0)
        ml_ready = item.get("ml_forecast_status") == "READY"
        ml_confidence = float(item.get("ml_confidence", 0) or 0)
        warnings = []
        if not ml_ready:
            level, score = "LOW", 0.20
            warnings.append(item.get("ml_forecast_warning", "ML forecast unavailable"))
        elif active_sources >= 3 and semantic_sources >= 2 and semantic_score >= 0.50:
            level, score = "HIGH", 0.90
        elif active_sources >= 2 or semantic_sources >= 2:
            level, score = "MEDIUM", 0.65
        else:
            level, score = "LOW", 0.35
            warnings.append("Prediction has sparse independent evidence")
        if ml_ready and ml_confidence < 0.50:
            warnings.append("ML class probability is uncertain")
            if level == "HIGH":
                level, score = "MEDIUM", 0.65
        if item.get("semantic_status") != "READY":
            warnings.append(item.get("semantic_warning", "Semantic model unavailable"))
        validated.append({
            "keyword": item.get("keyword"),
            "evidence_validation_level": level,
            "evidence_validation_score": score,
            "evidence_active_source_count": active_sources,
            "evidence_semantic_source_count": semantic_sources,
            "evidence_validation_warnings": warnings,
            "evidence_validation_method": "ml_probability_plus_cross_source_semantic_check",
        })
    return validated
