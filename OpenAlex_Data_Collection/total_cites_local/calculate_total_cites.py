"""Equation 11 (Total Cites, T_a) on the LOCAL database.

SQLite port of Calculating_Total_Cites/calculate_total_cites.py. The logic, the
statuses, the parameters and the table / column names are the same; only
PostgreSQL-specific syntax was translated (LATERAL VALUES -> UNION ALL, ::numeric
-> plain numbers, array parameter -> a temp table of selected authors,
BOOL_AND -> MIN(CASE ...), GREATEST -> two-argument MAX).

    T_a = CF_com * sum_p sum_f  W_p^(f,i) * TC_adj(p,i) / TC-bar_adj(f,y)
    CF_com = C * (t + 1) ** (-lambda),   t = as_of_year - first publication year
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence

from .db_connection import get_connection


DEFAULT_CAREER_BOOST = Decimal("1.25")
DEFAULT_CAREER_DECAY = Decimal("0.0601")
DEFAULT_DECIMAL_WEIGHT_TOLERANCE = Decimal("0.02")
DEFAULT_PERCENT_WEIGHT_TOLERANCE = Decimal("2")


def _raw_author(n: int) -> str:
    return f"""
    SELECT acw.pub_id, acw.author{n}id AS author_id, acw.author{n}id_weight AS author_weight
    FROM author_contribution_weight AS acw
    WHERE acw.author{n}id IS NOT NULL
      AND TRIM(acw.author{n}id) <> ''
      AND acw.author{n}id_weight IS NOT NULL
      AND acw.author{n}id_weight >= 0
    """


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


UNION_AUTHORS = "\n UNION ALL \n".join(_raw_author(n) for n in range(1, 11))
UNION_FIELDS = "\n UNION ALL \n".join(_raw_field(n) for n in (1, 2, 3))

PREPARE_STEPS = [
    "DROP TABLE IF EXISTS temp.tmp_eq11_normalized_authors",
    "DROP TABLE IF EXISTS temp.tmp_eq11_normalized_fields",
    "DROP TABLE IF EXISTS temp.tmp_eq11_expected_pairs",
    "DROP TABLE IF EXISTS temp.tmp_eq11_processed_pairs",

    f"""
    CREATE TEMP TABLE tmp_eq11_normalized_authors AS
    WITH raw_authors AS (
        {UNION_AUTHORS}
    ),
    merged_authors AS (
        SELECT pub_id, TRIM(author_id) AS author_id,
               SUM(author_weight) AS author_weight
        FROM raw_authors
        GROUP BY pub_id, TRIM(author_id)
    ),
    author_totals AS (
        SELECT pub_id, SUM(author_weight) AS total_author_weight
        FROM merged_authors
        GROUP BY pub_id
    )
    SELECT
        ma.pub_id,
        ma.author_id,
        ma.author_weight / at.total_author_weight AS author_overall_weight
    FROM merged_authors AS ma
    JOIN author_totals AS at ON at.pub_id = ma.pub_id
    WHERE at.total_author_weight > 0
      AND (
            ABS(at.total_author_weight - 1) <= :decimal_tolerance
            OR
            ABS(at.total_author_weight - 100) <= :percent_tolerance
      )
      AND (
            :has_author_filter = 0
            OR ma.author_id IN (SELECT author_id FROM tmp_selected_authors)
      )
    """,
    "CREATE INDEX temp.idx_tmp_eq11_na ON tmp_eq11_normalized_authors(author_id, pub_id)",
    "CREATE INDEX temp.idx_tmp_eq11_na_pub ON tmp_eq11_normalized_authors(pub_id)",

    f"""
    CREATE TEMP TABLE tmp_eq11_normalized_fields AS
    WITH raw_fields AS (
        {UNION_FIELDS}
    ),
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
        mf.field_weight / ft.total_field_weight AS field_weight
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
    "CREATE INDEX temp.idx_tmp_eq11_nf ON tmp_eq11_normalized_fields(pub_id, field_name)",

    """
    CREATE TEMP TABLE tmp_eq11_expected_pairs AS
    SELECT
        c.pub_id AS cited_pub_id,
        COUNT(DISTINCT c.cites_pub_id) AS expected_pair_count
    FROM citation AS c
    WHERE c.pub_id IS NOT NULL
      AND c.cites_pub_id IS NOT NULL
      AND c.pub_id <> c.cites_pub_id
    GROUP BY c.pub_id
    """,
    "CREATE INDEX temp.idx_tmp_eq11_ep ON tmp_eq11_expected_pairs(cited_pub_id)",

    """
    CREATE TEMP TABLE tmp_eq11_processed_pairs AS
    SELECT
        isc.cited_pub_id,
        COUNT(DISTINCT isc.citing_pub_id) AS processed_pair_count
    FROM influential_self_citations AS isc
    GROUP BY isc.cited_pub_id
    """,
    "CREATE INDEX temp.idx_tmp_eq11_pp ON tmp_eq11_processed_pairs(cited_pub_id)",
]


