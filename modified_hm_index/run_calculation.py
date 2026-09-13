import pandas as pd
import numpy as np

from datetime import datetime

from .database import get_connection
from .calculator import ModifiedHmIndexCalculator
from .config import TABLE_COLUMNS


# =============================================================
# SQL IDENTIFIER HELPER
# =============================================================

def quote_identifier(identifier):
    """
    Safely quote a PostgreSQL identifier.
    """

    return '"' + identifier.replace(
        '"',
        '""'
    ) + '"'


# =============================================================
# LOAD AUTHOR CONTRIBUTION DATA
# =============================================================

def load_author_contribution_weight(connection):
    """
    Convert the wide author contribution table:

        pub_id
        author1id
        author1id_weight
        author2id
        author2id_weight
        ...
        author10id
        author10id_weight

    into a normalized DataFrame:

        paper_id
        author_id
        contribution_weight
    """

    config = TABLE_COLUMNS[
        "author_contribution_weight"
    ]

    table = quote_identifier(
        config["table"]
    )

    paper_id_column = quote_identifier(
        config["paper_id"]
    )

    author_columns = config[
        "author_id_columns"
    ]

    weight_columns = config[
        "contribution_weight_columns"
    ]

    # ---------------------------------------------------------
    # Validate configuration
    # ---------------------------------------------------------

    if len(author_columns) != len(
        weight_columns
    ):

        raise ValueError(
            "The number of author ID columns "
            "must equal the number of "
            "contribution weight columns."
        )

    queries = []

    # ---------------------------------------------------------
    # Create one SELECT per author position
    # ---------------------------------------------------------

    for (
        author_column,
        weight_column,
    ) in zip(
        author_columns,
        weight_columns,
    ):

        author_column_sql = quote_identifier(
            author_column
        )

        weight_column_sql = quote_identifier(
            weight_column
        )

        query = f"""
            SELECT

                {paper_id_column}
                    AS paper_id,

                {author_column_sql}
                    AS author_id,

                {weight_column_sql}
                    AS contribution_weight

            FROM {table}

            WHERE {author_column_sql}
                IS NOT NULL

              AND {weight_column_sql}
                IS NOT NULL
        """

        queries.append(query)

    # ---------------------------------------------------------
    # Combine all author positions
    # ---------------------------------------------------------

    final_query = "\nUNION ALL\n".join(
        queries
    )

    print(
        "Fetching author contribution data..."
    )

    dataframe = pd.read_sql(
        final_query,
        connection,
    )
    # Convert contribution weights from percentage to proportion
    dataframe["contribution_weight"] = (
    pd.to_numeric(
        dataframe["contribution_weight"],
        errors="coerce"
    ) / 100.0
   )

    print(
        f"  Loaded {len(dataframe)} "
        f"author-paper records"
    )

    return dataframe


# =============================================================
# LOAD AUTHOR DATA
# =============================================================

def load_authors(connection):
    """
    Load author information.

    Database table:

        author

    Database columns:

        author_id
        career_compensation

    Python DataFrame columns:

        author_id
        career_factor
    """

    config = TABLE_COLUMNS[
        "author"
    ]

    table = quote_identifier(
        config["table"]
    )

    author_id = quote_identifier(
        config["author_id"]
    )

    career_factor = quote_identifier(
        config["career_factor"]
    )

    query = f"""
        SELECT

            {author_id}
                AS author_id,

            {career_factor}
                AS career_factor

        FROM {table}

        WHERE {author_id}
            IS NOT NULL

          AND {career_factor}
            IS NOT NULL
    """

    print(
        "Fetching authors and career factors..."
    )

    dataframe = pd.read_sql(
        query,
        connection,
    )

    print(
        f"  Loaded {len(dataframe)} "
        f"authors"
    )

    return dataframe


# =============================================================
# LOAD EFFECTIVE CITATIONS
# =============================================================

