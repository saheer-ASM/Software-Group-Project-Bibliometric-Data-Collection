-- ============================================================
-- Author Search Module — PostgreSQL Schema
-- ============================================================

-- Authors
CREATE TABLE IF NOT EXISTS authors (
    author_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    affiliation VARCHAR(500),
    email       VARCHAR(255),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_authors_name ON authors USING gin(to_tsvector('english', name));

-- Publications
CREATE TABLE IF NOT EXISTS publications (
    publication_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title          VARCHAR(1000) NOT NULL,
    year           INT,
    venue          VARCHAR(500),
    doi            VARCHAR(255) UNIQUE,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Author ↔ Publication  (many-to-many, ordered by contribution)
CREATE TABLE IF NOT EXISTS author_publications (
    author_id          UUID NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
    publication_id     UUID NOT NULL REFERENCES publications(publication_id) ON DELETE CASCADE,
    contribution_order INT  NOT NULL DEFAULT 1,
    PRIMARY KEY (author_id, publication_id)
);

CREATE INDEX IF NOT EXISTS idx_ap_author ON author_publications(author_id);
CREATE INDEX IF NOT EXISTS idx_ap_pub    ON author_publications(publication_id);

-- Citations (each row = one paper citing another)
CREATE TABLE IF NOT EXISTS citations (
    citation_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publication_id        UUID NOT NULL REFERENCES publications(publication_id) ON DELETE CASCADE,
    citing_publication_id UUID NOT NULL REFERENCES publications(publication_id) ON DELETE CASCADE,
    is_self_citation      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (publication_id, citing_publication_id)
);

CREATE INDEX IF NOT EXISTS idx_cit_pub ON citations(publication_id);

-- Research fields
CREATE TABLE IF NOT EXISTS fields (
    field_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name     VARCHAR(255) NOT NULL UNIQUE
);

-- Publication ↔ Field  (many-to-many)
CREATE TABLE IF NOT EXISTS publication_fields (
    publication_id UUID NOT NULL REFERENCES publications(publication_id) ON DELETE CASCADE,
    field_id       UUID NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    PRIMARY KEY (publication_id, field_id)
);

-- Pre-computed author metrics (recalculated on demand / background job)
CREATE TABLE IF NOT EXISTS author_metrics (
    metric_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id            UUID NOT NULL UNIQUE REFERENCES authors(author_id) ON DELETE CASCADE,
    h_index              INT   NOT NULL DEFAULT 0,
    c_index              NUMERIC(10, 4) NOT NULL DEFAULT 0,
    nm_index             NUMERIC(10, 4) NOT NULL DEFAULT 0,
    total_citations      INT   NOT NULL DEFAULT 0,
    total_self_citations INT   NOT NULL DEFAULT 0,
    total_publications   INT   NOT NULL DEFAULT 0,
    calculated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
