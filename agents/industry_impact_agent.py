import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
	PROCESSED_DIR,
)


# INDUSTRY IMPACT LEVELS
IMPACT_LEVELS = {
	"UNKNOWN": "Insufficient evidence to estimate industry impact",
	"CRITICAL": "High and immediate business impact across core value chains",
	"HIGH": "Strong business impact with clear commercial relevance",
	"MODERATE": "Meaningful but contained business impact",
	"LOW": "Limited or early-stage business impact",
	"MINIMAL": "Weak or uncertain business impact",
}


INDUSTRY_BUSINESS_AREAS = {
	"fashion": [
		"product_design",
		"merchandising",
		"retail",
		"ecommerce",
		"supply_chain",
		"social_commerce",
		"influencer_marketing",
	],
	"beauty": [
		"product_formulation",
		"retail",
		"ecommerce",
		"salon_services",
		"consumer_goods",
		"social_commerce",
		"influencer_marketing",
	],
	"retail": ["retail", "merchandising", "store_operations"],
	"ecommerce": ["ecommerce", "marketplaces", "search_conversion"],
	"consumer_goods": ["consumer_goods", "brand_marketing", "distribution"],
	"media": ["content_creation", "publishing", "editorial_coverage"],
	"marketing": ["brand_marketing", "performance_marketing", "creator_partnerships"],
	"salons": ["salon_services", "appointments", "local_services"],
}


# Impact is structural: it describes the possible business footprint of a
# trend, independently of current signal strength or source volume.
IMPACT_WEIGHTS = {
	"product_applicability": 0.20,
	"consumer_reach": 0.20,
	"category_breadth": 0.25,
	"commercial_relevance": 0.20,
	"india_relevance": 0.15,
}

FASHION_PROFILE = {
	"product_applicability": 0.55,
	"consumer_reach": 0.45,
	"category_breadth": 0.50,
	"commercial_relevance": 0.60,
	"india_relevance": 0.55,
}

BEAUTY_PROFILE = {
	"product_applicability": 0.50,
	"consumer_reach": 0.45,
	"category_breadth": 0.45,
	"commercial_relevance": 0.60,
	"india_relevance": 0.50,
}

UNKNOWN_PROFILE = {
	"product_applicability": 0.25,
	"consumer_reach": 0.20,
	"category_breadth": 0.20,
	"commercial_relevance": 0.25,
	"india_relevance": 0.20,
}

TREND_IMPACT_PROFILES = {
	"kurta set": {
		"components": {"product_applicability": 0.85, "consumer_reach": 0.75, "category_breadth": 0.70, "commercial_relevance": 0.75, "india_relevance": 0.90},
		"categories": ["ethnic wear", "casual fashion", "occasion wear", "accessories", "footwear", "online fashion retail"],
		"reasons": ["Applies across ethnic, casual and occasion apparel", "Relevant to broad Indian consumer use cases", "Supports product, styling and retail adaptations", "Strong alignment with Indian fashion consumption"],
	},
	"saree draping": {
		"components": {"product_applicability": 0.65, "consumer_reach": 0.60, "category_breadth": 0.55, "commercial_relevance": 0.65, "india_relevance": 0.90},
		"categories": ["ethnic wear", "occasion wear", "accessories", "beauty styling", "fashion content"],
		"reasons": ["Can influence sarees, styling services and accessories", "Relevant to Indian occasion and cultural wear", "Commercially useful for styling, content and retail"],
	},
	"lehenga skirt": {
		"components": {"product_applicability": 0.65, "consumer_reach": 0.50, "category_breadth": 0.55, "commercial_relevance": 0.65, "india_relevance": 0.80},
		"categories": ["occasion wear", "ethnic wear", "accessories", "footwear", "fashion retail"],
		"reasons": ["Strong fit for occasion and ethnic apparel", "Can extend into styling, accessories and footwear", "Indian market relevance is concentrated around occasions"],
	},
	"indo western": {
		"components": {"product_applicability": 0.75, "consumer_reach": 0.65, "category_breadth": 0.65, "commercial_relevance": 0.70, "india_relevance": 0.85},
		"categories": ["ethnic wear", "contemporary fashion", "occasion wear", "accessories", "fashion retail"],
		"reasons": ["Bridges ethnic and contemporary product categories", "Relevant to Indian Gen Z styling", "Supports apparel, accessories and retail adaptations"],
	},
	"dark academia": {
		"components": {"product_applicability": 0.45, "consumer_reach": 0.30, "category_breadth": 0.35, "commercial_relevance": 0.45, "india_relevance": 0.35},
		"categories": ["contemporary fashion", "accessories", "fashion content"],
		"reasons": ["Supports a coherent but niche styling direction", "Primarily affects apparel, accessories and content", "Appeal is narrower in the Indian mass market"],
	},
}

