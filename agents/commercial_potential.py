import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import quote_plus

try:
	import requests
except ImportError:
	requests = None

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
	PROCESSED_DIR,
)


# COMMERCIAL POTENTIAL LEVELS
VALIDATION_STATUSES = {
	"VALIDATED": "Direct marketplace metadata and upstream trend evidence support commercial potential",
	"PROBABLE": "Evidence suggests commercial potential, but confirmation is still partial",
	"PROXY_ONLY": "Only indirect marketplace metadata or pipeline evidence is available",
	"UNVERIFIED": "No reliable commercial evidence is available",
}


COMMERCIAL_LEVELS = {
	"HIGH": "High commercial signal",
	"MEDIUM": "Moderate commercial signal",
	"LOW": "Low commercial signal",
	"NONE": "No meaningful commercial signal",
}


MARKETPLACE_TIMEOUT = 8


def load_industry_impact_results():
	if not os.path.exists(PROCESSED_DIR):
		print(f"  [Financial] Processed directory not found: {PROCESSED_DIR}")
		return []

	files = [
		f for f in os.listdir(PROCESSED_DIR)
		if f.startswith("industry_impact_") and f.endswith(".json")
	]

	if not files:
		print("  No industry impact files found. Run industry_impact_agent.py first.")
		return []

	for latest_file in sorted(files, reverse=True):
		filepath = os.path.join(PROCESSED_DIR, latest_file)
		try:
			with open(filepath, "r", encoding="utf-8") as f:
				records = json.load(f)

			if isinstance(records, list):
				print(f"  Loaded {len(records)} industry impact records from {latest_file}")
				return records
		except Exception as e:
			print(f"  [Financial] Skipping invalid file {latest_file}: {e}")

	print("  No valid industry impact files found.")
	return []


def clamp(value, minimum=0.0, maximum=1.0):
	return max(minimum, min(maximum, value))


def slugify_keyword(keyword):
	slug = re.sub(r"[^a-z0-9]+", " ", str(keyword).lower()).strip()
	return quote_plus(slug)


def get_marketplace_metadata(url, keyword):
	if os.getenv("TRENDSENSE_OFFLINE", "0") == "1" or requests is None:
		return {
			"url": url, "status": "offline", "evidence_type": "unavailable",
			"observed": False, "query": keyword, "page_title": "",
			"meta_description": "", "signals": ["offline_mode"],
			"reason": "Marketplace collection disabled in offline mode",
		}
	headers = {
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
	}

	try:
		response = requests.get(url, headers=headers, timeout=MARKETPLACE_TIMEOUT)
		status_code = response.status_code
		text = response.text or ""

		if status_code != 200:
			return {
				"url": url,
				"status": status_code,
				"evidence_type": "unavailable",
				"observed": False,
				"query": keyword,
				"page_title": "",
				"meta_description": "",
				"signals": [],
				"reason": f"HTTP {status_code}",
			}

		title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
		description_match = re.search(
			r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
			text,
			re.IGNORECASE | re.DOTALL,
		)

		page_title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
		meta_description = re.sub(r"\s+", " ", description_match.group(1)).strip() if description_match else ""

		blocked_terms = ["captcha", "robot", "forbidden", "access denied", "verify you are a human"]
		text_lower = text.lower()
		if any(term in text_lower for term in blocked_terms):
			return {
				"url": url,
				"status": status_code,
				"evidence_type": "unavailable",
				"observed": False,
				"query": keyword,
				"page_title": page_title,
				"meta_description": meta_description,
				"signals": ["blocked_or_challenge_page"],
				"reason": "Marketplace served a challenge or block page",
			}

		query_present = keyword.lower() in (page_title + " " + meta_description).lower()

		signals = []
		if query_present:
			signals.append("query_present_in_metadata")
		if page_title:
			signals.append("page_title_available")
		if meta_description:
			signals.append("meta_description_available")

		evidence_type = "directly_observed" if query_present else "inferred/proxy"
		reason = "Keyword appears in visible marketplace metadata" if query_present else "Marketplace page loaded but keyword not confirmed in metadata"

		return {
			"url": url,
			"status": status_code,
			"evidence_type": evidence_type,
			"observed": query_present,
			"query": keyword,
			"page_title": page_title,
			"meta_description": meta_description,
			"signals": signals,
			"reason": reason,
		}
	except Exception as e:
		return {
			"url": url,
			"status": "error",
			"evidence_type": "unavailable",
			"observed": False,
			"query": keyword,
			"page_title": "",
			"meta_description": "",
			"signals": ["request_failed"],
			"reason": str(e),
		}


