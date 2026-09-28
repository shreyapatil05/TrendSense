"""Regression checks for selection isolation, causality and exact target matching."""
import copy
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from runtime_config import load_config, paths, save_json
from agents.window_features import build_window, FEATURES
from evaluation.time_splits import holdout, expanding_splits
from agents.selected_scout import filter_signals
from storage.configured_forecasts import append_records, read_records, record
from adaptive_thresholds import direction, rolling_band

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg(tmp_path):
    cfg = load_config(ROOT / "run_config.json")
    cfg["keywords"]["selected"] = ["alpha", "beta"]
    cfg["paths"]["root"] = str(tmp_path / "artifacts")
    cfg["window"]["end_date"] = "2026-08-31"
    cfg["window"].update(analysis_days=40, test_days=10, feature_warmup_days=30)
    cfg["models"]["candidates"] = ["logistic_regression"]
    cfg["validation"]["search_iterations"] = 1
    return cfg


def history(cfg, missing=False):
    p = paths(cfg)
    p["data"].mkdir(parents=True, exist_ok=True)
    rows = []
    for j, k in enumerate(cfg["keywords"]["selected"]):
        for i, d in enumerate(pd.date_range("2026-06-01", "2026-09-10", tz="UTC")):
            if missing and k == "alpha" and d == pd.Timestamp("2026-08-20", tz="UTC"):
                continue
            rows.append({"date": d, "keyword": k, "interest": 50+15*np.sin(i/3+j),
                         "batch_signature": "test", "snapshot_id": "test", "normalization_provenance": "synthetic_test"})
    pd.DataFrame(rows).to_csv(p["history"], index=False)
    return p["history"]


def test_keywords_and_cache_isolation(cfg):
    from keyword_selection import clean_keywords
    assert clean_keywords(["  Kurta   set ", "kurta set", "lip liner"]) == ["Kurta set", "lip liner"]
    with pytest.raises(ValueError):
        clean_keywords([])
    other = copy.deepcopy(cfg); other["keywords"]["selected"] = ["gamma"]
    assert paths(cfg)["history"] != paths(other)["history"]


def test_window_and_target_dates_and_causality(cfg):
    path = history(cfg, missing=True)
    window, frame, live, end, coverage = build_window(path, cfg)
    assert window.date.min() == end-pd.Timedelta(days=39)
    assert set(window.keyword) == {"alpha", "beta"}
    assert coverage["alpha"]["missing_days"] == 1
    assert (frame.target_date - frame.date).eq(pd.Timedelta(days=2)).all()
    train, test, start = holdout(frame, end, 10)
    assert train.target_date.max() < start
    for a, b in expanding_splits(train, 3):
        assert train.iloc[a].target_date.max() < train.iloc[b].date.min()
        assert set(train.iloc[a].date).isdisjoint(train.iloc[b].date)
    old = frame[frame.date < pd.Timestamp("2026-08-15", tz="UTC")].copy()
    raw = pd.read_csv(path); raw.loc[pd.to_datetime(raw.date, utc=True) >= pd.Timestamp("2026-08-18", tz="UTC"), "interest"] = 999
    raw.to_csv(path, index=False)
    _, changed, *_ = build_window(path, cfg)
    pd.testing.assert_frame_equal(old.reset_index(drop=True), changed[changed.date < pd.Timestamp("2026-08-15", tz="UTC")].reset_index(drop=True))


def test_filter_does_not_turn_query_into_evidence():
    rows = [{"title": "irrelevant", "seed_topic": "alpha", "source": "newsapi", "published_at": "2026-08-10"},
            {"title": "Alpha style", "source": "newsapi", "published_at": "2026-08-10"},
            {"title": "beta", "source": "newsapi", "published_at": "2026-08-10"}]
    result = filter_signals(rows, ["alpha"], pd.Timestamp("2026-08-01", tz="UTC"), pd.Timestamp("2026-08-31", tz="UTC"))
    assert len(result) == 1 and result[0]["title"] == "Alpha style"


def test_zero_variability_abstains(cfg):
    band = rolling_band(pd.Series([0.] * 50), 2, cfg["thresholds"])
    assert direction(0, band.iloc[-1]) == "UNKNOWN"


def test_exact_target_not_latest(cfg):
    p = paths(cfg); p["data"].mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"date": "2026-08-03", "keyword": "alpha", "interest": 15, "batch_signature": "b", "snapshot_id": "s"},
                  {"date": "2026-08-20", "keyword": "alpha", "interest": 99, "batch_signature": "b", "snapshot_id": "s"}]).to_csv(p["history"], index=False)
    forecast = {"forecast_id": "a", "created_at": "2026-08-01T00:00:00+00:00", "target_date": "2026-08-03T00:00:00+00:00",
                "keyword": "alpha", "ml_current_interest": 10, "predicted_interest": 16, "ml_predicted_direction": "UP",
                "threshold": 2, "batch_signature": "b", "snapshot_id": "s", "ml_horizon_days": 2}
    append_records(p["run"] / "forecasts.jsonl", [forecast])
    assert record(cfg)["recorded"] == 1
    row = read_records(p["run"] / "outcomes.jsonl")[0]
    assert row["actual_interest"] == 15 and row["absolute_error"] == 1
    assert record(cfg)["recorded"] == 0


