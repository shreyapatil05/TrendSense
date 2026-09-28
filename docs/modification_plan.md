# File-level modification plan

| Classification | Files | Reason |
|---|---|---|
| KEEP | scoring logic inside all eight agent modules | preserve current scientific meaning |
| MODIFY | config.py | versions, horizons, storage paths, optional dotenv |
| REFACTOR | main.py | valid imports, consistent Scout contract, persistence, CLI |
| MODIFY | commercial_potential.py | reproducible offline mode and optional requests |
| MODIFY | decision_engine.py | remove incorrectly indented final-item display |
| CREATE | contracts.py, storage modules | typed immutable observation/forecast records |
| CREATE | evaluation modules | ground truth, metrics, baselines, backtest |
| CREATE | tests | agent, persistence, metrics, and 55-trend integration checks |
| CREATE | README and docs | architecture, agents, validation, comparison, claims |
| DELETE | none | original logic remains available |
