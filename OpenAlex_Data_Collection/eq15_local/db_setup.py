"""Creates the Equation 15 table in the LOCAL database (SQLite port of
modified_hf_index/db_setup.py). Same table and column names; CHECK / FOREIGN KEY
constraints are omitted (plain SQLite floats)."""

from .db_connection import get_connection

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS author_paper_field_effective_citation (
        author_id TEXT NOT NULL,
        pub_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        career_factor REAL,
        author_field_weight REAL,
        capped_adjusted_citation REAL,
        effective_citation REAL,
        calculation_status TEXT NOT NULL,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (author_id, pub_id, field_name)
    ) WITHOUT ROWID
    """,
    "CREATE INDEX IF NOT EXISTS idx_eq15_publication "
    "ON author_paper_field_effective_citation(pub_id)",
    "CREATE INDEX IF NOT EXISTS idx_eq15_field ON author_paper_field_effective_citation(field_name)",
    "CREATE INDEX IF NOT EXISTS idx_eq15_status "
    "ON author_paper_field_effective_citation(calculation_status)",
]


def create_equation_15_table(connection=None) -> None:
    owns_connection = connection is None
    connection = connection or get_connection()
    try:
        with connection:
            for statement in STATEMENTS:
                connection.execute(statement)
        print("Created or verified table: author_paper_field_effective_citation")
        print("Created or verified indexes.")
    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_equation_15_table()
