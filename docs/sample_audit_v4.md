# Sample audit of the supplied historical data

This is a retrospective experiment, not verified prospective accuracy. It uses the default ten selected fashion keywords, a 40-day window ending 2026-09-21, latest 10 test-origin days and a 2-day horizon. The legacy collection-day observation was excluded conservatively. Changing keywords, dates or labels changes the task; these numbers are not directly comparable with the old 55-keyword reports.

After feature/label filtering, there are 196 training rows after the holdout purge and 68 mature test rows. The test has only **1 UP**, 42 STABLE and 25 DOWN examples. Sparse keywords have many zero observations: cottagecore and Y2K fashion each have 29 zero days out of 40; quiet luxury has 26. Zero robust-scale rows abstain and are excluded rather than creating arbitrary labels.

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|---:|
| Persistence | 0.262 | 0.618 | 0.255 | **6.000** | **9.144** |
| Seasonal naive | **0.587** | 0.441 | 0.337 | 11.029 | 15.606 |
| Logistic Regression / Ridge | 0.528 | 0.632 | 0.359 | 7.977 | 11.057 |
| Random Forest | 0.434 | 0.676 | 0.356 | 7.144 | 10.658 |
| Gradient Boosting | 0.462 | 0.647 | 0.355 | 7.587 | 11.706 |
| SVM / SVR | 0.555 | 0.676 | 0.415 | 7.618 | 11.892 |
| XGBoost | 0.452 | 0.632 | 0.349 | 6.786 | 10.302 |
| LightGBM | 0.498 | 0.647 | 0.375 | 7.281 | 10.956 |

Selection uses validation only: seasonal naive wins direction, and SVR wins numeric validation MAE. The selected direction model's test accuracy is below persistence, and SVR's test MAE is worse than persistence. SVM has the best test macro-F1 among candidates, but switching to it because of this test result would reuse the test for selection.

The corrected seasonal baseline uses the latest observed value on the **future target's weekday**, not a blind seven-day lag from the forecast origin. Recommendations remain WAIT when a baseline lacks a learned action threshold. Deterministic baseline outputs have no estimated confidence probability.

For the selected seasonal classifier, test precision/recall are: UP 0/0, STABLE 0.759/0.524, DOWN 0.500/0.320. Its confusion matrix (rows actual, columns predicted) is:

| | UP | STABLE | DOWN |
|---|---:|---:|---:|
| UP | 0 | 1 | 0 |
| STABLE | 12 | 22 | 8 |
| DOWN | 11 | 6 | 8 |

## What is appropriate for this data?

Keep persistence and seasonal naive as serious candidates. With few independent dates and only one UP test example, no reliable rising-trend detection claim is supported. Increasing model complexity has not solved the numeric forecasting problem. The priority is a broader daily history, meaningful selected terms with sufficient measured activity, and more untouched future targets. Do not replace rare-term observations with invented data or weaken labels merely to increase accuracy.

For the deadline, demonstrate the configurable pipeline and honest evaluation, show these limitations, and collect a small prospective sample. Use a separate development experiment for a longer analysis window if the history supports it; do not call repeated testing on this same holdout independent validation.

## Verification scope

The six model families and two baselines were actually run on the supplied history. Regression tests cover date grouping/purging, causal features, missing-day handling, selection isolation, failed-collection preservation, no fabricated query evidence, abstention, exact-date recording, approximate rebasing and training/inference. A historical replay through the agents was run with semantic inference disabled and empty text evidence.

Live Google/News/YouTube calls and a fresh Hugging Face model download were not exercised in this environment. Their availability, API quotas and credentials must be checked on the user's machine. Retained semantic functionality is integrated, but this audit does not claim a live semantic model evaluation.
