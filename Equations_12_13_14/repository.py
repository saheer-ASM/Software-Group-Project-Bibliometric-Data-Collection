from decimal import Decimal
from typing import Dict, List, Tuple

from psycopg2.extras import execute_values

from .models import (
    AuthorCitationRateResult,
    AuthorCitationsPerPaperResult,
    Equation13DetailRow,
    Equation14DetailRow,
    FieldAdjustedCitationAverage,
    FieldCitationPercentileCap,
)


# Equation 11 detail rows whose adjusted citation is not yet trustworthy
# because the influential self-citation pipeline (Equations 7-9) has
# not finished for every citing pair.
UPSTREAM_INCOMPLETE_STATUS = "INCOMPLETE_ISC"

READY = "READY"
READY_PROVISIONAL_BENCHMARK = "READY_PROVISIONAL_BENCHMARK"
INCOMPLETE_ISC = "INCOMPLETE_ISC"
MISSING_ADJUSTED_CITATION = "MISSING_ADJUSTED_CITATION"
MISSING_FIELD_AVERAGE = "MISSING_FIELD_AVERAGE"
ZERO_FIELD_AVERAGE = "ZERO_FIELD_AVERAGE"
MISSING_FIELD_YEAR_AVERAGE = "MISSING_FIELD_YEAR_AVERAGE"
ZERO_FIELD_YEAR_AVERAGE = "ZERO_FIELD_YEAR_AVERAGE"
MISSING_PERCENTILE_CAP = "MISSING_PERCENTILE_CAP"

INCLUDED_STATUSES = {READY, READY_PROVISIONAL_BENCHMARK}


# ---------------------------------------------------------------------------
# Reads from the existing Equation 9 / 11 pipeline and the author sheet.
# ---------------------------------------------------------------------------

