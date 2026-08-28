# Modified Hm-Index Calculation

## Overview

This module calculates the **Modified Hm-index** for authors using a modified Hm-index methodology that considers:

* Author career factor
* Author contribution weight
* Capped adjusted citations
* Multiple research fields
* Field-specific normalization
* Field weights

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
└── README.md
```

### File Responsibilities

| File                 | Responsibility                                                           |
| -------------------- | ------------------------------------------------------------------------ |
| `config.py`          | Contains database table and column mappings                              |
| `database.py`        | Creates the PostgreSQL database connection                               |
| `calculator.py`      | Contains the Modified Hm-index calculation logic                         |
| `run_calculation.py` | Loads database data, performs calculations, and updates the author table |
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

The capped adjusted citation value is used in the effective citation calculation.

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

---

# 6. Data Processing Flow

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
        Normalize Wide Tables
                │
                ▼
        Calculate Field Normalization
                │
                ▼
        Calculate Effective Citations
                │
                ▼
        Calculate Field-Specific Hm
                │
                ▼
        Calculate Weighted Hm
                │
                ▼
        Calculate Modified Hm-index
                │
                ▼
        Update author.modified_hm_index
```

---

# 7. Field Normalization

Field normalization is calculated before the Modified Hm-index calculation.

The process is:

1. Join paper fields with citation data.
2. Clean citation values.
3. Group citations by research field.
4. Calculate the **90th percentile** for each field.
5. Store the result as `hm_field_normalization`.
6. Remove normalization values that are not greater than zero.

The resulting DataFrame contains:

```text
field_id
hm_field_normalization
```

This normalization is calculated by `calculate_field_normalization()` in `run_calculation.py`.

---

# 8. Modified Hm-index Calculation

The main calculation is implemented in:

```text
calculator.py
```

The calculator expects five DataFrames:

```python
calculate(
    paper_authors,
    authors,
    paper_citations,
    field_classification,
    field_normalization
)
```

The required columns are validated before calculation begins.

---

## 8.1 Merge Author Contribution and Career Factor

Author contribution data is joined with author career-factor data using:

```text
author_id
```

The resulting data contains:

```text
paper_id
author_id
contribution_weight
career_factor
```

---

## 8.2 Merge Citation Data

Citation information is joined using:

```text
paper_id
```

This adds:

```text
capped_adjusted_citations
```

---

## 8.3 Merge Research Fields

Paper-field information is joined using:

```text
paper_id
```

This adds:

```text
field_id
field_weight
```

---

## 8.4 Merge Field Normalization

Field normalization is joined using:

```text
field_id
```

This adds:

```text
hm_field_normalization
```

The resulting dataset contains all values required for the Modified Hm-index calculation.

---

# 9. Data Validation

The calculator converts the following values to numeric values:

```text
career_factor
contribution_weight
capped_adjusted_citations
field_weight
hm_field_normalization
```

Invalid numeric values are converted to `NaN` and removed.

The calculation only retains records where:

```text
hm_field_normalization > 0
contribution_weight > 0
career_factor > 0
field_weight > 0
```

If no valid records remain, the calculation stops with an error.

This prevents invalid database values from affecting the final index.

---

# 10. Effective Citation Calculation

The implementation calculates effective citations as:

```text
TC_eff =
Career Factor
× Contribution Weight
× Capped Adjusted Citations
```

In Python:

```python
data["tc_eff"] = (
    data["career_factor"]
    * data["contribution_weight"]
    * data["capped_adjusted_citations"]
)
```

The calculated value is stored in:

```text
tc_eff
```

This value is then used to rank papers within each author-field combination.

---

# 11. Field-Specific Hm Calculation

The data is grouped by:

```text
author_id
field_id
```

For each author-field combination, papers are sorted by:

```text
tc_eff
```

in descending order.

The effective contribution for each paper is calculated as:

```text
effective_rank_contribution =
career_factor × contribution_weight
```

Then the cumulative effective contribution is calculated:

```text
r_eff = cumulative sum of effective_rank_contribution
```

The maximum value of `r_eff` is used for the field-specific Hm calculation.

---

# 12. Field-Specific Normalization

For each author-field combination:

```text
Hm'field,author =
Maximum Effective Rank
/
Field Normalization
```

In the implementation:

```python
hm_prime_field_author = (
    max_r_eff
    / normalization
)
```

The result is stored as:

```text
hm_prime_field_author
```

The field-specific result contains:

```text
author_id
field_id
hm_prime_field_author
```

---

# 13. Weighted Hm Across Fields

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

This allows an author who works across multiple research fields to have the field contributions incorporated into the final index.

---

# 14. Final Modified Hm-index

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
STEP 1: Loading database data
STEP 2: Calculating field normalization
STEP 3: Calculating Modified Hm-index
STEP 4: Results summary
STEP 5: Updating author table
```

The runner loads the four required database datasets before performing the calculation.

---

# 16. Console Output

During execution, the program displays:

### Field Normalization

```text
FIELD NORMALIZATION:
field_id    hm_field_normalization
...
```

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
hm_field_normalization
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

A separate database table called:

```text
field_normalization
```

is **not required** by the current implementation.

Field normalization is calculated dynamically in Python from the field classification and citation data. The resulting DataFrame contains:

```text
field_id
hm_field_normalization
```

and is passed directly to the calculator.

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

If field-specific Hm values cannot be calculated:

```text
ValueError:
No field-specific Hm-index values were calculated.
```

### Database Update Failure

If updating the author table fails:

```text
ROLLBACK
```

is performed so that incomplete database updates are avoided.

---

# 21. Dependencies

The implementation requires:

```text
Python 3.x
Pandas
NumPy
PostgreSQL
PostgreSQL Python database driver
```

Install the Python packages with:

```bash
pip install pandas numpy psycopg2-binary
```

If the project already has a `requirements.txt`, install using:

```bash
pip install -r requirements.txt
```

---

# 22. Calculation Summary

The complete calculation can be summarized as:

```text
Author Contribution
        +
Career Factor
        +
Capped Adjusted Citations
        +
Paper Fields
        +
Field Weights
        +
Field Normalization
        ↓
Effective Citations
        ↓
Field-Specific Hm
        ↓
Weighted Field Hm
        ↓
Final Modified Hm-index
        ↓
author.modified_hm_index
```

---

# 23. Output

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
3. Loads capped adjusted citations.
4. Loads paper research fields and field weights.
5. Calculates field normalization using the 90th percentile.
6. Calculates effective citations.
7. Calculates field-specific Hm values.
8. Combines multiple fields using field weights.
9. Produces the final Modified Hm-index.
10. Updates the calculated index in the `author` table.