BUSINESS_AREA_CATEGORIES = {
	"fashion": ["product_design", "merchandising", "retail", "ecommerce", "supply_chain", "social_commerce", "influencer_marketing"],
	"beauty": ["product_formulation", "retail", "ecommerce", "salon_services", "consumer_goods", "social_commerce", "influencer_marketing"],
}


AUTHENTICITY_FACTORS = {
	"UNKNOWN": 0.50,
	"GENUINE": 1.00,
	"LIKELY_GENUINE": 0.80,
	"SUSPICIOUS": 0.45,
	"ARTIFICIAL_HYPE": 0.20,
}


PHASE_FACTORS = {
	"UNKNOWN": 0.50,
	"GROWTH": 1.00,
	"EMERGING": 0.85,
	"PEAK": 0.75,
	"STABLE": 0.55,
	"DECLINE": 0.25,
}


def load_authenticity_results():
	if not os.path.exists(PROCESSED_DIR):
		print(f"  [IndustryImpact] Processed directory not found: {PROCESSED_DIR}")
		return []

	files = [
		f for f in os.listdir(PROCESSED_DIR)
		if f.startswith("authenticity_") and f.endswith(".json")
	]

	if not files:
		print("  No authenticity files found. Run authenticity_agent.py first.")
		return []

	for latest_file in sorted(files, reverse=True):
		filepath = os.path.join(PROCESSED_DIR, latest_file)
		try:
			with open(filepath, "r", encoding="utf-8") as f:
				signals = json.load(f)

			if isinstance(signals, list):
				print(f"  Loaded {len(signals)} authenticity records from {latest_file}")
				return signals
		except Exception as e:
			print(f"  [IndustryImpact] Skipping invalid file {latest_file}: {e}")

	print("  No valid authenticity files found.")
	return []


def clamp(value, minimum=0.0, maximum=1.0):
	return max(minimum, min(maximum, value))


def unique_preserve_order(items):
	seen = set()
	ordered = []
	for item in items:
		if item and item not in seen:
			seen.add(item)
			ordered.append(item)
	return ordered


def get_source_diversity(signal):
	source_scores = signal.get("source_scores", {}) or {}
	active_sources = sum(1 for value in source_scores.values() if value > 0.05)
	total_sources = max(len(source_scores), 1)
	return active_sources, active_sources / total_sources


def get_business_relevance_profile(signal):
	keyword = str(signal.get("keyword", "")).strip().lower()
	domain = str(signal.get("domain", signal.get("industry", "unknown"))).lower()
	if domain == "fashion_beauty":
		domain = "fashion" if any(
		term in keyword for term in ("saree", "kurta", "lehenga", "fashion", "dress", "style", "wear")
		) else "beauty"

	if keyword in TREND_IMPACT_PROFILES:
		return TREND_IMPACT_PROFILES[keyword]["components"], "keyword_specific", domain != "unknown"
	if domain == "fashion":
		return FASHION_PROFILE, "fashion_category", True
	if domain == "beauty":
		return BEAUTY_PROFILE, "beauty_category", True
	return UNKNOWN_PROFILE, "unknown_category", False


def infer_business_areas(signal, affected_industries):
	primary_industry = str(signal.get("domain", signal.get("industry", "unknown"))).lower()
	return BUSINESS_AREA_CATEGORIES.get(primary_industry, [])


def infer_affected_categories(signal):
	keyword = str(signal.get("keyword", "")).strip().lower()
	if keyword in TREND_IMPACT_PROFILES:
		return TREND_IMPACT_PROFILES[keyword]["categories"]
	primary_industry = str(signal.get("domain", signal.get("industry", "unknown"))).lower()
	if primary_industry == "fashion":
		return ["apparel", "accessories", "fashion retail"]
	if primary_industry == "beauty":
		return ["makeup", "skincare", "beauty retail"]
	return []


def infer_impact_reasons(signal, categories, components):
	keyword = str(signal.get("keyword", "")).strip().lower()
	profile_reasons = TREND_IMPACT_PROFILES.get(keyword, {}).get("reasons", [])
	if profile_reasons:
		return profile_reasons

	reasons = []
	if components.get("product_applicability", 0) >= 0.50:
		reasons.append("Can translate into products or services within its category")
	if components.get("category_breadth", 0) >= 0.50 and categories:
		reasons.append(f"Can influence multiple adjacent categories: {', '.join(categories[:3])}")
	if components.get("consumer_reach", 0) >= 0.50:
		reasons.append("Has potential relevance beyond a narrow early-adopter audience")
	if components.get("india_relevance", 0) >= 0.60:
		reasons.append("Shows meaningful alignment with Indian consumer context")
	if not reasons:
		reasons.append("Commercial applicability is limited to a narrow category or audience")
	return reasons


