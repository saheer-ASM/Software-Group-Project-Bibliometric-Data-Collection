"""Equations 12, 13 and 14 on the LOCAL database.

SQLite port of Equations_12_13_14/repository.py + calculator.py. The cloud code loads
every Equation 11 row into Python lists; with ~37M local rows that is impossible, so
the same rules are evaluated set-based inside SQLite (and numpy for the percentile).
The rules are unchanged:

    Eq 12  TC_cap = min(TC_adj, R_{k,f})          R_{k,f} = k-th percentile (linear
                                                  interpolation = percentile_cont) of
                                                  the adjusted citations of field f
    Eq 13  term   = W * TC_cap / (P * TC_bar_f)   P = distinct papers of the author
    Eq 14  term   = W * TC_cap / (y * TC_bar_{f,y})  y = max(1, as_of_year - pub_year)
    S_a / U_a = CF_com * sum(term over included rows),  CF_com = author.career_compensation

Status resolution is identical to the cloud resolve_status().
"""

from __future__ import annotations

from array import array
from decimal import Decimal

import numpy as np

READY = "READY"
READY_PROVISIONAL_BENCHMARK = "READY_PROVISIONAL_BENCHMARK"
INCOMPLETE_ISC = "INCOMPLETE_ISC"

INCLUDED_SQL = "('READY', 'READY_PROVISIONAL_BENCHMARK')"
EQ11 = "total_cites_equation_11_details"


# ---------------------------------------------------------------------------
# P: distinct publications per author (temp table reused by Eq 13)
# ---------------------------------------------------------------------------
def build_publication_counts(connection) -> None:
    connection.execute("DROP TABLE IF EXISTS temp.tmp_eq13_pub_counts")
    connection.execute(
        f"""
        CREATE TEMP TABLE tmp_eq13_pub_counts AS
        SELECT author_id, COUNT(DISTINCT pub_id) AS publication_count
        FROM {EQ11}
        GROUP BY author_id
        """
    )
    connection.execute(
        "CREATE UNIQUE INDEX temp.idx_tmp_eq13_pc ON tmp_eq13_pub_counts(author_id)")


# ---------------------------------------------------------------------------
# Equation 13 support: TC_bar_f (field-only average, all years combined)
# ---------------------------------------------------------------------------
def compute_field_adjusted_citation_averages(connection) -> list:
    return connection.execute(
        f"""
        SELECT
            field_name,
            COUNT(*) AS publication_count,
            COUNT(DISTINCT pub_id) AS distinct_publication_count,
            COALESCE(SUM(adjusted_citation), 0) AS sum_adjusted_citations,
            AVG(adjusted_citation) AS citation_avg_field,
            COALESCE(SUM(field_weight), 0) AS field_weight_sum,
            COALESCE(SUM(field_weight * adjusted_citation), 0)
                AS weighted_sum_adjusted_citations,
            CASE
                WHEN SUM(field_weight) > 0
                THEN SUM(field_weight * adjusted_citation) / SUM(field_weight)
                ELSE NULL
            END AS weighted_citation_avg_field,
            CASE
                WHEN COUNT(*) > 0
                THEN CAST(COUNT(*) FILTER (
                        WHERE calculation_status IN {INCLUDED_SQL}
                     ) AS REAL) / COUNT(*)
                ELSE 0
            END AS data_coverage_ratio
        FROM {EQ11}
        WHERE adjusted_citation IS NOT NULL
        GROUP BY field_name
        """
    ).fetchall()


def upsert_field_adjusted_citation_averages(connection, rows) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO field_adjusted_citation_average (
            field_name, publication_count, distinct_publication_count,
            sum_adjusted_citations, citation_avg_field, field_weight_sum,
            weighted_sum_adjusted_citations, weighted_citation_avg_field,
            data_coverage_ratio, calculated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, rows)


# ---------------------------------------------------------------------------
# Equation 12: R_{k,f}^{adj} per field
# ---------------------------------------------------------------------------
def compute_field_percentile_caps(connection, percentile_k: Decimal) -> list:
    """One streaming pass over the Eq 11 table; per-field values are kept in compact
    double arrays and the percentile is taken with linear interpolation
    (identical to PostgreSQL percentile_cont)."""
    values: dict[str, array] = {}
    cursor = connection.execute(
        f"SELECT field_name, adjusted_citation FROM {EQ11} "
        f"WHERE adjusted_citation IS NOT NULL")
    while True:
        chunk = cursor.fetchmany(500_000)
        if not chunk:
            break
        for field_name, value in chunk:
            bucket = values.get(field_name)
            if bucket is None:
                bucket = values[field_name] = array("d")
            bucket.append(value)

    rows = []
    for field_name, bucket in values.items():
        data = np.frombuffer(bucket, dtype=np.float64)
        cap = float(np.percentile(data, float(percentile_k)))   # linear interpolation
        rows.append((
            field_name, float(percentile_k), int(data.size),
            float(data.min()), float(data.max()), cap, int((data > cap).sum()),
        ))
    return rows


