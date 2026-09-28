# Viva questions

## How do you prove forecasting?
Concise: store a prediction at T, collect future evidence at T plus 14 or 28 days, and compare them. Technical: walk-forward evaluation with frozen ground-truth rules. Evidence: immutable forecast/outcome pair and metrics. Do not claim accuracy before forecasts mature.

## What is ground truth?
A predeclared cross-source future outcome using search and mention movement with at least two confirming source types. Conflicts become UNCERTAIN. Do not redefine it after seeing results.

## How do you prevent leakage?
Every method sees only observations timestamped at or before its forecast cutoff. Never use random time-series splitting.

## Are these AI agents?
They are deterministic specialised workflow agents. They lack autonomy, planning, negotiation and learning. Do not call the current core autonomous multi-agent AI.

## Why use an LLM?
Only for semantic normalization, contradiction interpretation, and explanation. Schema checks and source evidence control hallucination. Numeric scoring remains outside the LLM.

## Do you use RAG?
Not currently. It is future work only if historical evidence retrieval has a measurable benefit.

## What are the baselines?
Persistence, momentum, and moving average evaluated on the identical time cutoffs.

## How do you compare with WGSN or Trendalytics?
Conceptually using public facts. Their proprietary algorithms cannot be reproduced. Scientific performance comparison uses open baselines.

## Main limitations?
Small curated vocabulary, platform and geographic bias, API instability, marketplace proxies rather than sales, and insufficient matured history.
