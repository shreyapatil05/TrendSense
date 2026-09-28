"""Configurable, purged temporal comparison of classifiers and regressors."""
import json
import hashlib
from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import ParameterGrid, ParameterSampler
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from adaptive_thresholds import LABELS, direction, tune_policy
from agents.window_features import FEATURES, build_window
from evaluation.time_splits import expanding_splits, holdout
from evaluation.metrics import classification_metrics, regression_metrics
from model_registry import candidates, construct
from runtime_config import paths, resolve_prepared, save_json


def classify_metrics(actual, predicted):
    return classification_metrics(list(actual), list(predicted), LABELS)


def fit_pair(name, c, r, train):
    encoder = LabelEncoder().fit(train.label)
    encoded_labels = encoder.transform(train.label)
    # Compute weights from this training fold only. Minority classes receive
    # more influence without copying rows or looking at validation/test labels.
    full_weights = compute_sample_weight(
        class_weight="balanced",
        y=encoded_labels,
    )
    # alpha=0 means unweighted, 0.5 means moderate square-root weighting,
    # and 1 means fully balanced. Validation chooses alpha per model.
    balance_alpha = float(getattr(c, "_trendsense_balance_alpha", 0.0))
    sample_weights = np.power(full_weights, balance_alpha)
    # XGBoost requires consecutive integer labels, including within individual folds.
    if hasattr(c, "steps"):
        # Pipelines route weights to their final classifier step.
        final_step = c.steps[-1][0]
        c.fit(
            train[FEATURES],
            encoded_labels,
            **{f"{final_step}__sample_weight": sample_weights},
        )
    else:
        c.fit(train[FEATURES], encoded_labels, sample_weight=sample_weights)
    r.fit(train[FEATURES], train.delta)
    return c, r, encoder


def class_balance_summary(frame, results):
    """Document fold-safe base weights and validation-selected strengths."""
    counts = frame.label.value_counts().to_dict()
    total = len(frame)
    classes = max(len(counts), 1)
    weights = {
        label: total / (classes * count)
        for label, count in counts.items()
        if count
    }
    return {
        "method": "validation-tuned sample weights computed separately inside each training fold",
        "candidate_alpha": [0.0, 0.5, 1.0],
        "alpha_meaning": {"0.0": "unweighted", "0.5": "moderate", "1.0": "fully balanced"},
        "class_counts": {str(k): int(v) for k, v in counts.items()},
        "full_balance_weights": {str(k): float(v) for k, v in weights.items()},
        "selected_alpha_by_model": {
            name: values.get("params", {}).get("classifier", {}).get("balance_alpha")
            for name, values in results.items()
            if name not in {"persistence", "seasonal_naive"}
        },
    }


def predictions(c, r, encoder, frame):
    predicted = encoder.inverse_transform(c.predict(frame[FEATURES]).astype(int))
    if hasattr(c, "predict_proba"):
        raw = c.predict_proba(frame[FEATURES])
    else:
        # SVM margins are converted to scores, not advertised as calibrated probabilities.
        margin = c.decision_function(frame[FEATURES])
        if margin.ndim == 1:
            margin = np.column_stack([-margin, margin])
        margin = margin - margin.max(axis=1, keepdims=True)
        raw = np.exp(margin)
        raw /= raw.sum(axis=1, keepdims=True)
    probs = np.zeros((len(frame), 3))
    for j, encoded_label in enumerate(c.classes_):
        probs[:, LABELS.index(encoder.inverse_transform([int(encoded_label)])[0])] = raw[:, j]
    # Indices use the current request's scale; no arbitrary upper clipping at 100.
    future = np.maximum(0, frame.interest.to_numpy() + r.predict(frame[FEATURES]))
    return predicted, probs, future


def baseline(frame, name="persistence"):
    if name == "persistence":
        future = frame.interest.to_numpy()
    else:
        future = frame.seasonal_naive_interest.to_numpy()
    labels = [direction(p - x, b) for p, x, b in zip(future, frame.interest, frame.band)]
    return np.array(labels), future


def metrics(frame, labels, future):
    return {"classification": classify_metrics(frame.label, labels),
            "regression": regression_metrics(frame.future_interest.tolist(), list(future)),
            "rows": len(frame)}