def upsert_field_percentile_caps(connection, rows) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO field_citation_percentile_caps (
            field_name, percentile_k, sample_size, min_adjusted_citation,
            max_adjusted_citation, cap_threshold, outlier_count, calculated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, rows)


# ---------------------------------------------------------------------------
# Status resolution + terms (same rules as the cloud resolve_status / calculator)
# ---------------------------------------------------------------------------
def _status_sql(denominator: str, missing: str, zero: str) -> str:
    return f"""
        CASE
            WHEN d.adjusted_citation IS NULL THEN 'MISSING_ADJUSTED_CITATION'
            WHEN {denominator} IS NULL THEN '{missing}'
            WHEN {denominator} = 0 THEN '{zero}'
            WHEN c.cap_threshold IS NULL THEN 'MISSING_PERCENTILE_CAP'
            WHEN d.calculation_status = 'INCOMPLETE_ISC' THEN 'INCOMPLETE_ISC'
            WHEN d.calculation_status = 'READY_PROVISIONAL_BENCHMARK'
                THEN 'READY_PROVISIONAL_BENCHMARK'
            ELSE 'READY'
        END
    """


EQ13_SELECT = f"""
WITH base AS (
    SELECT
        d.author_id, d.pub_id, d.field_name,
        d.adjusted_citation,
        :percentile_k AS percentile_k,
        c.cap_threshold,
        MIN(d.adjusted_citation, c.cap_threshold) AS capped_adjusted_citation,
        CASE WHEN d.adjusted_citation IS NOT NULL AND c.cap_threshold IS NOT NULL
                  AND d.adjusted_citation > c.cap_threshold THEN 1 ELSE 0 END AS was_capped,
        d.author_field_weight,
        COALESCE(pc.publication_count, 0) AS publication_count,
        fa.citation_avg_field AS field_average,
        {_status_sql('fa.citation_avg_field', 'MISSING_FIELD_AVERAGE', 'ZERO_FIELD_AVERAGE')}
            AS calculation_status
    FROM {EQ11} AS d
    JOIN author AS a ON a.author_id = d.author_id
    LEFT JOIN tmp_eq13_pub_counts AS pc ON pc.author_id = d.author_id
    LEFT JOIN field_adjusted_citation_average AS fa ON fa.field_name = d.field_name
    LEFT JOIN field_citation_percentile_caps AS c
           ON c.field_name = d.field_name AND c.percentile_k = :percentile_k
),
termed AS (
    SELECT base.*,
        CASE
            WHEN calculation_status IN {INCLUDED_SQL}
             AND capped_adjusted_citation IS NOT NULL
             AND publication_count > 0
             AND field_average IS NOT NULL AND field_average <> 0
            THEN capped_adjusted_citation / (publication_count * field_average)
            ELSE NULL
        END AS normalized_citation_ratio
    FROM base
)
SELECT author_id, pub_id, field_name, adjusted_citation, percentile_k, cap_threshold,
       capped_adjusted_citation, was_capped, author_field_weight, publication_count,
       field_average, normalized_citation_ratio,
       author_field_weight * normalized_citation_ratio AS paper_field_contribution,
       calculation_status
FROM termed
"""

EQ14_SELECT = f"""
WITH base AS (
    SELECT
        d.author_id, d.pub_id, d.field_name, d.publication_year,
        d.adjusted_citation,
        :percentile_k AS percentile_k,
        c.cap_threshold,
        MIN(d.adjusted_citation, c.cap_threshold) AS capped_adjusted_citation,
        CASE WHEN d.adjusted_citation IS NOT NULL AND c.cap_threshold IS NOT NULL
                  AND d.adjusted_citation > c.cap_threshold THEN 1 ELSE 0 END AS was_capped,
        d.author_field_weight,
        MAX(1, :as_of_year - d.publication_year) AS years_elapsed,
        d.field_year_average,
        {_status_sql('d.field_year_average', 'MISSING_FIELD_YEAR_AVERAGE', 'ZERO_FIELD_YEAR_AVERAGE')}
            AS calculation_status
    FROM {EQ11} AS d
    JOIN author AS a ON a.author_id = d.author_id
    LEFT JOIN field_citation_percentile_caps AS c
           ON c.field_name = d.field_name AND c.percentile_k = :percentile_k
),
termed AS (
    SELECT base.*,
        CASE
            WHEN calculation_status IN {INCLUDED_SQL}
             AND capped_adjusted_citation IS NOT NULL
             AND years_elapsed > 0
             AND field_year_average IS NOT NULL AND field_year_average <> 0
            THEN capped_adjusted_citation / (years_elapsed * field_year_average)
            ELSE NULL
        END AS normalized_citation_ratio
    FROM base
)
SELECT author_id, pub_id, field_name, publication_year, adjusted_citation, percentile_k,
       cap_threshold, capped_adjusted_citation, was_capped, author_field_weight,
       years_elapsed, field_year_average, normalized_citation_ratio,
       author_field_weight * normalized_citation_ratio AS paper_field_contribution,
       calculation_status
FROM termed
"""


