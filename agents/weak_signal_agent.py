import json
import os
import sys
from datetime import datetime
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ALL_KEYWORDS,
    FASHION_KEYWORDS,
    BEAUTY_KEYWORDS,
    VELOCITY_THRESHOLD,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    DATA_DIR,
    PROCESSED_DIR
)



# SCORING WEIGHTS
# How much each source contributes to
# the final trend score


WEIGHTS = {
    "google_trends":          0.30,  # most reliable signal
    "wikipedia_pageviews":    0.20,  # mainstream awareness
    "youtube_shorts":         0.20,  # content creation activity
    "newsapi":                0.15,  # editorial coverage
    "rss_feed":               0.10,  # publication mentions
    "google_autocomplete":    0.05,  # search intent
}



# LOAD LATEST SIGNALS

def load_latest_signals():
    if not os.path.exists(DATA_DIR):
        print(f"  [WeakSignal] Data directory not found: {DATA_DIR}")
        return []

    files = [
        f for f in os.listdir(DATA_DIR)
        if f.startswith("signals_") and f.endswith(".json")
    ]

    if not files:
        print("  No signal files found. Run scout_agent.py first.")
        return []

    latest_file = sorted(files)[-1]
    filepath = os.path.join(DATA_DIR, latest_file)

    with open(filepath, "r", encoding="utf-8") as f:
        signals = json.load(f)

    print(f"  Loaded {len(signals)} signals from {latest_file}")
    return signals



# SCORE: GOOGLE TRENDS

def score_google_trends(signals, keyword):
    """
    Scores based on search velocity in India.
    Zero velocity = zero score. Rising velocity = high score.
    """
    matches = [
        s for s in signals
        if s["source"] == "google_trends"
        and s.get("keyword", "").lower() == keyword.lower()
    ]

    health = next(
        (s for s in signals if s.get("source") == "scout_health"),
        {}
    )

    if not matches:
        return 0.0, {
            "available": False,
            "velocity": 0,
            "recent_avg": 0,
            "historical_avg": None,
            "previous_avg": None,
            "acceleration": None,
            "observations": 0,
            "rising": False,
            "reason": "google_trends_data_unavailable",
            "scout_coverage": health.get("google_trends_coverage")
        }

    s = matches[0]
    velocity = s.get("velocity", 0)
    recent_avg = s.get("recent_avg", 0)
    historical_avg = s.get("historical_avg", s.get("overall_avg"))
    previous_avg = s.get("previous_avg")
    acceleration = s.get("acceleration")
    observations = s.get("observations", 0)
    rising = bool(s.get("rising", velocity >= VELOCITY_THRESHOLD))

    # If no search interest at all in India — score is 0
    if s.get("peak_value", 0) == 0:
        return 0.0, {
            "available": True,
            "velocity": velocity,
            "recent_avg": recent_avg,
            "historical_avg": historical_avg,
            "previous_avg": previous_avg,
            "acceleration": acceleration,
            "observations": observations,
            "rising": False
        }

    # Velocity score — positive velocity gets rewarded, negative penalized
    if velocity >= 20:
        velocity_score = 1.0
    elif velocity >= 10:
        velocity_score = 0.85
    elif velocity >= 5:
        velocity_score = 0.70
    elif velocity >= 2:
        velocity_score = 0.55
    elif velocity >= 0:
        velocity_score = 0.40
    elif velocity >= -5:
        velocity_score = 0.20
    else:
        velocity_score = 0.10

    # Recency bonus: high recent average = trend is active right now
    recency_bonus = min(recent_avg / 100.0, 0.25)

    raw_score = (velocity_score * 0.75) + recency_bonus

    return round(min(raw_score, 1.0), 3), {
        "available": True,
        "velocity": velocity,
        "recent_avg": recent_avg,
        "historical_avg": historical_avg,
        "previous_avg": previous_avg,
        "acceleration": acceleration,
        "observations": observations,
        "rising": rising
    }



# SCORE: WIKIPEDIA

