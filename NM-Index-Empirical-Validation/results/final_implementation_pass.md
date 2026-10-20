# Final source-supported implementation pass

**Decision: CODE_ISSUES_REMAIN.** The code paths added here are tested offline, but the full source-specified validation system is still incomplete: independent NM component verification and the design's name-based gender classification have no implementation, and several named RQ diagnostics and comparisons remain blocked by unspecified conventions. Real award, historical, scenario and full-coauthor evidence is also absent. This is not a completed empirical study or a claim that all RQs are ready. The older requirements audit remains a historical pre-pass snapshot; the updated 48-row [matrix](final_requirements_vs_code.md) is the current checklist.

## Sources and safety

Only `source_documents/Pasted markdown(7).md` (SHA-256 `0ec5857ff77d449ac9fb6ea131ebb7ce9755ce411af14e309dce478316896b8a`) and `source_documents/Nm Index novel model (1)(3).pdf` (SHA-256 `3bffd57d10b334bf4e37d437bf6babe6a9ae333cada1e6102be9181539ebdb91`) were used as current source documents. Both were readable. Neither was edited. All edits are inside this validation project. No database connection, SQL, production calculation runner, real 995-author experiment, commit or push was performed.

## Implemented changes and files

| Area | Change | Files |
|---|---|---|
| RQ1 and figures | Generate normal QQ plots for available metrics; include all available baseline columns in comparison/heatmap figure selection; use serif figure font. Existing Pearson r, exact p, Fisher CI and Bonferroni code was retained. | `visualization/correlations.py`, `visualization/core.py`, `src/pipeline.py` |
| RQ4 | Plot available Nm, h, g, raw C-score and Total Cites ROC curves together with AUC in the legend. Accept verified `award_events` for the 13 listed categories and count cohort/top-five-percent awardees. Binary labels are validated and never fabricated. | `experiments/rq04_discrimination.py`, `visualization/discrimination.py`, `src/external_inputs.py`, `src/pipeline.py` |
| RQ5 | Preserve all six ISC and six ordering scenario rows, eight exact domain-percentage bands, and nine exact listed career bands. Empty rows are `INPUT_DATA_REQUIRED`. Count labels and career years that cannot be placed, including the source's omitted `10<t<=15` interval. | `experiments/rq05_unique_power.py` |
| hf-index | Accept independently verified complete per-publication coauthor counts through a project-local CSV. Missing, invalid or unverified counts yield unavailable hf for the affected author. Input digests now support publication-keyed CSVs. | `src/external_inputs.py`, `src/pipeline.py` |
| Eligibility | Enforce activity within 2000–2024 and complete linked publication years/author positions in addition to existing publication, citation, NM and portfolio gates. Save each failure in `eligibility_reason`. | `src/eligibility.py`, `src/validation_dataset.py`, `src/pipeline.py` |
| Reports and handoff | Distinguish implemented result, unavailable input, methodology pending and not executed in each run report; document input contracts and the updated requirements matrix. | `src/pipeline.py`, `README.md`, `results/final_requirements_vs_code.csv`, `results/final_requirements_vs_code.md`, this report |
| Tests | Add offline regression checks for source bands and gap, RQ4 combined figure/category counts, hf verification, explicit eligibility reasons and QQ output. | `tests/test_final_pass.py` |

## RQ status and unresolved methods

**RQ1 — PARTIAL.** Pearson correlation, p-values, 95% CI, Bonferroni and the available-metric correlation matrix remain operational. Normal QQ plots are newly generated. The existing paired mean-difference scatter is only descriptive; the documents do not specify a regression model for residual plots or the scale/limits convention for Bland–Altman analysis across different index units. These are methodology dependencies, so no residual or limits-of-agreement result is claimed. A full 12×12 matrix still requires the unresolved baselines.

**RQ4 — PARTIAL / INPUT_DATA_REQUIRED.** With supplied binary labels, ROC/AUC, top-five-percent counts and a combined ROC figure work for available metrics. Optional award-event evidence produces counts for each of the 13 named awards; missing categories are explicit. The design does not define the reference population for comparator percentiles or the independent-group effect and p-value test convention, so Table 4's means, Cohen's d and p-value remain NULL. No awardee identities were inferred.

**RQ5 — PARTIAL / INPUT_DATA_REQUIRED.** Four required CSV names remain `self_citation_analysis.csv`, `author_ordering_analysis.csv`, `domain_sensitivity.csv`, and `career_stage_analysis.csv`. The table row labels and inequality boundaries now follow Tables 5–8. `rq05_unclassified.csv` records observations excluded by unsupported labels or the career-table gap. Observed scenario/ordering/domain/field evidence must be supplied. The multiple-regression predictor and covariate set is not specified; it remains an explicit decision. The design specifies RQ5 tables but no separate RQ5 figure with axes or plotting method, so no speculative RQ5 figure was added.

