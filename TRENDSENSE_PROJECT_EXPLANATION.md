# TrendSense Project: Complete Technical Explanation

**Document purpose:** Current code-level explanation, team onboarding guide, research defense, execution reference, and viva preparation document.  
**Active system:** Configurable TrendSense v4 pipeline  
**Domain:** Short-horizon fashion and beauty search-attention forecasting for India  
**Primary entry point:** `main.py`  
**Active orchestration:** `cli_v4.py`  
**Default forecast horizon:** 2 days  
**Last aligned with project:** 28 September 2026

---

## Table of Contents

1. Project Summary
2. Problem and Objectives
3. Current Architecture
4. Runtime Workflow
5. Dynamic Keywords
6. Data Sources and Storage
7. Features and Adaptive Labels
8. Training and Leakage Prevention
9. Models, Baselines and Imbalance
10. Agent-by-Agent Explanation
11. Semantic NLP
12. Decision and Ranking
13. Forecast Verification
14. Experimental Results
15. Live Beauty Case
16. Commands and Outputs
17. Classification of the Project
18. Contributions and Limitations
19. Safe and Unsafe Claims
20. File Mapping
21. Viva Questions
22. Verbal Explanations
23. Glossary

---

## 1. Project Summary

TrendSense is a configurable multi-agent AI and machine-learning system that forecasts whether user-selected fashion or beauty search trends are rising, stable, declining, or unavailable. It validates related textual evidence, ranks the selected trends, and produces conservative INVEST, WAIT, or AVOID recommendations with explicit reasons.

The current TrendSense is not the earlier fixed 55-keyword Random Forest prototype. The active v4 system provides:

- Any non-empty number of user-selected keywords
- Google Trends collection in batches of at most five
- Selection-specific history and experiment storage
- Dynamic analysis, test and forecast windows
- Adaptive MAD, IQR, z-score and percentile direction bands
- Four configured machine-learning classifiers
- Persistence and Seasonal Naive baselines
- Chronological hyperparameter search and model promotion
- Fold-specific class weighting
- Transformer-based semantic evidence
- Evidence-gated recommendations
- Keyword-specific ranking when baseline probabilities tie
- Stored forecasts and delayed future verification

TrendSense forecasts normalized search attention. It does not guarantee sales, profit, product success, or financial return.

---

## 2. Problem and Objectives

Fashion and beauty attention changes quickly. A company may observe a term becoming common in videos, articles, or search activity, but raw online visibility does not answer:

- Is interest actually rising, stable, or declining?
- Is the movement larger than the keyword's usual noise?
- Is there supporting textual evidence?
- Do categorical and numeric forecasts agree?
- Is there enough confidence to recommend action?

The original prototype used a fixed vocabulary, global direction cutoffs, manual weights, and limited model comparison. Those choices made the system difficult to reuse and defend scientifically.

### Current objectives

1. Allow users to select the industry and any non-empty keyword set.
2. Collect historical Google Trends data safely under the five-keyword request constraint.
3. Generate past-only time-series features.
4. Replace the fixed `+3/-3` rule with validation-selected adaptive labels.
5. Compare four ML classifiers with two transparent baselines.
6. Prevent temporal leakage through chronological folds and a held-out test interval.
7. Improve minority UP and DOWN learning through fold-specific class weights.
8. Collect and semantically validate external textual evidence.
9. Produce traceable recommendations without claiming verified profitability.
10. Store predictions and evaluate them after their future target dates arrive.

---

## 3. Current Architecture

The active entry path is:

```text
main.py
  -> cli_v4.py
  -> runtime_config.py
  -> selection/model resolver
  -> forecast_experiment.py
  -> evidence agents
  -> decision and explanation
  -> JSON, JSONL, CSV and plots
```

High-level architecture:

