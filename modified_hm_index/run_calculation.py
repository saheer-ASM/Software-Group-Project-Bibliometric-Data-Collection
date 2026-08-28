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
    Load capped adjusted citation values.

    Database table:

        author_paper_field_effective_citation

    Database columns:

        pub_id
        capped_adjusted_citation

    Python DataFrame:

        paper_id
        capped_adjusted_citations
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

    citation = quote_identifier(
        config[
            "capped_adjusted_citations"
        ]
    )

    query = f"""
        SELECT

            {paper_id}
                AS paper_id,

            {citation}
                AS capped_adjusted_citations

        FROM {table}

        WHERE {citation}
            IS NOT NULL
    """

    print(
        "Fetching capped adjusted citations..."
    )

    dataframe = pd.read_sql(
        query,
        connection,
    )

    print(
        f"  Loaded {len(dataframe)} "
        f"citation records"
    )

    return dataframe


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

    print(
        f"  Loaded {len(dataframe)} "
        f"paper-field records"
    )

    return dataframe


# =============================================================
# CALCULATE FIELD NORMALIZATION
# =============================================================

def calculate_field_normalization(
    field_classification,
    paper_citations,
):
    """
    Calculate Hm field normalization.

    Steps:
        1. Collect citations for each field.
        2. Calculate the 90th percentile of citations
           for each field.
        3. Store the result as hm_field_normalization.

    Returns:
        DataFrame containing:

            field_id
            hm_field_normalization
    """

    # =========================================================
    # 1. JOIN PAPER FIELDS WITH CITATIONS
    # =========================================================

    field_citations = field_classification.merge(
        paper_citations[
            [
                "paper_id",
                "capped_adjusted_citations",
            ]
        ],
        on="paper_id",
        how="inner",
    )

    # =========================================================
    # 2. CLEAN CITATION VALUES
    # =========================================================

    field_citations[
        "capped_adjusted_citations"
    ] = pd.to_numeric(
        field_citations[
            "capped_adjusted_citations"
        ],
        errors="coerce",
    )

    field_citations = field_citations.dropna(
        subset=[
            "field_id",
            "capped_adjusted_citations",
        ]
    )

    # =========================================================
    # 3. CALCULATE 90TH PERCENTILE FOR EACH FIELD
    # =========================================================

    field_normalization = (
        field_citations
        .groupby("field_id")[
            "capped_adjusted_citations"
        ]
        .quantile(0.90)
        .reset_index()
    )

    # =========================================================
    # 4. RENAME RESULT
    # =========================================================

    field_normalization = field_normalization.rename(
        columns={
            "capped_adjusted_citations":
                "hm_field_normalization"
        }
    )

    # =========================================================
    # 5. REMOVE INVALID NORMALIZATION VALUES
    # =========================================================

    field_normalization = field_normalization[
        field_normalization[
            "hm_field_normalization"
        ] > 0
    ]

    return field_normalization[
        [
            "field_id",
            "hm_field_normalization",
        ]
    ]


# =============================================================
# LOAD ALL DATABASE DATA
# =============================================================

def get_data_from_database():
    """
    Load all required data from PostgreSQL.
    """

    connection = get_connection()

    try:

        print()
        print("=" * 60)
        print("LOADING DATABASE DATA")
        print("=" * 60)

        # -----------------------------------------------------
        # Author contribution
        # -----------------------------------------------------

        paper_authors = (
            load_author_contribution_weight(
                connection
            )
        )

        # -----------------------------------------------------
        # Author career factors
        # -----------------------------------------------------

        authors = load_authors(
            connection
        )

        # -----------------------------------------------------
        # Effective citations
        # -----------------------------------------------------

        paper_citations = (
            load_effective_citations(
                connection
            )
        )

        # -----------------------------------------------------
        # Paper fields
        # -----------------------------------------------------

        field_classification = load_paper_fields(
            connection
        )

        return {

            "paper_authors":
                paper_authors,

            "authors":
                authors,

            "paper_citations":
                paper_citations,

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
            "STEP 2: Calculating field normalization..."
        )

        field_normalization = (
            calculate_field_normalization(
                data[
                    "field_classification"
                ],

                data[
                    "paper_citations"
                ],
            )
        )

        print(
            f"  Calculated normalization "
            f"for "
            f"{len(field_normalization)} "
            f"fields"
        )

        print("\nFIELD NORMALIZATION:")
        print(field_normalization.to_string(index=False))

        # =====================================================
        # STEP 3
        # =====================================================

        print()
        print(
            "STEP 3: Calculating Modified Hm-index..."
        )

        calculator = (
            ModifiedHmIndexCalculator()
        )

        results = calculator.calculate(

            paper_authors=
                data[
                    "paper_authors"
                ],

            authors=
                data[
                    "authors"
                ],

            paper_citations=
                data[
                    "paper_citations"
                ],

            field_classification=
                data[
                    "field_classification"
                ],

            field_normalization=
                field_normalization,
        )

        print(
            f"  Calculated Modified "
            f"Hm-index for "
            f"{len(results)} authors"
        )

        # =====================================================
        # STEP 4
        # =====================================================

        print()
        print(
            "STEP 4: RESULTS SUMMARY"
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
        # STEP 5
        # =====================================================

        print()
        print(
            "STEP 5: Updating author table..."
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