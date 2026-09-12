# Nm_index_step_by_step

A separate, explicit, one-step-at-a-time walkthrough of the Nm-index
final stage (paper Eq. 24-27), built alongside `final_nm_index/` (the
production module). **`final_nm_index/` is not touched by this
module** -- it was only read, read-only, to confirm which DB tables
hold the six component metrics.

Each metric gets its own file, done one at a time. **All six component
metrics are now implemented: `T_a`, `S_a`, `U_a` (the citation-metric/
log group) and `Hf'_a`, `Hm'_a`, `G'_a` (rank metrics, no log
transform).** Only the final Eq. 27 weighted average across the six
`Per_*` columns remains.

```
Nm_index_step_by_step/
├── __init__.py
├── config.py            # DB table/column map + step constants
├── database.py          # PostgreSQL connection (.env-based, same as final_nm_index)
├── build_dataset.py     # Step 1: author_id, T_a, S_a, U_a, Hf_a, Hm_a, G_a
├── step_T_a.py           # Steps 2-5: process T_a -> L_T, rank_T, P_T, Nor_T, Per_T
├── step_S_a.py           # Steps 2-5: process S_a -> L_S, rank_S, P_S, Nor_S, Per_S
├── step_U_a.py           # Steps 2-5: process U_a -> L_U, rank_U, P_U, Nor_U, Per_U
├── step_Hf_a.py           # Steps 3-6: process Hf_a -> rank_Hf, P_Hf, Nor_Hf, Per_Hf (no log, fractional rank)
├── step_Hm_a.py           # Steps 3-6: process Hm_a -> rank_Hm, P_Hm, Nor_Hm, Per_Hm (no log, fractional rank)
├── step_G_a.py            # Steps 3-6: process G_a  -> rank_G,  P_G,  Nor_G,  Per_G  (no log, fractional rank)
├── run_step_T_a.py       # demo / verification run for T_a (read-only, no writes)
├── run_step_S_a.py       # demo / verification run for S_a (read-only, no writes)
├── run_step_U_a.py       # demo / verification run for U_a (read-only, no writes)
├── run_step_Hf_a.py       # demo / verification run for Hf_a (read-only, no writes)
├── run_step_Hm_a.py       # demo / verification run for Hm_a (read-only, no writes)
├── run_step_G_a.py        # demo / verification run for G_a (read-only, no writes)
├── test_step_T_a.py      # tests against the hand-worked examples
├── test_step_S_a.py      # same shape of tests, for S_a
├── test_step_U_a.py      # same shape of tests, for U_a
├── test_step_Hf_a.py      # same shape of tests, for Hf_a
├── test_step_Hm_a.py      # same shape of tests, for Hm_a
├── test_step_G_a.py       # same shape of tests, for G_a
└── requirements.txt
```

## Step 1 -- `build_dataset.py`

`build_author_metric_dataset(connection)` returns one row per author:

```
author_id   T_a     S_a     U_a     Hf_a    Hm_a    G_a
A001        12.4    3.2     1.4     4.2     3.7     5.1
A002        0.0     0.0     0.0     0.0     0.0     0.0
A003        5.8     2.1     0.9     2.5     2.1     3.0
```

