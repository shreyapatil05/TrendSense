from evaluation.backtest import evaluate_pairs
from evaluation.ground_truth import outcome

def test_metrics_and_ground_truth():
    pairs = [
        {"actual_direction": "UP", "predicted_direction": "UP", "actual_strength": .7, "predicted_strength": .6},
        {"actual_direction": "DOWN", "predicted_direction": "UP", "actual_strength": .2, "predicted_strength": .5},
    ]
    result = evaluate_pairs(pairs)
    assert result["direction"]["accuracy"] == .5
    assert result["strength"]["mae"] > 0
    assert outcome(.2, .1, 3) == "STRENGTHENED"
    assert outcome(.2, None, 1) == "UNCERTAIN"
