# NM-Index Empirical Validation

This is an isolated, reproducible validation framework for the NM-index. The latest [experiment design](source_documents/Pasted%20markdown%287%29.md) and [NM manuscript](source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf) are the source of truth. Earlier manuscript versions do not override them. The existing bibliometric application is never modified. PostgreSQL is accessed by guarded SELECT statements in read-only transactions; results are local CSV/PNG/Markdown files. This project never recalculates or writes the production NM-index.

**No empirical validation has been completed.** The current database is incomplete. [Phase 4.5](results/phase4_5_completion.md) found author links for only 816 of 56,768 publications and unresolved citation-source/methodology questions. The framework is for a later, fully populated and verified database. Do not run `--all` against the current pilot or treat current records as final evidence.

## Architecture

| Package | Role |
|---|---|
| `src/config.py`, `src/database.py`, `src/repository.py` | Isolated configuration, SELECT-only/repeatable-read extraction, schema verification. |
| `src/data_quality.py`, `src/eligibility.py`, `src/validation_dataset.py` | Source-quality checks, explicit cohort rules, one-row-per-author dataset. |
| `src/metric_registry.py`, `src/methodology.py`, `src/provenance.py` | Metric status, unresolved decisions and local provenance. |
| `metrics/` | Source-grounded baseline calculators and approval-required strategy interfaces. |
| `nm_index/` | Authoritative stored NM score and six stored raw/percentile components; read only. |
| `analysis/`, `experiments/` | Statistical primitives and RQ1–RQ11 orchestration. |
| `visualization/`, generated `reports/` | PNG figures and human-readable run summaries. |
| `run_validation.py`, `src/pipeline.py` | Dry-run and future execution. |

The loader uses stable author/publication IDs, not names. The currently populated string-ID tables are `author`, `publication`, `citation`, `author_contribution_weight`, `field_classification`, `author_nm_index`, and raw NM-component result tables. `author_publications` and the parallel UUID tables are empty in the present database and are not silently used. Missing required tables/columns cause explicit schema errors. A real extraction uses one read-only repeatable-read snapshot; cursors/connections close and roll back. SQL and credentials are never assembled from uncontrolled values or logged.

## Baselines and NM handling

The latest-PDF-defined conventional baselines are `raw_total_cites` (sum of stored raw paper citation counts), `h_index` (largest h with h papers having at least h citations), `g_index` (largest g among observed papers whose top-g cumulative citations reach g²), and `hf_index` (largest h with the h-th largest `c_p/N_p` at least h). Conventional hf uses **uniform coauthor shares** and runs only for declared-complete synthetic authorship; real author slots cannot yet prove complete `N_p`. These baselines are separate from NM Equation 11 total cites and modified h/g components. The manuscript's five-paper g=12 example conflicts with its written definition; see [source issue](results/g_index_source_issue.md). The calculator follows the written top-g-papers rule and the discrepancy remains open.

`c_score_raw`, `c_score_sc_adjusted`, conventional `hm_index`, `m_index`, `fi_score`, `s_index`, and `ar_index` are **METHODOLOGY_PENDING**. Each has an explicit interface and no unapproved default formula. The m-index accepts an explicitly supplied career convention. Conventional hm/hf cannot use the production modified NM values. The [methodology status](results/methodology_status.md), [Phase 5A latest-PDF reference](results/latest_pdf_metric_reference.md), and [Phase 4.5 decision log](results/methodology_decision_log.md) specify the exact missing decisions. Unavailable metrics are NULL, never invented zeros.

After a methodology decision is documented, an approved `MetricStrategy`, `CScoreStrategy`, `FiStrategy`, `ARStrategy`, or `CareerConvention` can be supplied through the programmatic `src.pipeline.run_from_extracts(..., metric_strategies={"metric_name": strategy})` seam. The run records which strategies were activated. No pending strategy is selected by the CLI or the default pipeline.

The target `nm_index` comes only from `author_nm_index.nm_index` and carries `SOURCE = STORED_PRODUCTION_RESULT`. Six `per_*` fields are stored component **percentiles**. RQ10 instead loads six separately stored **raw component scores** from their authoritative result tables; it does not recompute any NM component.

## Configuration and setup

