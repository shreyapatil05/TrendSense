# Agent data contracts

Every stage supplies input, processing result, output, confidence or evidence status, warnings, timestamp, and provenance.

| Stage | Required input | Added output | Failure behaviour |
|---|---|---|---|
| Scout | keywords, source config, keys | raw records and health | partial data plus warnings |
| Weak Signal | raw records | source scores, final score, strength | INSUFFICIENT_DATA, not fake zero |
| Lifecycle | Trends windows | phase, velocity, acceleration | UNKNOWN |
| Authenticity | source scores and detail | level, score, reasons | UNKNOWN under two sources |
| Industry Impact | enriched record | industries, components, impact | low-confidence estimate |
| Commercial | impact and marketplace evidence | proxy score and status | unavailable, no fabricated sales |
| Decision | component scores | index, recommendation, confidence | WAIT on insufficient evidence |
| Explainability | decision record | reasons and warnings | exposes missing evidence |

contracts.py defines typed ObservationRecord and ForecastRecord structures. Agent dictionaries stay backward compatible.
