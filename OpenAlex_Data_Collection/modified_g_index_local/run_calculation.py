"""Equations 20, 21, 22 (modified g-index) on the LOCAL database.

SQLite port of Modified_G_Index (run_calculation + calculator). The cloud code loads
every row into pandas; the same rules are evaluated set-based in SQLite (window
functions) because the local data has tens of millions of rows. Rules, unchanged:

  source rows : author_paper_field_effective_citation with calculation_status = 'READY'
                and a non-NULL capped_adjusted_citation (Equation 15 output)
  fixed cap   : capped_adjusted_citation is clipped at OUTLIER_CITATION_CAP = 150
  fields      : field_classification unpivoted, field_weight = weight / 100
  join/clean  : inner join on (paper, field); author_field_weight, career_factor,
                field_weight must all be > 0
  Eq 15       : tc_eff = career_factor * author_field_weight * capped_citation
  Eq 20       : A_eff(k) = cumulative sum of tc_eff, papers of one (author, field)
                sorted by tc_eff descending
  Eq 21       : g_raw    = largest k with A_eff(k) >= k^2   (0 if none)
                G_f      = mean of g_raw over all authors in field f  (kept if > 0)
                G_{f,a}  = g_raw / G_f
  Eq 22       : G_a = sum(field_weight * G_{f,a}) / sum(field_weight)  (0 if denominator 0)

Writes author.modified_g_index (new column) and modified_g_index_results, exactly as
the cloud script does.

Needs eq15_local to be run first.

Run from the OpenAlex_Data_Collection folder:
    python -m modified_g_index_local.db_setup            # once (or skip: run creates them)
    python -m modified_g_index_local.run_calculation --dry-run
    python -m modified_g_index_local.run_calculation
"""

import argparse
import time
from datetime import datetime

from .db_connection import get_connection
from .db_setup import create_modified_g_index_tables

OUTLIER_CITATION_CAP = 150


def _fields() -> str:
    return "\n UNION ALL \n".join(
        f"SELECT pub_id AS paper_id, field{n}_name AS field_id, "
        f"field{n}_weight / 100.0 AS field_weight FROM field_classification "
        f"WHERE field{n}_name IS NOT NULL AND field{n}_weight IS NOT NULL"
        for n in (1, 2, 3))


STEPS = [
    "DROP TABLE IF EXISTS temp.tmp_g_fields",
    "DROP TABLE IF EXISTS temp.tmp_g_author_field",
    "DROP TABLE IF EXISTS temp.tmp_g_norm",
    "DROP TABLE IF EXISTS temp.tmp_g_result",

    f"CREATE TEMP TABLE tmp_g_fields AS {_fields()}",
    "CREATE INDEX temp.idx_tmp_g_fields ON tmp_g_fields(paper_id, field_id)",

    # Equation 20 (cumulative effective citations) and the Equation 21 numerator:
    # cum(k) - k^2 is concave in k, so the satisfied k form the run 1..g; the largest
    # satisfied rank is therefore the cloud's "leading run" k_valid.
    f"""
    CREATE TEMP TABLE tmp_g_author_field AS
    SELECT
        author_id, field_id,
        COALESCE(MAX(CASE WHEN cum_tc_eff >= rn * rn THEN rn END), 0) AS g_field_raw,
        SUM(field_weight) AS field_weight_sum
    FROM (
        SELECT
            author_id, field_id, field_weight,
            ROW_NUMBER() OVER w AS rn,
            SUM(tc_eff) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_tc_eff
        FROM (
            SELECT
                e.author_id,
                e.field_name AS field_id,
                f.field_weight,
                e.career_factor * e.author_field_weight
                    * MIN(e.capped_adjusted_citation, {float(OUTLIER_CITATION_CAP)}) AS tc_eff
            FROM author_paper_field_effective_citation AS e
            JOIN tmp_g_fields AS f
              ON f.paper_id = e.pub_id AND f.field_id = e.field_name
            WHERE e.calculation_status = 'READY'
              AND e.capped_adjusted_citation IS NOT NULL
              AND e.author_field_weight > 0
              AND e.career_factor > 0
              AND f.field_weight > 0
        )
        WINDOW w AS (PARTITION BY author_id, field_id ORDER BY tc_eff DESC)
    )
    GROUP BY author_id, field_id
    """,
    "CREATE INDEX temp.idx_tmp_g_af ON tmp_g_author_field(field_id)",

    # G_f = running mean of g_raw per field, kept only if > 0
    """
    CREATE TEMP TABLE tmp_g_norm AS
    SELECT field_id, AVG(g_field_raw) AS g_field_normalization
    FROM tmp_g_author_field
    GROUP BY field_id
    HAVING AVG(g_field_raw) > 0
    """,

    # Equation 21 -> Equation 22, plus the bookkeeping counts of the cloud results table
    """
    CREATE TEMP TABLE tmp_g_result AS
    SELECT
        t.author_id,
        t.field_row_count,
        t.included_field_row_count,
        t.field_row_count - t.included_field_row_count AS skipped_field_row_count,
        t.field_weight_total,
        t.weighted_g_sum,
        CASE WHEN t.field_weight_total <> 0
             THEN t.weighted_g_sum / t.field_weight_total ELSE 0 END AS modified_g_index,
        CASE WHEN t.field_weight_total > 0 THEN 1 ELSE 0 END AS calculation_complete
    FROM (
        SELECT
            af.author_id,
            COUNT(*) AS field_row_count,
            COUNT(n.field_id) AS included_field_row_count,
            COALESCE(SUM(CASE WHEN n.field_id IS NOT NULL THEN af.field_weight_sum END), 0)
                AS field_weight_total,
            COALESCE(SUM(CASE WHEN n.field_id IS NOT NULL
                 THEN af.field_weight_sum * (af.g_field_raw / n.g_field_normalization) END), 0)
                AS weighted_g_sum
        FROM tmp_g_author_field AS af
        LEFT JOIN tmp_g_norm AS n ON n.field_id = af.field_id
        GROUP BY af.author_id
        HAVING COUNT(n.field_id) > 0
    ) AS t
    """,
    "CREATE UNIQUE INDEX temp.idx_tmp_g_result ON tmp_g_result(author_id)",
]


