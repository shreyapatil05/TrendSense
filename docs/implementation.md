# TrendSense Implementation Plan

## 1. Title

TrendSense: A Hybrid AI and Machine Learning Based Multi-Agent System for Short-Horizon Indian Gen Z Fashion and Beauty Trend Forecasting

## 2. Problem Statement

Fashion and beauty brands need to notice trends before they become saturated. Current manual trend research is slow, subjective, expensive, and difficult to validate. Public platforms contain useful signals such as search interest, short-form video activity, news coverage, and search suggestions, but these signals are noisy.

The current TrendSense system collects public evidence for 55 Indian Gen Z fashion and beauty trend concepts and ranks them through predefined rules. This is useful for screening, but manually selected scoring weights are assumptions. They do not learn which historical signals actually predict future movement.

The project must answer: given evidence available today, will a fashion or beauty trend strengthen, remain stable, or weaken over the next one or three days? It must also give an evidence-aware business recommendation.

## 3. Solution

TrendSense will become a hybrid ML and AI-assisted multi-agent forecasting system.

1. Collect and store real-time and historical trend evidence.
2. Build numerical time-series features from historical Google Trends data.
3. Train a machine-learning model to predict future direction.
4. Use a pretrained Hugging Face NLP model to check whether YouTube, news, and RSS text is semantically relevant to a trend.
5. Combine learned model probability with evidence quality and transparent business safeguards.
6. Generate INVEST, WAIT, or AVOID with a traceable explanation.
7. Store every forecast and compare it with later actual outcomes.

The forecasting model will learn the relationship between historical features and future direction. Fixed manual weights will not decide the forecast.

## 4. Project Category

TrendSense is a Hybrid Machine Learning and AI-assisted Multi-Agent Trend Forecasting System.

| Component | Category |
|---|---|
| Data collection and storage | Data engineering |
| Historical feature creation | Statistical feature engineering |
| Future direction prediction | Supervised machine learning |
| Hugging Face semantic model | Pretrained NLP machine learning |
| Missing-data and business safeguards | Rule-based decision support |
| Specialised modules with structured handoffs | Multi-agent workflow |

The project must not claim fully autonomous Agentic AI. The agents are specialised automated components. They do not independently form goals, negotiate, self-reflect, or retrain without controlled evaluation.

## 5. System Architecture

    Google Trends historical and live data
    YouTube, News, RSS, Autocomplete, Wikipedia
                     |
                     v
             Data Ingestion Agent
                     |
                     v
          Historical Evidence Store
                     |
                     v
          Feature Engineering Agent
                     |
                     v
             ML Forecasting Agent
                     |
                     +-------------------------+
                     |                         |
                     v                         v
          Hugging Face Semantic Agent   Evidence Validation Agent
                     |                         |
                     +------------+------------+
                                  |
                                  v
                           Decision Agent
                                  |
                                  v
                        Explainability Agent
                                  |
                                  v
                            Forecast Store
                                  |
                                  v
                Future Observation and Evaluation

### Architecture principles

- Historical evidence is timestamped and append-only.
- ML learns prediction patterns from history instead of using manually fixed forecast weights.
- Hugging Face NLP handles text meaning and relevance.
- Rules remain only for transparent safety checks, missing data, and business constraints.
- Forecasting and business recommendations are separate tasks.

## 6. Agent Architecture

### 6.1 Data Ingestion Agent

Purpose: collect raw public evidence and preserve it.

Inputs: 55 curated trend concepts, India geography, source configuration.

Sources: Google Trends, YouTube Shorts, NewsAPI, Google News RSS, Google Autocomplete, Wikipedia pageviews.

Outputs: timestamped raw observations, source-health record, provenance, and API failure warnings.

### 6.2 Historical Dataset Agent

Purpose: build the ML training dataset from historical Google Trends daily series.

Inputs: historical daily interest values for each trend.

Outputs: one training row per trend per date, with features known at date T and a future label from T plus one or three days.

Rule: future values are never included in the features at time T.

### 6.3 Feature Engineering Agent

Purpose: transform raw time series into ML-ready feature vectors.

Features:

