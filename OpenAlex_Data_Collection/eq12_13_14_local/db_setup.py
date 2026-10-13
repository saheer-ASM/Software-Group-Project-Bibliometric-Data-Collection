"""Creates the Equation 12 / 13 / 14 tables in the LOCAL database (SQLite port of
Equations_12_13_14/db_setup.py). Same table, column and view names as the cloud
script; CHECK / FOREIGN KEY constraints are omitted (plain SQLite floats)."""

from .db_connection import get_connection

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS field_adjusted_citation_average (
        field_name TEXT PRIMARY KEY,
        publication_count INTEGER NOT NULL DEFAULT 0,
        distinct_publication_count INTEGER NOT NULL DEFAULT 0,
        sum_adjusted_citations REAL NOT NULL DEFAULT 0,
        citation_avg_field REAL,
        field_weight_sum REAL NOT NULL DEFAULT 0,
        weighted_sum_adjusted_citations REAL NOT NULL DEFAULT 0,
        weighted_citation_avg_field REAL,
        data_coverage_ratio REAL NOT NULL DEFAULT 0,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS field_citation_percentile_caps (
        field_name TEXT NOT NULL,
        percentile_k REAL NOT NULL,
        sample_size INTEGER NOT NULL,
        min_adjusted_citation REAL NOT NULL,
        max_adjusted_citation REAL NOT NULL,
        cap_threshold REAL NOT NULL,
        outlier_count INTEGER NOT NULL DEFAULT 0,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (field_name, percentile_k)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE IF NOT EXISTS citations_per_paper_details (
        author_id TEXT NOT NULL,
        pub_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        adjusted_citation REAL,
        percentile_k REAL NOT NULL,
        cap_threshold REAL,
        capped_adjusted_citation REAL,
        was_capped INTEGER NOT NULL DEFAULT 0,
        author_field_weight REAL NOT NULL,
        publication_count INTEGER NOT NULL,
        field_average REAL,
        normalized_citation_ratio REAL,
        paper_field_contribution REAL,
        calculation_status TEXT NOT NULL,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (author_id, pub_id, field_name)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE IF NOT EXISTS author_citations_per_paper (
        author_id TEXT PRIMARY KEY,
        career_factor REAL,
        publication_count INTEGER NOT NULL DEFAULT 0,
        field_row_count INTEGER NOT NULL DEFAULT 0,
        included_field_row_count INTEGER NOT NULL DEFAULT 0,
        provisional_field_row_count INTEGER NOT NULL DEFAULT 0,
        skipped_field_row_count INTEGER NOT NULL DEFAULT 0,
        normalized_contribution_sum REAL NOT NULL DEFAULT 0,
        citations_per_paper_score REAL,
        calculation_complete INTEGER NOT NULL DEFAULT 0,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS citation_rate_details (
        author_id TEXT NOT NULL,
        pub_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        publication_year INTEGER NOT NULL,
        adjusted_citation REAL,
        percentile_k REAL NOT NULL,
        cap_threshold REAL,
        capped_adjusted_citation REAL,
        was_capped INTEGER NOT NULL DEFAULT 0,
        author_field_weight REAL NOT NULL,
        years_elapsed INTEGER NOT NULL,
        field_year_average REAL,
        normalized_citation_ratio REAL,
        paper_field_contribution REAL,
        calculation_status TEXT NOT NULL,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (author_id, pub_id, field_name)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE IF NOT EXISTS author_citation_rate (
        author_id TEXT PRIMARY KEY,
        career_factor REAL,
        as_of_year INTEGER NOT NULL,
        field_row_count INTEGER NOT NULL DEFAULT 0,
        included_field_row_count INTEGER NOT NULL DEFAULT 0,
        provisional_field_row_count INTEGER NOT NULL DEFAULT 0,
        skipped_field_row_count INTEGER NOT NULL DEFAULT 0,
        normalized_contribution_sum REAL NOT NULL DEFAULT 0,
        citation_rate_score REAL,
        calculation_complete INTEGER NOT NULL DEFAULT 0,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE VIEW IF NOT EXISTS equation_13_citations_per_paper AS
    SELECT author_id, career_factor, publication_count, field_row_count,
           included_field_row_count, provisional_field_row_count,
           skipped_field_row_count, normalized_contribution_sum,
           citations_per_paper_score, calculation_complete, calculated_at
    FROM author_citations_per_paper
    """,
    """
    CREATE VIEW IF NOT EXISTS equation_14_citation_rate AS
    SELECT author_id, career_factor, as_of_year, field_row_count,
           included_field_row_count, provisional_field_row_count,
           skipped_field_row_count, normalized_contribution_sum,
           citation_rate_score, calculation_complete, calculated_at
    FROM author_citation_rate
    """,
    "CREATE INDEX IF NOT EXISTS idx_eq13_details_publication ON citations_per_paper_details(pub_id)",
    "CREATE INDEX IF NOT EXISTS idx_eq13_details_field ON citations_per_paper_details(field_name)",
    "CREATE INDEX IF NOT EXISTS idx_eq13_details_status ON citations_per_paper_details(calculation_status)",
    "CREATE INDEX IF NOT EXISTS idx_eq14_details_publication ON citation_rate_details(pub_id)",
    "CREATE INDEX IF NOT EXISTS idx_eq14_details_field_year ON citation_rate_details(field_name, publication_year)",
    "CREATE INDEX IF NOT EXISTS idx_eq14_details_status ON citation_rate_details(calculation_status)",
]


def create_equation_12_13_14_tables(connection) -> None:
    with connection:
        for statement in STATEMENTS:
            connection.execute(statement)


if __name__ == "__main__":
    conn = get_connection()
    try:
        create_equation_12_13_14_tables(conn)
        print("Created or verified Equation 12 / 13 / 14 tables and views.")
    finally:
        conn.close()
