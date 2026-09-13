from .db_connection import get_connection


# ---------------------------------------------------------------------------
# Equation 13 support table: TC_bar_f (field-only average, all years).
# ---------------------------------------------------------------------------

CREATE_FIELD_ADJUSTED_CITATION_AVERAGE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.field_adjusted_citation_average (
    field_name VARCHAR(255)
        PRIMARY KEY,

    publication_count INTEGER
        NOT NULL
        DEFAULT 0,

    distinct_publication_count INTEGER
        NOT NULL
        DEFAULT 0,

    sum_adjusted_citations NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    citation_avg_field NUMERIC(28, 16),

    field_weight_sum NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    weighted_sum_adjusted_citations
        NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    weighted_citation_avg_field NUMERIC(28, 16),

    data_coverage_ratio NUMERIC(18, 12)
        NOT NULL
        DEFAULT 0,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_field_avg_publication_count
        CHECK (publication_count >= 0),

    CONSTRAINT chk_field_avg_distinct_count
        CHECK (distinct_publication_count >= 0),

    CONSTRAINT chk_field_avg_sum_nonnegative
        CHECK (sum_adjusted_citations >= 0),

    CONSTRAINT chk_field_avg_coverage_ratio
        CHECK (
            data_coverage_ratio >= 0
            AND data_coverage_ratio <= 1
        )
);
"""


# ---------------------------------------------------------------------------
# Equation 12: R_{k,f}^{adj}, the field-level percentile cap threshold.
# ---------------------------------------------------------------------------

CREATE_FIELD_PERCENTILE_CAP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.field_citation_percentile_caps (
    field_name VARCHAR(255)
        NOT NULL,

    percentile_k NUMERIC(5, 2)
        NOT NULL
        DEFAULT 99.00,

    sample_size INTEGER
        NOT NULL
        DEFAULT 0,

    min_adjusted_citation NUMERIC(28, 16),

    max_adjusted_citation NUMERIC(28, 16),

    cap_threshold NUMERIC(28, 16)
        NOT NULL,

    outlier_count INTEGER
        NOT NULL
        DEFAULT 0,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        field_name,
        percentile_k
    ),

    CONSTRAINT chk_percentile_k_range
        CHECK (
            percentile_k > 0
            AND percentile_k <= 100
        ),

    CONSTRAINT chk_percentile_sample_size
        CHECK (sample_size >= 0),

    CONSTRAINT chk_percentile_cap_nonnegative
        CHECK (cap_threshold >= 0),

    CONSTRAINT chk_percentile_outlier_count
        CHECK (
            outlier_count >= 0
            AND outlier_count <= sample_size
        )
);
"""


# ---------------------------------------------------------------------------
# Equation 12 (applied) + Equation 13 detail rows: S_a per (author, pub, field)
# ---------------------------------------------------------------------------

