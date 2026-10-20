# Targeted remaining-gap review: RQ1, RQ4, RQ7

**Final decision: C. Some require a methodology decision.** None of the four remaining analyses can be completed from the current documents alone without choosing an unstated convention or supplying the counterfactual inputs described below. Existing partial analyses remain operational. This report is limited to the four requested items; it does not reopen the wider project audit or claim empirical findings.

Sources inspected: `source_documents/Pasted markdown(7).md` (latest lecturer design) and `source_documents/Nm Index novel model (1)(3).pdf` (latest manuscript). The former has SHA-256 `0ec5857ff77d449ac9fb6ea131ebb7ce9755ce411af14e309dce478316896b8a`; the latter has SHA-256 `3bffd57d10b334bf4e37d437bf6babe6a9ae333cada1e6102be9181539ebdb91`. No older version was used to override them.

## 1. RQ1 residual analysis

| Check | Finding |
|---|---|
| Lecturer requirement | Produce residual plots as diagnostics for the 100,000-profile, cross-index associative analysis. |
| Source location | Lecturer design, **RQ1 / Experiment 1.1 / Outputs**; latest manuscript, **§3.4 and Figure 5 placeholder**, printed pp. 25–26. |
| Exact method specified? | **No.** Neither source identifies a regression or fitted model, response/predictor pair, residual definition, residual scale, target comparisons, axis convention, or interpretation rule. Figure 5 is a placeholder, not a worked plot. |
| Current implementation | `analysis/correlation.py` and `experiments/rq01_correlation.py` calculate Pearson r, p-values, Fisher 95% CI, Bonferroni p-values and a matrix for available metrics. `visualization/correlations.py` and `src/pipeline.py` export scatter, heatmap, paired-difference and normal QQ plots. No plot is presented as a regression residual plot. |
| Exact missing functionality | A model-defined residual data series and its labelled figure/table. The existing paired difference is **not** silently relabelled as a model residual. |
| Methodology status | `METHODOLOGY_INPUT_REQUIRED`: specify fitted model, target/comparator, residual definition, scale and required axes/output. |
| Implementation status | `METHODOLOGY_INPUT_REQUIRED`; no source-complete residual algorithm can be added yet. |
| Files changed for this item | None. |
| Tests | Existing RQ1 and figure tests passed in the 53-test offline suite; no residual result was asserted. |

## 2. RQ1 Bland–Altman analysis

| Check | Finding |
|---|---|
| Lecturer requirement | Produce Bland–Altman plots among RQ1 diagnostic outputs. |
| Source location | Lecturer design, **RQ1 / Experiment 1.1 / Outputs**; latest manuscript, **§3.4 and Figure 5 placeholder**, printed pp. 25–26. |
| Exact method specified? | **Only the plot name.** Neither source states which two score measures should be compared, whether raw values or common-scale scores are used, how to handle the different units, the difference/mean convention, limits of agreement, confidence intervals, or the required table and interpretation. |
| Current implementation | `visualization/correlations.py::paired_difference` plots `(Nm + comparator)/2` against `Nm − comparator` in raw units and explicitly labels scale interpretation pending. `src/pipeline.py::_write_figures` exports it as `paired_nm_<metric>.png`. It has a zero line, **not** estimated bias or limits of agreement; it is a descriptive paired-difference scatter, not a completed Bland–Altman analysis. |
| Exact missing functionality | Approved comparison and scale plus fully defined Bland–Altman plot/limits and any table. |
| Methodology status | `METHODOLOGY_INPUT_REQUIRED`: specify score pair(s), common-scale conversion (if any), mean/difference convention, agreement limits and uncertainty/reporting convention. |
| Implementation status | `METHODOLOGY_INPUT_REQUIRED`; adding conventional limits or transforming scores without approval would import an unstated method. |
| Files changed for this item | None. |
| Tests | Existing paired-difference and figure-export tests passed; no Bland–Altman result was asserted. |

## 3. RQ4 award-recipient comparison

