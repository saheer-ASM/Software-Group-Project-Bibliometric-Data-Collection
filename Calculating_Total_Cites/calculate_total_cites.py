from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence

from Calculating_ISC.db_connection import get_connection


DEFAULT_CAREER_BOOST = Decimal("1.25")
DEFAULT_CAREER_DECAY = Decimal("0.0601")
DEFAULT_DECIMAL_WEIGHT_TOLERANCE = Decimal("0.02")
DEFAULT_PERCENT_WEIGHT_TOLERANCE = Decimal("2")


PREPARE_TEMP_TABLES_SQL = """
CREATE TEMP TABLE tmp_eq11_normalized_authors
ON COMMIT DROP AS
WITH raw_authors AS (
    SELECT
        acw.pub_id,
        author_item.author_id,
        author_item.author_weight::numeric AS author_weight
    FROM public.author_contribution_weight AS acw
    CROSS JOIN LATERAL (
        VALUES
            (acw.author1id, acw.author1id_weight),
            (acw.author2id, acw.author2id_weight),
            (acw.author3id, acw.author3id_weight),
            (acw.author4id, acw.author4id_weight),
            (acw.author5id, acw.author5id_weight),
            (acw.author6id, acw.author6id_weight),
            (acw.author7id, acw.author7id_weight),
            (acw.author8id, acw.author8id_weight),
            (acw.author9id, acw.author9id_weight),
            (acw.author10id, acw.author10id_weight)
    ) AS author_item(author_id, author_weight)
    WHERE author_item.author_id IS NOT NULL
      AND BTRIM(author_item.author_id) <> ''
      AND author_item.author_weight IS NOT NULL
      AND author_item.author_weight >= 0
),
merged_authors AS (
    SELECT
        pub_id,
        BTRIM(author_id) AS author_id,
        SUM(author_weight) AS author_weight
    FROM raw_authors
    GROUP BY pub_id, BTRIM(author_id)
),
author_totals AS (
    SELECT
        pub_id,
        SUM(author_weight) AS total_author_weight
    FROM merged_authors
    GROUP BY pub_id
)
SELECT
    ma.pub_id,
    ma.author_id,
    ma.author_weight / at.total_author_weight AS author_overall_weight
FROM merged_authors AS ma
JOIN author_totals AS at
    ON at.pub_id = ma.pub_id
WHERE at.total_author_weight > 0
  AND (
        ABS(at.total_author_weight - 1) <= %(decimal_tolerance)s
        OR
        ABS(at.total_author_weight - 100) <= %(percent_tolerance)s
  )
  AND (
        %(author_ids)s::text[] IS NULL
        OR ma.author_id = ANY(%(author_ids)s::text[])
  );

CREATE INDEX ON tmp_eq11_normalized_authors(author_id, pub_id);


CREATE TEMP TABLE tmp_eq11_normalized_fields
ON COMMIT DROP AS
WITH raw_fields AS (
    SELECT
        fc.pub_id,
        CASE
            WHEN p.year::text ~ '^[0-9]{4}$'
            THEN p.year::integer
            ELSE NULL
        END AS publication_year,
        BTRIM(field_item.field_name) AS field_name,
        field_item.field_weight::numeric AS field_weight
    FROM public.field_classification AS fc
    JOIN public.publication AS p
        ON p.pub_id = fc.pub_id
    CROSS JOIN LATERAL (
        VALUES
            (fc.field1_name, fc.field1_weight),
            (fc.field2_name, fc.field2_weight),
            (fc.field3_name, fc.field3_weight)
    ) AS field_item(field_name, field_weight)
    WHERE field_item.field_name IS NOT NULL
      AND BTRIM(field_item.field_name) <> ''
      AND field_item.field_weight IS NOT NULL
      AND field_item.field_weight > 0
),
merged_fields AS (
    SELECT
        pub_id,
        publication_year,
        field_name,
        SUM(field_weight) AS field_weight
    FROM raw_fields
    WHERE publication_year IS NOT NULL
    GROUP BY pub_id, publication_year, field_name
),
field_totals AS (
    SELECT
        pub_id,
        publication_year,
        SUM(field_weight) AS total_field_weight
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
        ABS(ft.total_field_weight - 1) <= %(decimal_tolerance)s
        OR
        ABS(ft.total_field_weight - 100) <= %(percent_tolerance)s
  );

CREATE INDEX ON tmp_eq11_normalized_fields(pub_id, field_name);


CREATE TEMP TABLE tmp_eq11_expected_pairs
ON COMMIT DROP AS
SELECT
    c.pub_id AS cited_pub_id,
    COUNT(DISTINCT c.cites_pub_id)::integer AS expected_pair_count
FROM public.citation AS c
WHERE c.pub_id IS NOT NULL
  AND c.cites_pub_id IS NOT NULL
  AND c.pub_id <> c.cites_pub_id
GROUP BY c.pub_id;

CREATE INDEX ON tmp_eq11_expected_pairs(cited_pub_id);


CREATE TEMP TABLE tmp_eq11_processed_pairs
ON COMMIT DROP AS
SELECT
    isc.cited_pub_id,
    COUNT(DISTINCT isc.citing_pub_id)::integer AS processed_pair_count
FROM public.influential_self_citations AS isc
GROUP BY isc.cited_pub_id;

CREATE INDEX ON tmp_eq11_processed_pairs(cited_pub_id);
"""


