from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from agents import feature_engineering_agent as features
from agents import ml_forecasting_agent as forecasting


def test_temporal_training_and_inference(tmp_path, monkeypatch):
    keywords = [f"trend-{index}" for index in range(6)]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for keyword_index, keyword in enumerate(keywords):
        for day in range(70):
            rows.append({
                "date": (start + timedelta(days=day)).isoformat(),
                "keyword": keyword,
                "industry": "fashion" if keyword_index < 3 else "beauty",
                "interest": 50 + 30 * np.sin((day + keyword_index) / 2.5),
            })
    history = tmp_path / "history.csv"
    pd.DataFrame(rows).to_csv(history, index=False)
    monkeypatch.setattr(features, "HISTORICAL_DIR", str(tmp_path))
    monkeypatch.setattr(forecasting, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(forecasting, "EVALUATION_DIR", str(tmp_path))
    bundle, _, _ = forecasting.train_forecasting_model(str(history), 1)
    assert bundle["evaluation"]["evaluated_rows"] > 0
    current = [{
        "keyword": keyword, "industry": "fashion",
        "details": {"google_trends": {"available": True, "recent_avg": 55}},
    } for keyword in keywords]
    output = forecasting.run_ml_forecasting_analysis(current, 1, str(history))
    assert all(item["ml_forecast_status"] == "READY" for item in output)
    assert all(set(item["ml_probabilities"]) == {"UP", "STABLE", "DOWN"} for item in output)