| Check | Finding |
|---|---|
| Lecturer requirement | Compare awardee and non-awardee scores; count award recipients in the top 5% of Nm; present Table 4 rows for Nm, Total Cites, raw C-score, h and g with awardee/non-awardee mean percentiles, Cohen's d, AUC-ROC and p-value. Draw combined ROC curves with false-positive-rate and true-positive-rate axes and AUC in the legend. Cover the 13 named awards. |
| Source location | Lecturer design, **RQ4 / Experiment 4.1 / Award Categories / Table 4 / Figure**; latest manuscript, **§3.4.4**, printed p. 26. |
| Exact method specified? | **Partially.** The top-5% count, binary award discrimination, ROC/AUC, five table rows and combined figure are specified. The source does **not** specify the comparator percentile reference population/transformation, independent-group Cohen's d convention, p-value test, multiple-award attribution rule for inferential comparisons, or handling of missing award records. |
| Current implementation | `experiments/rq04_discrimination.py` accepts validated `award_labels` (`author_id,awardee`) and optional evidenced `award_events` (`author_id,award_category,evidence_reference`). It creates `award_analysis.csv` with five score rows, top-5% Nm counts, ROC/AUC and bootstrap AUC CI for available metrics; `award_category_counts.csv` covers all 13 named categories. `analysis/discrimination.py` derives AUC from binary labels. `visualization/discrimination.py::combined_roc`, invoked by `src/pipeline.py`, exports `figures/run_*/award_roc_combined.png` with the specified axes and AUC legend. A missing raw C-score remains unavailable rather than being fabricated. |
| Exact missing functionality | Valid awardee and non-awardee observations from a real sourced dataset; reference percentiles for each comparator; source-approved effect-size and p-test conventions. Current `awardee_mean_percentile`, `non_awardee_mean_percentile`, `cohen_d` and `p_value` columns remain NULL with `METHODOLOGY_PENDING`, correctly indicating Table 4 is incomplete. No real award dataset is present. |
| Methodology status | `METHODOLOGY_INPUT_REQUIRED` for the full Table 4 comparison; `INPUT_DATA_REQUIRED` for execution of already implemented top-5% and ROC/AUC paths on real authors. |
| Implementation status | `ALREADY_IMPLEMENTED` for specified top-5% counts, 13-category count structure, ROC/AUC and combined figure. `METHODOLOGY_INPUT_REQUIRED` for the unresolved comparison fields. |
| Files changed for this item | None. |
| Tests | Award-label, category-count and combined-figure regression tests passed. Synthetic output contains five table rows; raw C-score is `INSUFFICIENT_DATA`, and comparator mean/effect/p columns remain blank. |

**Input contract:** `award_labels.csv` has one `author_id,awardee` row per cohort author, with positive and negative labels established from independent evidence. `award_events.csv` records one evidenced `author_id,award_category,evidence_reference` row per award/category combination. Both are project-local and read-only inputs. The manuscript's approximate award counts are not individual labels and cannot be substituted for this dataset.

## 4. RQ7 counterfactual NM calculation

**RQ7 COUNTERFACTUAL NM CALCULATION: METHODOLOGY_INPUT_REQUIRED.**

| Check | Finding |
|---|---|
| Lecturer requirement | Simulate +50% self-citations, twice the papers with half the citations per paper, +30% coauthors, and their combined manipulation; report percentage inflation for Nm, h, C-score, hm, hf and g. |
| Source location | Lecturer design, **RQ7 / Experiment 7.1 / Table 9**; latest manuscript, **§3.4.7 / Table 17**, printed p. 28. Static NM model: manuscript **§§2.2–2.5, Equations 7–27**, printed pp. 8–13. |
| Exact method specified? | **No complete counterfactual method.** The manuscript gives the static ISC, component and percentile equations but does not map manipulated publications/citations/coauthors to a fully specified new author/citation graph, contribution weights, field/year benchmarks and reference percentile population. It does not say whether these benchmarks/percentiles are frozen or recomputed after each manipulation. |
| Current implementation | `analysis/gaming.py` transforms local paper-level arrays in memory for the three named strategies and combined case. `experiments/rq07_gaming_sensitivity.py` writes raw citation changes to `gaming_resistance.csv` and, with an explicit fractional-count decision, h/g percentage inflation to `gaming_index_inflation.csv`. Stored NM is never multiplied, approximated or overwritten; its counterfactual rows remain `METHODOLOGY_PENDING` and NULL. No database write is performed. |
| Exact missing functionality | For +50% self-citations: identify added citing papers/author identities and contribution weights so Equation 7 ISC can be recalculated, rather than adding an undifferentiated scalar. For salami slicing: define new paper dates, fields, author lists/positions/contributions, citation-edge allocation and career implications. For gift authorship: define the additional authors' identities/positions/contributions and resulting citation-overlap network. For all cases: obtain complete field/year comparison distributions, outlier caps, six component calculations, chosen percentile transform/reference cohort, update-versus-freeze policy, and zero-baseline percentage handling. A validated local NM calculator using these inputs would then be required. |
| Methodology status | `METHODOLOGY_INPUT_REQUIRED`: the static equations alone do not define these scenario-specific inputs and decisions. |
| Implementation status | `ALREADY_IMPLEMENTED` for local transformations and conditional h/g inflation; `METHODOLOGY_INPUT_REQUIRED` for counterfactual NM and the full Table 9. |
| Files changed for this item | None. |
| Tests | Gaming-array guards and synthetic-pipeline tests passed; the synthetic `gaming_index_inflation.csv` leaves all Nm counterfactual values NULL. |

## Verification and scope

Only this report was authored in the targeted review. No calculation, experiment, visualization or test code was changed. The current offline suite passed **53 tests**; AST parsing passed for **86** Python files; `run_validation.py --dry-run` returned `DRY_RUN_OK` with `database_access=false`; and `run_validation.py --data-source mock` completed at `results/run_20261017T142928525535Z` using labelled synthetic authors. That run is a software test, not a real RQ result.

The production frontend, backend, NM implementation and database were untouched. No real 995-author experiment, database connection, SQL, migration, commit or push occurred. The final outcome is **C. Some require a methodology decision**; real award data is an additional input requirement, not a substitute for the missing conventions.