def load_effective_citations(connection):
    """
    Load per (paper, author, field) effective-citation data.

    IMPORTANT: this table is unique at (pub_id, author_id,
    field_name) -- NOT at pub_id alone. It already contains the
    fully combined per-author-per-field weight (author_field_weight,
    i.e. Eq. 1/3/4/5's W_p^{f,i}) and the correct per-row
    career_factor -- these are read directly rather than being
    recomputed from author_contribution_weight.

    Database table:

        author_paper_field_effective_citation

    Database columns:

        pub_id
        author_id
        field_name
        career_factor
        author_field_weight
        capped_adjusted_citation
        calculation_status

    Python DataFrame:

        paper_id
        author_id
        field_id
        career_factor
        author_field_weight
        capped_adjusted_citations

    Only rows with calculation_status = 'READY' are loaded. Rows
    still pending (e.g. MISSING_VALUE) are excluded, since they do
    not yet have a valid capped_adjusted_citation to work with.
    """

    config = TABLE_COLUMNS[
        "author_paper_field_effective_citation"
    ]

    table = quote_identifier(
        config["table"]
    )

    paper_id = quote_identifier(
        config["paper_id"]
    )

    author_id = quote_identifier(
        config["author_id"]
    )

    field_id = quote_identifier(
        config["field_id"]
    )

    career_factor = quote_identifier(
        config["career_factor"]
    )

    author_field_weight = quote_identifier(
        config["author_field_weight"]
    )

    citation = quote_identifier(
        config[
            "capped_adjusted_citations"
        ]
    )

    calculation_status = quote_identifier(
        config["calculation_status"]
    )

    query = f"""
        SELECT

            {paper_id}
                AS paper_id,

            {author_id}
                AS author_id,

            {field_id}
                AS field_id,

            {career_factor}
                AS career_factor,

            {author_field_weight}
                AS author_field_weight,

            {citation}
                AS capped_adjusted_citations

        FROM {table}

        WHERE {calculation_status} = 'READY'

          AND {citation}
            IS NOT NULL
    """

    print(
        "Fetching effective citation data "
        "(paper, author, field level)..."
    )

    dataframe = pd.read_sql(
        query,
        connection,
    )

    print(
        f"  Loaded {len(dataframe)} "
        f"paper-author-field effective "
        f"citation records"
    )

    return dataframe


# =============================================================
# APPLY CITATION OUTLIER CAP
# =============================================================

# Fixed outlier cap: no paper's capped_adjusted_citations value is
# allowed to exceed this, regardless of field. This is a flat cap
# (not a per-field percentile) applied uniformly across the whole
# dataset, per instruction.
OUTLIER_CITATION_CAP = 150


def apply_citation_outlier_cap(
    paper_citations,
    cap=OUTLIER_CITATION_CAP,
):
    """
    Cap capped_adjusted_citations at a fixed outlier threshold.

    Any paper whose citation value exceeds `cap` (default 150) is
    truncated down to `cap`. Values at or below `cap` are left
    unchanged. This reduces the influence of any single
    exceptionally-cited paper on downstream calculations (effective
    citation sums, field normalization, and the Modified Hm-index
    itself), without needing a per-field percentile computation.

    Parameters:
        paper_citations: DataFrame with a
            "capped_adjusted_citations" column.
        cap: the fixed ceiling to apply (default 150).

    Returns:
        A copy of paper_citations with capped_adjusted_citations
        clipped at `cap`.
    """

    paper_citations = paper_citations.copy()

    paper_citations[
        "capped_adjusted_citations"
    ] = pd.to_numeric(
        paper_citations[
            "capped_adjusted_citations"
        ],
        errors="coerce",
    )

    before_count = (
        paper_citations[
            "capped_adjusted_citations"
        ] > cap
    ).sum()

    paper_citations[
        "capped_adjusted_citations"
    ] = paper_citations[
        "capped_adjusted_citations"
    ].clip(upper=cap)

    print(
        f"  Applied outlier cap of {cap} "
        f"citations "
        f"({before_count} record(s) were "
        f"above the cap and got truncated)"
    )

    return paper_citations


# =============================================================
# LOAD PAPER FIELDS
# =============================================================

