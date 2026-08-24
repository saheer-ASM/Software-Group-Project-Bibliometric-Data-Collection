from .db_connection import get_connection


# ---------------------------------------------------------------------------
# G'f : field normalization constant, the divisor in Equation 21.
#
# Not derivable from any existing table (see Modified_g_index_sheet.md) --
# this is a placeholder reference table so the value can be decided and
# populated later without a schema change.
# ---------------------------------------------------------------------------

CREATE_G_INDEX_FIELD_REFERENCE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.g_index_field_reference (
    field_name VARCHAR(255)
        PRIMARY KEY,

    normalization_method VARCHAR(50)
        NOT NULL
        DEFAULT 'PENDING',

    g_field_reference NUMERIC(28, 16),

    sample_size INTEGER
        NOT NULL
        DEFAULT 0,

    notes TEXT,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_g_field_reference_sample_size
        CHECK (sample_size >= 0),

    CONSTRAINT chk_g_field_reference_nonnegative
        CHECK (
            g_field_reference IS NULL
            OR g_field_reference > 0
        )
);
"""


# ---------------------------------------------------------------------------
# Per (author, publication, field) row: TCeff inputs/value, sort rank
# within the (author, field) group, running cumulative sum (Eq 20), and
# whether that rank satisfies Aeff(k) >= k^2.
# ---------------------------------------------------------------------------

CREATE_MODIFIED_G_INDEX_PAPER_DETAILS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.modified_g_index_paper_details (
    author_id VARCHAR(100)
        NOT NULL,

    pub_id VARCHAR(100)
        NOT NULL,

    field_name VARCHAR(255)
        NOT NULL,

    publication_year INTEGER,

    career_factor NUMERIC(18, 12)
        NOT NULL,

    author_field_weight NUMERIC(28, 16)
        NOT NULL,

    adjusted_citation NUMERIC(28, 16),

    cap_threshold NUMERIC(28, 16),

    capped_adjusted_citation NUMERIC(28, 16),

    was_capped BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    effective_citation NUMERIC(28, 16),

    field_rank INTEGER,

    cumulative_effective_citation NUMERIC(28, 16),

    satisfies_g_condition BOOLEAN,

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

    CONSTRAINT fk_gidx_paper_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_gidx_paper_publication
        FOREIGN KEY (pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_gidx_paper_adjusted_citation
        CHECK (
            adjusted_citation IS NULL
            OR adjusted_citation >= 0
        ),

    CONSTRAINT chk_gidx_paper_author_field_weight
        CHECK (
            author_field_weight >= 0
            AND author_field_weight <= 1
        ),

    CONSTRAINT chk_gidx_paper_capped_le_adjusted
        CHECK (
            capped_adjusted_citation IS NULL
            OR adjusted_citation IS NULL
            OR capped_adjusted_citation <= adjusted_citation
        ),

    CONSTRAINT chk_gidx_paper_effective_nonnegative
        CHECK (
            effective_citation IS NULL
            OR effective_citation >= 0
        ),

    CONSTRAINT chk_gidx_paper_rank_positive
        CHECK (
            field_rank IS NULL
            OR field_rank >= 1
        )
);
"""


# ---------------------------------------------------------------------------
# Per (author, field) row: the field-level g-index (Equation 21).
# ---------------------------------------------------------------------------

CREATE_MODIFIED_G_INDEX_FIELD_RESULTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.modified_g_index_field_results (
    author_id VARCHAR(100)
        NOT NULL,

    field_name VARCHAR(255)
        NOT NULL,

    paper_count INTEGER
        NOT NULL
        DEFAULT 0,

    included_paper_count INTEGER
        NOT NULL
        DEFAULT 0,

    g_field_raw INTEGER,

    g_field_reference NUMERIC(28, 16),

    g_field_normalized NUMERIC(28, 16),

    field_weight_sum NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    calculation_status VARCHAR(50)
        NOT NULL,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        author_id,
        field_name
    ),

    CONSTRAINT fk_gidx_field_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_gidx_field_paper_count
        CHECK (paper_count >= 0),

    CONSTRAINT chk_gidx_field_included_le_total
        CHECK (included_paper_count <= paper_count),

    CONSTRAINT chk_gidx_field_g_raw_nonnegative
        CHECK (
            g_field_raw IS NULL
            OR g_field_raw >= 0
        ),

    CONSTRAINT chk_gidx_field_reference_positive
        CHECK (
            g_field_reference IS NULL
            OR g_field_reference > 0
        ),

    CONSTRAINT chk_gidx_field_normalized_nonnegative
        CHECK (
            g_field_normalized IS NULL
            OR g_field_normalized >= 0
        ),

    CONSTRAINT chk_gidx_field_weight_sum_nonnegative
        CHECK (field_weight_sum >= 0)
);
"""


# ---------------------------------------------------------------------------
# Final per-author result: G'a (Equation 22).
# ---------------------------------------------------------------------------

CREATE_MODIFIED_G_INDEX_RESULTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.modified_g_index_results (
    author_id VARCHAR(100)
        PRIMARY KEY,

    field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    included_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    skipped_field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    field_weight_total NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    weighted_g_sum NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    modified_g_index NUMERIC(28, 16),

    calculation_complete BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_gidx_result_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_gidx_result_row_counts
        CHECK (
            included_field_row_count
                + skipped_field_row_count
                <= field_row_count
        ),

    CONSTRAINT chk_gidx_result_weight_total_nonnegative
        CHECK (field_weight_total >= 0),

    CONSTRAINT chk_gidx_result_weighted_sum_nonnegative
        CHECK (weighted_g_sum >= 0),

    CONSTRAINT chk_gidx_result_index_nonnegative
        CHECK (
            modified_g_index IS NULL
            OR modified_g_index >= 0
        )
);
"""


CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS
idx_gidx_paper_details_author
ON public.modified_g_index_paper_details(author_id);

CREATE INDEX IF NOT EXISTS
idx_gidx_paper_details_publication
ON public.modified_g_index_paper_details(pub_id);

CREATE INDEX IF NOT EXISTS
idx_gidx_paper_details_author_field_rank
ON public.modified_g_index_paper_details(author_id, field_name, field_rank);

CREATE INDEX IF NOT EXISTS
idx_gidx_paper_details_status
ON public.modified_g_index_paper_details(calculation_status);

CREATE INDEX IF NOT EXISTS
idx_gidx_field_results_status
ON public.modified_g_index_field_results(calculation_status);
"""


TABLE_STATEMENTS = [
    ("public.g_index_field_reference", CREATE_G_INDEX_FIELD_REFERENCE_TABLE_SQL),
    ("public.modified_g_index_paper_details", CREATE_MODIFIED_G_INDEX_PAPER_DETAILS_TABLE_SQL),
    ("public.modified_g_index_field_results", CREATE_MODIFIED_G_INDEX_FIELD_RESULTS_TABLE_SQL),
    ("public.modified_g_index_results", CREATE_MODIFIED_G_INDEX_RESULTS_TABLE_SQL),
]


def create_modified_g_index_tables(connection=None) -> None:
    """
    Create every table and index needed for the Modified g index
    (Section 2.10, Equations 20-22). Safe to run repeatedly (uses
    IF NOT EXISTS throughout).
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

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_modified_g_index_tables()
