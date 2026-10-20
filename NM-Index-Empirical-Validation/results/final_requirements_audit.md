# Final requirements-versus-code audit

## 1. Executive summary

**Final decision: CODE_ISSUES_REMAIN.** The framework can load stored NM scores, calculate three conventional raw baselines, execute several statistical analyses, and produce a labelled synthetic run. It **cannot yet execute every experiment and output required by the lecturer's design** on a fully populated database. Seven baseline definitions remain unresolved in the supplied documents; additional RQ1, RQ4, RQ5, RQ7, parameter-sensitivity, and figure/report functions are incomplete. The supplied 995-author cohort is now directly accepted, but it is a reduced-cohort **pilot** against the design's 100,000-profile study. A populated database alone will not fill the missing code or make 995 authors satisfy RQ8's 10,000-author and robustness checks' 25,000–100,000-author sample targets.

The authoritative sources are the complete [`Pasted markdown(7).md`](../source_documents/Pasted%20markdown%287%29.md) lecturer design and the latest [`Nm Index novel model (1)(3).pdf`](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf) where the NM model is relevant. No older document was used to override these. The complete 48-row checklist is in [`final_requirements_vs_code.csv`](final_requirements_vs_code.csv), with a readable [`Markdown matrix`](final_requirements_vs_code.md). Status counts: **7 READY, 18 PARTIAL, 7 MISSING_CODE, 7 INPUT_DATA_REQUIRED, 9 METHODOLOGY_UNSPECIFIED**. A status of `INPUT_DATA_REQUIRED` means a callable method exists, not that the whole associated RQ is complete.

## 2. Study cohort handling

`995_authors.csv` has 995 rows, 995 distinct stable IDs, and `author_id,author_name` columns. `src.external_inputs.load_pilot_author_ids` now accepts this exact file and returns the IDs in the supplied order. `run_validation.py --data-source pilot --pilot-author-ids 995_authors.csv` passes the exact IDs to `src.pipeline.run_pilot`, which enforces prespecified evidence before any connection and calls `src.repository.load_selected_author_ids` with parameterized SELECTs. No random sample or substitute ID selection occurs. The pilot loader accepts up to 6,000 IDs, so 995 fits. Names are retained in the CSV but are not used to select database authors. No real pilot was run.

The normal `--data-source database` route instead reads all authors and rejects fewer than 100,000. That is consistent with the lecturer's **full** design but cannot serve the 995-author reduced study. The pilot route is explicitly labelled `PILOT DATA — NOT FULL EMPIRICAL VALIDATION`. The lecturer's full study also requires 334 fields and stratification by field, career stage and region; the validation code does not construct or enforce that sample. Five-publication and ten-citation filters are present. The active-2000–2024 and complete position/metadata criteria are not all default gates. Independent portfolio verification is required before a real pilot connection.

## 3. NM-index handling

`src.repository.QUERIES['nm']` reads `author_nm_index.nm_index`, `metrics_available`, and six `per_*` percentile columns. `nm_index.loader.load` retains the **stored production result**; it does not recalculate Eq. 1–27. RQ10 additionally reads six separately stored raw component scores (`nm_raw_t`, `nm_raw_s`, `nm_raw_u`, `nm_raw_hf`, `nm_raw_hm`, `nm_raw_g`) through the repository. Experiment eligibility now excludes rows lacking any of six stored percentiles. The latest PDF's complete mathematical implementation has **not** been independently verified here; see [`final_nm_methodology_audit.md`](final_nm_methodology_audit.md). For an empirical comparison of the implemented production NM score, this read-only architecture is a valid consumption path once that score and its provenance are independently verified. It is not a local NM calculator.

## 4. Eleven-baseline audit

All 11 baseline columns are declared by `src.metric_registry` and placed in the one-row-per-author `validation_dataset.csv`; `src.pipeline` passes only non-null comparators to RQ analyses. Thus a declared column alone does **not** make a baseline available to RQ1–RQ3 or other RQs. No missing baseline is zero-filled.