def insert_equation_13_details(connection, percentile_k: Decimal) -> int:
    before = connection.total_changes
    connection.execute(
        """
        INSERT OR REPLACE INTO citations_per_paper_details (
            author_id, pub_id, field_name, adjusted_citation, percentile_k,
            cap_threshold, capped_adjusted_citation, was_capped, author_field_weight,
            publication_count, field_average, normalized_citation_ratio,
            paper_field_contribution, calculation_status
        ) """ + EQ13_SELECT,
        {"percentile_k": float(percentile_k)})
    return connection.total_changes - before


def insert_equation_14_details(connection, percentile_k: Decimal, as_of_year: int) -> int:
    before = connection.total_changes
    connection.execute(
        """
        INSERT OR REPLACE INTO citation_rate_details (
            author_id, pub_id, field_name, publication_year, adjusted_citation,
            percentile_k, cap_threshold, capped_adjusted_citation, was_capped,
            author_field_weight, years_elapsed, field_year_average,
            normalized_citation_ratio, paper_field_contribution, calculation_status
        ) """ + EQ14_SELECT,
        {"percentile_k": float(percentile_k), "as_of_year": as_of_year})
    return connection.total_changes - before


def status_counts(connection, select_sql: str, params: dict) -> list:
    """Dry run: status distribution without writing."""
    return connection.execute(
        f"SELECT calculation_status, COUNT(*) FROM ({select_sql}) GROUP BY 1 ORDER BY 1",
        params).fetchall()


def aggregate_equation_13(connection) -> int:
    before = connection.total_changes
    connection.execute(
        f"""
        INSERT OR REPLACE INTO author_citations_per_paper (
            author_id, career_factor, publication_count, field_row_count,
            included_field_row_count, provisional_field_row_count,
            skipped_field_row_count, normalized_contribution_sum,
            citations_per_paper_score, calculation_complete, calculated_at
        )
        SELECT
            d.author_id,
            a.career_compensation,
            COALESCE(pc.publication_count, 0),
            COUNT(*),
            COUNT(*) FILTER (WHERE d.calculation_status IN {INCLUDED_SQL}),
            COUNT(*) FILTER (WHERE d.calculation_status = 'READY_PROVISIONAL_BENCHMARK'),
            COUNT(*) FILTER (WHERE d.calculation_status NOT IN {INCLUDED_SQL}),
            COALESCE(SUM(d.paper_field_contribution) FILTER (
                WHERE d.calculation_status IN {INCLUDED_SQL}), 0),
            a.career_compensation * COALESCE(SUM(d.paper_field_contribution) FILTER (
                WHERE d.calculation_status IN {INCLUDED_SQL}), 0),
            CASE WHEN COUNT(*) FILTER (
                WHERE d.calculation_status NOT IN {INCLUDED_SQL}) = 0 THEN 1 ELSE 0 END,
            CURRENT_TIMESTAMP
        FROM citations_per_paper_details AS d
        JOIN author AS a ON a.author_id = d.author_id
        LEFT JOIN tmp_eq13_pub_counts AS pc ON pc.author_id = d.author_id
        GROUP BY d.author_id
        """)
    return connection.total_changes - before


def aggregate_equation_14(connection, as_of_year: int) -> int:
    before = connection.total_changes
    connection.execute(
        f"""
        INSERT OR REPLACE INTO author_citation_rate (
            author_id, career_factor, as_of_year, field_row_count,
            included_field_row_count, provisional_field_row_count,
            skipped_field_row_count, normalized_contribution_sum,
            citation_rate_score, calculation_complete, calculated_at
        )
        SELECT
            d.author_id,
            a.career_compensation,
            :as_of_year,
            COUNT(*),
            COUNT(*) FILTER (WHERE d.calculation_status IN {INCLUDED_SQL}),
            COUNT(*) FILTER (WHERE d.calculation_status = 'READY_PROVISIONAL_BENCHMARK'),
            COUNT(*) FILTER (WHERE d.calculation_status NOT IN {INCLUDED_SQL}),
            COALESCE(SUM(d.paper_field_contribution) FILTER (
                WHERE d.calculation_status IN {INCLUDED_SQL}), 0),
            a.career_compensation * COALESCE(SUM(d.paper_field_contribution) FILTER (
                WHERE d.calculation_status IN {INCLUDED_SQL}), 0),
            CASE WHEN COUNT(*) FILTER (
                WHERE d.calculation_status NOT IN {INCLUDED_SQL}) = 0 THEN 1 ELSE 0 END,
            CURRENT_TIMESTAMP
        FROM citation_rate_details AS d
        JOIN author AS a ON a.author_id = d.author_id
        GROUP BY d.author_id
        """, {"as_of_year": as_of_year})
    return connection.total_changes - before
