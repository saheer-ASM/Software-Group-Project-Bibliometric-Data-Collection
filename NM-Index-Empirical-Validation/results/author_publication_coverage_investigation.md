# Phase 4.5 author–publication coverage investigation

Read-only database inspection on 2026-10-04. All counts are from the live `public` schema. `author.author_id` (`A…` strings) and `publication.pub_id` (`W…` strings) are the NM-pipeline keys. The relationship probe and its exact SELECT statements are in [`src/investigate_phase4_5.py`](../src/investigate_phase4_5.py); detailed counts are in [publication_coverage_diagnostics.csv](publication_coverage_diagnostics.csv).

| Candidate | Rows | Distinct author–paper pairs | Distinct authors | Distinct papers | Pairs beyond contribution table | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| `author_contribution_weight`, ten ID slots | 816 | 3,065 | 2,340 | 816 | 0 | Only populated direct authorship source for NM-pipeline IDs. 3,070 filled slots contain five repeated author–paper pairs; deduplicate by stable IDs. |
| `author_paper_field_effective_citation` | 9,129 | 3,043 | 2,321 | 811 | 0 | Derived field-granularity calculation; 6,086 repeated pairs across fields. |
| `total_cites_equation_11_details` | 9,129 | 3,043 | 2,321 | 811 | 0 | Derived field-granularity calculation. |
| `total_cites_equation_11_details_with_score` | 9,129 | 3,043 | 2,321 | 811 | 0 | Derived field-granularity calculation. |
| `citations_per_paper_details` | 9,129 | 3,043 | 2,321 | 811 | 0 | Derived field-granularity calculation. |
| `citation_rate_details` | 9,129 | 3,043 | 2,321 | 811 | 0 | Derived field-granularity calculation. |
| `author_paper_adjusted_citations` and `equation_9_adjusted_citations` | 302 each | 302 each | 143 | 90 | 0 | Derived paper–target-author citation credits, not comprehensive authorship. |
| `influential_self_citations` | 9,792 | 302 | 143 | 90 | 0 | Citation events at a finer grain; 9,490 excess repeated paper–target-author pairs. |
| `modified_g_index_paper_details`, `eq15_effective_citations` | 0 each | 0 | 0 | 0 | 0 | Empty. |
| `author_publications` UUID junction | 0 | 0 | 0 | 0 | 0 | Empty parallel schema; `authors`, `publications`, `citations`, and `author_metrics` are also empty. UUID keys cannot be joined to the populated string-ID cohort. |

The `publication` table itself has no author identifier or author-list column. `field_classification`, `publication_fields`, and `citation` contain publication IDs but do not establish authorship. Author-level NM/metric tables contain author IDs but no publication IDs. The populated derived paper–author tables add **zero** pairs or papers beyond `author_contribution_weight`; the union of all populated string-ID candidates remains 3,065 distinct pairs, 816 papers and 2,340 authors. Their exact overlap with the contribution source is shown in the diagnostic CSV. Names are not stable join keys and were not used.

Of 56,768 publication rows, **55,952 have no author relationship** in any populated candidate (98.56%). Of 2,507 authors, **167 have no linked publication** (6.66%). The 816 linked papers and 3,065 distinct pairs have no orphan author or paper IDs. The current extraction is not missing another populated junction; it reads an intrinsically small source table. Six contribution rows fill all ten author slots, so the schema alone cannot prove that papers with more than ten authors are represented completely. The five repeated pairs within filled slots must be deduplicated. `publication.pub_id` and contribution `pub_id` share the same string-ID family and all 816 join; the separate UUID schema is empty, not an alternate route to the 56,768 papers.

**Recommendation:** Use `author_contribution_weight` as the authoritative *observed* author–paper link for this database, unpivot its ten slots and deduplicate `(author_id,pub_id)`. It does not establish complete career portfolios or prove complete coauthor lists. Do not infer missing papers by author name, derive authorship from citation events, or treat the 55,952 unlinked papers as authorless. Full-cohort baseline calculations require a verified complete authorship source or an explicitly restricted and labelled cohort, with completeness evidence independent of this table.
