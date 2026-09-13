# Modified g index — Element & Data Sheet (Section 2.10)

Source: Abstract doc, section **2.10 "Modified g index"**, Equations 20–22
(same as full paper section 2.4.6, Equations 21–23).

```
Aeff,f,a(k)  = Σ(p'=1→k) TCeff,f,p',iap'                       (Eq 20)
G'f,a        = max(k : Aeff,f,a(k) ≥ k²) / G'f                  (Eq 21)
G'a          = [ Σf Σp Vpf · G'f,a ] / [ Σf Σp Vpf ]             (Eq 22)
```

Papers are sorted **descending by `TCeff`** within each `(author, field)` group before
Eq 20/21 are evaluated. `TCeff` itself (full-paper Eq 15/19) is:

```
TCeff,f,p,iap = CFcom · Wp^(f,i) · TCcap,p,iap^(adj,k)
```

which in turn needs `TCcap` (Eq 12 capping) applied to the influential-self-citation
adjusted total `TC^adj` (Eq 7–9).

## Element table — what's needed vs. what's in the DB

| Symbol | Meaning | DB source (checked live, 2026-08-19) | Status |
|---|---|---|---|
| `TC^adj` | Self-citation-adjusted total citation (Eq 7–9) | `total_cites_equation_11_details.adjusted_citation` (also `equation_9_adjusted_citations`) | ✅ present, but **mostly not READY** — 264 rows total, 162 `INCOMPLETE_ISC`, 99 `ZERO_FIELD_YEAR_AVERAGE`, only 3 `READY_PROVISIONAL_BENCHMARK` |
| `R_{k,f}^adj` | 99th-pct field cap threshold (Eq 12) | `field_citation_percentile_caps.cap_threshold` | ✅ present, 19 fields, but sample sizes are tiny (2–9 rows/field) since it's built from the sparse `TC^adj` above |
| `TCcap` | Capped adjusted citation (Eq 12 applied) | Not stored anywhere — computed as `min(TC^adj, R_{k,f}^adj)` | ⚠️ compute on the fly (logic already exists: `Equations_12_13_14/calculator.py:cap_adjusted_citation`) |
| `Wp^(f,i)` | Author contribution weight (Eq 1–6) | `total_cites_equation_11_details.author_field_weight` (also raw components in `author_contribution_weight`) | ✅ present |
| `CFcom` | Career compensation (Eq 10) | `author.career_compensation` | ✅ present, populated for all 2507 authors |
| `Vpf` | Paper's field weight (0–1, up to 3 fields/paper) | `field_classification.field1_weight/2/3` | ⚠️ present but **stored as 0–100, not 0–1** (e.g. 46.59 + 37.36 + 16.05 = 100) — divide by 100 before use, don't assume it already sums to 1 |
| `TCeff` | Effective citation per paper/field (Eq 15/19) | `eq15_effective_citations` table exists (`cf_com`, `w_value`, `tc_cap`, `tc_eff_adj` columns match) | ❌ **0 rows, and `author_id`/`pub_id` are typed `integer`** — every other table uses `VARCHAR(100)`, so this table can't currently be joined to `author`/`publication`. Looks like an unfinished scaffold from another teammate — needs a fix or a schema decision before reuse, so I did not build on it (see below). |
| Sort + cumulative sum (Eq 20) | Descending sort of `TCeff` per `(author, field)`, running total | Nothing stored — pure computation over the rows above | New logic, no missing data |
| `G'f` | Field normalization constant, divisor in Eq 21 | **Not defined anywhere** — not in the DB, not in the paper's formula (the paper's own numeric demo just assumes a value, e.g. `G'f = 7`, without deriving it) | ❌ **open modeling decision** — see below |
| `G'a` | Final per-author score (Eq 22) | Nothing stored | New table, no missing data |

## The one real gap: `G'f`

Every other symbol above is either already in the database or is a pure computation over
existing columns. `G'f` is the exception — it's a genuine, undefined modeling choice, not
a data-collection gap. Two reasonable options, same pattern already used for `TC_bar_f`
(`field_adjusted_citation_average`) and `R_{k,f}^adj` (`field_citation_percentile_caps`):

1. **Empirical**: compute the raw (unweighted) g-index per field across every author
   currently in the DB, take the mean/median as `G'f`. Self-consistent with how the other
   two field benchmarks were built, but data is currently too sparse per field (most
   fields have single-digit sample sizes) to be stable yet.
2. **Fixed reference constant**: pick one global or per-field constant by team/supervisor
   decision (mirrors the paper's own demo, which just assumed `G'f = 7`).

I did not pick one silently — `g_index_field_reference` (below) is created with a
`normalization_method = 'PENDING'` and a nullable value, so whichever the team decides
can be populated without a schema change.

## Data readiness caveat

Even once the code is written, end-to-end results will be mostly `INCOMPLETE_ISC` /
placeholder right now: only 3 of 264 `total_cites_equation_11_details` rows are fully
`READY`. The g-index tables below carry the same `calculation_status` bookkeeping pattern
the team already uses in `citations_per_paper_details` / `citation_rate_details` for
exactly this reason — so partial data doesn't get silently reported as a finished score.

## DB tables created for this (2026-08-19)

Mirrors the 4-table pattern already used for Equations 12–14 (reference table → per-row
detail table → per-field result → per-author final result):

| Table | Role |
|---|---|
| `public.g_index_field_reference` | Holds `G'f` per field once the team decides how to derive it |
| `public.modified_g_index_paper_details` | Per (author, pub, field): `TCeff` inputs/value, sort rank within field, running cumulative sum, whether it satisfies `Aeff(k) ≥ k²` |
| `public.modified_g_index_field_results` | Per (author, field): `g_field_raw` (Eq 21 numerator), `G'f` used, `G'f,a` normalized |
| `public.modified_g_index_results` | Per author: final `G'a` (Eq 22 weighted average across fields) |

See `db_setup.py` in this folder for the exact DDL; `db_connection.py` reads the same
root `.env` every other module uses.
