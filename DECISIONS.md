# TrendSense Architecture and Research Decisions

This file records important decisions made while improving TrendSense. It prevents future contributors or coding assistants from reversing validated choices without understanding why they exist.

## ADR-001: Replace the fixed keyword list with dynamic selection

**Status:** Accepted  
**Decision:** Accept any non-empty user-selected keyword list through command-line arguments, files, interactive input or configured presets.

**Reason:** The original fixed 55-keyword design prevented focused industry analyses and could not support 6, 9, 60 or 100 selected terms.

**Consequences:** Every downstream stage must filter by the exact selected keywords. There is no automatic fixed-list fallback.

## ADR-002: Preserve keyword order

**Status:** Accepted  
**Decision:** Deduplicate keywords without sorting them.

**Reason:** Selection order controls Google Trends request batches and therefore normalization context.

**Consequences:** Reordering the same set can create a different selection fingerprint and dataset.

## ADR-003: Limit Google Trends batches to five keywords

**Status:** Accepted  
**Decision:** Split large selections into batches of at most five.

**Reason:** The underlying Google Trends comparison interface has a five-term request constraint.

**Consequences:** Large selections require multiple requests. Batch provenance must be retained because normalization occurs per request.

## ADR-004: Fingerprint selections and experiments

**Status:** Accepted  
**Decision:** Store history under a selection fingerprint and models/results under an experiment fingerprint.

**Reason:** Fashion, beauty, keyword order, windows, thresholds and horizons must not overwrite one another.

**Consequences:** Commands must use matching options to resolve prior artifacts.

## ADR-005: Automatically prepare missing selections

**Status:** Accepted  
**Decision:** A normal `main.py` run may collect/import history and train when no compatible prepared model exists.

**Reason:** Users should be able to forecast any non-empty selection without manually discovering every prerequisite command.

**Consequences:** First runs may be slow and depend on external APIs. Preparation is visible in terminal output.

## ADR-006: Reuse the smallest compatible trained superset

**Status:** Accepted  
**Decision:** A requested subset may use the smallest compatible trained superset with the same industry, country, horizon and window settings.

**Reason:** Retraining a five-keyword subset is unnecessary when a compatible nine-keyword model and history already contain all requested terms.

**Consequences:** Inference and source collection must return only requested keywords. Scout must read the resolved superset history path.

## ADR-007: Replace fixed direction cutoffs with adaptive bands

**Status:** Accepted  
**Decision:** Compare MAD, IQR, rolling z-score and percentile bands using past-only keyword history.

**Reason:** A fixed `+3/-3` change treats sparse and high-volume keywords as if they had identical variability.

**Consequences:** Different industries may select different threshold methods. Fashion selected rolling z-score; beauty selected IQR in the recorded final experiments.

## ADR-008: Exclude zero-variability labels

**Status:** Accepted  
**Decision:** Return UNKNOWN or UNAVAILABLE when a robust band cannot be calculated.

**Reason:** A zero band cannot define a meaningful rising, stable or declining movement.

**Consequences:** Sparse terms may remain unavailable rather than receiving a fabricated prediction.

## ADR-009: Use strictly chronological validation

**Status:** Accepted  
**Decision:** Use expanding time folds without shuffling and purge overlapping forecast targets.

**Reason:** Random splitting leaks future temporal structure and does not represent deployment.

**Consequences:** Reported performance may be lower than randomly split accuracy but is more credible.

## ADR-010: Hold out the most recent test window

**Status:** Accepted  
**Decision:** Reserve the latest configured days for final testing and never use them for threshold, hyperparameter or model selection.

**Reason:** Selecting from the test set would bias the reported result.

**Consequences:** XGBoost may achieve a better held-out score while Seasonal Naive remains correctly selected from validation.

## ADR-011: Compare four machine-learning models in the final experiment

**Status:** Accepted  
**Decision:** Use logistic regression, random forest, SVM and XGBoost as the configured final machine-learning comparison.

**Reason:** These represent linear, bagged-tree, margin-based and boosted-tree model families. Four models satisfy the comparative research objective without unnecessary search multiplicity.

**Consequences:** Gradient boosting and LightGBM may remain in the registry for experimentation but must not be claimed as part of a final run unless configured and executed.

## ADR-012: Always compare against transparent baselines

**Status:** Accepted  
**Decision:** Include persistence and Seasonal Naive in model comparison.

