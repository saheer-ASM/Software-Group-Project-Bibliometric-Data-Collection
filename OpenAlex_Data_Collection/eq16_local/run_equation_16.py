"""Equation 16 (field-level modified h-index) on the LOCAL database.

SQLite port of eq16_field_hindex (run_equation_16 + calculator + repository). Same
rules, evaluated set-based in SQL (the cloud code loads every row into Python):

    raw_h(a,f)  = max(h : TCadj_eff of the h-th best paper of author a in field f >= h)
                  (papers sorted by effective_citation, descending)
    Hf_f        = average of raw_h over every author that has >= 1 paper in field f
                  (same ASSUMPTION as the cloud calculator.compute_field_normalization)
    Hf_{f,a}    = raw_h / Hf_f      (status ZERO_FIELD_NORMALIZATION if Hf_f = 0)

Source: author_paper_field_effective_citation (Equation 15), rows with a non-NULL
effective_citation only. Needs eq15_local to be run first.

Run from the OpenAlex_Data_Collection folder:
    python -m eq16_local.run_equation_16 --dry-run
    python -m eq16_local.run_equation_16
"""

import argparse
import time

from .db_connection import get_connection
from .db_setup import create_equation_16_table

RAW_H_TEMPLATE = """
SELECT
    author_id,
    field_name,
    MAX(CASE WHEN effective_citation >= rn THEN rn ELSE 0 END) AS raw_h_value,
    COUNT(*) AS papers_used
FROM (
    SELECT author_id, field_name, effective_citation,
           ROW_NUMBER() OVER (
               PARTITION BY author_id, field_name
               ORDER BY effective_citation DESC
           ) AS rn
    FROM author_paper_field_effective_citation
    WHERE effective_citation IS NOT NULL{cohort_filter}
)
GROUP BY author_id, field_name
"""

COHORT_FILTER = {
    "all": "",
    "done": " AND author_id IN (SELECT author_id FROM author WHERE pub_finished = 'done')",
}
RAW_H_SQL = RAW_H_TEMPLATE.format(cohort_filter="")

RESULT_SQL = """
SELECT
    r.author_id,
    r.field_name,
    r.raw_h_value,
    r.papers_used,
    n.field_normalization,
    CASE WHEN n.field_normalization IS NULL OR n.field_normalization = 0
         THEN NULL
         ELSE CAST(r.raw_h_value AS REAL) / n.field_normalization END AS modified_hindex_field,
    CASE WHEN n.field_normalization IS NULL OR n.field_normalization = 0
         THEN 'ZERO_FIELD_NORMALIZATION' ELSE 'READY' END AS calculation_status
FROM tmp_eq16_raw AS r
JOIN tmp_eq16_norm AS n ON n.field_name = r.field_name
"""


def parse_arguments():
    parser = argparse.ArgumentParser(description="Calculate Equation 16.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-table-setup", action="store_true")
    parser.add_argument("--cohort", choices=["all", "done"], default="all",
                        help="all authors (cloud behaviour) or only pub_finished = done authors")
    return parser.parse_args()


def run(*, dry_run=False, skip_table_setup=False, cohort="all"):
    connection = get_connection()
    started = time.time()

    def stamp(message):
        print(f"[{(time.time() - started) / 60:5.1f} min] {message}", flush=True)

    try:
        if not dry_run and not skip_table_setup:
            create_equation_16_table(connection)

        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'author_paper_field_effective_citation'"
        ).fetchone()
        rows = (connection.execute(
            "SELECT COUNT(*) FROM author_paper_field_effective_citation "
            "WHERE effective_citation IS NOT NULL").fetchone()[0] if exists else 0)
        if not rows:
            print("No rows found in author_paper_field_effective_citation. "
                  "Run the Equation 15 pipeline first.")
            return
        stamp(f"{rows:,} effective-citation rows")

        connection.execute("DROP TABLE IF EXISTS temp.tmp_eq16_raw")
        connection.execute("DROP TABLE IF EXISTS temp.tmp_eq16_norm")
        connection.execute("CREATE TEMP TABLE tmp_eq16_raw AS " + RAW_H_TEMPLATE.format(
            cohort_filter=COHORT_FILTER[cohort]))
        stamp("raw h-values per (author, field) computed")
        connection.execute(
            "CREATE TEMP TABLE tmp_eq16_norm AS "
            "SELECT field_name, AVG(raw_h_value) AS field_normalization "
            "FROM tmp_eq16_raw GROUP BY field_name")

        counts = dict(connection.execute(
            f"SELECT calculation_status, COUNT(*) FROM ({RESULT_SQL}) GROUP BY 1").fetchall())
        ready = counts.get("READY", 0)
        stamp(f"Equation 16: {sum(counts.values()):,} (author, field) row(s) processed "
              f"({ready:,} READY).")

        for r in connection.execute(RESULT_SQL + " LIMIT 10"):
            print(f"  author={r[0]} field={r[1]} raw_h={r[2]} papers={r[3]} "
                  f"norm={r[4]} => Hf_f,a={r[5]} [{r[6]}]")

        if dry_run:
            print("Dry run: no changes written.")
            return

        with connection:
            if cohort != "all":
                connection.execute("DELETE FROM author_field_modified_hindex")  # no mixed populations
            connection.execute(
                "INSERT OR REPLACE INTO author_field_modified_hindex (author_id, "
                "field_name, raw_h_value, papers_used, field_normalization, "
                "modified_hindex_field, calculation_status) " + RESULT_SQL)
        stamp("Saved to author_field_modified_hindex.")

    finally:
        connection.close()


if __name__ == "__main__":
    arguments = parse_arguments()
    run(dry_run=arguments.dry_run, skip_table_setup=arguments.skip_table_setup,
        cohort=arguments.cohort)
