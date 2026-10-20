"""Fail-closed, read-only ID gate for the fixed 995-author experiment.

This does not calculate metrics. It records the first mandatory gate before
portfolio, benchmark, or counterfactual work may begin.
"""

import csv
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from .database import DatabaseAccessError, execute_select
from .phase6_readiness import COHORT, RESULTS, read_cohort


def main():
    cohort, ids = read_cohort()
    digest = hashlib.sha256(COHORT.read_bytes()).hexdigest()
    timestamp = datetime.now(timezone.utc).isoformat()
    found = None
    reason = ""
    try:
        rows = execute_select(
            "SELECT author_id, author_name FROM public.author WHERE author_id = ANY(%s)",
            (ids,),
        )
        found = {str(row["author_id"]): row["author_name"] for row in rows}
        if len(found) != len(ids):
            reason = "COHORT_ID_MISMATCH"
        else:
            reason = "FURTHER_DATA_AND_METHODOLOGY_GATES_NOT_VERIFIED"
    except (DatabaseAccessError, ValueError) as error:
        reason = "DATABASE_CONNECTION_UNAVAILABLE"
        error_class = type(error).__name__

    RESULTS.mkdir(exist_ok=True)
    columns = [
        "author_id", "author_name", "publication_count", "citation_edge_count",
        "coauthor_data_available", "field_data_available", "year_data_available",
        "contribution_data_available", "self_citation_data_available",
        "nm_data_available", "eligible", "exclusion_reason",
    ]
    path = RESULTS / "real_995_data_readiness.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in cohort:
            author_id = row["author_id"].strip()
            matched = found is not None and author_id in found
            gate = (
                "DATABASE_CONNECTION_UNAVAILABLE" if found is None else
                "AUTHOR_ID_NOT_FOUND" if not matched else
                "PORTFOLIO_AND_REFERENCE_NOT_YET_VERIFIED"
            )
            writer.writerow({
                "author_id": author_id,
                "author_name": row["author_name"],
                "publication_count": "NOT_CHECKED",
                "citation_edge_count": "NOT_CHECKED",
                "coauthor_data_available": "NOT_CHECKED",
                "field_data_available": "NOT_CHECKED",
                "year_data_available": "NOT_CHECKED",
                "contribution_data_available": "NOT_CHECKED",
                "self_citation_data_available": "NOT_CHECKED",
                "nm_data_available": "NOT_CHECKED",
                "eligible": "NO" if found is not None and not matched else "NOT_DETERMINED",
                "exclusion_reason": gate,
            })

    missing = [author_id for author_id in ids if found is not None and author_id not in found]
    missing_set = set(missing)
    if found is not None and missing:
        with (RESULTS / "real_995_missing_ids.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["author_id", "author_name"])
            writer.writeheader()
            writer.writerows(row for row in cohort if row["author_id"].strip() in missing_set)
    matched_count = "NOT_VERIFIED" if found is None else str(len(found))
    missing_list = "NOT_VERIFIED" if found is None else str(len(missing))
    matched_list = "NOT_VERIFIED" if found is None else (", ".join(author_id for author_id in ids if author_id in found) or "None")
    exclusion_detail = (
        "Database matching could not be verified; eligibility is undetermined for all 995."
        if found is None else
        f"{len(missing)} IDs failed the exact database match; the {len(found)} matched IDs were not assessed further."
    )
    error_detail = f" Connection error class: `{error_class}`; SQLSTATE unavailable." if found is None else ""
    report = f"""# Real 995-author experiment report

**Status: REAL_EXPERIMENT_BLOCKED**

Generated: {timestamp}. The fixed cohort contains 995 rows and 995 unique,
nonblank IDs. SHA-256 of unchanged `995_authors.csv`: `{digest}`.

## Cohort and database readiness

- Selected: 995; matched: {matched_count}; missing IDs: {missing_list}.
- Matched IDs: {matched_list}. The complete unmatched ID list is in
  `real_995_missing_ids.csv` when the ID gate fails.
- Stop reason: `{reason}`.{error_detail}
- The validation project's SELECT-only database interface was used for the
  exact-ID query. It enforces a read-only transaction, rollback, and close.
- The database identity, publication portfolios, citation edges, author lists,
  contribution, career data, stored NM components, and original 100,000-author
  reference could not be certified at this gate.

## Eligibility and exclusions

No author was processed in an analysis. {exclusion_detail} The companion CSV
records each author's status.

## Data coverage and missing data

Publication, citation, coauthor, field, year, contribution, self-citation,
career, stored NM/component, and 100,000-author reference coverage are all
**NOT VERIFIED**. No missing value was converted to zero.

## RQ1–RQ11 and sensitivity

| Analysis | Result |
|---|---|
{chr(10).join(f'| RQ{i} | NOT RUN — mandatory database gate failed |' for i in range(1, 12))}
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
- Python version: `{sys.version.split()[0]}`.
- Database identity and benchmark version: **NOT VERIFIED**.
- Methodology: latest lecturer documents and `results/lecturer_approved_methodology.md`.
- Output manifest: `results/real_995_data_readiness.csv` (995 data rows),
  `results/real_995_missing_ids.csv` (if any unmatched IDs were verified),
  `results/real_995_experiment_report.md` (this report).
- No metric calculations, production application edits, database-writing SQL,
  migrations, commits, or pushes were performed by this preflight.
"""
    (RESULTS / "real_995_experiment_report.md").write_text(report, encoding="utf-8")
    print(f"status=REAL_EXPERIMENT_BLOCKED selected=995 matched={matched_count} reason={reason}")


if __name__ == "__main__":
    main()
