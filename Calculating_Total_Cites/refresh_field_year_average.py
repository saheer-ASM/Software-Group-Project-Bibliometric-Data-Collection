from __future__ import annotations

from Calculating_ISC.db_connection import get_connection

# The existing project stores publication field totals as either decimals
# (approximately 1) or percentages (approximately 100).
DECIMAL_WEIGHT_TOLERANCE = 0.02
PERCENT_WEIGHT_TOLERANCE = 2.0


REFRESH_SQL = """
DELETE FROM public.field_year_adjusted_citation_average;

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

-- If the same field appears more than once for one publication, merge it.
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
),

-- Convert both 1-based and 100-based field weights to decimals summing to 1.
normalized_fields AS (
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
            ABS(ft.total_field_weight - 1)
                <= %(decimal_tolerance)s
            OR
            ABS(ft.total_field_weight - 100)
                <= %(percent_tolerance)s
      )
),

-- Number of incoming citation pairs that should be processed for each paper.
expected_pairs AS (
    SELECT
        c.pub_id AS cited_pub_id,
        COUNT(DISTINCT c.cites_pub_id)::integer AS expected_pair_count
    FROM public.citation AS c
    WHERE c.pub_id IS NOT NULL
      AND c.cites_pub_id IS NOT NULL
      AND c.pub_id <> c.cites_pub_id
    GROUP BY c.pub_id
),

-- Number of citation pairs actually completed by the ISC calculation.
processed_pairs AS (
    SELECT
        isc.cited_pub_id,
        COUNT(DISTINCT isc.citing_pub_id)::integer AS processed_pair_count
    FROM public.influential_self_citations AS isc
    GROUP BY isc.cited_pub_id
),

-- Equation 9 stores one adjusted total per paper and target author.
-- Sum all target-author totals to obtain one paper-level adjusted total.
-- Before ISC adjustment, all author/field fractional credits for one citation
-- sum to 1; after adjustment, this paper-level value is between 0 and 1 per
-- incoming citation.
paper_adjusted_totals AS (
    SELECT
        apac.cited_pub_id,
        SUM(apac.total_adjusted_citation) AS paper_adjusted_citations
    FROM public.author_paper_adjusted_citations AS apac
    GROUP BY apac.cited_pub_id
),

paper_status AS (
    SELECT
        p.pub_id,
        COALESCE(ep.expected_pair_count, 0) AS expected_pair_count,
        COALESCE(pp.processed_pair_count, 0) AS processed_pair_count,
        COALESCE(pat.paper_adjusted_citations, 0) AS paper_adjusted_citations,
        CASE
            WHEN COALESCE(ep.expected_pair_count, 0) = 0
                THEN TRUE
            WHEN COALESCE(ep.expected_pair_count, 0)
                 = COALESCE(pp.processed_pair_count, 0)
                 AND pat.cited_pub_id IS NOT NULL
                THEN TRUE
            ELSE FALSE
        END AS is_complete
    FROM public.publication AS p
    LEFT JOIN expected_pairs AS ep
        ON ep.cited_pub_id = p.pub_id
    LEFT JOIN processed_pairs AS pp
        ON pp.cited_pub_id = p.pub_id
    LEFT JOIN paper_adjusted_totals AS pat
        ON pat.cited_pub_id = p.pub_id
),

field_year_groups AS (
    SELECT
        nf.field_name,
        nf.publication_year,

        COUNT(DISTINCT nf.pub_id)::integer AS publication_count,

        COUNT(DISTINCT nf.pub_id) FILTER (
            WHERE ps.is_complete
        )::integer AS complete_publication_count,

        COUNT(DISTINCT nf.pub_id) FILTER (
            WHERE NOT ps.is_complete
        )::integer AS incomplete_publication_count,

        COUNT(DISTINCT nf.pub_id) FILTER (
            WHERE ps.is_complete
              AND ps.expected_pair_count = 0
        )::integer AS zero_citation_publication_count,

        COALESCE(
            SUM(ps.paper_adjusted_citations) FILTER (
                WHERE ps.is_complete
            ),
            0
        ) AS sum_adjusted_citations,

        AVG(ps.paper_adjusted_citations) FILTER (
            WHERE ps.is_complete
        ) AS citation_avg_field_and_year,

        COALESCE(
            SUM(nf.normalized_field_weight) FILTER (
                WHERE ps.is_complete
            ),
            0
        ) AS field_weight_sum,

        COALESCE(
            SUM(
                nf.normalized_field_weight
                * ps.paper_adjusted_citations
            ) FILTER (
                WHERE ps.is_complete
            ),
            0
        ) AS weighted_sum_adjusted_citations,

        (
            SUM(
                nf.normalized_field_weight
                * ps.paper_adjusted_citations
            ) FILTER (
                WHERE ps.is_complete
            )
            /
            NULLIF(
                SUM(nf.normalized_field_weight) FILTER (
                    WHERE ps.is_complete
                ),
                0
            )
        ) AS weighted_citation_avg_field_and_year,

        CASE
            WHEN COUNT(DISTINCT nf.pub_id) = 0 THEN 0
            ELSE
                COUNT(DISTINCT nf.pub_id) FILTER (
                    WHERE ps.is_complete
                )::numeric
                /
                COUNT(DISTINCT nf.pub_id)::numeric
        END AS data_coverage_ratio

    FROM normalized_fields AS nf
    JOIN paper_status AS ps
        ON ps.pub_id = nf.pub_id
    GROUP BY nf.field_name, nf.publication_year
)

INSERT INTO public.field_year_adjusted_citation_average (
    field_name,
    publication_year,
    publication_count,
    complete_publication_count,
    incomplete_publication_count,
    zero_citation_publication_count,
    sum_adjusted_citations,
    citation_avg_field_and_year,
    field_weight_sum,
    weighted_sum_adjusted_citations,
    weighted_citation_avg_field_and_year,
    data_coverage_ratio,
    calculated_at
)
SELECT
    field_name,
    publication_year,
    publication_count,
    complete_publication_count,
    incomplete_publication_count,
    zero_citation_publication_count,
    sum_adjusted_citations,
    citation_avg_field_and_year,
    field_weight_sum,
    weighted_sum_adjusted_citations,
    weighted_citation_avg_field_and_year,
    data_coverage_ratio,
    CURRENT_TIMESTAMP
FROM field_year_groups;
"""


def refresh_field_year_average() -> None:
    """
    Rebuild TC-bar(f,y,adj) from the latest database state.

    Rerun this function after publications, citation pairs, contribution
    weights, ISC rows, or Equation 9 totals change.
    """

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                REFRESH_SQL,
                {
                    "decimal_tolerance": DECIMAL_WEIGHT_TOLERANCE,
                    "percent_tolerance": PERCENT_WEIGHT_TOLERANCE,
                },
            )

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS field_year_group_count,
                    COALESCE(AVG(data_coverage_ratio), 0),
                    COALESCE(MIN(data_coverage_ratio), 0)
                FROM public.field_year_adjusted_citation_average;
                """
            )
            group_count, average_coverage, minimum_coverage = cursor.fetchone()

        connection.commit()

        print("Field-year adjusted citation averages refreshed.")
        print(f"Field-year groups: {group_count}")
        print(f"Average data coverage: {average_coverage}")
        print(f"Minimum data coverage: {minimum_coverage}")

        if minimum_coverage < 1:
            print(
                "Warning: some field-year averages are provisional because "
                "not all citation pairs have completed ISC processing."
            )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    refresh_field_year_average()