CREATE_EQUATION_13_DETAILS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.citations_per_paper_details (
    author_id VARCHAR(100)
        NOT NULL,

    pub_id VARCHAR(100)
        NOT NULL,

    field_name VARCHAR(255)
        NOT NULL,

    adjusted_citation NUMERIC(28, 16),

    percentile_k NUMERIC(5, 2)
        NOT NULL
        DEFAULT 99.00,

    cap_threshold NUMERIC(28, 16),

    capped_adjusted_citation NUMERIC(28, 16),

    was_capped BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    author_field_weight NUMERIC(28, 16)
        NOT NULL,

    publication_count INTEGER
        NOT NULL
        DEFAULT 0,

    field_average NUMERIC(28, 16),

    normalized_citation_ratio NUMERIC(28, 16),

    paper_field_contribution NUMERIC(28, 16),

    calculation_status VARCHAR(50)
        NOT NULL,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        author_id,
        pub_id,
        field_name
    ),

    CONSTRAINT fk_eq13_detail_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_eq13_detail_publication
        FOREIGN KEY (pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq13_detail_adjusted_citation
        CHECK (
            adjusted_citation IS NULL
            OR adjusted_citation >= 0
        ),

    CONSTRAINT chk_eq13_detail_author_field_weight
        CHECK (
            author_field_weight >= 0
            AND author_field_weight <= 1
        ),

    CONSTRAINT chk_eq13_detail_publication_count
        CHECK (publication_count >= 0),

    CONSTRAINT chk_eq13_detail_field_average
        CHECK (
            field_average IS NULL
            OR field_average >= 0
        ),

    CONSTRAINT chk_eq13_detail_normalized_ratio
        CHECK (
            normalized_citation_ratio IS NULL
            OR normalized_citation_ratio >= 0
        ),

    CONSTRAINT chk_eq13_detail_contribution
        CHECK (
            paper_field_contribution IS NULL
            OR paper_field_contribution >= 0
        ),

    CONSTRAINT chk_eq13_detail_capped_le_adjusted
        CHECK (
            capped_adjusted_citation IS NULL
            OR adjusted_citation IS NULL
            OR capped_adjusted_citation <= adjusted_citation
        )
);
"""


CREATE_AUTHOR_CITATIONS_PER_PAPER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.author_citations_per_paper (
    author_id VARCHAR(100)
        PRIMARY KEY,

    career_factor NUMERIC(18, 12)
        NOT NULL,

    publication_count INTEGER
        NOT NULL
        DEFAULT 0,

    field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    included_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    provisional_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    skipped_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    normalized_contribution_sum NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    citations_per_paper_score NUMERIC(28, 16),

    calculation_complete BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_eq13_score_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq13_score_publication_count
        CHECK (publication_count >= 0),

    CONSTRAINT chk_eq13_score_row_counts
        CHECK (
            included_field_row_count
                + skipped_field_row_count
                <= field_row_count
        ),

    CONSTRAINT chk_eq13_score_contribution_sum
        CHECK (normalized_contribution_sum >= 0),

    CONSTRAINT chk_eq13_score_nonnegative
        CHECK (
            citations_per_paper_score IS NULL
            OR citations_per_paper_score >= 0
        )
);
"""


# ---------------------------------------------------------------------------
# Equation 12 (applied) + Equation 14 detail rows: U_a per (author, pub, field)
# ---------------------------------------------------------------------------

CREATE_EQUATION_14_DETAILS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.citation_rate_details (
    author_id VARCHAR(100)
        NOT NULL,

    pub_id VARCHAR(100)
        NOT NULL,

    field_name VARCHAR(255)
        NOT NULL,

    publication_year INTEGER
        NOT NULL,

    adjusted_citation NUMERIC(28, 16),

    percentile_k NUMERIC(5, 2)
        NOT NULL
        DEFAULT 99.00,

    cap_threshold NUMERIC(28, 16),

    capped_adjusted_citation NUMERIC(28, 16),

    was_capped BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    author_field_weight NUMERIC(28, 16)
        NOT NULL,

    years_elapsed INTEGER
        NOT NULL,

    field_year_average NUMERIC(28, 16),

    normalized_citation_ratio NUMERIC(28, 16),

    paper_field_contribution NUMERIC(28, 16),

    calculation_status VARCHAR(50)
        NOT NULL,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        author_id,
        pub_id,
        field_name
    ),

    CONSTRAINT fk_eq14_detail_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_eq14_detail_publication
        FOREIGN KEY (pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq14_detail_adjusted_citation
        CHECK (
            adjusted_citation IS NULL
            OR adjusted_citation >= 0
        ),

    CONSTRAINT chk_eq14_detail_author_field_weight
        CHECK (
            author_field_weight >= 0
            AND author_field_weight <= 1
        ),

    CONSTRAINT chk_eq14_detail_years_elapsed
        CHECK (years_elapsed >= 1),

    CONSTRAINT chk_eq14_detail_field_year_average
        CHECK (
            field_year_average IS NULL
            OR field_year_average >= 0
        ),

    CONSTRAINT chk_eq14_detail_normalized_ratio
        CHECK (
            normalized_citation_ratio IS NULL
            OR normalized_citation_ratio >= 0
        ),

    CONSTRAINT chk_eq14_detail_contribution
        CHECK (
            paper_field_contribution IS NULL
            OR paper_field_contribution >= 0
        ),

    CONSTRAINT chk_eq14_detail_capped_le_adjusted
        CHECK (
            capped_adjusted_citation IS NULL
            OR adjusted_citation IS NULL
            OR capped_adjusted_citation <= adjusted_citation
        )
);
"""


CREATE_AUTHOR_CITATION_RATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.author_citation_rate (
    author_id VARCHAR(100)
        PRIMARY KEY,

    career_factor NUMERIC(18, 12)
        NOT NULL,

    as_of_year INTEGER
        NOT NULL,

    field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    included_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    provisional_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    skipped_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    normalized_contribution_sum NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    citation_rate_score NUMERIC(28, 16),

    calculation_complete BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_eq14_score_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq14_score_row_counts
        CHECK (
            included_field_row_count
                + skipped_field_row_count
                <= field_row_count
        ),

    CONSTRAINT chk_eq14_score_contribution_sum
        CHECK (normalized_contribution_sum >= 0),

    CONSTRAINT chk_eq14_score_nonnegative
        CHECK (
            citation_rate_score IS NULL
            OR citation_rate_score >= 0
        )
);
"""


