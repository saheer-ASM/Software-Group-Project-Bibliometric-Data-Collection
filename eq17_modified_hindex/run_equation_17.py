import argparse
from dotenv import load_dotenv

import repository
from db_connection import get_connection
from db_setup import create_equation_17_table

load_dotenv()


def parse_arguments():
    parser = argparse.ArgumentParser(description="Calculate Equation 17 (final Hf'_a).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-table-setup", action="store_true")
    return parser.parse_args()


def run(*, dry_run=False, skip_table_setup=False):
    connection = get_connection()

    try:
        if not skip_table_setup:
            create_equation_17_table(connection)

        rows = repository.fetch_author_field_weight_and_hindex(connection)

        if not rows:
            print("No authorship/field data found. Check author_contribution_weight and field_classification.")
            return

        results = repository.build_equation_17_results(rows)

        ready = sum(1 for r in results if r.calculation_status == "READY")
        print(f"Equation 17: {len(results)} author(s) processed ({ready} READY).")

        for r in sorted(
            results,
            key=lambda r: (r.modified_hindex_final is None, -(r.modified_hindex_final or 0)),
        )[:10]:
            print(
                f"  author={r.author_id} fields_used={r.field_count} "
                f"num={r.weighted_numerator_sum} denom={r.total_field_weight_sum} "
                f"=> Hf'_a={r.modified_hindex_final} [{r.calculation_status}]"
            )

        if dry_run:
            print("Dry run: no changes written.")
            return

        repository.upsert_equation_17_results(connection, results)
        connection.commit()
        print("Saved to public.author_modified_hindex — your final modified H-index.")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    args = parse_arguments()
    run(dry_run=args.dry_run, skip_table_setup=args.skip_table_setup)