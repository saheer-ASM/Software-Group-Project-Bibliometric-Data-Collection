import argparse
import os
from decimal import Decimal

from dotenv import load_dotenv
from psycopg2 import sql

from .db_connection import get_connection
from .isc_calculator import (
    aggregate_equation_9,
    calculate_isc,
)
from .isc_repository import ISCRepository
from .models import (
    AuthorWeight,
    FieldData,
    ISCResult,
)


load_dotenv()


ZERO = Decimal("0")
ONE = Decimal("1")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate ISC Equation 7, "
            "adjusted citations Equation 8, "
            "and paper totals Equation 9."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Process only the first N "
            "citation pairs."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Calculate and print without "
            "saving to PostgreSQL."
        ),
    )

    parser.add_argument(
        "--epsilon-zero",
        type=Decimal,
        default=Decimal(
            os.getenv(
                "ISC_EPSILON_ZERO",
                "0.90",
            )
        ),
    )

    parser.add_argument(
        "--weight-tolerance",
        type=Decimal,
        default=Decimal(
            os.getenv(
                "ISC_WEIGHT_TOLERANCE",
                "0.02",
            )
        ),
    )

    return parser.parse_args()


def normalize_author_weights(
    weights: list[AuthorWeight],
    *,
    pub_id: str,
    tolerance: Decimal,
) -> list[AuthorWeight]:
    total = sum(
        (
            item.weight
            for item in weights
        ),
        ZERO,
    )

    if total <= ZERO:
        raise RuntimeError(
            f"Author weights for {pub_id} "
            "total zero."
        )

    if abs(total - ONE) > tolerance:
        raise RuntimeError(
            f"Author weights for {pub_id} "
            f"must total 1. Current total: {total}."
        )

    factor = ONE / total

    return [
        AuthorWeight(
            author_id=item.author_id,
            weight=item.weight * factor,
        )
        for item in weights
    ]


def normalize_fields(
    fields: list[FieldData],
    *,
    pub_id: str,
    tolerance: Decimal,
) -> list[FieldData]:
    total = sum(
        (
            field.field_weight
            for field in fields
        ),
        ZERO,
    )

    if total <= ZERO:
        raise RuntimeError(
            f"Field weights for {pub_id} "
            "total zero."
        )

    if abs(total - ONE) > tolerance:
        raise RuntimeError(
            f"Field weights for {pub_id} "
            f"must total 1. Current total: {total}."
        )

    factor = ONE / total

    return [
        FieldData(
            field_name=field.field_name,
            field_weight=(
                field.field_weight
                * factor
            ),
        )
        for field in fields
    ]


def execute_savepoint(
    connection,
    command: str,
    name: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("{} {}").format(
                sql.SQL(command),
                sql.Identifier(name),
            )
        )