**Reason:** Complex models must demonstrate improvement over simple temporal behavior.

**Consequences:** A baseline can become the deployed model.

## ADR-013: Select direction models using validation macro-F1

**Status:** Accepted  
**Decision:** Use validation macro-F1 as the primary direction-model and threshold metric.

**Reason:** STABLE is the majority class, so accuracy alone can hide poor UP and DOWN performance.

**Consequences:** Accuracy, balanced accuracy and per-class metrics remain required secondary measures.

## ADR-014: Tune class weighting inside each fold

**Status:** Accepted  
**Decision:** Search class-balance exponent values 0.0, 0.5 and 1.0 using training-fold class counts.

**Reason:** UP and DOWN require more influence without leaking full-dataset frequencies or duplicating temporal rows.

**Consequences:** The recorded experiments selected moderate weighting, `alpha=0.5`, for all four configured classifiers.

## ADR-015: Accept the new model only when validation improves

**Status:** Accepted  
**Decision:** Promote a challenger only when it satisfies the configured validation macro-F1 improvement rule.

**Reason:** Automatic retraining should not replace a stronger incumbent with a weaker model.

**Consequences:** Test metrics are recorded but excluded from promotion.

## ADR-016: Allow Seasonal Naive to win

**Status:** Accepted  
**Decision:** Deploy Seasonal Naive when it has the best validation macro-F1.

**Reason:** The 90-day datasets are short, noisy and sparse. Complexity is not evidence of better forecasting.

**Consequences:** The paper must state that Seasonal Naive outperformed the configured machine-learning candidates on validation.

## ADR-017: Separate direction classification from numeric forecasting

**Status:** Accepted  
**Decision:** Use one selected model for categorical direction and a separately selected regressor for future interest.

**Reason:** Direction and numeric magnitude are related but distinct tasks.

**Consequences:** Recommendation logic can require categorical and numeric agreement.

## ADR-018: Use semantic embeddings after retrieval

**Status:** Accepted  
**Decision:** Use `sentence-transformers/all-MiniLM-L6-v2` to filter and validate candidate text after source retrieval.

**Reason:** Embeddings identify conceptual relevance beyond exact strings, but they cannot retrieve documents that an API query never returned.

**Consequences:** Retrieval aliases remain a fallback. Semantic support does not prove authenticity.

## ADR-019: Keep aliases as retrieval aids, not ground truth

**Status:** Accepted with future revision  
**Decision:** Keep a small deterministic alias layer for spelling, formatting and selected editorial retrieval terms.

**Reason:** External APIs require query strings before the NLP stage runs.

**Consequences:** Conceptual aliases are manually curated and must be reported as a limitation. Future query expansion should use related queries plus NLP filtering and human approval.

## ADR-020: Treat authenticity as unverified without labeled evidence

**Status:** Accepted  
**Decision:** Report provenance, domains and duplicates, but do not output a positive authenticity score without a manipulation dataset.

**Reason:** Publisher presence and semantic relevance do not prove organic demand.

**Consequences:** The Authenticity Agent may legitimately return `UNVERIFIED` for every trend.

## ADR-021: Accept TEXT_SUPPORTED as valid decision evidence

**Status:** Accepted  
**Decision:** Recognize `TEXT_SUPPORTED`, `MEDIUM` and `HIGH` as valid text-evidence states.

**Reason:** The configured semantic pipeline produces `TEXT_SUPPORTED`, while the legacy decision engine originally expected only `MEDIUM` or `HIGH`.

**Consequences:** A valid UP or DOWN forecast is no longer blocked merely because evidence uses the new configured label.

## ADR-022: Require agreement for INVEST and AVOID

**Status:** Accepted  
**Decision:** Require classifier direction, numeric direction, validation cutoff and text evidence to agree before action.

**Reason:** A single classifier label is insufficient for a commercially worded recommendation.

**Consequences:** Many live runs may return only WAIT. This is intended conservative behavior.

## ADR-023: Remove fixed configured recommendation cutoffs

**Status:** Accepted  
**Decision:** Use validation-selected UP and DOWN cutoffs from the promoted experiment.

**Reason:** Hardcoded INVEST or AVOID thresholds reproduce the same arbitrary-weight problem as fixed direction bands.

**Consequences:** Different experiments may have different directional policy cutoffs.