def build_marketplace_evidence(keyword):
	slug = slugify_keyword(keyword)
	amazon_url = f"https://www.amazon.in/s?k={slug}"
	myntra_url = f"https://www.myntra.com/{slug}"

	amazon_evidence = get_marketplace_metadata(amazon_url, keyword)
	myntra_evidence = get_marketplace_metadata(myntra_url, keyword)

	marketplace_evidence = [
		{
			"marketplace": "amazon",
			"evidence_type": amazon_evidence.get("evidence_type", "unavailable"),
			"observed": amazon_evidence.get("observed", False),
			"reason": amazon_evidence.get("reason", ""),
			"status": amazon_evidence.get("status", ""),
		},
		{
			"marketplace": "myntra",
			"evidence_type": myntra_evidence.get("evidence_type", "unavailable"),
			"observed": myntra_evidence.get("observed", False),
			"reason": myntra_evidence.get("reason", ""),
			"status": myntra_evidence.get("status", ""),
		},
	]

	return amazon_evidence, myntra_evidence, marketplace_evidence


def get_pipeline_evidence(signal):
	source_scores = signal.get("source_scores", {}) or {}
	active_sources = sum(1 for value in source_scores.values() if value > 0.05)
	source_diversity = active_sources / max(len(source_scores), 1)

	impact_score = float(signal.get("industry_impact_score", 0.0) or 0.0)
	final_score = float(signal.get("final_score", 0.0) or 0.0)
	signal_strength = str(signal.get("signal_strength", "UNKNOWN")).upper()
	authenticity_level = str(signal.get("authenticity_level", "UNKNOWN")).upper()
	phase = str(signal.get("phase", signal.get("lifecycle_phase", "UNKNOWN"))).upper()

	return {
		"source_count": active_sources,
		"source_diversity": round(source_diversity, 3),
		"final_score": final_score,
		"industry_impact_score": impact_score,
		"signal_strength": signal_strength,
		"authenticity_level": authenticity_level,
		"phase": phase,
	}


def score_marketplace_signal(amazon_evidence, myntra_evidence, pipeline_evidence, signal):
	score = 0.0
	reasons = []

	if pipeline_evidence["industry_impact_score"] >= 0.55:
		score += 0.25
		reasons.append("Industry impact score indicates clear commercial relevance")
	elif pipeline_evidence["industry_impact_score"] >= 0.30:
		score += 0.15
		reasons.append("Industry impact score suggests moderate commercial relevance")
	else:
		reasons.append("Industry impact score is weak")

	if pipeline_evidence["signal_strength"] in ["STRONG", "MODERATE"]:
		score += 0.15
		reasons.append("Upstream weak-signal stage is above noise")

	if pipeline_evidence["authenticity_level"] in ["GENUINE", "LIKELY_GENUINE"]:
		score += 0.15
		reasons.append("Authenticity analysis supports durable demand")
	elif pipeline_evidence["authenticity_level"] == "ARTIFICIAL_HYPE":
		score -= 0.20
		reasons.append("Authenticity analysis warns of hype risk")

	if pipeline_evidence["phase"] in ["GROWTH", "PEAK"]:
		score += 0.10
		reasons.append("Lifecycle phase suggests active consumer interest")
	elif pipeline_evidence["phase"] == "DECLINE":
		score -= 0.10
		reasons.append("Lifecycle phase suggests weakening demand")

	observed_marketplaces = 0
	if amazon_evidence.get("observed"):
		observed_marketplaces += 1
		score += 0.20
		reasons.append("Amazon search metadata directly observed")
	elif amazon_evidence.get("evidence_type") == "inferred/proxy":
		score += 0.05
		reasons.append("Amazon evidence is proxy-only")

	if myntra_evidence.get("observed"):
		observed_marketplaces += 1
		score += 0.20
		reasons.append("Myntra search metadata directly observed")
	elif myntra_evidence.get("evidence_type") == "inferred/proxy":
		score += 0.05
		reasons.append("Myntra evidence is proxy-only")

	if observed_marketplaces == 0:
		reasons.append("No directly observed marketplace evidence")

	if pipeline_evidence["source_diversity"] >= 0.5:
		score += 0.05
		reasons.append("Pipeline evidence spans multiple source types")

	if signal.get("affected_business_areas"):
		score += 0.05
		reasons.append("Trend has explicit business-area applicability")

	return round(clamp(score), 3), reasons


def classify_commercial_signal(score):
	if score >= 0.70:
		return "HIGH", COMMERCIAL_LEVELS["HIGH"]
	if score >= 0.45:
		return "MEDIUM", COMMERCIAL_LEVELS["MEDIUM"]
	if score >= 0.20:
		return "LOW", COMMERCIAL_LEVELS["LOW"]
	return "NONE", COMMERCIAL_LEVELS["NONE"]