def infer_affected_industries(signal):
	primary_industry = str(signal.get("domain", signal.get("industry", "unknown"))).lower()
	affected = []

	if primary_industry in ["fashion", "beauty"]:
		affected.append(primary_industry)

	if primary_industry == "fashion":
		affected.extend(["retail", "ecommerce", "consumer_goods", "media", "marketing"])
	elif primary_industry == "beauty":
		affected.extend(["consumer_goods", "retail", "ecommerce", "salons", "marketing"])
	else:
		return []

	return unique_preserve_order(affected)


def determine_primary_industry(signal, affected_industries):
	declared_industry = str(signal.get("industry", "unknown")).lower()
	if declared_industry in affected_industries:
		return declared_industry

	if affected_industries:
		return affected_industries[0]

	return declared_industry if declared_industry else "unknown"


def determine_impact_direction(signal):
	if signal.get("evidence_status") == "INSUFFICIENT_DATA":
		return "unknown"

	phase = str(signal.get("phase", signal.get("lifecycle_phase", ""))).upper()
	authenticity_level = str(signal.get("authenticity_level", "")).upper()
	signal_strength = str(signal.get("signal_strength", "")).upper()

	if authenticity_level == "ARTIFICIAL_HYPE" or phase == "DECLINE":
		return "negative"

	if authenticity_level == "SUSPICIOUS" and signal_strength in ["WEAK", "NOISE"]:
		return "negative"

	if phase in ["GROWTH", "EMERGING", "PEAK"] and authenticity_level in ["GENUINE", "LIKELY_GENUINE"]:
		return "positive"

	if signal_strength == "STRONG":
		return "positive"

	return "mixed"


def calculate_industry_impact_score(signal, affected_industries, business_areas):
	profile, profile_source, domain_known = get_business_relevance_profile(signal)
	active_sources, source_diversity = get_source_diversity(signal)
	components = {
		name: round(clamp(profile.get(name, 0.0)), 3)
		for name in IMPACT_WEIGHTS
	}
	raw_score = sum(
		components[name] * weight
		for name, weight in IMPACT_WEIGHTS.items()
	)
	confidence = "MEDIUM" if domain_known and active_sources >= 2 else "LOW"
	confidence_score = 0.75 if confidence == "MEDIUM" else 0.35
	status = "STRUCTURAL" if active_sources >= 2 else "LIMITED"

	return round(clamp(raw_score), 3), {
		"status": status,
		"evidence_status": status,
		"score_basis": "five_structural_dimensions",
		"profile_source": profile_source,
		"domain_known": domain_known,
		"components": components,
		"source_count": active_sources,
		"source_diversity": round(source_diversity, 3),
		"confidence": confidence,
		"confidence_score": confidence_score,
	}


def classify_impact_level(score, direction):
	if score is None:
		return "UNKNOWN", IMPACT_LEVELS["UNKNOWN"]
	if score >= 0.75:
		return "HIGH", IMPACT_LEVELS["HIGH"]
	if score >= 0.50:
		return "MODERATE", IMPACT_LEVELS["MODERATE"]
	if score >= 0.30:
		return "LOW", IMPACT_LEVELS["LOW"]
	return "MINIMAL", IMPACT_LEVELS["MINIMAL"]


def build_reasoning(signal, affected_industries, business_areas, categories, details):
	reasoning = []

	if affected_industries:
		reasoning.append(f"Affected industries: {', '.join(affected_industries[:4])}")
	if categories:
		reasoning.append(f"Affected categories: {', '.join(categories[:5])}")
	if business_areas:
		reasoning.append(f"Business areas: {', '.join(business_areas[:5])}")

	source_count = details.get("source_count", 0)
	source_diversity = details.get("source_diversity", 0)
	reasoning.append(f"Evidence coverage: {source_count} active source types, diversity {source_diversity}")
	reasoning.append(f"Impact basis: {details.get('score_basis', 'five_structural_dimensions')}")
	if details.get("domain_known") is False:
		reasoning.append("Domain is unknown; impact estimate is capped and low confidence")
	if details.get("evidence_status") == "LIMITED":
		reasoning.append("Structural impact is estimated with limited current trend evidence")

	return reasoning


