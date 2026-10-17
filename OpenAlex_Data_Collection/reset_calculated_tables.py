"""Remove the CALCULATED tables / columns from the local database so they can be rebuilt.

Raw data is NEVER touched. Kept:
    author (incl. pub_finished, institution_done, career_compensation), publication,
    citation, author_contribution_weight (its weights are recomputed with --recompute, not
    dropped), field_classification, institution, author_institution.

Dropped (everything the equation scripts wrote, all of it can be rebuilt):
    Eq 7-9   influential_self_citations, author_paper_adjusted_citations
    Eq 11    field_year_adjusted_citation_average, total_cites_equation_11_details,
             author_total_cites                          (+ view equation_11_total_cites)
    Eq 12-14 field_adjusted_citation_average, field_citation_percentile_caps,
             citations_per_paper_details, author_citations_per_paper,
             citation_rate_details, author_citation_rate  (+ views equation_13/14_*)
    Eq 15    author_paper_field_effective_citation
    Eq 16-17 author_field_modified_hindex, author_modified_hindex
    Eq 18-23 columns author.modified_hm_index, author.modified_g_index,
             tables modified_g_index_results, g_index_field_reference,
             modified_g_index_paper_details, modified_g_index_field_results
    Eq 24-27 author_nm_index

Usage (from the OpenAlex_Data_Collection folder):
    python reset_calculated_tables.py            # DRY RUN: only lists what would be dropped
    python reset_calculated_tables.py --yes      # really drops them
    python reset_calculated_tables.py --yes --vacuum   # ...and shrinks the database file
                                                       # (needs free disk space, takes long)
"""

import argparse
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))

from db import DB_PATH   # noqa: E402

VIEWS = ["equation_11_total_cites", "equation_13_citations_per_paper",
         "equation_14_citation_rate"]

TABLES = [
    "influential_self_citations", "author_paper_adjusted_citations",
    "field_year_adjusted_citation_average", "total_cites_equation_11_details",
    "author_total_cites",
    "field_adjusted_citation_average", "field_citation_percentile_caps",
    "citations_per_paper_details", "author_citations_per_paper",
    "citation_rate_details", "author_citation_rate",
    "author_paper_field_effective_citation",
    "author_field_modified_hindex", "author_modified_hindex",
    "modified_g_index_results", "g_index_field_reference",
    "modified_g_index_paper_details", "modified_g_index_field_results",
    "author_nm_index",
]

AUTHOR_COLUMNS = ["modified_hm_index", "modified_g_index"]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="really drop (default is a dry run)")
    parser.add_argument("--vacuum", action="store_true",
                        help="VACUUM afterwards to shrink the file (slow, needs free disk space)")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit(f"Local database not found: {DB_PATH}")
    size_before = os.path.getsize(DB_PATH) / 1e9
    conn = sqlite3.connect(DB_PATH, timeout=30)
    existing = {r[0]: r[1] for r in conn.execute("SELECT name, type FROM sqlite_master")}
    author_cols = [r[1] for r in conn.execute("PRAGMA table_info(author)")]

    views = [v for v in VIEWS if existing.get(v) == "view"]
    tables = [t for t in TABLES if existing.get(t) == "table"]
    columns = [c for c in AUTHOR_COLUMNS if c in author_cols]

    print(f"Database: {DB_PATH}  ({size_before:.1f} GB)\n")
    print("Will drop" if args.yes else "DRY RUN -- would drop")
    for v in views:
        print(f"  view    {v}")
    for t in tables:
        print(f"  table   {t}")
    for col in columns:
        print(f"  column  author.{col}")
    missing = [t for t in TABLES if t not in tables]
    if missing:
        print(f"(not present, skipped: {', '.join(missing)})")
    print("\nKept: author, publication, citation, author_contribution_weight, "
          "field_classification, institution, author_institution")

    if not args.yes:
        print("\nNothing was changed. Re-run with --yes to drop these.")
        return

    try:
        conn.execute("BEGIN IMMEDIATE")      # fails fast if another script is using the database
    except sqlite3.OperationalError as error:
        sys.exit(f"Database is busy ({error}). Stop any running script and retry.")
    conn.rollback()

    started = time.time()
    for v in views:
        conn.execute(f"DROP VIEW IF EXISTS {v}")
    for t in tables:
        t0 = time.time()
        conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()
        print(f"  dropped table {t:46} {time.time() - t0:6.1f}s", flush=True)
    for col in columns:
        conn.execute(f"ALTER TABLE author DROP COLUMN {col}")
        conn.commit()
        print(f"  dropped column author.{col}", flush=True)
    print(f"\nDone in {(time.time() - started) / 60:.1f} min. Free pages stay inside the file "
          "and are reused by the next runs.")

    if args.vacuum:
        print("VACUUM ... (this can take a long time)", flush=True)
        conn.execute("VACUUM")
        print(f"File size: {size_before:.1f} GB -> {os.path.getsize(DB_PATH) / 1e9:.1f} GB")
    else:
        print(f"File size is still {os.path.getsize(DB_PATH) / 1e9:.1f} GB (use --vacuum to shrink).")
    conn.close()


if __name__ == "__main__":
    main()