def score_wikipedia(signals, keyword):
    """
    Scores based on Wikipedia page view velocity.
    Rising views = trend reaching mainstream awareness.
    This is a confirmation signal — not early detection.
    """
    # Check pageview velocity for matching pages
    wiki_matches = [
        s for s in signals
        if s["source"] == "wikipedia_pageviews"
        and (
            keyword.lower() in s.get("page", "").lower()
            or s.get("page", "").lower() in keyword.lower()
            or keyword.lower() in [
                k.lower() for k in s.get("matched_keywords", [])
            ]
        )
    ]

    if not wiki_matches:
        return 0.0, {"wiki_velocity": 0, "avg_daily": 0, "rising": False}

    # Take the best matching page
    best = max(wiki_matches, key=lambda x: x.get("recent_avg_daily", 0))

    wiki_velocity = best.get("velocity", 0)
    avg_daily = best.get("recent_avg_daily", 0)
    rising = best.get("rising", False)

    # Normalize: velocity of 200+ views/day = strong signal
    velocity_score = min(max(wiki_velocity, 0) / 200.0, 1.0)

    # Volume bonus: high daily views means relevant topic
    volume_bonus = min(avg_daily / 1000.0, 0.3)

    raw_score = (velocity_score * 0.7) + volume_bonus

    return round(min(raw_score, 1.0), 3), {
        "wiki_velocity": wiki_velocity,
        "avg_daily": avg_daily,
        "page": best.get("page", ""),
        "rising": rising
    }


# SCORE: YOUTUBE

def score_youtube(signals, keyword):
    """
    Scores YouTube by checking if the keyword appears
    in video titles/descriptions OR if the seed topic
    is closely related to the keyword category.
    """
    youtube_signals = [
        s for s in signals
        if s["source"] == "youtube_shorts"
    ]

    mention_count = 0
    recent_count = 0

    for s in youtube_signals:
        content = (
            s.get("title", "") + " " +
            s.get("description", "") + " " +
            s.get("seed_topic", "")
        ).lower()

        # Direct keyword match
        if keyword.lower() in content:
            mention_count += 2  # direct match = stronger signal

            try:
                pub = datetime.fromisoformat(
                    s["published_at"].replace("Z", "+00:00")
                )
                now = datetime.now().astimezone()
                hours_ago = (now - pub).total_seconds() / 3600
                if hours_ago <= 48:
                    recent_count += 1
            except Exception:
                pass

        # Partial word match — e.g "saree" in "saree draping"
        keyword_words = keyword.lower().split()
        if any(word in content for word in keyword_words if len(word) > 4):
            mention_count += 1

        # Check matched_keywords field
        if keyword in s.get("matched_keywords", []):
            mention_count += 2

    raw_score = (mention_count * 0.3) + (recent_count * 1.0)
    normalized = min(raw_score / 10.0, 1.0)

    return round(normalized, 3), {
        "mention_count": mention_count,
        "recent_48h": recent_count
    }



# SCORE: NEWS + RSS

def score_news(signals, keyword):
    """
    Scores based on how many news articles and
    RSS feed posts mention this keyword.
    Editorial coverage = trend gaining legitimacy.
    """
    news_signals = [
        s for s in signals
        if s["source"] in ["newsapi", "rss_feed"]
    ]

    mention_count = 0

    for s in news_signals:
        content = (
            str(s.get("title", "")) + " " +
            str(s.get("description", "")) + " " +
            str(s.get("summary", ""))
        ).lower()

        if keyword.lower() in content:
            mention_count += 1

        if keyword in s.get("matched_keywords", []):
            mention_count += 1

    # Normalize: 5+ mentions = max score
    normalized = min(mention_count / 5.0, 1.0)

    return round(normalized, 3), {
        "mention_count": mention_count
    }



# SCORE: GOOGLE AUTOCOMPLETE

