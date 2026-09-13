from Calculating_ISC.db_connection import get_connection

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.field_year_adjusted_citation_average (
    field_name VARCHAR(255) NOT NULL,
    publication_year INTEGER NOT NULL,

    -- All publications with a valid field and year in this group.
    publication_count INTEGER NOT NULL DEFAULT 0,

    -- Publications whose citation pairs were fully processed by ISC.
    complete_publication_count INTEGER NOT NULL DEFAULT 0,
    incomplete_publication_count INTEGER NOT NULL DEFAULT 0,

    -- Complete publications that currently have no incoming citations.
    zero_citation_publication_count INTEGER NOT NULL DEFAULT 0,

    -- Sum and simple average used for the literal paper definition.
    sum_adjusted_citations NUMERIC(32, 16) NOT NULL DEFAULT 0,
    citation_avg_field_and_year NUMERIC(32, 16),

    -- Optional multi-field-weighted benchmark.
    field_weight_sum NUMERIC(32, 16) NOT NULL DEFAULT 0,
    weighted_sum_adjusted_citations NUMERIC(32, 16) NOT NULL DEFAULT 0,
    weighted_citation_avg_field_and_year NUMERIC(32, 16),

    -- complete_publication_count / publication_count
    data_coverage_ratio NUMERIC(18, 12) NOT NULL DEFAULT 0,

    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (field_name, publication_year),

    CONSTRAINT chk_fy_publication_count
        CHECK (publication_count >= 0),

    CONSTRAINT chk_fy_complete_count
        CHECK (complete_publication_count >= 0),

    CONSTRAINT chk_fy_incomplete_count
        CHECK (incomplete_publication_count >= 0),

    CONSTRAINT chk_fy_zero_count
        CHECK (zero_citation_publication_count >= 0),

    CONSTRAINT chk_fy_sum_adjusted
        CHECK (sum_adjusted_citations >= 0),

    CONSTRAINT chk_fy_average
        CHECK (
            citation_avg_field_and_year IS NULL
            OR citation_avg_field_and_year >= 0
        ),

    CONSTRAINT chk_fy_weighted_average
        CHECK (
            weighted_citation_avg_field_and_year IS NULL
            OR weighted_citation_avg_field_and_year >= 0
        ),

    CONSTRAINT chk_fy_coverage
        CHECK (
            data_coverage_ratio >= 0
            AND data_coverage_ratio <= 1
        )
);
"""


CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_fy_adjusted_average_field
    ON public.field_year_adjusted_citation_average(field_name);

CREATE INDEX IF NOT EXISTS idx_fy_adjusted_average_year
    ON public.field_year_adjusted_citation_average(publication_year);
"""

