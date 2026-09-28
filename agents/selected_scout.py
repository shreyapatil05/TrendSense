"""Focused collection using selected terms, with per-source health reporting."""
import re
from urllib.parse import quote
import pandas as pd
from runtime_config import paths, save_json


def filter_signals(signals, keywords, start=None, end=None):
    output = []
    for signal in signals:
        # Match content rather than injected seed_topic/query metadata.
        text = " ".join(str(signal.get(k, "") or "") for k in ("title", "description", "summary", "suggestion", "keyword")).casefold()
        matched = [k for k in keywords if re.search(r"(?<!\w)" + re.escape(k.casefold()) + r"(?!\w)", text)]
        if not matched:
            continue
        date = signal.get("published_at") or signal.get("publishedAt") or signal.get("published")
        date = pd.to_datetime(date, utc=True, errors="coerce") if date else pd.NaT
        if start is not None:
            # Undated content cannot be asserted to belong to the selected period.
            if pd.isna(date) or date < start or date >= end + pd.Timedelta(days=1):
                continue
        output.append({**signal, "url": signal.get("url") or signal.get("link") or
                       (f"https://www.youtube.com/watch?v={signal['video_id']}" if signal.get("video_id") else None),
                       "matched_keywords": matched, "published_at": date.isoformat() if not pd.isna(date) else None})
    # Canonical URL duplicate removal avoids counting the same story from RSS and NewsAPI twice.
    unique = {}
    for s in output:
        key = s.get("url") or s.get("link") or (s.get("source"), s.get("title"), s.get("suggestion"))
        unique[key] = s
    return list(unique.values())


def collect_selected(cfg, start, end, history_path=None):
    import requests
    import feedparser
    from config import NEWS_API_KEY
    from agents.scout_agent import fetch_youtube_shorts
    keywords = cfg["keywords"]["selected"]
    signals, health = [], {}
    print(f"\n[SCOUT] Collecting evidence for {len(keywords)} selected keywords from {start.date()} through {end.date()}")
    print("[SCOUT SOURCE 1/4] YouTube Shorts and videos")
    try:
        youtube = fetch_youtube_shorts(
            keywords, selected_keywords=keywords,
            published_after=start.isoformat().replace("+00:00", "Z"),
            published_before=(end + pd.Timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            region=cfg["collection"]["country"],
            content_modes=["shorts", "videos"],
        )
        signals.extend(youtube)
        health["youtube"] = {"retrieved": len(youtube), "by_type": {
            "shorts": sum(x.get("source") == "youtube_shorts" for x in youtube),
            "videos": sum(x.get("source") == "youtube_videos" for x in youtube)}}
    except Exception as exc:
        health["youtube"] = {"error": str(exc)}
    rss_count, news_count = 0, 0
    errors = []
    print("[SCOUT SOURCE 2/4] Google News RSS articles")
    for keyword in keywords:
        print(f"[SCOUT] Google News RSS query: {keyword}")
        try:
            query = f'{keyword} after:{start.date()} before:{(end + pd.Timedelta(days=1)).date()}'
            response = requests.get("https://news.google.com/rss/search", params={"q": query, "hl": cfg["collection"]["language"],
                "gl": cfg["collection"]["country"], "ceid": cfg["collection"]["country"] + ":en"}, timeout=20)
            response.raise_for_status()
            for entry in feedparser.parse(response.content).entries:
                signals.append({"source": "rss_feed", "title": entry.get("title", ""), "summary": entry.get("summary", ""),
                                "url": entry.get("link"), "published_at": entry.get("published")})
                rss_count += 1
        except Exception as exc:
            errors.append({"source": "rss", "keyword": keyword, "error": str(exc)})
        if NEWS_API_KEY:
            if news_count == 0:
                print("[SCOUT SOURCE 3/4] NewsAPI articles")
            print(f"[SCOUT] NewsAPI query: {keyword}")
            try:
                response = requests.get("https://newsapi.org/v2/everything", headers={"X-Api-Key": NEWS_API_KEY},
                    params={"q": keyword, "from": str(start.date()), "to": str(end.date()), "language": "en", "pageSize": 20}, timeout=20)
                response.raise_for_status()
                for article in response.json().get("articles", []):
                    signals.append({**article, "source": "newsapi", "published_at": article.get("publishedAt")})
                    news_count += 1
            except Exception as exc:
                errors.append({"source": "newsapi", "keyword": keyword, "error": str(exc)})
    if not NEWS_API_KEY:
        print("[SCOUT SOURCE 3/4] NewsAPI skipped: NEWS_API_KEY is not configured")

    # Google Trends is collected separately as a daily time series for the ML
    # forecaster. Report it here so the complete multi-source run is visible.
    try:
        # A subset run can reuse a compatible superset model. In that case,
        # read the resolved model's history instead of a nonexistent subset path.
        history = pd.read_csv(history_path or paths(cfg)["history"])
        history = history[history.keyword.isin(keywords)]
        trends_count = len(history)
        print(f"[SCOUT SOURCE 4/4] Google Trends: {trends_count} daily observations loaded")
        health["google_trends"] = {
            "observations": trends_count,
            "keywords": int(history.keyword.nunique()),
            "purpose": "time-series training and forecasting",
        }
    except Exception as exc:
        trends_count = 0
        errors.append({"source": "google_trends", "error": str(exc)})
        print(f"[SCOUT SOURCE 4/4] Google Trends unavailable: {exc}")

    selected = filter_signals(signals, keywords, start, end)
    print(f"[SCOUT] Collected: YouTube Shorts={health.get('youtube', {}).get('by_type', {}).get('shorts', 0)}, "
          f"YouTube videos={health.get('youtube', {}).get('by_type', {}).get('videos', 0)}, "
          f"RSS entries={rss_count}, NewsAPI articles={news_count}, "
          f"Google Trends rows={trends_count}; "
          f"{len(selected)} dated, keyword-matched unique evidence items retained")
    health.update({"rss_retrieved": rss_count, "news_retrieved": news_count, "errors": errors,
                   "selected_evidence": len(selected), "keywords": keywords,
                   "note": "No claim of exhaustive historical article/video coverage; APIs have retrieval limits"})
    save_json(paths(cfg)["data"] / "scout_health.json", health)
    return selected