def load_paper_fields(connection):
    """
    Convert the wide paper field structure:

        pub_id
        field1_name
        field1_weight
        field2_name
        field2_weight
        field3_name
        field3_weight

    into:

        paper_id
        field_id
        field_weight
    """

    config = TABLE_COLUMNS[
        "field_classification"
    ]

    table = quote_identifier(
        config["table"]
    )

    paper_id = quote_identifier(
        config["paper_id"]
    )

    field_columns = config[
        "field_id_columns"
    ]

    weight_columns = config[
        "field_weight_columns"
    ]

    # ---------------------------------------------------------
    # Validate configuration
    # ---------------------------------------------------------

    if len(field_columns) != len(
        weight_columns
    ):

        raise ValueError(
            "The number of field ID columns "
            "must equal the number of "
            "field weight columns."
        )

    queries = []

    # ---------------------------------------------------------
    # Create one SELECT per field position
    # ---------------------------------------------------------

    for (
        field_column,
        weight_column,
    ) in zip(
        field_columns,
        weight_columns,
    ):

        field_column_sql = quote_identifier(
            field_column
        )

        weight_column_sql = quote_identifier(
            weight_column
        )

        query = f"""
            SELECT

                {paper_id}
                    AS paper_id,

                {field_column_sql}
                    AS field_id,

                {weight_column_sql}
                    AS field_weight

            FROM {table}

            WHERE {field_column_sql}
                IS NOT NULL

              AND {weight_column_sql}
                IS NOT NULL
        """

        queries.append(query)

    final_query = "\nUNION ALL\n".join(
        queries
    )

    print(
        "Fetching paper-field data..."
    )

    dataframe = pd.read_sql(
        final_query,
        connection,
    )

    # Convert field weights from percentage to proportion,
    # matching the same treatment already applied to
    # contribution_weight in load_author_contribution_weight().
    dataframe["field_weight"] = (
        pd.to_numeric(
            dataframe["field_weight"],
            errors="coerce",
        ) / 100.0
    )

    print(
        f"  Loaded {len(dataframe)} "
        f"paper-field records"
    )

    return dataframe


# =============================================================
# NOTE: calculate_field_normalization() has been REMOVED.
#
# Field normalization (Hm'_f) is no longer computed here as a
# percentile of citations. Per supervisor instruction, it is now
# computed INTERNALLY inside ModifiedHmIndexCalculator.calculate()
# as the mean of every author's raw effective rank across all
# authors in that field -- a "running value" recalculated fresh
# on every call, not stored or passed in from outside. See the
# class docstring in calculator.py for details.
# =============================================================


# =============================================================
# LOAD ALL DATABASE DATA
# =============================================================

def get_data_from_database():
    """
    Load all required data from PostgreSQL.

    NOTE: load_author_contribution_weight() and load_authors() are
    no longer called here. author_paper_field_effective_citation
    already contains the fully combined author_field_weight and the
    correct career_factor per (paper, author, field) row -- there is
    no need to separately load and recombine
    author_contribution_weight or the author table's
    career_compensation for this calculation. Both loader functions
    remain defined above in case another part of the system still
    needs them directly.
    """

    connection = get_connection()

    try:

        print()
        print("=" * 60)
        print("LOADING DATABASE DATA")
        print("=" * 60)

        # -----------------------------------------------------
        # Effective citations (paper, author, field level)
        # -----------------------------------------------------

        effective_citations = (
            load_effective_citations(
                connection
            )
        )

        effective_citations = (
            apply_citation_outlier_cap(
                effective_citations
            )
        )

        # -----------------------------------------------------
        # Paper fields
        # -----------------------------------------------------

        field_classification = load_paper_fields(
            connection
        )

        return {

            "effective_citations":
                effective_citations,

            "field_classification":
                field_classification,
        }

    finally:

        connection.close()


# =============================================================
# UPDATE AUTHOR TABLE
# =============================================================

