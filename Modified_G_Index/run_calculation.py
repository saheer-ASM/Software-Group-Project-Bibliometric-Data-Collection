import pandas as pd
from psycopg2.extras import execute_values

from datetime import datetime

from .db_connection import get_connection
from .db_setup import create_modified_g_index_tables
from .calculator import ModifiedGIndexCalculator
from .config import TABLE_COLUMNS


# =============================================================
# SQL IDENTIFIER HELPER
# =============================================================

def quote_identifier(identifier):
    """
    Safely quote a PostgreSQL identifier.
    """

    return '"' + identifier.replace('"', '""') + '"'


# =============================================================
# LOAD EFFECTIVE CITATIONS
# =============================================================

def load_effective_citations(connection):
    """
    Load per (paper, author, field) effective-citation data.

    Same source table as modified_hm_index -- unique at (pub_id,
    author_id, field_name). Only calculation_status = 'READY' rows
    are loaded (252 rows currently sit at MISSING_VALUE and are
    excluded, matching modified_hm_index's filter).
    """

    config = TABLE_COLUMNS["author_paper_field_effective_citation"]

    table = quote_identifier(config["table"])
    paper_id = quote_identifier(config["paper_id"])
    author_id = quote_identifier(config["author_id"])
    field_id = quote_identifier(config["field_id"])
    career_factor = quote_identifier(config["career_factor"])
    author_field_weight = quote_identifier(config["author_field_weight"])
    citation = quote_identifier(config["capped_adjusted_citations"])
    calculation_status = quote_identifier(config["calculation_status"])

    query = f"""
        SELECT
            {paper_id} AS paper_id,
            {author_id} AS author_id,
            {field_id} AS field_id,
            {career_factor} AS career_factor,
            {author_field_weight} AS author_field_weight,
            {citation} AS capped_adjusted_citations
        FROM {table}
        WHERE {calculation_status} = 'READY'
          AND {citation} IS NOT NULL
    """

    print("Fetching effective citation data (paper, author, field level)...")

    dataframe = pd.read_sql(query, connection)

    print(f"  Loaded {len(dataframe)} paper-author-field effective citation records")

    return dataframe


# =============================================================
# APPLY CITATION OUTLIER CAP
#
# Same flat, uniform cap already applied in modified_hm_index (150),
# applied here for consistency across the Hf/Hm/g sub-index family --
# all three share the same TCeff input pipeline.
# =============================================================

OUTLIER_CITATION_CAP = ModifiedGIndexCalculator.OUTLIER_CITATION_CAP


def apply_citation_outlier_cap(paper_citations, cap=OUTLIER_CITATION_CAP):
    paper_citations = paper_citations.copy()

    paper_citations["capped_adjusted_citations"] = pd.to_numeric(
        paper_citations["capped_adjusted_citations"],
        errors="coerce",
    )

    before_count = (
        paper_citations["capped_adjusted_citations"] > cap
    ).sum()

    paper_citations["capped_adjusted_citations"] = (
        paper_citations["capped_adjusted_citations"].clip(upper=cap)
    )

    print(
        f"  Applied outlier cap of {cap} citations "
        f"({before_count} record(s) were above the cap and got truncated)"
    )

    return paper_citations


# =============================================================
# LOAD PAPER FIELDS
# =============================================================

def load_paper_fields(connection):
    """
    Convert the wide paper field structure (field1_name/weight,
    field2_name/weight, field3_name/weight) into a normalized
    (paper_id, field_id, field_weight) DataFrame. field_weight is
    stored as 0-100 in the DB and is converted to a 0-1 proportion
    here, matching modified_hm_index.
    """

    config = TABLE_COLUMNS["field_classification"]

    table = quote_identifier(config["table"])
    paper_id = quote_identifier(config["paper_id"])

    field_columns = config["field_id_columns"]
    weight_columns = config["field_weight_columns"]

    queries = []

    for field_column, weight_column in zip(field_columns, weight_columns):
        field_column_sql = quote_identifier(field_column)
        weight_column_sql = quote_identifier(weight_column)

        query = f"""
            SELECT
                {paper_id} AS paper_id,
                {field_column_sql} AS field_id,
                {weight_column_sql} AS field_weight
            FROM {table}
            WHERE {field_column_sql} IS NOT NULL
              AND {weight_column_sql} IS NOT NULL
        """

        queries.append(query)

    final_query = "\nUNION ALL\n".join(queries)

    print("Fetching paper-field data...")

    dataframe = pd.read_sql(final_query, connection)

    dataframe["field_weight"] = (
        pd.to_numeric(dataframe["field_weight"], errors="coerce") / 100.0
    )

    print(f"  Loaded {len(dataframe)} paper-field records")

    return dataframe


# =============================================================
# LOAD ALL DATABASE DATA
# =============================================================

def get_data_from_database():
    connection = get_connection()

    try:
        print()
        print("=" * 60)
        print("LOADING DATABASE DATA")
        print("=" * 60)

        effective_citations = load_effective_citations(connection)
        effective_citations = apply_citation_outlier_cap(effective_citations)

        field_classification = load_paper_fields(connection)

        return {
            "effective_citations": effective_citations,
            "field_classification": field_classification,
        }

    finally:
        connection.close()


# =============================================================
# ENSURE THE modified_g_index COLUMN EXISTS
# =============================================================

