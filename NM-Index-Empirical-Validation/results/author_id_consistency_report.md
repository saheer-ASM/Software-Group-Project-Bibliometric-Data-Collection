# Phase 4.5 author-ID consistency

Read-only live inspection on 2026-10-04. The populated `author` table has **2,507 unique non-NULL IDs**, all beginning `A`; no leading/trailing whitespace or case-only variants were observed. `author_contribution_weight` has 3,070 filled author slots and 3,065 unique author–paper pairs: the five repeated pairs are within the wide relationship data, not duplicate author records. Its 2,340 unique author IDs all resolve to `author.author_id`.

| Source family | Rows or distinct pairs | Unique author IDs | NULL IDs | Orphan IDs | Format/duplication finding |
|---|---:|---:|---:|---:|---|
| `author` | 2,507 rows | 2,507 | 0 | — | No duplicate author key, whitespace, or case variant. |
| `author_nm_index` | 2,507 rows | 2,507 | 0 | 0 | One row per authoritative author; no duplicate key. |
| `author_total_cites`, `author_citations_per_paper`, `author_citation_rate` | 2,321 rows each | 2,321 each | 0 | 0 | One row per represented author. |
| `author_modified_hindex` | 2,340 rows | 2,340 | 0 | 0 | One row per represented author. |
| `modified_g_index_results` | 2,143 rows | 2,143 | 0 | 0 | One row per represented author. |
| `author_field_modified_hindex` | 7,187 rows | 2,270 | 0 | 0 | Repeated author IDs reflect the author × field grain; not duplicate author records. |
| Main author–paper relation | 3,065 distinct pairs | 2,340 | 0 filled-slot NULLs | 0 | Five extra filled slots repeat existing pairs. Empty slots are expected NULLs, not bad author keys. |
| Derived field-paper tables | 3,043 distinct pairs each | 2,321 | 0 | 0 | Repeated IDs reflect author × paper × field rows; all pairs within main relation. |
| NM adjusted/self-citation sources | 302 distinct target-author/paper pairs each | 143 | 0 | 0 | All pairs within main relation; event rows are finer grain. |
| UUID `authors`, `author_publications`, `author_metrics` | 0 | 0 | 0 | 0 | Empty separate ID namespace; cannot bridge to `A…` IDs. |

The `equation_11_total_cites`, `equation_13_citations_per_paper`, and `equation_14_citation_rate` author-level mirrors each contain 2,321 non-orphan unique IDs; `modified_g_index_field_results` is empty. All inspected populated author-ID sources use the same `A…` prefix and had no whitespace or case-only variants. The citation-edge table has publication IDs only, no direct author ID. `influential_self_citations.target_author_id` is a *target for adjusted credit*, not a general author-list key. The empty UUID schema has a structurally different ID type but no rows to map.

**Conclusion:** observed populated author IDs are internally consistent. The blocker is absent author–paper coverage, not a broad ID-format mismatch. Repeated author IDs in field/event tables must be interpreted at their table grain; counting them as duplicate author records would be erroneous. No IDs were changed.
