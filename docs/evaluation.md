# Evaluation protocol

1. Freeze vocabulary, outcome rules, weights, and versions.
2. Collect weekly observations for at least eight weeks.
3. Generate 1-day and 3-day forecasts.
4. Match only observations at or after maturity.
5. Evaluate TrendSense and baselines on identical cutoffs.
6. Report sample size, uncertainty, class metrics, confusion matrix, errors, and Precision at K.
7. Store experiment ID, dataset version, horizon, features, configuration, system version, model, metrics, and notes.

Error labels include false positive, false negative, early, late, unstable spike, source conflict, and missing data. Manual versioned tuning is Level 1 improvement, not self-learning.
