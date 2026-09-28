# TrendSense

TrendSense is a configurable multi-agent AI and machine-learning system for short-term fashion and beauty trend intelligence. A user selects an industry and any number of keywords. The system collects Google Trends history and supporting web evidence, forecasts trend direction, ranks the selected keywords, and returns an explainable `INVEST`, `WAIT`, or `AVOID` recommendation.

The current implementation is the dynamic v4 pipeline. It replaces the earlier fixed 55-keyword workflow, fixed `+3/-3` direction rule, manually weighted score, and Random Forest-only approach.

## What the current system supports

- Any non-empty user-selected keyword list
- Fashion, beauty, or another user-defined focused industry
- Automatic Google Trends batching with no more than five keywords per request
- Configurable historical, test, forecast, and verification windows
- Adaptive direction thresholds selected from MAD, IQR, z-score, and percentile methods
- Four compared classifiers: Logistic Regression, Random Forest, SVM, and XGBoost
- Persistence and Seasonal Naive baselines
- Time-ordered validation with no random shuffling
- Class weighting for imbalanced `UP`, `STABLE`, and `DOWN` labels
- Eighteen past-only time-series features
- Textual evidence collection from YouTube, Google News RSS, and NewsAPI
- Semantic evidence validation with a Hugging Face sentence-transformer
- Multi-agent analysis, explainable recommendations, plots, and saved forecasts
- Later comparison of saved forecasts against actual observations

## System workflow

```text
User selects industry and keywords
               |
               v
Google Trends history collected in batches of five
               |
               v
Past-only time-series features generated
               |
               v
Adaptive labels and chronological splits created
               |
               v
Four ML models and two baselines compared
               |
               v
Best validation model retained
               |
               v
Scout collects dated text and video evidence
               |
               v
Specialized agents analyse each selected keyword
               |
               v
Decision, ranking, explanation, plots, and persistence
               |
               v
Actual outcomes recorded after the forecast horizon
```

## Agent pipeline

The terminal prints each stage while the pipeline runs.

| Stage | Component | Responsibility |
| --- | --- | --- |
| 1 | ML Forecaster | Predicts numeric interest and `UP`, `STABLE`, `DOWN`, or `UNAVAILABLE` direction |
| 2 | Scout Source Collector | Collects dated evidence for only the selected keywords |
| 3 | Weak Signal Agent | Measures early cross-source activity and momentum |
| 4 | Lifecycle Agent | Estimates whether a trend is emerging, growing, stable, peaking, or declining |
| 5 | Authenticity Agent | Checks provenance and evidence quality without claiming that popularity proves authenticity |
| 6 | Semantic Evidence Agent | Uses sentence embeddings to measure text relevance |
| 7 | Evidence Validation Agent | Marks evidence such as `TEXT_SUPPORTED` or `LIMITED` |
| 8 | Industry Impact Agent | Connects a trend to relevant industry impact |
| 9 | Commercial Validation Agent | Reports available commercial support and explicitly handles missing data |
| 10 | Decision and Ranking Engine | Produces recommendations and keyword-specific ranking |
| 11 | Explainability Engine | Produces human-readable reasons and supporting fields |

## Data sources

| Source | Use |
| --- | --- |
| Google Trends | Daily normalized search-interest history and forecasting input |
| YouTube Data API or configured YouTube collector | Videos and Shorts related to selected keywords |
| Google News RSS | Dated articles related to selected keywords |
| NewsAPI | Additional dated news evidence when an API key is available |
| Hugging Face MiniLM | Semantic similarity between a keyword and collected text |

Google Trends values are relative interest indices from 0 to 100. They are not sales, revenue, demand, or market-share measurements. Values from separately normalized request batches must not be compared as if they shared one absolute scale.

## Requirements

- Python 3.10 or newer
- Internet access for fresh collection
- A YouTube API key for YouTube evidence
- A NewsAPI key for NewsAPI evidence
- Enough memory to load the sentence-transformer locally

The project was tested with Python 3.13, but Python 3.10 to 3.12 may offer wider package compatibility.

## Installation

Open Command Prompt or PowerShell in the project folder.

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If the project contains a separate optional requirements file, install it as well:

```bat
python -m pip install -r requirements-optional.txt
```

Create or update `.env` without committing it:

```env
YOUTUBE_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
HF_TOKEN=your_optional_hugging_face_token
```

`HF_TOKEN` is optional. Without it, the Hugging Face Hub may display an unauthenticated-request warning and apply lower download limits.

## Check the environment

```bat
python doctor.py
```

The first check may report missing history and model files. That is expected before a keyword selection has been collected and trained.

## Quick start with any keyword count

The keyword count is dynamic. Replace the examples with any non-empty list and quote every multi-word keyword.