def determine_validation_status(score, amazon_evidence, myntra_evidence):
	observed_count = sum(1 for item in [amazon_evidence, myntra_evidence] if item.get("observed"))
	available_count = sum(
		1 for item in [amazon_evidence, myntra_evidence]
		if item.get("evidence_type") != "unavailable"
	)

	if available_count == 0:
		return "PROXY_ONLY", VALIDATION_STATUSES["PROXY_ONLY"]

	if score >= 0.70 and observed_count >= 1:
		return "VALIDATED", VALIDATION_STATUSES["VALIDATED"]
	if score >= 0.45:
		return "PROBABLE", VALIDATION_STATUSES["PROBABLE"]
	if amazon_evidence.get("evidence_type") == "inferred/proxy" or myntra_evidence.get("evidence_type") == "inferred/proxy":
		return "PROXY_ONLY", VALIDATION_STATUSES["PROXY_ONLY"]
	return "UNVERIFIED", VALIDATION_STATUSES["UNVERIFIED"]


def infer_demand_indicators(signal, pipeline_evidence, amazon_evidence, myntra_evidence):
	indicators = []

	if signal.get("affected_business_areas"):
		indicators.append("commercial_use_case_present")
	if pipeline_evidence["industry_impact_score"] >= 0.40:
		indicators.append("upstream_business_impact")
	if pipeline_evidence["authenticity_level"] in ["GENUINE", "LIKELY_GENUINE"]:
		indicators.append("durable_interest_signal")
	if pipeline_evidence["phase"] in ["GROWTH", "PEAK"]:
		indicators.append("active_market_momentum")
	if amazon_evidence.get("evidence_type") == "directly_observed":
		indicators.append("amazon_metadata_present")
	if myntra_evidence.get("evidence_type") == "directly_observed":
		indicators.append("myntra_metadata_present")
	if amazon_evidence.get("evidence_type") == "unavailable" and myntra_evidence.get("evidence_type") == "unavailable":
		indicators.append("marketplace_unavailable")

	return indicators


def infer_revenue_potential(signal, commercial_signal_level, validation_status):
	if commercial_signal_level == "HIGH" and validation_status == "VALIDATED":
		return "HIGH"
	if commercial_signal_level in ["HIGH", "MEDIUM"] and validation_status in ["VALIDATED", "PROBABLE"]:
		return "MEDIUM"
	if commercial_signal_level == "LOW" and validation_status in ["PROXY_ONLY", "UNVERIFIED"]:
		return "LOW"
	if signal.get("signal_strength") == "NOISE":
		return "LOW"
	return "UNCLEAR"


def build_financial_reasoning(signal, pipeline_evidence, marketplace_evidence, commercial_signal_level, validation_status, revenue_potential, marketplace_score):
	reasoning = []
	impact_score = signal.get("industry_impact_score")
	reasoning.append(
		f"Industry impact score: {impact_score:.3f}"
		if impact_score is not None
		else "Industry impact score: N/A (insufficient upstream evidence)"
	)
	reasoning.append(f"Commercial signal level: {commercial_signal_level}")
	reasoning.append(f"Validation status: {validation_status}")
	reasoning.append(f"Marketplace score: {marketplace_score:.3f}")
	reasoning.append(f"Lifecycle phase: {pipeline_evidence['phase']}")
	reasoning.append(f"Authenticity level: {pipeline_evidence['authenticity_level']}")

	observed = [item["marketplace"] for item in marketplace_evidence if item.get("evidence_type") == "directly_observed"]
	proxy = [item["marketplace"] for item in marketplace_evidence if item.get("evidence_type") == "inferred/proxy"]
	unavailable = [item["marketplace"] for item in marketplace_evidence if item.get("evidence_type") == "unavailable"]

	if observed:
		reasoning.append(f"Direct marketplace observation: {', '.join(observed)}")
	if proxy:
		reasoning.append(f"Proxy marketplace evidence: {', '.join(proxy)}")
	if unavailable:
		reasoning.append(f"Unavailable marketplace evidence: {', '.join(unavailable)}")

	reasoning.append(f"Revenue potential: {revenue_potential}")

	if pipeline_evidence["authenticity_level"] == "ARTIFICIAL_HYPE":
		reasoning.append("Conservative valuation applied because hype risk is elevated")

	return reasoning


