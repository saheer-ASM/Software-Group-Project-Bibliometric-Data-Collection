from db_connection import get_connection


CREATE_EQUATION_15_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.author_paper_field_effective_citation (
    author_id VARCHAR(100)
        NOT NULL,

    pub_id VARCHAR(100)
        NOT NULL,

    field_name VARCHAR(255)
        NOT NULL,

    career_factor NUMERIC(18, 12),

    author_field_weight NUMERIC(28, 16),

    capped_adjusted_citation NUMERIC(28, 16),

    effective_citation NUMERIC(28, 16),

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

    CONSTRAINT fk_eq15_author
        FOREIGN KEY (author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_eq15_publication
        FOREIGN KEY (pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eq15_career_factor
        CHECK (career_factor IS NULL OR career_factor >= 0),

    CONSTRAINT chk_eq15_field_weight
        CHECK (
            author_field_weight IS NULL
            OR (author_field_weight >= 0 AND author_field_weight <= 1)
        ),

    CONSTRAINT chk_eq15_capped_citation
        CHECK (
            capped_adjusted_citation IS NULL
            OR capped_adjusted_citation >= 0
        ),

    CONSTRAINT chk_eq15_effective_citation
        CHECK (
            effective_citation IS NULL
            OR effective_citation >= 0
        )
);
"""

CREATE_EQUATION_15_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS
idx_eq15_author
ON public.author_paper_field_effective_citation(author_id);

CREATE INDEX IF NOT EXISTS
idx_eq15_publication
ON public.author_paper_field_effective_citation(pub_id);

CREATE INDEX IF NOT EXISTS
idx_eq15_field
ON public.author_paper_field_effective_citation(field_name);

CREATE INDEX IF NOT EXISTS
idx_eq15_status
ON public.author_paper_field_effective_citation(calculation_status);
"""


def create_equation_15_table(connection=None) -> None:
    owns_connection = connection is None
    connection = connection or get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_EQUATION_15_TABLE_SQL)
            print("Created or verified table: "
                  "public.author_paper_field_effective_citation")

            cursor.execute(CREATE_EQUATION_15_INDEXES_SQL)
            print("Created or verified indexes.")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        if owns_connection:
            connection.close()


if __name__ == "__main__":
    create_equation_15_table()