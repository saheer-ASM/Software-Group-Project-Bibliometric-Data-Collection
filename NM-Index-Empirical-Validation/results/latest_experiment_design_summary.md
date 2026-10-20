# Latest experiment design — source summary

Source: [Pasted markdown(7).md](../source_documents/Pasted%20markdown%287%29.md),
read in full on 2026-10-04. This is a research plan, not completed empirical
evidence. It calls the target **Nm-Index** and the comparators **11 baselines**
(the table heading “12 Total” includes the Nm-index).

## Purpose, population and sample

The purpose is to evaluate associative power, paired differences,
interchangeability, discrimination, unique predictive power, score evolution,
gaming resistance, predictive validity, temporal stability, construct validity
and fairness. Primary data: 100,000 Google Scholar author profiles; OpenAlex
is supplementary. Sampling must be stratified over all 334 system fields,
career stage and geographic region. Stages are early `t≤5`, mid-early
`5<t≤15`, mid-late `15<t≤30`, senior `t>30` years. Eligibility calls for at
least five publications, at least ten total citations, an active record between
2000 and 2024, and complete publication years and author positions. The
current roughly 2,507-author database is a development pilot, not the final
target sample. The document gives no imputation rule; it explicitly excludes
authors with incomplete key metadata from its intended final sample.

## Baselines and explicit definitions

The “Baseline Indices (12 Total)” table names: Total cites (sum of all
citations); C-score raw (citation score with position weights); C-score SC adj.
(self-citation adjusted); h-index (maximum h with h papers having at least h
citations); hm-index (multi-authored, harmonic); hf-index (fractional,
contribution-weighted); g-index (maximum g whose top g papers have at least g²
total citations); m-index (h divided by career years); Fi-score
(self-citation evaluation); s-index (self-citation index); and AR-index
(age-weighted citation rate). Exact operational formulas are given only for
Total cites, h, g and m. The m entry does not fix an as-of date or year-count
convention. The document lists `T_a`, `S_a`, `U_a`, `Hf′`, `Hm′`, `G′` as six
distinct **NM sub-scores**, not as conventional baseline implementations.

## Research questions, methods and outputs

| RQ | Experiment, method and principal output |
|---|---|
| RQ1 Associative Power | Pearson r against all baselines, 95% CI and p-values; correlation matrix, QQ, residual and Bland–Altman plots. |
| RQ2 Paired Difference Analysis | Paired t-tests, mean difference, Cohen's d and 95% CI; paired difference table. |
| RQ3 Interchangeability | ICC for Nm versus each baseline; interpretation cutoffs <0.5 poor, 0.5–0.75 moderate, 0.75–0.9 good, >0.9 excellent. |
| RQ4 Discriminative Power | Top 5% Nm scores versus recipients of 13 listed awards; ROC/AUC, means, Cohen's d, p-values. |
| RQ5 Unique Predictive Power | Multiple linear regression and scenario comparisons for ISC, contribution/ordering norms, domain sensitivity and career stage. |
| RQ6 Score Evolution | Longitudinal line plots of one representative individual's Nm, h, C-score and citations against time/papers. |
| RQ7 Gaming Resistance | Simulate 50% more self-citations, twice the papers at half citations, 30% more coauthors, and their combination; report percentage index inflation. |
| RQ8 Predictive Validity | 10,000 authors with complete 2015–2024 longitudinal data; index at t versus citations in t+1…t+5, awards by t+5 and h growth. |
| RQ9 Temporal Stability | Annual mean absolute rank change, adjacent-year Spearman ρ and share with >10% rank change. |
| RQ10 Construct Validity | PCA on six NM sub-scores; expected 2–3 PCs explaining >80% variance. |
| RQ11 Fairness Analysis | Name-inferred gender, institution-derived region; Cohen's d male/female and variance of regional means. |

The required files named by the design are `correlation_matrix.csv`,
`paired_difference_stats.csv`, `icc_analysis.csv`, `award_analysis.csv`,
`self_citation_analysis.csv`, `author_ordering_analysis.csv`,
`domain_sensitivity.csv`, `career_stage_analysis.csv`, `score_evolution.csv`,
`gaming_resistance.csv`, `predictive_validity.csv`,
`temporal_stability.csv`, `pca_loadings.csv`, `fairness_analysis.csv`, and
`sensitivity_results.csv`. All are future experiment outputs, not requested
in this audit. Figures are specified as PDF/PNG at 300 DPI and in a
colorblind-safe palette. Reporting standards require exact p-values, 95% CIs,
effect sizes, Bonferroni correction and subgroup sample sizes.

## Hypotheses, robustness, fairness and missing data

The document phrases expectations such as lower gaming inflation, more
distinct sub-scores, and lower demographic disparities, but does not give a
numbered, formally prespecified hypothesis list. Its expected-results outline
includes a later “Evaluation of Formulated Hypotheses”. Those expectations
must not be reported as results.

Robustness checks vary sample size (25k, 50k, 75k, 100k) for Nm–h and Nm–C
correlations; sensitivity tables vary career compensation `(C, λ)` and ISC
`ε₀`. Fairness requires gender and geographic subgroup coverage, which the
current 15-table pilot schema does not establish. No general missing-value
imputation, missing-baseline pairwise-analysis policy, or treatment of
unavailable baselines is specified. The author selection rule excludes missing
publication years/positions, but the database pilot must report missingness
before applying final-cohort eligibility.

## Scope caution

This summary records the design's prospective experiments only. None of RQ1–11,
PCA, ROC/AUC, correlations, fairness or hypothesis tests has been performed by
the validation project in this audit.