INSERT_DETAILS_SQL = """
INSERT INTO public.total_cites_equation_11_details (
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
LEFT JOIN public.author_paper_adjusted_citations AS apac
    ON apac.cited_pub_id = na.pub_id
   AND apac.target_author_id = na.author_id
LEFT JOIN public.field_year_adjusted_citation_average AS fya
    ON fya.field_name = nf.field_name
   AND fya.publication_year = nf.publication_year;
"""


INSERT_FINAL_RESULTS_SQL = """
WITH author_profiles AS (
    SELECT
        na.author_id,
        MIN(nf.publication_year)::integer AS first_publication_year,
        COUNT(DISTINCT na.pub_id)::integer AS publication_count
    FROM tmp_eq11_normalized_authors AS na
    JOIN tmp_eq11_normalized_fields AS nf
        ON nf.pub_id = na.pub_id
    GROUP BY na.author_id
),
detail_summary AS (
    SELECT
        d.author_id,
        COUNT(*)::integer AS field_row_count,
        COUNT(*) FILTER (
            WHERE d.calculation_status IN (
                'READY',
                'READY_PROVISIONAL_BENCHMARK'
            )
        )::integer AS included_field_row_count,
        COUNT(*) FILTER (
            WHERE d.calculation_status NOT IN (
                'READY',
                'READY_PROVISIONAL_BENCHMARK'
            )
        )::integer AS skipped_field_row_count,
        COUNT(*) FILTER (
            WHERE d.calculation_status = 'READY_PROVISIONAL_BENCHMARK'
        )::integer AS provisional_field_row_count,
        COUNT(DISTINCT d.pub_id) FILTER (
            WHERE d.calculation_status IN (
                'READY',
                'READY_PROVISIONAL_BENCHMARK'
            )
        )::integer AS included_publication_count,
        COALESCE(
            SUM(d.paper_field_contribution) FILTER (
                WHERE d.calculation_status IN (
                    'READY',
                    'READY_PROVISIONAL_BENCHMARK'
                )
            ),
            0
        ) AS normalized_contribution_sum,
        BOOL_AND(d.calculation_status = 'READY') AS calculation_complete
    FROM public.total_cites_equation_11_details AS d
    WHERE (
        %(author_ids)s::text[] IS NULL
        OR d.author_id = ANY(%(author_ids)s::text[])
    )
    GROUP BY d.author_id
),
calculated AS (
    SELECT
        ap.author_id,
        ap.first_publication_year,
        %(as_of_year)s::integer AS as_of_year,
        GREATEST(
            %(as_of_year)s::integer - ap.first_publication_year,
            0
        )::integer AS career_time_years,
        %(career_boost)s::numeric AS career_boost_c,
        %(career_decay)s::numeric AS career_decay_lambda,
        (
            %(career_boost)s::numeric
            * POWER(
                (
                    GREATEST(
                        %(as_of_year)s::integer - ap.first_publication_year,
                        0
                    ) + 1
                )::numeric,
                -(%(career_decay)s::numeric)
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
        COALESCE(ds.calculation_complete, FALSE)
            AS calculation_complete
    FROM author_profiles AS ap
    LEFT JOIN detail_summary AS ds
        ON ds.author_id = ap.author_id
)
INSERT INTO public.author_total_cites (
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
FROM calculated;
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
        "author_ids": selected_author_ids,
        "as_of_year": resolved_year,
        "career_boost": career_boost,
        "career_decay": career_decay,
        "decimal_tolerance": decimal_weight_tolerance,
        "percent_tolerance": percent_weight_tolerance,
    }

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            # Selected runs replace only the selected authors. Full runs rebuild
            # all Equation 11 detail and final rows.
            if selected_author_ids:
                cursor.execute(
                    """
                    DELETE FROM public.total_cites_equation_11_details
                    WHERE author_id = ANY(%s);
                    """,
                    (selected_author_ids,),
                )
                cursor.execute(
                    """
                    DELETE FROM public.author_total_cites
                    WHERE author_id = ANY(%s);
                    """,
                    (selected_author_ids,),
                )
            else:
                cursor.execute(
                    "DELETE FROM public.total_cites_equation_11_details;"
                )
                cursor.execute("DELETE FROM public.author_total_cites;")

            cursor.execute(PREPARE_TEMP_TABLES_SQL, parameters)
            cursor.execute(INSERT_DETAILS_SQL, parameters)
            cursor.execute(INSERT_FINAL_RESULTS_SQL, parameters)

            cursor.execute(
                """
                SELECT
                    COUNT(*)::integer,
                    COUNT(*) FILTER (
                        WHERE total_cites_score IS NOT NULL
                    )::integer,
                    COUNT(*) FILTER (
                        WHERE calculation_complete
                    )::integer,
                    COUNT(*) FILTER (
                        WHERE NOT calculation_complete
                    )::integer
                FROM public.author_total_cites
                WHERE (
                    %s::text[] IS NULL
                    OR author_id = ANY(%s::text[])
                );
                """,
                (selected_author_ids, selected_author_ids),
            )
            (
                author_count,
                scored_author_count,
                complete_author_count,
                incomplete_author_count,
            ) = cursor.fetchone()

            cursor.execute(
                """
                SELECT calculation_status, COUNT(*)::integer
                FROM public.total_cites_equation_11_details
                WHERE (
                    %s::text[] IS NULL
                    OR author_id = ANY(%s::text[])
                )
                GROUP BY calculation_status
                ORDER BY calculation_status;
                """,
                (selected_author_ids, selected_author_ids),
            )
            status_counts = cursor.fetchall()

        connection.commit()

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

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()