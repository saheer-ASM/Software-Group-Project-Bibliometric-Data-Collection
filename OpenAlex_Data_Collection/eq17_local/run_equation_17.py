"""Equation 17 (final modified hf-index) on the LOCAL database.

SQLite port of eq17_modified_hindex (run_equation_17 + calculator + repository).
Same rules, evaluated set-based in SQL:

    Vf_p            = field weight / 100   (every field of every paper, from field_classification)
    field_weight_sum(a,f) = sum over the author's papers p of Vf_p
                      (authorship pairs come from author_contribution_weight, authors 1..10)
    numerator   = sum_f field_weight_sum(a,f) * Hf_{f,a}
    denominator = sum_f field_weight_sum(a,f)
                  -- only fields where Equation 16 produced a value (same note as cloud)
    Hf_a        = numerator / denominator  (NULL / 'NO_ELIGIBLE_FIELDS' if denominator = 0)

Needs eq16_local to be run first.

Run from the OpenAlex_Data_Collection folder:
    python -m eq17_local.run_equation_17 --dry-run
    python -m eq17_local.run_equation_17
"""

import argparse
import time

from .db_connection import get_connection
from .db_setup import create_equation_17_table


def _authors() -> str:
    return "\n UNION ALL \n".join(
        f"SELECT pub_id, author{n}id AS author_id FROM author_contribution_weight "
        f"WHERE author{n}id IS NOT NULL" for n in range(1, 11))


def _fields() -> str:
    return "\n UNION ALL \n".join(
        f"SELECT pub_id, field{n}_name AS field_name, field{n}_weight / 100.0 AS field_weight "
        f"FROM field_classification "
        f"WHERE field{n}_name IS NOT NULL AND field{n}_weight IS NOT NULL" for n in (1, 2, 3))


PREPARE = [
    "DROP TABLE IF EXISTS temp.tmp_eq17_paper_authors",
    "DROP TABLE IF EXISTS temp.tmp_eq17_author_field_weight",
    f"CREATE TEMP TABLE tmp_eq17_paper_authors AS {_authors()}",
    "CREATE INDEX temp.idx_tmp_eq17_pa ON tmp_eq17_paper_authors(pub_id)",
    f"""
    CREATE TEMP TABLE tmp_eq17_author_field_weight AS
    WITH paper_fields AS ({_fields()})
    SELECT pa.author_id, pf.field_name, SUM(pf.field_weight) AS field_weight_sum
    FROM tmp_eq17_paper_authors AS pa
    JOIN paper_fields AS pf ON pf.pub_id = pa.pub_id
    GROUP BY pa.author_id, pf.field_name
    """,
    "CREATE INDEX temp.idx_tmp_eq17_afw ON tmp_eq17_author_field_weight(author_id, field_name)",
]

RESULT_SQL = """
SELECT
    author_id,
    weighted_numerator_sum,
    total_field_weight_sum,
    CASE WHEN total_field_weight_sum = 0 THEN NULL
         ELSE weighted_numerator_sum / total_field_weight_sum END AS modified_hindex_final,
    field_count,
    CASE WHEN total_field_weight_sum = 0 THEN 'NO_ELIGIBLE_FIELDS' ELSE 'READY' END
        AS calculation_status
FROM (
    SELECT
        afw.author_id,
        COALESCE(SUM(CASE WHEN h.modified_hindex_field IS NOT NULL
                          THEN COALESCE(afw.field_weight_sum, 0) * h.modified_hindex_field
                     END), 0) AS weighted_numerator_sum,
        COALESCE(SUM(CASE WHEN h.modified_hindex_field IS NOT NULL
                          THEN COALESCE(afw.field_weight_sum, 0) END), 0)
            AS total_field_weight_sum,
        COUNT(h.modified_hindex_field) AS field_count
    FROM tmp_eq17_author_field_weight AS afw
    LEFT JOIN author_field_modified_hindex AS h
           ON h.author_id = afw.author_id AND h.field_name = afw.field_name
    GROUP BY afw.author_id
)
"""


def parse_arguments():
    parser = argparse.ArgumentParser(description="Calculate Equation 17 (final Hf_a).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-table-setup", action="store_true")
    return parser.parse_args()


def run(*, dry_run=False, skip_table_setup=False):
    connection = get_connection()
    started = time.time()

    def stamp(message):
        print(f"[{(time.time() - started) / 60:5.1f} min] {message}", flush=True)

    try:
        if not dry_run and not skip_table_setup:
            create_equation_17_table(connection)

        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'author_field_modified_hindex'").fetchone()
        if not exists or not connection.execute(
                "SELECT 1 FROM author_field_modified_hindex LIMIT 1").fetchone():
            print("No Equation 16 results found. Run the Equation 16 pipeline first.")
            return

        for number, statement in enumerate(PREPARE, start=1):
            connection.execute(statement)
            if "CREATE TEMP TABLE" in statement:
                stamp(f"prepared temp table (step {number}/{len(PREPARE)})")

        counts = dict(connection.execute(
            f"SELECT calculation_status, COUNT(*) FROM ({RESULT_SQL}) GROUP BY 1").fetchall())
        if not counts:
            print("No authorship/field data found. Check author_contribution_weight "
                  "and field_classification.")
            return
        stamp(f"Equation 17: {sum(counts.values()):,} author(s) processed "
              f"({counts.get('READY', 0):,} READY).")

        for r in connection.execute(
                RESULT_SQL + " ORDER BY modified_hindex_final IS NULL, "
                             "modified_hindex_final DESC LIMIT 10"):
            print(f"  author={r[0]} fields_used={r[4]} num={r[1]} denom={r[2]} "
                  f"=> Hf_a={r[3]} [{r[5]}]")

        if dry_run:
            print("Dry run: no changes written.")
            return

        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO author_modified_hindex (author_id, "
                "weighted_numerator_sum, total_field_weight_sum, modified_hindex_final, "
                "field_count, calculation_status) " + RESULT_SQL)
        stamp("Saved to author_modified_hindex -- your final modified H-index.")

    finally:
        connection.close()


if __name__ == "__main__":
    arguments = parse_arguments()
    run(dry_run=arguments.dry_run, skip_table_setup=arguments.skip_table_setup)
