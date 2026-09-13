"""
Configuration for the final Nm-index calculation (Eq. 24-27 of the
full paper / Eq. 23-25 of the extended abstract).

The Nm-index is the weighted average of the *percentile* scores of
six per-author component metrics:

    x1  T_a    outlier-uncontrolled WFYN total cites        (Eq. 11)
    x2  S_a    outlier-controlled  WFYN cites per paper      (Eq. 13)
    x3  U_a    outlier-controlled  WFYN citation rate        (Eq. 14)
    x4  Hf'_a  modified hf-index                             (Eq. 17)
    x5  Hm'_a  modified hm-index                             (Eq. 20)
    x6  G'_a   modified g-index                              (Eq. 23)

All six component scores are ALREADY computed by upstream pipelines
in this repo and stored one-row-per-author in the tables mapped
below. This module does NOT recompute them; it only does the final
transform -> normalize -> percentile -> weighted-average steps.
"""

# =============================================================
# SOURCE TABLES  (one row per author, read-only)
# =============================================================
#
# Each entry: logical metric name -> (table, id column, value column)
#
# NOTE (verified against the live DB on 2026-08-31):
#   * total_cites has ~1561/2321 non-null rows; the rest are still
#     NULL upstream and are treated as "metric not available".
#   * modified_g_index_results is currently EMPTY (0 rows). Until the
#     modified g-index pipeline is run, G'_a is unavailable for every
#     author and the Nm-index falls back to a 5-metric weighted
#     average (see NM_REQUIRE_ALL_METRICS below).
#   * The `calculation_complete` / `calculation_status` flags on these
#     tables are unreliable (mostly False/!READY even for rows that
#     hold a valid score), so we filter on "value IS NOT NULL" only.
#     Set NM_FILTER_STATUS = True to additionally honour them.

METRIC_SOURCES = {
    "total_cites": {
        "table": "author_total_cites",
        "author_id": "author_id",
        "value": "total_cites_score",
        "status": "calculation_complete",   # boolean
        "status_ok": (True,),
    },
    "citations_per_paper": {
        "table": "author_citations_per_paper",
        "author_id": "author_id",
        "value": "citations_per_paper_score",
        "status": "calculation_complete",
        "status_ok": (True,),
    },
    "citation_rate": {
        "table": "author_citation_rate",
        "author_id": "author_id",
        "value": "citation_rate_score",
        "status": "calculation_complete",
        "status_ok": (True,),
    },
    "modified_hf_index": {
        "table": "author_modified_hindex",
        "author_id": "author_id",
        "value": "modified_hindex_final",
        "status": "calculation_status",     # text
        "status_ok": ("READY",),
    },
    "modified_hm_index": {
        "table": "author",
        "author_id": "author_id",
        "value": "modified_hm_index",
        "status": None,
        "status_ok": (),
    },
    "modified_g_index": {
        "table": "modified_g_index_results",
        "author_id": "author_id",
        "value": "modified_g_index",
        "status": "calculation_complete",
        "status_ok": (True,),
    },
}

# The full set of authors to score is taken from this table.
AUTHOR_TABLE = {
    "table": "author",
    "author_id": "author_id",
    "author_name": "author_name",
}

# =============================================================
# OUTPUT
# =============================================================
#
# Results are written one-row-per-author into NM_RESULT_TABLE
# (created by schema.sql). Optionally the final score is also
# mirrored onto author.<AUTHOR_NM_COLUMN> the same way
# author.modified_hm_index is populated -- set NM_UPDATE_AUTHOR_TABLE
# to enable it (the column must exist first; see schema.sql).

NM_RESULT_TABLE = "author_nm_index"

NM_RESULT_COLUMNS = {
    "author_id": "author_id",
    # per-metric percentile scores (0-100), Per_a(x_i) from Eq. 26
    "total_cites": "per_total_cites",
    "citations_per_paper": "per_citations_per_paper",
    "citation_rate": "per_citation_rate",
    "modified_hf_index": "per_modified_hf_index",
    "modified_hm_index": "per_modified_hm_index",
    "modified_g_index": "per_modified_g_index",
    # bookkeeping
    "metrics_available": "metrics_available",   # int 0..6
    "nm_index": "nm_index",                     # final score, Eq. 27
    "calculated_at": "calculated_at",
}

NM_UPDATE_AUTHOR_TABLE = False
AUTHOR_NM_COLUMN = "nm_index"