def score_autocomplete(signals, keyword):
    """
    Scores based on how many Google autocomplete
    suggestions relate to this keyword.
    High autocomplete presence = people actively
    searching for this right now.
    """
    autocomplete_signals = [
        s for s in signals
        if s["source"] == "google_autocomplete"
    ]

    match_count = sum(
        1 for s in autocomplete_signals
        if keyword.lower() in s.get("suggestion", "").lower()
        or s.get("seed_query", "").strip().lower() in keyword.lower()
    )

    normalized = min(match_count / 5.0, 1.0)

    return round(normalized, 3), {
        "autocomplete_matches": match_count
    }



# CROSS PLATFORM BONUS

def calculate_cross_platform_bonus(source_scores):
    """
    Bonus when a trend appears across multiple sources.
    Signal on 4+ sources = very strong confirmation.
    """
    active = sum(1 for score in source_scores.values() if score > 0.05)

    if active >= 4:
        return 0.20
    elif active == 3:
        return 0.12
    elif active == 2:
        return 0.05
    else:
        return 0.0



# CLASSIFY SIGNAL STRENGTH

def classify_signal(final_score):
    if final_score >= CONFIDENCE_HIGH:
        return "STRONG", "High confidence emerging trend — recommend action"
    elif final_score >= CONFIDENCE_MEDIUM:
        return "MODERATE", "Possible emerging trend — monitor closely"
    elif final_score >= 0.15:
        return "WEAK", "Early whisper — insufficient cross-platform confirmation"
    else:
        return "NOISE", "No meaningful signal detected"


def has_measured_evidence(gt_detail, wiki_score, yt_score, news_score, ac_score):
    """Return false when the only missing component is unavailable Trends data."""
    return bool(
        gt_detail.get("available", False)
        or wiki_score > 0
        or yt_score > 0
        or news_score > 0
        or ac_score > 0
    )



# DETECT INDUSTRY

def detect_industry(keyword):
    if keyword in FASHION_KEYWORDS:
        return "fashion"
    elif keyword in BEAUTY_KEYWORDS:
        return "beauty"
    else:
        return "unknown"



# MAIN: ANALYSE ALL KEYWORDS

def run_weak_signal_detection(signals=None, run_config=None):
    if run_config is not None:
        from agents.configured_analysis import weak
        return weak(signals or [], run_config)
    print("\n" + "="*50)
    print("  WEAK SIGNAL AGENT RUNNING")
    print("="*50)

    if signals is None:
        signals = load_latest_signals()

    if not signals:
        print("  No signals to analyse.")
        return []

    print(f"\n  Analysing {len(ALL_KEYWORDS)} keywords...\n")

    trend_scores = []

    for keyword in ALL_KEYWORDS:
        # Score from each source
        gt_score,   gt_detail   = score_google_trends(signals, keyword)
        wiki_score, wiki_detail = score_wikipedia(signals, keyword)
        yt_score,   yt_detail   = score_youtube(signals, keyword)
        news_score, news_detail = score_news(signals, keyword)
        ac_score,   ac_detail   = score_autocomplete(signals, keyword)

        source_scores = {
            "google_trends":       gt_score,
            "wikipedia":           wiki_score,
            "youtube":             yt_score,
            "news":                news_score,
            "autocomplete":        ac_score,
        }

        # Renormalize when Trends is unavailable. Missing data must not lower
        # the score as if measured zero interest had been observed.
        components = [
            (gt_score, WEIGHTS["google_trends"], gt_detail.get("available", True)),
            (wiki_score, WEIGHTS["wikipedia_pageviews"], True),
            (yt_score, WEIGHTS["youtube_shorts"], True),
            (news_score, WEIGHTS["newsapi"] + WEIGHTS["rss_feed"], True),
            (ac_score, WEIGHTS["google_autocomplete"], True),
        ]
        available_weight = sum(weight for _, weight, available in components if available)
        weighted_score = (
            sum(score * weight for score, weight, available in components if available)
            / available_weight
            if available_weight
            else 0.0
        )

        measured_evidence = has_measured_evidence(
            gt_detail, wiki_score, yt_score, news_score, ac_score
        )

        # A missing Trends result plus no supporting source is not a measured
        # zero. Keep it explicit so downstream decisions cannot call it noise.
        if not measured_evidence:
            cross_bonus = 0.0
            final_score = None
            signal_strength = "INSUFFICIENT_DATA"
            description = "Insufficient evidence: Google Trends data was unavailable and no supporting source matched."
            evidence_status = "INSUFFICIENT_DATA"
        else:
            cross_bonus = calculate_cross_platform_bonus(source_scores)
            final_score = min(weighted_score + cross_bonus, 1.0)
            signal_strength, description = classify_signal(final_score)
            evidence_status = "MEASURED"

        # Industry tag
        industry = detect_industry(keyword)

        trend_scores.append({
            "keyword":         keyword,
            "industry":        industry,
            "final_score":     round(final_score, 3) if final_score is not None else None,
            "evidence_status": evidence_status,
            "signal_strength": signal_strength,
            "description":     description,
            "source_scores":   source_scores,
            "cross_bonus":     cross_bonus,
            "details": {
                "google_trends": gt_detail,
                "wikipedia":     wiki_detail,
                "youtube":       yt_detail,
                "news":          news_detail,
                "autocomplete":  ac_detail,
            },
            "analysed_at": datetime.now().isoformat()
        })

    # Sort by final score
    trend_scores.sort(key=lambda x: x["final_score"] if x["final_score"] is not None else -1, reverse=True)

    print("  Analysis complete.\n")
    return trend_scores



