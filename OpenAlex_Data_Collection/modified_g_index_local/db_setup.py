"""Creates the Modified g-index tables in the LOCAL database (SQLite port of
Modified_G_Index/db_setup.py). Same table, column and index names as the cloud
script; CHECK / FOREIGN KEY constraints are omitted (plain SQLite floats).

As in the cloud pipeline, only modified_g_index_results is populated by
run_calculation; the other three tables are created for schema parity."""

from .db_connection import get_connection

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS g_index_field_reference (
        field_name TEXT PRIMARY KEY,
        normalization_method TEXT NOT NULL DEFAULT 'PENDING',
        g_field_reference REAL,
        sample_size INTEGER,
        notes TEXT,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS modified_g_index_paper_details (
        author_id TEXT NOT NULL,
        pub_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        publication_year INTEGER,
        career_factor REAL,
        author_field_weight REAL,
        adjusted_citation REAL,
        cap_threshold REAL,
        capped_adjusted_citation REAL,
        was_capped INTEGER,
        effective_citation REAL,
        field_rank INTEGER,
        cumulative_effective_citation REAL,
        satisfies_g_condition INTEGER,
        calculation_status TEXT,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (author_id, pub_id, field_name)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE IF NOT EXISTS modified_g_index_field_results (
        author_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        paper_count INTEGER,
        included_paper_count INTEGER,
        g_field_raw INTEGER,
        g_field_reference REAL,
        g_field_normalized REAL,
        field_weight_sum REAL,
        calculation_status TEXT,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (author_id, field_name)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE IF NOT EXISTS modified_g_index_results (
        author_id TEXT PRIMARY KEY,
        field_row_count INTEGER NOT NULL DEFAULT 0,
        included_field_row_count INTEGER NOT NULL DEFAULT 0,
        skipped_field_row_count INTEGER NOT NULL DEFAULT 0,
        field_weight_total REAL NOT NULL DEFAULT 0,
        weighted_g_sum REAL NOT NULL DEFAULT 0,
        modified_g_index REAL,
        calculation_complete INTEGER NOT NULL DEFAULT 0,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_gidx_paper_details_publication "
    "ON modified_g_index_paper_details(pub_id)",
    "CREATE INDEX IF NOT EXISTS idx_gidx_paper_details_author_field_rank "
    "ON modified_g_index_paper_details(author_id, field_name, field_rank)",
    "CREATE INDEX IF NOT EXISTS idx_gidx_paper_details_status "
    "ON modified_g_index_paper_details(calculation_status)",
    "CREATE INDEX IF NOT EXISTS idx_gidx_field_results_status "
    "ON modified_g_index_field_results(calculation_status)",
]

TABLE_NAMES = [
    "g_index_field_reference",
    "modified_g_index_paper_details",
    "modified_g_index_field_results",
    "modified_g_index_results",
]


def create_modified_g_index_tables(connection=None) -> None:
    """Create every table and index needed for the Modified g index
    (Section 2.10, Equations 20-22). Safe to run repeatedly."""
    owns_connection = connection is None
    connection = connection or get_connection()
    try:
        with connection:
            for statement in STATEMENTS:
                connection.execute(statement)
        for name in TABLE_NAMES:
            print(f"Created or verified table: {name}")
        print("Created or verified indexes.")
    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_modified_g_index_tables()
