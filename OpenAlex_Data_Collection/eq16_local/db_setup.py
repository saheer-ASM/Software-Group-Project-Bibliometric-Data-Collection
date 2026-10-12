"""Creates the Equation 16 table in the LOCAL database (SQLite port of
eq16_field_hindex/db_setup.py). Same table / column names; no CHECK / FK constraints."""

from .db_connection import get_connection

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS author_field_modified_hindex (
        author_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        raw_h_value INTEGER NOT NULL DEFAULT 0,
        papers_used INTEGER NOT NULL DEFAULT 0,
        field_normalization REAL,
        modified_hindex_field REAL,
        calculation_status TEXT NOT NULL,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (author_id, field_name)
    ) WITHOUT ROWID
    """,
    "CREATE INDEX IF NOT EXISTS idx_eq16_field ON author_field_modified_hindex(field_name)",
]


def create_equation_16_table(connection=None) -> None:
    owns_connection = connection is None
    connection = connection or get_connection()
    try:
        with connection:
            for statement in STATEMENTS:
                connection.execute(statement)
        print("Created or verified table: author_field_modified_hindex")
        print("Created or verified indexes.")
    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_equation_16_table()