# SUMMARY PRINTER

def print_weak_signal_summary(trend_scores):
    print("\n" + "="*50)
    print("  TREND SIGNAL RANKINGS")
    print("="*50)

    categories = ["STRONG", "MODERATE", "WEAK", "NOISE"]

    for category in categories:
        items = [t for t in trend_scores if t["signal_strength"] == category]
        if not items:
            continue

        print(f"\n  [{category}] — {len(items)} keywords")
        print("  " + "-"*48)

        for item in items:
            ind = "F" if item["industry"] == "fashion" else "B"
            scores = item["source_scores"]

            print(
                f"  [{ind}] {item['keyword']:<28} "
                f"score: {item['final_score']}"
            )
            print(
                f"       GT:{scores['google_trends']:.2f}  "
                f"Wiki:{scores['wikipedia']:.2f}  "
                f"YT:{scores['youtube']:.2f}  "
                f"News:{scores['news']:.2f}  "
                f"AC:{scores['autocomplete']:.2f}  "
                f"Bonus:{item['cross_bonus']:.2f}"
            )

            # Show Google Trends velocity
            gt = item["details"]["google_trends"]
            if gt["velocity"] != 0:
                print(f"       Google velocity: {gt['velocity']}  "
                      f"recent avg: {gt['recent_avg']}")

            # Show Wikipedia info if relevant
            wiki = item["details"]["wikipedia"]
            if wiki["avg_daily"] > 0:
                status = "RISING" if wiki["rising"] else "stable"
                print(f"       Wikipedia: {wiki['page']} — "
                      f"{wiki['avg_daily']:.0f} views/day [{status}]")

            # Show news mentions
            if item["details"]["news"]["mention_count"] > 0:
                print(f"       News mentions: {item['details']['news']['mention_count']}")

    print("\n  Top 10 overall:")
    print("  " + "-"*48)
    for i, item in enumerate(trend_scores[:10], 1):
        ind = "F" if item["industry"] == "fashion" else "B"
        print(
            f"  {i:2}. [{ind}] {item['keyword']:<28} "
            f"{item['final_score']}  [{item['signal_strength']}]"
        )



# ENTRY POINT

if __name__ == "__main__":
    signals = load_latest_signals()
    trend_scores = run_weak_signal_detection(signals)
    print_weak_signal_summary(trend_scores)

    # Save results
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(PROCESSED_DIR, f"weak_signals_{timestamp}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(trend_scores, f, indent=2, ensure_ascii=False)

    print(f"\n  Results saved to: {filepath}")
