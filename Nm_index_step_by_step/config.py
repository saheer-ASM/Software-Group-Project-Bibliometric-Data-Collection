"""
DB table/column map for Nm_index_step_by_step.

This module is a separate, explicit, one-step-at-a-time walkthrough of
the Nm-index final stage (Eq. 24-27), built alongside `final_nm_index/`
(the production implementation) rather than inside it -- by
instruction, `final_nm_index/` is not edited here, only read for the
DB details below.

The six source tables are the SAME ones `final_nm_index/config.py`
reads from (verified by viewing that file, read-only, on 2026-09-11):

    T_a    <- author_total_cites.total_cites_score
    S_a    <- author_citations_per_paper.citations_per_paper_score
    U_a    <- author_citation_rate.citation_rate_score
    Hf'_a  <- author_modified_hindex.modified_hindex_final
    Hm'_a  <- author.modified_hm_index
    G'_a   <- author.modified_g_index

(Hf'_a, Hm'_a, G'_a are written here as Hf_a, Hm_a, G_a -- the prime is
dropped only because "Hf'_a" is not a legal Python/pandas identifier.)

Nothing here recomputes citations, h-index, hm-index, etc. -- these
six values are already final, upstream-computed scores; this module
only reads them.
"""

# One entry per output column of Step 1 (build_dataset.py).
METRIC_SOURCES = {
    "T_a": {
        "table": "author_total_cites",
        "author_id": "author_id",
        "value": "total_cites_score",
    },
    "S_a": {
        "table": "author_citations_per_paper",
        "author_id": "author_id",
        "value": "citations_per_paper_score",
    },
    "U_a": {
        "table": "author_citation_rate",
        "author_id": "author_id",
        "value": "citation_rate_score",
    },
    "Hf_a": {
        "table": "author_modified_hindex",
        "author_id": "author_id",
        "value": "modified_hindex_final",
    },
    "Hm_a": {
        "table": "author",
        "author_id": "author_id",
        "value": "modified_hm_index",
    },
    "G_a": {
        "table": "author",
        "author_id": "author_id",
        "value": "modified_g_index",
    },
}

# The full set of authors (author_id universe) that Step 1 builds rows for.
AUTHOR_TABLE = {
    "table": "author",
    "author_id": "author_id",
}

# Order of columns in the Step 1 output dataset.
METRIC_COLUMNS = ("T_a", "S_a", "U_a", "Hf_a", "Hm_a", "G_a")

# Citation-group metrics -- log10(x+1) transform, "normal" (competition)
# ranking, per paper Eq. 24. T_a is implemented first; S_a and U_a follow
# the identical recipe in later steps.
CITATION_METRICS = ("T_a", "S_a", "U_a")

# --- Step 3 ranking method & Step 4 Blom constant -------------------
# Paper Eq. 24: "... and normal ranking for the raw citations" ->
# pandas method="min" (competition ranking: ties share the lower rank).
RANK_METHOD = "min"

# --- Rank tie method for the index metrics (Hf'_a, Hm'_a, G'_a) -----
# Paper Eq. 24: "fractional ranking [39] for the hm, hf, g indices
# (as they contain many ties) ... and normal ranking for the raw
# citations" -> pandas method="average" (fractional ranking: ties
# split the rank evenly, e.g. two tied values at positions 1-2 both
# get rank 1.5), used for Hf_a / Hm_a / G_a instead of RANK_METHOD
# ("min") above, which stays for T_a / S_a / U_a.
RANK_METHOD_RANK = "average"

# Blom's constant a in P = (r - a) / (N + 1 - 2a); the paper uses
# a = 0.375, giving P = (r - 0.375) / (N + 0.25).
BLOM_A = 0.375
