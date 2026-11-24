"""Fetch publication years that are missing in the LOCAL database from OpenAlex.

Eq 10 (career factor) needs each author's first publication year. An author
whose papers all have publication.year = NULL gets NO career factor and is
excluded (see career_compensation_local). OpenAlex has a publication_year for
nearly every work, so a missing year usually means it was not saved locally.

For each publication with year IS NULL that has authors (a row in
author_contribution_weight), 100 per request:

    fetch  id, publication_year  from OpenAlex
    UPDATE publication SET year = <publication_year>   (only if OpenAlex has one)

Run it before career_compensation_local/run_career_compensation.py.
Resumable: filled years are never reselected.

Usage (from the OpenAlex_Data_Collection folder):
    python fill_missing_years.py --limit 200 --dry-run
    python fill_missing_years.py
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))

from db import DB_PATH, get_conn                        # noqa: E402
from fill_publications import (                         # noqa: E402
    BudgetExhausted, OPENALEX_API_KEY, OPENALEX_MAILTO, OPENALEX_WORKS_URL,
    REQUEST_DELAY_SECONDS, _get, short_id,
)

IDS_PER_REQUEST = 100          # OpenAlex allows up to 100 OR-ed ids per filter


def fetch_years(pub_ids):
    """{pub_id: year} for the works OpenAlex returned with a year."""
    params = {
        "filter": "openalex_id:" + "|".join(pub_ids),
        "per_page": IDS_PER_REQUEST,
        "select": "id,publication_year",
    }
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO
    page = _get(OPENALEX_WORKS_URL, params)
    years = {}
    for work in page.get("results", []):
        year = work.get("publication_year")
        if isinstance(year, int) and year > 0:
            years[short_id(work.get("id"))] = year
    return years


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None,
                        help="only the first N publications (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and print, write nothing to the database")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit(f"{DB_PATH} not found")
    conn = get_conn()

    todo = [r[0] for r in conn.execute(
        "SELECT p.pub_id FROM publication AS p "
        "JOIN author_contribution_weight AS a ON a.pub_id = p.pub_id "
        "WHERE p.year IS NULL ORDER BY p.rowid")]
    if args.limit:
        todo = todo[:args.limit]
    total = len(todo)
    print(f"{total:,} publication(s) with authors but no year\n")

    filled = still_missing = 0
    try:
        for start in range(0, total, IDS_PER_REQUEST):
            chunk = todo[start:start + IDS_PER_REQUEST]
            try:
                years = fetch_years(chunk)
            except BudgetExhausted as exc:
                print(f"\n!! {exc}\n   re-run after the reset; progress is saved")
                break
            except Exception as exc:
                print(f"[{start}/{total}] request failed ({exc}) -- continuing")
                continue
            if args.dry_run:
                for pub_id, year in list(years.items())[:3]:
                    print(f"  {pub_id}: {year}")
            else:
                with conn:
                    conn.executemany("UPDATE publication SET year = ? WHERE pub_id = ?",
                                     [(y, p) for p, y in years.items()])
            filled += len(years)
            still_missing += len(chunk) - len(years)
            print(f"[{start + len(chunk):,}/{total:,}] {len(years)} filled", flush=True)
            time.sleep(REQUEST_DELAY_SECONDS)
    except KeyboardInterrupt:
        print("\ninterrupted -- finished chunks are already saved")
    finally:
        conn.close()

    print("\n--- summary ---")
    print(f"years filled from OpenAlex:      {filled:,}")
    print(f"still no year (OpenAlex has none): {still_missing:,}")
    if args.dry_run:
        print("[dry run] nothing written to the database")


if __name__ == "__main__":
    main()