def main() -> None:
    arguments = parse_arguments()

    if (
        arguments.limit is not None
        and arguments.limit <= 0
    ):
        raise ValueError(
            "--limit must be greater than zero."
        )

    if arguments.weight_tolerance < ZERO:
        raise ValueError(
            "--weight-tolerance cannot be negative."
        )

    connection = get_connection()
    repository = ISCRepository(
        connection
    )

    processed_pairs = 0
    skipped_pairs = 0
    saved_equation_8_rows = 0

    try:
        citation_pairs = (
            repository.fetch_citation_pairs(
                arguments.limit
            )
        )

        for pair_number, pair in enumerate(
            citation_pairs,
            start=1,
        ):
            savepoint_name = (
                f"isc_pair_{pair_number}"
            )

            execute_savepoint(
                connection,
                "SAVEPOINT",
                savepoint_name,
            )

            try:
                # Authors and weights of cited paper p.
                cited_author_weights = (
                    repository
                    .fetch_publication_author_weights(
                        pair.cited_pub_id
                    )
                )

                # Authors and weights of citing paper q.
                citing_author_weights = (
                    repository
                    .fetch_publication_author_weights(
                        pair.citing_pub_id
                    )
                )

                # Fields belong to cited paper p because
                # raw citation W_p^(f,i) is calculated
                # using the cited paper contribution.
                cited_fields = (
                    repository
                    .fetch_publication_fields(
                        pair.cited_pub_id
                    )
                )

                if not cited_author_weights:
                    raise RuntimeError(
                        "No author weights for cited "
                        f"paper {pair.cited_pub_id}."
                    )

                if not citing_author_weights:
                    raise RuntimeError(
                        "No author weights for citing "
                        f"paper {pair.citing_pub_id}."
                    )

                if not cited_fields:
                    raise RuntimeError(
                        "No field classification for "
                        f"cited paper {pair.cited_pub_id}."
                    )

                cited_author_weights = (
                    normalize_author_weights(
                        cited_author_weights,
                        pub_id=pair.cited_pub_id,
                        tolerance=(
                            arguments
                            .weight_tolerance
                        ),
                    )
                )

                citing_author_weights = (
                    normalize_author_weights(
                        citing_author_weights,
                        pub_id=pair.citing_pub_id,
                        tolerance=(
                            arguments
                            .weight_tolerance
                        ),
                    )
                )

                cited_fields = normalize_fields(
                    cited_fields,
                    pub_id=pair.cited_pub_id,
                    tolerance=(
                        arguments
                        .weight_tolerance
                    ),
                )

                cited_author_ids = [
                    item.author_id
                    for item
                    in cited_author_weights
                ]

                if not arguments.dry_run:
                    repository.delete_results_for_pair(
                        pair.cited_pub_id,
                        pair.citing_pub_id,
                    )

                pair_results: list[
                    ISCResult
                ] = []

                # For every cited-paper field.
                for field in cited_fields:

                    # For every author of cited paper p.
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
                            epsilon_zero=(
                                arguments
                                .epsilon_zero
                            ),
                            weight_tolerance=(
                                arguments
                                .weight_tolerance
                            ),
                        )

                        pair_results.append(
                            result
                        )

                        if arguments.dry_run:
                            print(
                                f"q="
                                f"{pair.citing_pub_id} "
                                f"-> p="
                                f"{pair.cited_pub_id} | "
                                f"author="
                                f"{target_author.author_id} | "
                                f"field="
                                f"{field.field_name} | "
                                f"ISC="
                                f"{result.isc_value:.6f} | "
                                f"raw="
                                f"{result.raw_citation:.6f} | "
                                f"adjusted="
                                f"{result.adjusted_citation:.6f}"
                            )

                        else:
                            repository.save_result(
                                result
                            )

                            saved_equation_8_rows += 1

                if arguments.dry_run:
                    results_by_author: dict[
                        str,
                        list[ISCResult],
                    ] = {}

                    for result in pair_results:
                        results_by_author.setdefault(
                            result.target_author_id,
                            [],
                        ).append(result)

                    for author_results in (
                        results_by_author.values()
                    ):
                        partial_total = (
                            aggregate_equation_9(
                                author_results
                            )
                        )

                        print(
                            "Partial Equation 9 "
                            f"for this citing paper | "
                            f"p="
                            f"{partial_total.cited_pub_id} | "
                            f"author="
                            f"{partial_total.target_author_id} | "
                            f"raw="
                            f"{partial_total.total_raw_citation:.6f} | "
                            f"adjusted="
                            f"{partial_total.total_adjusted_citation:.6f}"
                        )

                execute_savepoint(
                    connection,
                    "RELEASE SAVEPOINT",
                    savepoint_name,
                )

                processed_pairs += 1

                if (
                    not arguments.dry_run
                    and processed_pairs % 100 == 0
                ):
                    connection.commit()

                    print(
                        f"Committed {processed_pairs} "
                        "citation pairs."
                    )

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
            # Equation 9 is calculated from all
            # stored Equation 8 rows.
            repository.refresh_equation_9_results()

            connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print(
        "\nISC processing completed"
    )

    print(
        "Processed citation pairs: "
        f"{processed_pairs}"
    )

    print(
        "Skipped citation pairs:   "
        f"{skipped_pairs}"
    )

    print(
        "Saved Equation 8 rows:    "
        f"{saved_equation_8_rows}"
    )

    if not arguments.dry_run:
        print(
            "Equation 9 totals were refreshed."
        )


if __name__ == "__main__":
    main()