# final_nm_index

Implements the **final Nm-index** (Nilmantha's index) — the last stage
of the Nm-index model from the paper *"Nm Index: A Percentile Score by
Considering Author Contribution, Ordering, Influential Self Citation,
Career Stage, and Domain Norms…"*.

This module implements **only Eq. 24–27** (paper §2.5 "Final score";
Eq. 23–25 in the extended abstract):

| Step | Eq. | What it does |
|---|---|---|
| `Tra_a(x)` | 24 | transform each raw component metric |
| `Nor_a(x)` | 25 | normalise the transformed value |
| `Per_a(x)` | 26 | map to a 0–100 percentile |
| `Nm_a` | 27 | weighted average of the six percentiles |

Everything **before** Eq. 24 (author contribution & ordering weights
Eq. 1–6, influential self-citation Eq. 7–9, career factor Eq. 10, and
the six component metrics themselves Eq. 11–23) is already computed by
other pipelines in this repo and stored in PostgreSQL. This module
reads those stored values and does not recompute them.

```
final_nm_index/
├── __init__.py
├── config.py            # table/column maps, weights, distribution assumptions
├── database.py          # PostgreSQL connection (.env-based, identical to modified_hm_index)
├── calculator.py        # Eq. 24–27, pure pandas/numpy/scipy, no DB
├── run_calculation.py   # load 6 metrics → calculate → write results
├── schema.sql           # run ONCE to create the output table
├── test_calculator.py   # hand-derived regression tests, no DB
└── requirements.txt
```

> The folder is named `final_nm_index` (underscores), not "final Nm
> index", because `python -m` cannot import a package whose name
> contains spaces. This matches the `modified_hm_index` sibling.

---

## Quick start

```bash
pip install -r "final_nm_index/requirements.txt"

# 1. one-time: create the output table (and optional author.nm_index column)
psql "$DATABASE_URL" -f "final_nm_index/schema.sql"

# 2. run tests (no DB needed)
python -m pytest "final_nm_index/test_calculator.py" -v

# 3. run the calculation (reads + writes the DB)
python -m final_nm_index.run_calculation
```

Run from the **repo root** so `final_nm_index` is importable as a package.

---

## The six component metrics (x1…x6)

| # | Symbol | Meaning | Source table | Source column |
|---|---|---|---|---|
| x1 | `T_a`   | outlier-**un**controlled WFYN total cites (Eq. 11) | `author_total_cites` | `total_cites_score` |
| x2 | `S_a`   | outlier-controlled WFYN cites per paper (Eq. 13)   | `author_citations_per_paper` | `citations_per_paper_score` |
| x3 | `U_a`   | outlier-controlled WFYN citation rate (Eq. 14)     | `author_citation_rate` | `citation_rate_score` |
| x4 | `Hf'_a` | modified hf-index (Eq. 17)                         | `author_modified_hindex` | `modified_hindex_final` |
| x5 | `Hm'_a` | modified hm-index (Eq. 20)                         | `author` | `modified_hm_index` |
| x6 | `G'_a`  | modified g-index (Eq. 23)                          | `modified_g_index_results` | `modified_g_index` |

All six are keyed on `author_id`, one row per author. The full author
universe is taken from the `author` table.

These mappings live in `config.METRIC_SOURCES` — change them there if a
table/column is renamed, or to point `total_cites` at the equivalent
`equation_11_total_cites` table instead.

### ⚠️ Current DB state (checked 2026-08-31)

| Metric | Authors with a value | Note |
|---|---|---|
| `total_cites` | 1561 / 2507 | ~760 rows still `NULL` upstream |
| `citations_per_paper` | 2321 / 2507 | |
| `citation_rate` | 2321 / 2507 | |
| `modified_hf_index` | 2143 / 2507 | 197 authors `NO_ELIGIBLE_FIELDS` |
| `modified_hm_index` | 2254 / 2507 | |
| **`modified_g_index`** | **0 / 2507** | **table is empty — the modified g-index pipeline has not been run** |

Because `modified_g_index_results` is empty, **every author currently
scores on ≤ 5 of the 6 metrics.** The Nm-index is still produced (see
"Missing-metric policy" below); once the g-index pipeline populates its
table, re-running this module picks it up automatically with no code
change.

The per-table `calculation_complete` / `calculation_status` flags were
found to be unreliable (mostly `False` / not `READY` even for rows
holding a valid score), so by default we filter on `value IS NOT NULL`
only. Set `config.NM_FILTER_STATUS = True` to also honour them.

---

## The maths (what `calculator.py` actually does)

Two metric families, handled differently (Eq. 24):

### Log metrics — `T_a`, `S_a`, `U_a`

1. **Eq. 24** `L(x) = log10(x + 1)`
2. **Eq. 25**, per `config.NM_DISTRIBUTION[metric]`:
   * `"hooked"` *(default)* → `Nor(x) = Φ⁻¹( P(L(x)) )` (rank-based inverse normal),
     with `P` the Blom plotting position and **normal / competition ranking**
     (`RANK_METHOD_LOG = "min"`)
   * `"lognormal"` → `Nor(x) = ( L(x) − mean L(x) ) / std L(x)` (population std, ddof=0)
3. **Eq. 26** `Per(x) = 100 · Φ( Nor(x) )`
   * for `"hooked"` this reduces exactly to `100 · P(L(x))`

### Rank metrics — `Hf'_a`, `Hm'_a`, `G'_a`

1. **Eq. 24** `P(x) = (r(x) − 0.375) / (N + 0.25)` — the **Blom plotting
   position** on the **fractional rank** `r(x)` (ties → average rank,
   `RANK_METHOD_RANK = "average"`).
   `N` = number of authors with a non-null value for that metric
   (or `config.NM_REFERENCE_N` if set).
2. **Eq. 25** `Nor(x) = Φ⁻¹( P(x) )`
3. **Eq. 26** `Per(x) = 100 · P(x)`

This is exactly the recipe spelled out in **paper §3.3.3 "Final Nm-Index
Calculation"** (the only worked end-to-end example): *"citation metrics
(T_a, S_a, U_a) follow a hooked power law, so Nor_a(x) = φ⁻¹(P(L(x))) …
normal ranking. Indices (Hf', Hm', G') use fractional ranking for ties,
with Nor_a(x) = φ⁻¹(P(x))"*, then `Nm_a = (1/6) Σ Per`. (§3.3.2
*"Evaluation of overall score at a given time"* is a **stub heading with
no body** in the PDF — the "given time" / `as_of_year` handling it
alludes to lives in the upstream Eq. 10–14 pipelines, not here.)

### Eq. 27 — the final score

```
Nm_a = Σ  w_i · Per_a(x_i)          Σ w_i = 1
```

`config.NM_WEIGHTS` defaults to `1/6` each (the paper's suggested equal
weighting).

---

## Modelling choices you may need supervisor sign-off on

These are genuine choices the paper leaves open. They are all in
`config.py`; **don't change them silently.**

### 1. `NM_DISTRIBUTION` — log-normal vs hooked power law

Eq. 25 branches on whether a metric "follows log normal" (→ Z-score) or
"follows hooked power law" (→ rank-based inverse normal). The paper
splits this by *research stream* (humanities / social science ≈
log-normal; medical / natural science ≈ hooked). Because `T_a / S_a /
U_a` are already **cross-field per-author aggregates** by the time they
reach this module, there is no single field to switch on, so we apply
**one assumption per metric**.

Default: **`"hooked"`** for all three — this is what §3.3.3 does
explicitly. Switch a metric to `"lognormal"` if that stream really is
log-normal and you want the Z-score branch (the only branch where the
`log10` transform changes the ordering-based result).

### 2. Rank tie method — `RANK_METHOD_LOG` / `RANK_METHOD_RANK`

Eq. 24: *"fractional ranking for the hm, hf, g indices (as they contain
many ties) … and normal ranking for the raw citations"*. So:
`RANK_METHOD_RANK = "average"` (fractional) for the indices,
`RANK_METHOD_LOG = "min"` (normal / competition) for `T/S/U`.
**Caveat:** the real citation-metric data *also* has a big block of
exact `0.0`. Under `"min"` that whole block shares rank 1 and lands near
the 0th percentile, which is why the real-data `Nm_a` median sits around
~20, not ~50. Set `RANK_METHOD_LOG = "average"` to spread the zero block
to the middle instead — a judgement call for the supervisor.

