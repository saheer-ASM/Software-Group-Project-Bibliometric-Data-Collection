# Phase 3: source mapping and stored-value inspection

Author cohort: 2507 distinct authors.
Inspection interval (UTC): 2026-10-04T10:09:17.867080+00:00 to 2026-10-04T10:11:17.697883+00:00

## Required metric availability

| Metric | Available | Needs future calculation | Notes |
|---|---|---|---|
| NM-index | YES | NO | Stored final six-component percentile result. Inspect metrics_available; do not use the author mirror or backend H-squared/publication helper. |
| Total cites | NO | YES | Raw author-level total is not author_total_cites.total_cites_score, which is weighted/normalized. Paper totals require aggregation; legacy totals require ID/provenance verification. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| C-score raw | NO | YES | No verified stored experiment-design C-score. Backend c_index is total minus self citations; the UI C Score is total_cites_score. Neither is assumed equivalent. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| C-score SC adjusted | NO | YES | Adjusted paper-author citations are inputs, not a stored C-score. Exact baseline definition is required. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| h-index | NO | YES | Legacy h_index belongs to the plural authors schema. The research dashboard computes h-index at query time. No calculation or cross-schema identity inference here. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| hm-index | NO | YES | Modified hm is an NM component, not automatically the conventional hm baseline. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| hf-index | NO | YES | Modified hf is an NM component, not automatically the conventional hf baseline. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| g-index | NO | YES | Modified g is not automatically conventional g. Both stored modified-g locations are inspected separately. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| m-index | NO | YES | No verified stored baseline. Requires exact design definition and suitable citation/career data. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| Fi-score | NO | YES | No verified stored baseline. Exact experiment-design definition is required. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| s-index | NO | YES | No verified stored baseline. Exact experiment-design definition is required. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |
| AR-index | NO | YES | No verified stored baseline. Exact experiment-design definition and paper age/citation data are required. No verified stored result is available for validation. Confirm the supplied design definition before any later calculation; this phase does not calculate it. |

## Stored sources and coverage

| Source | Exact column | Authors | NULL rows | Duplicate author IDs | Min | Max | Mean | Median |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| NM-index | author_nm_index.nm_index | 2321 | 186 | 0 | 0.026925148088314487 | 99.94727886124838 | 27.109484629372243 | 24.57547249371654 |
| Total Cites Score (NM component) | author_total_cites.total_cites_score | 1561 | 760 | 0 | 0.0 | 165.12031636903077 | 0.17462814208357794 | 0.0 |
| Citations per paper (NM component) | author_citations_per_paper.citations_per_paper_score | 2321 | 0 | 0 | 0.0 | 10.591176045191238 | 0.03671154282766155 | 0.0 |
| Citation rate (NM component) | author_citation_rate.citation_rate_score | 2321 | 0 | 0 | 0.0 | 114.35623429827805 | 0.06683283604439297 | 0.0 |
| Modified hf (NM component) | author_modified_hindex.modified_hindex_final | 2143 | 197 | 0 | 0.0 | 467.0 | 0.9212933026860567 | 0.0 |
| Modified hm (NM component) | author.modified_hm_index | 2254 | 253 | 0 | 0.0 | 241.10728953597553 | 0.9315438687347016 | 0.0 |
| Modified g (NM component) | modified_g_index_results.modified_g_index | 2143 | 0 | 0 | 0.0 | 311.3333333333333 | 0.8487618255663949 | 0.0 |
| Modified g (author mirror) | author.modified_g_index | 2143 | 364 | 0 | 0.0 | 311.3333333333333 | 0.8487618255663949 | 0.0 |
| NM-index (author mirror) | author.nm_index | 0 | 2507 | 0 |  |  |  |  |
| Adjusted citations (paper-author records) | author_paper_adjusted_citations.total_adjusted_citation | 143 | 0 | 42 | 0.0 | 34.52877804014168 | 2.7556523702412905 | 0.5994557823129251 |
| Raw citations (paper-author records) | author_paper_adjusted_citations.total_raw_citation | 143 | 0 | 42 | 0.0550964187327823 | 35.45454545454546 | 3.1490066225165565 | 0.7249635036496349 |
| h-index (legacy candidate) | author_metrics.h_index | 0 | 0 | 0 |  |  |  |  |
| Total cites (legacy candidate) | author_metrics.total_citations | 0 | 0 | 0 |  |  |  |  |
| C-score (legacy candidate; different definition) | author_metrics.c_index | 0 | 0 | 0 |  |  |  |  |

