"""Equations 18, 19, 20 (modified hm-index) on the LOCAL database.

SQLite port of modified_hm_index (run_calculation + calculator). The cloud code
loads every row into pandas; with tens of millions of local rows the same rules are
evaluated set-based in SQLite (window functions) instead. Rules, unchanged:

  source rows : author_paper_field_effective_citation with calculation_status = 'READY'
                and a non-NULL capped_adjusted_citation (Equation 15 output)
  fixed cap   : capped_adjusted_citation is clipped at OUTLIER_CITATION_CAP = 150
  fields      : field_classification unpivoted, field_weight = weight / 100
  join        : (paper, field)  -- inner join
  clean       : author_field_weight > 0, career_factor > 0, field_weight > 0
  Eq 15       : tc_eff   = career_factor * author_field_weight * capped_citation
  Eq 18       : r_eff    = cumulative sum of (career_factor * author_field_weight),
                           papers of one (author, field) sorted by tc_eff descending
  Eq 19       : k_valid  = number of leading papers with tc_eff >= r_eff
                max_r_eff = r_eff at k_valid  (0 if none)
                Hm_f      = mean of max_r_eff over all authors in field f  (kept if > 0)
                Hm_{f,a}  = max_r_eff / Hm_f
  Eq 20       : Hm_a = sum(field_weight * Hm_{f,a}) / sum(field_weight)  over the author's
                paper rows (0 if the denominator is 0)

Result is written to the NEW column author.modified_hm_index (same as the cloud script).

Needs eq15_local to be run first.

Run from the OpenAlex_Data_Collection folder:
    python -m modified_hm_index_local.run_calculation --dry-run
    python -m modified_hm_index_local.run_calculation
"""

import argparse
import time
from datetime import datetime

from .db_connection import get_connection

OUTLIER_CITATION_CAP = 150


def _fields() -> str:
    return "\n UNION ALL \n".join(
        f"SELECT pub_id AS paper_id, field{n}_name AS field_id, "
        f"field{n}_weight / 100.0 AS field_weight FROM field_classification "
        f"WHERE field{n}_name IS NOT NULL AND field{n}_weight IS NOT NULL"
        for n in (1, 2, 3))


COHORT_FILTER = {
    "all": "",
    "done": " AND e.author_id IN (SELECT author_id FROM author WHERE pub_finished = 'done')",
}


STEPS = [
    "DROP TABLE IF EXISTS temp.tmp_hm_fields",
    "DROP TABLE IF EXISTS temp.tmp_hm_ranked",
    "DROP TABLE IF EXISTS temp.tmp_hm_author_field",
    "DROP TABLE IF EXISTS temp.tmp_hm_norm",
    "DROP TABLE IF EXISTS temp.tmp_hm_result",

    f"CREATE TEMP TABLE tmp_hm_fields AS {_fields()}",
    "CREATE INDEX temp.idx_tmp_hm_fields ON tmp_hm_fields(paper_id, field_id)",

    # Equation 15 (tc_eff) and Equation 18 (cumulative effective rank), per (author, field)
    f"""
    CREATE TEMP TABLE tmp_hm_ranked AS
    SELECT
        author_id, field_id, field_weight, tc_eff,
        SUM(contribution) OVER (
            PARTITION BY author_id, field_id
            ORDER BY tc_eff DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS r_eff
    FROM (
        SELECT
            e.author_id,
            e.field_name AS field_id,
            f.field_weight,
            e.career_factor * e.author_field_weight AS contribution,
            e.career_factor * e.author_field_weight
                * MIN(e.capped_adjusted_citation, {float(OUTLIER_CITATION_CAP)}) AS tc_eff
        FROM author_paper_field_effective_citation AS e
        JOIN tmp_hm_fields AS f
          ON f.paper_id = e.pub_id AND f.field_id = e.field_name
        WHERE e.calculation_status = 'READY'
          AND e.capped_adjusted_citation IS NOT NULL
          AND e.author_field_weight > 0
          AND e.career_factor > 0
          AND f.field_weight > 0/*COHORT*/
    )
    """,

    # Pass 1: max_r_eff per (author, field); the comparison tc_eff >= r_eff is true
    # for a leading run of papers and false afterwards (tc_eff is sorted descending,
    # r_eff strictly increasing), so the largest satisfied r_eff is the one at k_valid.
    """
    CREATE TEMP TABLE tmp_hm_author_field AS
    SELECT
        author_id, field_id,
        COALESCE(MAX(CASE WHEN tc_eff >= r_eff THEN r_eff END), 0.0) AS max_r_eff,
        SUM(field_weight) AS field_weight_sum
    FROM tmp_hm_ranked
    GROUP BY author_id, field_id
    """,

    # Pass 2: Hm_f = mean max_r_eff per field, kept only if > 0
    """
    CREATE TEMP TABLE tmp_hm_norm AS
    SELECT field_id, AVG(max_r_eff) AS hm_field_normalization
    FROM tmp_hm_author_field
    GROUP BY field_id
    HAVING AVG(max_r_eff) > 0
    """,

    # Equation 19 -> Equation 20
    """
    CREATE TEMP TABLE tmp_hm_result AS
    SELECT
        af.author_id,
        CASE WHEN SUM(af.field_weight_sum) <> 0
             THEN SUM(af.field_weight_sum * (af.max_r_eff / n.hm_field_normalization))
                  / SUM(af.field_weight_sum)
             ELSE 0 END AS modified_hm_index
    FROM tmp_hm_author_field AS af
    JOIN tmp_hm_norm AS n ON n.field_id = af.field_id
    GROUP BY af.author_id
    """,
    "CREATE UNIQUE INDEX temp.idx_tmp_hm_result ON tmp_hm_result(author_id)",
]