def fetch_equation_11_rows(connection) -> List[dict]:
    """
    One row per (author, publication, field), sourced from the already
    populated Equation 9 / 11 pipeline plus CF_com from the author sheet
    (public.author.career_compensation, the Equation 10 result).
    """

    query = """
        SELECT
            d.author_id,
            d.pub_id,
            d.field_name,
            d.publication_year,
            d.author_field_weight,
            d.adjusted_citation,
            d.field_year_average,
            d.calculation_status AS eq11_status,
            a.career_compensation
        FROM public.total_cites_equation_11_details d
        JOIN public.author a
            ON a.author_id = d.author_id
        ORDER BY d.author_id, d.pub_id, d.field_name;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [description.name for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_publication_counts(connection) -> Dict[str, int]:
    """
    P: distinct publication count per author, over the same population
    used by Equations 9 and 11.
    """

    query = """
        SELECT author_id, COUNT(DISTINCT pub_id)
        FROM public.total_cites_equation_11_details
        GROUP BY author_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        return {author_id: count for author_id, count in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Equation 13 support: TC_bar_f (field-only average, all years combined).
# ---------------------------------------------------------------------------

def compute_field_adjusted_citation_averages(
    connection,
) -> Dict[str, FieldAdjustedCitationAverage]:
    query = """
        SELECT
            field_name,
            COUNT(*) AS publication_count,
            COUNT(DISTINCT pub_id) AS distinct_publication_count,
            SUM(adjusted_citation) AS sum_adjusted_citations,
            AVG(adjusted_citation) AS citation_avg_field,
            SUM(field_weight) AS field_weight_sum,
            SUM(field_weight * adjusted_citation)
                AS weighted_sum_adjusted_citations,
            CASE
                WHEN SUM(field_weight) > 0
                THEN SUM(field_weight * adjusted_citation)
                     / SUM(field_weight)
                ELSE NULL
            END AS weighted_citation_avg_field,
            CASE
                WHEN COUNT(*) > 0
                THEN COUNT(*) FILTER (
                        WHERE calculation_status IN (%s, %s)
                     )::numeric / COUNT(*)
                ELSE 0
            END AS data_coverage_ratio
        FROM public.total_cites_equation_11_details
        WHERE adjusted_citation IS NOT NULL
        GROUP BY field_name;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (READY, READY_PROVISIONAL_BENCHMARK),
        )

        results = {}

        for row in cursor.fetchall():
            (
                field_name,
                publication_count,
                distinct_publication_count,
                sum_adjusted_citations,
                citation_avg_field,
                field_weight_sum,
                weighted_sum_adjusted_citations,
                weighted_citation_avg_field,
                data_coverage_ratio,
            ) = row

            results[field_name] = FieldAdjustedCitationAverage(
                field_name=field_name,
                publication_count=publication_count,
                distinct_publication_count=distinct_publication_count,
                sum_adjusted_citations=sum_adjusted_citations or Decimal("0"),
                citation_avg_field=citation_avg_field,
                field_weight_sum=field_weight_sum or Decimal("0"),
                weighted_sum_adjusted_citations=(
                    weighted_sum_adjusted_citations or Decimal("0")
                ),
                weighted_citation_avg_field=weighted_citation_avg_field,
                data_coverage_ratio=data_coverage_ratio or Decimal("0"),
            )

        return results


def upsert_field_adjusted_citation_averages(
    connection,
    averages: List[FieldAdjustedCitationAverage],
) -> None:
    if not averages:
        return

    rows = [
        (
            a.field_name,
            a.publication_count,
            a.distinct_publication_count,
            a.sum_adjusted_citations,
            a.citation_avg_field,
            a.field_weight_sum,
            a.weighted_sum_adjusted_citations,
            a.weighted_citation_avg_field,
            a.data_coverage_ratio,
        )
        for a in averages
    ]

    query = """
        INSERT INTO public.field_adjusted_citation_average (
            field_name,
            publication_count,
            distinct_publication_count,
            sum_adjusted_citations,
            citation_avg_field,
            field_weight_sum,
            weighted_sum_adjusted_citations,
            weighted_citation_avg_field,
            data_coverage_ratio
        )
        VALUES %s
        ON CONFLICT (field_name) DO UPDATE SET
            publication_count = EXCLUDED.publication_count,
            distinct_publication_count =
                EXCLUDED.distinct_publication_count,
            sum_adjusted_citations = EXCLUDED.sum_adjusted_citations,
            citation_avg_field = EXCLUDED.citation_avg_field,
            field_weight_sum = EXCLUDED.field_weight_sum,
            weighted_sum_adjusted_citations =
                EXCLUDED.weighted_sum_adjusted_citations,
            weighted_citation_avg_field =
                EXCLUDED.weighted_citation_avg_field,
            data_coverage_ratio = EXCLUDED.data_coverage_ratio,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)


# ---------------------------------------------------------------------------
# Equation 12: R_{k,f}^{adj} per field.
# ---------------------------------------------------------------------------