def test_bad_recommendation_withheld(cfg):
    from agents.configured_analysis import decision
    item = {"keyword": "cottagecore", "ml_forecast_status": "READY", "ml_predicted_direction": "UP", "numeric_direction": "UP",
            "threshold": 2., "policy_cutoffs": {"UP": .6}, "ml_probabilities": {"UP": .9}, "semantic_evidence_count": 0}
    assert decision([item], cfg)[0]["decision"] == "WAIT"


def test_text_supported_allows_validation_gated_invest(cfg):
    from agents.configured_analysis import decision
    item = {"keyword": "alpha", "ml_forecast_status": "READY",
            "ml_predicted_direction": "UP", "numeric_direction": "UP",
            "predicted_change": 4.0, "threshold": 2.0,
            "policy_cutoffs": {"UP": .6}, "ml_probabilities": {"UP": .72},
            "evidence_validation_level": "TEXT_SUPPORTED", "semantic_evidence_count": 0}
    row = decision([item], cfg)[0]
    assert row["decision"] == "INVEST"
    assert row["up_candidate"] is True


def test_seasonal_naive_probability_ties_use_keyword_numeric_margin(cfg):
    from agents.configured_analysis import decision
    shared = {"ml_forecast_status": "READY", "ml_predicted_direction": "STABLE",
              "numeric_direction": "STABLE", "threshold": 2.0,
              "policy_cutoffs": {"STABLE": .5},
              "ml_probabilities": {"UP": .144, "STABLE": .7, "DOWN": .156},
              "evidence_validation_level": "TEXT_SUPPORTED"}
    rows = decision([
        {**shared, "keyword": "weaker", "predicted_change": .2, "semantic_evidence_count": 3},
        {**shared, "keyword": "stronger", "predicted_change": 1.5, "semantic_evidence_count": 1},
    ], cfg)
    assert [x["keyword"] for x in rows] == ["stronger", "weaker"]
    assert rows[0]["watchlist_score"] > rows[1]["watchlist_score"]
    assert rows[0]["decision_score"] == rows[1]["decision_score"] == .144


def test_small_window_baseline(cfg):
    from forecast_experiment import train_experiment, infer
    cfg["window"].update(analysis_days=10, test_days=8)
    history(cfg)
    report = train_experiment(cfg)
    assert report["classifier"] == "persistence"
    rows, _, _ = infer(cfg)
    assert {x["keyword"] for x in rows} == {"alpha", "beta"}


def test_train_compare_predict(cfg):
    from forecast_experiment import train_experiment, infer
    history(cfg)
    report = train_experiment(cfg)
    assert report["test_rows"] > 0
    assert "persistence" in report["models"] and "logistic_regression" in report["models"]
    assert all(pd.Timestamp(f["train_target_end"]) < pd.Timestamp(f["validation_origin_start"]) for f in report["folds"])
    rows, _, _ = infer(cfg)
    assert all(x["predicted_interest"] >= 0 for x in rows)
    assert all(pd.Timestamp(x["target_date"]) == pd.Timestamp("2026-09-02", tz="UTC") for x in rows)


def test_failed_collection_preserves_history(cfg, monkeypatch):
    from agents.historical_data_agent import collect_configured
    import pytrends.request
    path = history(cfg)
    previous = path.read_bytes()
    cfg["collection"].update(max_retries=1, delay_seconds=0)

    class FailedClient:
        def __init__(self, **kwargs):
            pass

        def build_payload(self, *args, **kwargs):
            raise RuntimeError("simulated source failure")

    monkeypatch.setattr(pytrends.request, "TrendReq", FailedClient)
    with pytest.raises(RuntimeError, match="Prior history preserved"):
        collect_configured(cfg, refresh=True)
    assert path.read_bytes() == previous


def test_refreshed_snapshot_rebased_and_labeled(cfg):
    p = paths(cfg); p["data"].mkdir(parents=True, exist_ok=True)
    reference = [{"date": d.isoformat(), "interest": 10.} for d in pd.date_range("2026-08-01", periods=7, tz="UTC")]
    rows = [{**r, "interest": 20., "keyword": "alpha", "batch_signature": "b", "snapshot_id": "new"} for r in reference]
    rows.append({"date": "2026-08-09", "interest": 30., "keyword": "alpha", "batch_signature": "b", "snapshot_id": "new"})
    pd.DataFrame(rows).to_csv(p["history"], index=False)
    forecast = {"forecast_id": "rebased", "created_at": "2026-08-07T00:00:00+00:00", "target_date": "2026-08-09T00:00:00+00:00",
                "keyword": "alpha", "ml_current_interest": 10., "predicted_interest": 16., "ml_predicted_direction": "UP",
                "threshold": 2., "batch_signature": "b", "snapshot_id": "old", "ml_horizon_days": 2, "reference_overlap": reference}
    append_records(p["run"] / "forecasts.jsonl", [forecast])
    assert record(cfg)["recorded"] == 1
    row = read_records(p["run"] / "outcomes.jsonl")[0]
    assert row["measurement_status"] == "APPROXIMATE_REBASED"
    assert row["actual_interest"] == 15. and row["rebase_factor"] == 2.