def empirical_class_probabilities(actual, predicted, smoothing=1.0):
    """Estimate P(actual class | predicted class) from validation predictions."""
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)
    result = {}
    for predicted_label in LABELS:
        selected = actual[predicted == predicted_label]
        counts = np.array([(selected == label).sum() for label in LABELS], dtype=float)
        counts += smoothing
        result[predicted_label] = dict(zip(LABELS, (counts / counts.sum()).tolist()))
    return result


def probability_rows(predicted, calibration):
    uniform = {label: 1.0 / len(LABELS) for label in LABELS}
    return np.asarray([[calibration.get(str(value), uniform).get(label, 0.0)
                        for label in LABELS] for value in predicted], dtype=float)


def select_threshold_configuration(cfg, history):
    """Jointly tune label sensitivity and a small forecasting probe suite."""
    effective = deepcopy(cfg)
    if not cfg["thresholds"].get("auto_select", False):
        return effective, []

    trials = []
    base_multiplier = float(cfg["thresholds"]["multiplier"])
    mad_multipliers = cfg["thresholds"].get(
        "candidate_multipliers", [0.6, 0.8, 1.0, 1.2, 1.4]
    )
    methods = cfg["thresholds"].get(
        "candidate_methods", [cfg["thresholds"]["method"]]
    )
    for method in methods:
        # Tune label sensitivity for MAD. Retain the configured scale for the
        # other methods so the search remains small and explainable.
        multipliers = mad_multipliers if method == "mad" else [base_multiplier]
        for multiplier in multipliers:
            candidate = deepcopy(cfg)
            candidate["thresholds"]["method"] = method
            candidate["thresholds"]["multiplier"] = float(multiplier)
            candidate["thresholds"]["auto_select"] = False
            try:
                window, frame, _, end, _ = build_window(history, candidate)
                train, _, _ = holdout(frame, end, candidate["window"]["test_days"])
                folds = expanding_splits(train, candidate["validation"]["n_splits"])
                probe_chunks = {
                    "logistic_regression": [],
                    "seasonal_naive": [],
                    "persistence": [],
                }
                for earlier_indices, validation_indices in folds:
                    earlier = train.iloc[earlier_indices]
                    later = train.iloc[validation_indices]
                    if earlier.label.nunique() < 2 or later.empty:
                        continue
                    encoder = LabelEncoder().fit(earlier.label)
                    classifier = make_pipeline(
                        StandardScaler(),
                        LogisticRegression(
                            max_iter=2000,
                            class_weight="balanced",
                            random_state=candidate["validation"]["random_state"],
                        ),
                    )
                    classifier.fit(
                        earlier[FEATURES], encoder.transform(earlier.label)
                    )
                    logistic_labels = encoder.inverse_transform(
                        classifier.predict(later[FEATURES]).astype(int)
                    )
                    actual_labels = later.label.to_numpy()
                    seasonal_labels, _ = baseline(later, "seasonal_naive")
                    persistence_labels, _ = baseline(later, "persistence")
                    probe_chunks["logistic_regression"].append(
                        (actual_labels, logistic_labels)
                    )
                    probe_chunks["seasonal_naive"].append(
                        (actual_labels, seasonal_labels)
                    )
                    probe_chunks["persistence"].append(
                        (actual_labels, persistence_labels)
                    )
                if not probe_chunks["logistic_regression"]:
                    raise ValueError("insufficient chronological folds")

                # The old implementation tuned every threshold using only
                # Logistic Regression. This could select a label definition
                # that was poor for the final winning baseline. Score several
                # forecasting probes and select threshold + probe together.
                probe_scores = {}
                for probe_name, chunks in probe_chunks.items():
                    actual = np.concatenate([chunk[0] for chunk in chunks])
                    predicted = np.concatenate([chunk[1] for chunk in chunks])
                    probe_scores[probe_name] = classify_metrics(actual, predicted)
                selected_probe, score = max(
                    probe_scores.items(),
                    key=lambda item: (
                        item[1]["macro_f1"],
                        item[1]["balanced_accuracy"],
                    ),
                )
                trial = {
                    "method": method,
                    "multiplier": float(multiplier),
                    "selection_probe": selected_probe,
                    "validation_macro_f1": score["macro_f1"],
                    "validation_balanced_accuracy": score["balanced_accuracy"],
                    "probe_scores": {
                        name: {
                            "macro_f1": values["macro_f1"],
                            "balanced_accuracy": values["balanced_accuracy"],
                        }
                        for name, values in probe_scores.items()
                    },
                    "labeled_rows": len(frame),
                    "excluded_rows": len(window) - len(frame),
                    "class_counts": frame.label.value_counts().to_dict(),
                    "status": "READY",
                }
                trials.append(trial)
                print(
                    f"Threshold {method} x{float(multiplier):g}: "
                    f"best probe={selected_probe}, "
                    f"validation macro-F1={score['macro_f1']:.3f}"
                )
            except Exception as exc:
                trials.append({
                    "method": method,
                    "multiplier": float(multiplier),
                    "status": "SKIPPED",
                    "reason": str(exc),
                })

    ready = [trial for trial in trials if trial["status"] == "READY"]
    if ready:
        winner = max(ready, key=lambda trial: (
            trial["validation_macro_f1"],
            trial["validation_balanced_accuracy"],
            -abs(trial["multiplier"] - base_multiplier),
            trial["labeled_rows"],
        ))
        effective["thresholds"]["method"] = winner["method"]
        effective["thresholds"]["multiplier"] = winner["multiplier"]
        effective["thresholds"]["auto_select"] = False
        print(
            f"Selected adaptive threshold: {winner['method']} "
            f"x{winner['multiplier']:g} using {winner['selection_probe']}"
        )
    return effective, trials