def compute_field_percentile_caps(
    connection,
    percentile_k: Decimal,
) -> Dict[str, FieldCitationPercentileCap]:
    query = """
        WITH stats AS (
            SELECT
                field_name,
                COUNT(*) AS sample_size,
                MIN(adjusted_citation) AS min_adjusted_citation,
                MAX(adjusted_citation) AS max_adjusted_citation,
                (percentile_cont(%s / 100.0) WITHIN GROUP (
                    ORDER BY adjusted_citation
                ))::numeric AS cap_threshold
            FROM public.total_cites_equation_11_details
            WHERE adjusted_citation IS NOT NULL
            GROUP BY field_name
        )
        SELECT
            s.field_name,
            s.sample_size,
            s.min_adjusted_citation,
            s.max_adjusted_citation,
            s.cap_threshold,
            COUNT(d.adjusted_citation) FILTER (
                WHERE d.adjusted_citation > s.cap_threshold
            ) AS outlier_count
        FROM stats s
        JOIN public.total_cites_equation_11_details d
            ON d.field_name = s.field_name
            AND d.adjusted_citation IS NOT NULL
        GROUP BY
            s.field_name,
            s.sample_size,
            s.min_adjusted_citation,
            s.max_adjusted_citation,
            s.cap_threshold;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (percentile_k,))

        results = {}

        for row in cursor.fetchall():
            (
                field_name,
                sample_size,
                min_adjusted_citation,
                max_adjusted_citation,
                cap_threshold,
                outlier_count,
            ) = row

            results[field_name] = FieldCitationPercentileCap(
                field_name=field_name,
                percentile_k=percentile_k,
                sample_size=sample_size,
                min_adjusted_citation=min_adjusted_citation,
                max_adjusted_citation=max_adjusted_citation,
                cap_threshold=cap_threshold,
                outlier_count=outlier_count,
            )

        return results


def upsert_field_percentile_caps(
    connection,
    caps: List[FieldCitationPercentileCap],
) -> None:
    if not caps:
        return

    rows = [
        (
            c.field_name,
            c.percentile_k,
            c.sample_size,
            c.min_adjusted_citation,
            c.max_adjusted_citation,
            c.cap_threshold,
            c.outlier_count,
        )
        for c in caps
    ]

    query = """
        INSERT INTO public.field_citation_percentile_caps (
            field_name,
            percentile_k,
            sample_size,
            min_adjusted_citation,
            max_adjusted_citation,
            cap_threshold,
            outlier_count
        )
        VALUES %s
        ON CONFLICT (field_name, percentile_k) DO UPDATE SET
            sample_size = EXCLUDED.sample_size,
            min_adjusted_citation = EXCLUDED.min_adjusted_citation,
            max_adjusted_citation = EXCLUDED.max_adjusted_citation,
            cap_threshold = EXCLUDED.cap_threshold,
            outlier_count = EXCLUDED.outlier_count,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)


# ---------------------------------------------------------------------------
# Status resolution shared by Equation 13 and Equation 14 rows.
# ---------------------------------------------------------------------------

def resolve_status(
    *,
    adjusted_citation,
    denominator,
    cap_threshold,
    eq11_status: str,
    missing_denominator_status: str,
    zero_denominator_status: str,
    provisional_status: str = READY_PROVISIONAL_BENCHMARK,
) -> str:
    if adjusted_citation is None:
        return MISSING_ADJUSTED_CITATION

    if denominator is None:
        return missing_denominator_status

    if denominator == Decimal("0"):
        return zero_denominator_status

    if cap_threshold is None:
        return MISSING_PERCENTILE_CAP

    if eq11_status == UPSTREAM_INCOMPLETE_STATUS:
        return INCOMPLETE_ISC

    if eq11_status == provisional_status:
        return provisional_status

    return READY


# ---------------------------------------------------------------------------
# Equation 13: outlier-controlled, field-normalized citations per paper.
# ---------------------------------------------------------------------------

def build_equation_13_details(
    equation_11_rows: List[dict],
    publication_counts: Dict[str, int],
    field_averages: Dict[str, FieldAdjustedCitationAverage],
    percentile_caps: Dict[str, FieldCitationPercentileCap],
    percentile_k: Decimal,
) -> List[Equation13DetailRow]:
    from . import calculator

    details = []

    for row in equation_11_rows:
        field_average_row = field_averages.get(row["field_name"])
        field_average = (
            field_average_row.citation_avg_field
            if field_average_row is not None
            else None
        )

        cap_row = percentile_caps.get(row["field_name"])
        cap_threshold = cap_row.cap_threshold if cap_row is not None else None

        status = resolve_status(
            adjusted_citation=row["adjusted_citation"],
            denominator=field_average,
            cap_threshold=cap_threshold,
            eq11_status=row["eq11_status"],
            missing_denominator_status=MISSING_FIELD_AVERAGE,
            zero_denominator_status=ZERO_FIELD_AVERAGE,
        )

        capped_adjusted_citation = calculator.cap_adjusted_citation(
            row["adjusted_citation"], cap_threshold
        )

        publication_count = publication_counts.get(row["author_id"], 0)

        normalized_citation_ratio = None
        paper_field_contribution = None

        if status in INCLUDED_STATUSES:
            normalized_citation_ratio, paper_field_contribution = (
                calculator.equation_13_term(
                    row["author_field_weight"],
                    capped_adjusted_citation,
                    publication_count,
                    field_average,
                )
            )

        details.append(
            Equation13DetailRow(
                author_id=row["author_id"],
                pub_id=row["pub_id"],
                field_name=row["field_name"],
                adjusted_citation=row["adjusted_citation"],
                percentile_k=percentile_k,
                cap_threshold=cap_threshold,
                capped_adjusted_citation=capped_adjusted_citation,
                was_capped=calculator.is_capped(
                    row["adjusted_citation"], cap_threshold
                ),
                author_field_weight=row["author_field_weight"],
                publication_count=publication_count,
                field_average=field_average,
                normalized_citation_ratio=normalized_citation_ratio,
                paper_field_contribution=paper_field_contribution,
                calculation_status=status,
            )
        )

    return details


