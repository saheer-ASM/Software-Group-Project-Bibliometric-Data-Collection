"""Command-line runner for Equation 11 on the LOCAL database.

SQLite port of Calculating_Total_Cites/run_total_cites.py. Same options, same two
steps. Run from the OpenAlex_Data_Collection folder:

    python -m total_cites_local.db_setup               # once: create the tables
    python -m total_cites_local.run_total_cites        # benchmark + Equation 11
    python -m total_cites_local.run_total_cites --author-id A5050585435
    python -m total_cites_local.run_total_cites --as-of-year 2026
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation

from .calculate_total_cites import calculate_total_cites
from .db_connection import get_connection
from .refresh_field_year_average import refresh_field_year_average


def decimal_argument(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid decimal value: {value}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the field/year adjusted-citation benchmark and then "
            "calculate Equation 11 (Total Cites T_a)."
        )
    )

    parser.add_argument(
        "--author-id",
        action="append",
        dest="author_ids",
        help=(
            "Calculate only this author. Repeat the option for multiple "
            "authors. Omit it to calculate all authors."
        ),
    )
    parser.add_argument(
        "--as-of-year",
        type=int,
        default=None,
        help="Year used to calculate career time. Default: current year.",
    )
    parser.add_argument(
        "--career-boost",
        type=decimal_argument,
        default=Decimal("1.25"),
        help="Equation 10 parameter C. Default: 1.25.",
    )
    parser.add_argument(
        "--career-decay",
        type=decimal_argument,
        default=Decimal("0.0601"),
        help="Equation 10 parameter lambda. Default: 0.0601.",
    )

    parser.add_argument(
        "--cohort",
        choices=["all", "done"],
        default="all",
        help="all authors (cloud behaviour) or only authors with pub_finished = 'done'.",
    )
    parser.add_argument(
        "--benchmark-population",
        choices=["updated", "all"],
        default="updated",
        help="papers used for the field-year averages: 'updated' = papers whose citing "
             "papers were collected (default), 'all' = every publication (cloud behaviour).",
    )
    parser.add_argument(
        "--min-group-size",
        type=int,
        default=10,
        help="field-year groups with fewer papers are smoothed (default 10).",
    )
    return parser


def main() -> None:
    arguments = build_parser().parse_args()

    # Rebuild the global field/year benchmark from the latest source data.
    print("Step 1/2: Refreshing field-year adjusted citation averages...")
    refresh_field_year_average(
        population=arguments.benchmark_population,
        min_group=arguments.min_group_size,
    )

    # Rebuild Equation 11 detail rows and final author-level T_a results.
    print("Step 2/2: Calculating Equation 11 Total Cites...")
    author_ids = arguments.author_ids
    if arguments.cohort == "done" and not author_ids:
        connection = get_connection()
        try:
            author_ids = [r[0] for r in connection.execute(
                "SELECT author_id FROM author WHERE pub_finished = 'done'")]
        finally:
            connection.close()
        print(f"Cohort 'done': {len(author_ids):,} authors")
    calculate_total_cites(
        author_ids=author_ids,
        as_of_year=arguments.as_of_year,
        career_boost=arguments.career_boost,
        career_decay=arguments.career_decay,
    )


if __name__ == "__main__":
    main()
