import argparse

from dotenv import load_dotenv

import repository
from db_connection import get_connection
from db_setup import create_equation_15_table


load_dotenv()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate Equation 15 effective citations."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and print a summary without writing to PostgreSQL.",
    )

    parser.add_argument(
        "--skip-table-setup",
        action="store_true",
        help="Skip CREATE TABLE / index statements (assume table exists).",
    )

    return parser.parse_args()


def run(*, dry_run: bool = False, skip_table_setup: bool = False) -> None:
    connection = get_connection()

    try:
        if not skip_table_setup:
            create_equation_15_table(connection)

        source_rows = repository.fetch_equation_15_source_rows(connection)

        if not source_rows:
            print(
                "No rows found in public.citations_per_paper_details. "
                "Run the Equation 12/13 pipeline first."
            )
            return

        details = repository.build_equation_15_details(source_rows)

        ready = sum(1 for d in details if d.calculation_status == "READY")
        print(
            f"Equation 15: {len(details)} row(s) processed "
            f"({ready} with a usable effective_citation)."
        )

        for d in details[:10]:
            print(
                f"  author={d.author_id} pub={d.pub_id} "
                f"field={d.field_name} "
                f"CFcom={d.career_factor} "
                f"W={d.author_field_weight} "
                f"TCcap={d.capped_adjusted_citation} "
                f"=> TCadj_eff={d.effective_citation} "
                f"[{d.calculation_status}]"
            )

        if dry_run:
            print("Dry run: no changes written to PostgreSQL.")
            return

        repository.upsert_equation_15_details(connection, details)
        connection.commit()

        print(
            "Saved Equation 15 results to "
            "public.author_paper_field_effective_citation."
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    arguments = parse_arguments()

    run(
        dry_run=arguments.dry_run,
        skip_table_setup=arguments.skip_table_setup,
    )