def aggregate_equation_13(
    details: List[Equation13DetailRow],
    career_factors: Dict[str, Decimal],
    publication_counts: Dict[str, int],
) -> List[AuthorCitationsPerPaperResult]:
    from . import calculator

    by_author: Dict[str, List[Equation13DetailRow]] = {}
    for detail in details:
        by_author.setdefault(detail.author_id, []).append(detail)

    results = []

    for author_id, rows in by_author.items():
        included = [r for r in rows if r.calculation_status in INCLUDED_STATUSES]
        provisional = [
            r for r in rows
            if r.calculation_status == READY_PROVISIONAL_BENCHMARK
        ]
        skipped = [r for r in rows if r.calculation_status not in INCLUDED_STATUSES]

        normalized_contribution_sum = sum(
            (r.paper_field_contribution for r in included),
            Decimal("0"),
        )

        career_factor = career_factors[author_id]

        citations_per_paper_score = (
            calculator.equation_13_score(career_factor, normalized_contribution_sum)
            if rows
            else None
        )

        results.append(
            AuthorCitationsPerPaperResult(
                author_id=author_id,
                career_factor=career_factor,
                publication_count=publication_counts.get(author_id, 0),
                field_row_count=len(rows),
                included_field_row_count=len(included),
                provisional_field_row_count=len(provisional),
                skipped_field_row_count=len(skipped),
                normalized_contribution_sum=normalized_contribution_sum,
                citations_per_paper_score=citations_per_paper_score,
                calculation_complete=(len(skipped) == 0),
            )
        )

    return results


def upsert_equation_13_details(
    connection, details: List[Equation13DetailRow]
) -> None:
    if not details:
        return

    rows = [
        (
            d.author_id,
            d.pub_id,
            d.field_name,
            d.adjusted_citation,
            d.percentile_k,
            d.cap_threshold,
            d.capped_adjusted_citation,
            d.was_capped,
            d.author_field_weight,
            d.publication_count,
            d.field_average,
            d.normalized_citation_ratio,
            d.paper_field_contribution,
            d.calculation_status,
        )
        for d in details
    ]

    query = """
        INSERT INTO public.citations_per_paper_details (
            author_id, pub_id, field_name,
            adjusted_citation, percentile_k, cap_threshold,
            capped_adjusted_citation, was_capped,
            author_field_weight, publication_count, field_average,
            normalized_citation_ratio, paper_field_contribution,
            calculation_status
        )
        VALUES %s
        ON CONFLICT (author_id, pub_id, field_name) DO UPDATE SET
            adjusted_citation = EXCLUDED.adjusted_citation,
            percentile_k = EXCLUDED.percentile_k,
            cap_threshold = EXCLUDED.cap_threshold,
            capped_adjusted_citation = EXCLUDED.capped_adjusted_citation,
            was_capped = EXCLUDED.was_capped,
            author_field_weight = EXCLUDED.author_field_weight,
            publication_count = EXCLUDED.publication_count,
            field_average = EXCLUDED.field_average,
            normalized_citation_ratio = EXCLUDED.normalized_citation_ratio,
            paper_field_contribution = EXCLUDED.paper_field_contribution,
            calculation_status = EXCLUDED.calculation_status,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)


def upsert_author_citations_per_paper(
    connection, results: List[AuthorCitationsPerPaperResult]
) -> None:
    if not results:
        return

    rows = [
        (
            r.author_id,
            r.career_factor,
            r.publication_count,
            r.field_row_count,
            r.included_field_row_count,
            r.provisional_field_row_count,
            r.skipped_field_row_count,
            r.normalized_contribution_sum,
            r.citations_per_paper_score,
            r.calculation_complete,
        )
        for r in results
    ]

    query = """
        INSERT INTO public.author_citations_per_paper (
            author_id, career_factor, publication_count,
            field_row_count, included_field_row_count,
            provisional_field_row_count, skipped_field_row_count,
            normalized_contribution_sum, citations_per_paper_score,
            calculation_complete
        )
        VALUES %s
        ON CONFLICT (author_id) DO UPDATE SET
            career_factor = EXCLUDED.career_factor,
            publication_count = EXCLUDED.publication_count,
            field_row_count = EXCLUDED.field_row_count,
            included_field_row_count = EXCLUDED.included_field_row_count,
            provisional_field_row_count =
                EXCLUDED.provisional_field_row_count,
            skipped_field_row_count = EXCLUDED.skipped_field_row_count,
            normalized_contribution_sum =
                EXCLUDED.normalized_contribution_sum,
            citations_per_paper_score = EXCLUDED.citations_per_paper_score,
            calculation_complete = EXCLUDED.calculation_complete,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)