| Baseline | Calculator / inputs | Author value and downstream availability | Status and test/limitation |
|---|---|---|---|
| Total cites | `metrics.total_cites.calculate`; complete author-paper links and `publication.total_citation` | Produces author value; reaches RQ1/2/3 and other selected RQs | READY; synthetic tests; source-count provenance must be verified |
| C-score raw | `metrics.c_score.calculate_raw` strategy interface; six indicators/positions/reference distributions | Default null; omitted by comparator selection | METHODOLOGY_UNSPECIFIED; pending-strategy test; no complete formula in sources |
| C-score SC adjusted | `metrics.c_score.calculate_self_citation_adjusted` strategy interface; self-citation adjustment rule | Default null; omitted | METHODOLOGY_UNSPECIFIED; pending-strategy test; NM ISC is not this rule |
| h-index | `metrics.h_index.calculate`; complete paper citation counts | Produces author value; reaches RQ1/2/3 and other selected RQs | READY; independent synthetic expected-value test |
| hm-index | `metrics.hm_index.calculate` strategy interface; full coauthors and rank rule | Default null; omitted | METHODOLOGY_UNSPECIFIED; pending-strategy test; conventional definition unresolved |
| hf-index | `metrics.hf_index.calculate`; fractional `c_p/N_p` and verified full coauthor count | Synthetic author values; **real pipeline leaves null** because ten slots do not prove full `N_p` | PARTIAL; latest-PDF synthetic test; no verified real input path |
| g-index | `metrics.g_index.calculate`; complete ordered paper citation counts | Produces author value; reaches RQ1/2/3 and selected RQs | READY; synthetic tests; PDF worked example conflicts with written top-g-papers rule |
| m-index | `metrics.m_index.calculate` with explicit career convention; h and career start | Default null; omitted | METHODOLOGY_UNSPECIFIED; strategy test; duration convention not given |
| Fi-score | `metrics.fi_score.calculate` strategy interface; self-citation threshold | Default null; omitted | METHODOLOGY_UNSPECIFIED; strategy test; threshold/equation absent |
| s-index | `metrics.s_index.calculate` strategy interface; self-citation definition | Default null; omitted | METHODOLOGY_UNSPECIFIED; strategy test; label and cited b-index source ambiguous |
| AR-index | `metrics.ar_index.calculate` strategy interface; citation age convention | Default null; omitted | METHODOLOGY_UNSPECIFIED; strategy test; age-weighting equation absent |

RQ1 and RQ2 compare against the **available** baseline list, not all 11. RQ3 does the same only if an ICC model is explicitly chosen. RQ4 uses those available comparators; RQ5 summaries and RQ6/RQ8/RQ9 likewise cannot produce the design's full baseline tables until the missing metrics exist. RQ11 asks for `m_index` and `c_score_raw` percentiles; these are unavailable by default.

## 5. RQ1 — associative power

`experiments.rq01_correlation.run` writes `correlation_matrix.csv` and `correlation_stats.csv`. `analysis.correlation.correlate` calculates Pearson r, exact p-values, Fisher 95% CIs, paired n and Bonferroni-adjusted p-values for available metrics. The matrix is not 12×12 while seven baseline columns are null. `visualization.correlations` creates scatter, paired-difference and heatmap PNGs but **not** the specified QQ, residual, or Bland–Altman diagnostics. **PARTIAL**; missing diagnostic figure code is a concrete gap.

## 6. RQ2 — paired differences

`experiments.rq02_paired_comparison.run` and `analysis.paired_tests.compare` implement paired t, mean/median difference, SD, Cohen's d, 95% CI, exact p and Bonferroni values in `paired_difference_stats.csv`. Synthetic tests exercise it. It cannot cover all 11 baselines while seven remain null. **PARTIAL** overall; core statistical code is ready for available comparators.

## 7. RQ3 — interchangeability

`experiments.rq03_agreement.run` writes `icc_analysis.csv`. `analysis.agreement.icc` has an ICC(A,1) two-way random absolute-agreement implementation and bootstrap CI, but the lecturer document says only “ICC” and does not choose a model or scale. Default output is `METHODOLOGY_PENDING`; the CLI exposes an explicit `--icc-model`. It compares only available baselines. **METHODOLOGY_UNSPECIFIED**, with comparator availability also incomplete.