(`Hf_a` / `Hm_a` / `G_a` stand for `Hf'_a` / `Hm'_a` / `G'_a` -- the
prime just isn't a legal identifier.)

Nothing here recomputes citations, h-index, hm-index, or g-index --
these six columns are read as-is from the already-computed source
tables (same ones `final_nm_index/config.py` maps):

| Column | Source |
|---|---|
| `T_a` | `author_total_cites.total_cites_score` |
| `S_a` | `author_citations_per_paper.citations_per_paper_score` |
| `U_a` | `author_citation_rate.citation_rate_score` |
| `Hf_a` | `author_modified_hindex.modified_hindex_final` |
| `Hm_a` | `author.modified_hm_index` |
| `G_a` | `author.modified_g_index` |

A metric that is `NULL` upstream for a given author stays `NaN` in the
output -- it is never filled with `0`.

## Steps 2-5 -- `step_T_a.py`, `step_S_a.py`, `step_U_a.py`

`process_T_a(dataset)` / `process_S_a(dataset)` / `process_U_a(dataset)`
each append six columns for their metric (`T`, `S`, or `U`), identical
recipe:

```
T_a -> L_T -> rank_T -> (N_T) -> P_T -> Nor_T -> Per_T
S_a -> L_S -> rank_S -> (N_S) -> P_S -> Nor_S -> Per_S
U_a -> L_U -> rank_U -> (N_U) -> P_U -> Nor_U -> Per_U
```

1. **Step 2 (log transform):** `L = log10(x + 1)`
2. **Step 3 (rank):** `rank = L.rank(method="min")` -- "normal"
   (competition) ranking, per the paper's Eq. 24 wording for raw
   citations. Tied values (mostly the large `x = 0` block) share the
   lower rank.
3. **Step 4 (Blom plotting position):** `P = (rank - 0.375) / (N + 0.25)`,
   `N` = number of authors with a non-null value for that metric.
4. **Step 5 (percentile):** `Nor = Φ⁻¹(P)` then `Per = 100·Φ(Nor)`,
   computed explicitly via `scipy.stats.norm.ppf` / `.cdf` to reproduce
   Eq. 25 literally, rather than jumping straight to the algebraic
   shortcut `Per = 100·P` (which it is always numerically equal to,
   since `Φ(Φ⁻¹(P)) ≡ P` -- verified in the test files).

An author with a `NULL` value gets `NaN` in every one of these columns
for that metric and is excluded from `N` and from the ranking --
**never** treated as `0`.

## Step 3-6 (no log, fractional rank) -- `step_Hf_a.py`, `step_Hm_a.py`, `step_G_a.py`

`process_Hf_a(dataset)` / `process_Hm_a(dataset)` / `process_G_a(dataset)`
follow the identical percentile framework but **skip the log-transform
step** -- `Hf'_a` / `Hm'_a` / `G'_a` are already small, index-shaped
numbers with many ties, not raw skewed citation counts, so Eq. 24
ranks the raw value directly:

```
Hf_a -> rank_Hf -> (N_Hf) -> P_Hf -> Nor_Hf -> Per_Hf
Hm_a -> rank_Hm -> (N_Hm) -> P_Hm -> Nor_Hm -> Per_Hm
G_a  -> rank_G  -> (N_G)  -> P_G  -> Nor_G  -> Per_G
```

Same Step 4 (Blom), Step 5/6 (explicit `norm.ppf` / `norm.cdf` round
trip) as the citation metrics -- but Step 3 uses **fractional**
(`"average"`) ranking here, not `"min"`: Eq. 24 says *"fractional
ranking ... for the hm, hf, g indices (as they contain many ties) ...
and normal ranking for the raw citations"* -- so `Hf_a`/`Hm_a`/`G_a`
use `config.RANK_METHOD_RANK = "average"` while `T_a`/`S_a`/`U_a` keep
`config.RANK_METHOD = "min"`. A tied pair now splits its rank evenly
(e.g. two ties at positions 1-2 both get rank `1.5`) instead of both
taking the lower rank.

Real-DB dry run (`run_step_T_a.py` / `run_step_S_a.py` / `run_step_U_a.py`
/ `run_step_Hf_a.py` / `run_step_Hm_a.py` / `run_step_G_a.py`, read-only):

| Metric | ranking | N (non-null) | Per median | Per max |
|---|---|---|---|---|
| `T_a` | min | 1561 | 0.040 | 99.960 |
| `S_a` | min | 2321 | 0.027 | 99.973 |
| `U_a` | min | 2321 | 0.027 | 99.973 |
| `Hf_a` | average (fractional) | 2143 | 49.533 | 99.971 |
| `Hm_a` | average (fractional) | 2254 | 48.292 | 99.972 |
| `G_a` | average (fractional) | 2143 | 49.533 | 99.971 |

The ranking method changes everything about where the tied block
lands: under `"min"` (T/S/U) the ~95% tied-at-zero block sits at rank 1
-> near the 0th percentile. Under `"average"` (Hf, Hm, G) that same
kind of tied block instead sits at its *average* rank across the whole
tie -> here, rank ≈1062/2143 for Hf and G, ≈1089/2254 for Hm -> `Per ≈
48-50`, right in the middle. Same underlying zero-inflation, very
different-looking output -- purely a consequence of which ranking
method the metric uses, not of the data being different in kind.

**`Hf_a` and `G_a` produce identical `N` and an identical `Per`
distribution shape** on the real data (same 2143 non-null authors,
same tie-block boundary at rank 1062). That means the same set of
authors is zero-valued in both -- worth a quick sanity check against
the source pipelines if that surprises you, but it is a property of
the real DB content, not of this module (this module only reads
`author_modified_hindex.modified_hindex_final` and
`author.modified_g_index` as given).

## All six components -- what's left

With `step_T_a.py` through `step_G_a.py` in place, every author now has
(up to) six `Per_*` columns: `Per_T`, `Per_S`, `Per_U`, `Per_Hf`,
`Per_Hm`, `Per_G`. The only remaining step is Eq. 27's weighted
average across them (`Nm_a = Σ w_i · Per_a(x_i)`, default `w_i = 1/6`),
with the same missing-metric renormalisation policy documented in
`final_nm_index/` -- not yet built here.

## Run it

```bash
pip install -r Nm_index_step_by_step/requirements.txt
python -m pytest Nm_index_step_by_step/ -v                      # no DB needed
python -m Nm_index_step_by_step.run_step_T_a                    # reads the DB, read-only
python -m Nm_index_step_by_step.run_step_S_a                    # reads the DB, read-only
python -m Nm_index_step_by_step.run_step_U_a                    # reads the DB, read-only
python -m Nm_index_step_by_step.run_step_Hf_a                   # reads the DB, read-only
python -m Nm_index_step_by_step.run_step_Hm_a                   # reads the DB, read-only
python -m Nm_index_step_by_step.run_step_G_a                    # reads the DB, read-only
```

## Relationship to `final_nm_index/`

Same six source tables, same Eq. 24-27 maths, same defaults (`"min"`
ranking, Blom `a = 0.375`, hooked-power-law percentile collapsing to
`100·P`). The difference is presentation: `final_nm_index/` computes
all six metrics through one generic `NmIndexCalculator`; this module
spells out each metric's own file and every intermediate column
(`L_T`, `rank_T`, `N_T`, `P_T`, `Nor_T`) for inspection, one metric at
a time.
