import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["TRENDSENSE_OFFLINE"] = "1"

def sample_signals():
    from config import ALL_KEYWORDS
    rows = []
    for index, keyword in enumerate(ALL_KEYWORDS):
        recent = 30 + (index % 20)
        previous = 20 + (index % 10)
        velocity = recent - previous
        rows.append({
            "source": "google_trends", "keyword": keyword, "geo": "IN",
            "velocity": velocity, "recent_avg": recent,
            "previous_avg": previous, "historical_avg": 18 + (index % 8),
            "acceleration": 2.0, "observations": 30, "peak_value": 70,
            "rising": True, "data_status": "fixture"
        })
    rows.append({"source": "scout_health", "google_trends_coverage": 1.0})
    return rows
