"""Creates the Equation 11 tables in the LOCAL database (SQLite port of
Calculating_Total_Cites/db_setup.py). Same table, column and view names as the cloud
script; CHECK / FOREIGN KEY constraints are omitted (SQLite stores plain floats, so
a weight such as 1.0000000000000002 would otherwise be rejected)."""

from .db_connection import get_connection

CREATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS field_year_adjusted_citation_average (
        field_name TEXT NOT NULL,
        publication_year INTEGER NOT NULL,
        publication_count INTEGER NOT NULL DEFAULT 0,
        complete_publication_count INTEGER NOT NULL DEFAULT 0,
        incomplete_publication_count INTEGER NOT NULL DEFAULT 0,
        zero_citation_publication_count INTEGER NOT NULL DEFAULT 0,
        sum_adjusted_citations REAL NOT NULL DEFAULT 0,
        citation_avg_field_and_year REAL,
        field_weight_sum REAL NOT NULL DEFAULT 0,
        weighted_sum_adjusted_citations REAL NOT NULL DEFAULT 0,
        weighted_citation_avg_field_and_year REAL,
        data_coverage_ratio REAL NOT NULL DEFAULT 0,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (field_name, publication_year)
    ) WITHOUT ROWID
    """,
    "CREATE INDEX IF NOT EXISTS idx_fy_adjusted_average_field "
    "ON field_year_adjusted_citation_average(field_name)",
    "CREATE INDEX IF NOT EXISTS idx_fy_adjusted_average_year "
    "ON field_year_adjusted_citation_average(publication_year)",
    """
    CREATE TABLE IF NOT EXISTS total_cites_equation_11_details (
        author_id TEXT NOT NULL,
        pub_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        publication_year INTEGER NOT NULL,
        author_overall_weight REAL NOT NULL,
        field_weight REAL NOT NULL,
        author_field_weight REAL NOT NULL,
        adjusted_citation REAL,
        field_year_average REAL,
        benchmark_coverage_ratio REAL,
        normalized_citation_ratio REAL,
        paper_field_contribution REAL,
        expected_citing_pair_count INTEGER NOT NULL DEFAULT 0,
        processed_citing_pair_count INTEGER NOT NULL DEFAULT 0,
        calculation_status TEXT NOT NULL,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (author_id, pub_id, field_name)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE IF NOT EXISTS author_total_cites (
        author_id TEXT PRIMARY KEY,
        first_publication_year INTEGER NOT NULL,
        as_of_year INTEGER NOT NULL,
        career_time_years INTEGER NOT NULL,
        career_boost_c REAL NOT NULL,
        career_decay_lambda REAL NOT NULL,
        career_factor REAL NOT NULL,
        publication_count INTEGER NOT NULL DEFAULT 0,
        included_publication_count INTEGER NOT NULL DEFAULT 0,
        field_row_count INTEGER NOT NULL DEFAULT 0,
        included_field_row_count INTEGER NOT NULL DEFAULT 0,
        skipped_field_row_count INTEGER NOT NULL DEFAULT 0,
        provisional_field_row_count INTEGER NOT NULL DEFAULT 0,
        normalized_contribution_sum REAL NOT NULL DEFAULT 0,
        total_cites_score REAL,
        calculation_complete INTEGER NOT NULL DEFAULT 0,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE VIEW IF NOT EXISTS equation_11_total_cites AS
    SELECT author_id, first_publication_year, as_of_year, career_time_years,
           career_boost_c, career_decay_lambda, career_factor, publication_count,
           included_publication_count, field_row_count, included_field_row_count,
           skipped_field_row_count, provisional_field_row_count,
           normalized_contribution_sum, total_cites_score, calculation_complete,
           calculated_at
    FROM author_total_cites
    """,
    "CREATE INDEX IF NOT EXISTS idx_eq11_details_publication "
    "ON total_cites_equation_11_details(pub_id)",
    "CREATE INDEX IF NOT EXISTS idx_eq11_details_field_year "
    "ON total_cites_equation_11_details(field_name, publication_year)",
    "CREATE INDEX IF NOT EXISTS idx_eq11_details_status "
    "ON total_cites_equation_11_details(calculation_status)",
]


def create_tables() -> None:
    connection = get_connection()
    try:
        with connection:
            for statement in CREATE_STATEMENTS:
                connection.execute(statement)
        print("Created or verified Total Cites tables and view.")
        print("- field_year_adjusted_citation_average")
        print("- total_cites_equation_11_details")
        print("- author_total_cites")
        print("- equation_11_total_cites")
    finally:
        connection.close()


if __name__ == "__main__":
    create_tables()
