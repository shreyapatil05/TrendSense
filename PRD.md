# TrendSense Product Requirements Document

## 1. Product Overview

**Product name:** TrendSense  
**Product type:** Multi-agent AI and machine-learning trend-intelligence system  
**Primary domains:** Fashion and beauty  
**Initial market focus:** India  
**Primary interface:** Python command-line application  
**Current system version:** Configurable v4 pipeline

TrendSense collects digital attention signals for a user-selected set of keywords, forecasts short-horizon Google search-interest direction, validates related textual evidence, ranks the selected trends, and produces conservative INVEST, WAIT, or AVOID recommendations with reasons.

TrendSense predicts changes in normalized search interest. It does not predict guaranteed sales, profit, stock returns, or product-market success.

## 2. Problem Statement

Fashion and beauty trends change quickly across search engines, news sources, video platforms, and online marketplaces. A company or analyst cannot reliably monitor every term manually, and raw popularity values do not answer the important questions:

- Is attention rising, stable, or declining?
- Is the observed movement larger than the keyword's normal variability?
- Is there supporting textual evidence?
- Are multiple agents and models consistent?
- Is the evidence strong enough to justify action, or should the system abstain?

Earlier versions of TrendSense used a fixed keyword list, manually chosen scoring weights, global direction cutoffs, and fixed recommendation boundaries. Those choices restricted the system to predefined terms and made its decisions difficult to justify scientifically.

The current product must allow users to select any non-empty number of keywords, use data-derived thresholds and chronological validation, compare multiple models with transparent baselines, and explain why a recommendation was or was not issued.

## 3. Product Vision

TrendSense should become a reproducible trend-screening system that helps researchers and market analysts identify which selected fashion or beauty topics deserve further investigation.

The system should favor a transparent WAIT or UNAVAILABLE result over an unsupported INVEST recommendation.

## 4. Target Users

### 4.1 Primary users

- Fashion and beauty market researchers
- Small brands and product teams exploring consumer attention
- Academic researchers studying digital trend forecasting
- Students demonstrating multi-agent AI and time-series machine learning

### 4.2 Secondary users

- Marketing analysts
- Merchandising teams
- Content strategists
- Faculty evaluators reviewing the project and research methodology

## 5. User Needs

A user must be able to:

1. Select an industry.
2. Enter any non-empty number of keywords.
3. Use command-line keywords, an interactive prompt, a keyword file, or a configured preset.
4. Collect historical search-interest data only for the selected keywords.
5. Run large selections even though Google Trends accepts at most five keywords per comparison request.
6. Configure the analysis window, test window, and forecast horizon.
7. Compare adaptive threshold methods.
8. Compare four configured machine-learning classifiers with persistence and Seasonal Naive baselines.
9. Train and evaluate models without random shuffling or future leakage.
10. See every agent start, complete, or fail.
11. Understand whether missing output is caused by sparse history, external API failure, or evidence insufficiency.
12. Receive a ranked watchlist with actual model probability or score clearly separated from rank percentile.
13. Store forecasts and later compare them with observed outcomes.
14. Generate plots and machine-readable JSON reports for the research paper.

## 6. Goals

### 6.1 Product goals

- Support dynamic, variable-sized keyword selections.
- Forecast two-day search-interest direction using a configurable horizon.
- Replace fixed direction thresholds with adaptive per-keyword bands.
- Compare model families using chronological validation.
- Retain a simple baseline when it validates better than complex models.
- Use semantic NLP to validate whether retrieved text supports a selected trend.
- Produce evidence-gated recommendations and explanations.
- Preserve experiment reproducibility through configuration and artifact fingerprints.
- Support retrospective backtesting and prospective forecast verification.

### 6.2 Research goals

- Measure performance using accuracy, balanced accuracy, macro-F1, per-class precision, recall and F1, and confusion matrices.
- Compare numeric forecasts using MAE and RMSE.
- Report results against persistence and Seasonal Naive.
- Measure minority UP and DOWN performance instead of relying only on accuracy.
- Record unavailable cases instead of silently excluding them from live output.

## 7. Non-Goals

The current version does not aim to:

- Guarantee investment returns or product profitability.
- Replace professional market research.
- Scrape private accounts, private messages, or protected personal data.
- Authenticate users or provide role-based access control.
- Provide a graphical web or mobile interface.
- Perform automated purchasing, trading, advertising, or inventory allocation.
- Train a large language model from scratch.
- Claim that semantically related text proves authenticity.
- Claim that Google search interest is equivalent to sales.
- Force every run to contain INVEST, WAIT, and AVOID decisions.

## 8. Core Product Capabilities

## 8.1 Dynamic keyword selection

The system shall accept keywords through:

- `--keywords`
- `--keywords-file`
- `--interactive`
- `run_config.json`
- Industry presets where available

Requirements:

- At least one keyword is required.
- There is no application-level fixed maximum keyword count.
- Duplicate keywords are removed case-insensitively.
- Unicode and whitespace are normalized.
- Phrase keywords can be quoted in the terminal.
- Comma-separated values are accepted.
- The order is preserved because it controls normalization batches.
- There is no automatic fallback to the old fixed 55-keyword list.

