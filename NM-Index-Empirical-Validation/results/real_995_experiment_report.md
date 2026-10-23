# Real 995-author experiment report

> **Superseded.** This 2026-10-19 preflight predates the SQLite-backed run of
> 2026-10-22 (`results/run_20261022T153122834180Z/`). See
> [final_995_experiment_review.md](final_995_experiment_review.md) for the
> current assessment.

**Status: REAL_EXPERIMENT_BLOCKED**

Generated: 2026-10-19T08:58:25.556024+00:00. The fixed cohort contains 995 rows and 995 unique,
nonblank IDs. SHA-256 of unchanged `995_authors.csv`: `c704eeaa45602c445160d27ba07f07c9c123cf1145b9d8edc6b5855d80b651e9`.

## Cohort and database readiness

- Selected: 995; matched: 8; missing IDs: 987.
- Matched IDs: A5044182686, A5010244939, A5002072930, A5004065644, A5050803432, A5080607818, A5050585435, A5054657936. The complete unmatched ID list is in
  `real_995_missing_ids.csv` when the ID gate fails.
- Stop reason: `COHORT_ID_MISMATCH`.
- The validation project's SELECT-only database interface was used for the
  exact-ID query. It enforces a read-only transaction, rollback, and close.
- The database identity, publication portfolios, citation edges, author lists,
  contribution, career data, stored NM components, and original 100,000-author
  reference could not be certified at this gate.

## Eligibility and exclusions

No author was processed in an analysis. 987 IDs failed the exact database match; the 8 matched IDs were not assessed further. The companion CSV
records each author's status.

## Data coverage and missing data

Publication, citation, coauthor, field, year, contribution, self-citation,
career, stored NM/component, and 100,000-author reference coverage are all
**NOT VERIFIED**. No missing value was converted to zero.

## RQ1–RQ11 and sensitivity

| Analysis | Result |
|---|---|
| RQ1 | NOT RUN — mandatory database gate failed |
| RQ2 | NOT RUN — mandatory database gate failed |
| RQ3 | NOT RUN — mandatory database gate failed |
| RQ4 | NOT RUN — mandatory database gate failed |
| RQ5 | NOT RUN — mandatory database gate failed |
| RQ6 | NOT RUN — mandatory database gate failed |
| RQ7 | NOT RUN — mandatory database gate failed |
| RQ8 | NOT RUN — mandatory database gate failed |
| RQ9 | NOT RUN — mandatory database gate failed |
| RQ10 | NOT RUN — mandatory database gate failed |
| RQ11 | NOT RUN — mandatory database gate failed |
| Sensitivity | NOT RUN — mandatory database gate failed |

No real-data counterfactual scenario, baseline, statistical test, or figure
was run. The only outputs are this preflight report and
`real_995_data_readiness.csv`.

## Methodology and limitations

Execution also requires independently verified complete portfolios and the
original frozen 100,000-author benchmark. The current RQ7 implementation
explicitly lacks a complete independent NM counterfactual calculator, as
documented in the project README and `experiments/rq07_gaming_sensitivity.py`.
Those gates cannot be bypassed by stored aggregate citation counts.

## Reproducibility and safety

- Cohort identifier: `995_authors.csv`; hash above; no sampling or edits.
- Python version: `3.14.2`.
- Database identity and benchmark version: **NOT VERIFIED**.
- Methodology: latest lecturer documents and `results/lecturer_approved_methodology.md`.
- Output manifest: `results/real_995_data_readiness.csv` (995 data rows),
  `results/real_995_missing_ids.csv` (if any unmatched IDs were verified),
  `results/real_995_experiment_report.md` (this report).
- No metric calculations, production application edits, database-writing SQL,
  migrations, commits, or pushes were performed by this preflight.
