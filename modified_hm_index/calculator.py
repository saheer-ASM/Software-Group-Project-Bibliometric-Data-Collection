import pandas as pd
import numpy as np


class ModifiedHmIndexCalculator:
    """
    Calculates the Modified Hm-index.

    DATA SOURCE (important -- this changed from earlier versions):

        The calculator now reads `career_factor` and the combined
        author-field weight (W_p^{f,i} from Eq. 1/3/4/5) DIRECTLY
        from `effective_citations`, which is unique at
        (paper_id, author_id, field_id) -- NOT from separately
        recombining author_contribution_weight and
        field_classification. That table already contains the
        authoritative, precomputed values.

        `field_classification.field_weight` (V_p^f) is still
        needed separately, for a SECOND, different purpose: the
        final Eq. 20 cross-field combination. field_weight is
        used twice in this model by design -- once already baked
        into author_field_weight (used inside tc_eff / r_eff),
        and once again standalone here (used to weight each
        field's contribution to the author's overall score).

    FIELD NORMALIZATION (per supervisor instruction):

        Hm'_f is NOT supplied externally and is NOT a percentile of
        raw citations. It is a "running value" -- the mean of every
        author's raw effective rank (max_r_eff, the Eq. 19 numerator,
        BEFORE dividing by anything) across all authors who have at
        least one paper in that field.

        This is recalculated fresh from the current dataset on every
        call to calculate() -- nothing is stored or reused between
        runs. Authors with zero papers in a field are naturally
        excluded, since they never produce a max_r_eff for that
        field in the first place.

        This requires a two-pass calculation:

            Pass 1: compute max_r_eff for every (author, field)
                    combination present in the data (Eq. 15, 18, 19
                    numerator only).
            Pass 2: for each field, average max_r_eff across all
                    authors in that field -> this becomes Hm'_f.
                    Divide each author's own max_r_eff by their
                    field's average to get Hm'_{f,a}.

        A field with only one contributing author will always
        normalize to exactly 1.0 for that author, since the "field
        average" and the author's own value are identical in that
        case -- this is expected, not a bug.
    """

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
        #
        # (paper_id, field_id) -- effective_citations is already
        # unique at (paper_id, author_id, field_id), and
        # field_classification is unique at (paper_id, field_id),
        # so this merge cannot cross-join or duplicate rows, as
        # long as both source tables genuinely hold to those
        # uniqueness guarantees.
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

        data = data.dropna(
            subset=numeric_columns
        )

        data = data[
            data["author_field_weight"] > 0
        ]

        data = data[
            data["career_factor"] > 0
        ]

        data = data[
            data["field_weight"] > 0
        ]

        if data.empty:

            raise ValueError(
                "No valid data remains after cleaning."
            )

        # =====================================================
        # 5. EQUATION 15
        #
        # TC_eff =
        # Career Factor
        # × Author-Field Weight (already combines position
        #   weight and field share -- see class docstring)
        # × Capped Adjusted Citations
        #
        # This should closely match the effective_citation
        # column already present in the source table -- that
        # equivalence was verified by hand before this change
        # was made.
        # =====================================================

        data["tc_eff"] = (
            data["career_factor"]
            * data["author_field_weight"]
            * data["capped_adjusted_citations"]
        )

        print("\nTOP AUTHOR CALCULATION DATA:")
        print(
            data[
                [
                    "paper_id",
                    "author_id",
                    "field_id",
                    "career_factor",
                    "author_field_weight",
                    "capped_adjusted_citations",
                    "tc_eff",
                ]
            ]
            .sort_values("tc_eff", ascending=False)
            .head(20)
            .to_string(index=False)
        )

        # =====================================================
        # 6. PASS 1: PER (AUTHOR, FIELD) EFFECTIVE RANK
        #
        # Equations 15, 18, 19 (numerator only -- max_r_eff is
        # NOT yet divided by anything here).
        # =====================================================

        author_field_results = []

        grouped = data.groupby(
            [
                "author_id",
                "field_id",
            ],
            dropna=False,
        )

        for (
            author_id,
            field_id,
        ), group in grouped:

            # -------------------------------------------------
            # Sort papers according to effective citations
            # -------------------------------------------------

            sorted_group = group.sort_values(
                by="tc_eff",
                ascending=False,
            ).copy()

            # -------------------------------------------------
            # Effective contribution (Eq. 18 term)
            # -------------------------------------------------

            sorted_group[
                "effective_rank_contribution"
            ] = (
                sorted_group["career_factor"]
                * sorted_group["author_field_weight"]
            )

            # -------------------------------------------------
            # Cumulative effective rank and cumulative
            # effective citations (needed for the Eq. 19
            # threshold condition)
            # -------------------------------------------------

            sorted_group[
                "r_eff"
            ] = (
                sorted_group[
                    "effective_rank_contribution"
                ].cumsum()
            )

            sorted_group[
                "cum_tc_eff"
            ] = (
                sorted_group[
                    "tc_eff"
                ].cumsum()
            )

            # -------------------------------------------------
            # Find the largest k such that cumulative effective
            # citations still meet/exceed the cumulative
            # effective rank (h-index-style condition, Eq. 19)
            # -------------------------------------------------

            k_valid = 0
            for satisfied in (
                sorted_group["cum_tc_eff"]
                >= sorted_group["r_eff"]
            ):
                if satisfied:
                    k_valid += 1
                else:
                    break

            # -------------------------------------------------
            # Effective rank at the largest valid k
            # (this is the Eq. 19 NUMERATOR -- not yet
            # normalized)
            # -------------------------------------------------

            max_r_eff = (
                sorted_group["r_eff"].iloc[k_valid - 1]
                if k_valid > 0
                else 0.0
            )

            author_field_results.append(
                {
                    "author_id":
                        author_id,

                    "field_id":
                        field_id,

                    "max_r_eff":
                        max_r_eff,
                }
            )

        # =====================================================
        # 7. CREATE PER-AUTHOR-FIELD RESULTS DATAFRAME
        # =====================================================

        author_field_df = pd.DataFrame(
            author_field_results
        )

        if author_field_df.empty:

            raise ValueError(
                "No field-specific effective rank values "
                "were calculated."
            )

        # =====================================================
        # 8. PASS 2: FIELD AVERAGE NORMALIZATION (Hm'_f)
        #
        # Computed fresh from the current dataset -- this is
        # the "running value" described in the class docstring,
        # not a stored or externally supplied constant.
        # =====================================================

        field_normalization = (
            author_field_df
            .groupby("field_id")["max_r_eff"]
            .mean()
            .reset_index()
            .rename(
                columns={
                    "max_r_eff":
                        "hm_field_normalization"
                }
            )
        )

        field_normalization = field_normalization[
            field_normalization[
                "hm_field_normalization"
            ] > 0
        ]

        if field_normalization.empty:

            raise ValueError(
                "No fields have a positive average "
                "effective rank; cannot normalize."
            )

        author_field_df = author_field_df.merge(
            field_normalization,
            on="field_id",
            how="inner",
        )

        # =====================================================
        # 9. EQUATION 19
        #
        # Field-specific Hm, normalized by the field average
        # computed in Step 8.
        # =====================================================

        author_field_df["hm_prime_field_author"] = (
            author_field_df["max_r_eff"]
            / author_field_df["hm_field_normalization"]
        )

        # =====================================================
        # 10. MERGE FIELD RESULTS BACK INTO MAIN DATA
        # =====================================================

        data = data.merge(
            author_field_df[
                [
                    "author_id",
                    "field_id",
                    "hm_prime_field_author",
                ]
            ],
            on=[
                "author_id",
                "field_id",
            ],
            how="inner",
        )

        # =====================================================
        # 11. EQUATION 20
        #
        # Weighted Hm across fields. field_weight here is
        # field_classification's V_p^f -- the SECOND use of
        # field_weight in this model (see class docstring).
        # =====================================================

        data["weighted_hm"] = (
            data["field_weight"]
            * data["hm_prime_field_author"]
        )

        # =====================================================
        # 12. GROUP BY AUTHOR
        # =====================================================

        author_results = (
            data.groupby(
                "author_id"
            )
            .agg(
                numerator=(
                    "weighted_hm",
                    "sum",
                ),

                denominator=(
                    "field_weight",
                    "sum",
                ),
            )
            .reset_index()
        )

        # =====================================================
        # 13. CALCULATE FINAL MODIFIED HM-INDEX
        # =====================================================

        author_results[
            "modified_hm_index"
        ] = np.where(

            author_results[
                "denominator"
            ] != 0,

            author_results[
                "numerator"
            ]
            /
            author_results[
                "denominator"
            ],

            0,
        )

        # =====================================================
        # 14. RETURN
        # =====================================================

        return author_results[
            [
                "author_id",
                "modified_hm_index",
            ]
        ]

    # =========================================================
    # COLUMN VALIDATION
    # =========================================================

    @staticmethod
    def _validate_columns(
        dataframe,
        required_columns,
        dataframe_name,
    ):

        missing_columns = [
            column
            for column in required_columns
            if column not in dataframe.columns
        ]

        if missing_columns:

            raise ValueError(
                f"{dataframe_name} is missing "
                f"columns: {missing_columns}"
            )
