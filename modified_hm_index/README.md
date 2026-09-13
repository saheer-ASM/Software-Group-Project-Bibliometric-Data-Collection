# Modified Hm-Index Calculation

## Overview

This module calculates the **Modified Hm-index** for authors using a modified Hm-index methodology that considers:

* Author career factor (`career_factor`, precomputed per author)
* The combined author position/ordering weight × paper field share (`author_field_weight`), read directly from the effective-citation table
* Capped adjusted citations (outlier-capped at a fixed threshold before reaching this calculation — see Section 6)
* Multiple research fields per paper
* Field weights (`field_weight`), applied at the cross-field combination stage (Section 11); the within-field scaling is already baked into `author_field_weight` upstream
* An h-index-style threshold condition that limits which papers count toward the field-specific score
* A **field-average normalization**, computed internally and freshly on every run (see Section 9)

The calculated Modified Hm-index is written back to the `author` table.

The calculation is implemented using Python, Pandas, NumPy, and PostgreSQL.

---

## Project Structure

```text
modified_hm_index/
│
├── __init__.py
├── config.py
├── database.py
├── calculator.py
├── run_calculation.py
├── test_calculator.py
└── README.md
```

### File Responsibilities

| File                 | Responsibility                                                           |
| -------------------- | ------------------------------------------------------------------------ |
| `config.py`          | Contains database table and column mappings                              |
| `database.py`        | Creates the PostgreSQL database connection                               |
| `calculator.py`      | Contains the Modified Hm-index calculation logic, including internal field normalization |
| `run_calculation.py` | Loads database data, applies the citation outlier cap, runs the calculator, and updates the author table |
| `test_calculator.py` | Regression tests for the calculation logic (see Section 21)              |
| `README.md`          | Documentation for the module                                             |

---

# 1. Database Configuration

The database structure is mapped in:

```text
config.py
```

The `TABLE_COLUMNS` dictionary allows the calculation code to work with the existing database schema without changing the calculation logic.

The calculation reads from **two** tables (`author_paper_field_effective_citation` and `field_classification`) and **writes** to one (`author`). See Section 18 for the full list of required columns.

---

## 2. Author Contribution Table (no longer used by this calculation)

### Database Table

```text
author_contribution_weight
```

> **This table is not read by the Modified Hm-index calculation any more.**
> The per-author, per-field weight it used to supply (`W_p^{f,i}`) is now taken
> directly from `author_paper_field_effective_citation.author_field_weight`
> (Section 4), which already combines the position/ordering weight with the
> paper's field share. `config.py` still contains the mapping, and
> `run_calculation.load_author_contribution_weight()` still exists — in case
> another part of the wider system reads this table directly — but
> `get_data_from_database()` no longer calls it.

For reference, the historical processing was: a **wide format** table with up to
10 author positions per paper (`pub_id`, `author1id`, `author1id_weight`, …,
`author10id`, `author10id_weight`), normalized into `paper_id, author_id,
contribution_weight` via `UNION ALL`, with the raw value divided by `100.0`
(stored as a 0–100 percentage). `contribution_weight` was the position/ordering
weight only (alphabetical, harmonic, or CRediT/ACI ordering) — it did **not**
include the paper's field split, which was applied separately.

---

# 3. Author Table

### Database Table

```text
author
```

### Configuration

```python
'author': {
    'table': 'author',
    'author_id': 'author_id',
    'career_factor': 'career_compensation',
    'modified_hm_index': 'modified_hm_index',
}
```

### Required Columns

```text
author_id
modified_hm_index
```

This table is the **write target**. After the calculation completes, the runner
writes each author's final score to `author.modified_hm_index` (Section 17).

The calculation **no longer reads** `career_compensation` from this table — the
per-row `career_factor` now comes from `author_paper_field_effective_citation`
(Section 4). The `career_factor` → `career_compensation` mapping is kept in
`config.py` only for `load_authors()`, which `get_data_from_database()` no longer
calls.

---

# 4. Effective Citation Table

### Database Table

```text
author_paper_field_effective_citation
```

### Configuration

```python
'author_paper_field_effective_citation': {
    'table': 'author_paper_field_effective_citation',
    'paper_id': 'pub_id',
    'author_id': 'author_id',
    'field_id': 'field_name',
    'career_factor': 'career_factor',
    'author_field_weight': 'author_field_weight',
    'capped_adjusted_citations': 'capped_adjusted_citation',
    'calculation_status': 'calculation_status',
}
```