```text
USER INPUT
industry + keywords + analysis window + test size + horizon
        |
        v
CONFIGURATION VALIDATION AND ARTIFACT RESOLUTION
        |
        +---------------------------+
        |                           |
        v                           v
GOOGLE TRENDS HISTORY          LIVE TEXT EVIDENCE
        |                      YouTube / RSS / NewsAPI
        v                           |
FEATURES + ADAPTIVE LABELS          v
        |                      EVIDENCE AGENTS
        v                           |
MODEL COMPARISON / INFERENCE        |
        +-------------+-------------+
                      v
             DECISION AND RANKING
                      |
                      v
          EXPLANATION + SAVED OUTPUTS
```

Each agent has a bounded task, defined inputs, structured outputs, and a visible failure state. The agents are not all LLMs. The ML Forecaster uses trained models and baselines, the Semantic Agent uses a pretrained transformer, and several agents use transparent deterministic logic.

---

## 4. Runtime Workflow

When `python main.py` runs:

1. `main.py` delegates to `cli_v4.main("run")`.
2. The CLI loads `run_config.json`.
3. Command-line values override the in-memory configuration.
4. `runtime_config.validate_config()` checks all values.
5. TrendSense computes selection and experiment fingerprints.
6. It searches for an exact prepared history and model.
7. If exact artifacts are missing, it searches for the smallest compatible trained superset.
8. If no compatible model exists, it collects or imports history and trains automatically.
9. The ML Forecaster produces categorical and numeric forecasts.
10. The Scout collects source evidence only for requested keywords.
11. The analysis agents enrich each keyword.
12. The Decision Agent applies validation-selected gates.
13. The Explainability Agent records reasons and warnings.
14. The terminal prints a watchlist and every selected keyword.
15. Results and plots are saved under the current experiment.
16. Future forecasts are appended for later verification unless disabled or replayed.

### Compatible subset reuse

If a five-keyword selection is a subset of an existing compatible nine-keyword model, TrendSense can reuse the nine-keyword model and history. Compatibility requires the same industry, country, forecast horizon, analysis window, and warm-up period.

The Scout reads the resolved prepared history rather than searching for a nonexistent exact-subset `history.csv`.

---

## 5. Dynamic Keywords

TrendSense accepts one keyword or a large list such as 5, 9, 60, or 100 keywords.

### Direct input

```powershell
python main.py --industry beauty --keywords "glass skin" "lip liner" --plots
```

### Interactive input

```powershell
python main.py --interactive --plots
```

### File input

```powershell
python main.py --industry fashion --keywords-file fashion_keywords.txt --plots
```

### Configured keywords

```powershell
python main.py --use-config-keywords --plots
```

`keyword_selection.py` normalizes Unicode and whitespace, removes case-insensitive duplicates, preserves order, and rejects an empty list. There is no automatic fallback to the old 55-keyword set.

### Why order matters

Google Trends normalizes values inside each comparison request. The order controls five-keyword batch membership, so sorting could change normalization context.

### Suggestions and aliases

Google Trends related-query suggestions are opt-in and never silently modify the selected list.

Small alias dictionaries remain useful for retrieval because external APIs require query text before the NLP model runs. The transformer validates retrieved candidates after collection. Conceptual aliases are manually curated and should be reported as a limitation.

---

## 6. Data Sources and Storage

### Active configured source groups

| Source | Purpose | Current behavior |
|---|---|---|
| Google Trends | Daily search-interest history | Core forecasting source |
| YouTube | Video and Shorts metadata | May return HTTP 429 |
| Google News RSS | Dated editorial evidence | Main no-key article source |
| NewsAPI | Dated news evidence | Depends on API key, plan and date access |

Legacy files may contain older integrations such as Wikipedia or autocomplete. Their presence does not prove they contributed to a configured v4 experiment.

### Evidence filtering

An item is retained only when:

- Content matches a selected keyword.
- It has a parseable publication date.
- It falls within the selected analysis period.
- Its canonical URL is not already retained.

Injected query or `seed_topic` metadata alone does not count as evidence.

### Historical defaults

- History: 90 days
- Analysis window: 90 days
- Held-out test: 14 days
- Feature warm-up: 21 days
- Forecast horizon: 2 days
- Verification delay: 2 days
- Batch size: 5

