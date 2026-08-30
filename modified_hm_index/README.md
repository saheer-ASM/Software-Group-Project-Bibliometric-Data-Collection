# Modified Hm-Index Calculation

## Overview

This module calculates the **Modified Hm-index** for authors using a modified Hm-index methodology that considers:

* Author career factor
* Author contribution weight
* Capped adjusted citations (outlier-capped at a fixed threshold before reaching this calculation — see Section 6)
* Multiple research fields
* Field weights (applied both within each field's calculation and when combining fields)
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

---

## 2. Author Contribution Table

### Database Table

```text
author_contribution_weight
```

### Configuration

```python
'author_contribution_weight': {
    'table': 'author_contribution_weight',
    'paper_id': 'pub_id',

    'author_id_columns': [
        'author1id',
        'author2id',
        ...
        'author10id',
    ],

    'contribution_weight_columns': [
        'author1id_weight',
        'author2id_weight',
        ...
        'author10id_weight',
    ],
}
```

### Required Structure

The table uses a **wide format**, where each paper can contain up to 10 authors.

For example:

```text
pub_id
author1id
author1id_weight
author2id
author2id_weight
...
author10id
author10id_weight
```

The program converts this wide structure into a normalized DataFrame:

```text
paper_id
author_id
contribution_weight
```

Each author position is converted into a separate record. The implementation uses `UNION ALL` to combine all author positions.

`contribution_weight` here is the **position/ordering-based** weight for the author on that paper (e.g. from alphabetical, relative-contribution/harmonic, or CRediT/ACI ordering). It does **not** yet include the paper's field split — that is applied separately via `field_weight` (see Section 5 and Section 8).

> **IMPORTANT — one row per (paper, author), not per (paper, field):** `paper_authors` must contain exactly one row per `(paper_id, author_id)` combination. If an author's contribution row is accidentally duplicated once per field the paper belongs to, the merge in `calculator.py` will silently cross-join and double (or worse) every downstream value for that paper. Field-specific splitting is handled entirely through `field_classification` (Section 5) — never through duplicating rows in `paper_authors`.

> **Note:** `run_calculation.py` divides the raw database value by 100 (`contribution_weight = raw / 100.0`), so the source column is expected to be stored as a percentage (0–100), not already as a proportion (0–1). Confirm this matches your schema before running against a new database.

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
career_compensation
modified_hm_index
```

The database column:

```text
career_compensation
```

is loaded into Python as:

```text
career_factor
```

The final Modified Hm-index is stored in:

```text
modified_hm_index
```

The runner updates this column after the calculation is completed.

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
    'capped_adjusted_citations': 'capped_adjusted_citation',
}
```

### Required Columns

```text
pub_id
capped_adjusted_citation
```

These values are loaded into Python as:

```text
paper_id
capped_adjusted_citations
```

This is the citation value used throughout the calculation — after the outlier cap in Section 6 is applied to it.

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

As with author contributions, the three field positions are combined into one normalized DataFrame using `UNION ALL`.

`field_weight` (V_p^f in the underlying model) is used **twice** in the calculation:

1. Inside the field-specific effective citation and effective rank calculation (Section 8), to scale a multi-field paper's contribution down to its share in that particular field.
2. Again when combining each field's Hm score into the author's overall score (Section 12).

---

# 6. Citation Outlier Cap

Before citations reach the field normalization or the main calculator, a **fixed outlier cap of 150 citations** is applied in `run_calculation.py`:

```python
OUTLIER_CITATION_CAP = 150

def apply_citation_outlier_cap(paper_citations, cap=OUTLIER_CITATION_CAP):
    paper_citations["capped_adjusted_citations"] = (
        paper_citations["capped_adjusted_citations"].clip(upper=cap)
    )
    return paper_citations
```

Any paper's `capped_adjusted_citations` value above 150 is truncated down to 150; values at or below 150 are left unchanged. This is applied once, in `get_data_from_database()`, immediately after citations are loaded — so both the calculator and (indirectly) the field normalization step described in Section 9 operate on already-capped values.

This is a **flat cap applied uniformly across every field** — not a per-field percentile.

---

# 7. Data Processing Flow

The complete calculation follows these steps:

```text
PostgreSQL Database
        │
        ├── author_contribution_weight
        │
        ├── author
        │
        ├── author_paper_field_effective_citation
        │
        └── field_classification
                │
                ▼
        Load Database Data
                │
                ▼
        Apply Outlier Cap (150 citations, Section 6)
                │
                ▼
        Normalize Wide Tables
                │
                ▼
        Calculate Effective Citations (field-weighted, Eq. 15)
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
        Calculate Field-Specific Hm
                │
                ▼
        Calculate Weighted Hm (Eq. 20)
                │
                ▼
        Calculate Modified Hm-index
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
× Contribution Weight
× Field Weight
× Capped Adjusted Citations
```

In Python:

```python
data["tc_eff"] = (
    data["career_factor"]
    * data["contribution_weight"]
    * data["field_weight"]
    * data["capped_adjusted_citations"]
)
```

`field_weight` is included here so that a paper split across multiple fields (e.g. 60% Computer Science, 40% Biomedical Engineering) contributes only its proportional share of citations to each field's calculation, rather than being fully counted in every field it belongs to.

This value is then used to rank papers within each author-field combination.

---

# 9. Field Normalization — Computed Internally (Equations 18–19)

**This is the central design decision in the current implementation, and it differs from earlier drafts of this module.** `Hm'_f` (the field normalization denominator in Equation 19) is **not** supplied as an external input, and is **not** a percentile of raw citations. It is calculated internally, inside `calculator.calculate()`, as a **field average** of every author's own raw effective rank — recalculated fresh from the current dataset on every call ("a running value," not a stored constant).

This decision follows directly from the paper's own text (Sections 2.4.4–2.4.6 describe `Hf'_f`/`Hm'_f`/`G'_f` only as "field normalization," and a companion abstract explicitly describes the analogous `Hf'_f` as "normalized by field average"). The paper's own worked numerical demo (Section 3.3) never shows how its example constants (e.g. `Hm'_f = 3`) were derived — this implementation fills that gap using the "field average" description.

### 9.1 Pass 1 — per author-field effective rank

For each `(author_id, field_id)` combination present in the data, papers are sorted by `tc_eff` descending, and the calculator finds the largest `k` (`k_valid`) such that cumulative effective citations still meet or exceed cumulative effective rank (the same h-index-style threshold condition as before — see Section 11 in earlier revisions of this README):

```python
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

The result of this pass, `max_r_eff`, is the Equation 19 **numerator only** — it is not yet divided by anything.

### 9.2 Pass 2 — field-average normalization

Once every author-field combination has a `max_r_eff`, the calculator groups by `field_id` and takes the **mean**:

```python
field_normalization = (
    author_field_df
    .groupby("field_id")["max_r_eff"]
    .mean()
    .reset_index()
    .rename(columns={"max_r_eff": "hm_field_normalization"})
)
```

Each author's own `max_r_eff` is then divided by their field's average:

```python
author_field_df["hm_prime_field_author"] = (
    author_field_df["max_r_eff"] / author_field_df["hm_field_normalization"]
)
```

### 9.3 What this means in practice

- An author whose contribution is exactly at their field's average scores **1.0** for that field.
- An author above the field average scores **above 1.0**; below average scores **below 1.0**.
- **A field with only one contributing author always normalizes to exactly 1.0** for that author, since the "field average" and the author's own value are identical when there is no one else to compare against. This is expected behavior, not a bug — with no peers, you are the average.
- Authors with zero papers in a field are naturally excluded from that field's average, since they never produce a `max_r_eff` for a field they don't publish in.
- Because this is recalculated from scratch on every run, results for the same author can shift between runs purely because *other authors'* data changed the field average — this is intentional ("a running value"), not instability.

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

This allows an author who works across multiple research fields to have the field contributions incorporated into the final index. Note this is the **second** use of `field_weight` in the calculation (see Section 5) — the first use scales the per-field effective citations and rank (Section 8/9), and this second use weights how much each field's resulting score contributes to the author's overall index.

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
    paper_authors: pd.DataFrame,
    authors: pd.DataFrame,
    paper_citations: pd.DataFrame,
    field_classification: pd.DataFrame,
) -> pd.DataFrame
```

> **Note:** this signature takes **four** DataFrames. There is **no `field_normalization` argument** — earlier drafts of this module took a fifth `field_normalization` DataFrame computed externally; that has been removed, since normalization is now computed internally as described in Section 9.

---

# 14. Data Validation

The calculator converts the following values to numeric values:

```text
career_factor
contribution_weight
capped_adjusted_citations
field_weight
```

Invalid numeric values are converted to `NaN` and removed.

The calculation only retains records where:

```text
contribution_weight > 0
career_factor > 0
field_weight > 0
```

If no valid records remain, the calculation stops with an error.

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

> **Recommended for first runs against a new or changed database:** comment out the `update_authors_table(results)` call in `main()` and inspect `results['modified_hm_index'].describe()` plus a few known authors before allowing the calculation to write to the `author` table. This is especially worth doing after this normalization redesign, since the score's meaning has changed (relative-to-field-average rather than relative-to-a-percentile-of-citations) — existing intuitions about "what a good score looks like" from before this change no longer apply directly.

---

# 16. Console Output

During execution, the program displays:

### Author Calculation Data

The calculator displays the top records according to effective citations:

```text
TOP AUTHOR CALCULATION DATA:
paper_id
author_id
field_id
career_factor
contribution_weight
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

## `author_contribution_weight`

```text
pub_id
author1id
author1id_weight
author2id
author2id_weight
author3id
author3id_weight
author4id
author4id_weight
author5id
author5id_weight
author6id
author6id_weight
author7id
author7id_weight
author8id
author8id_weight
author9id
author9id_weight
author10id
author10id_weight
```

## `author`

```text
author_id
career_compensation
modified_hm_index
```

## `author_paper_field_effective_citation`

```text
pub_id
capped_adjusted_citation
```

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

### Important

**No `field_normalization` table is needed, and no percentile is computed from citation data.** Field normalization is calculated entirely inside `calculator.calculate()` from the same author-contribution and citation data already being loaded — see Section 9.

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

If every field's average effective rank comes out to zero or negative (should not normally happen, since effective rank is built from validated positive inputs):

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
| `test_long_tail_triggers_early_break` | Confirms the Eq. 19 threshold condition (`k_valid`) genuinely stops accumulating papers once cumulative citations fall behind cumulative rank, with the exact expected value hand-derived and asserted (a looser "compare to the unbroken case" assertion was tried first and found unreliable — see the in-file comments) |
| `test_field_weight_applied_inside_field_specific_calc` | Confirms `field_weight` is applied inside the per-field calculation (Eq. 15/18), not only in the final cross-field combination (Eq. 20) |
| `test_eq20_multi_author_multi_field` | A full, hand-verified multi-author, multi-field scenario exercising Pass 1, Pass 2, and the Eq. 20 combination together |
| `test_missing_required_column_raises` | Confirms column validation still raises `ValueError` on malformed input |
| `test_all_rows_filtered_out_raises` | Confirms the calculator fails loudly, rather than silently returning an empty result, when all rows are filtered out during cleaning |

### Not currently covered

* No test exercises `database.py` or `run_calculation.py` directly (these require a live PostgreSQL connection).
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
pytest (for running test_calculator.py)
```

Install the Python packages with:

```bash
pip install pandas numpy psycopg2-binary pytest
```

If the project already has a `requirements.txt`, install using:

```bash
pip install -r requirements.txt
```

---

# 23. Calculation Summary

The complete calculation can be summarized as:

```text
Author Contribution
        +
Career Factor
        +
Capped Adjusted Citations (outlier-capped at 150)
        +
Paper Fields
        +
Field Weights (applied twice: per-field and cross-field)
        ↓
Effective Citations (field-weighted, Eq. 15)
        ↓
PASS 1: Per-Author-Field Effective Rank
        (Threshold Condition, Eq. 18/19 numerator)
        ↓
PASS 2: Field-Average Normalization
        (computed internally, a running value, Eq. 19 denominator)
        ↓
Field-Specific Hm
        ↓
Weighted Field Hm (Eq. 20)
        ↓
Final Modified Hm-index
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

1. Loads author contribution data.
2. Loads author career factors.
3. Loads capped adjusted citations and applies a fixed outlier cap (150 citations).
4. Loads paper research fields and field weights.
5. Calculates field-weighted effective citations and effective rank (Pass 1).
6. Applies an h-index-style threshold condition to determine which papers count per author-field combination.
7. Computes field normalization internally as a field-average "running value" of every author's own effective rank (Pass 2) — not a stored constant, not a percentile of citations.
8. Calculates field-specific Hm values.
9. Combines multiple fields using field weights (Eq. 20).
10. Produces the final Modified Hm-index.
11. Updates the calculated index in the `author` table.
12. Is covered by a regression test suite (`test_calculator.py`) that validates the calculation logic — including hand-derived exact expected values — independently of the database.
