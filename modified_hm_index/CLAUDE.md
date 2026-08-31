# CLAUDE.md

Context file for Claude Code (or any AI assistant) working on this project. Read this before making changes — several design decisions here look wrong at first glance but are intentional, and are documented below along with *why*.

## Project Overview

This module calculates the **Modified Hm-index** (a bibliometric author-impact score from a research paper on the Nm-index) for authors, using PostgreSQL as the data source, and writes the result back to `author.modified_hm_index`.

```
modified_hm_index/
├── __init__.py
├── config.py            # DB table/column name mappings
├── database.py          # PostgreSQL connection (.env-based)
├── calculator.py        # Core calculation logic
├── run_calculation.py   # Loads data, calls calculator, writes results
├── test_calculator.py   # Regression tests (no DB required)
└── README.md            # Full documentation
```

Run it with:
```bash
python -m modified_hm_index.run_calculation
```

Run tests with:
```bash
pytest test_calculator.py -v
```

---

## Current Calculator Interface (IMPORTANT — changed recently)

```python
calculate(effective_citations: pd.DataFrame, field_classification: pd.DataFrame) -> pd.DataFrame
```

**Only two DataFrames.** Earlier versions of this module took `paper_authors`, `authors`, `paper_citations`, `field_classification` (and even earlier, a fifth `field_normalization` DataFrame). All of that was consolidated because of a real data-model discovery — see below.

