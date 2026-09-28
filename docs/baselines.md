# Baselines

Persistence keeps the current direction. Momentum maps velocity sign to direction. Moving average compares the latest short-window mean with the preceding window. All use the same historical cutoff as TrendSense.

Add logistic regression only after enough labelled pairs exist. TrendSense may claim improvement only after it beats baselines on the same walk-forward folds. No genuine comparison result exists yet.
