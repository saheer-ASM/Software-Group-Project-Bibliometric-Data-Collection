# Assumption and methodology-decision register

This register originated in the Phase 4.5 read-only audit. Phase 5A has since
run synthetic baseline calculations, but no real-author metric or NM
recalculation. Earlier descriptive counts remain historical. Source support is from the
[latest design](../source_documents/Pasted%20markdown%287%29.md),
[latest manuscript](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf)
and [database input map](validation_database_input_map.csv).

| Assumption or decision | Reason / source support | Effect on result | Avoidable? | Future methodology confirmation? |
|---|---|---|---|---|
| Use `author.author_id` and `publication.pub_id` as stable join keys. | Current schema and application joins use IDs; author names are not stable identifiers. | Prevents name collisions and wrong paper attribution. | No practical alternative for reliable join. | No, unless source schema changes. |
| Treat the ten-slot `author_contribution_weight` table as the observed author-publication link, not a verified full portfolio. | Application uses this link; only 816 of 56,768 publications and 2,340 of 2,507 authors are covered. | Any conventional baseline would be limited to observed linked papers. | Yes, by obtaining a complete authoritative authorship source. | **Yes** before full-cohort baseline claims. |
| Do not silently convert an author with no linked papers to zero. | The link table misses 167 authors; zero would imply known absence of publications. | Provisional input preparation yields NULL for these authors. | Yes, if complete negative evidence is supplied. | **Yes** for final-cohort policy. |
| Use `publication.total_citation` as candidate raw stored total, not `author_total_cites.total_cites_score`. | Design defines raw sum; manuscript Eq. 11 shows latter is a normalized, weighted NM component. | Prevents mixing baseline and NM units. | No for component distinction; raw-source selection can change. | **Yes** for raw citation provenance. |
| Do not replace stored publication totals with counts from `citation` edges. | 16 of 37 sampled IDs disagree; edges may be partial. | Raw baseline remains pending a source-of-truth decision. | Yes, by documenting origin/completeness of both representations. | **Yes**. |
| Deduplicate repeated publication-author links locally and invalidate conflicting paper totals. | Provisional `metrics/inputs.py` avoids double counting; current tables show zero duplicate key excess but future runs may differ. | One observed paper counted once; conflicts become NULL. | Yes, with unique source constraints and complete provenance. | Yes, for final handling. |
| Missing/negative/noninteger citation tally is invalid rather than zero. | Raw citations are counts; design has no imputation rule. Current `publication.total_citation` has no NULL, but future data may. | Prevents understated results; provisional portfolio becomes NULL if a linked count is unresolved. | Yes, if corrected source data arrives. | Yes, for final missing-data policy. |
| Conventional g ranges over observed papers only. | Latest manuscript p. 2 says “top g papers” but its five-paper example reports g=12. | Implemented written rule restricts output to at most paper count; example conflict remains. | Yes, by explicit ruling on an extension. | **Yes — REQUIRES METHODOLOGY DECISION for the example.** |
| Conventional hm interpretation. | Design says harmonic; manuscript describes 1/N effective rank. | Could change score materially. | Yes, with the intended reference formula. | **Yes — REQUIRES METHODOLOGY DECISION.** |
| Conventional hf weighting. | Latest manuscript pp. 22-25 specifies uniform `1/N_p` fractional citations and h-th-paper threshold; design's contribution-weighted label is secondary. | Source-grounded synthetic hf is calculable; real output is gated until full coauthor counts are verified. | Formula conflict resolved by primary-source rule; missing input remains. | **No formula decision; yes for real coauthor completeness.** |
| m-index career years/as-of date and zero-year policy. | Documents specify h/t but not those operational choices. | Changes m values; t=0 otherwise undefined. | Yes, with a fixed analysis date and rule. | **Yes**. |
| Raw and SC-adjusted C-score reference distribution and adjustments. | Latest manuscript offers examples, not complete composite construction or C-score SC rule. | No faithful score can be produced. | Yes, with cited method specifications and appropriate reference data. | **Yes**. |
| s-index identity and formula. | Design names s-index but manuscript cites Brown's b-index publication. | Comparator may be mislabeled. | Yes, by confirming intended index/source. | **Yes — REQUIRES METHODOLOGY DECISION.** |
| Fi-score threshold and AR age formula. | Neither source supplies complete rules. | Both baselines remain unavailable. | Yes, with approved methods. | **Yes**. |
| Distinguish stored NM component scores from `per_*` percentiles. | `author_nm_index` stores the six percentile columns and `metrics_available`; raw components live in separate tables. | Prevents running PCA or comparisons on mislabeled values later. | No; this is a necessary data distinction. | No, but Phase 5 must choose which level each experiment requires. |
| Do not infer NM's missing-component weighting policy from Eq. 27. | Manuscript uses six weights; 784 stored scored authors have fewer than six components in Phase 3 snapshot. | Stored NM may not be directly reconstructable from visible six percentiles; no recomputation is authorized. | Yes, by reading production methodology/code for provenance in a later approved audit. | **Yes** before interpreting completeness. |
| Read a fixed extract batch within one read-only repeatable-read transaction. | Current `execute_select_batch` supports this; older Phase 2 audits used separate SELECT transactions. | Data extracts share a consistent snapshot. | Already implemented for the validation loader. | Verify source completeness separately. |
| Pilot does not represent the intended 100,000-author stratified cohort. | Design and manuscript specify 100,000 profiles/334 fields; current database has 2,507 authors. | Pilot coverage cannot establish empirical validation or fairness. | Yes, with final data acquisition. | Yes before Phase 5 study interpretation. |

For source conflicts unrelated to implemented calculations (RQ numbering,
manuscript outlier treatment and inconsistent example values), see
[source_consistency_audit.md](source_consistency_audit.md). No assumptions were
silently adopted to resolve them.
