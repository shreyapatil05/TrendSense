from conftest import sample_signals
from main import run_pipeline

def test_full_pipeline_scores_all_55_keywords(tmp_path, monkeypatch):
    import main
    monkeypatch.setattr(main, "PROCESSED_DIR", str(tmp_path))
    output = run_pipeline(sample_signals(), persist=False, semantic_enabled=False)
    assert len(output) == 55
    assert all(x["decision"] in {"INVEST", "WAIT", "AVOID"} for x in output)
    assert all("explanation" in x for x in output)
    assert all("ml_forecast_status" in x for x in output)