# ---------------------------------------------------------------------------
# Equation 14: outlier-controlled, field- and year-normalized citation rate.
# ---------------------------------------------------------------------------

def build_equation_14_details(
    equation_11_rows: List[dict],
    percentile_caps: Dict[str, FieldCitationPercentileCap],
    percentile_k: Decimal,
    as_of_year: int,
) -> List[Equation14DetailRow]:
    from . import calculator

    details = []

    for row in equation_11_rows:
        cap_row = percentile_caps.get(row["field_name"])
        cap_threshold = cap_row.cap_threshold if cap_row is not None else None

        status = resolve_status(
            adjusted_citation=row["adjusted_citation"],
            denominator=row["field_year_average"],
            cap_threshold=cap_threshold,
            eq11_status=row["eq11_status"],
            missing_denominator_status=MISSING_FIELD_YEAR_AVERAGE,
            zero_denominator_status=ZERO_FIELD_YEAR_AVERAGE,
        )

        capped_adjusted_citation = calculator.cap_adjusted_citation(
            row["adjusted_citation"], cap_threshold
        )

        years = calculator.years_elapsed(as_of_year, row["publication_year"])

        normalized_citation_ratio = None
        paper_field_contribution = None

        if status in INCLUDED_STATUSES:
            normalized_citation_ratio, paper_field_contribution = (
                calculator.equation_14_term(
                    row["author_field_weight"],
                    capped_adjusted_citation,
                    years,
                    row["field_year_average"],
                )
            )

        details.append(
            Equation14DetailRow(
                author_id=row["author_id"],
                pub_id=row["pub_id"],
                field_name=row["field_name"],
                publication_year=row["publication_year"],
                adjusted_citation=row["adjusted_citation"],
                percentile_k=percentile_k,
                cap_threshold=cap_threshold,
                capped_adjusted_citation=capped_adjusted_citation,
                was_capped=calculator.is_capped(
                    row["adjusted_citation"], cap_threshold
                ),
                author_field_weight=row["author_field_weight"],
                years_elapsed=years,
                field_year_average=row["field_year_average"],
                normalized_citation_ratio=normalized_citation_ratio,
                paper_field_contribution=paper_field_contribution,
                calculation_status=status,
            )
        )

    return details