## 8.2 Related-query suggestions

The user may request Google Trends related-query suggestions through `keyword_selection.py`.

Suggestions must never silently change the selected set. They are opt-in candidates that the user reviews.

Deterministic aliases may be used as retrieval fallbacks for spelling and formatting variants. Conceptual aliases must not be described as learned unless a validated NLP expansion module is actually implemented.

## 8.3 Historical data collection

The collection module shall:

- Collect the configured number of historical days.
- Split selected keywords into batches of at most five.
- Retry temporary failures using configured retry controls.
- Avoid overwriting a usable prior history file when refresh fails.
- Store keyword, date, interest, batch signature, snapshot identifier, and normalization provenance.
- Support importing compatible existing history without making new API requests.
- Isolate history by selection fingerprint.

## 8.4 Dynamic windows

The user shall be able to configure:

- `analysis_days`
- `test_days`
- `feature_warmup_days`
- `horizon_days`
- `verification_delay_days`

The test window must be smaller than the analysis window. All splits must preserve chronological order.

## 8.5 Adaptive direction labels

The system shall support:

- Median absolute deviation
- Interquartile range
- Rolling z-score
- Percentile threshold

MAD multipliers may be selected from the configured candidate list. Threshold choice must be based on validation performance, not held-out test performance.

Labels are:

- `UP`: future change is above the positive adaptive band.
- `DOWN`: future change is below the negative adaptive band.
- `STABLE`: future change remains inside the band.
- `UNKNOWN` or unavailable: the scale or required features are missing.

## 8.6 Model comparison and training

The configured final comparison shall include:

- Logistic regression
- Random forest
- Support vector machine
- XGBoost when installed
- Persistence baseline
- Seasonal Naive baseline

Optional models in the registry, such as generic gradient boosting or LightGBM, must not appear in the final comparison unless they are explicitly added to `run_config.json` and reported honestly.

Training requirements:

- Three chronological validation folds by default.
- No shuffling.
- Purging between training targets and validation origins.
- Hyperparameter search within training and validation data.
- Fold-specific class weighting.
- Macro-F1 as the primary direction-selection metric.
- Test metrics excluded from model promotion.
- Existing models replaced only when the configured validation promotion rule is satisfied.

## 8.7 Multi-agent evidence workflow

The active run shall execute these stages:

1. ML Forecaster
2. Scout Source Collector
3. Weak Signal Agent
4. Lifecycle Agent
5. Authenticity Agent
6. Semantic Evidence Agent
7. Evidence Validation Agent
8. Industry Impact Agent
9. Commercial Validation Agent
10. Decision and Ranking Agent
11. Explainability Agent

Each stage must print a visible start and completion message. Failures must name the agent and exception.

## 8.8 Scout and evidence collection

The Scout shall attempt to collect:

- YouTube Shorts and standard videos
- Google News RSS articles
- NewsAPI articles
- Google Trends time-series observations

The Scout must report source health separately. One unavailable source must not erase evidence from working sources.

Only dated, in-window, selected-keyword evidence shall be retained. Query metadata alone must not count as content evidence. Duplicate canonical URLs shall be removed.

## 8.9 Semantic evidence

The semantic agent shall use `sentence-transformers/all-MiniLM-L6-v2` unless the configuration is changed and documented.

The agent shall:

- Compare selected keywords with titles and descriptions.
- Record the model name and threshold method.
- Record semantic evidence and source counts.
- Return `READY` or an explicit unavailable state.

Semantic similarity shall not be described as proof of authenticity, independence, or sales demand.

## 8.10 Recommendation policy

The configured decision engine shall issue:

- `INVEST` only when the categorical prediction is UP, numeric direction is UP, the validation-selected UP cutoff is met, the forecast is ready, the target is genuinely future, and valid text evidence exists.
- `AVOID` only when the corresponding validated DOWN conditions pass.
- `WAIT` for STABLE forecasts, model disagreement, insufficient confidence, missing evidence, replayed targets, or unavailable forecasts.

`TEXT_SUPPORTED`, `MEDIUM`, and `HIGH` are valid text-evidence states.

INVEST means “candidate for a limited commercial trial.” It does not mean verified profitability.

## 8.11 Watchlist ranking

The system shall preserve the model's UP probability or score separately from ranking.

When Seasonal Naive produces identical class probabilities, ranking shall use:

1. UP probability
2. Numeric predicted change divided by the keyword's adaptive band
3. Semantic evidence count
4. Total retained evidence count

`watchlist_score` is a within-run rank percentile. It must never be printed as `P(UP)`.

## 8.12 Explainability

Each final row shall include:

- Keyword
- Forecast status
- Predicted direction
- Numeric forecast
- Adaptive threshold
- Model score or probability
- Watchlist rank
- Evidence status
- Final recommendation
- Decision reasons
- Model names
- Warnings and limitations