### Required Columns

```text
pub_id
author_id
field_name
career_factor
author_field_weight
capped_adjusted_citation
calculation_status
```

These are loaded into Python as:

```text
paper_id
author_id
field_id
career_factor
author_field_weight
capped_adjusted_citations
```

### Important properties

* **This table is unique at `(pub_id, author_id, field_name)` — not at `pub_id`
  alone.** It is the single source of per-author, per-field data for the
  calculation.
* `career_factor` is the precomputed per-author career compensation factor
  (`CF_com`), repeated across that author's rows.
* `author_field_weight` is the **fully combined** position/ordering weight ×
  field share (`W_p^{f,i}` from Eq. 1/3/4/5) — already a proper 0–1 proportion in
  the real data (e.g. `0.0710072`, `0.526400`). **Do not** apply a `/100.0`
  conversion to it.
* Only rows with `calculation_status = 'READY'` and a non-null
  `capped_adjusted_citation` are loaded. Rows in other states (e.g.
  `MISSING_VALUE`) are excluded by the SQL `WHERE` clause.
* `career_factor × author_field_weight × capped_adjusted_citation` should closely
  match this table's own `effective_citation` column — verified by hand to six
  decimal places before the calculator was rewritten to read these columns
  directly.

The 150-citation outlier cap (Section 6) is applied to
`capped_adjusted_citations` immediately after loading.

---

# 5. Field Classification Table

### Database Table

```text
field_classification
```

### Configuration

```python
'field_classification': {
    'table': 'field_classification',
    'paper_id': 'pub_id',

    'field_id_columns': [
        'field1_name',
        'field2_name',
        'field3_name',
    ],

    'field_weight_columns': [
        'field1_weight',
        'field2_weight',
        'field3_weight',
    ],
}
```

### Required Structure

Each paper can contain up to three research fields:

```text
pub_id
field1_name
field1_weight
field2_name
field2_weight
field3_name
field3_weight
```

The program converts this wide structure into:

```text
paper_id
field_id
field_weight
```

The three field positions are combined into one normalized DataFrame using
`UNION ALL`. `run_calculation.load_paper_fields()` divides the raw value by
`100.0` (`field_weight = raw / 100.0`), so the source column is expected to be
stored as a percentage (0–100). This table is expected to be unique at
`(pub_id, field_name)`.

### How `field_weight` is used

`field_weight` (`V_p^f` in the underlying model) is used **twice in the
underlying model** — once to scale a multi-field paper's contribution down to its
share in each field, and once to weight each field's Hm score into the author's
overall score.

In **this codebase**, the calculator applies it **once**, at the Eq. 20
cross-field combination stage (Section 11). The other use — scaling the per-field
effective citations and rank — is already baked into
`author_paper_field_effective_citation.author_field_weight` upstream, so the
calculator must **not** multiply `field_weight` into `tc_eff`/`r_eff` again.

> **Note:** a *uniform* percentage-vs-proportion error in `field_weight` cancels
> out exactly in the final `modified_hm_index` (it is a common multiplier on both
> sides of every ratio in the model) — confirmed empirically (results differ only
> by floating-point noise). It is still converted for correctness, but it is an
> unlikely cause of a wrong-number bug.

---

# 6. Citation Outlier Cap

Before citations reach the field normalization or the main calculator, a
**fixed outlier cap of 150 citations** is applied in `run_calculation.py`:

```python
OUTLIER_CITATION_CAP = 150

def apply_citation_outlier_cap(paper_citations, cap=OUTLIER_CITATION_CAP):
    paper_citations["capped_adjusted_citations"] = (
        pd.to_numeric(paper_citations["capped_adjusted_citations"], errors="coerce")
          .clip(upper=cap)
    )
    return paper_citations
```

Any row whose `capped_adjusted_citations` value exceeds 150 is truncated down to
150; values at or below 150 are left unchanged. This is applied once, in
`get_data_from_database()`, immediately after the effective-citation rows are
loaded — so both the effective-citation calculation and the internal field
normalization (Section 9) operate on already-capped values.

This is a **flat cap applied uniformly across every field** — not a per-field
percentile. It is a separate, unrelated concept from the field-average
normalization in Section 9 (which rescales the final computed rank, not the raw
citation input); the two values do not need to relate to each other.

---

# 7. Data Processing Flow

The complete calculation follows these steps:

```text
PostgreSQL Database
        │
        ├── author_paper_field_effective_citation
        │       (pub_id, author_id, field_name, career_factor,
        │        author_field_weight, capped_adjusted_citation; READY rows only)
        │
        └── field_classification
                (pub_id, field1..3_name / field1..3_weight)
                │
                ▼
        Load Database Data
                │
                ▼
        Apply Outlier Cap (150 citations, Section 6)
                │
                ▼
        Normalize wide field_classification → (paper_id, field_id, field_weight)
                │
                ▼
        Merge on the (paper_id, field_id) composite key
                │
                ▼
        Calculate Effective Citations (Eq. 15)
                │
                ▼
        PASS 1: Per-Author-Field Effective Rank (Eq. 18/19 numerator,
                with the h-index-style threshold condition)
                │
                ▼
        PASS 2: Field-Average Normalization (Eq. 19 denominator,
                computed internally from the current data)
                │
                ▼
        Calculate Field-Specific Hm (Eq. 19)
                │
                ▼
        Calculate Weighted Hm (Eq. 20)
                │
                ▼
        Calculate Final Modified Hm-index
                │
                ▼
        Update author.modified_hm_index
```

---

# 8. Effective Citation Calculation (Equation 15)

The calculator computes effective citations as:

```text
TC_eff =
Career Factor
× Author-Field Weight
× Capped Adjusted Citations
```

In Python:

```python
data["tc_eff"] = (
    data["career_factor"]
    * data["author_field_weight"]
    * data["capped_adjusted_citations"]
)
```

`author_field_weight` already combines the author's position/ordering weight with
the paper's field share (`V_p^f`), so a paper split across multiple fields
already contributes only its proportional share to each field's calculation.
`field_weight` from `field_classification` is **not** multiplied in here — doing
so would double-count it. `field_weight` is used only later, at the Eq. 20 stage
(Section 11).

`tc_eff` should closely match the `effective_citation` column already present in
`author_paper_field_effective_citation` — that equivalence was verified by hand
to six decimal places before the interface was changed.

This value is then used to rank papers within each author-field combination.

---

# 9. Field Normalization — Computed Internally (Equations 18–19)

**This is the central design decision in the current implementation, and it
differs from earlier drafts of this module.** `Hm'_f` (the field normalization
denominator in Equation 19) is **not** supplied as an external input, and is
**not** a percentile of raw citations. It is calculated internally, inside
`calculator.calculate()`, as a **field average** of every author's own raw
effective rank — recalculated fresh from the current dataset on every call
("a running value," not a stored constant).

This decision follows directly from the paper's own text (Sections 2.4.4–2.4.6
describe `Hf'_f`/`Hm'_f`/`G'_f` only as "field normalization," and a companion
abstract explicitly describes the analogous `Hf'_f` as "normalized by field
average"). The paper's own worked numerical demo (Section 3.3) never shows how
its example constants (e.g. `Hm'_f = 3`) were derived — this implementation fills
that gap using the "field average" description. Lemma 14's proof (Appendix,
Section 6.4.5) only requires `Hm'_f > 0`, not any particular formula.

### 9.1 Pass 1 — per author-field effective rank

For each `(author_id, field_id)` combination present in the data, papers are
sorted by `tc_eff` descending, and the calculator finds the largest `k`
(`k_valid`) such that cumulative effective citations still meet or exceed
cumulative effective rank (an h-index-style threshold condition):

```python
sorted_group["effective_rank_contribution"] = (
    sorted_group["career_factor"] * sorted_group["author_field_weight"]
)
sorted_group["r_eff"] = sorted_group["effective_rank_contribution"].cumsum()
sorted_group["cum_tc_eff"] = sorted_group["tc_eff"].cumsum()

k_valid = 0
for satisfied in (sorted_group["cum_tc_eff"] >= sorted_group["r_eff"]):
    if satisfied:
        k_valid += 1
    else:
        break

max_r_eff = sorted_group["r_eff"].iloc[k_valid - 1] if k_valid > 0 else 0.0
```

The result of this pass, `max_r_eff`, is the Equation 19 **numerator only** — it
is not yet divided by anything.

### 9.2 Pass 2 — field-average normalization

Once every author-field combination has a `max_r_eff`, the calculator groups by
`field_id` and takes the **mean**:

```python
field_normalization = (
    author_field_df
    .groupby("field_id")["max_r_eff"]
    .mean()
    .reset_index()
    .rename(columns={"max_r_eff": "hm_field_normalization"})
)
```

Fields whose average comes out `<= 0` are dropped; if none remain, the
calculation raises `ValueError`. Each author's own `max_r_eff` is then divided by
their field's average:

```python
author_field_df["hm_prime_field_author"] = (
    author_field_df["max_r_eff"] / author_field_df["hm_field_normalization"]
)
```

### 9.3 What this means in practice

* An author whose contribution is exactly at their field's average scores **1.0**
  for that field.
* An author above the field average scores **above 1.0**; below average scores
  **below 1.0**.
* **A field with only one contributing author always normalizes to exactly 1.0**
  for that author, since the "field average" and the author's own value are
  identical when there is no one else to compare against. This is expected
  behavior, not a bug — with no peers, you are the average.
* Authors with zero papers in a field are naturally excluded from that field's
  average, since they never produce a `max_r_eff` for a field they don't publish
  in.
* Because this is recalculated from scratch on every run, results for the same
  author can shift between runs purely because *other authors'* data changed the
  field average — this is intentional ("a running value"), not instability.

> **Known open item (pending supervisor input):** on real data, most
> `capped_adjusted_citations` values are exactly `0.0` (extreme citation skew).
> This means most authors score `max_r_eff = 0` in most fields, and a plain mean
> is not robust to that zero-inflation — a field where only a few authors have
> real citations produces a field average crushed near zero, and those few
> authors then get divided by a near-zero denominator, producing extreme scores.
> This is mathematically consistent with the current design. Candidate
> alternatives (exclude zero-scorers, use median, accept as-is) have been
> discussed but **not** implemented — do not change this without supervisor
> sign-off.

---

# 10. Field-Specific Normalization (Equation 19)

Putting Section 9's two passes together, for each author-field combination:

```text
Hm'field,author =
max_r_eff (this author, this field)
/
Field Average of max_r_eff (all authors, this field)
```

The result is stored as:

```text
hm_prime_field_author
```

---

# 11. Weighted Hm Across Fields (Equation 20)

The field-specific Hm value is combined with the paper's field weight:

```text
weighted_hm =
field_weight × hm_prime_field_author
```

In Python:

```python
data["weighted_hm"] = (
    data["field_weight"]
    * data["hm_prime_field_author"]
)
```

This allows an author who works across multiple research fields to have the field
contributions incorporated into the final index. This is the **only** place
`field_weight` from `field_classification` is applied in this codebase — the
per-field scaling that `field_weight` also performs in the underlying model is
already baked into `author_field_weight` (see Section 5 and Section 8).

---

# 12. Final Modified Hm-index

The calculation groups results by:

```text
author_id
```

Two values are calculated:

### Numerator

```text
Σ weighted_hm
```

### Denominator

```text
Σ field_weight
```

The final Modified Hm-index is:

```text
Modified Hm-index =
Σ(weighted_hm)
/
Σ(field_weight)
```

If the denominator is zero, the result is set to:

```text
0
```

The final result contains:

```text
author_id
modified_hm_index
```

---

# 13. Calculator Interface

```python
calculate(
    effective_citations: pd.DataFrame,
    field_classification: pd.DataFrame,
) -> pd.DataFrame
```

**Two DataFrames only.**

`effective_citations` — required columns:

```text
paper_id, author_id, field_id, career_factor,
author_field_weight, capped_adjusted_citations
```

Must be unique at `(paper_id, author_id, field_id)` — one row per author per
field, each with its own `author_field_weight` already reflecting that field's
share.

`field_classification` — required columns:

```text
paper_id, field_id, field_weight
```

Must be unique at `(paper_id, field_id)`.

> **History:** earlier drafts took **four** DataFrames
> (`paper_authors`, `authors`, `paper_citations`, `field_classification`), and an
> even earlier one took a fifth externally-computed `field_normalization`. Both
> were removed. The author/field weights and career factor are now read straight
> from `author_paper_field_effective_citation`, which is genuinely one row per
> `(paper, author, field)`; field normalization is computed internally
> (Section 9). If you see `paper_authors` or `authors` referenced anywhere, that
> is stale code from before this change.

---

# 14. Data Validation

The calculator converts the following values to numeric:

```text
career_factor
author_field_weight
capped_adjusted_citations
field_weight
```

Invalid numeric values are coerced to `NaN` and the affected rows are dropped.