### 3. Reference population for percentiles — `NM_REFERENCE_N`

The paper's percentiles are "directly comparable **globally**" and
§3.3.3 uses `N = 100000` because it ranks one profile inside a global
100k-profile sample. **By default this module ranks each author only
against the cohort you load** (`NM_REFERENCE_N = None` → `N` = scored
authors, currently ~2,300). Set `NM_REFERENCE_N` to a fixed number only
if the cohort you load is genuinely at that scale — with a small cohort
a large fixed `N` crushes every percentile toward 0.

### 4. Zero-inflation (inherited from the component metrics)

Most component scores are exactly `0.0` (extreme citation skew — see
`modified_hm_index/CLAUDE.md` for the same issue one layer down). With
the shipped defaults (`"hooked"` + `"min"` ranking for `T/S/U`), the
zero-mass on the citation metrics lands near the 0th percentile while
the fractional-ranked index metrics put their zeros mid-scale, so on the
real dataset `Nm_a` has median ≈ 20 with a thin tail up to ≈ 100. Under
`"lognormal"` the zero-mass instead ties near the 45–48th percentile. In
**both** cases this is **mathematically consistent with the model**, not
a bug — but the distribution shape is worth a conversation, and is
mostly a symptom of the upstream component metrics being ~96% zero.