def train_experiment(cfg, history=None):
    p = paths(cfg)
    history = Path(history or p["history"])
    effective_cfg, threshold_trials = select_threshold_configuration(cfg, history)
    window, frame, live, end, coverage = build_window(history, effective_cfg)
    train, test, test_start = holdout(frame, end, effective_cfg["window"]["test_days"])
    splits = expanding_splits(train, effective_cfg["validation"]["n_splits"])
    splits = [(a, b) for a, b in splits if train.iloc[a].label.nunique() >= 2]
    warnings = ["Historical Google Trends is a retrospectively normalized snapshot. This is a backtest, not prospective evidence.",
                "Recommendation tuning optimizes directional F1, not profit. ML probabilities remain uncalibrated; winning baselines use empirical validation reliability."]
    if not splits:
        warnings.append("Too few dates/classes for model tuning; using persistence only.")
    warnings.append(f"{len(window) - len(frame)} window rows excluded from classification for missing features, immature targets or zero robust variability. See coverage.")
    if any(v["missing_days"] for v in coverage.values()):
        warnings.append("Missing days reduce feature and label coverage. Missing values were not filled with zero.")
    registry, skipped = candidates(effective_cfg["validation"]["random_state"])
    results, fitted, oof = {}, {}, {}
    baseline_calibrations = {}
    fold_rows = sorted(set(int(i) for _, valid in splits for i in valid))
    validation_frame = train.iloc[fold_rows].reset_index(drop=True)
    for name in ("persistence", "seasonal_naive"):
        lab, future = baseline(validation_frame, name)
        results[name] = {"validation": metrics(validation_frame, lab, future), "params": {}, "status": "READY"}
        calibration = empirical_class_probabilities(validation_frame.label, lab)
        baseline_calibrations[name] = calibration
        oof[name] = {"actual": validation_frame, "labels": lab,
                     "probs": probability_rows(lab, calibration), "future": future,
                     "regression_errors": (future - validation_frame.future_interest.to_numpy()).tolist()}
    for name in effective_cfg["models"]["candidates"]:
        if name not in registry:
            skipped.setdefault(name, "Unknown or unavailable candidate")
            continue
        if not splits:
            skipped[name] = "Insufficient chronological training folds with multiple classes"
            continue
        c0, r0, space = registry[name]
        trials = []
        # Tune class weighting as a normal hyperparameter. This keeps the
        # requested search budget honest instead of tripling every trial.
        search_space = {**space, "balance_alpha": [0.0, 0.5, 1.0]}
        total_combinations = len(ParameterGrid(search_space))
        requested = effective_cfg["validation"]["search_iterations"]
        if total_combinations <= requested:
            sampled_params = list(ParameterGrid(search_space))
            search_kind = "exhaustive_grid"
        else:
            sampled_params = list(ParameterSampler(
                search_space,
                n_iter=requested,
                random_state=effective_cfg["validation"]["random_state"],
            ))
            search_kind = "randomized"
        print(
            f"Searching {name}: {len(sampled_params)} configurations, "
            f"{len(splits)} chronological folds"
        )
        for params in sampled_params:
            chunks = []
            fold_classification = []
            fold_regression = []
            try:
                for a, b in splits:
                    earlier, later = train.iloc[a], train.iloc[b]
                    c, r = construct(name, c0, r0, params)
                    c, r, encoder = fit_pair(name, c, r, earlier)
                    labels, probs, future = predictions(c, r, encoder, later)
                    chunks.append((later, labels, probs, future))
                    fold_classification.append(
                        classify_metrics(later.label, labels)["macro_f1"]
                    )
                    fold_regression.append(
                        regression_metrics(
                            later.future_interest.tolist(), list(future)
                        )["mae"]
                    )
                actual = pd.concat([v[0] for v in chunks], ignore_index=True)
                labels = np.concatenate([v[1] for v in chunks])
                probs = np.concatenate([v[2] for v in chunks])
                future = np.concatenate([v[3] for v in chunks])
                trials.append({"params": params, "metrics": metrics(actual, labels, future),
                               "actual": actual, "labels": labels, "probs": probs, "future": future,
                               "fold_macro_f1": fold_classification,
                               "fold_mae": fold_regression})
            except Exception as exc:
                skipped[name] = f"Trial failed: {type(exc).__name__}: {exc}"
        if not trials:
            continue
        # Prefer strong pooled performance, then stable performance across time.
        best_c = max(trials, key=lambda x: (
            x["metrics"]["classification"]["macro_f1"],
            x["metrics"]["classification"]["balanced_accuracy"],
            -float(np.std(x["fold_macro_f1"])),
        ))
        best_r = min(trials, key=lambda x: (
            x["metrics"]["regression"]["mae"],
            float(np.std(x["fold_mae"])),
        ))
        c, _ = construct(name, c0, r0, best_c["params"])
        _, r = construct(name, c0, r0, best_r["params"])
        fitted[name] = fit_pair(name, c, r, train)
        oof[name] = best_c
        oof[name]["regression_errors"] = (best_r["future"] - best_r["actual"].future_interest.to_numpy()).tolist()
        results[name] = {"validation": {"classification": best_c["metrics"]["classification"],
                                         "regression": best_r["metrics"]["regression"], "rows": len(validation_frame)},
                         "params": {"classifier": best_c["params"], "regressor": best_r["params"]},
                         "search": {"strategy": search_kind,
                                    "evaluated_configurations": len(trials),
                                    "chronological_folds": len(splits),
                                    "classifier_fold_macro_f1": best_c["fold_macro_f1"],
                                    "classifier_fold_macro_f1_std": float(np.std(best_c["fold_macro_f1"])),
                                    "regressor_fold_mae": best_r["fold_mae"],
                                    "regressor_fold_mae_std": float(np.std(best_r["fold_mae"]))},
                         "status": "READY"}
        print(f"Compared {name}: validation macro-F1={results[name]['validation']['classification']['macro_f1']:.3f}")
    # Selection uses validation only. Ties favor the earlier, simpler baseline.
    classifier_name = max(results, key=lambda name: results[name]["validation"]["classification"]["macro_f1"])
    numeric = [name for name in results if results[name]["validation"]["regression"]["mae"] is not None]
    regressor_name = min(numeric, key=lambda name: results[name]["validation"]["regression"]["mae"]) if numeric else "persistence"
    policy = tune_policy(oof[classifier_name]["actual"].label, oof[classifier_name]["probs"]) if classifier_name in oof else {"UP": None, "DOWN": None}
    test_predictions = []
    for name in results:
        if test.empty:
            results[name]["test"] = {"status": "NO_MATURE_TEST_ROWS"}
            continue
        if name in fitted:
            labels, _, future = predictions(*fitted[name], test)
        else:
            labels, future = baseline(test, name)
        results[name]["test"] = metrics(test, labels, future)
        for (_, row), label, pred in zip(test.iterrows(), labels, future):
            test_predictions.append({"model": name, "keyword": row.keyword, "origin_date": row.date.isoformat(),
                 "target_date": row.target_date.isoformat(), "actual_direction": row.label,
                 "predicted_direction": str(label), "actual_interest": float(row.future_interest),
                 "predicted_interest": float(pred), "current_interest": float(row.interest)})
    bundle_models = {}
    # Refit winners for FUTURE use only, after holdout measurement is saved in memory.
    for name in {classifier_name, regressor_name}:
        if name in fitted:
            c0, r0, _ = registry[name]
            c, _ = construct(name, c0, r0, results[name]["params"]["classifier"])
            _, r = construct(name, c0, r0, results[name]["params"]["regressor"])
            bundle_models[name] = fit_pair(name, c, r, frame)
    report = {"system_version": "4.5.0", "experiment_id": p["experiment_id"],
              "trained_at": pd.Timestamp.now(tz="UTC").isoformat(), "window_end": end.isoformat(),
              "window_start": str(window.date.min()), "test_start": test_start.isoformat(),
              "nominal_train_days": effective_cfg["window"]["analysis_days"] - effective_cfg["window"]["test_days"],
              "training_rows_after_purge": len(train), "test_rows": len(test),
              "class_counts": frame.label.value_counts().to_dict(), "coverage": coverage,
              "window_rows": len(window), "labeled_rows": len(frame),
              "excluded_classification_rows": len(window) - len(frame),
              "target_definition": "causal per-keyword rolling variability band; excludes zero-scale labels",
              "feature_design": "past-only level, lag, relative-change, relative-trend, rolling-z and calendar features",
              "class_balancing": class_balance_summary(train, results),
              "classifier": classifier_name, "regressor": regressor_name, "recommendation_cutoffs": policy,
              "baseline_calibration": baseline_calibrations,
              "models": results, "skipped": skipped, "warnings": warnings,
              "folds": [{"train_origin_end": str(train.iloc[a].date.max()),
                         "train_target_end": str(train.iloc[a].target_date.max()),
                         "validation_origin_start": str(train.iloc[b].date.min()),
                         "train_rows": len(a), "validation_rows": len(b)} for a, b in splits],
              "threshold_settings": effective_cfg["thresholds"], "threshold_comparison": threshold_trials}
    # Approximate residual spread, explicitly not a coverage-guaranteed prediction interval.
    errors = oof.get(regressor_name, {}).get("regression_errors", [])
    spread = float(np.std(errors)) if errors else None
    bundle = {"report": report, "models": bundle_models, "cfg": effective_cfg, "features": FEATURES,
              "history_hash": hashlib.sha256(history.read_bytes()).hexdigest(), "residual_std": spread}
    p["run"].mkdir(parents=True, exist_ok=True)

    # Champion/challenger gate. Test metrics never participate in promotion.
    # An existing deployed bundle is replaced only when the new validation
    # macro-F1 exceeds it by at least the configured minimum improvement.
    challenger_score = float(
        results[classifier_name]["validation"]["classification"]["macro_f1"]
    )
    minimum_delta = float(
        effective_cfg["validation"].get("promotion_min_delta", 0.0)
    )
    incumbent_score = None
    incumbent_classifier = None
    promotion_reason = "no_existing_model"
    promoted = True
    if p["model"].exists():
        try:
            incumbent = joblib.load(p["model"])
            incumbent_report = incumbent["report"]
            incumbent_classifier = incumbent_report["classifier"]
            incumbent_score = float(
                incumbent_report["models"][incumbent_classifier]
                ["validation"]["classification"]["macro_f1"]
            )
            promoted = challenger_score > incumbent_score + minimum_delta
            promotion_reason = (
                "validation_improved" if promoted
                else "validation_did_not_improve"
            )
        except Exception as exc:
            # A corrupt or legacy artifact must not silently block deployment.
            promoted = True
            promotion_reason = f"incumbent_unreadable:{type(exc).__name__}"

    report["promotion"] = {
        "metric": "validation_macro_f1",
        "challenger_classifier": classifier_name,
        "challenger_score": challenger_score,
        "incumbent_classifier": incumbent_classifier,
        "incumbent_score": incumbent_score,
        "minimum_required_improvement": minimum_delta,
        "accepted": promoted,
        "reason": promotion_reason,
        "test_metrics_used": False,
    }
    if promoted:
        joblib.dump(bundle, p["model"])
        print(
            f"Model promotion ACCEPTED: validation macro-F1="
            f"{challenger_score:.3f}"
        )
    else:
        print(
            f"Model promotion REJECTED: challenger validation macro-F1="
            f"{challenger_score:.3f}, incumbent={incumbent_score:.3f}"
        )
    save_json(p["run"] / "comparison.json", report)
    save_json(p["run"] / "test_predictions.json", test_predictions)
    save_json(p["run"] / "config.json", effective_cfg)
    frame.to_csv(p["run"] / "features.csv", index=False)
    print(f"Challenger classifier: {classifier_name}; regressor: {regressor_name}")
    print(f"Comparison report: {p['run'] / 'comparison.json'}")
    return report


