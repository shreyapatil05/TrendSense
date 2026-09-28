"""V4 implementations used by the existing agent entry points.

Legacy functions remain readable for comparison; the configured CLI never uses
their hand-weighted scores. Evidence is descriptive, not a profitability label.
"""
from collections import Counter
from urllib.parse import urlparse
import numpy as np


VALID_TEXT_EVIDENCE = {"TEXT_SUPPORTED", "MEDIUM", "HIGH"}


def _finite(value, default=0.0):
    """Return a finite float without allowing missing values to distort ranking."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _up_margin(item):
    """Continuous forecast change measured in keyword-specific adaptive bands."""
    band = abs(_finite(item.get("threshold")))
    if band <= 0:
        return float("-inf")
    return _finite(item.get("predicted_change")) / band


def _text_supported(item, cfg):
    if not cfg["recommendation"]["require_text_evidence"]:
        return True
    level = str(item.get("evidence_validation_level", "")).upper()
    return level in VALID_TEXT_EVIDENCE or int(item.get("semantic_evidence_count", 0) or 0) > 0


def weak(signals, cfg):
    output = []
    for keyword in cfg["keywords"]["selected"]:
        matched = [s for s in signals if keyword in s.get("matched_keywords", []) or s.get("keyword") == keyword]
        counts = Counter(s.get("source", "unknown") for s in matched)
        output.append({"keyword": keyword, "industry": cfg["industry"], "source_counts": dict(counts),
                       "evidence_count": len(matched), "raw_evidence": matched,
                       "signal_strength": "OBSERVED" if matched else "UNAVAILABLE",
                       "evidence_status": "MEASURED" if matched else "INSUFFICIENT_DATA",
                       "final_score": None, "source_scores": {},
                       "signal_method": "observed_counts_without_source_weights"})
    return output


def lifecycle(items, cfg):
    return [{**x, "phase": {"UP": "GROWTH", "DOWN": "DECLINE", "STABLE": "STABLE"}.get(x.get("past_direction"), "UNKNOWN"),
             "lifecycle_method": "observed_horizon_change_vs_causal_robust_band",
             "lifecycle_limitation": "Emerging and saturation phases require longer adoption evidence"} for x in items]


def authenticity(items, cfg):
    result = []
    for x in items:
        urls = [s.get("url") or s.get("link") for s in x.get("raw_evidence", [])]
        urls = [u for u in urls if u]
        domains = {urlparse(u).netloc.lower().removeprefix("www.") for u in urls}
        # Publisher domains are not proof of independent ownership or genuine demand.
        result.append({**x, "authenticity_level": "UNVERIFIED", "authenticity_score": None,
                       "publisher_domains": sorted(domains), "duplicate_url_count": len(urls)-len(set(urls)),
                       "authenticity_reason": "No labeled bot/manipulation dataset; report provenance rather than assert GENUINE"})
    return result


def evidence(items, cfg):
    return [{**x, "evidence_validation_level": "TEXT_SUPPORTED" if x.get("semantic_evidence_count", 0) else "LIMITED",
             "evidence_validation_score": None,
             "evidence_validation_method": "semantic_candidate_evidence_and_explicit_missingness",
             "evidence_validation_warnings": [] if x.get("semantic_evidence_count", 0) else ["No semantic text support"]}
            for x in items]


def industry(items, cfg):
    # Reuse original domain mappings, but do not score arbitrary new industries.
    from agents.industry_impact_agent import infer_affected_industries, infer_business_areas, infer_affected_categories
    output = []
    for x in items:
        known = cfg["industry"] in {"fashion", "beauty"}
        affected = infer_affected_industries(x) if known else [cfg["industry"]]
        output.append({**x, "primary_industry": cfg["industry"], "affected_industries": affected,
                       "affected_business_areas": infer_business_areas(x, affected) if known else [],
                       "affected_categories": infer_affected_categories(x) if known else [],
                       "industry_impact_score": None, "industry_impact_evidence_status": "DESCRIPTIVE" if known else "UNMAPPED",
                       "industry_impact_reason": "Category applicability, not a learned revenue estimate"})
    return output


def commercial(items, cfg):
    # Marketplace metadata cannot validate sales, margins, or profitability.
    import os
    from agents.commercial_potential import build_marketplace_evidence
    output = []
    for x in items:
        evidence = []
        if os.getenv("TRENDSENSE_OFFLINE") != "1" and cfg["industry"] in {"fashion", "beauty"}:
            _, _, evidence = build_marketplace_evidence(x["keyword"])
        output.append({**x, "marketplace_evidence": evidence, "commercial_potential_score": None,
                       "financial_validation_available": False, "commercial_potential_available": False,
                       "validation_status": "UNVERIFIED", "commercial_reason": "Sales and margin data unavailable; no profit estimate"})
    return output


def decision(items, cfg):
    output = []
    for x in items:
        reasons = []
        label = x.get("ml_predicted_direction", "UNKNOWN")
        numeric = x.get("numeric_direction", "UNKNOWN")
        cutoff = x.get("policy_cutoffs", {}).get(label)
        score = x.get("ml_probabilities", {}).get(label)
        ready = x.get("ml_forecast_status") == "READY"
        supported = _text_supported(x, cfg)
        action = "WAIT"
        if not ready:
            reasons.append(x.get("ml_forecast_warning", "Forecast unavailable"))
        elif x.get("target_already_observed"):
            reasons.append("Target is no longer future; this is a historical replay")
        elif label != numeric:
            reasons.append("Classifier and numeric forecast disagree")
        elif label == "STABLE":
            reasons.append("Forecast remains inside the adaptive stable band")
        elif cutoff is None or score is None or score < cutoff:
            reasons.append("Directional confidence does not meet the validation-selected cutoff")
        elif not supported:
            reasons.append("Text evidence unavailable; recommendation withheld")
        else:
            action = "INVEST" if label == "UP" else "AVOID"
            reasons.append(f"{label} forecast exceeds validation-selected cutoff {cutoff:.3f}")
            if action == "INVEST":
                reasons.append("UP class and numeric forecast agree with text support")
                reasons.append("Candidate for a limited commercial trial; profitability is unverified")
        if ready:
            reasons.append(f"Adaptive interest-change band: +/-{x['threshold']:.3f} index points")
        # UP probability remains untouched. Keyword-specific numeric margin is a
        # transparent tie-breaker when a baseline emits identical probabilities.
        up_probability = _finite(x.get("ml_probabilities", {}).get("UP"))
        margin = _up_margin(x)
        evidence_count = int(x.get("semantic_evidence_count", 0) or 0)
        raw_count = int(x.get("evidence_count", 0) or 0)
        output.append({**x, "decision": action, "decision_score": up_probability,
                       "_rank_up_probability": up_probability, "_rank_margin": margin,
                       "_rank_text_evidence": evidence_count, "_rank_raw_evidence": raw_count,
                       "decision_reasons": reasons,
                       "decision_engine": "validation_tuned_direction_policy_v4", "decision_confidence": x.get("ml_confidence"),
                       "up_decision_cutoff": x.get("policy_cutoffs", {}).get("UP"),
                       "up_candidate": bool(ready and label == "UP" and numeric == "UP" and supported),
                       "ranking_components": {"up_probability": up_probability,
                                              "numeric_change_in_adaptive_bands": None if not np.isfinite(margin) else margin,
                                              "semantic_evidence_count": evidence_count,
                                              "evidence_count": raw_count},
                       "ranking_basis": "UP_probability_then_keyword_numeric_margin_then_evidence"})
    output.sort(key=lambda x: (
        x.get("ml_forecast_status") == "READY",
        x["_rank_up_probability"], x["_rank_margin"],
        x["_rank_text_evidence"], x["_rank_raw_evidence"], x.get("keyword", "")
    ), reverse=True)
    ready_count = sum(x.get("ml_forecast_status") == "READY" for x in output)
    rank = 0
    for item in output:
        for field in ("_rank_up_probability", "_rank_margin", "_rank_text_evidence", "_rank_raw_evidence"):
            item.pop(field, None)
        if item.get("ml_forecast_status") == "READY":
            rank += 1
            item["watchlist_rank"] = rank
            # A rank percentile is deliberately not presented as a probability.
            item["watchlist_score"] = round((ready_count - rank + 1) / ready_count, 6)
            item["watchlist_score_type"] = "within_run_rank_percentile"
        else:
            item["watchlist_rank"] = None
            item["watchlist_score"] = None
            item["watchlist_score_type"] = "unavailable"
    return output


def explain(items, cfg):
    return [{**x, "explanation": {"summary": f"{x['keyword']}: {x['decision']}",
             "reasons": x["decision_reasons"],
             "warnings": ["Forecast concerns normalized search interest, not sales.",
                          "Authenticity and profitability remain unverified.",
                          "Model scores are not calibrated probabilities of business success."],
             "models": {"direction": x.get("ml_forecast_method"), "numeric": x.get("numeric_model")}}} for x in items]
