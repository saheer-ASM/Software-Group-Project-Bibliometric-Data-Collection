# Lecturer-approved methodology and implementation boundary

Authoritative materials: the current `source_documents/Pasted markdown(7).md`, the latest `source_documents/Nm Index novel model (1)(3).pdf`, and the lecturer-approved decisions supplied for this implementation pass. **LECTURER-APPROVED DECISION** below identifies the new answers; implementation details and remaining dependencies are distinguished explicitly.

## RQ1: OLS residuals

**LECTURER-APPROVED DECISION:** Regress NM-index percentile on C-score percentile by ordinary least squares in the complete 100,000-author reference sample. For every author, residual = observed NM percentile − fitted NM percentile. Produce residual-versus-fitted and residual-versus-middle-author-paper-share plots, colouring points by career stage. The second plot tests whether profiles dominated by middle-author papers have positive residuals; it is a diagnostic, not a presupposed result.

`analysis/rq01_diagnostics.py` fits one-intercept/one-slope OLS and exports coefficients, fitted values, residuals, model R² and author-level exclusions. `src/pipeline.py` exports the two named figures. Real runs require `reference_scores.csv` with exactly 100,000 unique author IDs and columns `author_id,nm_index,c_score_raw,middle_author_share,career_stage,reference_version,evidence_reference`; optional baseline score columns enable additional Bland–Altman comparisons. Middle-author share must be independently derived from complete paper authorship, with value in [0,1]. Career stage must be one of `Early`, `Mid-Early`, `Mid-Late`, `Senior`. The selected 995 IDs must all occur in this reference. A synthetic fixture may use a smaller explicitly labelled TEST-only reference. No missing author is silently dropped.

The implementation uses empirical percentage ranks with average ties (`pandas.rank(method="average", pct=True) × 100`) for both axes. This is a documented operational tie convention, not a claim that the lecturer separately specified tie handling for every baseline. If the research team requires a different tie convention, it must approve that before interpreting real results.

## RQ1: percentile Bland–Altman

**LECTURER-APPROVED DECISION:** Convert NM and every baseline to percentiles using the **same original 100,000-author reference**. For each author, difference `D = NM_percentile − baseline_percentile`, mean `M = (NM_percentile + baseline_percentile)/2`; bias is mean(D), and conventional lower/upper 95% limits are `bias ± 1.96 × sample SD(D)`. Export a plot with bias and both limits, and a difference histogram, per available baseline. Also report 2.5th/97.5th empirical difference percentiles when the distribution is clearly skewed; do not automatically replace the conventional limits.

The code always supplies the empirical endpoints alongside conventional limits so a reviewer can assess skewness without a fabricated numeric cutoff. It reports numeric skewness and `REVIEW_REQUIRED` rather than claiming the distribution is clearly skewed by an unsupported threshold. A baseline with any missing/nonfinite score in the frozen reference is marked `DATA_REQUIRED`; no partial cohort is silently re-ranked. Seven baselines still lack approved formulas or full data, so those comparisons remain unavailable. Existing raw-unit `paired_nm_*.png` plots are descriptive and are **not** the percentile Bland–Altman outputs.

## RQ7: original reference and frozen benchmarks

**LECTURER-APPROVED DECISION:** First calculate field/year citation means, kth-percentile caps, Z-normalization means and SDs, and percentile-reference distributions from the **original unmanipulated 100,000 authors**. Keep all these fixed while manipulating one author's copied data and rescore against that original population. Never multiply a stored NM score to imitate recalculation.

`analysis/counterfactual.py::FrozenBenchmarks` copies and hashes five benchmark tables and records the original author-set digest and version. Snapshots are separate copies; tests verify later source/snapshot mutation does not change the frozen bytes. The real 100,000-author source and its five benchmark tables have **not** been supplied. This contract is only a freeze/validation layer; it does not compute NM components.

## RQ7: three graph-level manipulations

**LECTURER-APPROVED DECISION:** (1) Add +50% self-citations as real citing-paper/citation-edge records whose authors include the target and relevant core collaborators. (2) Split each target paper into two with the same authors/field/year and half of its citations on each. (3) Add the target as a middle author on existing coauthors' papers equal to 30% of the target portfolio, retaining those papers' real citations and the target's original career start year. Recalculate contribution, ISC, career factor, normalization, capping, all six components, their percentiles and NM from these manipulated inputs.

`analysis/counterfactual.py` supplies **in-memory, guarded transformations** for the three input scenarios. It requires real edge identities, source paper metadata, explicit allocation of each original citation edge to one salami half, full citing-paper authors, a core-coauthor list, and explicit gift-paper middle positions. It does not invent these choices. If an exact +50% or +30% count is fractional, it raises `MethodologyInputRequired` because rounding was not specified. The original DataFrames remain unchanged. The previous aggregate-count helper in `analysis/gaming.py` is labelled legacy and is no longer called by the RQ7 runner.

**Remaining code/data gap:** There is no independently validated local implementation of the full latest-manuscript NM Equations 7–27, and the currently extracted records lack complete citing-paper authorship/contribution, full field/year benchmark and percentile-reference data. Accordingly, `experiments/rq07_gaming_sensitivity.py` does not claim an NM counterfactual. Its machine-readable rows retain author ID, scenario, parameters, blank original/manipulated NM percentiles and inflation, benchmark fields, authors used and explicit missing-data/exclusion reasons. A full NM calculation and integration are still required before real RQ7 execution.

## RQ7: baselines and inflation

**LECTURER-APPROVED DECISION:** Apply the same manipulated underlying papers/citation graph to h, hm, hf, g, C-score and other approved baselines. Do not invent unresolved baseline formulas. For each recalculable metric use `(manipulated percentile − original percentile) / original percentile × 100`; if the original percentile is zero, report undefined/not applicable, never infinity.

`analysis/counterfactual.py::percentile_inflation` implements and tests this arithmetic and zero guard. Full percentile recalculation is **not yet wired into RQ7** because the graph-level NM engine, frozen reference data and several baseline formulas are missing. RQ7 marks hm and C-score `METHODOLOGY_UNSPECIFIED`; it does not fabricate values for the other metrics.

## The selected 995-author cohort

The project-local `995_authors.csv` has **995 unique IDs** and columns `author_id,author_name`. This is approximately the lecturer's 1,000-author RQ7 cohort, so no new random authors should be drawn. The CSV does **not** include field, first-publication year, career stage, complete portfolios or graph evidence. Field/career stratification cannot be verified from this file alone. Those labels and the complete original 100,000-author reference must come from independently verified inputs before any real simulation. No real database connection or 995-author experiment was made in this pass.

## Offline code-completion update

The RQ7 code-gap statements above describe the earlier implementation stage.
`nm_index/counterfactual_calculator.py` now independently computes all six
latest-manuscript NM components from full, source-supplied citation graphs,
contribution modes, field weights and the frozen original benchmark. It uses
Equations 1–27, including Equation 7 ISC, Equation 10 career factor, and the
Blom plotting position for modified Hf/Hm/G components. Its out-of-reference
counterfactual values use a documented insertion-rank convention against the
unchanged reference, clamped to the original 1..N ranks. The analysis runner
recomputes NM for the three lecturer scenarios and four source-supported
conventional baselines, leaving unresolved hm and C-score formulas unavailable.
The full real-data graph and 100,000-author reference remain **input** gates,
not substitutes for source evidence. See `FINAL_HANDOVER_GUIDE.md` for the
canonical export contract and the current synthetic verification path.
