import argparse
from dotenv import load_dotenv

import repository
from db_connection import get_connection
from db_setup import create_equation_16_table

load_dotenv()


def parse_arguments():
    parser = argparse.ArgumentParser(description="Calculate Equation 16.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-table-setup", action="store_true")
    return parser.parse_args()


def run(*, dry_run=False, skip_table_setup=False):
    connection = get_connection()

    try:
        if not skip_table_setup:
            create_equation_16_table(connection)

        rows = repository.fetch_effective_citations(connection)

        if not rows:
            print(
                "No rows found in public.author_paper_field_effective_citation. "
                "Run the Equation 15 pipeline first."
            )
            return

        results = repository.build_equation_16_results(rows)

        ready = sum(1 for r in results if r.calculation_status == "READY")
        print(f"Equation 16: {len(results)} (author, field) row(s) processed ({ready} READY).")

        for r in results[:10]:
            print(
                f"  author={r.author_id} field={r.field_name} "
                f"raw_h={r.raw_h_value} papers={r.papers_used} "
                f"Hf_f={r.field_normalization} "
                f"=> Hf'_{{f,a}}={r.modified_hindex_field} [{r.calculation_status}]"
            )

        if dry_run:
            print("Dry run: no changes written.")
            return

        repository.upsert_equation_16_results(connection, results)
        connection.commit()
        print("Saved to public.author_field_modified_hindex.")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    args = parse_arguments()
    run(dry_run=args.dry_run, skip_table_setup=args.skip_table_setup)