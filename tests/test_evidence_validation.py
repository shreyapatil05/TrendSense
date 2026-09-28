from agents.evidence_validation_agent import run_evidence_validation_analysis


def test_evidence_validation_uses_ml_and_semantic_support():
    item = {
        "keyword": "glass skin",
        "ml_forecast_status": "READY",
        "ml_confidence": 0.78,
        "source_scores": {"google_trends": 0.8, "youtube": 0.6, "news": 0.4},
        "semantic_source_count": 2,
        "semantic_agreement_score": 0.70,
        "semantic_status": "READY",
    }
    result = run_evidence_validation_analysis([item])[0]
    assert result["evidence_validation_level"] == "HIGH"