INSERT_DETAILS_SQL = """
INSERT INTO total_cites_equation_11_details (
    author_id,
    pub_id,
    field_name,
    publication_year,
    author_overall_weight,
    field_weight,
    author_field_weight,
    adjusted_citation,
    field_year_average,
    benchmark_coverage_ratio,
    normalized_citation_ratio,
    paper_field_contribution,
    expected_citing_pair_count,
    processed_citing_pair_count,
    calculation_status,
    calculated_at
)
SELECT
    na.author_id,
    na.pub_id,
    nf.field_name,
    nf.publication_year,
    na.author_overall_weight,
    nf.field_weight,
    na.author_overall_weight * nf.field_weight AS author_field_weight,

    CASE
        WHEN COALESCE(ep.expected_pair_count, 0) = 0 THEN 0
        ELSE apac.total_adjusted_citation
    END AS adjusted_citation,

    fya.citation_avg_field_and_year AS field_year_average,
    fya.data_coverage_ratio AS benchmark_coverage_ratio,

    CASE
        WHEN (
            COALESCE(ep.expected_pair_count, 0) = 0
            OR (
                COALESCE(pp.processed_pair_count, 0)
                    = COALESCE(ep.expected_pair_count, 0)
                AND apac.total_adjusted_citation IS NOT NULL
            )
        )
        AND fya.citation_avg_field_and_year > 0
        THEN
            CASE
                WHEN COALESCE(ep.expected_pair_count, 0) = 0 THEN 0
                ELSE apac.total_adjusted_citation
            END
            / fya.citation_avg_field_and_year
        ELSE NULL
    END AS normalized_citation_ratio,

    CASE
        WHEN (
            COALESCE(ep.expected_pair_count, 0) = 0
            OR (
                COALESCE(pp.processed_pair_count, 0)
                    = COALESCE(ep.expected_pair_count, 0)
                AND apac.total_adjusted_citation IS NOT NULL
            )
        )
        AND fya.citation_avg_field_and_year > 0
        THEN
            (na.author_overall_weight * nf.field_weight)
            * (
                CASE
                    WHEN COALESCE(ep.expected_pair_count, 0) = 0 THEN 0
                    ELSE apac.total_adjusted_citation
                END
                / fya.citation_avg_field_and_year
            )
        ELSE NULL
    END AS paper_field_contribution,

    COALESCE(ep.expected_pair_count, 0) AS expected_citing_pair_count,
    COALESCE(pp.processed_pair_count, 0) AS processed_citing_pair_count,

    CASE
        WHEN COALESCE(ep.expected_pair_count, 0) > 0
             AND COALESCE(pp.processed_pair_count, 0)
                 < COALESCE(ep.expected_pair_count, 0)
            THEN 'INCOMPLETE_ISC'

        WHEN COALESCE(ep.expected_pair_count, 0) > 0
             AND apac.total_adjusted_citation IS NULL
            THEN 'MISSING_ADJUSTED_CITATION'

        WHEN fya.field_name IS NULL
            THEN 'MISSING_FIELD_YEAR_AVERAGE'

        WHEN fya.citation_avg_field_and_year IS NULL
            THEN 'MISSING_FIELD_YEAR_AVERAGE'

        WHEN fya.citation_avg_field_and_year = 0
            THEN 'ZERO_FIELD_YEAR_AVERAGE'

        WHEN fya.data_coverage_ratio < 1
            THEN 'READY_PROVISIONAL_BENCHMARK'

        ELSE 'READY'
    END AS calculation_status,

    CURRENT_TIMESTAMP
FROM tmp_eq11_normalized_authors AS na
JOIN tmp_eq11_normalized_fields AS nf
    ON nf.pub_id = na.pub_id
LEFT JOIN tmp_eq11_expected_pairs AS ep
    ON ep.cited_pub_id = na.pub_id
LEFT JOIN tmp_eq11_processed_pairs AS pp
    ON pp.cited_pub_id = na.pub_id
LEFT JOIN author_paper_adjusted_citations AS apac
    ON apac.cited_pub_id = na.pub_id
   AND apac.target_author_id = na.author_id
LEFT JOIN field_year_adjusted_citation_average AS fya
    ON fya.field_name = nf.field_name
   AND fya.publication_year = nf.publication_year
ORDER BY na.author_id, na.pub_id, nf.field_name
"""