## 8. RQ4 — award-recipient discrimination

Externally supplied binary `award_labels` can support top-5% selection, ROC/AUC and bootstrap CI in `award_analysis.csv`; ROC PNGs are produced **one metric at a time**. The code does not verify all 13 listed award categories, does not populate awardee/non-awardee mean percentiles, Cohen's d, or p-value, and does not create the specified combined ROC plot with AUC legend. Those table fields are written as NaN with `METHODOLOGY_PENDING`. Thus the core classifier is **INPUT_DATA_REQUIRED**, while the full lecturer experiment is **PARTIAL** and requires additional code and decisions. Missing award labels are not a code failure.

## 9. RQ5 — four unique-power studies

`experiments.rq05_unique_power.run` can join supplied `scenario_data`, produce the four named CSVs, group summaries, and optional `unique_power_regression.csv`. The four studies are **PARTIAL**:

- **A. ISC:** filters `t<15`, groups observed `isc_scenario`, and can fit a prespecified regression. The six exact scenario categories and approved predictors/covariates are not enforced.
- **B. Contribution/order:** filters `15<t<30` and groups ordering labels, but does not enforce the design's six rows or all baseline metrics.
- **C. Domain:** filters late-career/high-contribution authors and bins main-domain percentage; current interval endpoints do not exactly reproduce every inequality in Table 7.
- **D. Career:** filters low-ISC/high-contribution Computer networks and communication profiles, but uses four broad career bands rather than the design's detailed Table 8 bins.

No RQ5-specific figures are generated. The input CSV must provide observed scenario, career, domain, contribution, ISC, and field labels; the validation code does not infer them from the current extract. Missing labels are an **input requirement**, while row/boundary and figure fidelity are **code gaps**.

## 10. RQ6 — score evolution

`experiments.rq06_temporal_evolution.run` requires historical `annual_scores`, a representative author, and an explicit normalization decision to create `score_evolution.csv`, `score_evolution_normalized.csv`, and `score_evolution.png`. The mock run reached `OK_WITH_EXPLICIT_CONVENTION`. The real historical series and chosen author are **INPUT_DATA_REQUIRED**; the lecturer does not specify a unique normalized-scale convention, so this decision must be documented. Current 995-author database records alone do not reconstruct historical NM snapshots.

## 11. RQ7 — gaming resistance

`analysis.gaming.simulate` transforms local paper inputs for +50% self-citation, doubled papers/halved citations, and +30% coauthors without database writes. `gaming_resistance.csv` records raw changes. With an explicitly chosen fractional-count policy, h and g can be compared in `gaming_index_inflation.csv`. Counterfactual **NM, C-score, hm and hf values and their percentage inflation are not computed**, so the Table 9 comparison cannot be completed even with a populated database. There is no RQ7 figure. **MISSING_CODE** for the core NM comparison; methodology and complete paper inputs also remain required.

## 12. RQ8 — predictive validity

`experiments.rq08_predictive_validity.run` checks a dated historical `t` snapshot against citations, awards and h-growth over `t+1` through `t+5`, then writes `predictive_validity.csv` via `analysis.predictive.future_association`. It requires independent historical/future datasets; current scores cannot serve as historical snapshots. The code enforces the lecturer's **10,000 complete longitudinal authors for a real database run**. Therefore the exact 995-author cohort cannot fulfill this full-study RQ without an approved reduced-sample study change. **INPUT_DATA_REQUIRED** for the implemented method, plus a cohort-scope conflict.

## 13. RQ9 — temporal stability

`experiments.rq09_temporal_stability.run` and `analysis.temporal.rank_stability` support adjacent-year Spearman, mean absolute rank change and a >10% rank-change statistic in `temporal_stability.csv`. Annual score snapshots are **INPUT_DATA_REQUIRED**. The lecturer does not define the denominator for “10% rank change”; code leaves that result pending unless `--rank-change-denominator paired_cohort_size` is explicitly approved. No temporal-correlation-matrix figure is generated. **METHODOLOGY_UNSPECIFIED** for that percentage; other statistics have code.

## 14. RQ10 — construct validity

