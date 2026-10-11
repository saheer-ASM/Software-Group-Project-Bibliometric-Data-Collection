"""Equation 15 (effective citations) on the LOCAL database.

SQLite port of modified_hf_index/run_equation_15.py (+ calculator + repository).
Same rule, evaluated set-based in SQL (the cloud code loads every row into Python):

    TCadj_eff(f, p, i) = CFcom * W_p^(f,i) * TCadj_cap
        CFcom = author.career_compensation, W and TCadj_cap come from
        citations_per_paper_details (Equation 12/13 stage)
    status = 'READY' if the product exists, else 'MISSING_VALUE'
    (None if any of the three inputs is missing -- same as the cloud calculator)

Needs: eq12_13_14_local and career_compensation_local to be run first.

Run from the OpenAlex_Data_Collection folder:
    python -m eq15_local.run_equation_15 --dry-run
    python -m eq15_local.run_equation_15
"""

import argparse
import time

from .db_connection import get_connection
from .db_setup import create_equation_15_table

SELECT_SQL = """
SELECT
    d.author_id,
    d.pub_id,
    d.field_name,
    a.career_compensation AS career_factor,
    d.author_field_weight,
    d.capped_adjusted_citation,
    a.career_compensation * d.author_field_weight * d.capped_adjusted_citation
        AS effective_citation,
    CASE
        WHEN a.career_compensation IS NOT NULL
         AND d.author_field_weight IS NOT NULL
         AND d.capped_adjusted_citation IS NOT NULL
        THEN 'READY' ELSE 'MISSING_VALUE'
    END AS calculation_status
FROM citations_per_paper_details AS d
JOIN author AS a ON a.author_id = d.author_id
"""


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate Equation 15 effective citations."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Calculate and print a summary without writing to the database.")
    parser.add_argument(
        "--skip-table-setup", action="store_true",
        help="Skip CREATE TABLE / index statements (assume table exists).")
    return parser.parse_args()


def run(*, dry_run: bool = False, skip_table_setup: bool = False) -> None:
    connection = get_connection()
    started = time.time()
    try:
        if not dry_run and not skip_table_setup:
            create_equation_15_table(connection)

        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'citations_per_paper_details'"
        ).fetchone()
        total = (connection.execute(
            "SELECT COUNT(*) FROM citations_per_paper_details").fetchone()[0]
            if exists else 0)
        if not total:
            print("No rows found in citations_per_paper_details. "
                  "Run the Equation 12/13 pipeline first.")
            return

        counts = dict(connection.execute(
            f"SELECT calculation_status, COUNT(*) FROM ({SELECT_SQL}) GROUP BY 1").fetchall())
        ready = counts.get("READY", 0)
        print(f"Equation 15: {sum(counts.values()):,} row(s) processed "
              f"({ready:,} with a usable effective_citation).")

        for row in connection.execute(SELECT_SQL + " LIMIT 10"):
            print(f"  author={row[0]} pub={row[1]} field={row[2]} CFcom={row[3]} "
                  f"W={row[4]} TCcap={row[5]} => TCadj_eff={row[6]} [{row[7]}]")

        if dry_run:
            print("Dry run: no changes written to the database.")
            return

        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO author_paper_field_effective_citation ("
                "author_id, pub_id, field_name, career_factor, author_field_weight, "
                "capped_adjusted_citation, effective_citation, calculation_status) "
                + SELECT_SQL)

        print("Saved Equation 15 results to author_paper_field_effective_citation "
              f"({(time.time() - started) / 60:.1f} min).")

    finally:
        connection.close()


if __name__ == "__main__":
    arguments = parse_arguments()
    run(dry_run=arguments.dry_run, skip_table_setup=arguments.skip_table_setup)
