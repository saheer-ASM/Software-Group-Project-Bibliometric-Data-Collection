"""Equations 12, 13, 14 on the LOCAL database (SQLite port of
Equations_12_13_14/run_equations_12_13_14.py). Same options.

Needs the Equation 11 tables (total_cites_local) and author.career_compensation
(career_compensation_local) to be filled first.

Run from the OpenAlex_Data_Collection folder:
    python -m eq12_13_14_local.run_equations_12_13_14 --dry-run
    python -m eq12_13_14_local.run_equations_12_13_14
    python -m eq12_13_14_local.run_equations_12_13_14 --percentile-k 99 --as-of-year 2026
"""

import argparse
import time
from datetime import date
from decimal import Decimal

from . import repository
from .db_connection import get_connection
from .db_setup import create_equation_12_13_14_tables

DEFAULT_PERCENTILE_K = Decimal("99")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Calculate the outlier cap (Equation 12), citations "
            "per paper (Equation 13), and citation rate "
            "(Equation 14) on top of the existing Equation 9 / 11 "
            "pipeline."
        )
    )
    parser.add_argument(
        "--percentile-k", type=Decimal, default=DEFAULT_PERCENTILE_K,
        help="Percentile used for the Equation 12 cap threshold R_k,f (default: 99).")
    parser.add_argument(
        "--as-of-year", type=int, default=date.today().year,
        help="Evaluation year used for Equation 14's years-elapsed term (default: current year).")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Calculate and print a summary without writing to the database.")
    parser.add_argument(
        "--skip-table-setup", action="store_true",
        help="Skip CREATE TABLE / index / view statements (assume they already exist).")
    return parser.parse_args()


def run(*, percentile_k=DEFAULT_PERCENTILE_K, as_of_year=date.today().year,
        dry_run=False, skip_table_setup=False):
    connection = get_connection()
    started = time.time()

    def stamp(message):
        print(f"[{(time.time() - started) / 60:5.1f} min] {message}", flush=True)

    try:
        if not dry_run and not skip_table_setup:
            create_equation_12_13_14_tables(connection)

        n_rows = connection.execute(
            f"SELECT COUNT(*) FROM {repository.EQ11}").fetchone()[0]
        if not n_rows:
            print("No rows found in total_cites_equation_11_details. "
                  "Run the Equation 9 / 11 pipeline first.")
            return
        stamp(f"{n_rows:,} Equation 11 detail rows")

        repository.build_publication_counts(connection)
        stamp("publication counts (P) built")

        # --- Equation 12: field-level percentile cap thresholds -----------
        caps = repository.compute_field_percentile_caps(connection, percentile_k)
        stamp(f"Equation 12: computed R_{{{percentile_k},f}} for {len(caps)} field(s)")

        # --- Equation 13 support: TC_bar_f (field-only average) -----------
        averages = repository.compute_field_adjusted_citation_averages(connection)
        stamp("Equation 13 support: computed field-only adjusted citation averages "
              f"for {len(averages)} field(s)")

        if dry_run:
            print("\nDry run: no changes written to the database.")
            print("Top 5 field caps (field, n, cap, outliers):")
            for row in sorted(caps, key=lambda r: -r[2])[:5]:
                print(f"  {row[0]:45} n={row[2]:>10,}  cap={row[5]:.6f}  outliers={row[6]:,}")
            return

        with connection:
            repository.upsert_field_percentile_caps(connection, caps)
            repository.upsert_field_adjusted_citation_averages(connection, averages)
        stamp("Saved field caps and field averages")

        # --- Equation 13: citations per paper (S_a) ------------------------
        with connection:
            written = repository.insert_equation_13_details(connection, percentile_k)
        stamp(f"Equation 13: {written:,} detail row(s) written")
        with connection:
            authors = repository.aggregate_equation_13(connection)
        stamp(f"Equation 13: S_a written for {authors:,} author(s)")

        # --- Equation 14: citation rate (U_a) -------------------------------
        with connection:
            written = repository.insert_equation_14_details(
                connection, percentile_k, as_of_year)
        stamp(f"Equation 14: {written:,} detail row(s) written")
        with connection:
            authors = repository.aggregate_equation_14(connection, as_of_year)
        stamp(f"Equation 14: U_a written for {authors:,} author(s)")

        complete_13 = connection.execute(
            "SELECT COUNT(*) FROM author_citations_per_paper "
            "WHERE calculation_complete = 1").fetchone()[0]
        total_13 = connection.execute(
            "SELECT COUNT(*) FROM author_citations_per_paper").fetchone()[0]
        complete_14 = connection.execute(
            "SELECT COUNT(*) FROM author_citation_rate "
            "WHERE calculation_complete = 1").fetchone()[0]
        total_14 = connection.execute(
            "SELECT COUNT(*) FROM author_citation_rate").fetchone()[0]
        print(f"Authors with a fully complete S_a: {complete_13} / {total_13}")
        print(f"Authors with a fully complete U_a: {complete_14} / {total_14}")
        print("Saved Equation 12 field caps, Equation 13 "
              "(citations_per_paper_details, author_citations_per_paper), and "
              "Equation 14 (citation_rate_details, author_citation_rate).")

    finally:
        connection.close()


if __name__ == "__main__":
    arguments = parse_arguments()
    run(
        percentile_k=arguments.percentile_k,
        as_of_year=arguments.as_of_year,
        dry_run=arguments.dry_run,
        skip_table_setup=arguments.skip_table_setup,
    )