Run from this directory on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config/config.example.env config/config.env
```

Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE` in the ignored local `config/config.env`. SSL mode must be `require`, `verify-ca`, or `verify-full`. Do not paste credentials into reports, commit them, or read the production app's `.env`. Optional settings are `VALIDATION_AS_OF_DATE` (ISO date), `MIN_PUBLICATIONS` (default 5), `MIN_RAW_CITES` (default 10), `MIN_METRIC_COVERAGE` (0–1, default 0), `RANDOM_SEED` (default 2026), and `OUTPUT_DIRECTORY` (must stay under `results/`). An as-of date alone does **not** approve the m-index career-year convention.

Dry-run checks local configuration, all source documents and selected modules, prints document SHA-256 hashes and pending methods, and **does not connect to PostgreSQL or write files**:

```powershell
.\.venv\Scripts\python.exe -B run_validation.py --dry-run
.\.venv\Scripts\python.exe -B run_validation.py --dry-run --experiment rq01
```

Only after the final database is fully populated and source/methodology decisions are recorded, execute a selected experiment or all RQs:

```powershell
.\.venv\Scripts\python.exe -B run_validation.py --experiment rq01
.\.venv\Scripts\python.exe -B run_validation.py --all
```

Experiments needing data outside the known database schema accept explicit CSVs **inside this validation project**. For example, `--experiment rq04 --input award_labels=inputs/award_labels.csv` expects `author_id,awardee`. The checked input kinds in `src/external_inputs.py` include `award_labels`, `award_events`, `reference_scores`, `annual_scores`, `historical_scores`, `future_outcomes`, `scenario_data`, `subgroup_labels`, `paper_inputs`, `coauthor_counts`, and `portfolio_verification`. Annual data needs author/year rows; RQ8 additionally requires an independent historical score snapshot with `score_year` so current scores cannot leak into a future-outcome analysis. Future outcomes need `outcome_start_year`, `outcome_end_year`, `future_citations`, `future_awards`, and `h_index_growth`; dates must equal t+1 through t+5. Aggregate `paper_inputs` are insufficient for the lecturer-approved RQ7 graph-level counterfactual. Use `--score-year`, `--first-year`, `--representative-author`, `--group-column`, `--predictors`, `--covariates`, and `--icc-model` only with their matching experiment and a prespecified methodology. The CLI never infers demographics or outcome labels.

The pipeline first verifies the schema, extracts data, writes a data-quality report, and **stops** if author–paper coverage, keys or citations fail the hard gate. A missing or invalid publication year does not stop the run: following the design's selection criterion, every author linked to such a paper is excluded as `INCOMPLETE_PUBLICATION_METADATA` (`run_metadata.json` records `publication_year_policy`). The cohort-only `--exclude-missing-year-publications` flag instead drops those papers and keeps their authors; that is not the design rule and needs lecturer approval. Production completeness flags for stored NM components, where the schema has them, are reported as the `stored_nm_components_flagged_incomplete` warning and the `nm_stored_calculation_complete` column; they do not change eligibility. It does not run the current incomplete database automatically. Data-quality statuses are `VALID`, `WARNING`, `ERROR`, and `INCOMPLETE`. Eligibility requires the configured minimum publication and raw-citation counts, non-NULL stored NM score, metric coverage threshold, and verified portfolio; an optional programmatic time-span rule is available. The design's final-cohort rules also call for an active 2000–2024 record, complete years/positions and stratified 100,000-author/334-field target; these require additional verified data and explicit activation. Each run exports author exclusion reasons by experiment. No missing citation or metric is imputed.

## Experiments and safeguards

- RQ1: pairwise Pearson correlations with finite complete pairs, Fisher 95% CI and Bonferroni values.
- RQ2: paired t statistics, mean/median difference, Cohen's d and 95% CI, using only paired authors. The sources do not fix a common score scale, so these native-unit statistics are labelled `score_scale=native_units` and RQ2 is reported as `METHODOLOGY_PENDING`, as for RQ3.
- RQ3: ICC interface; the source omits the required model/scale choice, so default output is pending. An explicit ICC(A,1) model is available only when approved.
- RQ4: award-label ROC/AUC with stratified bootstrap CI, only with verified external labels.
- RQ5: scenario/covariate regression, only with prespecified observed inputs.
- RQ6: observed annual trajectory, only with historical score snapshots.
- RQ7: with a complete `--rq07-bundle`, the three approved graph scenarios are recalculated by the independent NM calculator against the frozen original reference; without one, every row reports its missing input. The design's "Combined manipulation" row is always emitted as `METHODOLOGY_PENDING` because the order and interaction of the three manipulations are not approved. No database record changes.
- RQ8: future citations, awards and h-growth association from an historical t snapshot to t+1…t+5. This is distinct from RQ5.
- RQ9: adjacent-year Spearman/rank-change stability, only with annual snapshots.
- RQ10: complete-case z-standardized PCA of six raw stored NM component scores, with explained variance and loadings.
- RQ11: subgroup means, dispersion and effects from **approved supplied** gender/region labels. No name-based demographic inference occurs.
- Supplementary `sensitivity`: seeded 25k/50k/75k/100k sample-size checks when the cohort supports them. The independent in-memory calculator reruns the design document's career and ISC parameter grids against complete graph inputs and frozen original benchmarks. Rank-change, Gini, and binary-ISC summaries remain pending until their conventions are approved.

