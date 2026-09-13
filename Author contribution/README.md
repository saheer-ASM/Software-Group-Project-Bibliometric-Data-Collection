# Author Contribution Weight Calculator

Python-based system for calculating and storing author contribution weights for academic publications.

The system determines the author ordering norm and calculates contribution weights based on publication fields and their assigned weights.

## Features

* Detects author ordering as:

  * `alphabetical`
  * `relative`
* Supports publications with up to 10 authors
* Supports up to 3 field classifications per publication
* Calculates equal contributions for alphabetical ordering
* Calculates position-based contributions for relative ordering
* Combines contributions across multiple research fields
* Stores calculated weights in PostgreSQL
* Supports batch processing using offset and limit
* Supports co-first and co-last author parameters in the calculation layer

---

## Project Structure

```text
project/
│
├── author_contribution_calculator.py
├── process_author_contributions.py
├── database.py
└── README.md
```

### `author_contribution_calculator.py`

Contains the `AuthorContributionCalculator` class.

Responsible for:

* Detecting author ordering
* Calculating alphabetical contribution weights
* Calculating relative contribution weights
* Combining field-level contributions
* Returning the final contribution result

### `process_author_contributions.py`

Handles the database processing workflow.

Responsible for:

1. Retrieving publications
2. Retrieving author IDs
3. Retrieving author names
4. Retrieving field weights
5. Calculating contributions
6. Updating the database

### `database.py`

Provides the PostgreSQL database connection through:

```python
get_connection()
```

---

## Processing Flow

```text
PostgreSQL
    │
    ▼
Retrieve Publications
    │
    ▼
Retrieve Author IDs
    │
    ▼
Retrieve Author Names
    │
    ▼
Retrieve Field Weights
    │
    ▼
Detect Author Ordering
    │
    ├── Alphabetical
    │
    └── Relative
    │
    ▼
Calculate Contributions
    │
    ▼
Update PostgreSQL
```

---

## Database Tables

### `author_contribution_weight`

Used to retrieve publication authors and store calculated contribution weights.

Expected columns:

```text
pub_id

author1id
author2id
author3id
author4id
author5id
author6id
author7id
author8id
author9id
author10id

author_ordering_norm

author1id_weight
author2id_weight
author3id_weight
author4id_weight
author5id_weight
author6id_weight
author7id_weight
author8id_weight
author9id_weight
author10id_weight
```

### `author`

Used to retrieve author names from author IDs.

```sql
SELECT author_name
FROM public.author
WHERE author_id = %s;
```

### `field_classification`

Used to retrieve field names and their weights.

Expected fields:

```text
pub_id

field1_name
field1_weight

field2_name
field2_weight

field3_name
field3_weight
```

---

## Author Ordering Detection

The system uses the following rules.

### One or Two Authors

For one or two authors, the ordering is always assumed to be:

```text
relative
```

### Three or More Authors

The author list is compared with an alphabetically sorted version.

For example:

```text
Alice Brown
David Perera
John Smith
```

is detected as:

```text
alphabetical
```

While:

```text
John Smith
Alice Brown
David Perera
```

is detected as:

```text
relative
```

---

## Alphabetical Contribution

For alphabetical ordering, every author receives an equal share of the field weight.

Formula:

```text
Contribution = Field Weight / Number of Authors
```

Example:

```text
Field Weight = 0.6
Authors = 3

Contribution per author = 0.6 / 3
                        = 0.2
```

Result:

```text
Author 1 = 0.2
Author 2 = 0.2
Author 3 = 0.2
```

---

## Relative Contribution

For relative ordering, the contribution is based on author position.

The default position values are:

```text
Author 1 → 1
Author 2 → 2
Author 3 → 3
Author 4 → 4
```

The reciprocal of each position is calculated:

```text
Author 1 → 1 / 1 = 1.0000
Author 2 → 1 / 2 = 0.5000
Author 3 → 1 / 3 = 0.3333
Author 4 → 1 / 4 = 0.2500
```

These values are normalized against their total.

Formula:

```text
Contribution(i) =
(Field Weight × (1 / i))
/
Σ(1 / j)
```

where `j` represents every author position.

This ensures that:

```text
Sum of Author Contributions = Field Weight
```

---

## Field-Based Calculation

A publication can have multiple field weights.

Example:

```python
{
    "Artificial Intelligence": 0.6,
    "Computer Science": 0.3,
    "Data Science": 0.1
}
```

Each field is processed independently.

The resulting author contributions are then added together.

For example:

```text
AI contribution
        +
Computer Science contribution
        +
Data Science contribution
        =
Final Author Contribution
```

The final total should equal the total field weight.

---

## Calculation Result

The calculator returns a structure similar to:

```python
{
    "ordering_norm": "relative",

    "field_weights": {
        "AI": 0.6,
        "Networks": 0.4
    },

    "author_contributions": {
        "Alice": 0.5455,
        "Bob": 0.2727,
        "Charlie": 0.1818
    },

    "detailed_contributions": {
        "AI": {
            "Alice": 0.3273,
            "Bob": 0.1636,
            "Charlie": 0.1091
        },
        "Networks": {
            "Alice": 0.2182,
            "Bob": 0.1091,
            "Charlie": 0.0727
        }
    },

    "total_weight": 1.0
}
```

---

## Database Update

After calculation, the system updates:

```text
author_ordering_norm
```

and:

```text
author1id_weight
author2id_weight
author3id_weight
...
author10id_weight
```

The weights correspond to the author's position.

Example:

```text
author1id = 101
author1id_weight = 0.5455

author2id = 102
author2id_weight = 0.2727

author3id = 103
author3id_weight = 0.1818
```

Unused author positions are stored as `NULL`.

---

## Requirements

* Python 3.9+
* PostgreSQL
* PostgreSQL Python driver (`psycopg2` or equivalent)
* Access to the required database tables

Install the PostgreSQL driver if required:

```bash
pip install psycopg2-binary
```

---

## Database Configuration

Configure the PostgreSQL connection in `database.py`.

Example:

```python
import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="your_database",
        user="your_username",
        password="your_password"
    )
```

For production environments, use environment variables instead of hard-coded credentials.

Example:

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password
```

---

## Running the Program

The script accepts:

```text
offset limit
```

### Process the first 5 publications

```bash
python process_author_contributions.py 0 5
```

### Process 204 publications

```bash
python process_author_contributions.py 0 204
```

### Process the next batch

```bash
python process_author_contributions.py 204 204
```

### Process another batch

```bash
python process_author_contributions.py 408 100
```

If no arguments are supplied, the default values are:

```text
offset = 0
limit = 204
```

Run:

```bash
python process_author_contributions.py
```

---

## Example Output

```text
Processing 5 publications
Offset: 0, Limit: 5

==============================
Processing: PUB001
==============================

Authors:
1 Alice Brown
2 Bob Smith
3 Charlie Perera

Fields:
{'AI': 0.6, 'Networks': 0.4}

Ordering: relative

Contribution:
Alice Brown => 0.545455
Bob Smith => 0.272727
Charlie Perera => 0.181818

Total: 1.0

Updated successfully: PUB001
```

---

## Validation

The most important validation rule is:

```text
Total Author Contribution
=
Total Field Weight
```

For example:

```text
Field 1 = 0.5
Field 2 = 0.3
Field 3 = 0.2

Total Field Weight = 1.0
```

Therefore:

```text
Total Author Contribution = 1.0
```

Always verify this after changing the calculation logic.

---

## Database Verification

After processing, verify the updated records:

```sql
SELECT
    pub_id,
    author_ordering_norm,
    author1id_weight,
    author2id_weight,
    author3id_weight,
    author4id_weight
FROM public.author_contribution_weight
ORDER BY pub_id
LIMIT 20;
```

---

## Testing Recommendation

Before processing the complete dataset, start with a small batch.

```bash
python process_author_contributions.py 0 5
```

Verify:

1. Authors are retrieved correctly
2. Field weights are correct
3. Ordering norm is correct
4. Contribution weights are reasonable
5. Total contribution equals total field weight
6. Database records are updated correctly

Then process a larger batch.

```text
5 publications
      ↓
Verify
      ↓
20 publications
      ↓
Verify
      ↓
