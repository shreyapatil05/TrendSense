"""Reproducible forecasting baselines."""
def persistence(current_direction, **_): return current_direction

def momentum(velocity, **_):
    return "UP" if velocity > 0 else "DOWN" if velocity < 0 else "STABLE"

def moving_average(values, window=3):
    if len(values) < 2: return "UNKNOWN"
    current = sum(values[-window:]) / min(window, len(values))
    prior_values = values[-window-1:-1]
    if not prior_values: return "UNKNOWN"
    prior = sum(prior_values) / len(prior_values)
    return "UP" if current > prior else "DOWN" if current < prior else "STABLE"
