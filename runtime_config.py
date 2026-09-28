"""Validate an experiment configuration and isolate its artifacts."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def load_config(path="run_config.json"):
    from keyword_selection import select_keywords
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg["industry"] = cfg["industry"].strip().lower()
    if not cfg["industry"]:
        raise ValueError("Industry is required")
    cfg["keywords"]["selected"] = select_keywords(cfg)
    return validate_config(cfg)


def validate_config(cfg):
    """Validate both file-based and runtime-overridden configuration."""
    from keyword_selection import clean_keywords
    cfg["industry"] = str(cfg.get("industry", "")).strip().lower()
    if not cfg["industry"]:
        raise ValueError("Industry is required")
    cfg["keywords"]["selected"] = clean_keywords(cfg["keywords"]["selected"])
    for group, keys in {
        "collection": ["history_days", "batch_size", "max_retries"],
        "window": ["analysis_days", "test_days", "feature_warmup_days"],
        "forecast": ["horizon_days", "verification_delay_days"],
        "thresholds": ["lookback_days"],
        "validation": ["n_splits", "search_iterations"],
    }.items():
        for key in keys:
            value = cfg[group][key]
            if type(value) is not int or value <= 0:
                raise ValueError(f"{group}.{key} must be a positive integer")
    if cfg["collection"]["batch_size"] > 5:
        raise ValueError("Google Trends accepts at most five keywords per request")
    if cfg["window"]["test_days"] >= cfg["window"]["analysis_days"]:
        raise ValueError("test_days must be smaller than analysis_days")
    if cfg["validation"]["n_splits"] < 2:
        raise ValueError("n_splits must be at least two")
    promotion_delta = cfg["validation"].get("promotion_min_delta", 0.0)
    if type(promotion_delta) not in {int, float} or promotion_delta < 0:
        raise ValueError("validation.promotion_min_delta must be a nonnegative number")
    if cfg["thresholds"]["method"] not in {"mad", "iqr", "zscore", "percentile"}:
        raise ValueError("threshold method must be mad, iqr, zscore or percentile")
    methods = cfg["thresholds"].get("candidate_methods", [cfg["thresholds"]["method"]])
    if not isinstance(methods, list) or not methods:
        raise ValueError("thresholds.candidate_methods must be a nonempty list")
    if any(method not in {"mad", "iqr", "zscore", "percentile"} for method in methods):
        raise ValueError("candidate threshold methods must be mad, iqr, zscore or percentile")
    if not isinstance(cfg["thresholds"].get("auto_select", False), bool):
        raise ValueError("thresholds.auto_select must be true or false")
    multipliers = cfg["thresholds"].get("candidate_multipliers", [cfg["thresholds"]["multiplier"]])
    if not isinstance(multipliers, list) or not multipliers:
        raise ValueError("thresholds.candidate_multipliers must be a nonempty list")
    if any(type(value) not in {int, float} or value <= 0 for value in multipliers):
        raise ValueError("candidate threshold multipliers must be positive numbers")
    if cfg["thresholds"]["multiplier"] <= 0 or not 0 < cfg["thresholds"]["percentile"] < 1:
        raise ValueError("Invalid threshold parameters")
    return cfg


def paths(cfg):
    root = Path(cfg["paths"]["root"])
    root = root if root.is_absolute() else BASE / root
    # Preserve selection order: it controls the normalization batches.
    selection = fingerprint({"industry": cfg["industry"], "keywords": cfg["keywords"]["selected"],
                             "country": cfg["collection"]["country"],
                             "batch_size": cfg["collection"]["batch_size"]})
    experiment = fingerprint({k: v for k, v in cfg.items() if k != "paths"})
    data = root / "selections" / selection
    run = root / "experiments" / experiment
    return {"root": root, "data": data, "run": run, "history": data / "history.csv",
            "model": run / "model.joblib", "selection_id": selection, "experiment_id": experiment}


def resolve_prepared(cfg):
    """Resolve an exact model or the smallest compatible trained superset."""
    exact = paths(cfg)
    if exact["history"].exists() and exact["model"].exists():
        return {**exact, "exact": True, "model_cfg": cfg}

    requested = {value.casefold() for value in cfg["keywords"]["selected"]}
    candidates = []
    experiments = exact["root"] / "experiments"
    if not experiments.exists():
        return None

    for config_path in experiments.glob("*/config.json"):
        model_path = config_path.parent / "model.joblib"
        if not model_path.exists():
            continue
        try:
            candidate_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            candidate_keywords = {
                value.casefold()
                for value in candidate_cfg["keywords"]["selected"]
            }
            compatible = (
                candidate_cfg.get("industry") == cfg.get("industry")
                and requested.issubset(candidate_keywords)
                and candidate_cfg["collection"]["country"] == cfg["collection"]["country"]
                and candidate_cfg["forecast"]["horizon_days"] == cfg["forecast"]["horizon_days"]
                and candidate_cfg["window"]["analysis_days"] == cfg["window"]["analysis_days"]
                and candidate_cfg["window"]["feature_warmup_days"] == cfg["window"]["feature_warmup_days"]
            )
            if not compatible:
                continue
            candidate_paths = paths(candidate_cfg)
            if not candidate_paths["history"].exists():
                continue
            candidates.append((
                len(candidate_keywords),
                -model_path.stat().st_mtime,
                {
                    **candidate_paths,
                    "run": config_path.parent,
                    "model": model_path,
                    "exact": False,
                    "model_cfg": candidate_cfg,
                },
            ))
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
            continue

    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