### `effective_citations` — required columns
```
paper_id, author_id, field_id, career_factor, author_field_weight, capped_adjusted_citations
```
Loaded from `author_paper_field_effective_citation`. **This table is unique at `(pub_id, author_id, field_name)` — NOT at `pub_id` alone.** It already contains:
- `career_factor` — precomputed per author (same value repeated across that author's rows)
- `author_field_weight` — the **fully combined** position-weight × field-share (i.e. the paper's own `W_p^{f,i}` from Eq. 1/3/4/5), NOT a raw percentage, NOT position-only

### `field_classification` — required columns
```
paper_id, field_id, field_weight
```
`field_weight` (`V_p^f`) is used **only** for the outer Eq. 20 cross-field combination now — it is *not* multiplied into `tc_eff`/`r_eff` inside the calculator, because `author_field_weight` already has that baked in upstream.

---

## Critical History — Why the Interface Looks Like This

### 1. The original bug: duplicated rows from a too-coarse join

Early versions merged `paper_authors` + `paper_citations` + `field_classification` on `paper_id` alone. This silently cross-joined any paper with multiple authors or multiple fields, multiplying `tc_eff`/`r_eff` for affected rows. Diagnosed via `.duplicated(subset=["paper_id"])` on the real DB — came back with **8877/8877 rows flagged**, i.e. every row shared its `paper_id` with something else. Root cause: `author_paper_field_effective_citation` is genuinely one row per `(paper, author, field)`, but the old code only ever selected `pub_id` + citation from it, discarding the columns that actually distinguish rows.

**Fix:** confirmed via SQL that `author_paper_field_effective_citation` has real `author_id` and `field_name` columns (plus `career_factor`, `author_field_weight`, `calculation_status`), and that `career_factor × author_field_weight × capped_adjusted_citation ≈ effective_citation` (verified by hand against real rows — exact match to 6 decimal places). The calculator was rewritten to read these directly and join on the full `(paper_id, field_id)` composite key against `field_classification`, which is itself unique at `(paper_id, field_id)` (confirmed via `GROUP BY ... HAVING COUNT(*) > 1` returning empty).

**If you ever see `paper_authors` or `authors` DataFrames referenced anywhere** — that's stale code from before this fix. `load_author_contribution_weight()` and `load_authors()` still exist in `run_calculation.py` but are **no longer called** in `get_data_from_database()`, kept only in case something else in the wider system still needs them directly.

### 2. Field normalization (`Hm'_f`) — not in the paper, invented, then redefined

The source paper defines Eq. 19 as `Hm'_{f,a} = max_r_eff / Hm'_f`, but **never specifies how to compute `Hm'_f`** for real data — its own worked example just asserts a bare constant (`Hm'_f = 3`) with zero derivation shown. This was independently confirmed via Lemma 14's proof (Appendix, Section 6.4.5), which only requires `Hm'_f > 0` — no formula.

History of approaches, in order:
1. **90th percentile of raw citations per field** — an early invented stand-in. Abandoned: unit mismatch (an hm-index-shaped numerator divided by a citations-shaped denominator — Eq. 19's own reduction case shows `Hm'_f` should be on the same scale as a plain hm-index).
2. **Hardcoded fixed value (150)** — briefly tried per a misunderstanding, then reverted. (150 was later correctly repurposed as a **citation outlier cap** instead — see below, a completely different, unrelated concept.)
3. **Current approach — field average, computed internally, "running value":** per direct instruction from the project supervisor. `Hm'_f` = the mean of every author's own `max_r_eff` (the Eq. 19 *numerator*, before dividing by anything) across all authors who have ≥1 paper in that field. Recomputed fresh from the current dataset on every run — never stored, never passed in externally.

This requires a **two-pass calculation** inside `calculate()`:
- **Pass 1**: compute `max_r_eff` per `(author_id, field_id)` (sort by `tc_eff` desc, walk the h-index-style threshold condition `cum_tc_eff(k) >= r_eff(k)`, take `r_eff` at the largest valid `k`).
- **Pass 2**: group Pass 1's results by `field_id`, take the mean → becomes `hm_field_normalization`. Divide each author's own `max_r_eff` by their field's average.

**Known consequence, not yet resolved with the supervisor:** on real data, ~90% of `capped_adjusted_citations` values are exactly `0.0` (extreme citation skew — consistent with the paper's own stated log-normal/hooked-power-law assumption in Section 2.5). This means most authors score `max_r_eff = 0` in most fields (the threshold condition fails at `k=1` whenever an author's single best paper has `< 1` citation). A plain mean is **not robust** to this zero-inflation: fields where only a handful of authors have any real citations produce a field average crushed near zero, and those few non-zero authors then get divided by that near-zero denominator — producing extreme scores (seen in practice: values like `94`, `53`, `24` alongside a sea of `0.0000`). **This is mathematically consistent with the current design, not a bug** — but it's an open question whether the supervisor intended a plain mean to behave this way on real (rather than toy) data. Candidate alternatives discussed but NOT implemented: exclude zero-scorers from the average, use median instead of mean, or accept it as intentional ("rare achievers in an otherwise dormant field should score exceptionally"). **Do not unilaterally change this without supervisor sign-off** — it's been an explicit instruction, revisited multiple times already.

### 3. Citation outlier cap (150) — separate from field normalization, easy to confuse

`OUTLIER_CITATION_CAP = 150` in `run_calculation.py`, applied via `apply_citation_outlier_cap()` immediately after loading citations, before anything else touches them. Caps any `capped_adjusted_citations` value above 150 down to 150 — flat, uniform across all fields (not a per-field percentile like the paper's own Eq. 12 `R_k,f`, which uses a 99th-percentile cap conceptually — this was simplified to a fixed value per instruction).

**Do not confuse this with `hm_field_normalization`.** They are unrelated: one caps raw citation *input* values; the other rescales the *final computed rank* per field. A uniform citation-cap value does NOT need to match or relate to the normalization value in any way.

### 4. Percentage-vs-proportion conversions

Two places convert DB percentage values (0–100) to proportions (0–1):
- `load_author_contribution_weight()` — `/100.0` on `contribution_weight` (still present, though this loader is currently unused — see point 1)
- `load_paper_fields()` — `/100.0` on `field_weight`

**Note:** empirically verified that a *uniform* percentage-vs-proportion error in `field_weight` cancels out exactly in the final `modified_hm_index` (it's a common multiplier on both sides of every ratio in the model) — confirmed by running identical data through the calculator with `field_weight` as `0.7/0.3` vs `70/30` and getting results differing by `4.4e-16` (floating-point noise only). Still fixed for correctness/consistency, but if you're debugging a *different* wrong-number issue, this conversion is very unlikely to be the cause.

`author_field_weight` in `author_paper_field_effective_citation` is **already a proper 0–1 proportion** in the real data (confirmed by inspection: values like `0.0710072`, `0.526400`) — do **not** apply a `/100.0` conversion to it.

---

## Data Model Quick Reference

| Concept | Paper's notation | Column in this codebase |
|---|---|---|
| Career compensation factor | `CF_com` | `career_factor` (in `effective_citations`) |
| Combined position+field weight | `W_p^{f,i}` (Eq. 1/3/4/5) | `author_field_weight` |
| Field share of a paper | `V_p^f` | `field_weight` (in `field_classification`) — used ONLY for Eq. 20 now |
| Effective citations | `TC_eff` (Eq. 15) | `tc_eff` (computed in `calculator.py`) |
| Effective rank at threshold | numerator of Eq. 19 | `max_r_eff` |
| Field normalization | `Hm'_f` (Eq. 19 denominator) | `hm_field_normalization` — computed internally now, see history above |
| Final per-field score | `Hm'_{f,a}` | `hm_prime_field_author` |
| Final combined score | `Hm'_a` (Eq. 20) | `modified_hm_index` |

**`field_weight` (`V_p^f`) is used TWICE by design** in the underlying model — this is confirmed in the paper's own worked numerical example, not a redundancy bug. In the current codebase, though, it's only applied *once*, at the Eq. 20 stage — because the *other* use is already pre-baked into `author_field_weight` before it ever reaches this calculator.

---

## Testing Notes

`test_calculator.py` has no DB dependency — pure in-memory DataFrame tests. All hand-derived expected values are shown in comments directly above each assertion; if you change the calculation logic, re-derive by hand before updating the assertions, don't just accept whatever the code outputs.

**Known gap:** no test exercises the actual `run_calculation.py` / `database.py` DB-loading path. All bugs found in this project's history (the composite-key join issue, the percentage conversions) were found by manually running against real DB output and diagnosing from there — the test suite validates `calculator.py`'s math in isolation, not the DB-to-calculator pipeline.

**Common test-writing trap** (hit multiple times during development): giving `effective_citations` more than one row per `(paper_id, author_id, field_id)` — e.g. accidentally duplicating an author's row once per field instead of giving each field its own row with its own `author_field_weight`. Always double check row counts after any merge in a new test.

---

## Open Items / Not Yet Done

- [ ] README.md may still reference the old multi-DataFrame calculator interface in places — worth a full pass to confirm it matches the current 2-DataFrame signature.
- [ ] The field-average zero-inflation issue (history item #2 above) is unresolved — pending supervisor input on whether to exclude zero-scorers, use a different statistic, or accept as-is.
- [ ] No diagnostic tooling is currently checked into the repo for inspecting `field_normalization` distributions or duplicate-row checks — these were run ad hoc during debugging (see conversation history) but not saved as reusable scripts.
- [ ] `calculation_status` values other than `READY` (e.g. `MISSING_VALUE`) are filtered out in the SQL `WHERE` clause — confirmed this matches intent (252 `MISSING_VALUE` rows exist in real data, correctly excluded), but worth re-confirming if the upstream job that populates this table changes its status vocabulary.