Google Trends exposes past observations, so 90 days can be downloaded today. This is retrospective history, not 90 days of prospective collection by the project.

### Selection artifacts

```text
data/v4/selections/<selection_id>/
├── history.csv
├── signals.json
└── scout_health.json
```

### Experiment artifacts

```text
data/v4/experiments/<experiment_id>/
├── comparison.json
├── config.json
├── features.csv
├── model.joblib
├── test_predictions.json
├── forecasts.jsonl
├── outcomes.jsonl
├── final_results_<timestamp>.json
└── plots/
```

Fingerprints prevent one selection or experiment from overwriting another.

---

## 7. Features and Adaptive Labels

### Active 18 features

The v4 feature set is defined in `agents/window_features.py`.

| Features | Purpose |
|---|---|
| `interest` | Current search-interest level |
| `lag1`, `lag3`, `lag7` | Previous levels |
| `mean3`, `mean7`, `mean14` | Short and medium rolling levels |
| `std7` | Local variability |
| `change1`, `change3` | Absolute movement |
| `gap3_14` | Short-versus-medium mean gap |
| `relative_change1`, `relative_change3` | Scale-adjusted movement |
| `relative_trend7` | Relative weekly movement |
| `relative_gap3_14` | Scale-adjusted mean gap |
| `rolling_z7` | Local standardized deviation |
| `day_sin`, `day_cos` | Cyclical weekday position |

Every feature at origin day `t` uses only observations at or before `t`.

### Adaptive labels

For keyword `k`, origin `t`, and horizon `h`:

```text
delta = interest(t + h) - interest(t)
```

A keyword-specific band is calculated from changes already visible at `t`:

```text
delta > band        -> UP
delta < -band       -> DOWN
otherwise           -> STABLE
zero/invalid band   -> UNKNOWN
```

Compared band methods:

1. Median absolute deviation (MAD)
2. Interquartile range (IQR)
3. Rolling z-score scale
4. Percentile of absolute changes

MAD multipliers `0.6`, `0.8`, `1.0`, `1.2`, and `1.4` are also compared.

Recorded winners:

- Fashion: rolling z-score × 1.0
- Beauty: IQR × 1.0

Different domain winners demonstrate why one fixed `+3/-3` rule was inappropriate.

---

## 8. Training and Leakage Prevention

Random shuffling is prohibited.

TrendSense uses:

- Three expanding chronological validation folds
- A final untouched chronological test interval
- Past-only features
- Fold-fitted scalers
- Training-fold class weights
- Purging so training target dates end before validation origins begin

Threshold method, threshold multiplier, class-weight strength, hyperparameters, and classifier are selected without viewing final test performance.

This may produce lower accuracy than a random split, but it is a more defensible estimate of future performance.

---

## 9. Models, Baselines and Imbalance

### Four configured ML classifiers

1. Logistic regression
2. Random forest
3. Support vector machine
4. XGBoost

These represent linear, bagged-tree, margin-based, and boosted-tree families.

`model_registry.py` also contains optional experimental candidates. A model being present in the registry does not mean it was used in the reported final experiment.

### Baselines

- Persistence
- Seasonal Naive

Seasonal Naive uses the most recent observation aligned with the future target's weekday.

### Numeric regression

Direction classification and numeric future-interest forecasting are separate tasks. The recorded final bundles selected an SVM regressor for the numeric task.

### Class imbalance

STABLE is more common than UP and DOWN. TrendSense therefore reports accuracy, balanced accuracy, macro-F1, class-wise precision, recall and F1, and confusion matrices.

Class-weight exponent is searched inside training folds:

```text
0.0 = unweighted
0.5 = moderate balancing
1.0 = full balancing
```

The recorded final experiments selected moderate weighting for all four ML classifiers.

### Model selection

Validation macro-F1 is the primary direction metric. A challenger is promoted only when validation satisfies the configured improvement rule. Test metrics do not control promotion.

