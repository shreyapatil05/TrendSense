"""Pretrained Hugging Face semantic matching for unstructured evidence."""
from collections import defaultdict

from config import SEMANTIC_MODEL_NAME, SEMANTIC_RELEVANCE_THRESHOLD

TEXT_SOURCES = {"youtube_shorts", "youtube_videos", "newsapi", "rss_feed", "google_autocomplete"}


def _signal_text(signal):
    fields = ("title", "description", "summary", "suggestion", "seed_topic")
    return " ".join(str(signal.get(field, "") or "") for field in fields).strip()


def run_semantic_evidence_analysis(trend_results, raw_signals, enabled=True, run_config=None):
    if not enabled:
        return [{"keyword": item.get("keyword"), "semantic_status": "DISABLED"}
                for item in trend_results]
    candidates = []
    for signal in raw_signals:
        if signal.get("source") not in TEXT_SOURCES:
            continue
        # A query/seed is not document evidence of relevance.
        text = " ".join(str(signal.get(f, "") or "") for f in ("title", "description", "summary", "suggestion")) if run_config else _signal_text(signal)
        if text:
            candidates.append({
                "text": text[:1000], "source": signal.get("source", "unknown"),
                "url": signal.get("url") or signal.get("link"),
            })
    if not candidates:
        return [{"keyword": item.get("keyword"), "semantic_status": "UNAVAILABLE",
                 "semantic_warning": "No unstructured evidence was collected"}
                for item in trend_results]
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return [{"keyword": item.get("keyword"), "semantic_status": "UNAVAILABLE",
                 "semantic_warning": "Install sentence-transformers and torch"}
                for item in trend_results]

    try:
        model = SentenceTransformer(SEMANTIC_MODEL_NAME)
        keywords = [item.get("keyword", "") for item in trend_results]
        keyword_vectors = model.encode(keywords, normalize_embeddings=True, show_progress_bar=False)
        evidence_vectors = model.encode(
            [item["text"] for item in candidates],
            normalize_embeddings=True, show_progress_bar=False, batch_size=32,
        )
    except Exception as exc:
        return [{"keyword": item.get("keyword"), "semantic_status": "UNAVAILABLE",
                 "semantic_warning": f"Semantic model could not load: {exc}"}
                for item in trend_results]
    similarity = keyword_vectors @ evidence_vectors.T
    results = []
    for keyword_index, keyword in enumerate(keywords):
        threshold = SEMANTIC_RELEVANCE_THRESHOLD
        if run_config:
            import numpy as np
            scores = similarity[keyword_index]
            threshold = float(np.median(scores) + np.median(np.abs(scores - np.median(scores))))
        ranked = sorted(
            [(float(similarity[keyword_index][i]), candidates[i])
             for i in range(len(candidates))],
            key=lambda pair: pair[0], reverse=True,
        )
        relevant = []
        source_best = defaultdict(float)
        for score, evidence in ranked:
            if score < threshold or (run_config and score <= threshold):
                continue
            source_best[evidence["source"]] = max(source_best[evidence["source"]], score)
            if len(relevant) < 8:
                relevant.append({
                    "source": evidence["source"], "similarity": round(score, 4),
                    "text": evidence["text"][:300], "url": evidence["url"],
                })
        agreement = sum(source_best.values()) / len(source_best) if source_best else 0.0
        results.append({
            "keyword": keyword, "semantic_status": "READY",
            "semantic_model": SEMANTIC_MODEL_NAME,
            "semantic_relevance_threshold": threshold,
            "semantic_threshold_method": "candidate_median_plus_MAD_uncalibrated" if run_config else "legacy_fixed",
            "semantic_evidence_count": len(relevant),
            "semantic_source_count": len(source_best),
            "semantic_agreement_score": round(agreement, 4),
            "semantic_relevant_evidence": relevant,
            "semantic_conflict": len(source_best) < 2,
        })
    return results