- Current normalized interest
- One-day change
- Three-day, seven-day, and fourteen-day moving averages
- Velocity
- Acceleration
- Rolling volatility
- Distance from recent peak
- Fashion or beauty category
- Number of active evidence sources
- Hugging Face semantic evidence agreement

Output: one feature vector per trend and date.

### 6.4 ML Forecasting Agent

Purpose: predict future direction.

Primary model: Random Forest Classifier.

Why this model:

- Learns relationships without manually fixed weights
- Captures non-linear feature interactions
- Runs locally without GPU
- Returns UP, STABLE, and DOWN probabilities
- Provides feature importance
- Is practical and explainable for a final-year project

Prediction classes:

- UP: future trend strength rises beyond tolerance
- STABLE: movement stays within tolerance
- DOWN: future trend strength falls beyond tolerance

Forecast horizons:

- One day as the main short-horizon experiment
- Three days as the secondary short-horizon experiment

Output: predicted class, UP/STABLE/DOWN probabilities, model confidence, model version, and important features.

### 6.5 Hugging Face Semantic Evidence Agent

Model: sentence-transformers/all-MiniLM-L6-v2

Purpose: determine whether unstructured text evidence is truly about a trend concept.

Inputs: trend concept, YouTube title/description, news title/description, RSS summary.

Workflow:

1. Convert trend and evidence text into embeddings.
2. Calculate cosine similarity.
3. Keep text above a fixed relevance threshold.
4. Group semantically related phrases under the same trend.
5. Calculate cross-source semantic agreement and flag conflicts.

Output: relevant evidence, rejected evidence, similarity values, agreement score, and conflict warnings.

The model does not decide INVEST, WAIT, or AVOID. It does not create facts.

### 6.6 Evidence Validation Agent

Purpose: check if the ML prediction has enough independent support.

Inputs: ML probabilities, semantic agreement, source count, data quality, and source-health records.

Outputs: HIGH, MEDIUM, or LOW evidence confidence; missing-data warnings; source-conflict warnings.

### 6.7 Lifecycle Agent

Purpose: describe the present stage: EMERGING, GROWTH, PEAK, STABLE, DECLINE, or UNKNOWN.

Inputs: historical interest features and the ML direction prediction.

Lifecycle remains an explanation layer. The ML prediction becomes the main learned future-direction output.

### 6.8 Industry Impact Agent

Purpose: estimate structural relevance to fashion or beauty categories.

Outputs: affected categories, business areas, impact explanation, and confidence.

### 6.9 Decision Agent

Purpose: convert ML forecast and validated evidence into INVEST, WAIT, or AVOID.

Inputs: ML probability, predicted direction, evidence confidence, semantic agreement, lifecycle, risk status, industry impact, and commercial evidence.

Decision policy:

- INVEST requires high UP probability and sufficient evidence.
- WAIT is used for uncertainty, sparse coverage, or conflicting evidence.
- AVOID is used for strong DOWN probability or confirmed risk.

Rules remain transparent business safeguards, not manual forecasting weights.

### 6.10 Explainability Agent

Purpose: explain the output.

Output includes predicted class and probability, important ML features, relevant text evidence, source coverage, warnings, and decision rationale.

### 6.11 Evaluation Agent

Purpose: compare mature forecasts against later outcomes.

Outputs: accuracy, macro F1, balanced accuracy, confusion matrix, MAE/RMSE where applicable, Precision at K, baseline comparison, and error examples.

## 7. Individual Model Architecture

### 7.1 Machine-Learning Forecasting Model

    Historical daily interest
              |
              v
       Feature engineering at T
              |
              v
    Training row plus future label
              |
              v
     Chronological walk-forward split
              |
              v
       Random Forest Classifier
              |
              v
    UP, STABLE, DOWN probabilities
              |
              v
        Immutable forecast record

### Training dataset format

| trend_id | date | current_interest | velocity | acceleration | ma_3 | ma_7 | volatility | source_count | semantic_agreement | future_direction |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| glass_skin | T | value | value | value | value | value | value | value | value | UP |

### Ground truth

Future change equals future interest at T plus horizon minus current interest at T.

