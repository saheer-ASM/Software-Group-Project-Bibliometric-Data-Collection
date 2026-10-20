# NM components versus conventional baselines

The six raw NM components are **stored production results** read from `author_total_cites.total_cites_score`, `author_citations_per_paper.citations_per_paper_score`, `author_citation_rate.citation_rate_score`, `author_modified_hindex.modified_hindex_final`, `author.modified_hm_index`, and `modified_g_index_results.modified_g_index`. Their six percentile counterparts are `author_nm_index.per_*`. The final target is `author_nm_index.nm_index`, labelled `STORED_PRODUCTION_RESULT`. The validation project never computes a new production NM score.

| Similar name | NM component | Conventional baseline |
|---|---|---|
| Total Cites | `T_a`, Eq. 11: ISC-adjusted, author/field/year-weighted, career-compensated relative score. | Raw sum of `publication.total_citation` over distinct complete author-linked papers; Table 5 p. 21 example 165. |
| Citation per paper/rate | `S_a` and `U_a`, Eqs. 12–14: capped adjusted field-normalized scores, with `U_a` also using publication age. | Neither substitutes for AR-index or a raw total; no matching conventional comparator column exists. |
| hf | `Hf′_a`, Eqs. 15–17: effective adjusted citations with actual author contribution, career and field weighting. | `hf_index`: fractional raw citations `c_p/N_p`, h-th largest ≥ h; **no** NM weights. Real input is gated pending verified full coauthor counts. |
| hm | `Hm′_a`, Eqs. 18–20: career × contribution effective rank and field aggregation. | Conventional `hm_index` is unresolved and remains null by default. |
| g | `G′_a`, Eqs. 21–23: effective adjusted citations and field aggregation. | `g_index`: raw top-g-paper cumulative rule; five-paper manuscript example conflict is documented separately. |

Code boundaries: `nm_index.loader` reads the target and percentile columns, `src.repository` maps stored raw component tables to `nm_raw_*`, `src.validation_dataset` merges these under their separate names, and only `metrics/*` modules populate conventional baseline columns. `src/pipeline` calculates conventional hf for the declared-complete **synthetic fixture only**; real ten-slot authorship cannot prove complete `N_p`. No NM component is used to fill a missing baseline.