Complete dataset
```

---

## Important Assumptions

### Author Limit

The current database structure supports a maximum of 10 authors.

### Field Limit

The current `get_field_weights()` implementation supports a maximum of 3 fields.

### Ordering Detection

Alphabetical ordering is detected only when the complete author list matches the case-insensitive alphabetical order.

### One or Two Authors

One or two authors are always treated as relative ordering.

### Missing Authors

NULL author IDs are removed before calculation.

### Missing Field Classification

Publications without field classification are skipped.

---

## Co-First and Co-Last Authors

The calculation layer supports:

```python
core_first_indices
core_last_indices
```

These can be used to represent groups such as:

* Co-first authors
* Co-last authors

The current publication-processing workflow does not provide these values, so normal positional weighting is used by default.

---

## Important Safety Note

This program performs database `UPDATE` operations.

Before processing the complete dataset:

1. Back up the database.
2. Run a small test batch.
3. Verify the calculated values.
4. Confirm the database updates.
5. Process the complete dataset.

Recommended workflow:

```text
Database Backup
      ↓
Process 5 Records
      ↓
Validate
      ↓
Process 20 Records
      ↓
Validate
      ↓
Process Complete Dataset
```

---

## Troubleshooting

### `No authors found`

Possible causes:

* Author IDs are NULL
* Publication has no registered authors
* Author data is incomplete

Check:

```sql
SELECT *
FROM public.author_contribution_weight
WHERE pub_id = '<PUB_ID>';
```

---

### Author Name Not Found

Check:

```sql
SELECT *
FROM public.author
WHERE author_id = '<AUTHOR_ID>';
```

---

### `No field classification found`

Check:

```sql
SELECT *
FROM public.field_classification
WHERE pub_id = '<PUB_ID>';
```

---

### PostgreSQL Connection Error

Check:

* PostgreSQL is running
* Host is correct
* Port is correct
* Database name is correct
* Username is correct
* Password is correct

Default PostgreSQL port:

```text
5432
```

---

## Future Improvements

Potential improvements include:

* Support more than 10 authors
* Support more than 3 fields
* Improve database connection management
* Use connection pooling
* Retrieve author names using batch queries
* Add transaction rollback handling
* Add structured logging
* Add unit tests
* Add integration tests
* Add input validation
* Add contribution validation
* Add dry-run mode
* Add progress reporting
* Add calculation reports
* Improve alphabetical ordering detection
* Handle identical author names
* Support co-first and co-last authors more explicitly
* Move configuration to environment variables
* Add automated database validation

---

## Core Calculation Summary

### Alphabetical Ordering

```text
Contribution per Author
=
Field Weight / Number of Authors
```

### Relative Ordering

```text
Position Value = 1 / Author Position
```

Then:

```text
Author Contribution
=
(Field Weight × Position Value)
/
Sum of All Position Values
```

### Final Contribution

```text
Final Author Contribution
=
Sum of Contributions Across All Fields
```

### Main Validation Rule

```text
Σ Author Contributions
=
Σ Field Weights
```

---

## Quick Reference

| Function                                 | Purpose                                   |
| ---------------------------------------- | ----------------------------------------- |
| `detect_ordering_norm()`                 | Detects alphabetical or relative ordering |
| `calculate_alphabetical_weights()`       | Calculates equal author contributions     |
| `calculate_relative_weights()`           | Calculates position-based contributions   |
| `calculate_total_author_contributions()` | Combines all field contributions          |
| `get_publications()`                     | Retrieves publication and author IDs      |
| `get_author_name()`                      | Retrieves author name from ID             |
| `get_field_weights()`                    | Retrieves field classification weights    |
| `update_author_weights()`                | Stores calculated weights                 |
| `process_publications()`                 | Runs the complete processing workflow     |

---

## Summary

The Author Contribution Weight Calculator processes academic publication data by combining:

```text
Publication
    +
Author Information
    +
Author Ordering
    +
Field Classification
    +
Field Weights
        ↓
Author Contribution Calculation
        ↓
Contribution Weights
        ↓
PostgreSQL
```

The system's primary goal is to provide a consistent and reproducible method for calculating author contribution weights while preserving the calculated results in the publication database.