def infer(cfg):
    prepared = resolve_prepared(cfg)
    if prepared is None:
        raise ValueError("No model for this keyword selection. Run main.py with --prepare first")
    bundle = joblib.load(prepared["model"])
    model_cfg = bundle.get("cfg", cfg)
    window, _, live, end, coverage = build_window(prepared["history"], model_cfg)
    report = bundle["report"]
    if pd.Timestamp(report["window_end"]) > end:
        raise ValueError("Model trained on future data relative to this window")
    cname, rname = report["classifier"], report["regressor"]
    if live.empty:
        return [{"keyword": k, "industry": cfg["industry"], "ml_forecast_status": "UNAVAILABLE",
                 "ml_forecast_warning": "Missing latest-day features"} for k in cfg["keywords"]["selected"]], window, bundle
    if cname in bundle["models"]:
        labels, probs, _ = predictions(*bundle["models"][cname], live)
    else:
        labels, _ = baseline(live, cname)
        calibration = report.get("baseline_calibration", {}).get(cname, {})
        probs = probability_rows(labels, calibration)
    if rname in bundle["models"]:
        _, _, future = predictions(*bundle["models"][rname], live)
    else:
        _, future = baseline(live, rname)
    rows = {}
    for i, row in live.iterrows():
        if not np.isfinite(row.band) or row.band <= 0:
            continue
        delta = float(future[i] - row.interest)
        past = window[(window.keyword == row.keyword) & (window.date <= row.date)].dropna(subset=["interest"])
        old = past[past.date == row.date - pd.Timedelta(days=model_cfg["forecast"]["horizon_days"])]
        past_delta = float(row.interest - old.interest.iloc[0]) if len(old) else None
        rows[row.keyword] = {"keyword": row.keyword, "industry": cfg["industry"], "ml_forecast_status": "READY",
            "ml_predicted_direction": str(labels[i]), "ml_probabilities": dict(zip(LABELS, map(float, probs[i]))),
            "ml_confidence": float(probs[i][LABELS.index(str(labels[i]))]),
            "confidence_type": ("uncalibrated_score" if cname == "svm" else "uncalibrated_probability")
                               if cname in bundle["models"] else "validation_empirical_probability",
            "ml_forecast_method": cname, "numeric_model": rname, "ml_horizon_days": model_cfg["forecast"]["horizon_days"],
            "ml_current_interest": float(row.interest), "predicted_interest": float(future[i]), "predicted_change": delta,
            "predicted_growth_percent": 100 * delta / float(row.interest) if row.interest > 0 else None,
            "numeric_direction": direction(delta, row.band), "threshold": float(row.band),
            "past_direction": direction(past_delta, row.band) if past_delta is not None else "UNKNOWN",
            "forecast_origin_date": row.date.isoformat(), "target_date": row.target_date.isoformat(),
            "ml_model_version": report["trained_at"], "policy_cutoffs": report["recommendation_cutoffs"],
            "residual_std": bundle["residual_std"], "history_coverage": coverage[row.keyword],
            "batch_signature": str(row.get("batch_signature", "unknown")),
            "normalization_provenance": str(row.get("normalization_provenance", "unknown")),
            "snapshot_id": str(row.get("snapshot_id", "unknown")),
            "reference_overlap": [{"date": x.date.isoformat(), "interest": float(x.interest)} for x in past.tail(21).itertuples()]}
    output = [rows.get(k, {"keyword": k, "industry": cfg["industry"], "ml_forecast_status": "UNAVAILABLE",
                         "ml_forecast_warning": "Missing latest features or zero robust variability; cannot issue adaptive direction"})
              for k in cfg["keywords"]["selected"]]
    return output, window, bundle
