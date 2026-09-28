# Forecast validation

Detection, forecasting, and business decisions are different tasks and are evaluated separately.

At time T, TrendSense stores a 1-day or 3-day forecast using only evidence available at T. At T plus H, new observations define UP, STABLE, or DOWN. STRENGTHENED or WEAKENED requires movement plus confirmation from at least two source types. Sparse or conflicting outcomes are UNCERTAIN.

Use expanding-window or walk-forward evaluation, never a random time split.

Metrics are macro F1, balanced accuracy, and confusion matrix for direction; MAE and RMSE for strength; Precision at K for ranking; and per-class decision precision, especially INVEST. Uncertain outcomes are excluded from accuracy and counted separately.