def ensure_modified_g_index_column(connection):
    config = TABLE_COLUMNS["author"]
    table = quote_identifier(config["table"])
    column = quote_identifier(config["modified_g_index"])

    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} NUMERIC;"
        )
    connection.commit()


# =============================================================
# UPDATE AUTHOR TABLE
# =============================================================

def update_authors_table(results):
    connection = get_connection()
    cursor = connection.cursor()

    config = TABLE_COLUMNS["author"]

    try:
        connection.autocommit = False

        ensure_modified_g_index_column(connection)

        table = quote_identifier(config["table"])
        author_id = quote_identifier(config["author_id"])
        modified_g_index = quote_identifier(config["modified_g_index"])

        update_sql = f"""
            UPDATE {table}
            SET {modified_g_index} = %s
            WHERE {author_id} = %s
        """

        print()
        print("=" * 60)
        print("UPDATING AUTHOR TABLE")
        print("=" * 60)

        updated_count = 0
        total_authors = len(results)

        for index, (_, row) in enumerate(results.iterrows(), start=1):
            cursor.execute(
                update_sql,
                (
                    float(row["modified_g_index"]),
                    row["author_id"],
                ),
            )

            updated_count += 1

            if updated_count % 500 == 0 or index == total_authors:
                percentage = (index / total_authors) * 100
                print(f"[{index}/{total_authors}] {percentage:6.2f}% updated")

        connection.commit()

        print(f"Successfully updated {updated_count} authors.")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# =============================================================
# UPSERT INTO public.modified_g_index_results (the dedicated,
# already-designed 4-table schema from db_setup.py -- previously
# created but never populated by any pipeline).
# =============================================================

def upsert_g_index_results(connection, results):
    if results.empty:
        return

    rows = [
        (
            row["author_id"],
            int(row["field_row_count"]),
            int(row["included_field_row_count"]),
            int(row["skipped_field_row_count"]),
            float(row["field_weight_total"]),
            float(row["weighted_g_sum"]),
            float(row["modified_g_index"]),
            bool(row["calculation_complete"]),
        )
        for _, row in results.iterrows()
    ]

    query = """
        INSERT INTO public.modified_g_index_results (
            author_id, field_row_count, included_field_row_count,
            skipped_field_row_count, field_weight_total, weighted_g_sum,
            modified_g_index, calculation_complete
        )
        VALUES %s
        ON CONFLICT (author_id) DO UPDATE SET
            field_row_count = EXCLUDED.field_row_count,
            included_field_row_count = EXCLUDED.included_field_row_count,
            skipped_field_row_count = EXCLUDED.skipped_field_row_count,
            field_weight_total = EXCLUDED.field_weight_total,
            weighted_g_sum = EXCLUDED.weighted_g_sum,
            modified_g_index = EXCLUDED.modified_g_index,
            calculation_complete = EXCLUDED.calculation_complete,
            calculated_at = CURRENT_TIMESTAMP;
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)


def save_g_index_results_table(results):
    connection = get_connection()

    try:
        connection.autocommit = False

        print()
        print("=" * 60)
        print("POPULATING public.modified_g_index_results")
        print("=" * 60)

        create_modified_g_index_tables(connection)
        upsert_g_index_results(connection, results)

        connection.commit()

        print(f"Wrote {len(results)} row(s) to public.modified_g_index_results.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================
# MAIN
# =============================================================

def main():
    print()
    print("=" * 60)
    print("MODIFIED G-INDEX CALCULATION")
    print("=" * 60)
    print(f"Started: {datetime.now()}")

    try:
        print()
        print("STEP 1: Loading database data...")

        data = get_data_from_database()

        print()
        print("STEP 2: Calculating Modified g-index...")
        print(
            "  (field normalization G'_f is computed internally by the "
            "calculator, as a running field-average value -- see calculator.py)"
        )

        calculator = ModifiedGIndexCalculator()

        results = calculator.calculate(
            effective_citations=data["effective_citations"],
            field_classification=data["field_classification"],
        )

        print(f"  Calculated Modified g-index for {len(results)} authors")

        print()
        print("STEP 3: RESULTS SUMMARY")
        print("-" * 60)
        print(f"Total authors: {len(results)}")
        print(f"Average Modified g-index: {results['modified_g_index'].mean():.4f}")
        print(f"Minimum Modified g-index: {results['modified_g_index'].min():.4f}")
        print(f"Maximum Modified g-index: {results['modified_g_index'].max():.4f}")
        print(
            f"Authors with a non-zero Modified g-index: "
            f"{(results['modified_g_index'] > 0).sum()} / {len(results)}"
        )

        print()
        print("Top 5 Authors:")
        top_authors = results.nlargest(5, "modified_g_index")
        for _, row in top_authors.iterrows():
            print(f"  Author {row['author_id']}: {row['modified_g_index']:.4f}")

        print()
        print("STEP 4: Updating author table...")

        update_authors_table(results)

        print()
        print("STEP 5: Populating public.modified_g_index_results...")

        save_g_index_results_table(results)

        print()
        print("=" * 60)
        print("MODIFIED G-INDEX CALCULATION COMPLETE")
        print("=" * 60)
        print(f"Completed: {datetime.now()}")

    except Exception as error:
        print()
        print("=" * 60)
        print("CALCULATION FAILED")
        print("=" * 60)
        print(f"Error: {error}")

        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