INSERT_FINAL_RESULTS_SQL = """
WITH author_profiles AS (
    SELECT
        na.author_id,
        MIN(nf.publication_year) AS first_publication_year,
        COUNT(DISTINCT na.pub_id) AS publication_count
    FROM tmp_eq11_normalized_authors AS na
    JOIN tmp_eq11_normalized_fields AS nf
        ON nf.pub_id = na.pub_id
    GROUP BY na.author_id
),
detail_summary AS (
    SELECT
        d.author_id,
        COUNT(*) AS field_row_count,
        COUNT(*) FILTER (
            WHERE d.calculation_status IN (
                'READY',
                'READY_PROVISIONAL_BENCHMARK'
            )
        ) AS included_field_row_count,
        COUNT(*) FILTER (
            WHERE d.calculation_status NOT IN (
                'READY',
                'READY_PROVISIONAL_BENCHMARK'
            )
        ) AS skipped_field_row_count,
        COUNT(*) FILTER (
            WHERE d.calculation_status = 'READY_PROVISIONAL_BENCHMARK'
        ) AS provisional_field_row_count,
        COUNT(DISTINCT d.pub_id) FILTER (
            WHERE d.calculation_status IN (
                'READY',
                'READY_PROVISIONAL_BENCHMARK'
            )
        ) AS included_publication_count,
        COALESCE(
            SUM(d.paper_field_contribution) FILTER (
                WHERE d.calculation_status IN (
                    'READY',
                    'READY_PROVISIONAL_BENCHMARK'
                )
            ),
            0
        ) AS normalized_contribution_sum,
        MIN(CASE WHEN d.calculation_status = 'READY' THEN 1 ELSE 0 END)
            AS calculation_complete
    FROM total_cites_equation_11_details AS d
    WHERE (
        :has_author_filter = 0
        OR d.author_id IN (SELECT author_id FROM tmp_selected_authors)
    )
    GROUP BY d.author_id
),
calculated AS (
    SELECT
        ap.author_id,
        ap.first_publication_year,
        :as_of_year AS as_of_year,
        MAX(:as_of_year - ap.first_publication_year, 0) AS career_time_years,
        :career_boost AS career_boost_c,
        :career_decay AS career_decay_lambda,
        (
            :career_boost
            * POWER(
                MAX(:as_of_year - ap.first_publication_year, 0) + 1,
                -(:career_decay)
            )
        ) AS career_factor,
        ap.publication_count,
        COALESCE(ds.included_publication_count, 0)
            AS included_publication_count,
        COALESCE(ds.field_row_count, 0) AS field_row_count,
        COALESCE(ds.included_field_row_count, 0)
            AS included_field_row_count,
        COALESCE(ds.skipped_field_row_count, 0)
            AS skipped_field_row_count,
        COALESCE(ds.provisional_field_row_count, 0)
            AS provisional_field_row_count,
        COALESCE(ds.normalized_contribution_sum, 0)
            AS normalized_contribution_sum,
        COALESCE(ds.calculation_complete, 0)
            AS calculation_complete
    FROM author_profiles AS ap
    LEFT JOIN detail_summary AS ds
        ON ds.author_id = ap.author_id
)
INSERT INTO author_total_cites (
    author_id,
    first_publication_year,
    as_of_year,
    career_time_years,
    career_boost_c,
    career_decay_lambda,
    career_factor,
    publication_count,
    included_publication_count,
    field_row_count,
    included_field_row_count,
    skipped_field_row_count,
    provisional_field_row_count,
    normalized_contribution_sum,
    total_cites_score,
    calculation_complete,
    calculated_at
)
SELECT
    author_id,
    first_publication_year,
    as_of_year,
    career_time_years,
    career_boost_c,
    career_decay_lambda,
    career_factor,
    publication_count,
    included_publication_count,
    field_row_count,
    included_field_row_count,
    skipped_field_row_count,
    provisional_field_row_count,
    normalized_contribution_sum,
    CASE
        WHEN included_field_row_count = 0 THEN NULL
        ELSE career_factor * normalized_contribution_sum
    END AS total_cites_score,
    calculation_complete,
    CURRENT_TIMESTAMP
FROM calculated
"""