def parse_arguments():
    parser = argparse.ArgumentParser(description="Modified g-index (Eq 20-22), local database.")
    parser.add_argument("--dry-run", action="store_true",
                        help="calculate and print a summary, write nothing")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    print()
    print("=" * 60)
    print("MODIFIED G-INDEX CALCULATION")
    print("=" * 60)
    print(f"Started: {datetime.now()}")

    connection = get_connection()
    started = time.time()

    def stamp(message):
        print(f"[{(time.time() - started) / 60:5.1f} min] {message}", flush=True)

    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'author_paper_field_effective_citation'"
        ).fetchone()
        if not exists:
            print("author_paper_field_effective_citation not found. "
                  "Run the Equation 15 pipeline first.")
            return

        print("\nSTEP 1/3: Calculating (author, field) raw g-values ...")
        for number, statement in enumerate(STEPS, start=1):
            connection.execute(statement)
            if "CREATE TEMP TABLE" in statement:
                stamp(f"step {number}/{len(STEPS)} done")

        count, mean, low, high, nonzero = connection.execute(
            "SELECT COUNT(*), AVG(modified_g_index), MIN(modified_g_index), "
            "MAX(modified_g_index), SUM(modified_g_index > 0) FROM tmp_g_result").fetchone()
        if not count:
            print("No valid data remains after cleaning (or no field has a positive "
                  "average raw g-index).")
            return

        print(f"\n  Calculated Modified g-index for {count:,} authors")
        print("\nRESULTS SUMMARY")
        print("-" * 60)
        print(f"Total authors: {count:,}")
        print(f"Average Modified g-index: {mean:.4f}")
        print(f"Minimum Modified g-index: {low:.4f}")
        print(f"Maximum Modified g-index: {high:.4f}")
        print(f"Authors with a non-zero Modified g-index: {nonzero:,} / {count:,}")
        print("\nTop 5 Authors:")
        for author_id, value in connection.execute(
                "SELECT author_id, modified_g_index FROM tmp_g_result "
                "ORDER BY modified_g_index DESC LIMIT 5"):
            print(f"  Author {author_id}: {value:.4f}")

        if arguments.dry_run:
            print("\nDry run: nothing written to the database.")
            return

        print("\nSTEP 2/3: Updating author table ...")
        with connection:
            columns = [r[1] for r in connection.execute("PRAGMA table_info(author)")]
            if "modified_g_index" not in columns:
                connection.execute("ALTER TABLE author ADD COLUMN modified_g_index REAL")
            connection.execute(
                "UPDATE author SET modified_g_index = "
                "(SELECT r.modified_g_index FROM tmp_g_result r "
                " WHERE r.author_id = author.author_id) "
                "WHERE author_id IN (SELECT author_id FROM tmp_g_result)")
        stamp(f"Successfully updated {count:,} authors.")

        print("\nSTEP 3/3: Populating modified_g_index_results ...")
        create_modified_g_index_tables(connection)
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO modified_g_index_results (author_id, "
                "field_row_count, included_field_row_count, skipped_field_row_count, "
                "field_weight_total, weighted_g_sum, modified_g_index, "
                "calculation_complete, calculated_at) "
                "SELECT author_id, field_row_count, included_field_row_count, "
                "skipped_field_row_count, field_weight_total, "
                "weighted_g_sum, modified_g_index, "
                "calculation_complete, CURRENT_TIMESTAMP FROM tmp_g_result")
        stamp(f"Wrote {count:,} row(s) to modified_g_index_results.")

        print()
        print("=" * 60)
        print("MODIFIED G-INDEX CALCULATION COMPLETE")
        print("=" * 60)
        print(f"Completed: {datetime.now()}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