def run_financial_validation(signals=None, run_config=None):
	if run_config is not None:
		from agents.configured_analysis import commercial
		return commercial(signals or [], run_config)
	print("\n" + "=" * 50)
	print("  COMMERCIAL POTENTIAL AGENT RUNNING")
	print("=" * 50)

	if signals is None:
		signals = load_industry_impact_results()

	if not signals:
		print("  No signals to analyse.")
		return []

	print(f"\n  Validating commercial potential for {len(signals)} trends...\n")

	validation_results = []

	for signal in signals:
		keyword = signal.get("keyword", "")
		pipeline_evidence = get_pipeline_evidence(signal)
		amazon_evidence, myntra_evidence, marketplace_evidence = build_marketplace_evidence(keyword)
		marketplace_score, marketplace_reasoning = score_marketplace_signal(
			amazon_evidence,
			myntra_evidence,
			pipeline_evidence,
			signal,
		)
		commercial_signal_level, commercial_description = classify_commercial_signal(marketplace_score)
		validation_status, validation_description = determine_validation_status(
			marketplace_score,
			amazon_evidence,
			myntra_evidence,
		)
		demand_indicators = infer_demand_indicators(signal, pipeline_evidence, amazon_evidence, myntra_evidence)
		revenue_potential = infer_revenue_potential(signal, commercial_signal_level, validation_status)
		financial_reasoning = build_financial_reasoning(
			signal,
			pipeline_evidence,
			marketplace_evidence,
			commercial_signal_level,
			validation_status,
			revenue_potential,
			marketplace_score,
		)
		commercial_potential_score = round(clamp(
			marketplace_score * 0.45
			+ float(signal.get("industry_impact_score", 0.0) or 0.0) * 0.25
			+ (1.0 if pipeline_evidence["phase"] in ["GROWTH", "PEAK"] else 0.0) * 0.10
			+ (1.0 if pipeline_evidence["authenticity_level"] in ["GENUINE", "LIKELY_GENUINE"] else 0.0) * 0.10
			+ (1.0 if signal.get("signal_strength") in ["STRONG", "MODERATE"] else 0.0) * 0.10
		), 3)
		observed_marketplace_count = sum(
			1 for item in [amazon_evidence, myntra_evidence]
			if item.get("observed")
		)

		result = dict(signal)
		result.update({
			"commercial_potential_score": commercial_potential_score,
			# Compatibility alias for existing decision-engine consumers.
			"financial_validation_score": commercial_potential_score,
			"financial_validation_available": False,
			"commercial_potential_available": True,
			"commercial_potential_confidence": (
				"HIGH" if validation_status == "VALIDATED" and observed_marketplace_count >= 1
				else "MEDIUM" if validation_status == "PROBABLE" and observed_marketplace_count >= 1
				else "LOW"
			),
			"score_type": "commercial_potential_proxy",
			"commercial_signal_level": commercial_signal_level,
			"commercial_signal_description": commercial_description,
			"validation_status": validation_status,
			"validation_description": validation_description,
			"marketplace_evidence": marketplace_evidence,
			"amazon_evidence": amazon_evidence,
			"myntra_evidence": myntra_evidence,
			"demand_indicators": demand_indicators,
			"revenue_potential": revenue_potential,
			"financial_reasoning": financial_reasoning + marketplace_reasoning,
			"analysed_at": datetime.now().isoformat(),
		})
		validation_results.append(result)

	validation_results.sort(key=lambda x: (x.get("commercial_potential_score", 0), x.get("industry_impact_score", 0)), reverse=True)

	print("  Commercial potential analysis complete.\n")
	return validation_results


# Backward-compatible name for existing callers.
run_commercial_potential_analysis = run_financial_validation


def print_financial_summary(validation_results):
	print("\n" + "=" * 50)
	print("  COMMERCIAL POTENTIAL ANALYSIS")
	print("=" * 50)

	levels = ["HIGH", "MEDIUM", "LOW", "NONE"]

	for level in levels:
		items = [item for item in validation_results if item.get("commercial_signal_level") == level]
		if not items:
			continue

		print(f"\n  [{level}] — {len(items)} trends")
		print("  " + "-" * 48)

		for item in items[:5]:
			print(
				f"  {item['keyword']:<28} "
				f"score: {item['commercial_potential_score']:.3f}  "
				f"status: {item['validation_status']}"
			)
			amazon_state = item.get("amazon_evidence", {}).get("evidence_type", "unavailable")
			myntra_state = item.get("myntra_evidence", {}).get("evidence_type", "unavailable")
			print(f"       Amazon: {amazon_state} | Myntra: {myntra_state}")

	print("\n  Top 10 overall by commercial potential:")
	print("  " + "-" * 48)
	for i, item in enumerate(validation_results[:10], 1):
		print(
			f"  {i:2}. {item['keyword']:<28} "
			f"{item['commercial_signal_level']:<6} {item['commercial_potential_score']:.3f}"
		)


if __name__ == "__main__":
	signals = load_industry_impact_results()
	validation_results = run_commercial_potential_analysis(signals)
	print_financial_summary(validation_results)

	os.makedirs(PROCESSED_DIR, exist_ok=True)
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filepath = os.path.join(PROCESSED_DIR, f"commercial_potential_{timestamp}.json")

	with open(filepath, "w", encoding="utf-8") as f:
		json.dump(validation_results, f, indent=2, ensure_ascii=False)

	print(f"\n  Results saved to: {filepath}")
