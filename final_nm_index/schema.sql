-- ============================================================
-- Schema for the final Nm-index (Eq. 27) output.
-- Run this ONCE against the target database before the first
--   python -m "final Nm index".run_calculation
-- ============================================================

-- One row per author: the six percentile component scores
-- (Per_a(x_i), Eq. 26) plus the final weighted Nm-index (Eq. 27).
CREATE TABLE IF NOT EXISTS author_nm_index (
    author_id                 VARCHAR PRIMARY KEY
                              REFERENCES author (author_id),

    -- Per_a(x_i): 0-100, NULL when that component metric is not
    -- available for this author upstream.
    per_total_cites           NUMERIC,
    per_citations_per_paper    NUMERIC,
    per_citation_rate          NUMERIC,
    per_modified_hf_index      NUMERIC,
    per_modified_hm_index      NUMERIC,
    per_modified_g_index       NUMERIC,

    -- How many of the 6 components fed the weighted average.
    metrics_available          SMALLINT NOT NULL DEFAULT 0,

    -- Eq. 27 result. NULL if the author had 0 usable components
    -- (or <6 when NM_REQUIRE_ALL_METRICS = True).
    nm_index                   NUMERIC,

    calculated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- OPTIONAL: mirror the final score onto the author table, the same
-- way author.modified_hm_index is populated. Only needed if
-- config.NM_UPDATE_AUTHOR_TABLE = True.
ALTER TABLE author
    ADD COLUMN IF NOT EXISTS nm_index NUMERIC;