**RQ7 — METHODOLOGY_DECISION_REQUIRED.** Existing code already transforms copies in memory for +50% self-citations, doubled papers/halved citations, +30% coauthors and the combined case. It records raw changes and can calculate h/g inflation only with an approved fractional-citation policy. It does not recompute stored NM, C-score, hm or hf under counterfactuals. To do so, the project needs a separately validated local NM/ISC calculator with complete paper-author, contribution, field-reference and citation inputs, plus an approved treatment of fractional counts, changed author networks and zero original scores. The latest PDF describes the NM model, but the complete counterfactual data/method and verified independent implementation are not available here. No result is substituted.

**Career/ISC parameter sensitivity — METHODOLOGY_DECISION_REQUIRED.** The lecturer lists C/λ pairs `(1.00,0.00)`, `(1.25,0.0601)`, `(1.50,0.10)`, `(2.00,0.15)` and ISC ε₀ values `0.50,0.75,0.90,1.00`, with rank, Gini, mean ISC and binary-correlation outputs. Recomputable and independently verified NM/ISC inputs, the binary comparator, and explicit comparison conventions are not available. Stored production NM values cannot be reused as alternate-parameter results. No fabricated parameter table was generated.

**hf-index — INPUT_DATA_REQUIRED for real data.** `--input coauthor_counts=inputs/coauthor_counts.csv` expects `pub_id,coauthor_count,verified_complete,evidence_reference`; `verified_complete=true` attests the full paper author count. Every linked paper must have a unique verified positive integer count. Any absent or unverified paper makes that author's hf NULL. The source database's ten author slots are never treated as proof of complete coauthorship.

**Eligibility — READY as an observed-snapshot gate.** Each author receives all applicable reason codes. Active 2000–2024 means at least one linked publication year in that inclusive period. Every linked publication year must be valid, and each observed link must have a position. These checks do not prove a complete career portfolio; independent `portfolio_verification` remains mandatory. This pass did not implement the lecturer's full 100,000-author, 334-field stratified sampling.

**Figures — PARTIAL.** Generated PNGs use 300 DPI, 6×4 or 10×6 canvases, local output folders and serif fonts. Available RQ1 QQ plots have theoretical/observed quantile axes; the correlation heatmap labels metrics and Pearson r; the combined RQ4 plot labels false/true positive axes and has AUC legend. Existing RQ6, PCA, fairness and robustness plots retain their code paths. Full RQ1 residual/Bland–Altman analyses and a defensible RQ7 inflation plot depend on the unresolved methods or values. The lecturer lists RQ5 tables, with no defined RQ5 plot. Synthetic test figures carry a classification footer.

**Reports — PARTIAL.** Run reports now show execution/evidence states and avoid treating status-only outputs as findings. A full Results/Discussion/Conclusion paper cannot be written without real analysis, complete baselines and approved methods. The 995-author pilot cannot satisfy the design's 100,000-author full study, RQ8's 10,000-author sample, or 25,000–100,000 robustness targets.

The unresolved baseline formulas remain unresolved: raw and self-citation-adjusted C-score, hm, m convention, Fi, s, and AR. No textbook substitute was added. ICC model/scale, RQ9 rank-change denominator, several normalization choices, demographic inference policy and the RQ1/RQ4/RQ7 methods above also require documented decisions.

## External input format

- `award_labels.csv`: `author_id,awardee`, one row per author, true/false binary labels with independently documented provenance.
- `award_events.csv`: `author_id,award_category,evidence_reference`, zero or more awards per author, exact 13 source category strings, unique author/category pairs. A cohort event must agree with a positive binary label.
- `coauthor_counts.csv`: `pub_id,coauthor_count,verified_complete,evidence_reference`, one row per paper, complete verified full coauthor count.
- Existing RQ5 observed `scenario_data`, portfolio evidence, annual/historical and future records, demographic labels, reference percentiles and paper-level gaming inputs remain separately required; their schemas are in `src/external_inputs.py` and `README.md`.

## Offline verification

- All **53** offline unit tests passed, including six new regression tests. No DB connection was used.
- Python AST syntax parsing passed for **86** project `.py` files outside environments/caches.
- `run_validation.py --dry-run` returned `DRY_RUN_OK`, `database_access=false`, `database_writes=false`.
- `run_validation.py --data-source mock` completed with **12 synthetic authors, 12 eligible, 39 CSVs, 33 PNGs and six reports** in `results/run_20261017T142234940275Z` and matching `figures/` directory. These are labelled **SYNTHETIC TEST DATA — NOT EMPIRICAL RESULTS**. Several RQ statuses remain pending; a completed mock run is not completed validation.
- `git status --short` in the parent production repository showed only `?? NM-Index-Empirical-Validation/` (the entire validation project is untracked). No tracked production file was changed, and no commit/push was made.