# =============================================================
# ALGORITHM PARAMETERS
# =============================================================

# --- Eq. 27 weights: w_i, must sum to 1.0 ---------------------
# Equal 1/6 weighting is the paper's suggested default. Override
# here to emphasise particular metrics.
NM_WEIGHTS = {
    "total_cites": 1 / 6,
    "citations_per_paper": 1 / 6,
    "citation_rate": 1 / 6,
    "modified_hf_index": 1 / 6,
    "modified_hm_index": 1 / 6,
    "modified_g_index": 1 / 6,
}

# --- Eq. 24/25 metric families -------------------------------
# LOG_METRICS   -> Tra(x) = L(x) = log10(x + 1), then Nor(x) per
#                  NM_DISTRIBUTION below.
# RANK_METRICS  -> Tra(x) = P(x) (Blom plotting position on the
#                  fractional rank), then Nor(x) = phi^-1(P(x)),
#                  so Per(x) = 100 * P(x).
LOG_METRICS = ("total_cites", "citations_per_paper", "citation_rate")
RANK_METRICS = ("modified_hf_index", "modified_hm_index", "modified_g_index")

# --- Eq. 25 distribution assumption for the LOG metrics -------
# Per metric, one of:
#   "lognormal" -> Nor(x) = standard Z-score of L(x)
#                  Per(x) = 100 * phi(Z)
#   "hooked"    -> Nor(x) = phi^-1( P(L(x)) )   (rank-based inverse
#                  normal); reduces to Per(x) = 100 * P(L(x)).
#
# The paper splits this by research stream (humanities / social
# science ~ log-normal; medical / natural science ~ hooked power
# law). Because T_a / S_a / U_a are already cross-field per-author
# aggregates here, we apply one assumption per metric.
#
# DEFAULT = "hooked" for all three, because the paper's ONLY worked
# end-to-end example (section 3.3.3 "Final Nm-Index Calculation")
# explicitly states: "citation metrics (T_a, S_a, U_a) follow a
# hooked power law, so Nor_a(x) = phi^-1(P(L(x)))". Set a metric to
# "lognormal" to use the Z-score branch instead (better when a
# stream really is log-normal). CHANGE ONLY WITH SUPERVISOR SIGN-OFF
# -- this is a modelling choice, not a bug.
NM_DISTRIBUTION = {
    "total_cites": "hooked",
    "citations_per_paper": "hooked",
    "citation_rate": "hooked",
}

# --- Blom plotting position constant, P(x) = (r - a)/(N + 1 - 2a)
# Paper uses a = 0.375  ->  (r - 0.375) / (N + 0.25)
BLOM_A = 0.375

# --- Reference population size N in the plotting position ----
# None  -> N = number of authors actually scored for that metric
#          (the right choice when your author table is the whole
#          population you care about).
# int   -> use this fixed N instead. The paper's 3.3.3 example uses
#          N = 100000 because it ranks one profile inside a global
#          100k-profile sample. Only meaningful if the cohort you
#          load is genuinely at that scale -- with a small cohort a
#          large fixed N crushes every percentile toward 0.
NM_REFERENCE_N = None

# --- Rank tie handling --------------------------------------
# Paper section 2.5 / Eq. 24: "fractional ranking [39] for the
# hm, hf, g indices (as they contain many ties) ... and normal
# ranking for the raw citations".
#   RANK_METHOD_RANK -> Hf'/Hm'/G' : "average" == fractional ranking
#   RANK_METHOD_LOG  -> T/S/U      : "min"     == normal/competition
# NOTE: the real component data has a large mass of exact 0.0 in the
# citation metrics too (extreme skew). Under "min" that whole zero
# block shares rank 1 and lands near the 0th percentile; switch
# RANK_METHOD_LOG to "average" to spread it to the middle instead.
RANK_METHOD_RANK = "average"
RANK_METHOD_LOG = "min"

# --- Missing-metric policy ----------------------------------
# False -> if an author is missing >=1 of the 6 metrics, the
#          Nm-index is the weighted average over the metrics they
#          DO have, with NM_WEIGHTS renormalised to sum to 1 across
#          the available subset. metrics_available records how many
#          were used.
# True  -> authors missing any metric get nm_index = NULL.
NM_REQUIRE_ALL_METRICS = False

# Honour the per-table status flags in addition to NOT NULL.
NM_FILTER_STATUS = False
