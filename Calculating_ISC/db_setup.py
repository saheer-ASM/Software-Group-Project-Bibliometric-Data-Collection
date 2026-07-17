from .db_connection import get_connection


CREATE_ISC_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.influential_self_citations (
    isc_id BIGSERIAL PRIMARY KEY,

    cited_pub_id VARCHAR(100)
        NOT NULL,

    citing_pub_id VARCHAR(100)
        NOT NULL,

    target_author_id VARCHAR(100)
        NOT NULL,

    field_name VARCHAR(255)
        NOT NULL,

    field_weight NUMERIC(18, 12)
        NOT NULL,

    target_author_overall_weight
        NUMERIC(18, 12)
        NOT NULL,

    self_author_ids TEXT[]
        NOT NULL
        DEFAULT ARRAY[]::TEXT[],

    core_author_ids TEXT[]
        NOT NULL
        DEFAULT ARRAY[]::TEXT[],

    non_overlap_author_ids TEXT[]
        NOT NULL
        DEFAULT ARRAY[]::TEXT[],

    self_influence_sum NUMERIC(18, 12)
        NOT NULL
        DEFAULT 0,

    core_influence_sum NUMERIC(18, 12)
        NOT NULL
        DEFAULT 0,

    non_overlap_influence_sum
        NUMERIC(18, 12)
        NOT NULL
        DEFAULT 0,

    core_author_count INTEGER
        NOT NULL
        DEFAULT 0,

    epsilon_zero NUMERIC(18, 12)
        NOT NULL
        DEFAULT 0.90,

    epsilon_value NUMERIC(18, 12)
        NOT NULL
        DEFAULT 0,

    isc_numerator NUMERIC(24, 16)
        NOT NULL
        DEFAULT 0,

    isc_denominator NUMERIC(24, 16)
        NOT NULL
        DEFAULT 0,

    isc_value NUMERIC(24, 16)
        NOT NULL,

    raw_citation NUMERIC(24, 16)
        NOT NULL,

    adjusted_citation NUMERIC(24, 16)
        NOT NULL,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_isc_cited_publication
        FOREIGN KEY (cited_pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_isc_citing_publication
        FOREIGN KEY (citing_pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_isc_target_author
        FOREIGN KEY (target_author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_isc_field_weight
        CHECK (
            field_weight > 0
            AND field_weight <= 1
        ),

    CONSTRAINT chk_isc_target_author_weight
        CHECK (
            target_author_overall_weight >= 0
            AND target_author_overall_weight <= 1
        ),

    CONSTRAINT chk_isc_core_author_count
        CHECK (
            core_author_count >= 0
        ),

    CONSTRAINT chk_isc_epsilon_zero
        CHECK (
            epsilon_zero >= 0
            AND epsilon_zero <= 1
        ),

    CONSTRAINT chk_isc_value
        CHECK (
            isc_value >= 0
            AND isc_value <= 1
        ),

    CONSTRAINT chk_isc_raw_citation
        CHECK (
            raw_citation >= 0
            AND raw_citation <= 1
        ),

    CONSTRAINT chk_isc_adjusted_citation
        CHECK (
            adjusted_citation >= 0
            AND adjusted_citation
                <= raw_citation
        ),

    CONSTRAINT uq_influential_self_citation
        UNIQUE (
            cited_pub_id,
            citing_pub_id,
            target_author_id,
            field_name
        )
);
"""


MIGRATE_EXISTING_ISC_TABLE_SQL = """
ALTER TABLE
public.influential_self_citations
ADD COLUMN IF NOT EXISTS
target_author_overall_weight
NUMERIC(18, 12)
NOT NULL
DEFAULT 0;


ALTER TABLE
public.influential_self_citations
ADD COLUMN IF NOT EXISTS
raw_citation
NUMERIC(24, 16)
NOT NULL
DEFAULT 0;


ALTER TABLE
public.influential_self_citations
ADD COLUMN IF NOT EXISTS
adjusted_citation
NUMERIC(24, 16)
NOT NULL
DEFAULT 0;


ALTER TABLE
public.influential_self_citations
ADD COLUMN IF NOT EXISTS
isc_value
NUMERIC(24, 16)
NOT NULL
DEFAULT 0;


DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name =
              'influential_self_citations'
          AND column_name = 'isc'
    ) THEN
        EXECUTE '
            UPDATE
            public.influential_self_citations
            SET isc_value = isc
            WHERE isc IS NOT NULL
        ';
    END IF;
END
$$;


ALTER TABLE
public.influential_self_citations
DROP COLUMN IF EXISTS isc;
"""


CREATE_EQUATION_9_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS
public.author_paper_adjusted_citations (
    cited_pub_id VARCHAR(100)
        NOT NULL,

    target_author_id VARCHAR(100)
        NOT NULL,

    citing_paper_count INTEGER
        NOT NULL
        DEFAULT 0,

    field_row_count INTEGER
        NOT NULL
        DEFAULT 0,

    total_raw_citation NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    total_adjusted_citation
        NUMERIC(28, 16)
        NOT NULL
        DEFAULT 0,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        cited_pub_id,
        target_author_id
    ),

    CONSTRAINT fk_equation9_publication
        FOREIGN KEY (cited_pub_id)
        REFERENCES public.publication(pub_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_equation9_author
        FOREIGN KEY (target_author_id)
        REFERENCES public.author(author_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_equation9_citing_count
        CHECK (
            citing_paper_count >= 0
        ),

    CONSTRAINT chk_equation9_field_count
        CHECK (
            field_row_count >= 0
        ),

    CONSTRAINT chk_equation9_raw
        CHECK (
            total_raw_citation >= 0
        ),

    CONSTRAINT chk_equation9_adjusted
        CHECK (
            total_adjusted_citation >= 0
            AND total_adjusted_citation
                <= total_raw_citation
        )
);
"""


CREATE_VIEW_SQL = """
CREATE OR REPLACE VIEW
public.equation_9_adjusted_citations AS
SELECT
    cited_pub_id,
    target_author_id,
    citing_paper_count,
    field_row_count,
    total_raw_citation,
    total_adjusted_citation,
    calculated_at
FROM public.author_paper_adjusted_citations;
"""


CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS
idx_isc_target_author
ON public.influential_self_citations(
    target_author_id
);

CREATE INDEX IF NOT EXISTS
idx_isc_cited_pub
ON public.influential_self_citations(
    cited_pub_id
);

CREATE INDEX IF NOT EXISTS
idx_isc_citing_pub
ON public.influential_self_citations(
    citing_pub_id
);

CREATE INDEX IF NOT EXISTS
idx_isc_cited_author
ON public.influential_self_citations(
    cited_pub_id,
    target_author_id
);
"""


def create_isc_tables() -> None:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                CREATE_ISC_TABLE_SQL
            )

            cursor.execute(
                MIGRATE_EXISTING_ISC_TABLE_SQL
            )

            cursor.execute(
                CREATE_EQUATION_9_TABLE_SQL
            )

            cursor.execute(
                CREATE_INDEXES_SQL
            )

            cursor.execute(
                CREATE_VIEW_SQL
            )

        connection.commit()

        print(
            "Created or updated Equation 7/8 table:"
        )

        print(
            "public.influential_self_citations"
        )

        print(
            "Created Equation 9 table:"
        )

        print(
            "public.author_paper_adjusted_citations"
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_isc_tables()