- Change above a fixed tolerance means UP.
- Change within tolerance means STABLE.
- Change below negative tolerance means DOWN.

The tolerance must be fixed before experiments and cannot be adjusted after seeing metrics.

### Validation

Chronological walk-forward validation:

1. Train only on earlier dates.
2. Predict the next unseen period.
3. Move the date cutoff forward.
4. Repeat.

Random data splitting is prohibited because it leaks the future into the past.

### 7.2 Semantic NLP Model

    Trend concept + YouTube/News/RSS text
                    |
                    v
          MiniLM embedding model
                    |
                    v
             Cosine similarity
                    |
                    v
     Relevant evidence and agreement score
                    |
                    v
     Evidence validation and ML feature input

MiniLM is used without fine-tuning because the project has no labelled trend-text relevance dataset.

## 8. Complete Workflow

### Phase A: Historical ML preparation

1. Download approximately three months of daily Google Trends series for all 55 terms.
2. Store raw observations.
3. Create dated feature rows.
4. Create one-day and three-day future-direction labels.
5. Train Random Forest using earlier historical dates.
6. Evaluate chronologically against persistence, momentum, and moving-average baselines.
7. Save trained model, metrics, feature schema, and experiment configuration.

### Phase B: Daily automated forecasting

1. Collect live public evidence.
2. Store raw observations.
3. Build current features.
4. Run Hugging Face semantic relevance analysis.
5. Run the trained ML forecasting model.
6. Run evidence, lifecycle, impact, decision, and explanation agents.
7. Save immutable one-day and three-day forecasts.

### Phase C: Daily evaluation

1. Collect later observations.
2. Match every mature forecast with the correct future observation.
3. Build actual direction with the fixed ground-truth rule.
4. Calculate errors and classification metrics.
5. Update experiment reports.
6. Analyse failures without changing old forecasts.

## 9. Five-Day Evaluation Plan

| Day | Work |
|---|---|
| Day 1 | Fix evaluation commands; integrate historical data, ML, and semantic model |
| Day 2 | Train and evaluate historically; begin daily one-day and three-day forecasts |
| Day 3 | Record first one-day outcomes and inspect errors |
| Day 4 | Record additional one-day outcomes and first three-day outcomes |
| Day 5 | Final metrics, baseline comparison, confusion matrix, error analysis, and report |

Historical walk-forward evaluation is the main quantitative evidence. Five days of new live data is only a short demonstration of the automated loop.

## 10. Expected Outputs

1. Historical observation dataset.
2. ML-ready feature dataset.
3. Trained Random Forest model and metadata.
4. Semantic evidence output from Hugging Face MiniLM.
5. One-day and three-day forecasts with probability.
6. INVEST, WAIT, or AVOID recommendation with evidence.
7. Immutable forecast history and outcomes.
8. Baseline comparison report.
9. Confusion matrix, macro F1, balanced accuracy, MAE/RMSE, Precision at K, and error analysis.

## 11. Honest Claims

The final project can claim:

- It is a hybrid ML and AI-assisted multi-agent trend forecasting system.
- Forecast probabilities are learned from historical features rather than manually assigned forecast weights.
- Hugging Face MiniLM performs semantic evidence relevance and grouping.
- Forecasts are evaluated chronologically against baselines.
- Evidence, forecasts, outcomes, and experiment configurations are preserved for reproducibility.

The project must not claim:

- Perfect or guaranteed forecasting.
- Long-term fashion forecasting proof from five days of live data.
- Sales or ROI prediction without sales ground truth.
- Fully autonomous Agentic AI.
- Superiority to WGSN or Trendalytics.

## 12. Future Implementation Order

1. Fix the runnable evaluation flow.
2. Change prediction horizons to one and three days.
3. Build the historical Google Trends dataset.
4. Build feature engineering.
5. Train and validate the Random Forest model.
6. Add Hugging Face MiniLM semantic evidence analysis.
7. Replace fixed forecasting weights with ML probabilities.
8. Integrate output into lifecycle, validation, decision, and explanation stages.
9. Run historical evaluation and daily automated forecasts.
10. Freeze final experiments and documentation.
