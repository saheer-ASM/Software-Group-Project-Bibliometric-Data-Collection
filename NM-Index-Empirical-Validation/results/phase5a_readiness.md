# Phase 5A metric-layer readiness

**Status: METRIC_LAYER_NOT_READY** for complete empirical validation of the lecturer-selected 1,000 authors. This status concerns the **metric layer**, not whether the offline software runs. No real-author calculation was performed in Phase 5A.

## Ready metrics, subject to data gates

| Metric | Source-supported implementation | Real-data gate |
|---|---|---|
| Raw Total Cites | Sum raw citations across distinct author-linked papers. | Independently verified complete portfolio and approved provenance of `publication.total_citation`. |
| h-index | Largest rank `h` with the `h`th most-cited paper having at least `h` citations. | Same portfolio and citation-source gates. |
| g-index | Largest `g` among observed papers whose top-`g` cumulative citations reach `g²`. | Same data gates; the manuscript's five-paper `g=12` example conflicts with its written rule, so approve the finite-paper interpretation before comparative claims. |
| hf-index | Largest `h` whose `h`th ranked `c_p/N_p` reaches `h`, with uniform full-coauthor fractional shares. | Verified **complete** coauthor count `N_p` per paper and an approved real-input path. The current real/pilot pipeline deliberately leaves it null; it runs on declared-complete synthetic data only. |

The stored `author_nm_index.nm_index` is the NM target, not a locally recomputed baseline. Its six stored components and percentiles remain separate from every conventional comparator.

## Pending metrics and exact reasons

| Metric | Blocking source or data issue |
|---|---|
| C-score raw | The latest PDF names six standardized indicators and shows a paper-role fraction, but omits a general six-indicator construction, normalization reference distributions, and complete standardization procedure; its attribution descriptions are internally unclear. |
| C-score self-citation adjusted | A distinct conventional adjustment formula and rule for recalculating all indicators are **NOT SPECIFIED IN LATEST SOURCE**. NM influential-self-citation equations cannot be substituted. |
| hm-index | Original fractional rank is described, but full threshold/ranking treatment is not consistently specified; worked examples conflict. |
| m-index | `m=h/t` is stated, but as-of date, elapsed versus inclusive career-year convention, and missing/zero-duration rules are **NOT SPECIFIED IN LATEST SOURCE**. |
| Fi-score | Formula, data-driven threshold and its derivation are **NOT SPECIFIED IN LATEST SOURCE**. |
| s-index | Exact equation is **NOT SPECIFIED IN LATEST SOURCE**, and the PDF's s-versus-b-index identity/reference is unclear. |
| AR-index | Exact age weighting, as-of date and zero-age handling are **NOT SPECIFIED IN LATEST SOURCE**. |

All seven pending comparator columns remain null by default. Their strategy interfaces require an explicit approval reference and do not supply substitute formulas. An approval string alone is not independent methodological review.

Before real empirical execution, resolve the seven definitions/conventions with citable authority and approved procedures, settle the g example interpretation, establish full author-paper/coauthor coverage and citation provenance, and review the cohort and RQ-specific methodology gates. The synthetic pipeline demonstrates software behavior only; it provides no validation conclusion.

See [the full Phase 5A audit](phase5a_metric_audit_report.md), [formula table](baseline_formula_verification.csv), [latest-PDF reference](latest_pdf_metric_reference.md) and [g-index discrepancy](g_index_source_issue.md).
