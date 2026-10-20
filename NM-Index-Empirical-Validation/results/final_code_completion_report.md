# Final code completion and handover report

**Status: READY_FOR_HANDOVER for the isolated validation code; the real 995-author experiment has not run.** This means the source-supported implementations and synthetic execution are ready to give to the member with the populated database. It does not mean all research inputs or unresolved methodology decisions have been supplied. No claim of empirical findings is made here.

## Implemented experimental paths

| Experiment | Code and latest synthetic outcome | Real-run dependency or limit |
|---|---|---|
| RQ1 | OLS of NM percentile on C-score percentile; fitted/residual tables, career-stage residual plots, percentile Bland–Altman plots and histograms. Synthetic status `OK`. | Verified complete original 100,000-author reference and validated C-score values. |
| RQ2 | Correlation and paired-rank comparison with available baselines; `OK`. | Complete author portfolios and supported baseline values. |
| RQ3 | Reliability/ICC path; `METHODOLOGY_PENDING`. | Approved ICC model and valid repeated measures. |
| RQ4 | Top-5% counts, ROC/AUC, 13-category table and combined ROC; explicit optional Welch/pooled-d inference. Synthetic status `OK` with TEST-only labels and decision reference. | Complete award labels/events, original reference scores, and an approved real-data inferential convention. |
| RQ5 | Supplied scenario/order/domain/career tables and regression gates; `METHODOLOGY_PENDING`. | Observed labels, prespecified predictors/covariates and approved interpretation. No synthetic categories are passed as real observations. |
| RQ6 | Historical score trajectories; `OK_WITH_EXPLICIT_CONVENTION` on synthetic data. | Historical scores and approved normalization/representative-author choices. |
| RQ7 | Three fully recomputed in-memory graph counterfactuals (+50% self-citation edges, salami splitting, +30% gift authorship), original frozen benchmarks, NM components and percentiles, supported baseline recalculation and inflation; `OK`, 36/36 synthetic author-scenario rows. | Complete per-author citation/authorship graph and original 100,000-author benchmark bundle. Unsupported baselines remain explicitly unavailable. |
| RQ8 | Historical-to-future outcome validation; `OK` on synthetic data. | Independently dated historical scores and future outcomes. |
| RQ9 | Adjacent-year ranks, changes, Spearman and >10% change; `METHODOLOGY_PENDING` in fixture. | Longitudinal data and approved rank-change denominator/coverage. |
| RQ10 | PCA of T, S, U, modified Hf/Hm/G with loadings/explained variance; `OK` with TEST-only preprocessing choice. | Approved preprocessing and decision reference. |
| RQ11 | Demographic/geographic fairness routines; `METHODOLOGY_PENDING` in fixture. | Approved subgroup labels, complete comparator percentiles, and effect/variance conventions. |
| Sensitivity | Seeded sample-size checks plus full NM recalculation for the design's four career pairs and four ISC epsilon values; 96/96 TEST-only parameter rows `OK`. Overall `SCORES_READY_SUMMARIES_PENDING`. | Real graph/reference inputs. The source does not define rank-delta tie/direction rules, Gini target, or binary-ISC comparison convention; their summaries are withheld. |

## Metric layer

The supported conventional baselines are **raw Total Cites, h-index, hf-index and g-index**. They use complete publication/citation/coauthor evidence; the conventional hf implementation requires verified full coauthor counts. **C-score raw, self-citation-adjusted C-score, hm-index, m-index, Fi-score, s-index and AR-index** remain `METHODOLOGY_PENDING`: the authoritative documents do not provide enough unambiguous calculation detail to implement them faithfully. Their cells are missing with reasons, never substituted from similarly named NM components. The existing stored NM score and its six stored component sources are read through the read-only adapter for ordinary comparison; RQ7 and parameter sensitivity independently recalculate NM in memory from full canonical graphs, without calling production calculators.

## Data contract and handover

The fixed `995_authors.csv` is validated for 995 distinct stable IDs and is unchanged. The selected-author adapter is separated from canonical data construction, metric calculation, experiment modules and reports. Real cohort execution requires independently verified portfolios and citation source, all 995 author records, publications, complete authorship order/contribution, citation relationships, the original 100,000-author reference tables, plus experiment-specific external inputs. The exact bundle schema, configuration, dry-run, test and real-run commands, output checks, failure tracing and reproduction fields are in `FINAL_HANDOVER_GUIDE.md`. Database access is designed for SELECT-only, read-only transactions; the current database was not accessed during this completion pass.

## Offline verification

- 75 offline tests passed; syntax parsed for 96 Python files and key modules imported.
- Dry-run returned `DRY_RUN_OK` and reported `database_access=false`, `database_writes=false`.
- Complete synthetic run: `results/run_20261020T152802457653Z/`, 12/12 TEST authors eligible, all 36 RQ7 counterfactual rows and all 96 parameter-grid rows `OK`.
- Output manifest: 99 entries, 44 PNG figures, zero missing/size/hash mismatches; all outputs are labelled **SYNTHETIC TEST DATA — NOT EMPIRICAL RESULTS**.
- Fixed cohort SHA-256 remains `c704eeaa45602c445160d27ba07f07c9c123cf1145b9d8edc6b5855d80b651e9`.
- `git status --short` in the production repository showed only `?? NM-Index-Empirical-Validation/`; no tracked production file was edited. No database connection, SQL, migration, calculation runner, commit or push was performed in this pass.

The next member should populate the separate database configuration and verified input bundle, check the 995-author readiness evidence, run the documented commands, and review every RQ status and exclusion report. Pending research decisions remain explicit until approved; the synthetic run is a software check, not the real experiment.