```bat
python main.py --industry beauty --keywords "glass skin" "dewy skin" "skin barrier repair" "niacinamide serum" --plots
```

```bat
python main.py --industry fashion --keywords "co-ord set" "kurta set" "wide leg pants" "corset top" "quiet luxury" "tote bag" --plots
```

If an exact or compatible prepared selection exists, the system reuses it. If no compatible history and model exist, the current CLI automatically prepares the requested selection by collecting history and running model comparison before the agent pipeline.

For a clean explicit workflow, use the three commands below.

## Step 1: Collect historical data

```bat
python collect_historical.py --industry beauty --keywords "glass skin" "dewy skin" "skin barrier repair" "niacinamide serum" --refresh
```

The collector:

1. Accepts the complete variable-size keyword list.
2. Divides it into groups of at most five for Google Trends.
3. Collects the configured number of historical days.
4. Saves the selection-specific history under `data/v4/selections/<selection_id>/history.csv`.

Do not change keyword spelling or order between collection, training, and execution unless the CLI deliberately reuses a compatible superset model.

## Step 2: Train and compare models

Use the same industry and keyword list:

```bat
python train_models.py --industry beauty --keywords "glass skin" "dewy skin" "skin barrier repair" "niacinamide serum" --plots
```

Training performs the following work:

1. Builds eighteen time-series features using only information available at each prediction origin.
2. Tests MAD, IQR, z-score, and percentile direction-label methods.
3. Tunes eligible threshold parameters on chronological validation data.
4. Compares Logistic Regression, Random Forest, SVM, and XGBoost.
5. Compares every trained model with Persistence and Seasonal Naive baselines.
6. Uses chronological folds and never shuffles time-series rows.
7. Holds the latest configured days out for final testing.
8. Selects the winner using validation macro-F1, not test performance.
9. Promotes a challenger only when validation improves over the accepted model or baseline.
10. Saves metrics, predictions, plots, and the selected model bundle.

The baseline is allowed to win. A simple baseline beating the ML candidates is a valid experimental result, especially with short and noisy history.

## Step 3: Run the complete agent pipeline

```bat
python main.py --industry beauty --keywords "glass skin" "dewy skin" "skin barrier repair" "niacinamide serum" --plots
```

This command:

- Loads compatible Google Trends history and the selected model
- Forecasts only the requested keywords
- Collects current evidence from configured sources
- Runs all specialized agents
- Validates evidence semantically
- Produces the watchlist, decisions, explanations, and plots
- Saves future forecasts for later evaluation

## Configuration

The CLI arguments are the safest way to prove that keyword selection is dynamic. A `run_config.json` file can also store repeatable settings.

Typical fields include:

```json
{
  "industry": "beauty",
  "keywords": {
    "selected": [
      "glass skin",
      "dewy skin",
      "skin barrier repair"
    ]
  },
  "window": {
    "analysis_days": 90,
    "test_days": 14
  },
  "forecast": {
    "horizon_days": 2,
    "verification_delay_days": 2
  }
}
```

Run a stored configuration with:

```bat
python collect_historical.py --config run_config.json --refresh
python train_models.py --config run_config.json --plots
python main.py --config run_config.json --plots
```

The analysis, test, forecast, and verification windows are configurable. The professor's demonstration timeline can be represented as a 30-day training region, a 10-day held-out recommendation/test region, and a 2-day verification delay. Larger windows should be used when enough history is available.

## Forecasting design

### Active features

The v4 feature builder produces eighteen past-only features. They cover:

- Lagged interest
- Short and medium rolling means
- Rolling spread and robust variability
- Short-term and medium-term momentum
- Relative change
- Rolling z-score behaviour
- Local slope and acceleration
- Seasonal or weekday context

The exact feature names in the saved model bundle and `agents/window_features.py` are authoritative. Rolling features require warm-up observations, so the first rows for a keyword are not eligible training origins.

### Dynamic labels

`UP`, `STABLE`, and `DOWN` are not defined by one universal change such as `+3/-3`. The training pipeline evaluates adaptive bands:

- Median absolute deviation, or MAD
- Interquartile range, or IQR
- Rolling z-score
- Percentile-based bands

Each method adapts to the observed variability rather than treating a quiet keyword and a volatile keyword identically.

### Leakage control

- All splits follow time order.
- Shuffling is disabled.
- Features use current and past observations only.
- Target-overlap purging prevents training labels from crossing into validation.
- The final held-out test does not select the threshold or model.
- Keyword and batch-normalization boundaries are tracked.

## Semantic evidence

The semantic stage uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model converts keyword text and article or video text into embeddings. Their similarity helps determine whether evidence is relevant even when it does not repeat the keyword exactly.