def calculate_total_cites(
    *,
    author_ids: Sequence[str] | None = None,
    as_of_year: int | None = None,
    career_boost: Decimal = DEFAULT_CAREER_BOOST,
    career_decay: Decimal = DEFAULT_CAREER_DECAY,
    decimal_weight_tolerance: Decimal = DEFAULT_DECIMAL_WEIGHT_TOLERANCE,
    percent_weight_tolerance: Decimal = DEFAULT_PERCENT_WEIGHT_TOLERANCE,
) -> None:
    """Calculate and store Equation 11 for all authors or selected authors."""

    resolved_year = as_of_year if as_of_year is not None else date.today().year
    selected_author_ids = sorted(set(author_ids)) if author_ids else None

    if resolved_year < 0:
        raise ValueError("as_of_year must be non-negative.")

    if career_boost < 1:
        raise ValueError("career_boost C must be at least 1.")

    if not Decimal("0") <= career_decay <= Decimal("1"):
        raise ValueError("career_decay lambda must be between 0 and 1.")

    parameters = {
        "has_author_filter": 1 if selected_author_ids else 0,
        "as_of_year": resolved_year,
        "career_boost": float(career_boost),
        "career_decay": float(career_decay),
        "decimal_tolerance": float(decimal_weight_tolerance),
        "percent_tolerance": float(percent_weight_tolerance),
    }

    connection = get_connection()

    def run(statement, params=None):
        used = {k: v for k, v in parameters.items() if f":{k}" in statement}
        return connection.execute(statement, used if params is None else params)

    try:
        with connection:
            connection.execute("DROP TABLE IF EXISTS temp.tmp_selected_authors")
            connection.execute(
                "CREATE TEMP TABLE tmp_selected_authors (author_id TEXT PRIMARY KEY)")
            if selected_author_ids:
                connection.executemany(
                    "INSERT INTO tmp_selected_authors VALUES (?)",
                    [(a,) for a in selected_author_ids])

            # Selected runs replace only the selected authors. Full runs rebuild
            # all Equation 11 detail and final rows.
            if selected_author_ids:
                connection.execute(
                    "DELETE FROM total_cites_equation_11_details "
                    "WHERE author_id IN (SELECT author_id FROM tmp_selected_authors)")
                connection.execute(
                    "DELETE FROM author_total_cites "
                    "WHERE author_id IN (SELECT author_id FROM tmp_selected_authors)")
            else:
                connection.execute("DELETE FROM total_cites_equation_11_details")
                connection.execute("DELETE FROM author_total_cites")

            for number, statement in enumerate(PREPARE_STEPS, start=1):
                if "CREATE TEMP TABLE" in statement:
                    print(f"  preparing temp table {number}/{len(PREPARE_STEPS)} ...",
                          flush=True)
                run(statement)

            print("  writing Equation 11 detail rows ...", flush=True)
            run(INSERT_DETAILS_SQL)
            print("  writing author-level T_a rows ...", flush=True)
            run(INSERT_FINAL_RESULTS_SQL)

            (author_count, scored_author_count,
             complete_author_count, incomplete_author_count) = connection.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (WHERE total_cites_score IS NOT NULL),
                    COUNT(*) FILTER (WHERE calculation_complete = 1),
                    COUNT(*) FILTER (WHERE calculation_complete = 0)
                FROM author_total_cites
                WHERE (
                    :has_author_filter = 0
                    OR author_id IN (SELECT author_id FROM tmp_selected_authors)
                )
                """,
                {"has_author_filter": parameters["has_author_filter"]},
            ).fetchone()

            status_counts = connection.execute(
                """
                SELECT calculation_status, COUNT(*)
                FROM total_cites_equation_11_details
                WHERE (
                    :has_author_filter = 0
                    OR author_id IN (SELECT author_id FROM tmp_selected_authors)
                )
                GROUP BY calculation_status
                ORDER BY calculation_status
                """,
                {"has_author_filter": parameters["has_author_filter"]},
            ).fetchall()

            for table in ("tmp_eq11_normalized_authors", "tmp_eq11_normalized_fields",
                          "tmp_eq11_expected_pairs", "tmp_eq11_processed_pairs",
                          "tmp_selected_authors"):
                connection.execute(f"DROP TABLE IF EXISTS temp.{table}")

        print("Equation 11 Total Cites calculation completed.")
        print(f"As-of year: {resolved_year}")
        print(f"Career parameters: C={career_boost}, lambda={career_decay}")
        print(f"Authors processed: {author_count}")
        print(f"Authors with a T_a value: {scored_author_count}")
        print(f"Fully complete authors: {complete_author_count}")
        print(f"Provisional/incomplete authors: {incomplete_author_count}")
        print("Detail row status counts:")
        for status, count in status_counts:
            print(f"- {status}: {count}")

    finally:
        connection.close()