CREATE_VIEWS_SQL = """
CREATE OR REPLACE VIEW
public.equation_13_citations_per_paper AS
SELECT
    author_id,
    career_factor,
    publication_count,
    field_row_count,
    included_field_row_count,
    provisional_field_row_count,
    skipped_field_row_count,
    normalized_contribution_sum,
    citations_per_paper_score,
    calculation_complete,
    calculated_at
FROM public.author_citations_per_paper;


CREATE OR REPLACE VIEW
public.equation_14_citation_rate AS
SELECT
    author_id,
    career_factor,
    as_of_year,
    field_row_count,
    included_field_row_count,
    provisional_field_row_count,
    skipped_field_row_count,
    normalized_contribution_sum,
    citation_rate_score,
    calculation_complete,
    calculated_at
FROM public.author_citation_rate;
"""


CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS
idx_field_percentile_caps_field
ON public.field_citation_percentile_caps(field_name);

CREATE INDEX IF NOT EXISTS
idx_eq13_details_author
ON public.citations_per_paper_details(author_id);

CREATE INDEX IF NOT EXISTS
idx_eq13_details_publication
ON public.citations_per_paper_details(pub_id);

CREATE INDEX IF NOT EXISTS
idx_eq13_details_field
ON public.citations_per_paper_details(field_name);

CREATE INDEX IF NOT EXISTS
idx_eq13_details_status
ON public.citations_per_paper_details(calculation_status);

CREATE INDEX IF NOT EXISTS
idx_eq14_details_author
ON public.citation_rate_details(author_id);

CREATE INDEX IF NOT EXISTS
idx_eq14_details_publication
ON public.citation_rate_details(pub_id);

CREATE INDEX IF NOT EXISTS
idx_eq14_details_field_year
ON public.citation_rate_details(field_name, publication_year);

CREATE INDEX IF NOT EXISTS
idx_eq14_details_status
ON public.citation_rate_details(calculation_status);
"""


TABLE_STATEMENTS = [
    ("public.field_adjusted_citation_average", CREATE_FIELD_ADJUSTED_CITATION_AVERAGE_TABLE_SQL),
    ("public.field_citation_percentile_caps", CREATE_FIELD_PERCENTILE_CAP_TABLE_SQL),
    ("public.citations_per_paper_details", CREATE_EQUATION_13_DETAILS_TABLE_SQL),
    ("public.author_citations_per_paper", CREATE_AUTHOR_CITATIONS_PER_PAPER_TABLE_SQL),
    ("public.citation_rate_details", CREATE_EQUATION_14_DETAILS_TABLE_SQL),
    ("public.author_citation_rate", CREATE_AUTHOR_CITATION_RATE_TABLE_SQL),
]


def create_equation_12_13_14_tables(connection=None) -> None:
    """
    Create every table, index, and view needed for Equations 12, 13,
    and 14. Safe to run repeatedly (uses IF NOT EXISTS / OR REPLACE
    throughout).
    """

    owns_connection = connection is None
    connection = connection or get_connection()

    try:
        with connection.cursor() as cursor:
            for table_name, statement in TABLE_STATEMENTS:
                cursor.execute(statement)
                print(f"Created or verified table: {table_name}")

            cursor.execute(CREATE_INDEXES_SQL)
            print("Created or verified indexes.")

            cursor.execute(CREATE_VIEWS_SQL)
            print("Created or replaced views: "
                  "public.equation_13_citations_per_paper, "
                  "public.equation_14_citation_rate")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_equation_12_13_14_tables()
