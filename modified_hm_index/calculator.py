import pandas as pd
import numpy as np


class ModifiedHmIndexCalculator:
    """
    Calculates the Modified Hm-index.

    The calculation considers:

        1. Career factor
        2. Author contribution
        3. Capped adjusted citations
        4. Multiple research fields
        5. Field normalization

    The field normalization is supplied as a DataFrame
    calculated before this class is called.
    """

    def __init__(self):
        pass

    # =========================================================
    # MAIN CALCULATION
    # =========================================================

    def calculate(
        self,
        paper_authors: pd.DataFrame,
        authors: pd.DataFrame,
        paper_citations: pd.DataFrame,
        field_classification: pd.DataFrame,
        field_normalization: pd.DataFrame,
    ) -> pd.DataFrame:

        # =====================================================
        # 1. VALIDATE INPUT COLUMNS
        # =====================================================

        self._validate_columns(
            paper_authors,
            [
                "paper_id",
                "author_id",
                "contribution_weight",
            ],
            "paper_authors",
        )

        self._validate_columns(
            authors,
            [
                "author_id",
                "career_factor",
            ],
            "authors",
        )

        self._validate_columns(
            paper_citations,
            [
                "paper_id",
                "capped_adjusted_citations",
            ],
            "paper_citations",
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

        self._validate_columns(
            field_normalization,
            [
                "field_id",
                "hm_field_normalization",
            ],
            "field_normalization",
        )

        # =====================================================
        # 2. MERGE AUTHOR CONTRIBUTION + CAREER FACTOR
        # =====================================================

        data = paper_authors.merge(
            authors[
                [
                    "author_id",
                    "career_factor",
                ]
            ],
            on="author_id",
            how="inner",
        )

        # =====================================================
        # 3. MERGE CITATION DATA
        # =====================================================

        data = data.merge(
            paper_citations[
                [
                    "paper_id",
                    "capped_adjusted_citations",
                ]
            ],
            on="paper_id",
            how="inner",
        )

        # =====================================================
        # 4. MERGE PAPER FIELDS
        # =====================================================

        data = data.merge(
            field_classification[
                [
                    "paper_id",
                    "field_id",
                    "field_weight",
                ]
            ],
            on="paper_id",
            how="inner",
        )

        # =====================================================
        # 5. MERGE FIELD NORMALIZATION
        # =====================================================

        data = data.merge(
            field_normalization[
                [
                    "field_id",
                    "hm_field_normalization",
                ]
            ],
            on="field_id",
            how="inner",
        )

        # =====================================================
        # 6. CONVERT NUMERIC VALUES
        # =====================================================

        numeric_columns = [
            "career_factor",
            "contribution_weight",
            "capped_adjusted_citations",
            "field_weight",
            "hm_field_normalization",
        ]

        for column in numeric_columns:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        # =====================================================
        # 7. REMOVE INVALID DATA
        # =====================================================

        data = data.dropna(
            subset=numeric_columns
        )

        data = data[
            data["hm_field_normalization"] > 0
        ]

        data = data[
            data["contribution_weight"] > 0
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
        # 8. EQUATION 15
        #
        # TC_eff =
        # Career Factor
        # × Contribution Weight
        # × Capped Adjusted Citations
        # =====================================================

        data["tc_eff"] = (
            data["career_factor"]
            * data["contribution_weight"]
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
                    "contribution_weight",
                    "capped_adjusted_citations",
                    "hm_field_normalization",
                    "tc_eff",
                ]
            ]
            .sort_values("tc_eff", ascending=False)
            .head(20)
            .to_string(index=False)
        )

        # =====================================================
        # 9. FIELD-SPECIFIC HM CALCULATION
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
            # Effective contribution
            # -------------------------------------------------

            sorted_group[
                "effective_rank_contribution"
            ] = (
                sorted_group["career_factor"]
                * sorted_group["contribution_weight"]
            )

            # -------------------------------------------------
            # Cumulative effective contribution
            # -------------------------------------------------

            sorted_group[
                "r_eff"
            ] = (
                sorted_group[
                    "effective_rank_contribution"
                ].cumsum()
            )

            # -------------------------------------------------
            # Maximum effective rank
            # -------------------------------------------------

            max_r_eff = (
                sorted_group["r_eff"].max()
            )

            # -------------------------------------------------
            # Field normalization
            # -------------------------------------------------

            normalization = (
                sorted_group[
                    "hm_field_normalization"
                ].iloc[0]
            )

            # -------------------------------------------------
            # Field-specific Hm
            # -------------------------------------------------

            hm_prime_field_author = (
                max_r_eff
                / normalization
            )

            author_field_results.append(
                {
                    "author_id":
                        author_id,

                    "field_id":
                        field_id,

                    "hm_prime_field_author":
                        hm_prime_field_author,
                }
            )

        # =====================================================
        # 10. CREATE FIELD RESULTS DATAFRAME
        # =====================================================

        author_field_df = pd.DataFrame(
            author_field_results
        )

        if author_field_df.empty:

            raise ValueError(
                "No field-specific Hm-index "
                "values were calculated."
            )

        # =====================================================
        # 11. MERGE FIELD RESULTS
        # =====================================================

        data = data.merge(
            author_field_df,
            on=[
                "author_id",
                "field_id",
            ],
            how="inner",
        )

        # =====================================================
        # 12. EQUATION 20
        #
        # Weighted Hm across fields
        # =====================================================

        data["weighted_hm"] = (
            data["field_weight"]
            * data["hm_prime_field_author"]
        )

        # =====================================================
        # 13. GROUP BY AUTHOR
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
        # 14. CALCULATE FINAL MODIFIED HM-INDEX
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
        # 15. RETURN
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