### 5. `NM_REQUIRE_ALL_METRICS` — missing-metric policy

* `False` (default): an author missing *k* of the 6 metrics is scored on
  the remaining `6 − k`, with `NM_WEIGHTS` renormalised to sum to 1
  over the available subset. `metrics_available` records how many were
  used. This is what keeps the pipeline producing output while the
  g-index table is empty.
* `True`: authors without all 6 metrics get `nm_index = NULL`.

---

## Output

### `author_nm_index` (created by `schema.sql`)

| Column | Meaning |
|---|---|
| `author_id` | PK, FK → `author` |
| `per_total_cites` … `per_modified_g_index` | the six `Per_a(x_i)` (0–100, `NULL` if that component is unavailable) |
| `metrics_available` | `SMALLINT` 0–6 — how many components fed `nm_index` |
| `nm_index` | the final Eq. 27 score (`NULL` if 0 components, or < 6 when `NM_REQUIRE_ALL_METRICS`) |
| `calculated_at` | run timestamp |

`run_calculation.py` upserts (`INSERT … ON CONFLICT (author_id) DO
UPDATE`), so re-running is safe and idempotent.

### `author.nm_index` (optional)

Set `config.NM_UPDATE_AUTHOR_TABLE = True` to also mirror the final
score onto the `author` table (column added by `schema.sql`), the same
way `author.modified_hm_index` is populated.

---

## What you need to create in the real DB

Nothing for **inputs** — every source table already exists. You only need:

1. **`author_nm_index` table** — run `schema.sql`.
2. *(optional)* **`author.nm_index` column** — also in `schema.sql`
   (`ALTER TABLE author ADD COLUMN IF NOT EXISTS nm_index NUMERIC`),
   only needed if you enable `NM_UPDATE_AUTHOR_TABLE`.
3. **Populate `modified_g_index_results`** by running the modified
   g-index pipeline — otherwise `G'_a` stays unavailable and every
   `nm_index` is a 5-metric average.

---

## Testing

`test_calculator.py` is pure in-memory — no DB. Every expected number is
derived by hand in the comments (the standard-normal CDF `Φ` is taken
from `scipy.stats.norm`, exactly as Eq. 25/26 intend). If you change
the calculation, re-derive by hand — don't paste in whatever the code
prints.

**No test exercises `run_calculation.py` / `database.py`** — same known
gap as `modified_hm_index`. The DB path was validated by a read-only
dry run against the live database during development.



To run this

pip install -r "final_nm_index/requirements.txt"
psql "<your DB>" -f "final_nm_index/schema.sql"
python -m pytest "final_nm_index/test_calculator.py" -v
python -m final_nm_index.run_calculation