The repository loads six **raw** stored NM component scores, rather than six `per_*` percentiles. `experiments.rq10_pca.run` performs complete-case PCA through `analysis.pca.analyze` when `--pca-preprocessing complete_case_z_standardization` and a decision reference are supplied. It writes `pca_loadings.csv`, `pca_status.csv`, and scree/loading PNGs. **INPUT_DATA_REQUIRED** for complete component records and an approved preprocessing choice; the implemented path passes synthetic tests.

## 15. RQ11 — fairness

`experiments.rq11_fairness.run` and `analysis.fairness.compare_percentiles` support supplied gender/region labels, subgroup mean percentiles, Cohen's d and regional variance in `fairness_analysis.csv` and `fairness_effects.csv`. They require approved external labels, comparator reference percentiles, and explicit effect/variance conventions. The lecturer expressly proposes name-based gender inference; this code deliberately **does not implement** that data-collection method and instead requires supplied labels with provenance. This is a documented deviation, not merely missing database input. Under the lecturer's exact method, name-inference code is **MISSING_CODE**; the analysis from approved labels is **INPUT_DATA_REQUIRED**. No inference was attempted here.

## 16. Sensitivity and sample-size robustness

`experiments.sensitivity.run` and `analysis.robustness.sample_size` can resample available NM–h/C relationships at 25k, 50k, 75k, and 100k when a full cohort and metrics exist. The 995-author cohort cannot supply these sizes. The specified career `C,λ` and ISC `ε₀` parameter grids, rank changes, Gini changes, mean ISC and binary-correlation effects **cannot be computed** because the project cannot rerun NM/ISC under alternate parameters. `sensitivity_results.csv` currently contains sample-size checks or a status; `parameter_sensitivity_status.csv` explicitly marks the absent method. **MISSING_CODE** for parameter sensitivity; sample-size robustness is **PARTIAL** and data-dependent.

## 17. Required-output audit

All listed names are wired through `src.pipeline.run_from_extracts`: it writes each returned experiment table to `results/run_<UTC timestamp>/<name>.csv`. A missing input or pending method may return only an `rq##_status.csv` rather than the expected analytical CSV. The mock run created all names below, which verifies file wiring **only**; several contents were status-bearing or based on 12 synthetic authors.

| Output name | Required by design | Code exists / generation function | Output path | Status | Reason |
|---|---|---|---|---|---|
| `correlation_matrix.csv` | Yes | Yes; `rq01.run` | `results/run_*/` | PARTIAL | No full 12×12 until all baselines exist |
| `paired_difference_stats.csv` | Yes | Yes; `rq02.run` | `results/run_*/` | PARTIAL | Core stats work; missing comparator values |
| `icc_analysis.csv` | Yes | Yes; `rq03.run` | `results/run_*/` | METHODOLOGY_UNSPECIFIED | ICC model/scale decision required |
| `award_analysis.csv` | Yes | Yes; `rq04.run` | `results/run_*/` | PARTIAL | Means/effects/p and categories absent |
| `self_citation_analysis.csv` | Yes | Yes; `rq05.run` | `results/run_*/` | PARTIAL | Input labels and exact scenario fidelity needed |
| `author_ordering_analysis.csv` | Yes | Yes; `rq05.run` | `results/run_*/` | PARTIAL | Exact category rows not enforced |
| `domain_sensitivity.csv` | Yes | Yes; `rq05.run` | `results/run_*/` | PARTIAL | Boundary fidelity and real labels needed |
| `career_stage_analysis.csv` | Yes | Yes; `rq05.run` | `results/run_*/` | PARTIAL | Design Table 8 detailed bands absent |
| `score_evolution.csv` | Yes | Yes; `rq06.run` | `results/run_*/` | INPUT_DATA_REQUIRED | Annual snapshots and selected author needed |
| `gaming_resistance.csv` | Yes | Yes; `rq07.run` | `results/run_*/` | MISSING_CODE | Raw transformations exist but NM inflation missing |
| `predictive_validity.csv` | Yes | Yes; `rq08.run` | `results/run_*/` | INPUT_DATA_REQUIRED | Historical/future series and 10k cohort needed |
| `temporal_stability.csv` | Yes | Yes; `rq09.run` | `results/run_*/` | METHODOLOGY_UNSPECIFIED | >10% denominator decision; annual inputs needed |
| `pca_loadings.csv` | Yes | Yes; `rq10.run` | `results/run_*/` | INPUT_DATA_REQUIRED | Six raw components and preprocessing choice needed |
| `fairness_analysis.csv` | Yes | Yes; `rq11.run` | `results/run_*/` | INPUT_DATA_REQUIRED | Approved labels/reference percentiles; exact inference absent |
| `sensitivity_results.csv` | Yes | Yes; `sensitivity.run` | `results/run_*/` | MISSING_CODE | Parameter-grid results are not implemented |