def update_authors_table(results):
    """
    Update calculated Modified Hm-index values
    in the author table.
    """

    connection = get_connection()

    cursor = connection.cursor()

    config = TABLE_COLUMNS[
        "author"
    ]

    try:

        connection.autocommit = False

        table = quote_identifier(
            config["table"]
        )

        author_id = quote_identifier(
            config["author_id"]
        )

        modified_hm_index = quote_identifier(
            config["modified_hm_index"]
        )

        # -----------------------------------------------------
        # UPDATE query
        # -----------------------------------------------------

        update_sql = f"""
            UPDATE {table}

            SET {modified_hm_index} = %s

            WHERE {author_id} = %s
        """

        print()
        print("=" * 60)
        print("UPDATING AUTHOR TABLE")
        print("=" * 60)

        updated_count = 0

        # -----------------------------------------------------
        # Update each author
        # -----------------------------------------------------

        


        total_authors = len(results)

        for index, (_, row) in enumerate(
            results.iterrows(),
            start=1
        ):

            cursor.execute(
                update_sql,
                (
                    float(
                        row[
                            "modified_hm_index"
                        ]
                    ),

                    row[
                        "author_id"
                    ],
                ),
            )

            percentage = (index / total_authors) * 100

            print(
            f"[{index}/{total_authors}] "
            f"{percentage:6.2f}% | "
            f"Author: {row['author_id']} | "
            f"Hm-index: {row['modified_hm_index']:.4f}"
            )




            updated_count += 1

            if updated_count % 1000 == 0:

                print(
                    f"  Updated "
                    f"{updated_count} authors..."
                )

        # -----------------------------------------------------
        # Commit
        # -----------------------------------------------------

        connection.commit()

        print(
            f"Successfully updated "
            f"{updated_count} authors."
        )

    except Exception:

        connection.rollback()

        raise

    finally:

        cursor.close()

        connection.close()


# =============================================================
# MAIN
# =============================================================

def main():

    print()
    print("=" * 60)
    print("MODIFIED HM-INDEX CALCULATION")
    print("=" * 60)

    print(
        f"Started: {datetime.now()}"
    )

    try:

        # =====================================================
        # STEP 1
        # =====================================================

        print()
        print(
            "STEP 1: Loading database data..."
        )

        data = get_data_from_database()

        # =====================================================
        # STEP 2
        # =====================================================

        print()
        print(
            "STEP 2: Calculating Modified Hm-index..."
        )
        print(
            "  (field normalization is now computed "
            "internally by the calculator, as a running "
            "field-average value -- see calculator.py)"
        )

        calculator = (
            ModifiedHmIndexCalculator()
        )

        results = calculator.calculate(

            effective_citations=
                data[
                    "effective_citations"
                ],

            field_classification=
                data[
                    "field_classification"
                ],
        )

        print(
            f"  Calculated Modified "
            f"Hm-index for "
            f"{len(results)} authors"
        )

        # =====================================================
        # STEP 3
        # =====================================================

        print()
        print(
            "STEP 3: RESULTS SUMMARY"
        )

        print("-" * 60)

        print(
            f"Total authors: "
            f"{len(results)}"
        )

        print(
            f"Average Modified Hm-index: "
            f"{results['modified_hm_index'].mean():.4f}"
        )

        print(
            f"Minimum Modified Hm-index: "
            f"{results['modified_hm_index'].min():.4f}"
        )

        print(
            f"Maximum Modified Hm-index: "
            f"{results['modified_hm_index'].max():.4f}"
        )

        # =====================================================
        # TOP 5
        # =====================================================

        print()
        print(
            "Top 5 Authors:"
        )

        top_authors = results.nlargest(
            5,
            "modified_hm_index",
        )

        for _, row in (
            top_authors.iterrows()
        ):

            print(
                f"  Author "
                f"{row['author_id']}: "
                f"{row['modified_hm_index']:.4f}"
            )

        # =====================================================
        # STEP 4
        # =====================================================

        print()
        print(
            "STEP 4: Updating author table..."
        )

        update_authors_table(
            results
        )

        # =====================================================
        # COMPLETE
        # =====================================================

        print()
        print("=" * 60)
        print(
            "MODIFIED HM-INDEX CALCULATION COMPLETE"
        )
        print("=" * 60)

        print(
            f"Completed: {datetime.now()}"
        )

    except Exception as error:

        print()
        print("=" * 60)
        print(
            "CALCULATION FAILED"
        )
        print("=" * 60)

        print(
            f"Error: {error}"
        )

        import traceback

        traceback.print_exc()


# =============================================================
# RUN
# =============================================================

if __name__ == "__main__":

    main()