Manual aliases may still be used for source retrieval because semantic similarity cannot search external APIs before results have been downloaded. Aliases improve recall for known spelling variants and editorial phrasing. The semantic model then validates the retrieved text. Aliases are retrieval aids, not manually assigned trend scores.

## Recommendations

TrendSense separates ranking from recommendation.

### INVEST

`INVEST` is issued only when the configured decision requirements are satisfied, including:

- Forecast direction is `UP`
- Numeric forecast also exceeds the selected adaptive band
- Classifier and numeric forecast agree
- Confidence clears a validation-derived requirement
- Valid evidence such as `TEXT_SUPPORTED`, `MEDIUM`, or `HIGH` is present

`INVEST` means a limited trial candidate. It does not promise profit.

### AVOID

`AVOID` is used for a sufficiently supported declining forecast when the categorical and numeric signals agree.

### WAIT

`WAIT` is an explicit abstention. It is appropriate for stable forecasts, unavailable features, disagreement, insufficient confidence, or limited evidence.

The system must not force an `INVEST` result simply to make the output look more exciting.

## Ranking

The watchlist rank and `P(UP)` are different fields.

- `P(UP)` is the model or validation-derived upward-class confidence.
- `rank_score` breaks ties using keyword-specific numeric momentum, forecast movement, evidence, and other available ranking signals.
- A keyword can rank first and still receive `WAIT` when its direction is stable.

This distinction is important when Seasonal Naive assigns identical class probabilities to multiple keywords.

## Outputs

Selection-specific files are stored under `data/v4/`. The terminal prints the exact output directories.

| Output | Purpose |
| --- | --- |
| `history.csv` | Daily Google Trends history for a selection |
| `comparison.json` | Threshold, model, baseline, fold, class, and test metrics |
| `test_predictions.json` | Held-out actual values and model predictions |
| `model.joblib` | Selected trained model bundle and metadata |
| `model_metrics*.csv` | Validation and held-out metrics for compared candidates |
| `model_comparison*.png` | Model and baseline comparison plot |
| `confusion_matrix*.png` | Held-out class confusion matrix for the selected classifier |
| `test_<keyword>.png` | Past versus predicted behaviour for a keyword |
| `selected_window_*.png` | User-selected analysis-window plots |
| `watchlist.png` | Ranked live watchlist |
| `final_results_*.json` | Complete agent outputs, recommendations, and explanations |
| `forecasts.jsonl` | Forecasts saved at issue time |
| `outcomes.jsonl` | Actual observations matched to mature forecasts |
| `outcome_pending.json` | Forecasts that cannot yet be verified and their reasons |
| `live_evaluation.json` | Prospective performance against actual outcomes and baselines |

The plotting code must close each Matplotlib figure after saving it. This prevents the `More than 20 figures have been opened` warning when many keywords are processed.

## Evaluate forecasts after the target date

Forecast evaluation cannot be completed immediately because the future actual value does not exist yet. After the forecast horizon and verification delay have passed, run:

```bat
python collect_historical.py --config run_config.json --refresh
python record_outcomes.py --config run_config.json
python evaluate_forecasts.py --config run_config.json --plots
```

The evaluation reports:

- Direction match
- Accuracy and macro-F1
- Per-class precision and recall
- Confusion matrix
- Numeric mean absolute error
- Numeric root mean squared error
- Performance against Persistence and Seasonal Naive
- Verified, approximate, or pending measurement status

Use the same selection and compatible Google Trends normalization when verifying a forecast. Google Trends can revise or rescale historical values, so approximate rebasing must be labelled honestly.

## Recorded experiment results

The following are the final recorded held-out results used in the current project documentation. They must not be described as live prospective accuracy.

### Fashion experiment

| Item | Result |
| --- | ---: |
| Keywords | 100 |
| Historical rows | 9,000 |
| Training examples | 5,708 |
| Held-out test examples | 1,107 |
| Selected threshold | z-score × 1.0 |
| Selected classifier | Seasonal Naive |
| Selected regressor | SVM |
| Validation macro-F1 | 0.6202 |
| Held-out accuracy | 0.6856 |
| Held-out balanced accuracy | 0.6047 |
| Held-out macro-F1 | 0.5434 |
| UP precision | 0.4167 |
| UP recall | 0.6522 |
| DOWN recall | 0.4341 |
| Numeric MAE | 7.0163 |
| Numeric RMSE | 11.9992 |

### Beauty experiment

