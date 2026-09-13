from db_connection import get_connection


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.author_modified_hindex (
    author_id VARCHAR(100) PRIMARY KEY,

    weighted_numerator_sum NUMERIC(28, 16) NOT NULL DEFAULT 0,
    total_field_weight_sum NUMERIC(28, 16) NOT NULL DEFAULT 0,
    modified_hindex_final NUMERIC(28, 16),

    field_count INTEGER NOT NULL DEFAULT 0,

    calculation_status VARCHAR(50) NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_eq17_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq17_final_nonneg
        CHECK (
            modified_hindex_final IS NULL
            OR modified_hindex_final >= 0
        )
);
"""


def create_equation_17_table(connection=None) -> None:
    owns_connection = connection is None
    connection = connection or get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            print("Created or verified table: public.author_modified_hindex")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_equation_17_table()