## 8.13 Forecast persistence and evaluation

The system shall:

- Save future forecasts with unique identifiers.
- Avoid persisting historical replay outputs as future forecasts.
- Record an outcome only when the exact target date is available.
- Avoid recording the same outcome twice.
- Compare predicted and actual direction.
- Calculate direction match, MAE and RMSE when enough outcomes exist.
- Produce evaluation plots when requested.

## 9. MVP Definition

The current MVP is complete when a user can:

1. Create or activate the Python environment.
2. Pass the environment check.
3. Enter any non-empty keyword set.
4. Automatically prepare missing history and models.
5. See historical data collected in batches of five.
6. See all agent stages execute.
7. Receive a forecast or explicit unavailable state for every selected keyword.
8. Receive a ranked watchlist and explained decision.
9. Generate comparison metrics, confusion matrices, model comparison plots, keyword test plots and live watchlist plots.
10. Store forecasts and evaluate them after the verification delay.

## 10. Success Criteria

### 10.1 Functional success

- A selection of 1, 5, 9, 60 or 100 keywords can be accepted without a fixed-list error.
- Google Trends requests never exceed five keywords per batch.
- Subsets can reuse the smallest compatible prepared superset.
- The Scout reads the resolved history when a superset is reused.
- Every requested keyword appears in final output, including unavailable keywords.
- The terminal distinguishes `P(UP)` from `rank_score`.
- `TEXT_SUPPORTED` can satisfy the decision evidence gate.
- No recommendation is produced from a target that is already observed unless explicitly run as replay.

### 10.2 Research success

- All candidate models are compared against at least one naive baseline.
- Chronological folds and the final held-out test are documented.
- Macro-F1 and per-class metrics are reported.
- Test performance is not used for model selection.
- Threshold sensitivity is stored and plotted.
- The research paper distinguishes historical backtesting from a live case study.

### 10.3 Reliability success

- External-source failures are visible and nonfatal where possible.
- Prior valid history survives failed refreshes.
- Model, history, configuration and results are isolated by fingerprints.
- JSON output does not contain invalid `NaN` values.
- Core tests pass before a release is shared.

## 11. Known Current Results

These values describe the recorded final experiments and must not be silently replaced:

### Fashion experiment

- Keywords: 100
- Historical rows: 9,000
- Selected threshold: rolling z-score, multiplier 1.0
- Selected direction model: Seasonal Naive
- Validation macro-F1: approximately 0.620
- Held-out accuracy: approximately 0.686
- Held-out macro-F1: approximately 0.543
- Held-out UP recall: approximately 0.652

### Beauty experiment

- Keywords: 60
- Historical rows: 5,400
- Selected threshold: IQR, multiplier 1.0
- Selected direction model: Seasonal Naive
- Validation macro-F1: approximately 0.603
- Held-out accuracy: approximately 0.784
- Held-out macro-F1: approximately 0.537
- Held-out UP recall: approximately 0.688

### Nine-keyword beauty live case

- Historical rows loaded: 810
- Retained dated text records: 113 in the cited run
- Ready forecasts: 7
- Unavailable forecasts: 2
- Decisions: INVEST 0, WAIT 9, AVOID 0
- Interpretation: no selected keyword met the validated evidence-gated UP or DOWN requirements.

## 12. Current Constraints and Risks

- Google Trends data are normalized request snapshots.
- Different batches may not be directly comparable without anchors.
- Sparse keywords can contain many zero days.
- YouTube may return HTTP 429.
- NewsAPI free-plan behavior may restrict historical results.
- Hugging Face unauthenticated downloads have lower rate limits.
- Semantic thresholds are not calibrated against a human-labeled evidence dataset.
- Authenticity remains unverified without manipulation ground truth.
- Marketplace evidence does not provide verified sales or margins.
- Ninety days are insufficient for strong seasonal conclusions.
- A two-day horizon does not establish long-term commercial value.

## 13. Future Product Scope

- Daily prospective snapshot collection
- Six to twelve months of history
- Batch anchor terms for improved Google Trends comparability
- NLP-assisted related-query expansion with human approval
- Human-labeled semantic relevance evaluation
- Probability calibration
- Confidence intervals and repeated-snapshot uncertainty
- External demand or sales proxies where legally available
- Web dashboard after the research pipeline is stable
- Safer action labels such as TRIAL, MONITOR and DEPRIORITIZE

## 14. Acceptance Checklist

- [ ] Environment check passes.
- [ ] Keywords are supplied dynamically.
- [ ] History exists for the exact selection or a compatible superset.
- [ ] Threshold comparison is generated.
- [ ] Models and baselines are compared chronologically.
- [ ] A model is promoted using validation only.
- [ ] All agents complete or expose a clear source failure.
- [ ] `TEXT_SUPPORTED` is accepted by the decision engine.
- [ ] True UP probability and rank percentile use different labels.
- [ ] Final JSON, plots and forecast records are saved.
- [ ] Claims in documentation match recorded output.
