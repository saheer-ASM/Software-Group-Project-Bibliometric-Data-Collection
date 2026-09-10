from typing import List
from psycopg2.extras import execute_values

import calculator
from models import Equation15DetailRow


def fetch_equation_15_source_rows(connection) -> List[dict]:
    """
    Pulls the already-computed Equation 12/13 fields
    (author_field_weight, capped_adjusted_citation) straight from
    citations_per_paper_details, plus CFcom from public.author.
    """

    query = """
        SELECT
            d.author_id,
            d.pub_id,
            d.field_name,
            d.author_field_weight,
            d.capped_adjusted_citation,
            d.calculation_status,
            a.career_compensation
        FROM public.citations_per_paper_details d
        JOIN public.author a
            ON a.author_id = d.author_id
        ORDER BY d.author_id, d.pub_id, d.field_name;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [description.name for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_equation_15_details(
    source_rows: List[dict],
) -> List[Equation15DetailRow]:
    details = []

    for row in source_rows:
        effective_citation = calculator.equation_15_effective_citation(
            row["career_compensation"],
            row["author_field_weight"],
            row["capped_adjusted_citation"],
        )

        status = "READY" if effective_citation is not None else "MISSING_VALUE"

        details.append(
            Equation15DetailRow(
                author_id=row["author_id"],
                pub_id=row["pub_id"],
                field_name=row["field_name"],
                career_factor=row["career_compensation"],
                author_field_weight=row["author_field_weight"],
                capped_adjusted_citation=row["capped_adjusted_citation"],
                effective_citation=effective_citation,
                calculation_status=status,
            )
        )

    return details


def upsert_equation_15_details(
    connection, details: List[Equation15DetailRow]
) -> None:
    if not details:
        return

    rows = [
        (
            d.author_id,
            d.pub_id,
            d.field_name,
            d.career_factor,
            d.author_field_weight,
            d.capped_adjusted_citation,
            d.effective_citation,
            d.calculation_status,
        )
        for d in details
    ]

    query = """
        INSERT INTO public.author_paper_field_effective_citation (
            author_id, pub_id, field_name,
            career_factor, author_field_weight,
            capped_adjusted_citation, effective_citation,
            calculation_status
        )
        VALUES %s
        ON CONFLICT (author_id, pub_id, field_name) DO UPDATE SET
            career_factor = EXCLUDED.career_factor,
            author_field_weight = EXCLUDED.author_field_weight,
            capped_adjusted_citation = EXCLUDED.capped_adjusted_citation,
            effective_citation = EXCLUDED.effective_citation,
            calculation_status = EXCLUDED.calculation_status,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)