Seasonal Naive won the recorded fashion and beauty validation comparisons. Retaining it is a strength because the system did not assume complex ML must win.

---

## 10. Agent-by-Agent Explanation

### 10.1 ML Forecaster

**Files:** `forecast_experiment.py`, `agents/window_features.py`, `model_registry.py`

Produces categorical direction, class scores, numeric future interest, numeric direction, adaptive threshold, target date, model names, coverage and provenance.

### 10.2 Scout Source Collector

**Files:** `agents/scout_agent.py`, `agents/selected_scout.py`

Collects dated evidence for the exact selected keywords and reports source health. One failed source does not erase usable sources.

### 10.3 Weak Signal Agent

**File:** `agents/weak_signal_agent.py`

Counts observed evidence by source and retains raw evidence. Configured v4 does not use arbitrary source weights.

### 10.4 Lifecycle Agent

**File:** `agents/lifecycle_agent.py`

Maps measured direction to growth, stable, decline, or unknown descriptions. Longer adoption stages require more evidence.

### 10.5 Authenticity Agent

**File:** `agents/authenticity_agent.py`

The correct term is **Authenticity Agent**, not Authentication Agent. It reports domains, duplicates and provenance. It returns `UNVERIFIED` without labeled manipulation ground truth.

### 10.6 Semantic Evidence Agent

**File:** `agents/semantic_evidence_agent.py`

Uses sentence embeddings to compare keywords with candidate titles and descriptions. It records relevant snippets, similarities, evidence counts and source counts.

### 10.7 Evidence Validation Agent

**File:** `agents/evidence_validation_agent.py`

Produces `TEXT_SUPPORTED` when relevant semantic text exists and `LIMITED` when it does not. `TEXT_SUPPORTED` is valid decision evidence.

### 10.8 Industry Impact Agent

**File:** `agents/industry_impact_agent.py`

Maps trends to applicable industries, categories and business areas. Configured output is descriptive, not a learned revenue estimate.

### 10.9 Commercial Validation Agent

**File:** `agents/commercial_potential.py`

Attempts to collect marketplace evidence and explicitly states when sales, margin, or profitability data are unavailable.

### 10.10 Decision and Ranking Agent

**Files:** `agents/decision_engine.py`, `agents/configured_analysis.py`

Applies validation-selected action gates and keyword-specific ranking. Configured calls delegate to `configured_analysis.decision()`.

### 10.11 Explainability Agent

**File:** `agents/explainability_engine.py`

Attaches decision reasons, warnings, direction and numeric model names, and limitations.

---

## 11. Semantic NLP

### Model

```text
sentence-transformers/all-MiniLM-L6-v2
```

This is a free pretrained Hugging Face sentence-transformer. TrendSense uses it for inference and has not fine-tuned it.

### Workflow

```text
keyword
  -> retrieved candidate text
  -> MiniLM sentence embeddings
  -> cosine similarity
  -> adaptive semantic threshold
  -> relevant evidence snippets
  -> TEXT_SUPPORTED or LIMITED
```

The semantic model does not forecast direction, prove authenticity, or predict profit. An unauthenticated Hugging Face warning means lower hub download limits, not failed inference.

---

## 12. Decision and Ranking

The configured v4 decision engine does not use the old weighted decision score or global `0.70` INVEST boundary.

### INVEST

All conditions must pass:

1. Forecast status is READY.
2. Target remains in the future.
3. Classifier direction is UP.
4. Numeric direction is UP.
5. UP score meets the validation-selected UP cutoff.
6. Evidence is `TEXT_SUPPORTED`, `MEDIUM`, or `HIGH`.

INVEST means limited trial candidate, not guaranteed profitability.

### AVOID

The corresponding DOWN direction, numeric agreement, validation cutoff, and evidence gates must pass.

### WAIT

WAIT is returned for:

- STABLE forecasts
- Classifier and numeric disagreement
- Score below the validation cutoff
- Missing text support
- Unavailable features or variability
- Historical replay

