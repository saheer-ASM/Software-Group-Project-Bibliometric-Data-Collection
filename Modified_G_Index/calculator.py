import pandas as pd
import numpy as np


class ModifiedGIndexCalculator:
    """
    Calculates the Modified g-index (Section 2.10 / Equations 20-22 of
    the Nm-index paper; same section numbered 21-23 in the earlier
    full-paper draft).

        Aeff,f,a(k) = SUM_{p'=1..k} TCeff,f,p',iap'         (Eq 20)
        G'_{f,a}    = max(k : Aeff,f,a(k) >= k^2) / G'_f     (Eq 21)
        G'_a        = [SUM_f (SUM_p Vpf) * G'_{f,a}]
                      / [SUM_f SUM_p Vpf]                    (Eq 22)

    DATA SOURCE: identical inputs to modified_hm_index --

        The calculator reads `career_factor` and the fully combined
        author-field weight (W_p^{f,i}, Eq. 1/3/4/5) DIRECTLY from
        `author_paper_field_effective_citation`, which is unique at
        (pub_id, author_id, field_name). `capped_adjusted_citations`
        there is already the Eq. 12 outlier-capped citation count, so
        Eq. 15's TCeff = CF_com * W_p^{f,i} * TC_cap is computed the
        same way it is for the Hf/Hm/g family of sub-indices -- see
        modified_hm_index/calculator.py, which shares this exact
        TCeff formula (only the aggregation after TCeff differs
        between hf, hm, and g).

    FIELD NORMALIZATION (G'_f) -- same open-modeling-decision problem
    as Hm'_f, resolved the same way, per the same supervisor
    instruction already applied in modified_hm_index:

        The paper defines Eq. 21 as G'_{f,a} = g_field_raw / G'_f but
        never specifies how to derive G'_f for real data -- its own
        worked example just asserts a bare constant (G'_f = 7) with
        no derivation shown (see Modified_G_Index/Modified_g_index_
        sheet.md for the earlier investigation that flagged this as
        the one genuine open item).

        Resolution (mirrors modified_hm_index's Hm'_f): G'_f is a
        "running value" -- the mean of every author's own raw
        g-index numerator (g_field_raw, the Eq. 21 numerator BEFORE
        dividing by anything) across all authors who have at least
        one paper in that field. Recomputed fresh from the current
        dataset on every call to calculate() -- nothing is stored or
        reused between runs, same as Hm'_f.

        This requires the same two-pass calculation Hm'_f uses:

            Pass 1: compute g_field_raw for every (author, field)
                    combination present in the data (Eq. 20/21
                    numerator only -- the largest k with
                    Aeff(k) >= k^2).
            Pass 2: for each field, average g_field_raw across all
                    authors in that field -> this becomes G'_f.
                    Divide each author's own g_field_raw by their
                    field's average to get G'_{f,a}.

        A field with only one contributing author will always
        normalize to exactly 1.0 for that author (same edge case as
        Hm'_f) -- expected, not a bug.

        Unlike Hm'_f (which uses a citation-weighted *effective rank*
        r_eff as its threshold), g-index compares cumulative effective
        citations directly against k^2 -- a strictly harder, faster-
        growing bar. On real data with heavy citation-count skew
        (most papers score TCeff far below 1), this means g_field_raw
        is 0 for most (author, field) pairs, exactly like Hm'_f's
        zero-inflation issue already documented for that module.
    """

    OUTLIER_CITATION_CAP = 150

    def __init__(self):
        pass

    # =========================================================
    # MAIN CALCULATION
    # =========================================================

    def calculate(
        self,
        effective_citations: pd.DataFrame,
        field_classification: pd.DataFrame,
    ) -> pd.DataFrame:

        # =====================================================
        # 1. VALIDATE INPUT COLUMNS
        # =====================================================

        self._validate_columns(
            effective_citations,
            [
                "paper_id",
                "author_id",
                "field_id",
                "career_factor",
                "author_field_weight",
                "capped_adjusted_citations",
            ],
            "effective_citations",
        )

        self._validate_columns(
            field_classification,
            [
                "paper_id",
                "field_id",
                "field_weight",
            ],
            "field_classification",
        )

        # =====================================================
        # 2. MERGE ON THE FULL COMPOSITE KEY
        # =====================================================

        data = effective_citations.merge(
            field_classification[
                [
                    "paper_id",
                    "field_id",
                    "field_weight",
                ]
            ],
            on=[
                "paper_id",
                "field_id",
            ],
            how="inner",
        )

        # =====================================================
        # 3. CONVERT NUMERIC VALUES
        # =====================================================

        numeric_columns = [
            "career_factor",
            "author_field_weight",
            "capped_adjusted_citations",
            "field_weight",
        ]

        for column in numeric_columns:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        # =====================================================
        # 4. REMOVE INVALID DATA
        # =====================================================

        data = data.dropna(subset=numeric_columns)

        data = data[data["author_field_weight"] > 0]
        data = data[data["career_factor"] > 0]
        data = data[data["field_weight"] > 0]

        if data.empty:
            raise ValueError("No valid data remains after cleaning.")

        # =====================================================
        # 5. EQUATION 15: TC_eff = CF_com * W_p^{f,i} * TC_cap^{adj,k}
        # =====================================================

        data["tc_eff"] = (
            data["career_factor"]
            * data["author_field_weight"]
            * data["capped_adjusted_citations"]
        )

        # =====================================================
        # 6. PASS 1: PER (AUTHOR, FIELD) RAW G-INDEX
        #
        # Equations 20-21 numerator only (g_field_raw is NOT yet
        # divided by anything here).
        # =====================================================

        author_field_results = []

        grouped = data.groupby(
            ["author_id", "field_id"],
            dropna=False,
        )

        for (author_id, field_id), group in grouped:

            # -------------------------------------------------
            # Sort papers descending by effective citations
            # (Eq. 20's requirement before taking the running
            # cumulative sum).
            # -------------------------------------------------

            sorted_group = group.sort_values(
                by="tc_eff",
                ascending=False,
            ).copy()

            # -------------------------------------------------
            # Cumulative effective citations, A_eff(k) (Eq. 20)
            # -------------------------------------------------

            sorted_group["cum_tc_eff"] = (
                sorted_group["tc_eff"].cumsum()
            )

            # -------------------------------------------------
            # Largest k such that A_eff(k) >= k^2 (Eq. 21
            # numerator). Once the condition fails it cannot
            # hold again for a larger k, because after sorting
            # descending the marginal citation added per step is
            # non-increasing while k^2's marginal requirement
            # (2k+1) strictly increases -- so a simple
            # first-failure break is equivalent to taking the
            # true maximum over all k.
            # -------------------------------------------------

            k_valid = 0
            for rank, cumulative in enumerate(
                sorted_group["cum_tc_eff"], start=1
            ):
                if cumulative >= rank * rank:
                    k_valid = rank
                else:
                    break

            author_field_results.append(
                {
                    "author_id": author_id,
                    "field_id": field_id,
                    "g_field_raw": float(k_valid),
                }
            )

        # =====================================================
        # 7. CREATE PER-AUTHOR-FIELD RESULTS DATAFRAME
        # =====================================================

        author_field_df = pd.DataFrame(author_field_results)

        if author_field_df.empty:
            raise ValueError(
                "No field-specific raw g-index values were calculated."
            )

        # Total distinct fields each author has >=1 valid paper in, BEFORE
        # the G'_f > 0 filter below drops any field. This is the
        # field_row_count reported in public.modified_g_index_results.
        field_row_counts = (
            author_field_df.groupby("author_id").size().rename("field_row_count")
        )

        # =====================================================
        # 8. PASS 2: FIELD AVERAGE NORMALIZATION (G'_f)
        #
        # Computed fresh from the current dataset -- the "running
        # value" described in the class docstring, not a stored or
        # externally supplied constant. Same treatment as Hm'_f in
        # modified_hm_index.
        # =====================================================

        field_normalization = (
            author_field_df
            .groupby("field_id")["g_field_raw"]
            .mean()
            .reset_index()
            .rename(columns={"g_field_raw": "g_field_normalization"})
        )

        field_normalization = field_normalization[
            field_normalization["g_field_normalization"] > 0
        ]

        if field_normalization.empty:
            raise ValueError(
                "No fields have a positive average raw g-index; "
                "cannot normalize."
            )

        author_field_df = author_field_df.merge(
            field_normalization,
            on="field_id",
            how="inner",
        )

        # =====================================================
        # 9. EQUATION 21: field-specific G', normalized by the
        # field average computed in Step 8.
        # =====================================================

        author_field_df["g_prime_field_author"] = (
            author_field_df["g_field_raw"]
            / author_field_df["g_field_normalization"]
        )

        # Distinct fields per author that actually survived the G'_f > 0
        # filter above (i.e. contribute to Equation 22, whether their own
        # g_prime_field_author is positive or exactly 0 -- see the
        # "phantom zero field" note in calculator.py's class docstring /
        # CLAUDE.md). This is included_field_row_count.
        included_field_row_counts = (
            author_field_df.groupby("author_id").size()
            .rename("included_field_row_count")
        )

        # =====================================================
        # 10. MERGE FIELD RESULTS BACK INTO MAIN DATA
        # =====================================================

        data = data.merge(
            author_field_df[
                [
                    "author_id",
                    "field_id",
                    "g_field_raw",
                    "g_field_normalization",
                    "g_prime_field_author",
                ]
            ],
            on=["author_id", "field_id"],
            how="inner",
        )

        # =====================================================
        # 11. EQUATION 22: weighted g-index across fields.
        # field_weight here is field_classification's V_p^f --
        # summing field_weight * g_prime_field_author over every
        # (paper, field) row for an author reproduces
        # SUM_f [ (SUM_p Vpf) * G'_{f,a} ], since G'_{f,a} is
        # constant within a given (author, field) group.
        # =====================================================

        data["weighted_g"] = (
            data["field_weight"] * data["g_prime_field_author"]
        )

        # =====================================================
        # 12. GROUP BY AUTHOR
        # =====================================================

        author_results = (
            data.groupby("author_id")
            .agg(
                weighted_g_sum=("weighted_g", "sum"),
                field_weight_total=("field_weight", "sum"),
            )
            .reset_index()
        )

        # =====================================================
        # 13. CALCULATE FINAL MODIFIED G-INDEX
        # =====================================================

        author_results["modified_g_index"] = np.where(
            author_results["field_weight_total"] != 0,
            author_results["weighted_g_sum"] / author_results["field_weight_total"],
            0,
        )

        # =====================================================
        # 13b. ATTACH FIELD-COUNT DIAGNOSTICS
        #
        # field_row_count: distinct fields this author has >=1 valid paper
        # in, before the G'_f > 0 filter.
        # included_field_row_count: of those, how many actually survived
        # into Equation 22 (their field's G'_f > 0 -- note this can
        # include "phantom zero" fields, see calculator.py docstring).
        # skipped_field_row_count: the rest -- fields whose dataset-wide
        # mean raw g is 0, so no author (including this one) can score
        # anything there.
        # =====================================================

        author_results = author_results.merge(
            field_row_counts, on="author_id", how="left"
        ).merge(
            included_field_row_counts, on="author_id", how="left"
        )

        author_results["field_row_count"] = (
            author_results["field_row_count"].fillna(0).astype(int)
        )
        author_results["included_field_row_count"] = (
            author_results["included_field_row_count"].fillna(0).astype(int)
        )
        author_results["skipped_field_row_count"] = (
            author_results["field_row_count"]
            - author_results["included_field_row_count"]
        )

        author_results["calculation_complete"] = (
            author_results["field_weight_total"] > 0
        )

        # =====================================================
        # 14. RETURN
        # =====================================================

        return author_results[
            [
                "author_id",
                "field_row_count",
                "included_field_row_count",
                "skipped_field_row_count",
                "field_weight_total",
                "weighted_g_sum",
                "modified_g_index",
                "calculation_complete",
            ]
        ]

    # =========================================================
    # COLUMN VALIDATION
    # =========================================================

    @staticmethod
    def _validate_columns(dataframe, required_columns, dataframe_name):
        missing_columns = [
            column
            for column in required_columns
            if column not in dataframe.columns
        ]

        if missing_columns:
            raise ValueError(
                f"{dataframe_name} is missing columns: {missing_columns}"
            )
