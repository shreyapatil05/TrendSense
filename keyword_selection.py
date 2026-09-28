"""Manual/preset selection and opt-in related-query suggestions."""
import argparse
import json
from pathlib import Path
import unicodedata


def clean_keywords(values):
    if not isinstance(values, list):
        raise ValueError("keywords.selected must be a JSON list")
    result, seen = [], set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("Each keyword must be text")
        value = " ".join(unicodedata.normalize("NFKC", value).split())
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    if not result:
        raise ValueError("Select at least one keyword. No automatic 55-keyword fallback.")
    return result


def parse_keyword_arguments(values):
    """Accept quoted CLI values and comma-separated lists without a size limit."""
    if not values:
        return None
    expanded = []
    for value in values:
        expanded.extend(value.split(","))
    return clean_keywords(expanded)


def load_keyword_file(path):
    """Read either a JSON list or one/comma-separated keyword per line."""
    source = Path(path)
    if not source.exists():
        raise ValueError(f"Keyword file not found: {source}")
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("Keyword file is empty")
    if source.suffix.lower() == ".json":
        return clean_keywords(json.loads(text))
    values = []
    for line in text.splitlines():
        values.extend(line.split(","))
    return clean_keywords(values)


def select_keywords(cfg):
    spec = cfg["keywords"]
    if spec["selection_mode"] == "manual":
        return clean_keywords(spec["selected"])
    if spec["selection_mode"] == "preset":
        from config import INDUSTRY_TAGS
        name = spec.get("preset_name") or cfg["industry"]
        if name not in INDUSTRY_TAGS:
            raise ValueError(f"No preset for {name}; use manual selection")
        return clean_keywords(INDUSTRY_TAGS[name])
    raise ValueError("selection_mode must be manual or preset")


def related_suggestions(keyword, geo="IN"):
    from pytrends.request import TrendReq
    client = TrendReq(hl="en-IN", tz=330, timeout=(10, 30))
    client.build_payload([keyword], timeframe="today 3-m", geo=geo)
    tables = client.related_queries().get(keyword, {})
    return sorted({str(q) for table in tables.values() if table is not None
                   for q in table.get("query", [])})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Suggestions only; never modifies the selection")
    parser.add_argument("--suggest", required=True)
    parser.add_argument("--geo", default="IN")
    args = parser.parse_args()
    try:
        print(json.dumps(related_suggestions(args.suggest, args.geo), indent=2))
    except Exception as exc:
        parser.exit(1, f"Suggestions unavailable: {exc}. Manual selection still works.\n")