NULL counts refer to rows actually present in each source, not missing author rows. Coverage counts finite values (including zero) on distinct IDs in public.author.
Repeated author IDs are expected for paper-author rows; use (cited_pub_id, target_author_id) to check duplicate records. No paper values were aggregated into author metrics.

## Exact source contracts

- NM: author_nm_index.author_id is the author key; nm_index is final. The six per_* columns are stored component percentiles. metrics_available is the component-count indicator, not a separate boolean completeness flag; calculated_at is its timestamp.
- Total Cites Score: author_total_cites.author_id, total_cites_score, career_factor, calculation_complete, calculated_at. This table has no separately stored raw/adjusted citation totals. Its score is normalized/weighted, not raw Total cites.
- Adjusted citation inputs: author_paper_adjusted_citations.cited_pub_id, target_author_id, citing_paper_count, field_row_count, total_raw_citation, total_adjusted_citation, calculated_at. Values are per paper-author, and raw_citation here must not be assumed to be a simple integer citation count.
- Modified hm is author.modified_hm_index. Modified g has two locations, reported separately. author.nm_index is only a mirror and is not used as the final source.

## NM-index distribution

```json
{
  "rows": 2507,
  "nonnull_finite_scores": 2321,
  "minimum": 0.026925148088314487,
  "maximum": 99.94727886124838,
  "mean": 27.109484629372243,
  "median": 24.57547249371654,
  "sample_standard_deviation": 12.098552676556316,
  "number_ge_90": 20,
  "number_ge_95": 20,
  "number_ge_99": 12,
  "number_eq_100": 0,
  "outside_0_100": 0,
  "metrics_available_distribution": {
    "6": 1537,
    "5": 606,
    "2": 67,
    "4": 24,
    "3": 87,
    "0": 186
  },
  "component_count_mismatches": 0,
  "component_null_counts": {
    "per_total_cites": 946,
    "per_citations_per_paper": 186,
    "per_citation_rate": 186,
    "per_modified_hf_index": 364,
    "per_modified_hm_index": 253,
    "per_modified_g_index": 364
  },
  "scored_with_fewer_than_six_components": 784
}
```

## Quality and interpretation

- See metric_data_quality.csv for nonfinite/negative values, orphan IDs, duplicate IDs, status conflicts, and sample standard deviation. Values marked incomplete are reported, never silently discarded.
- Per-metric summaries are descriptive statistics of stored values, not recalculated metrics.
- Source reads use separate read-only transactions. Concurrent pipeline updates can cause cross-table timing differences; this is not a single consistent snapshot.
- The complete experiment-design document is not included in this project. Conventional baseline definitions must be confirmed before any later implementation.

## Proposed final dataset

One row per public.author.author_id with author_name, the verified NM result, its six percentile components, metrics_available, and calculation timestamp. Store the required 11 baselines only after their definitions/sources have been verified in a later authorized phase. Keep modified component values and any mirror columns explicitly labelled as auxiliary fields; include provenance and completeness flags.
The current preview contains at most 20 deterministic IDs with available stored values. It is not a representative sample. Unknown values are blank, never imputed as zero. Duplicate author-level source IDs are excluded from preview joins rather than arbitrarily collapsed.
Actual preview columns: author_id, author_name, nm_index, total_cites_score, citations_per_paper_score, citation_rate_score, modified_hf_index, modified_hm_index, modified_g_index, author_modified_g_index, per_total_cites, per_citations_per_paper, per_citation_rate, per_modified_hf_index, per_modified_hm_index, per_modified_g_index, metrics_available, calculated_at

## Execution and safety

Run `.\.venv\Scripts\python.exe -B -m experiments.inspect_author_coverage` from the validation project.
All database operations use src.database.execute_select. No existing calculation scripts are imported or run. No metrics, correlations, paired tests, ICC, PCA, or ROC/AUC are calculated. No database writes, migrations, commits, or pushes are performed.
