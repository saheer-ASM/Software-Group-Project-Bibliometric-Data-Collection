# Final methodology implementation report

**Final status: CODE_ISSUES_REMAIN.** The lecturer-approved RQ1 OLS residual and percentile Bland–Altman methods are implemented and tested on synthetic data. RQ7 has a frozen-original-reference contract, guarded graph transformations and percentile-inflation arithmetic, but **does not have a validated end-to-end NM counterfactual calculator**. No real 995-author experiment should be started or interpreted as complete RQ7 validation.

The current source of truth was `source_documents/Pasted markdown(7).md`, `source_documents/Nm Index novel model (1)(3).pdf`, and the lecturer decisions supplied for this pass. The reference documents were read, not edited. See [lecturer-approved methodology](lecturer_approved_methodology.md) for the exact methods and remaining boundaries.

## Files changed

| Purpose | Files |
|---|---|
| RQ1 percentile reference, OLS and Bland–Altman calculations | `analysis/rq01_diagnostics.py`, `experiments/rq01_correlation.py` |
| RQ1 figures | `visualization/correlations.py`, `src/pipeline.py` |
| RQ7 frozen reference, graph transformations and inflation guard | `analysis/counterfactual.py`, `analysis/gaming.py`, `experiments/rq07_gaming_sensitivity.py` |
| External reference input contract | `src/external_inputs.py` |
| Synthetic regression and integration checks | `tests/test_lecturer_methodology.py`, `tests/fixtures/synthetic.py` |
| Handoff documentation and 48-row matrix | `README.md`, `results/lecturer_approved_methodology.md`, `results/final_requirements_vs_code.csv`, `results/final_requirements_vs_code.md`, this report |

## RQ1 result

The OLS fit uses the lecturer's `NM percentile ~ C-score percentile` model, with author residual `observed − fitted`. It exports regression coefficients, R², fitted values, residuals and author-level exclusion reasons. Two labelled, career-coloured figures plot residuals against fitted NM percentile and middle-author-paper share. A real input must provide an evidenced, versioned **exactly 100,000-author** reference and contain all selected author IDs. The local 995-author pilot is never used as a substitute percentile reference.

The Bland–Altman path converts NM and each complete available baseline column to percentiles **within that same reference**, then exports pair means, differences, bias, sample SD, conventional `bias ± 1.96×SD` limits, empirical 2.5th/97.5th difference endpoints, and numeric skewness. It generates a labelled plot and difference histogram for each complete baseline. It does not replace conventional limits automatically. The source gives no numeric definition of *clearly skewed*, so the output marks skewness assessment for review rather than inventing a cutoff. Average tied empirical percentage ranks are documented as the operational ranking convention; approval of a different tie convention would require an explicit methodology update. Baselines absent from the reference are individually `DATA_REQUIRED`, never zero-filled.

The synthetic run generated `rq01_residual_coefficients.csv`, `rq01_residuals.csv`, `rq01_bland_altman_summary.csv`, `rq01_bland_altman_pairs.csv`, author-status data, two residual figures, five Bland–Altman figures and five difference histograms. Five baseline comparisons had complete synthetic data; the remaining six were marked `DATA_REQUIRED`. This is **software verification only**.

## RQ7 result and boundary

`FrozenBenchmarks` retains immutable serialized copies and a SHA-256 digest of original field/year means, field caps, Z means, Z SDs and percentile references, keyed to the original author set and benchmark version. A real snapshot is rejected unless it has exactly 100,000 unique original authors. Tests prove that mutating source or returned table copies does not alter the frozen snapshot.

Guarded in-memory functions add explicitly supplied citing-paper edges containing the target and relevant core authors; split papers with identical authors, field and year and explicitly allocated equal citation edges; and add the target to an explicit middle position on existing coauthors' papers equal to 30% of the portfolio. They preserve original DataFrames and reject missing graph metadata, inconsistent citation totals, noninteger exact 50%/30% counts, or unsupported allocations. The scalar-count helper is retained only as a labelled legacy diagnostic and is no longer called by the RQ7 runner.

`percentile_inflation` implements `(manipulated − original) / original × 100` on validated percentile values and returns `NOT_APPLICABLE` with an explicit reason when the original percentile is zero. **It is not applied to NM in a real scenario**, because this validation project still lacks an independent, validated implementation of the latest manuscript's full ISC, contribution, career, field/year normalization, outlier-capping, six-component and percentile NM calculation and lacks its complete graph/reference inputs. The RQ7 runner now exports the required author/scenario/parameter/benchmark/exclusion columns with manipulated NM and inflation blank and a reason, rather than claiming aggregate citation changes are NM counterfactual results. It also leaves unapproved hm/C-score baselines `METHODOLOGY_UNSPECIFIED`.

This is a material **code gap**, with additional data and decisions: a complete citing-paper authorship/citation graph, contribution/order and field metadata, all five original 100,000-author benchmark tables, exact self-citation additions, explicit edge allocation for splits and gift-paper/position assignments. The lecturer fixed the frozen-reference policy but did not specify rounding when 50% or 30% is noninteger; those cases are rejected pending a decision. No NM score is approximated or multiplied.

## The selected cohort

`995_authors.csv` contains 995 selected stable IDs with `author_id,author_name` columns. It is already approximately the lecturer's 1,000-author RQ7 group; no random replacement cohort was created. The file lacks fields, first-publication dates, career stages and full-paper/citation metadata, so stratification across fields and careers cannot be verified from it alone. The complete 100,000-author reference is a separate required input. No real database connection was made to fill these gaps.

## Verification and safety

- **63/63** offline tests passed, including new checks for the RQ1 residual definition, OLS fit/fitted values, career-coloured figures, percentile Bland–Altman bias/limits/endpoints, frozen benchmark immutability, graph transforms, inflation and zero guard.
- AST parsing passed for **89** project Python files outside environments/caches.
- `run_validation.py --dry-run` returned `DRY_RUN_OK`, `database_access=false`, `database_writes=false`.
- The final `--data-source mock` run completed in `results/run_20261019T081248058338Z`: **12 synthetic authors, 12 eligible, 44 CSVs, 45 PNGs and six reports**. It produced 12 new RQ1 residual/Bland–Altman figures. RQ1's overall status remains `DATA_REQUIRED` for missing baseline/reference coverage; RQ7 remains `METHODOLOGY_PENDING`. All mock outputs are labelled synthetic and are **not empirical results**.
- The parent repository's `git status --short` showed only `?? NM-Index-Empirical-Validation/`; no tracked production file changed. No database connection, SQL write, migration, existing calculation runner, real 995-author experiment, commit or push occurred. Credentials were not read or exposed.

**Readiness decision: CODE_ISSUES_REMAIN.** RQ1 diagnostics are implemented for a complete supplied reference, but the full RQ7 NM recalculation and applicable baseline integration are not. Real external data alone will not make this pass ready for full handover until that independent calculator is completed and validated.