The calculation only retains records where:

```text
author_field_weight > 0
career_factor > 0
field_weight > 0
```

If no valid records remain, the calculation stops with:

```text
ValueError: No valid data remains after cleaning.
```

This prevents invalid database values from affecting the final index.

---

# 15. Running the Calculation

From the project environment, run:

```bash
python -m modified_hm_index.run_calculation
```

Alternatively, if running directly from the package structure:

```bash
python run_calculation.py
```

The program executes the following major steps:

```text
STEP 1: Loading database data (includes applying the 150-citation outlier cap)
STEP 2: Calculating Modified Hm-index (field normalization computed internally)
STEP 3: Results summary
STEP 4: Updating author table
```

> **Recommended for first runs against a new or changed database:** comment out
> the `update_authors_table(results)` call in `main()` and inspect
> `results['modified_hm_index'].describe()` plus a few known authors before
> allowing the calculation to write to the `author` table. This is especially
> worth doing after the normalization redesign, since the score's meaning has
> changed (relative-to-field-average rather than relative-to-a-percentile-of-
> citations) — existing intuitions about "what a good score looks like" from
> before this change no longer apply directly.

---

# 16. Console Output

During execution, the program displays:

### Author Calculation Data

The calculator displays the top records according to effective citations:

```text
paper_id
author_id
field_id
career_factor
author_field_weight
capped_adjusted_citations
tc_eff
```

### Results Summary

The program reports:

```text
Total authors
Average Modified Hm-index
Minimum Modified Hm-index
Maximum Modified Hm-index
```

It also displays the top five authors by Modified Hm-index.

---

# 17. Database Update

After successful calculation, the resulting values are written to:

```text
author.modified_hm_index
```

The update is performed using:

```sql
UPDATE author
SET modified_hm_index = %s
WHERE author_id = %s
```

The database transaction is committed after all author records are successfully updated.

If an error occurs, the transaction is rolled back.

---

# 18. Important Database Requirements

Before running the calculation, verify that the following tables and columns exist.

## `author_paper_field_effective_citation`

```text
pub_id
author_id
field_name
career_factor
author_field_weight
capped_adjusted_citation
calculation_status
```

Unique at `(pub_id, author_id, field_name)`. Only
`calculation_status = 'READY'` rows with a non-null `capped_adjusted_citation`
are used.

## `field_classification`

```text
pub_id
field1_name
field1_weight
field2_name
field2_weight
field3_name
field3_weight
```

## `author`

```text
author_id
modified_hm_index
```

Write target only. `career_compensation` is **not** read by this calculation any
more (see Section 3).

### Not required

* **`author_contribution_weight`** is no longer read (Section 2) —
  `author_field_weight` in `author_paper_field_effective_citation` already
  contains its value combined with the paper's field share.
* **No `field_normalization` table**, and no percentile is computed from citation
  data. Field normalization is calculated entirely inside
  `calculator.calculate()` from the effective-citation data already being loaded
  — see Section 9.

---

# 19. Configuration Customization

If the database column names change, update only:

```text
config.py
```

For example:

```python
TABLE_COLUMNS = {
    ...
}
```

The calculation logic should not need to be changed as long as the configured columns provide the required data.

This separation makes the implementation easier to adapt to an existing database schema.

---

# 20. Error Handling

The implementation performs several validation checks.

### Missing Columns

If an expected column is missing:

```text
ValueError:
<dataframe> is missing columns: [...]
```

### Invalid Data

Invalid numeric values are removed before calculation.

### Empty Dataset

If no valid data remains:

```text
ValueError:
No valid data remains after cleaning.
```

### No Field Results

If field-specific effective rank values cannot be calculated:

```text
ValueError:
No field-specific effective rank values were calculated.
```

### No Positive Field Averages

If every field's average effective rank comes out to zero or negative:

```text
ValueError:
No fields have a positive average effective rank; cannot normalize.
```

### Database Update Failure

If updating the author table fails:

```text
ROLLBACK
```

is performed so that incomplete database updates are avoided.

---

# 21. Testing

Regression tests for the calculation logic live in:

```text
test_calculator.py
```

These tests run entirely against in-memory DataFrames — no database connection is required.

### Running the tests

```bash
pytest test_calculator.py -v
```

### What is covered

