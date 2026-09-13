from collections import defaultdict
from decimal import Decimal
from typing import Dict, List
from psycopg2.extras import execute_values

import calculator
from models import AuthorModifiedHIndexResult


def fetch_author_field_weight_and_hindex(connection) -> List[dict]:
    """
    Builds (author_id, field_name, field_weight_sum, modified_hindex_field)
    by:
      - unpivoting author1id..author10id in author_contribution_weight
        to get (pub_id, author_id) authorship pairs
      - unpivoting field1..field3 (name/weight) in field_classification
        to get (pub_id, field_name, Vf_p) pairs
      - joining them on pub_id, then summing Vf_p per (author_id, field_name)
        -> field_weight_sum = sum_p Vf_p
      - left-joining Equation 16's author_field_modified_hindex to attach
        Hf'_{f,a}
    """

    query = """
        WITH paper_authors AS (
            SELECT pub_id, author1id  AS author_id FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author2id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author3id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author4id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author5id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author6id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author7id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author8id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author9id  FROM public.author_contribution_weight
            UNION ALL SELECT pub_id, author10id FROM public.author_contribution_weight
        ),
        paper_fields AS (
            SELECT pub_id, field1_name AS field_name,
                   field1_weight / 100.0 AS field_weight
            FROM public.field_classification
            WHERE field1_name IS NOT NULL AND field1_weight IS NOT NULL

            UNION ALL
            SELECT pub_id, field2_name, field2_weight / 100.0
            FROM public.field_classification
            WHERE field2_name IS NOT NULL AND field2_weight IS NOT NULL

            UNION ALL
            SELECT pub_id, field3_name, field3_weight / 100.0
            FROM public.field_classification
            WHERE field3_name IS NOT NULL AND field3_weight IS NOT NULL
        ),
        author_field_weight AS (
            SELECT
                pa.author_id,
                pf.field_name,
                SUM(pf.field_weight) AS field_weight_sum
            FROM paper_authors pa
            JOIN paper_fields pf ON pf.pub_id = pa.pub_id
            WHERE pa.author_id IS NOT NULL
            GROUP BY pa.author_id, pf.field_name
        )
        SELECT
            afw.author_id,
            afw.field_name,
            afw.field_weight_sum,
            h.modified_hindex_field
        FROM author_field_weight afw
        LEFT JOIN public.author_field_modified_hindex h
            ON h.author_id = afw.author_id
            AND h.field_name = afw.field_name
        ORDER BY afw.author_id, afw.field_name;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [d.name for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_equation_17_results(
    rows: List[dict],
) -> List[AuthorModifiedHIndexResult]:
    """
    NOTE on scope: only fields where Equation 16 has already produced
    a modified_hindex_field are included in BOTH the numerator and the
    denominator, so a missing Hf'_{f,a} does not silently dilute the
    final average. Run Equation 16 fully before this step for the
    most accurate Hf'_a.
    """

    by_author: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        by_author[row["author_id"]].append(row)

    results = []

    for author_id, author_rows in by_author.items():
        weighted_numerator_sum = Decimal("0")
        total_field_weight_sum = Decimal("0")
        field_count = 0

        for row in author_rows:
            if row["modified_hindex_field"] is None:
                continue  # Eq. 16 hasn't produced a value for this field yet

            weight_sum = row["field_weight_sum"] or Decimal("0")
            weighted_numerator_sum += weight_sum * row["modified_hindex_field"]
            total_field_weight_sum += weight_sum
            field_count += 1

        final_value = calculator.equation_17_final_hindex(
            weighted_numerator_sum, total_field_weight_sum
        )

        status = "READY" if final_value is not None else "NO_ELIGIBLE_FIELDS"

        results.append(
            AuthorModifiedHIndexResult(
                author_id=author_id,
                weighted_numerator_sum=weighted_numerator_sum,
                total_field_weight_sum=total_field_weight_sum,
                modified_hindex_final=final_value,
                field_count=field_count,
                calculation_status=status,
            )
        )

    return results


def upsert_equation_17_results(
    connection, results: List[AuthorModifiedHIndexResult]
) -> None:
    if not results:
        return

    rows = [
        (
            r.author_id,
            r.weighted_numerator_sum,
            r.total_field_weight_sum,
            r.modified_hindex_final,
            r.field_count,
            r.calculation_status,
        )
        for r in results
    ]

    query = """
        INSERT INTO public.author_modified_hindex (
            author_id, weighted_numerator_sum, total_field_weight_sum,
            modified_hindex_final, field_count, calculation_status
        )
        VALUES %s
        ON CONFLICT (author_id) DO UPDATE SET
            weighted_numerator_sum = EXCLUDED.weighted_numerator_sum,
            total_field_weight_sum = EXCLUDED.total_field_weight_sum,
            modified_hindex_final = EXCLUDED.modified_hindex_final,
            field_count = EXCLUDED.field_count,
            calculation_status = EXCLUDED.calculation_status,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)