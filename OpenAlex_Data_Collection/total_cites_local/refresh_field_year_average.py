"""TC-bar_adj(f, y): the field / publication-year adjusted-citation benchmark.

SQLite port of Calculating_Total_Cites/refresh_field_year_average.py. The logic and
the SQL are the same; only PostgreSQL-specific syntax was translated
(LATERAL VALUES -> UNION ALL, ~ regex -> GLOB, ::numeric / ::integer -> CAST,
CTEs that were used twice -> TEMP tables). Table and column names are unchanged.
"""

from __future__ import annotations

from .db_connection import get_connection

# The existing project stores publication field totals as either decimals
# (approximately 1) or percentages (approximately 100).
DECIMAL_WEIGHT_TOLERANCE = 0.02
PERCENT_WEIGHT_TOLERANCE = 2.0


def _raw_field(n: int) -> str:
    return f"""
    SELECT
        fc.pub_id,
        CASE
            WHEN p.year IS NOT NULL
             AND CAST(p.year AS TEXT) GLOB '[0-9][0-9][0-9][0-9]'
            THEN CAST(p.year AS INTEGER)
            ELSE NULL
        END AS publication_year,
        TRIM(fc.field{n}_name) AS field_name,
        fc.field{n}_weight AS field_weight
    FROM field_classification AS fc
    JOIN publication AS p ON p.pub_id = fc.pub_id
    WHERE fc.field{n}_name IS NOT NULL
      AND TRIM(fc.field{n}_name) <> ''
      AND fc.field{n}_weight IS NOT NULL
      AND fc.field{n}_weight > 0
    """