## 18. Figure generation

`src.pipeline._write_figures` can create histogram, NM scatter, paired-difference, ranking, correlation heatmap, separate ROC curves, score-evolution, PCA scree/loadings, fairness subgroup and sample-size robustness PNGs. The 12-author mock run produced **28 PNGs**. `visualization.core.save` uses 300 DPI. **FIGURE CODE MISSING** for the RQ1 QQ/residual/Bland–Altman diagnostics, combined award ROC/AUC legend, RQ5-specific scenario figures, RQ7 inflation plots, and the manuscript's temporal-correlation matrix. The lecturer specifies PNG or PDF, 6×4 or 10×6 inches, a colorblind-safe palette and serif font; current output is PNG-only, figure sizes vary, `coolwarm` is used for the heatmap, and serif fonts are not set globally. Existing figures do not establish full figure-spec compliance.

## 19. Human-readable reports and reproducibility

`src.pipeline._write_reports` creates six local run reports: `executive_summary.md`, `methodology.md`, `data_quality.md`, `metric_results.md`, `statistical_results.md`, and `limitations.md`. These are status and coverage summaries, **not** a complete RQ-by-RQ paper Results/Discussion/Conclusion in the lecturer's expected structure. `run_metadata.json` records UTC run time, document/code SHA-256 hashes, Python version, seed, author count, metric coverage, experiment statuses and eligibility. Run directories are timestamped and classified synthetic/pilot/real. Exact p/CI/n/Bonferroni reporting is present for some core tests but cannot be claimed for all RQs while their methods are pending. Public data/code availability is a future handoff requirement, not established by these local files.

## 20. Offline tests and syntax

After the cohort-parser fix, **47/47 existing offline tests passed** using `python -B -m unittest discover -s tests -v`. Tests include DB safety mocks, cohort routing, core baselines, statistical primitives, mock pipeline, figures and reports. The amended test verifies that a two-column cohort file passes its exact ID sequence to the pilot route. Python AST syntax parsing of **85 `.py` files** passed. No real DB connection was opened by these checks.

## 21. Synthetic end-to-end result

`python -B run_validation.py --dry-run` returned `DRY_RUN_OK` with `database_access=false`. `python -B run_validation.py --data-source mock` then completed entirely offline in [`results/run_20261017T140831848898Z`](run_20261017T140831848898Z/): **12 synthetic authors, 12 eligible, 38 CSVs, 28 PNGs, six Markdown reports**. Outputs are labelled `SYNTHETIC TEST DATA — NOT EMPIRICAL RESULTS`. The run's statuses were RQ2, RQ8 and RQ10 `OK`; RQ6 `OK_WITH_EXPLICIT_CONVENTION`; RQ1/3/4/5/7/9/11 `METHODOLOGY_PENDING`; sensitivity `INSUFFICIENT_DATA`. Therefore “mock run completed” must not be read as “every lecturer experiment was completed.”

## 22. Issues found

The principal **coding tasks** are: (1) provide real-data conventional hf input wiring once full `N_p` is independently verified; (2) implement RQ1 QQ/residual/Bland–Altman diagnostics and required figure-spec compliance; (3) complete RQ4 thirteen-category award table and combined ROC display; (4) make RQ5's four tables and boundaries faithful to the specified categories and add supported figures; (5) implement defensible RQ7 NM/baseline counterfactuals and parameter-sensitivity reruns after methodology approval; (6) complete the specified RQ-by-RQ report/figure outputs; and (7) decide whether to implement the lecturer's name-based gender collection method or obtain an approved replacement. Additional code may be needed to enforce the 2000–2024 activity and complete position/metadata criteria and full-sample stratification. These are not fixed by a new database alone.

