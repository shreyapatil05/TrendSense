# Historical dataset

Each Scout run appends source observations to data/history/observations.jsonl. Records include IDs, trend, category, source/platform, India geography, language, timestamp, raw evidence, normalized values, reliability, provenance, and warnings.

Forecasts append to data/forecasts/forecasts.jsonl with horizon, predicted strength, direction, lifecycle, decision, evidence snapshot, sources, and software/configuration versions. Original predictions never change. Later facts are separate outcomes.

The Historical Data Agent also creates approximately three months of genuine
daily Google Trends history for supervised ML training. It stores
google_trends_daily.csv plus version metadata. Synthetic fixtures are used only
for software tests and cannot support research claims.
