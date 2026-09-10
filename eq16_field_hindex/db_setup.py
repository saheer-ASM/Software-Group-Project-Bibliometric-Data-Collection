from db_connection import get_connection


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.author_field_modified_hindex (
    author_id VARCHAR(100) NOT NULL,
    field_name VARCHAR(255) NOT NULL,

    raw_h_value INTEGER NOT NULL DEFAULT 0,
    papers_used INTEGER NOT NULL DEFAULT 0,

    field_normalization NUMERIC(28, 16),
    modified_hindex_field NUMERIC(28, 16),

    calculation_status VARCHAR(50) NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (author_id, field_name),

    CONSTRAINT fk_eq16_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq16_raw_h_nonneg
        CHECK (raw_h_value >= 0),

    CONSTRAINT chk_eq16_modified_nonneg
        CHECK (
            modified_hindex_field IS NULL
            OR modified_hindex_field >= 0
        )
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS
idx_eq16_author ON public.author_field_modified_hindex(author_id);

CREATE INDEX IF NOT EXISTS
idx_eq16_field ON public.author_field_modified_hindex(field_name);
"""


def create_equation_16_table(connection=None) -> None:
    owns_connection = connection is None
    connection = connection or get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            print("Created or verified table: public.author_field_modified_hindex")
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
    create_equation_16_table()