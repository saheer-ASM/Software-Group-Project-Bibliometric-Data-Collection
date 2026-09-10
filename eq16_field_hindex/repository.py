from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple
from psycopg2.extras import execute_values

import calculator
from models import AuthorFieldModifiedHIndexResult


def fetch_effective_citations(connection) -> List[dict]:
    """
    Source data for Equation 16: the Equation 15 output table.
    Only rows with a real (non-NULL) effective_citation are usable
    as papers in the h-index calculation.
    """

    query = """
        SELECT author_id, pub_id, field_name, effective_citation
        FROM public.author_paper_field_effective_citation
        WHERE effective_citation IS NOT NULL
        ORDER BY author_id, field_name, effective_citation DESC;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [d.name for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def group_by_author_field(
    rows: List[dict],
) -> Dict[Tuple[str, str], List[Decimal]]:
    grouped: Dict[Tuple[str, str], List[Decimal]] = defaultdict(list)

    for row in rows:
        key = (row["author_id"], row["field_name"])
        grouped[key].append(row["effective_citation"])

    return grouped


def build_equation_16_results(
    rows: List[dict],
) -> List[AuthorFieldModifiedHIndexResult]:
    grouped = group_by_author_field(rows)

    # --- Pass 1: raw H value per (author, field) -----------------
    raw_h_by_key: Dict[Tuple[str, str], Tuple[int, int]] = {}

    for key, values in grouped.items():
        raw_h_by_key[key] = calculator.compute_raw_h_value(values)

    # --- Field-level normalization Hf'_f --------------------------
    raw_h_by_field: Dict[str, List[int]] = defaultdict(list)

    for (author_id, field_name), (raw_h, _papers_used) in raw_h_by_key.items():
        raw_h_by_field[field_name].append(raw_h)

    field_normalization: Dict[str, Decimal] = {
        field_name: calculator.compute_field_normalization(values)
        for field_name, values in raw_h_by_field.items()
    }

    # --- Pass 2: final per-(author, field) result -------------------
    results = []

    for (author_id, field_name), (raw_h, papers_used) in raw_h_by_key.items():
        normalization = field_normalization.get(field_name)

        modified = calculator.compute_modified_hindex_field(raw_h, normalization)

        status = "READY" if modified is not None else "ZERO_FIELD_NORMALIZATION"

        results.append(
            AuthorFieldModifiedHIndexResult(
                author_id=author_id,
                field_name=field_name,
                raw_h_value=raw_h,
                papers_used=papers_used,
                field_normalization=normalization,
                modified_hindex_field=modified,
                calculation_status=status,
            )
        )

    return results


def upsert_equation_16_results(
    connection, results: List[AuthorFieldModifiedHIndexResult]
) -> None:
    if not results:
        return

    rows = [
        (
            r.author_id,
            r.field_name,
            r.raw_h_value,
            r.papers_used,
            r.field_normalization,
            r.modified_hindex_field,
            r.calculation_status,
        )
        for r in results
    ]

    query = """
        INSERT INTO public.author_field_modified_hindex (
            author_id, field_name, raw_h_value, papers_used,
            field_normalization, modified_hindex_field,
            calculation_status
        )
        VALUES %s
        ON CONFLICT (author_id, field_name) DO UPDATE SET
            raw_h_value = EXCLUDED.raw_h_value,
            papers_used = EXCLUDED.papers_used,
            field_normalization = EXCLUDED.field_normalization,
            modified_hindex_field = EXCLUDED.modified_hindex_field,
            calculation_status = EXCLUDED.calculation_status,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)