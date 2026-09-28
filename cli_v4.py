"""Shared CLI for existing scripts. All commands use the same run config."""
import argparse
import json
import os
from pathlib import Path
from runtime_config import load_config, paths, resolve_prepared, save_json
BASE = Path(__file__).resolve().parent


def _add_runtime_options(parser, command):
    parser.add_argument(
        "--keywords", nargs="+", metavar="KEYWORD",
        help='Runtime keywords. Quote phrases: --keywords "kurta set" "wide leg pants"',
    )
    parser.add_argument("--keywords-file", help="JSON list or text file containing keywords")
    parser.add_argument("--interactive", action="store_true", help="Ask for industry and keywords in the terminal")
    if command == "run":
        parser.add_argument(
            "--use-config-keywords", action="store_true",
            help="Use keywords from run_config.json instead of asking in the terminal",
        )
    parser.add_argument("--industry", help="Override the configured industry")
    parser.add_argument("--analysis-days", type=int, help="Override the analysis window")
    parser.add_argument("--test-days", type=int, help="Override the final chronological test window")
    parser.add_argument("--horizon", type=int, help="Override the forecast horizon")
    if command == "run":
        parser.add_argument(
            "--prepare", action="store_true",
            help="Import/fetch history and train a selection-specific model when missing",
        )
        parser.add_argument("--refresh-history", action="store_true", help="Fetch a fresh historical snapshot")
        parser.add_argument("--retrain", action="store_true", help="Retrain even when a model exists")
        parser.add_argument(
            "--legacy-history", default="data/historical/google_trends_daily.csv",
            help="Existing daily CSV to reuse when it covers every selected keyword",
        )


def _apply_runtime_options(cfg, args, command):
    from keyword_selection import clean_keywords, load_keyword_file, parse_keyword_arguments

    selected = None
    if args.keywords and args.keywords_file:
        raise ValueError("Use either --keywords or --keywords-file, not both")
    if args.keywords:
        selected = parse_keyword_arguments(args.keywords)
    elif args.keywords_file:
        selected = load_keyword_file(args.keywords_file)

    interactive = args.interactive or (
        command == "run"
        and not args.keywords
        and not args.keywords_file
        and not args.use_config_keywords
    )
    if interactive:
        default_industry = args.industry or cfg["industry"]
        industry = input(f"Industry [{default_industry}]: ").strip()
        if industry:
            args.industry = industry
        print("Enter any number of keywords separated by commas.")
        entered = input("Keywords: ").strip()
        if not entered:
            raise ValueError("Interactive keyword selection cannot be empty")
        selected = clean_keywords(entered.split(","))

    if selected is not None:
        cfg["keywords"] = {
            "selection_mode": "manual",
            "selected": selected,
            "preset_name": None,
        }
    if args.industry:
        cfg["industry"] = args.industry.strip().lower()
    if args.analysis_days is not None:
        cfg["window"]["analysis_days"] = args.analysis_days
    if args.test_days is not None:
        cfg["window"]["test_days"] = args.test_days
    if args.horizon is not None:
        cfg["forecast"]["horizon_days"] = args.horizon

    # Reuse the normal validator after applying CLI values.
    from runtime_config import validate_config
    return validate_config(cfg)


def _legacy_covers(path, keywords):
    import pandas as pd
    source = Path(path)
    if not source.exists():
        return False
    try:
        available = {
            value.casefold()
            for value in pd.read_csv(source, usecols=["keyword"])["keyword"].dropna().astype(str)
        }
    except (ValueError, OSError):
        return False
    return {value.casefold() for value in keywords}.issubset(available)


def prepare_selection(cfg, args):
    """Create history/model artifacts isolated to the runtime keyword selection."""
    from agents.historical_data_agent import collect_configured
    from forecast_experiment import train_experiment

    p = paths(cfg)
    keywords = cfg["keywords"]["selected"]
    needs_history = args.refresh_history or not p["history"].exists()
    if needs_history:
        legacy = Path(args.legacy_history)
        if not legacy.is_absolute():
            legacy = BASE / legacy
        if not args.refresh_history and _legacy_covers(legacy, keywords):
            print(f"\n[PREPARE] Reusing June-to-September history for {len(keywords)} selected keywords")
            collect_configured(cfg, import_csv=str(legacy))
        else:
            print(f"\n[PREPARE] Fetching {cfg['collection']['history_days']} historical days for "
                  f"{len(keywords)} selected keywords")
            collect_configured(cfg, refresh=True)
    else:
        print(f"\n[PREPARE] Using selection-specific history: {p['history']}")

    if args.retrain or args.refresh_history or not p["model"].exists():
        print("\n[PREPARE] Training and comparing models for this keyword selection")
        report = train_experiment(cfg)
        if args.plots:
            make_plots(cfg, report)
    else:
        print(f"[PREPARE] Using trained selection-specific model: {p['model']}")