def run_industry_impact_analysis(signals=None, run_config=None):
	if run_config is not None:
		from agents.configured_analysis import industry
		return industry(signals or [], run_config)
	print("\n" + "=" * 50)
	print("  INDUSTRY IMPACT AGENT RUNNING")
	print("=" * 50)

	if signals is None:
		signals = load_authenticity_results()

	if not signals:
		print("  No signals to analyse.")
		return []

	print(f"\n  Analysing industry impact for {len(signals)} trends...\n")

	impact_results = []

	for signal in signals:
		_, profile_source, domain_known = get_business_relevance_profile(signal)
		resolved_domain = str(signal.get("domain", signal.get("industry", "unknown"))).lower()
		affected_industries = infer_affected_industries(signal)
		primary_industry = determine_primary_industry(signal, affected_industries)
		business_areas = infer_business_areas(signal, affected_industries)
		affected_categories = infer_affected_categories(signal)
		direction = determine_impact_direction(signal)
		impact_score, score_details = calculate_industry_impact_score(signal, affected_industries, business_areas)
		impact_level, impact_description = classify_impact_level(impact_score, direction)
		profile_reasons = infer_impact_reasons(
			signal,
			affected_categories,
			score_details.get("components", {}),
		)
		reasoning = build_reasoning(signal, affected_industries, business_areas, affected_categories, score_details)
		reasoning.extend(profile_reasons)

		result = dict(signal)
		result.update({
			"affected_industries": affected_industries,
			"primary_industry": primary_industry,
			"industry_domain": resolved_domain,
			"impact_profile_source": profile_source,
			"industry_domain_known": domain_known,
			"industry_impact_score": impact_score,
			"industry_impact_confidence": score_details.get("confidence", "LOW"),
			"industry_impact_confidence_score": score_details.get("confidence_score", 0.35),
			"industry_impact_evidence_status": score_details.get("evidence_status", "LIMITED"),
			"business_relevance": (
				"High" if impact_score is not None and impact_score >= 0.75
				else "Moderate" if impact_score is not None and impact_score >= 0.50
				else "Low" if impact_score is not None
				else "Unavailable"
			),
			"industry_impact_level": impact_level,
			"impact_level": impact_level,
			"impact_direction": direction,
			"affected_business_areas": business_areas,
			"affected_categories": affected_categories,
			"industry_impact_components": score_details.get("components", {}),
			"impact_reasons": profile_reasons,
			"industry_impact_reasoning": reasoning,
			"industry_impact_description": impact_description,
			"industry_impact_details": score_details,
			"analysed_at": datetime.now().isoformat(),
		})
		impact_results.append(result)

	impact_results.sort(key=lambda x: (
		x.get("industry_impact_score") if x.get("industry_impact_score") is not None else -1,
		x.get("final_score") if x.get("final_score") is not None else -1,
	), reverse=True)

	print("  Industry impact analysis complete.\n")
	return impact_results


def print_industry_impact_summary(impact_results):
	print("\n" + "=" * 50)
	print("  INDUSTRY IMPACT ANALYSIS")
	print("=" * 50)

	levels = ["CRITICAL", "HIGH", "MODERATE", "LOW", "MINIMAL", "UNKNOWN"]

	for level in levels:
		items = [item for item in impact_results if item.get("impact_level") == level]
		if not items:
			continue

		print(f"\n  [{level}] — {len(items)} trends")
		print("  " + "-" * 48)

		for item in items[:5]:
			industry_label = item.get("primary_industry", "unknown")
			score_text = (
				f"{item['industry_impact_score']:.3f}"
				if item.get("industry_impact_score") is not None
				else "N/A"
			)
			print(
				f"  [{industry_label[:1].upper()}] {item['keyword']:<28} "
				f"score: {score_text}  "
				f"direction: {item['impact_direction']}"
			)
			print(
				f"       Industries: {', '.join(item.get('affected_industries', [])[:4])}"
			)

	print("\n  Top 10 overall by industry impact:")
	print("  " + "-" * 48)
	for i, item in enumerate(impact_results[:10], 1):
		score_text = (
			f"{item['industry_impact_score']:.3f}"
			if item.get("industry_impact_score") is not None
			else "N/A"
		)
		print(
			f"  {i:2}. {item['keyword']:<28} "
			f"{item['impact_level']:<9} {score_text}"
		)


if __name__ == "__main__":
	signals = load_authenticity_results()
	impact_results = run_industry_impact_analysis(signals)
	print_industry_impact_summary(impact_results)

	os.makedirs(PROCESSED_DIR, exist_ok=True)
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filepath = os.path.join(PROCESSED_DIR, f"industry_impact_{timestamp}.json")

	with open(filepath, "w", encoding="utf-8") as f:
		json.dump(impact_results, f, indent=2, ensure_ascii=False)

	print(f"\n  Results saved to: {filepath}")
