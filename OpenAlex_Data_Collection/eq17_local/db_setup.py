"""Creates the Equation 17 table in the LOCAL database (SQLite port of
eq17_modified_hindex/db_setup.py). Same table / column names; no CHECK / FK constraints."""

from .db_connection import get_connection

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS author_modified_hindex (
        author_id TEXT PRIMARY KEY,
        weighted_numerator_sum REAL NOT NULL DEFAULT 0,
        total_field_weight_sum REAL NOT NULL DEFAULT 0,
        modified_hindex_final REAL,
        field_count INTEGER NOT NULL DEFAULT 0,
        calculation_status TEXT NOT NULL,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


def create_equation_17_table(connection=None) -> None:
    owns_connection = connection is None
    connection = connection or get_connection()
    try:
        with connection:
            for statement in STATEMENTS:
                connection.execute(statement)
        print("Created or verified table: author_modified_hindex")
    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_equation_17_table()