CREATE_EQUATION_11_DETAILS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.total_cites_equation_11_details (
    author_id VARCHAR(100) NOT NULL,
    pub_id VARCHAR(100) NOT NULL,
    field_name VARCHAR(255) NOT NULL,
    publication_year INTEGER NOT NULL,

    author_overall_weight NUMERIC(28, 16) NOT NULL,
    field_weight NUMERIC(28, 16) NOT NULL,
    author_field_weight NUMERIC(28, 16) NOT NULL,

    adjusted_citation NUMERIC(32, 16),
    field_year_average NUMERIC(32, 16),
    benchmark_coverage_ratio NUMERIC(18, 12),
    normalized_citation_ratio NUMERIC(32, 16),
    paper_field_contribution NUMERIC(32, 16),

    expected_citing_pair_count INTEGER NOT NULL DEFAULT 0,
    processed_citing_pair_count INTEGER NOT NULL DEFAULT 0,
    calculation_status VARCHAR(64) NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (author_id, pub_id, field_name),

    CONSTRAINT fk_eq11_detail_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_eq11_detail_publication
        FOREIGN KEY (pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq11_detail_author_weight
        CHECK (author_overall_weight >= 0 AND author_overall_weight <= 1),

    CONSTRAINT chk_eq11_detail_field_weight
        CHECK (field_weight > 0 AND field_weight <= 1),

    CONSTRAINT chk_eq11_detail_author_field_weight
        CHECK (author_field_weight >= 0 AND author_field_weight <= 1),

    CONSTRAINT chk_eq11_detail_adjusted_citation
        CHECK (adjusted_citation IS NULL OR adjusted_citation >= 0),

    CONSTRAINT chk_eq11_detail_field_year_average
        CHECK (field_year_average IS NULL OR field_year_average >= 0),

    CONSTRAINT chk_eq11_detail_coverage
        CHECK (
            benchmark_coverage_ratio IS NULL
            OR (
                benchmark_coverage_ratio >= 0
                AND benchmark_coverage_ratio <= 1
            )
        ),

    CONSTRAINT chk_eq11_detail_normalized_ratio
        CHECK (
            normalized_citation_ratio IS NULL
            OR normalized_citation_ratio >= 0
        ),

    CONSTRAINT chk_eq11_detail_contribution
        CHECK (
            paper_field_contribution IS NULL
            OR paper_field_contribution >= 0
        ),

    CONSTRAINT chk_eq11_detail_expected_pairs
        CHECK (expected_citing_pair_count >= 0),

    CONSTRAINT chk_eq11_detail_processed_pairs
        CHECK (processed_citing_pair_count >= 0)
);
"""


CREATE_AUTHOR_TOTAL_CITES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.author_total_cites (
    author_id VARCHAR(100) PRIMARY KEY,

    first_publication_year INTEGER NOT NULL,
    as_of_year INTEGER NOT NULL,
    career_time_years INTEGER NOT NULL,

    career_boost_c NUMERIC(18, 12) NOT NULL,
    career_decay_lambda NUMERIC(18, 12) NOT NULL,
    career_factor NUMERIC(28, 16) NOT NULL,

    publication_count INTEGER NOT NULL DEFAULT 0,
    included_publication_count INTEGER NOT NULL DEFAULT 0,

    field_row_count INTEGER NOT NULL DEFAULT 0,
    included_field_row_count INTEGER NOT NULL DEFAULT 0,
    skipped_field_row_count INTEGER NOT NULL DEFAULT 0,
    provisional_field_row_count INTEGER NOT NULL DEFAULT 0,

    normalized_contribution_sum NUMERIC(32, 16) NOT NULL DEFAULT 0,
    total_cites_score NUMERIC(32, 16),
    calculation_complete BOOLEAN NOT NULL DEFAULT FALSE,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_author_total_cites_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_author_total_cites_years
        CHECK (
            first_publication_year >= 0
            AND as_of_year >= first_publication_year
            AND career_time_years >= 0
        ),

    CONSTRAINT chk_author_total_cites_c
        CHECK (career_boost_c >= 1),

    CONSTRAINT chk_author_total_cites_lambda
        CHECK (career_decay_lambda >= 0 AND career_decay_lambda <= 1),

    CONSTRAINT chk_author_total_cites_factor
        CHECK (career_factor >= 0),

    CONSTRAINT chk_author_total_cites_counts
        CHECK (
            publication_count >= 0
            AND included_publication_count >= 0
            AND field_row_count >= 0
            AND included_field_row_count >= 0
            AND skipped_field_row_count >= 0
            AND provisional_field_row_count >= 0
        ),

    CONSTRAINT chk_author_total_cites_sum
        CHECK (normalized_contribution_sum >= 0),

    CONSTRAINT chk_author_total_cites_score
        CHECK (total_cites_score IS NULL OR total_cites_score >= 0)
);
"""


CREATE_VIEW_AND_INDEXES_SQL = """
CREATE OR REPLACE VIEW public.equation_11_total_cites AS
SELECT
    author_id,
    first_publication_year,
    as_of_year,
    career_time_years,
    career_boost_c,
    career_decay_lambda,
    career_factor,
    publication_count,
    included_publication_count,
    field_row_count,
    included_field_row_count,
    skipped_field_row_count,
    provisional_field_row_count,
    normalized_contribution_sum,
    total_cites_score,
    calculation_complete,
    calculated_at
FROM public.author_total_cites;

CREATE INDEX IF NOT EXISTS idx_eq11_details_author
    ON public.total_cites_equation_11_details(author_id);

CREATE INDEX IF NOT EXISTS idx_eq11_details_publication
    ON public.total_cites_equation_11_details(pub_id);

CREATE INDEX IF NOT EXISTS idx_eq11_details_field_year
    ON public.total_cites_equation_11_details(field_name, publication_year);

CREATE INDEX IF NOT EXISTS idx_eq11_details_status
    ON public.total_cites_equation_11_details(calculation_status);
"""


def create_tables() -> None:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(CREATE_INDEXES_SQL)
            cursor.execute(CREATE_EQUATION_11_DETAILS_TABLE_SQL)
            cursor.execute(CREATE_AUTHOR_TOTAL_CITES_TABLE_SQL)
            cursor.execute(CREATE_VIEW_AND_INDEXES_SQL)

        connection.commit()
        print("Created or verified Total Cites tables and view.")
        print("- public.field_year_adjusted_citation_average")
        print("- public.total_cites_equation_11_details")
        print("- public.author_total_cites")
        print("- public.equation_11_total_cites")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_tables()