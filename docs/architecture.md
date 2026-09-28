# Architecture

Data sources feed Scout. Scout writes append-only observations and passes raw evidence to Weak Signal. The pipeline then runs Lifecycle, Authenticity, Industry Impact, Commercial Potential, Decision, and Explainability. Final records are appended to the forecast store. After the horizon matures, future observations and outcomes enter evaluation.

All handoffs are lists of dictionaries keyed by keyword. The orchestrator merges Lifecycle and Authenticity outputs into the complete record. Later agents copy the whole input and add fields, preserving provenance.

The forecasting core is a supervised Random Forest trained on historical
time-series features. Hugging Face MiniLM provides semantic evidence matching.
Rules remain for missing-data handling and transparent business safeguards.
There is no autonomous planning, negotiation, reflection, online learning, or
RAG, so the system is an automated hybrid multi-agent ML workflow rather than
fully autonomous Agentic AI.

Storage uses append-only JSONL. Outcomes link to immutable forecasts using forecast_id. Temporal evaluation allows only information available at each cutoff.