Separately, the supplied source documents do not fully specify C-score raw/SC-adjusted, conventional hm, Fi, s, AR, ICC model/scale, RQ9 denominator, and some simulation/normalization rules. They require **documented lecturer/advisor decisions**, not invented formulas. The latest NM methodology audit also prevents claiming independent formula verification. The 995-versus-100,000 scope and RQ8/robustness sample-size incompatibility require an approved reduced-study interpretation.

## 23. Fixes made

One small, objectively confirmed cohort-ingestion issue was fixed inside this validation project: `src.external_inputs.load_pilot_author_ids` now accepts either a one-column ID CSV or the supplied `author_id,author_name` CSV. It still validates unique nonblank stable IDs and a maximum of 6,000 and uses IDs alone for selection. The exact 995-row file loaded offline. `tests/test_mock_pipeline.py` and `results/limited_author_pilot_protocol.md` were updated accordingly. No metric equation, statistical method, RQ definition, production file, database query, credential, or database record was changed.

## 24. External and populated-data requirements

The other group member must supply or verify: a database containing the **same 995 stable IDs** and complete author-paper links; independent portfolio/coauthor completeness evidence for every selected ID; trustworthy citation-source semantics; source/benchmark provenance for stored NM and six raw components; award labels with all required categories and non-awardees; observed RQ5 scenario/order/domain/career variables; annual and historical NM/baseline snapshots; future `t+1…t+5` citations/awards/h-growth; approved gender/region labels and reference-population percentiles; and full local paper-level inputs for gaming. The current selected 995 IDs were found only 8 times in the previously connected database, but this audit **did not use that incomplete database to judge code completeness**. The correct database is expected later. The 995 cohort cannot produce the design's 10k/25k/100k sample-specific outputs without a scope decision or additional authors.

## 25. Final readiness decision

**CODE_ISSUES_REMAIN.** A handoff for a limited, explicitly labelled pilot of currently supported RQs is possible after data/evidence checks, but a handoff advertised as “all lecturer experiments ready for the real 995-author study” would be inaccurate. The populated database alone does not resolve the missing code, source-definition decisions, or sample-size mismatch. Do not run `--all` and interpret status-only files as completed analyses.

## 26. Exact instructions for the group member

1. **Do not run the real study yet.** First obtain lecturer/advisor decisions for the unresolved baseline definitions, ICC/percent-change conventions, 995-author reduced scope, and the counterfactual NM method; complete the coding tasks in §22. Independently verify the supplied 995 IDs against the intended database and document portfolio, coauthor, citation and NM provenance.
2. From the validation-project directory, verify the offline environment with:

   ```powershell
   .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
   .\.venv\Scripts\python.exe -B run_validation.py --dry-run
   ```

3. **Only after those issues and data checks are resolved**, a selected-ID read-only pilot can be invoked with the unchanged master CSV. Replace each quoted reference with a real documented reference and supply the project-local `inputs/portfolio_verification.csv`; add external `--input` CSVs and method flags required by the specific RQ:

   ```powershell
   .\.venv\Scripts\python.exe -B run_validation.py --data-source pilot --experiment rq01 `
     --pilot-author-ids 995_authors.csv `
     --pilot-design-reference "approved 995-author reduced-study protocol" `
     --database-ready-reference "verified cohort and database readiness report" `
     --citation-source-reference "approved citation-source provenance" `
     --input portfolio_verification=inputs/portfolio_verification.csv
   ```

   The project reads its own ignored `config/config.env`. Never pass credentials on the command line. Review `data_quality_report.csv`, `validation_dataset.csv`, `experiment_eligibility.csv`, per-RQ status files and `run_metadata.json` before any interpretation. The 995-author route remains labelled a **pilot**, not the planned 100,000-profile study.

No real experiment, production database access or write, migration, production code change, commit, or push occurred during this audit.
