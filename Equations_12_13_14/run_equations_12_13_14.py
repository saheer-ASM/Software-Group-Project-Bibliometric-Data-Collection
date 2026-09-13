import argparse
from datetime import date
from decimal import Decimal

from dotenv import load_dotenv

from . import repository
from .calculator import DEFAULT_PERCENTILE_K
from .db_connection import get_connection
from .db_setup import create_equation_12_13_14_tables


load_dotenv()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate the outlier cap (Equation 12), citations "
            "per paper (Equation 13), and citation rate "
            "(Equation 14) on top of the existing Equation 9 / 11 "
            "pipeline."
        )
    )

    parser.add_argument(
        "--percentile-k",
        type=Decimal,
        default=DEFAULT_PERCENTILE_K,
        help="Percentile used for the Equation 12 cap threshold R_k,f (default: 99).",
    )

    parser.add_argument(
        "--as-of-year",
        type=int,
        default=date.today().year,
        help="Evaluation year used for Equation 14's years-elapsed term (default: current year).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and print a summary without writing to PostgreSQL.",
    )

    parser.add_argument(
        "--skip-table-setup",
        action="store_true",
        help="Skip CREATE TABLE / index / view statements (assume they already exist).",
    )

    return parser.parse_args()


def run(
    *,
    percentile_k: Decimal = DEFAULT_PERCENTILE_K,
    as_of_year: int = date.today().year,
    dry_run: bool = False,
    skip_table_setup: bool = False,
) -> None:
    connection = get_connection()

    try:
        if not skip_table_setup:
            create_equation_12_13_14_tables(connection)

        equation_11_rows = repository.fetch_equation_11_rows(connection)

        if not equation_11_rows:
            print(
                "No rows found in public.total_cites_equation_11_details. "
                "Run the Equation 9 / 11 pipeline first."
            )
            return

        publication_counts = repository.fetch_publication_counts(connection)

        career_factors = {
            row["author_id"]: row["career_compensation"]
            for row in equation_11_rows
        }

        # --- Equation 12: field-level percentile cap thresholds -----------
        percentile_caps = repository.compute_field_percentile_caps(
            connection, percentile_k
        )

        print(
            f"Equation 12: computed R_{{{percentile_k},f}} for "
            f"{len(percentile_caps)} field(s)."
        )

        # --- Equation 13 support: TC_bar_f (field-only average) -----------
        field_averages = repository.compute_field_adjusted_citation_averages(
            connection
        )

        print(
            "Equation 13 support: computed field-only adjusted "
            f"citation averages for {len(field_averages)} field(s)."
        )

        # --- Equation 13: citations per paper (S_a) ------------------------
        equation_13_details = repository.build_equation_13_details(
            equation_11_rows,
            publication_counts,
            field_averages,
            percentile_caps,
            percentile_k,
        )

        equation_13_results = repository.aggregate_equation_13(
            equation_13_details,
            career_factors,
            publication_counts,
        )

        # --- Equation 14: citation rate (U_a) -------------------------------
        equation_14_details = repository.build_equation_14_details(
            equation_11_rows,
            percentile_caps,
            percentile_k,
            as_of_year,
        )

        equation_14_results = repository.aggregate_equation_14(
            equation_14_details,
            career_factors,
            as_of_year,
        )

        print_summary(
            equation_13_details,
            equation_13_results,
            equation_14_details,
            equation_14_results,
        )

        if dry_run:
            print("Dry run: no changes written to PostgreSQL.")
            return

        repository.upsert_field_adjusted_citation_averages(
            connection, list(field_averages.values())
        )

        repository.upsert_field_percentile_caps(
            connection, list(percentile_caps.values())
        )

        repository.upsert_equation_13_details(connection, equation_13_details)
        repository.upsert_author_citations_per_paper(
            connection, equation_13_results
        )

        repository.upsert_equation_14_details(connection, equation_14_details)
        repository.upsert_author_citation_rate(connection, equation_14_results)

        connection.commit()

        print(
            "Saved Equation 12 field caps, Equation 13 "
            "(public.citations_per_paper_details, "
            "public.author_citations_per_paper), and Equation 14 "
            "(public.citation_rate_details, "
            "public.author_citation_rate)."
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def print_summary(
    equation_13_details,
    equation_13_results,
    equation_14_details,
    equation_14_results,
) -> None:
    included_13 = sum(
        1
        for d in equation_13_details
        if d.calculation_status in repository.INCLUDED_STATUSES
    )

    included_14 = sum(
        1
        for d in equation_14_details
        if d.calculation_status in repository.INCLUDED_STATUSES
    )

    print(
        f"Equation 13: {len(equation_13_details)} detail row(s) "
        f"({included_13} included in S_a) across "
        f"{len(equation_13_results)} author(s)."
    )

    print(
        f"Equation 14: {len(equation_14_details)} detail row(s) "
        f"({included_14} included in U_a) across "
        f"{len(equation_14_results)} author(s)."
    )

    complete_13 = sum(
        1 for r in equation_13_results if r.calculation_complete
    )

    complete_14 = sum(
        1 for r in equation_14_results if r.calculation_complete
    )

    print(
        f"Authors with a fully complete S_a: {complete_13} / "
        f"{len(equation_13_results)}"
    )

    print(
        f"Authors with a fully complete U_a: {complete_14} / "
        f"{len(equation_14_results)}"
    )


if __name__ == "__main__":
    arguments = parse_arguments()

    run(
        percentile_k=arguments.percentile_k,
        as_of_year=arguments.as_of_year,
        dry_run=arguments.dry_run,
        skip_table_setup=arguments.skip_table_setup,
    )