The analysis layer reports `OK`, `INSUFFICIENT_DATA`, `INVALID_INPUT`, `METHODOLOGY_PENDING`, or `NOT_APPLICABLE` when applicable. It checks finite values, sample size, variance, singular regressions, group emptiness and temporal order. A pending status is not a result. Do not interpret correlation as causation or claim significance without a valid computed test.

## Outputs and reproducibility

Each real run creates a timestamped `results/run_.../` directory containing `data_quality_report.csv/.md`, `validation_dataset.csv`, `metric_provenance.csv`, `descriptive_statistics.csv`, per-RQ CSVs, `run_metadata.json`, and six generated Markdown reports under `reports/`. Figures, when supported by real data, are saved at 300 DPI under `figures/run_.../` using the same run ID. A run never overwrites another run's files. `run_metadata.json` records UTC time, source hashes, package versions, random seed, author counts, coverage, experiments and pending methods. `results/methodology_status.json/.md` and `results/metric_provenance.csv` document the current implementation before any real run. The source documents are reference-only and are not edited.

Use offline tests and syntax/import checks before a future run:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B run_validation.py --dry-run
```

The current database's incomplete relationships, unresolved citation-count provenance, incomplete self-citation labels, missing historical/award/subgroup data, and pending baseline definitions prevent final empirical conclusions. See [pilot readiness](results/pilot_dataset_readiness.md) and [source plan](results/final_baseline_data_source_plan.md) for the remaining data work.

## Final test-ready synthetic workflow

The current CLI also supports an entirely offline source. The synthetic fixture uses only `TEST_` IDs; every mock CSV, report and metadata file is labelled **SYNTHETIC TEST DATA — NOT EMPIRICAL RESULTS**. The mock mode rejects external `--input` files and never calls PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -B run_validation.py --data-source mock
.\.venv\Scripts\python.exe -B run_validation.py --experiment rq01 --data-source mock
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

The existing `--data-source database` route remains SELECT-only and is reserved for the later verified cohort. Results for either route use separate timestamped `results/run_.../` and `figures/run_.../` folders. Pending baselines remain NULL. Real-run eligibility requires an independently evidenced `portfolio_verification` CSV, supplied with `--input portfolio_verification=inputs/portfolio_verification.csv`; an internally consistent snapshot is never treated as proof of a complete career portfolio. Source and approval references are required for programmatically activated pending metric strategies.

RQ10 requires `--pca-preprocessing complete_case_z_standardization` and `--pca-decision-reference ...` before computing PCA. RQ9's greater-than-10%-rank-change statistic stays pending unless an explicit `--rank-change-denominator` choice is supplied. RQ11 requires approved gender/region labels with provenance, supplied reference-population percentile columns, and all three `--fairness-*` convention options. Its effect sizes are saved as rows in `fairness_effects.csv`; unavailable comparator percentiles remain pending. RQ4–RQ7 still have unresolved source or input decisions, so a mock run exercises supported partial paths while reporting `METHODOLOGY_PENDING` for unsupported conclusions. See [source of truth](results/source_of_truth.md), [NM methodology](results/nm_methodology_reference.md), [separation rules](results/nm_baseline_separation.md), and the final test report for current status. Earlier sections describe the initial framework and should be read with these stricter test-ready gates.

## Limited-author pilot

For an advisor-approved smaller study, use the separate `--data-source pilot` route with an exact stable-ID CSV, independently verified author portfolios, and documented pilot, cohort-readiness and citation-source references. The route reads only selected linked records in a read-only snapshot and labels every output as pilot data. It does not turn the reduced sample into the planned 100,000-author study. Follow [the limited-author pilot protocol](results/limited_author_pilot_protocol.md) before connecting to the database.

## Final-pass input contracts and limits

The final-pass read-only path accepts `--input coauthor_counts=inputs/coauthor_counts.csv`. This CSV has one row per `pub_id` and columns `pub_id,coauthor_count,verified_complete,evidence_reference`. `verified_complete` is `true` only if the count is the independently verified **full** number of paper authors, beyond any database slot limit. The paper must also be in the extracted publication set. Any missing, invalid or unverified paper count makes that author's hf-index unavailable; no count is estimated from the ten author slots. This is in addition to author-level `portfolio_verification`.

RQ4 accepts `--input award_labels=inputs/award_labels.csv` with one row per author, `author_id,awardee` (`true` or `false`). For the 13-category count table, also provide `--input award_events=inputs/award_events.csv` with `author_id,award_category,evidence_reference`; it may contain multiple awards for an author but only one row per author/category pair. Category text must exactly match the 13 names in the lecturer design. Every event for an analysed author must agree with a positive binary label. No award labels or events are inferred. The combined ROC plot uses available Nm, h, g, C-score raw and Total Cites curves, with AUC values in its legend. Mean percentile comparisons, Cohen's d and p-values remain pending because their required reference and test conventions are not specified.

Eligibility now records separate reasons for missing 2000–2024 activity and incomplete publication year/author-position metadata, alongside publication/citation and portfolio checks. RQ5 tables preserve all lecturer-listed categories even when no observed authors occupy a row; the source's omitted `10<t<=15` career interval is reported in `rq05_unclassified.csv` and never assigned an invented band. RQ1 exports normal QQ plots for available metrics, plus the newly approved residual and Bland–Altman diagnostics when the frozen reference is supplied. Existing raw-unit paired mean-difference plots remain descriptive only. Run reports classify each experiment as implemented result, unavailable input, methodology pending or not executed. See [final implementation pass](results/final_implementation_pass.md) for the earlier status and the newer [methodology report](results/final_methodology_implementation_report.md) for current readiness.

## Lecturer-approved RQ1 and RQ7 decisions (latest pass)

The lecturer has now approved RQ1 OLS residuals and percentile Bland–Altman calculations. For a real RQ1 run, supply `--input reference_scores=inputs/reference_scores.csv` from the original complete 100,000-author reference. It must have `author_id,nm_index,c_score_raw,middle_author_share,career_stage,reference_version,evidence_reference` and additional score columns for each baseline to be compared. Every selected author must occur in that original reference; missing values are reported, never filled. The run exports `rq01_residual_coefficients.csv`, `rq01_residuals.csv`, `rq01_bland_altman_summary.csv`, `rq01_bland_altman_pairs.csv`, career-coloured residual figures, percentile Bland–Altman plots and difference histograms. The old raw-unit paired-difference plots are separate descriptive graphics. See [lecturer-approved methodology](results/lecturer_approved_methodology.md) for the precise equations and tie convention.

The lecturer also approved a **frozen original 100,000-author benchmark** for RQ7. In-memory graph transformations and a benchmark-freezing contract are implemented and tested, but the full independent NM recalculation engine and complete citing-paper/author/field/reference data are still missing. Aggregate `paper_inputs` do not qualify as a complete counterfactual: `rq07` now reports explicit missing-data statuses and blank NM inflation rather than treating scalar citation arithmetic as an NM result. The project-local `995_authors.csv` preserves the intended approximately 1,000 selected IDs, but supplies only IDs and names; verified field/career strata and full portfolios must be provided separately. The [implementation report](results/final_methodology_implementation_report.md) records readiness and remaining work. Earlier README sections describe previous framework stages; this section supersedes their RQ1/RQ7 pending descriptions.

## Latest offline counterfactual implementation and handover

The earlier RQ7 paragraph above records an older stage. The current
`nm_index/counterfactual_calculator.py` independently recomputes contribution,
influential self-citation adjustment, career factor, field/year normalization,
capping, six raw components, manuscript component transformations and NM from
complete in-memory citation graphs and an immutable original reference.
`analysis/rq07_engine.py` applies the lecturer's three graph scenarios and
recomputes source-supported conventional baselines. It reports unavailable
inputs instead of changing a stored NM score. The bundled mock workflow now
tests all three scenarios on `TEST_` authors only.

For a later real 995-author run, use the new `--data-source cohort` path and a
complete `--rq07-bundle` export from the member's populated database. The
bundle must include full ordered authorship, complete citation edges, explicit
scenario assignments and the original 100,000-author reference. The
[final handover guide](results/FINAL_HANDOVER_GUIDE.md) gives the exact file
contract, commands, readiness checks and output locations. Local database
coverage is not a code-completion criterion; no real 995-author experiment
was run in this offline implementation pass.
