from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation

from .calculate_total_cites import calculate_total_cites
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

    return parser


def main() -> None:
    arguments = build_parser().parse_args()

    # Rebuild the global field/year benchmark from the latest source data.
    print("Step 1/2: Refreshing field-year adjusted citation averages...")
    refresh_field_year_average()

    # Rebuild Equation 11 detail rows and final author-level T_a results.
    print("Step 2/2: Calculating Equation 11 Total Cites...")
    calculate_total_cites(
        author_ids=arguments.author_ids,
        as_of_year=arguments.as_of_year,
        career_boost=arguments.career_boost,
        career_decay=arguments.career_decay,
    )


if __name__ == "__main__":
    main()