STEPS = [
    "DELETE FROM field_year_adjusted_citation_average",

    "DROP TABLE IF EXISTS temp.tmp_fy_normalized_fields",
    "DROP TABLE IF EXISTS temp.tmp_fy_paper_status",

    # Convert both 1-based and 100-based field weights to decimals summing to 1.
    f"""
    CREATE TEMP TABLE tmp_fy_normalized_fields AS
    WITH raw_fields AS (
        {_raw_field(1)}
        UNION ALL
        {_raw_field(2)}
        UNION ALL
        {_raw_field(3)}
    ),
    -- If the same field appears more than once for one publication, merge it.
    merged_fields AS (
        SELECT pub_id, publication_year, field_name,
               SUM(field_weight) AS field_weight
        FROM raw_fields
        WHERE publication_year IS NOT NULL
        GROUP BY pub_id, publication_year, field_name
    ),
    field_totals AS (
        SELECT pub_id, publication_year, SUM(field_weight) AS total_field_weight
        FROM merged_fields
        GROUP BY pub_id, publication_year
    )
    SELECT
        mf.pub_id,
        mf.publication_year,
        mf.field_name,
        mf.field_weight / ft.total_field_weight AS normalized_field_weight
    FROM merged_fields AS mf
    JOIN field_totals AS ft
        ON ft.pub_id = mf.pub_id
       AND ft.publication_year = mf.publication_year
    WHERE ft.total_field_weight > 0
      AND (
            ABS(ft.total_field_weight - 1) <= :decimal_tolerance
            OR
            ABS(ft.total_field_weight - 100) <= :percent_tolerance
      )
    """,
    "CREATE INDEX temp.idx_tmp_fy_nf_pub ON tmp_fy_normalized_fields(pub_id)",

    """
    CREATE TEMP TABLE tmp_fy_paper_status AS
    WITH
    -- Number of incoming citation pairs that should be processed for each paper.
    expected_pairs AS (
        SELECT c.pub_id AS cited_pub_id,
               COUNT(DISTINCT c.cites_pub_id) AS expected_pair_count
        FROM citation AS c
        WHERE c.pub_id IS NOT NULL
          AND c.cites_pub_id IS NOT NULL
          AND c.pub_id <> c.cites_pub_id
        GROUP BY c.pub_id
    ),
    -- Number of citation pairs actually completed by the ISC calculation.
    processed_pairs AS (
        SELECT isc.cited_pub_id,
               COUNT(DISTINCT isc.citing_pub_id) AS processed_pair_count
        FROM influential_self_citations AS isc
        GROUP BY isc.cited_pub_id
    ),
    -- Equation 9: one adjusted total per paper and target author; sum them to get
    -- one paper-level adjusted total.
    paper_adjusted_totals AS (
        SELECT apac.cited_pub_id,
               SUM(apac.total_adjusted_citation) AS paper_adjusted_citations
        FROM author_paper_adjusted_citations AS apac
        GROUP BY apac.cited_pub_id
    )
    SELECT
        p.pub_id,
        COALESCE(ep.expected_pair_count, 0) AS expected_pair_count,
        COALESCE(pp.processed_pair_count, 0) AS processed_pair_count,
        COALESCE(pat.paper_adjusted_citations, 0) AS paper_adjusted_citations,
        CASE
            WHEN COALESCE(ep.expected_pair_count, 0) = 0
                THEN 1
            WHEN COALESCE(ep.expected_pair_count, 0)
                 = COALESCE(pp.processed_pair_count, 0)
                 AND pat.cited_pub_id IS NOT NULL
                THEN 1
            ELSE 0
        END AS is_complete
    FROM publication AS p
    LEFT JOIN expected_pairs AS ep ON ep.cited_pub_id = p.pub_id
    LEFT JOIN processed_pairs AS pp ON pp.cited_pub_id = p.pub_id
    LEFT JOIN paper_adjusted_totals AS pat ON pat.cited_pub_id = p.pub_id
    /*POPULATION*/
    """,
    "CREATE INDEX temp.idx_tmp_fy_ps_pub ON tmp_fy_paper_status(pub_id)",

    """
    INSERT INTO field_year_adjusted_citation_average (
        field_name, publication_year, publication_count,
        complete_publication_count, incomplete_publication_count,
        zero_citation_publication_count, sum_adjusted_citations,
        citation_avg_field_and_year, field_weight_sum,
        weighted_sum_adjusted_citations, weighted_citation_avg_field_and_year,
        data_coverage_ratio, calculated_at
    )
    SELECT
        nf.field_name,
        nf.publication_year,

        COUNT(DISTINCT nf.pub_id) AS publication_count,

        COUNT(DISTINCT nf.pub_id) FILTER (WHERE ps.is_complete = 1)
            AS complete_publication_count,

        COUNT(DISTINCT nf.pub_id) FILTER (WHERE ps.is_complete = 0)
            AS incomplete_publication_count,

        COUNT(DISTINCT nf.pub_id) FILTER (
            WHERE ps.is_complete = 1 AND ps.expected_pair_count = 0
        ) AS zero_citation_publication_count,

        COALESCE(SUM(ps.paper_adjusted_citations) FILTER (
            WHERE ps.is_complete = 1), 0) AS sum_adjusted_citations,

        AVG(ps.paper_adjusted_citations) FILTER (WHERE ps.is_complete = 1)
            AS citation_avg_field_and_year,

        COALESCE(SUM(nf.normalized_field_weight) FILTER (
            WHERE ps.is_complete = 1), 0) AS field_weight_sum,

        COALESCE(SUM(nf.normalized_field_weight * ps.paper_adjusted_citations)
            FILTER (WHERE ps.is_complete = 1), 0)
            AS weighted_sum_adjusted_citations,

        (
            SUM(nf.normalized_field_weight * ps.paper_adjusted_citations)
                FILTER (WHERE ps.is_complete = 1)
            /
            NULLIF(SUM(nf.normalized_field_weight)
                FILTER (WHERE ps.is_complete = 1), 0)
        ) AS weighted_citation_avg_field_and_year,

        CASE
            WHEN COUNT(DISTINCT nf.pub_id) = 0 THEN 0
            ELSE
                CAST(COUNT(DISTINCT nf.pub_id) FILTER (
                    WHERE ps.is_complete = 1) AS REAL)
                /
                CAST(COUNT(DISTINCT nf.pub_id) AS REAL)
        END AS data_coverage_ratio,

        CURRENT_TIMESTAMP
    FROM tmp_fy_normalized_fields AS nf
    JOIN tmp_fy_paper_status AS ps ON ps.pub_id = nf.pub_id
    GROUP BY nf.field_name, nf.publication_year
    """,

    "DROP TABLE IF EXISTS temp.tmp_fy_normalized_fields",
    "DROP TABLE IF EXISTS temp.tmp_fy_paper_status",
]