def parse_arguments():
    parser = argparse.ArgumentParser(description="Modified Hm-index (Eq 18-20), local database.")
    parser.add_argument("--cohort", choices=["all", "done"], default="all",
                        help="all authors (cloud behaviour) or only pub_finished = done authors")
    parser.add_argument("--dry-run", action="store_true",
                        help="calculate and print a summary, do not update the author table")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    print()
    print("=" * 60)
    print("MODIFIED HM-INDEX CALCULATION")
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

        print("\nSTEP 1/2: Calculating (author, field) effective ranks ...")
        for number, statement in enumerate(STEPS, start=1):
            statement = statement.replace("/*COHORT*/", COHORT_FILTER[arguments.cohort])
            connection.execute(statement)
            if "CREATE TEMP TABLE" in statement:
                stamp(f"step {number}/{len(STEPS)} done")

        count, mean, low, high = connection.execute(
            "SELECT COUNT(*), AVG(modified_hm_index), MIN(modified_hm_index), "
            "MAX(modified_hm_index) FROM tmp_hm_result").fetchone()
        if not count:
            print("No valid data remains after cleaning (or no field has a positive "
                  "average effective rank).")
            return

        print(f"\n  Calculated Modified Hm-index for {count:,} authors")
        print("\nRESULTS SUMMARY")
        print("-" * 60)
        print(f"Total authors: {count:,}")
        print(f"Average Modified Hm-index: {mean:.4f}")
        print(f"Minimum Modified Hm-index: {low:.4f}")
        print(f"Maximum Modified Hm-index: {high:.4f}")
        print("\nTop 5 Authors:")
        for author_id, value in connection.execute(
                "SELECT author_id, modified_hm_index FROM tmp_hm_result "
                "ORDER BY modified_hm_index DESC LIMIT 5"):
            print(f"  Author {author_id}: {value:.4f}")

        if arguments.dry_run:
            print("\nDry run: author table not updated.")
            return

        print("\nSTEP 2/2: Updating author table ...")
        with connection:
            columns = [r[1] for r in connection.execute("PRAGMA table_info(author)")]
            if "modified_hm_index" not in columns:
                connection.execute("ALTER TABLE author ADD COLUMN modified_hm_index REAL")
            if arguments.cohort != "all":   # no mixed populations
                connection.execute("UPDATE author SET modified_hm_index = NULL "
                                   "WHERE modified_hm_index IS NOT NULL "
                                   "AND author_id NOT IN (SELECT author_id FROM tmp_hm_result)")
            connection.execute(
                "UPDATE author SET modified_hm_index = "
                "(SELECT r.modified_hm_index FROM tmp_hm_result r "
                " WHERE r.author_id = author.author_id) "
                "WHERE author_id IN (SELECT author_id FROM tmp_hm_result)")
        stamp(f"Successfully updated {count:,} authors.")

        print()
        print("=" * 60)
        print("MODIFIED HM-INDEX CALCULATION COMPLETE")
        print("=" * 60)
        print(f"Completed: {datetime.now()}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
