# Agent inventory and data flow

These modules are deterministic agentic-workflow components, not autonomous AI agents.

## 1. Scout

Receives 55 curated terms, seed topics, India geography, and optional API keys. It queries Google Trends through pytrends, YouTube Data API, Google Autocomplete, NewsAPI or Google News RSS, and Wikipedia pageviews/top pages. It normalizes text, maps aliases, detects fashion/beauty relevance, deduplicates records, and emits source records plus a health snapshot. Rate limits create cached or missing states.

## 2. Weak Signal

Receives all Scout records and scores every keyword. Google Trends converts velocity bands to 0.10 to 1.00, adds recent interest up to 0.25, then calculates 0.75 times velocity score plus recency bonus. Wikipedia combines 0.70 times normalized view velocity and a volume bonus up to 0.30. YouTube uses keyword mentions and recent posts. News/RSS normalize mention count at five. Autocomplete normalizes matches at five.

Base score = 0.30 Trends + 0.20 Wikipedia + 0.20 YouTube + 0.15 NewsAPI + 0.10 RSS + 0.05 Autocomplete. Available weights are renormalized and a source-agreement bonus is added. Thresholds are STRONG at 0.40, MODERATE at 0.25, WEAK at 0.15, otherwise NOISE. No evidence produces INSUFFICIENT_DATA.

## 3. Lifecycle

Receives score plus Trends windows. It uses recent, previous and historical averages, velocity, acceleration, and observation count. Low baseline with positive movement is EMERGING. Velocity at least 5 with positive acceleration and rising flag is GROWTH. Interest at least 50 with flattening momentum is PEAK. Velocity below minus 5 with non-positive acceleration is DECLINE. Near-flat velocity and acceleration is STABLE. Insufficient or mixed evidence is UNKNOWN.

## 4. Authenticity

Receives source scores and Trends detail. Three sources add 0.40, two add 0.20. Moderate positive velocity adds 0.30; a spike above 20 subtracts 0.30. Credible Wikipedia/news support adds 0.20; no such support subtracts 0.10. Sustained interest adds 0.10. Output is GENUINE, LIKELY_GENUINE, SUSPICIOUS, ARTIFICIAL_HYPE, or UNKNOWN. Sparse evidence never becomes artificial hype.

## 5. Industry Impact

Receives enriched trend evidence and maps fashion or beauty to product applicability, supply-chain effect, category breadth, consumer reach, and India relevance. Weighted structural components create a 0 to 1 impact score. Source diversity affects confidence, not structural relevance. It emits affected industries, categories, business areas, direction, reasons, and warnings.

## 6. Commercial Potential

Receives impact results and optionally checks Amazon and Myntra page metadata. Marketplace evidence is only a presence proxy. Commercial potential = 0.45 marketplace proxy + 0.25 industry impact + 0.10 growth/peak + 0.10 genuine/likely genuine + 0.10 strong/moderate signal. It emits validation status, demand indicators, confidence, and a compatibility financial_validation_score field. Offline mode marks marketplace evidence unavailable.

## 7. Decision Engine

When a trained model is available, the engine uses learned UP, STABLE, and DOWN
probabilities as its forecast signal. INVEST requires UP probability of at
least 0.60, adequate independent evidence, and business relevance. DOWN with
adequate confidence can produce AVOID. Uncertainty produces WAIT. Artificial
hype and missing-data rules remain transparent safeguards. The original
weighted rule score is used only when ML is explicitly unavailable.

## 8. Explainability

Receives decision records and deterministically creates a summary, evidence coverage, reasons, and warnings. It does not use an LLM and does not alter the recommendation.

## 9. Historical Data and Feature Engineering

The Historical Data Agent collects approximately three months of daily Google
Trends data in resumable batches. The Feature Engineering Agent calculates
current interest, changes, moving averages, velocity, acceleration, volatility,
peak distance, calendar features, and category without using future values.

## 10. ML Forecasting

A Random Forest learns UP, STABLE, and DOWN from historical features for 1-day
and 3-day horizons. Expanding-window tests compare it with persistence,
momentum, and moving-average baselines. Learned class probabilities replace
manual source weights as the primary forecasting output.

## 11. Semantic Evidence

Hugging Face MiniLM embeds trend concepts and unstructured YouTube, news, RSS,
and autocomplete text. Cosine similarity keeps relevant evidence and produces
semantic source agreement. It validates meaning but does not invent forecast
values.

## 12. Evidence Validation

This agent combines ML confidence, active source coverage, and semantic
agreement to label evidence HIGH, MEDIUM, or LOW.

## Concrete trace

For glass skin, Scout collects current source evidence. Historical features
represent its recent daily trajectory. The Random Forest predicts its 1-day or
3-day direction. MiniLM retains semantically related text and Evidence
Validation checks independent support. Lifecycle and Authenticity describe
current context. Industry and Commercial agents assess business relevance.
Decision applies safeguards to learned probabilities, Explainability reports
the evidence, and the forecast is stored immutably.