| Item | Result |
| --- | ---: |
| Keywords | 60 |
| Historical rows | 5,400 |
| Training examples | 2,496 |
| Held-out test examples | 421 |
| Selected threshold | IQR × 1.0 |
| Selected classifier | Seasonal Naive |
| Selected regressor | SVM |
| Validation macro-F1 | 0.6027 |
| Held-out accuracy | 0.7838 |
| Held-out balanced accuracy | 0.5842 |
| Held-out macro-F1 | 0.5369 |
| UP precision | 0.4151 |
| UP recall | 0.6875 |
| DOWN recall | 0.2105 |
| Numeric MAE | 6.9596 |
| Numeric RMSE | 11.5005 |

Accuracy is not enough because the classes are imbalanced. Macro-F1, balanced accuracy, per-class precision and recall, and confusion matrices must be reported with it.

## Current limitations

- Ninety days of history is short for reliable long-term forecasting.
- Google Trends supplies normalized attention, not commercial demand.
- YouTube may return HTTP 429 when quota or rate limits are reached.
- NewsAPI may return no results when the key, plan, date range, or query limits access.
- Rare or flat keywords may have zero robust variability and return `UNAVAILABLE`.
- Seasonal Naive currently beats the trained classifiers on validation for the recorded fashion and beauty selections.
- The current live demonstration produced stable forecasts and `WAIT` recommendations. This is valid abstention, not proof that `INVEST` is impossible.
- More prospective forecast outcomes are required before making strong generalization claims.
- Commercial validation does not prove profitability when direct marketplace evidence is absent.

## Troubleshooting

### No prepared history or model

Run `main.py` normally to allow automatic preparation, or explicitly run collection and training with exactly the same industry and keywords.

### `UNAVAILABLE` direction

The keyword may have insufficient non-zero history, zero robust variability, missing recent features, or too few warm-up observations. Refresh history and inspect `history.csv` before changing thresholds.

### All recommendations are `WAIT`

Check the predicted directions and reasons. If forecasts are genuinely stable or signals disagree, `WAIT` is correct. Do not lower the decision requirements just to generate `INVEST`.

### YouTube HTTP 429

Wait for the quota or rate-limit window to reset, verify `YOUTUBE_API_KEY`, reduce repeated requests, and reuse a valid cache when appropriate. Other agents can still run, but the final evidence record should show that YouTube evidence was unavailable.

### Hugging Face unauthenticated warning

Set `HF_TOKEN` for higher Hub limits. The warning does not mean the local model failed if its weights load successfully.

### `More than 20 figures have been opened`

Ensure every plotting function calls `plt.close(fig)` after `fig.savefig(...)`.

### Old plot timestamps

Use the experiment directory printed by the latest command. Different keyword selections have different hashed directories. Sort files by modification time and confirm the new `comparison.json` path.

## Tests

Run available regression tests from the project root:

```bat
python -m pytest -q
```

At minimum, verify:

- Arbitrary keyword counts
- Five-keyword batching
- Exact filtering to selected keywords
- Chronological split order
- No target overlap across folds
- Feature columns match the saved bundle
- Baseline comparison is present
- Class metrics and confusion matrix are generated
- All agents preserve one record per selected keyword
- `TEXT_SUPPORTED` is accepted as valid decision evidence
- Ranking remains keyword-specific when class probabilities tie
- Forecasts are persisted only when intended

## Documentation

- `PRD.md`: what the project builds, users, scope, requirements, and success criteria
- `ARCHITECTURE.md`: pipeline, modules, data flow, folder structure, and architectural boundaries
- `RULES.md`: coding, ML, evidence, security, testing, and documentation rules
- `DECISIONS.md`: important technical decisions and the reasons behind them
- `TRENDSENSE_PROJECT_EXPLANATION.md`: detailed explanation, experiment results, viva questions, and interview scripts
- `docs/implementation_v4.md`: implementation mapping for the professor's requested changes

## Responsible claims

Safe claims:

- TrendSense is a configurable multi-agent AI and ML prototype.
- It forecasts short-term Google search-interest direction.
- It compares trained classifiers with naive time-series baselines.
- It uses adaptive thresholds and chronological evaluation.
- It validates supporting text using sentence embeddings.
- It can abstain when confidence, agreement, or evidence is insufficient.

Claims to avoid:

- Guaranteed investment returns
- Guaranteed trend authenticity
- Guaranteed 90 percent accuracy
- Direct prediction of sales or profit
- Proof that one experiment generalizes to every industry
- Claims that all external sources were available when logs show rate limits or missing data

## Project status

TrendSense v4 is suitable as a final-year research prototype and demonstration system. Its strongest contribution is not a forced `INVEST` output. Its contribution is a reproducible dynamic pipeline that selects user keywords, adapts labels to observed behaviour, compares ML models against honest baselines, validates evidence through specialized agents, explains abstention, and stores forecasts for future verification.