def main(command):
    parser = argparse.ArgumentParser(description=f"TrendSense v4: {command}")
    parser.add_argument("--config", default="run_config.json")
    _add_runtime_options(parser, command)
    if command == "collect":
        parser.add_argument("--refresh", action="store_true")
        parser.add_argument("--import-csv", help="Import existing daily data without API calls")
    if command in {"run", "train"}:
        parser.add_argument("--plots", action="store_true")
    if command == "run":
        parser.add_argument("--cache", action="store_true", help="Use selection-specific text cache")
        parser.add_argument("--input", help="Use and filter a raw signal JSON file")
        parser.add_argument("--offline", action="store_true", help="Disable marketplace fetching only")
        parser.add_argument("--no-semantic", action="store_true")
        parser.add_argument("--no-persist", action="store_true")
        parser.add_argument("--replay", action="store_true", help="Historical demo; never persist a future forecast")
    if command == "evaluate":
        parser.add_argument("--plots", action="store_true")
    args = parser.parse_args()
    try:
        cfg = _apply_runtime_options(load_config(args.config), args, command)
        print(f"\n[SELECTION] Industry: {cfg['industry']}")
        print(f"[SELECTION] Keywords ({len(cfg['keywords']['selected'])}): "
              f"{', '.join(cfg['keywords']['selected'])}")
        if command == "collect":
            from agents.historical_data_agent import collect_configured
            collect_configured(cfg, args.refresh, args.import_csv)
        elif command == "train":
            from forecast_experiment import train_experiment
            report = train_experiment(cfg)
            if args.plots:
                make_plots(cfg, report)
        elif command == "run":
            if args.prepare or args.refresh_history or args.retrain:
                prepare_selection(cfg, args)
            run(cfg, args)
        elif command == "record":
            from storage.configured_forecasts import record
            print(json.dumps(record(cfg), indent=2))
        elif command == "evaluate":
            from storage.configured_forecasts import evaluate
            print(json.dumps(evaluate(cfg, args.plots), indent=2))
        elif command == "doctor":
            doctor(cfg)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        parser.exit(1, f"TrendSense: {exc}\n")


def make_plots(cfg, report, forecasts=None):
    import joblib
    from agents.window_features import build_window
    from evaluation.plots import plot_experiment
    p = paths(cfg)
    prepared = resolve_prepared(cfg)
    if prepared is None:
        raise ValueError("No compatible prepared model is available for plotting")
    bundle = joblib.load(prepared["model"])
    model_cfg = bundle.get("cfg", prepared["model_cfg"])
    window, *_ = build_window(prepared["history"], model_cfg)
    predictions = json.loads((prepared["run"] / "test_predictions.json").read_text())
    plot_experiment(window, report, predictions, p["run"] / "plots", forecasts)
    print(f"Plots: {p['run'] / 'plots'}")


