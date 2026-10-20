# NM target, NM components, and conventional baselines

The [latest manuscript](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf) §2 Equations 11–27 defines six weighted, normalized NM components and their final percentile aggregate. The [experiment design](../source_documents/Pasted%20markdown%287%29.md) baseline table separately names 11 **conventional** comparators. `nm_index/loader.py` reads the existing `author_nm_index.nm_index`; the validation project never recalculates or updates it.

| Quantity | Validation column and source | Never substitute with |
|---|---|---|
| Final NM-index | `nm_index` from `author_nm_index.nm_index` | A local average of six stored components or percentiles |
| Conventional raw Total Cites | `raw_total_cites`, sum of complete linked `publication.total_citation` counts | `author_total_cites.total_cites_score` (NM Eq. 11) |
| Conventional h | `h_index`, raw sorted citation counts | Modified hf or hm |
| Conventional g | `g_index`, written raw top-g-papers rule | `modified_g_index_results.modified_g_index` or `author.modified_g_index` |
| Conventional hf and hm | `hf_index` uses verified `c_p/N_p` fractional citations (synthetic only until real coauthor completeness is proven); `hm_index` remains methodology-pending | `author_modified_hindex.modified_hindex_final` and `author.modified_hm_index` |
| NM component scores for RQ10 | `nm_raw_t/s/u/hf/hm/g`, loaded from six existing component sources | The six `author_nm_index.per_*` percentile columns |

`src/metric_registry.py` and `src/provenance.py` assign distinct names and source references; `src/validation_dataset.py` preserves separate columns. Synthetic tests assert the target comes from the stored record and that unavailable comparators remain NULL. The existing data's incomplete author-paper links and citation-source disagreement still block real-cohort interpretation.