def aggregate_equation_14(
    details: List[Equation14DetailRow],
    career_factors: Dict[str, Decimal],
    as_of_year: int,
) -> List[AuthorCitationRateResult]:
    from . import calculator

    by_author: Dict[str, List[Equation14DetailRow]] = {}
    for detail in details:
        by_author.setdefault(detail.author_id, []).append(detail)

    results = []

    for author_id, rows in by_author.items():
        included = [r for r in rows if r.calculation_status in INCLUDED_STATUSES]
        provisional = [
            r for r in rows
            if r.calculation_status == READY_PROVISIONAL_BENCHMARK
        ]
        skipped = [r for r in rows if r.calculation_status not in INCLUDED_STATUSES]

        normalized_contribution_sum = sum(
            (r.paper_field_contribution for r in included),
            Decimal("0"),
        )

        career_factor = career_factors[author_id]

        citation_rate_score = (
            calculator.equation_14_score(career_factor, normalized_contribution_sum)
            if rows
            else None
        )

        results.append(
            AuthorCitationRateResult(
                author_id=author_id,
                career_factor=career_factor,
                as_of_year=as_of_year,
                field_row_count=len(rows),
                included_field_row_count=len(included),
                provisional_field_row_count=len(provisional),
                skipped_field_row_count=len(skipped),
                normalized_contribution_sum=normalized_contribution_sum,
                citation_rate_score=citation_rate_score,
                calculation_complete=(len(skipped) == 0),
            )
        )

    return results


def upsert_equation_14_details(
    connection, details: List[Equation14DetailRow]
) -> None:
    if not details:
        return

    rows = [
        (
            d.author_id,
            d.pub_id,
            d.field_name,
            d.publication_year,
            d.adjusted_citation,
            d.percentile_k,
            d.cap_threshold,
            d.capped_adjusted_citation,
            d.was_capped,
            d.author_field_weight,
            d.years_elapsed,
            d.field_year_average,
            d.normalized_citation_ratio,
            d.paper_field_contribution,
            d.calculation_status,
        )
        for d in details
    ]

    query = """
        INSERT INTO public.citation_rate_details (
            author_id, pub_id, field_name, publication_year,
            adjusted_citation, percentile_k, cap_threshold,
            capped_adjusted_citation, was_capped,
            author_field_weight, years_elapsed, field_year_average,
            normalized_citation_ratio, paper_field_contribution,
            calculation_status
        )
        VALUES %s
        ON CONFLICT (author_id, pub_id, field_name) DO UPDATE SET
            publication_year = EXCLUDED.publication_year,
            adjusted_citation = EXCLUDED.adjusted_citation,
            percentile_k = EXCLUDED.percentile_k,
            cap_threshold = EXCLUDED.cap_threshold,
            capped_adjusted_citation = EXCLUDED.capped_adjusted_citation,
            was_capped = EXCLUDED.was_capped,
            author_field_weight = EXCLUDED.author_field_weight,
            years_elapsed = EXCLUDED.years_elapsed,
            field_year_average = EXCLUDED.field_year_average,
            normalized_citation_ratio = EXCLUDED.normalized_citation_ratio,
            paper_field_contribution = EXCLUDED.paper_field_contribution,
            calculation_status = EXCLUDED.calculation_status,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)


def upsert_author_citation_rate(
    connection, results: List[AuthorCitationRateResult]
) -> None:
    if not results:
        return

    rows = [
        (
            r.author_id,
            r.career_factor,
            r.as_of_year,
            r.field_row_count,
            r.included_field_row_count,
            r.provisional_field_row_count,
            r.skipped_field_row_count,
            r.normalized_contribution_sum,
            r.citation_rate_score,
            r.calculation_complete,
        )
        for r in results
    ]

    query = """
        INSERT INTO public.author_citation_rate (
            author_id, career_factor, as_of_year,
            field_row_count, included_field_row_count,
            provisional_field_row_count, skipped_field_row_count,
            normalized_contribution_sum, citation_rate_score,
            calculation_complete
        )
        VALUES %s
        ON CONFLICT (author_id) DO UPDATE SET
            career_factor = EXCLUDED.career_factor,
            as_of_year = EXCLUDED.as_of_year,
            field_row_count = EXCLUDED.field_row_count,
            included_field_row_count = EXCLUDED.included_field_row_count,
            provisional_field_row_count =
                EXCLUDED.provisional_field_row_count,
            skipped_field_row_count = EXCLUDED.skipped_field_row_count,
            normalized_contribution_sum =
                EXCLUDED.normalized_contribution_sum,
            citation_rate_score = EXCLUDED.citation_rate_score,
            calculation_complete = EXCLUDED.calculation_complete,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)
