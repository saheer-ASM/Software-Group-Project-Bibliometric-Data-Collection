# Phase 4.5 stored NM-index coverage

Read-only comparison of `author_nm_index` with authoritative `author` on 2026-10-04. No NM values or components were recalculated.

| Check | Count |
|---|---:|
| Authors in `author` | 2,507 |
| Rows in `author_nm_index` | 2,507 |
| Unique matched author IDs | 2,507 |
| Authors with no NM row | 0 |
| Orphan NM rows | 0 |
| Duplicate NM author rows | 0 |
| Non-NULL `nm_index` | 2,321 |
| NULL `nm_index` | 186 |
| Rows missing at least one of six stored component percentiles | 970 |
| Non-NULL final scores with incomplete component percentiles | 784 |
| `metrics_available` disagrees with count of non-NULL percentile columns | 0 |

`metrics_available` distribution: 0 components: 186 authors; 2: 67; 3: 87; 4: 24; 5: 606; 6: 1,537. The 186 NULL final scores are **present records**, not missing records. All 186 have zero available component percentiles. A non-NULL stored final score therefore does **not** imply all six component percentiles are present: 784 scored authors have incomplete coverage. The authoritative result is `author_nm_index.nm_index`; `author.nm_index` is a separate mirror and was not used. The six `per_*` fields are stored percentiles, distinct from raw component scores in other tables. The manuscript describes a six-component weighted index, but this audit does not infer how the existing application handled missing components when producing stored scores. For a strict six-component pilot, only the 1,537 complete-component rows are candidate records, subject to other data checks and an explicit cohort decision.