## ADR-024: Keep WAIT as an abstention state

**Status:** Accepted  
**Decision:** WAIT represents stable direction, disagreement, insufficient evidence, low confidence, replay or unavailable data.

**Reason:** A trustworthy system must be allowed not to recommend action.

**Consequences:** Zero INVEST results do not imply that the pipeline failed.

## ADR-025: Make watchlist ranking keyword-specific

**Status:** Accepted  
**Decision:** When UP scores tie, rank by numeric change in adaptive-band units, semantic evidence count and total evidence count.

**Reason:** Seasonal Naive can give every keyword with the same predicted class an identical empirical probability.

**Consequences:** Keywords receive meaningful relative ordering without altering forecast probabilities.

## ADR-026: Separate probability from rank percentile

**Status:** Accepted  
**Decision:** Print actual `ml_probabilities.UP` as `P(UP)` and print `watchlist_score` as `rank_score`.

**Reason:** Earlier display code incorrectly showed rank percentiles such as 1.000 as if they were UP probabilities.

**Consequences:** Plots and terminal output must label these values separately.

## ADR-027: Keep source failures visible but isolated

**Status:** Accepted  
**Decision:** Report YouTube, RSS, NewsAPI and Google Trends health separately and continue with usable sources.

**Reason:** Rate limiting or one API failure should not erase valid evidence from other sources.

**Consequences:** Final reports must state which sources actually contributed.

## ADR-028: Store forecasts before evaluating outcomes

**Status:** Accepted  
**Decision:** Save future forecasts to JSONL, wait until target dates, record exact outcomes, then evaluate.

**Reason:** Same-day evaluation of a future prediction is invalid.

**Consequences:** Prospective evaluation requires repeated runs over time.

## ADR-029: Keep historical replay separate from prospective evidence

**Status:** Accepted  
**Decision:** Mark replay runs and prevent them from being persisted as new future forecasts.

**Reason:** Retrospective demonstrations must not contaminate the prospective forecast log.

**Consequences:** Papers must separate backtesting, live case studies and verified future outcomes.

## ADR-030: Use selection-specific generated artifacts

**Status:** Accepted  
**Decision:** Store plots, metrics and results in the current experiment directory.

**Reason:** Reused filenames previously made old plots appear to be new outputs.

**Consequences:** Teammates must inspect the printed experiment path and file timestamps.

## ADR-031: Close every Matplotlib figure

**Status:** Accepted  
**Decision:** Close figures after saving.

**Reason:** Generating per-keyword plots opened more than 20 figures and produced memory warnings.

**Consequences:** New plotting functions must close individual figures or call `plt.close('all')` safely.

## ADR-032: Use multi-agent terminology precisely

**Status:** Accepted  
**Decision:** Describe agents as bounded software components with specialized tasks and structured handoffs.

**Reason:** Not every agent is an LLM or independently autonomous.

**Consequences:** TrendSense may be described as a multi-agent AI/ML system, but documentation must state the actual method used by each agent.

## ADR-033: Report search attention, not profitability

**Status:** Accepted  
**Decision:** Limit forecast claims to normalized search-interest direction and evidence-supported watchlisting.

**Reason:** The project lacks verified sales, margin and profit ground truth.

**Consequences:** INVEST means limited trial candidate. It is not financial advice or a guaranteed commercial return.

## ADR-034: Start the paper without forcing INVEST

**Status:** Accepted  
**Decision:** Report the nine-keyword live case with zero INVEST, nine WAIT and zero AVOID decisions.

**Reason:** Changing thresholds to manufacture INVEST would invalidate the evaluation.

**Consequences:** Historical held-out metrics demonstrate UP-class capability; the live case demonstrates conservative abstention.

## ADR-035: Prioritize prospective history as the next major improvement

**Status:** Proposed  
**Decision:** Append daily snapshots and evaluate forecasts only after target dates mature.

**Reason:** Retrospectively normalized 90-day Google Trends snapshots are useful for backtesting but are weaker than independently collected prospective history.

**Consequences:** The team should collect data daily for at least six months before claiming seasonal robustness.

## Decision Change Procedure

Before reversing an accepted decision:

1. State the problem with the current decision.
2. Provide code and experiment evidence.
3. Define the replacement and migration impact.
4. Add or update tests.
5. Rerun chronological validation.
6. Update this ADR entry instead of silently deleting history.
