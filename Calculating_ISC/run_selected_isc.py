from __future__ import annotations
from pathlib import Path

import argparse
import os
from decimal import Decimal

from dotenv import load_dotenv

from .db_connection import get_connection
from .isc_calculator import calculate_isc
from .isc_repository import ISCRepository
from .run_isc import (
    execute_savepoint,
    normalize_author_weights,
    normalize_fields,
)


ZERO = Decimal("0")


# Duplicate IDs from the original list were removed.
# SELECTED_CITED_PUBLICATIONS = {
#     line.strip().strip('"').strip("'")
#     for line in Path(
#         "Calculating_ISC/selected_cited_publications.txt"
#     ).read_text().splitlines()
#     if line.strip()
# }

def get_weighted_publications(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT pub_id
            FROM author_contribution_weight
            """
        )

        return {
            row[0]
            for row in cursor.fetchall()
        }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate ISC Equations 7 and 8 for selected cited "
            "publications, then refresh their Equation 9 totals."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Calculate and display results without saving them."
        ),
    )

    parser.add_argument(
        "--env-file",
        default=None,
        help=(
            "Optional dotenv file containing database configuration."
        ),
    )

    parser.add_argument(
        "--epsilon-zero",
        type=Decimal,
        default=None,
        help=(
            "ISC epsilon-zero value. Defaults to ISC_EPSILON_ZERO "
            "from .env or 0.90."
        ),
    )

    parser.add_argument(
        "--weight-tolerance",
        type=Decimal,
        default=None,
        help=(
            "Allowed difference around weight totals 1 or 100. "
            "Defaults to ISC_WEIGHT_TOLERANCE from .env or 0.02."
        ),
    )


    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Number of publications per batch.",
    )

    parser.add_argument(
        "--batch-number",
        type=int,
        default=1,
        help="Batch number to process.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()



    if arguments.env_file:
        load_dotenv(
            dotenv_path=arguments.env_file,
            override=True,
        )

    epsilon_zero = (
        arguments.epsilon_zero
        if arguments.epsilon_zero is not None
        else Decimal(
            os.getenv(
                "ISC_EPSILON_ZERO",
                "0.90",
            )
        )
    )

    weight_tolerance = (
        arguments.weight_tolerance
        if arguments.weight_tolerance is not None
        else Decimal(
            os.getenv(
                "ISC_WEIGHT_TOLERANCE",
                "0.02",
            )
        )
    )

    if not ZERO <= epsilon_zero <= Decimal("1"):
        raise ValueError(
            "epsilon_zero must be between 0 and 1."
        )

    if weight_tolerance < ZERO:
        raise ValueError(
            "weight_tolerance cannot be negative."
        )

    connection = get_connection()

    selected_cited_publications = get_weighted_publications(
        connection
    )

    selected_ids = sorted(
        selected_cited_publications
    )

    if arguments.batch_size:

        start = (
            arguments.batch_number - 1
        ) * arguments.batch_size

        end = start + arguments.batch_size

        selected_ids = selected_ids[start:end]


    print(
        f"Processing publications: {len(selected_ids)}"
    )





    print(
    f"Selected weighted publications: {len(selected_cited_publications)}"
    )

    repository = ISCRepository(connection)

    processed_pairs = 0
    skipped_pairs = 0
    calculated_rows = 0
    saved_rows = 0

    try:
        citation_pairs = repository.fetch_citation_pairs(
            cited_pub_ids=selected_ids,
        )

        found_cited_publications = {
            pair.cited_pub_id
            for pair in citation_pairs
        }

        publications_without_citations = (
            selected_cited_publications
            - found_cited_publications
        )

        print(
            "Selected unique cited publications:",
            len(selected_cited_publications),
        )
        print(
            "Citation pairs found:",
            len(citation_pairs),
        )

        if publications_without_citations:
            print(
                "\nSelected publications with no citation pairs:"
            )
            for publication_id in sorted(
                publications_without_citations
            ):
                print(f"  {publication_id}")

        for pair_number, pair in enumerate(
            citation_pairs,
            start=1,
        ):
            savepoint_name = (
                f"selected_isc_{pair_number}"
            )

            execute_savepoint(
                connection,
                "SAVEPOINT",
                savepoint_name,
            )

            try:
                cited_author_weights = (
                    repository
                    .fetch_publication_author_weights(
                        pair.cited_pub_id
                    )
                )

                citing_author_weights = (
                    repository
                    .fetch_publication_author_weights(
                        pair.citing_pub_id
                    )
                )

                cited_fields = (
                    repository
                    .fetch_publication_fields(
                        pair.cited_pub_id
                    )
                )

                if not cited_author_weights:
                    raise RuntimeError(
                        "No author weights for cited publication "
                        f"{pair.cited_pub_id}."
                    )

                if not citing_author_weights:
                    raise RuntimeError(
                        "No author weights for citing publication "
                        f"{pair.citing_pub_id}."
                    )

                if not cited_fields:
                    raise RuntimeError(
                        "No field classification for cited publication "
                        f"{pair.cited_pub_id}."
                    )

                cited_author_weights = (
                    normalize_author_weights(
                        cited_author_weights,
                        pub_id=pair.cited_pub_id,
                        tolerance=weight_tolerance,
                    )
                )

                citing_author_weights = (
                    normalize_author_weights(
                        citing_author_weights,
                        pub_id=pair.citing_pub_id,
                        tolerance=weight_tolerance,
                    )
                )

                cited_fields = normalize_fields(
                    cited_fields,
                    pub_id=pair.cited_pub_id,
                    tolerance=weight_tolerance,
                )

                cited_author_ids = [
                    author.author_id
                    for author
                    in cited_author_weights
                ]

                if not arguments.dry_run:
                    repository.delete_results_for_pair(
                        pair.cited_pub_id,
                        pair.citing_pub_id,
                    )

                for field in cited_fields:
                    for target_author in (
                        cited_author_weights
                    ):
                        result = calculate_isc(
                            cited_pub_id=(
                                pair.cited_pub_id
                            ),
                            citing_pub_id=(
                                pair.citing_pub_id
                            ),
                            cited_author_ids=(
                                cited_author_ids
                            ),
                            citing_author_weights=(
                                citing_author_weights
                            ),
                            target_author_id=(
                                target_author.author_id
                            ),
                            target_author_overall_weight=(
                                target_author.weight
                            ),
                            field_name=(
                                field.field_name
                            ),
                            field_weight=(
                                field.field_weight
                            ),
                            epsilon_zero=epsilon_zero,
                            weight_tolerance=(
                                weight_tolerance
                            ),
                        )

                        calculated_rows += 1

                        if arguments.dry_run:
                            print(
                                f"q={pair.citing_pub_id} "
                                f"-> p={pair.cited_pub_id} | "
                                f"author={target_author.author_id} | "
                                f"field={field.field_name} | "
                                f"ISC={result.isc_value:.6f} | "
                                f"raw={result.raw_citation:.6f} | "
                                f"adjusted="
                                f"{result.adjusted_citation:.6f}"
                            )
                        else:
                            repository.save_result(result)
                            saved_rows += 1

                execute_savepoint(
                    connection,
                    "RELEASE SAVEPOINT",
                    savepoint_name,
                )

                processed_pairs += 1

                # Save every successful pair immediately. A later crash will
                # not remove results from pairs that already completed.
                if not arguments.dry_run:
                    connection.commit()

            except Exception as error:
                skipped_pairs += 1

                execute_savepoint(
                    connection,
                    "ROLLBACK TO SAVEPOINT",
                    savepoint_name,
                )
                execute_savepoint(
                    connection,
                    "RELEASE SAVEPOINT",
                    savepoint_name,
                )

                print(
                    "SKIPPED "
                    f"q={pair.citing_pub_id} "
                    f"-> p={pair.cited_pub_id}: "
                    f"{error}"
                )

        if arguments.dry_run:
            connection.rollback()
        else:
            # Refresh only the selected publications. Unrelated Equation 9
            # rows created by collaborators are left unchanged.
            repository.refresh_equation_9_results(
                cited_pub_ids=selected_ids,
            )
            connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print("\nSelected ISC processing completed")
    print(
        "Processed citation pairs:",
        processed_pairs,
    )
    print(
        "Skipped citation pairs:  ",
        skipped_pairs,
    )
    print(
        "Calculated Equation 7/8 rows:",
        calculated_rows,
    )
    print(
        "Saved Equation 7/8 rows:     ",
        saved_rows,
    )

    if arguments.dry_run:
        print(
            "Dry run completed: no database rows were saved."
        )
    else:
        print(
            "Selected Equation 9 totals refreshed."
        )


if __name__ == "__main__":
    main()