def run(cfg, args):
    import pandas as pd
    from forecast_experiment import infer
    from agents.selected_scout import filter_signals
    from agents.weak_signal_agent import run_weak_signal_detection
    from agents.lifecycle_agent import run_lifecycle_analysis
    from agents.authenticity_agent import run_authenticity_analysis
    from agents.semantic_evidence_agent import run_semantic_evidence_analysis
    from agents.evidence_validation_agent import run_evidence_validation_analysis
    from agents.industry_impact_agent import run_industry_impact_analysis
    from agents.commercial_potential import run_commercial_potential_analysis
    from agents.decision_engine import run_decision_engine
    from agents.explainability_engine import run_explainability_engine
    from storage.configured_forecasts import persist
    if args.offline:
        os.environ["TRENDSENSE_OFFLINE"] = "1"
    p = paths(cfg)
    prepared = resolve_prepared(cfg)
    if prepared is None:
        print("\n[AUTO PREPARE] No compatible model found; preparing this keyword selection")
        prepare_selection(cfg, args)
        prepared = resolve_prepared(cfg)
    if prepared is None:
        raise ValueError("History/model preparation did not produce usable artifacts")
    if not prepared["exact"]:
        print(
            f"\n[MODEL REUSE] Using compatible {len(prepared['model_cfg']['keywords']['selected'])}-keyword "
            f"{cfg['industry']} model for {len(cfg['keywords']['selected'])} requested keywords"
        )
    history = pd.read_csv(prepared["history"])
    print(f"\n[DATA SOURCE] Google Trends history: {len(history)} rows, "
          f"{history['keyword'].nunique()} selected keywords")
    ml, window, bundle = run_agent(
        "ML forecaster",
        infer,
        cfg,
    )
    start, end = window.date.min(), window.date.max()
    cache = p["data"] / "signals.json"
    if args.input:
        print(f"[Scout] Reading supplied signals: {args.input}")
        signals = json.loads(Path(args.input).read_text(encoding="utf-8"))
    elif args.cache:
        if not cache.exists():
            raise ValueError("No cache for this selection. Run without --cache or supply --input.")
        print(f"[Scout] Reading selection cache: {cache}")
        signals = json.loads(cache.read_text(encoding="utf-8"))
    else:
        from agents.scout_agent import run_scout
        signals = run_agent(
            "Scout source collector",
            run_scout,
            cfg,
            start,
            end,
        )
    signals = filter_signals(signals, cfg["keywords"]["selected"], start, end)
    print(f"[Scout] {len(signals)} unique, dated, selected-keyword evidence items passed filtering")
    save_json(cache, signals)
    weak = run_agent("Weak Signal", run_weak_signal_detection, signals, cfg)
    by_keyword = {x["keyword"]: x for x in ml}
    items = [{**x, **by_keyword[x["keyword"]]} for x in weak]
    today = pd.Timestamp.now(tz="UTC").normalize()
    for x in items:
        x["target_already_observed"] = bool(x.get("target_date") and pd.Timestamp(x["target_date"]) < today)
    items = run_agent("Lifecycle", run_lifecycle_analysis, items, cfg)
    items = run_agent("Authenticity", run_authenticity_analysis, items, cfg)
    semantic_rows = run_agent(
        "Semantic evidence (Hugging Face)",
        run_semantic_evidence_analysis,
        items,
        signals,
        not args.no_semantic,
        cfg,
    )
    semantic = {x["keyword"]: x for x in semantic_rows}
    items = [{**x, **semantic[x["keyword"]]} for x in items]
    items = run_agent("Evidence validation", run_evidence_validation_analysis, items, cfg)
    items = run_agent("Industry impact", run_industry_impact_analysis, items, cfg)
    items = run_agent("Commercial validation", run_commercial_potential_analysis, items, cfg)
    items = run_agent("Decision and ranking", run_decision_engine, items, cfg)
    items = run_agent("Explainability", run_explainability_engine, items, cfg)
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S%f")
    destination = p["run"] / f"final_results_{stamp}.json"
    save_json(destination, items)
    count = 0 if args.no_persist or args.replay else persist(cfg, items)
    print("\nTOP 10 DATA-DRIVEN WATCHLIST")

    watchlist_items = [
        item
        for item in items
        if item.get("watchlist_rank") is not None
    ][:10]

    for x in watchlist_items:
        probabilities = x.get("ml_probabilities") or {}
        up_probability = float(probabilities.get("UP", 0.0))
        rank_score = x.get("watchlist_score")

        print(
            f"#{x['watchlist_rank']:<2} "
            f"{x['keyword']:<28} "
            f"P(UP)={up_probability:.3f} "
            f"rank_score={rank_score:.3f} "
            f"direction={x.get('ml_predicted_direction', 'UNAVAILABLE'):<9} "
            f"decision={x.get('decision', 'WAIT')}"
        )
    print("\nALL KEYWORDS")
    for x in items:
        print(f"{x['keyword']:<28} {x['decision']:<7} direction={x.get('ml_predicted_direction', 'UNAVAILABLE'):<9} numeric={x.get('predicted_interest')} evidence={x.get('semantic_status')} reason={'; '.join(x.get('decision_reasons', []))}")
    print(f"Results: {destination}\nSaved {count} future forecasts.")
    if args.plots:
        make_plots(cfg, bundle["report"], items)


def run_agent(name, function, *args):
    """Print a visible start/end record for each sequential pipeline stage."""
    print(f"\n[AGENT RUNNING] {name}")
    try:
        result = function(*args)
    except Exception as exc:
        print(f"[AGENT FAILED] {name}: {type(exc).__name__}: {exc}")
        raise

    if isinstance(result, list):
        print(f"[AGENT COMPLETE] {name}: {len(result)} output records")
    elif isinstance(result, tuple):
        print(f"[AGENT COMPLETE] {name}")
    else:
        print(f"[AGENT COMPLETE] {name}")

    return result


def doctor(cfg):
    import importlib.util
    import pandas as pd
    p = paths(cfg)
    print(f"Industry: {cfg['industry']}; selected keywords: {len(cfg['keywords']['selected'])}")
    print(f"Window: {cfg['window']['analysis_days']}; test: {cfg['window']['test_days']}; horizon: {cfg['forecast']['horizon_days']}")
    for name in ["pandas", "numpy", "sklearn", "joblib", "matplotlib", "requests", "pytrends", "feedparser", "sentence_transformers", "torch", "xgboost", "lightgbm"]:
        print(f"{name:<25} {'INSTALLED' if importlib.util.find_spec(name) else 'MISSING'}")
    print(f"History: {p['history']} ({'exists' if p['history'].exists() else 'collect/import required'})")
    if p["history"].exists():
        from agents.window_features import build_window
        _, frame, live, end, coverage = build_window(p["history"], cfg)
        print(f"History ends {end.date()}; mature labeled rows: {len(frame)}; live feature rows: {len(live)}")
        print(json.dumps(coverage, indent=2))
    print(f"Model: {p['model']} ({'exists' if p['model'].exists() else 'training required'})")
    print("Optional boosters may be skipped. Zero-variability series cannot produce adaptive direction labels.")
