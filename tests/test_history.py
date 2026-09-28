import json
from conftest import sample_signals
from storage import history

def test_observations_are_appended(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_DIR", str(tmp_path))
    path, first = history.persist_observations(sample_signals(), "2026-01-01T00:00:00+00:00")
    history.persist_observations(sample_signals(), "2026-01-02T00:00:00+00:00")
    with open(path, encoding="utf-8") as handle: lines = [json.loads(x) for x in handle]
    assert len(lines) == len(first) * 2
    assert lines[0]["provenance"]["collector"] == "scout_agent"