| Test | Purpose |
| --- | --- |
| `test_two_author_field_average` | Hand-verified regression check on the core field-average arithmetic: an above-average and a below-average contributor in the same field, checked against an independent calculation |
| `test_solo_author_in_field_normalizes_to_one` | Confirms the solo-contributor edge case (Section 9.3) — a field with exactly one author must normalize to 1.0 |
| `test_long_tail_triggers_early_break` | Confirms the Eq. 19 threshold condition (`k_valid`) genuinely stops accumulating papers once cumulative citations fall behind cumulative rank, with the exact expected value hand-derived and asserted |
| `test_field_weight_affects_outer_combination` | Confirms `field_weight` drives the Eq. 20 cross-field combination — its role after the interface change, since `author_field_weight` now carries the per-field scaling that used to be `field_weight`'s first job |
| `test_eq20_multi_author_multi_field` | A full, hand-verified multi-author, multi-field scenario exercising Pass 1, Pass 2, and the Eq. 20 combination together |
| `test_missing_required_column_raises` | Confirms column validation still raises `ValueError` on malformed input |
| `test_all_rows_filtered_out_raises` | Confirms the calculator fails loudly, rather than silently returning an empty result, when all rows are filtered out during cleaning |

### Not currently covered

* No test exercises `database.py` or `run_calculation.py` directly (these require a live PostgreSQL connection). Every bug found in this project's history — the composite-key join issue, the percentage conversions — was found by manually running against real DB output, not by the test suite.
* No test for tie-breaking when two papers have identical `tc_eff`.
* No test for how much a single new author's data shifts the field average for *other* authors already in that field (relevant given normalization is a "running value" recalculated on every run).

Add new test cases to `test_calculator.py` alongside the existing ones if calculation behavior changes.

---

# 22. Dependencies

The implementation requires:

```text
Python 3.x
Pandas
NumPy
PostgreSQL
PostgreSQL Python database driver
python-dotenv
pytest (for running test_calculator.py)
```

Install the Python packages with:

```bash
pip install pandas numpy psycopg2-binary python-dotenv pytest
```

If the project already has a `requirements.txt`, install using:

```bash
pip install -r requirements.txt
```

Database connection settings are read from a `.env` file (`DB_HOST`, `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_PORT`) by `database.py`.

---

# 23. Calculation Summary

The complete calculation can be summarized as:

```text
author_paper_field_effective_citation
  (career_factor, author_field_weight, capped_adjusted_citation; READY rows)
        +
field_classification (field_weight)
        +
Citation Outlier Cap (150)
        ↓
Effective Citations
  (Eq. 15: career_factor × author_field_weight × capped_adjusted_citation)
        ↓
PASS 1: Per-Author-Field Effective Rank
        (h-index-style threshold condition, Eq. 18/19 numerator)
        ↓
PASS 2: Field-Average Normalization
        (computed internally, a running value, Eq. 19 denominator)
        ↓
Field-Specific Hm (Eq. 19)
        ↓
Weighted Field Hm (Eq. 20: field_weight × Hm'_{f,a})
        ↓
Final Modified Hm-index (Σ weighted_hm / Σ field_weight)
        ↓
author.modified_hm_index
```

---

# 24. Output

The primary Python output is:

```text
author_id
modified_hm_index
```

The final database output is stored in:

```text
author.modified_hm_index
```

The calculation is therefore designed to integrate directly with the existing author database rather than creating a separate result table.

---

## Conclusion

The `modified_hm_index` module provides a database-integrated implementation of the Modified Hm-index.

It:

1. Loads per-(paper, author, field) effective-citation data from
   `author_paper_field_effective_citation` (`READY` rows only), including the
   precomputed `career_factor` and the combined `author_field_weight`.
2. Applies a fixed citation outlier cap (150 citations).
3. Loads paper research fields and field weights from `field_classification`.
4. Merges the two on the `(paper_id, field_id)` composite key.
5. Calculates effective citations (Eq. 15) and per-author-field effective rank
   with an h-index-style threshold condition (Pass 1).
6. Computes field normalization internally as a field-average "running value" of
   every author's own effective rank (Pass 2) — not a stored constant, not a
   percentile of citations.
7. Calculates field-specific Hm values (Eq. 19).
8. Combines multiple fields using field weights (Eq. 20).
9. Produces the final Modified Hm-index and writes it to
   `author.modified_hm_index`.
10. Is covered by a regression test suite (`test_calculator.py`) that validates
    the calculation logic — including hand-derived exact expected values —
    independently of the database.
