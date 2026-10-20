# Phase 4.5 citation semantics audit

Read-only inspection on 2026-10-04. In `citation`, `pub_id` is the **cited** paper and `cites_pub_id` the **citing** paper. Both sides resolve to `publication.pub_id` for every observed edge. `publication.total_citation` is a stored publication-level count; neither schema nor supplied source documents establish the import time, upstream source, or counting rule for that stored value. These are different data products, not proven equivalents.

The citation table contains 52,370 rows and 52,370 unique `(pub_id,cites_pub_id)` pairs: no duplicate edges were observed. It covers 1,496 distinct cited papers and 47,029 distinct citing papers. Across all 56,768 publication rows, stored total equals cited-edge count for 8,603 papers, exceeds it for 48,146, and is below it for 19. **48,056 papers have a positive stored total but zero cited edges**; one has stored zero and a positive edge count. The sum of stored paper totals is 2,585,166 versus 52,370 observed cited edges. These comparisons are data-quality diagnostics, not author metrics.

| Publication ID | Stored `total_citation` | Rows citing this paper | Difference (stored − edges) | Observed explanation |
|---|---:|---:|---:|---|
| `W1182682356` | 2,645 | 200 | 2,445 | Edge table includes only a fraction of the stored count. |
| `W1054753857` | 39 | 38 | 1 | One-count discrepancy; no duplicate pair explains it. |
| `W1981182823` | 65 | 65 | 0 | Representations agree for this paper. |
| `W3013815164` | 26 | 0 | 26 | No inbound edge recorded despite positive stored total. |
| `W1750736927` | 0 | 1 | −1 | Edge exists despite zero stored count. |
| `W1634434013` | 12 | 13 | −1 | Edge count exceeds stored count. |

The prior deterministic 37-ID audit found 16 mismatches ([sample CSV](citation_semantics_sample.csv)); the whole-table comparison confirms the issue is widespread. The cited/citing orientation is not the explanation: using `cites_pub_id` counts outgoing references, not citations received. Duplicate edge rows are not the explanation. The empty UUID `citations` table cannot fill gaps. `influential_self_citations` holds 9,792 *derived NM adjustment* rows for 90 cited papers/143 target authors; it is not a complete conventional self-citation flag across all 52,370 edges. The latest manuscript's synthetic example assumes no self-citations but does not define these database counts.

**What remains unproved:** an incomplete import of citation edges, different source snapshots, different external-provider count definitions, and self-citation exclusion are plausible, but no source timestamps/provenance or complete edge-level self-citation labels were found to distinguish them. The 19 reverse discrepancies show that even a blanket “stored count contains all edges” rule is false for some papers. Do not claim an exact cause from the present evidence.

**Recommended provisional source for conventional raw citation-count baselines:** `publication.total_citation`, because it is available for every publication and the edge table covers only 1,496 cited papers. Label it explicitly as the *stored publication count* and obtain source provenance/definition before treating it as fully reliable or comparing to a different citation universe. Do not sum edge rows as a replacement, treat absent edges as zero, or use `author_total_cites.total_cites_score` (an NM component) as raw Total Cites. Self-citation-adjusted baselines require a separate complete attribution rule and data source.