WAIT is a valid abstention.

### Ranking when probabilities tie

Seasonal Naive may assign the same empirical UP score to all keywords predicted as one class. TrendSense breaks ties using:

1. UP score
2. Numeric change divided by the adaptive threshold
3. Semantic evidence count
4. Total evidence count
5. Keyword text as a deterministic final fallback

Two values must remain separate:

```text
P(UP)      = model or baseline UP score
rank_score = within-run rank percentile
```

`rank_score=1.000` means first place, not a 100% chance of rising.

---

## 13. Forecast Verification

A future forecast cannot be evaluated on the day it is created.

```text
main.py
  -> forecasts.jsonl
  -> wait for exact target date
  -> record_outcomes.py
  -> outcomes.jsonl
  -> evaluate_forecasts.py
  -> direction match, MAE, RMSE and plots
```

Rules:

- Prefer the exact target date.
- Do not replace a missing target with the latest observation.
- Do not record the same outcome twice.
- Do not persist historical replay as a new future forecast.

---

## 14. Experimental Results

### Fashion

| Item | Result |
|---|---:|
| Keywords | 100 |
| Historical rows | 9,000 |
| Labeled rows | 5,708 |
| Test rows | 1,107 |
| Selected threshold | Rolling z-score × 1.0 |
| Selected classifier | Seasonal Naive |
| Numeric model | SVM regressor |
| Validation macro-F1 | 0.6202 |
| Test accuracy | 0.6856 |
| Test balanced accuracy | 0.6047 |
| Test macro-F1 | 0.5434 |
| UP precision | 0.4167 |
| UP recall | 0.6522 |
| DOWN recall | 0.4341 |
| Numeric MAE | 7.0163 |
| Numeric RMSE | 11.9992 |

### Beauty

| Item | Result |
|---|---:|
| Keywords | 60 |
| Historical rows | 5,400 |
| Labeled rows | 2,496 |
| Test rows | 421 |
| Selected threshold | IQR × 1.0 |
| Selected classifier | Seasonal Naive |
| Numeric model | SVM regressor |
| Validation macro-F1 | 0.6027 |
| Test accuracy | 0.7838 |
| Test balanced accuracy | 0.5842 |
| Test macro-F1 | 0.5369 |
| UP precision | 0.4151 |
| UP recall | 0.6875 |
| DOWN recall | 0.2105 |
| Numeric MAE | 6.9596 |
| Numeric RMSE | 11.5005 |

Beauty XGBoost achieved a stronger held-out macro-F1 of approximately `0.5948`, but its validation macro-F1 was approximately `0.5582`. Selecting it after viewing the test set would be test-set leakage.

Persistence achieved high raw accuracy because STABLE dominated, but balanced accuracy was `0.3333`. This is why accuracy alone is not an acceptable model-selection metric.

---

## 15. Live Beauty Case

Selected keywords:

```text
glass skin, dewy skin, skin barrier repair, ceramide moisturizer,
niacinamide serum, vitamin c serum, retinol serum, lip liner, bold brow
```

Recorded run:

- Google Trends rows: 810
- YouTube: HTTP 429, zero retained videos
- Google News RSS: 764 raw entries
- NewsAPI: zero articles
- Final retained dated evidence: 113 items
- Ready forecasts: 7
- Unavailable forecasts: 2
- Ready directions: all STABLE
- Empirical P(UP): 0.144 for ready STABLE forecasts
- Decisions: INVEST 0, WAIT 9, AVOID 0

Watchlist order:

1. Glass skin
2. Niacinamide serum
3. Vitamin C serum
4. Lip liner
5. Ceramide moisturizer
6. Retinol serum
7. Skin barrier repair

Dewy skin and bold brow were unavailable because the latest features or robust variability were insufficient.

This is a valid result. The system should not lower thresholds to manufacture INVEST. Historical test results demonstrate UP detection, while the live case demonstrates conservative abstention.

---

## 16. Commands and Outputs

