# NM components versus conventional validation baselines

Sources: latest [experiment design](../source_documents/Pasted%20markdown%287%29.md),
latest [manuscript](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf),
and [read-only input map](validation_database_input_map.csv).

| NM model component (read stored only) | Authoritative existing column | Conventional baseline or comparator | Why the values differ |
|---|---|---|---|
| `T_a`, weighted normalized total cites | `author_total_cites.total_cites_score`; percentile `author_nm_index.per_total_cites` | Total Cites: sum of raw `publication.total_citation` over an author's linked papers | NM Eq. 11 uses ISC-adjusted credits, author and field weights, field/year mean normalization and career factor. The numeric `total_cites_score` is not a raw citation count. |
| `S_a`, weighted normalized citations per paper | `author_citations_per_paper.citations_per_paper_score`; percentile `per_citations_per_paper` | No identically named required conventional baseline | NM Eqs. 12–13 add cap, contribution, field and career adjustments. |
| `U_a`, weighted normalized citation rate | `author_citation_rate.citation_rate_score`; percentile `per_citation_rate` | AR-index is an age-weighted comparator; m-index is h/career years | NM Eq. 14 uses capped ISC-adjusted credits, field/year means, paper age and career factor. Neither comparator is defined by this stored score. |
| `Hf′_a`, modified hf | `author_modified_hindex.modified_hindex_final`; percentile `per_modified_hf_index` | hf-index | NM Eqs. 15–17 use adjusted effective citations and field normalization. Design's contribution-weighted hf wording also conflicts with manuscript's uniform-share original comparator. |
| `Hm′_a`, modified hm | `author.modified_hm_index`; percentile `per_modified_hm_index` | hm-index | NM Eqs. 18–20 use career/contribution-adjusted effective rank; the conventional rank rule is not the same. |
| `G′_a`, modified g | `modified_g_index_results.modified_g_index`; percentile `per_modified_g_index` | g-index | NM Eqs. 21–23 use adjusted effective field citations and normalization; conventional g uses raw paper citation totals. `author.modified_g_index` is an additional mirror, not a baseline. |

`author_nm_index.nm_index` is the authoritative final stored NM-index result.
Its key is `author_id`; six `per_*` columns are the stored component
**percentiles**, not the pre-percentile component values; `metrics_available`
counts available components and `calculated_at` is the calculation timestamp.
There is no separate boolean completeness/status column in this table. The
current audit found 2,507 rows, no duplicate author keys, 2,321 non-NULL
NM results and 186 NULL results. The `author.nm_index` mirror is NULL in all
2,507 current author rows and must not be used.

## Citation representation and authorship link

`publication.total_citation` is a stored integer citation tally on a
publication row (56,768 rows, currently no NULL tally). `citation` contains
52,370 directed paper-to-paper edges: `citation.pub_id` is the **cited**
publication, `citation.cites_pub_id` the **citing** publication. This direction
is supported by the production application's read-only source inspection and
the current sample. In a 37-ID deterministic sample, 21 stored totals matched
counts where the ID was the cited paper and 16 did not. For example, one
sampled stored total was 2,645 while 200 matching citation edges were present.
Therefore the edge table is not a proven complete reconstruction of the stored
total; provenance and scope need a methodology decision. This audit does not
choose a count source for calculations.

The production application joins `publication.pub_id` to
`author_contribution_weight.pub_id` and checks the stable author ID against
`author1id`–`author10id`; it does not join by names. The current database has
816 such unique contribution rows, all referring to existing publications;
the ten slots link 2,340 distinct IDs in `author`, leaving 167 author records
without a link in that table. Six contribution rows fill all ten slots, so
larger author lists cannot be ruled out. This wide table is the current
application's author-publication lookup, **not** a verified complete normalized
authorship relation or full portfolio export. Raw baselines would be values
for the observed linked set only unless complete portfolios are obtained.

`author_paper_adjusted_citations.total_raw_citation` and
`total_adjusted_citation` are paper-author NM aggregates and can be
fractional. `influential_self_citations` is a paper-to-paper-author-field
adjustment. Neither is an interchangeable source for traditional raw
publication counts or C-score self-citation adjustment.

The [baseline audit](latest_baseline_audit.csv) gives per-comparator readiness,
and [source consistency audit](source_consistency_audit.md) records the
unresolved manuscript/design differences. No NM components or baseline
metrics were calculated for this audit.