POPULATION_FILTER = {
    # papers whose citing papers were collected -- the only papers whose citation count is known
    "updated": "WHERE p.update_status = 'updated'",
    # cloud behaviour: every publication (citing papers count as zero-cited -> benchmark far too small)
    "all": "",
}
MIN_GROUP_SIZE = 10     # a (field, year) group with fewer papers is smoothed
YEAR_WINDOW = 2         # pool the same field over +-2 years, then fall back to the whole field


def smooth_thin_groups(connection, min_group: int, window: int) -> dict:
    """Replace the average of thin (field, year) groups. NOT in the paper: it avoids
    averages of 1-4 papers. Smoothed rows get benchmark_method 'window' / 'field', which
    Equation 11 reports as READY_PROVISIONAL_BENCHMARK."""
    rows = connection.execute(
        "SELECT field_name, publication_year, complete_publication_count, "
        "sum_adjusted_citations FROM field_year_adjusted_citation_average").fetchall()
    by_field = {}
    for field, year, n, total in rows:
        by_field.setdefault(field, {})[year] = (n, total)
    counts = {"exact": 0, "window": 0, "field": 0, "none": 0}
    for field, years in by_field.items():
        field_n = sum(n for n, _ in years.values())
        field_sum = sum(t for _, t in years.values())
        for year, (n, total) in years.items():
            if n >= min_group:
                counts["exact"] += 1
                connection.execute(
                    "UPDATE field_year_adjusted_citation_average SET benchmark_method = 'exact', "
                    "benchmark_papers = ? WHERE field_name = ? AND publication_year = ?",
                    (n, field, year))
                continue
            pool = [years[y] for y in range(year - window, year + window + 1) if y in years]
            pooled_n = sum(x[0] for x in pool)
            if pooled_n >= min_group:
                method, used_n, average = "window", pooled_n, sum(x[1] for x in pool) / pooled_n
            elif field_n > 0:
                method, used_n, average = "field", field_n, field_sum / field_n
            else:
                counts["none"] += 1
                continue
            counts[method] += 1
            connection.execute(
                "UPDATE field_year_adjusted_citation_average SET benchmark_method = ?, "
                "benchmark_papers = ?, citation_avg_field_and_year = ? "
                "WHERE field_name = ? AND publication_year = ?",
                (method, used_n, average, field, year))
    return counts


def refresh_field_year_average(population: str = "updated", min_group: int = MIN_GROUP_SIZE,
                               window: int = YEAR_WINDOW) -> None:
    """
    Rebuild TC-bar(f,y,adj) from the latest database state.

    Rerun this function after publications, citation pairs, contribution
    weights, ISC rows, or Equation 9 totals change.
    """

    connection = get_connection()
    parameters = {
        "decimal_tolerance": DECIMAL_WEIGHT_TOLERANCE,
        "percent_tolerance": PERCENT_WEIGHT_TOLERANCE,
    }

    try:
        with connection:
            print(f"  benchmark population: {population}", flush=True)
            for number, statement in enumerate(STEPS, start=1):
                if "CREATE TEMP TABLE" in statement or statement.lstrip().startswith("INSERT"):
                    print(f"  step {number}/{len(STEPS)} ...", flush=True)
                statement = statement.replace("/*POPULATION*/", POPULATION_FILTER[population])
                connection.execute(statement, parameters if ":" in statement and
                                   ("decimal_tolerance" in statement) else ())
            counts = smooth_thin_groups(connection, min_group, window)
            print(f"  groups: {counts['exact']} exact (>= {min_group} papers), "
                  f"{counts['window']} pooled over +-{window} years, "
                  f"{counts['field']} field-only, {counts['none']} without data")

            group_count, average_coverage, minimum_coverage = connection.execute(
                """
                SELECT
                    COUNT(*) AS field_year_group_count,
                    COALESCE(AVG(data_coverage_ratio), 0),
                    COALESCE(MIN(data_coverage_ratio), 0)
                FROM field_year_adjusted_citation_average
                """
            ).fetchone()

        print("Field-year adjusted citation averages refreshed.")
        print(f"Field-year groups: {group_count}")
        print(f"Average data coverage: {average_coverage}")
        print(f"Minimum data coverage: {minimum_coverage}")

        if minimum_coverage < 1:
            print(
                "Warning: some field-year averages are provisional because "
                "not all citation pairs have completed ISC processing."
            )

    finally:
        connection.close()


if __name__ == "__main__":
    refresh_field_year_average()