### Install

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-optional.txt
```

### Check environment

```powershell
python doctor.py
```

### Run any selection

```powershell
python main.py --industry beauty --keywords "glass skin" "lip liner" --plots
```

### Force fresh history and training

```powershell
python main.py --industry beauty --keywords "glass skin" "lip liner" --refresh-history --retrain --plots
```

### Separate collection and training

```powershell
python collect_historical.py --industry beauty --keywords "glass skin" "lip liner" --refresh
python train_models.py --industry beauty --keywords "glass skin" "lip liner" --plots
```

### Record and evaluate mature forecasts

```powershell
python record_outcomes.py --industry beauty --keywords "glass skin" "lip liner"
python evaluate_forecasts.py --industry beauty --keywords "glass skin" "lip liner" --plots
```

### Important outputs

| File | Purpose |
|---|---|
| `comparison.json` | Full training, threshold, validation, test and promotion report |
| `model_metrics*.csv` | Per-model metric summary |
| `confusion_matrix*.png` | Actual versus predicted classes |
| `model_comparison*.png` | Model performance comparison |
| `test_<keyword>.png` | Held-out numeric forecast plot |
| `watchlist.png` | Within-run rank percentile plot |
| `final_results_<timestamp>.json` | Complete enriched output |
| `forecasts.jsonl` | Pending future forecasts |
| `outcomes.jsonl` | Mature observed outcomes |

`--offline` disables marketplace fetching only. It does not mean every source or model is offline.

---

## 17. Classification of the Project

TrendSense is:

### Machine learning

It trains and compares classifiers and regressors on historical time-series features.

### Artificial intelligence

It uses transformer NLP, model-based forecasting, automated decision gates, ranking and explanations.

### Multi-agent architecture

It divides the workflow among specialized components with structured handoffs.

Best description:

> TrendSense is a multi-agent AI/ML decision-support system combining short-horizon time-series forecasting, transformer-based semantic evidence matching, and transparent rule-based safety gates.

It is not a fully autonomous LLM swarm.

---

## 18. Contributions and Limitations

### Main contributions

1. Variable-sized keyword selection
2. Five-keyword Google Trends batching
3. Selection and experiment fingerprints
4. Adaptive, causal direction labels
5. Chronological model comparison
6. Four ML families and two baselines
7. Fold-specific class weighting
8. Validation-only model promotion
9. Transformer semantic evidence
10. Explicit missingness and abstention
11. Keyword-specific tie ranking
12. Prospective forecast storage and verification

The contribution is the integrated architecture and evaluation protocol, not a newly invented ML algorithm.

### Current limitations

1. Only 90 historical days
2. Retrospectively normalized Google Trends snapshots
3. Cross-batch normalization differences
4. Many zeros for niche keywords
5. YouTube rate limits
6. NewsAPI plan restrictions
7. No human-labeled semantic relevance dataset
8. No manipulation ground truth
9. No verified sales or margin data
10. No calibrated commercial-success probabilities
11. No confidence intervals or significance tests
12. CLI only

### Best next improvements

- Collect prospective daily snapshots for six to twelve months.
- Add anchor terms across Google Trends batches.
- Label semantic evidence manually and calibrate its threshold.
- Calibrate directional probabilities on a separate chronological period.
- Add temporal confidence intervals.
- Evaluate matured forecasts repeatedly.
- Add a web interface only after the research pipeline is stable.

---

## 19. Safe and Unsafe Claims

### Safe

- TrendSense accepts any non-empty keyword set.
- It compares four configured ML models and two baselines.
- It uses chronological validation.
- Seasonal Naive won the recorded validation experiments.
- It uses MiniLM for semantic text relevance.
- It reports class-wise performance.
- It supports evidence-gated INVEST, WAIT and AVOID.
- The cited live run produced nine WAIT decisions.
- It forecasts normalized search attention.

### Unsafe

- “TrendSense guarantees profit.”
- “The model achieved 90% accuracy.”
- “Every agent is an LLM.”
- “MiniLM forecasts the future.”
- “All trends are verified authentic.”
- “Rank score 1.0 means 100% probability.”
- “All sources contributed to every run.”
- “XGBoost was deployed because it won the test set.”
- “The 90-day history was prospectively collected by our team.”
- “TrendSense predicts sales.”

---

## 20. File Mapping

| Concept | File |
|---|---|
| Primary run | `main.py` |
| Configured CLI | `cli_v4.py` |
| Config validation, paths and reuse | `runtime_config.py` |
| Dynamic keywords | `keyword_selection.py` |
| Adaptive bands and cutoffs | `adaptive_thresholds.py` |
| Training and inference | `forecast_experiment.py` |
| Model registry | `model_registry.py` |
| V4 features | `agents/window_features.py` |
| Historical collection | `agents/historical_data_agent.py` |
| Scout | `agents/scout_agent.py`, `agents/selected_scout.py` |
| Weak signal | `agents/weak_signal_agent.py` |
| Lifecycle | `agents/lifecycle_agent.py` |
| Authenticity | `agents/authenticity_agent.py` |
| Semantic evidence | `agents/semantic_evidence_agent.py` |
| Evidence validation | `agents/evidence_validation_agent.py` |
| Industry impact | `agents/industry_impact_agent.py` |
| Commercial validation | `agents/commercial_potential.py` |
| Decisions | `agents/decision_engine.py`, `agents/configured_analysis.py` |
| Explanation | `agents/explainability_engine.py` |
| Time splits | `evaluation/time_splits.py` |
| Baselines | `evaluation/baselines.py` |
| Metrics | `evaluation/metrics.py` |
| Plots | `evaluation/plots.py` |
| Forecast lifecycle | `storage/configured_forecasts.py` |
| Environment checks | `doctor.py` |
| Tests | `tests/` |

---

## 21. Viva Questions

### Q1. Can users enter 100 keywords?

Yes. The application has no fixed maximum. It creates API-safe groups of five.

### Q2. Why are there aliases if NLP understands meaning?

Aliases help external APIs retrieve candidates. NLP validates candidates after retrieval.

### Q3. Which semantic model is used?

`sentence-transformers/all-MiniLM-L6-v2`.

### Q4. Was the Hugging Face model fine-tuned?

No. It is used as a free pretrained embedding model.

### Q5. How many forecasting features exist?

The current v4 forecaster uses 18 features.

### Q6. How is leakage prevented?

Past-only features, chronological folds, purged overlapping targets, fold-fitted preprocessing, training-fold class weights, and an untouched test interval.

### Q7. Which models are compared?

Logistic regression, random forest, SVM and XGBoost, plus persistence and Seasonal Naive.

### Q8. Why did Seasonal Naive win?

The data are short and noisy. Seasonal Naive had the strongest validation macro-F1, so the protocol correctly retained it.

### Q9. Why not deploy beauty XGBoost after its higher test result?

That would use the test set for selection and bias the research result.

### Q10. Why macro-F1?

It gives equal importance to UP, STABLE and DOWN despite STABLE imbalance.

### Q11. How is imbalance handled?

Class-weight strength is tuned inside each training fold.

### Q12. What does the Scout do?

It collects dated evidence from configured sources for only the selected keywords and reports source failures.

### Q13. Does the Authenticity Agent prove authenticity?

No. It reports provenance and returns UNVERIFIED without manipulation ground truth.

### Q14. What does TEXT_SUPPORTED mean?

Relevant semantic text exists. It does not mean verified demand or authenticity.

### Q15. When is INVEST issued?

When ready categorical and numeric forecasts both say UP, the validation cutoff is met, the target is future, and valid text evidence exists.

### Q16. Why were all live decisions WAIT?

All ready forecasts were STABLE and two keywords were unavailable.

### Q17. Is zero INVEST a failure?

No. It demonstrates conservative abstention. Historical test data still contain UP and DOWN classes.

### Q18. What is P(UP) versus rank score?

P(UP) is a class score. Rank score is a within-run percentile position.

### Q19. What happens after YouTube HTTP 429?

YouTube contributes no evidence, but the rest of the pipeline continues with available sources.

### Q20. What is the project's largest limitation?

The short retrospectively normalized Google Trends history and absence of verified sales, profit, and authenticity ground truth.

### Q21. Is TrendSense agentic AI or ML?

It is a multi-agent AI/ML decision-support system. Different agents use ML, transformer NLP, or transparent deterministic rules.

### Q22. Can it forecast a new keyword?

Yes, if enough usable history can be collected. Otherwise it returns unavailable rather than fabricating a forecast.

### Q23. Does first rank mean INVEST?

No. Ranking and decision are independent. A first-ranked trend can be STABLE and WAIT.

### Q24. What should be improved next?

Prospective daily collection, longer history, batch anchors, semantic labels, calibrated probabilities, uncertainty estimates, and repeated future verification.

---

## 22. Verbal Explanations

### Two-minute explanation

TrendSense is a multi-agent AI and machine-learning system for short-term fashion and beauty trend intelligence. A user selects an industry and any number of keywords. Google Trends history is collected in groups of five because of request constraints. The system creates 18 past-only time-series features and defines UP, STABLE or DOWN using adaptive keyword-specific bands instead of one hardcoded change threshold.

We compare logistic regression, random forest, SVM and XGBoost against persistence and Seasonal Naive with chronological validation. We do not shuffle time-series data, and the latest test period is not used for model selection. Seasonal Naive achieved the strongest validation macro-F1 in the final fashion and beauty experiments, so we retained it honestly.

After forecasting, the Scout collects dated video and news evidence. Specialized agents analyze weak signals, lifecycle, provenance, semantic relevance, industry applicability and commercial-data availability. MiniLM sentence embeddings validate whether text is relevant. The decision engine issues INVEST or AVOID only when categorical and numeric forecasts agree, validation-selected confidence passes, and text support exists. Otherwise it returns WAIT.

In the final nine-keyword beauty live case, seven keywords were forecastable, two were unavailable, and all nine received WAIT because ready forecasts were STABLE. TrendSense predicts normalized search attention, not guaranteed sales or profit.

### Thirty-second explanation

TrendSense lets users enter any fashion or beauty keywords, collects Google Trends history in five-keyword batches, compares four ML models with two baselines using leakage-safe chronological validation, and forecasts UP, STABLE or DOWN. Specialized agents and a Hugging Face sentence-transformer validate supporting text, rank the selected keywords, and issue conservative INVEST, WAIT or AVOID decisions with reasons. It separates search attention, evidence, ranking and profitability claims.

---

## 23. Glossary

| Term | Meaning |
|---|---|
| Agent | Specialized software component with a bounded task |
| Adaptive band | Keyword-specific change scale used to create labels |
| Balanced accuracy | Average recall across classes |
| Baseline | Simple model used to test whether complexity adds value |
| Chronological fold | Time-preserving train-validation split |
| IQR | Interquartile range |
| Leakage | Using information unavailable at prediction time |
| MAD | Median absolute deviation |
| MAE | Mean absolute numeric error |
| Macro-F1 | Equal-weight average F1 across classes |
| Model promotion | Replacing an incumbent after validation improvement |
| P(UP) | UP class score or empirical baseline probability |
| Rank score | Within-run rank percentile, not probability |
| RMSE | Root mean squared numeric error |
| Seasonal Naive | Baseline using aligned recent seasonal history |
| TEXT_SUPPORTED | Relevant semantic text is available |
| UNAVAILABLE | Forecast cannot be produced responsibly |
| WAIT | Explicit abstention state |

---

## Final Team Note

Before changing TrendSense, also read:

- `PRD.md` for what is being built and why
- `ARCHITECTURE.md` for how the active system works
- `RULES.md` for development and research safeguards
- `DECISIONS.md` for the reasons behind major improvements

Any new claim must match the active v4 code and a stored experiment artifact.
