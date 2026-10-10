"""Equation 10 (career factor) on the LOCAL database (database/openalex.db).

SQLite port of  career-compentation/career-compentation.py  (cloud PostgreSQL).
Same formula, same constants, same rules:

    CF_com = C * (t + 1) ** (-lambda)            C = 1.25, lambda = 0.0601
    t      = AS_OF_YEAR - first_publication_year  (0 if the year is unknown)
    value  = round(CF_com, 4)

    first_publication_year = the earliest publication.year among the papers the
    author appears on in author_contribution_weight (any of author1id..author10id).

Only authors that appear in author_contribution_weight get a value (same as the
cloud script). The result is stored in a new column  author.career_compensation.

Idempotent: a re-run only rewrites rows whose value would change.

Usage (from the OpenAlex_Data_Collection folder):
    python career_compensation_local/run_career_compensation.py
    python career_compensation_local/run_career_compensation.py --limit 10
    python career_compensation_local/run_career_compensation.py --dry-run
    python career_compensation_local/run_career_compensation.py --as-of-year 2026
"""

import argparse
import os
import sys
from collections import Counter

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "database"))

from db import DB_PATH, get_conn                          # noqa: E402

C = 1.25                 # career boost at t = 0
LAMBDA = 0.0601          # decay rate
DEFAULT_AS_OF_YEAR = 2026   # the cloud script hard-codes 2026
WRITE_BATCH = 50_000

AUTHOR_COLS = ", ".join(f"a.author{i}id" for i in range(1, 11))


def career_factor(first_pub_year, as_of_year):
    """Eq 10 exactly as the cloud script computes it."""
    t = (as_of_year - first_pub_year) if first_pub_year else 0
    return round(C * ((t + 1) ** -LAMBDA), 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of-year", type=int, default=DEFAULT_AS_OF_YEAR,
                        help=f"evaluation year (default {DEFAULT_AS_OF_YEAR}, as in the cloud script)")
    parser.add_argument("--limit", type=int, default=None,
                        help="write only the first N authors (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="calculate and print, write nothing to the database")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit(f"Local database not found: {DB_PATH}")
    conn = get_conn()

    # ---- 1. earliest publication year per author (one streaming pass)
    print("Scanning author_contribution_weight x publication ...", flush=True)
    first_year = {}          # author_id -> min year (None if no known year)
    papers = 0
    cursor = conn.execute(
        f"SELECT {AUTHOR_COLS}, p.year FROM author_contribution_weight a "
        "JOIN publication p ON a.pub_id = p.pub_id")
    for row in cursor:
        papers += 1
        year = row[10]
        for aid in row[:10]:
            if aid is None:
                continue
            current = first_year.get(aid, 0)       # 0 = seen, no year yet
            if year is not None and (current == 0 or year < current):
                first_year[aid] = year
            elif aid not in first_year:
                first_year[aid] = 0
        if papers % 500_000 == 0:
            print(f"  {papers:,} papers scanned, {len(first_year):,} authors", flush=True)
    print(f"Scanned {papers:,} papers -> {len(first_year):,} authors\n")

    # ---- 2. Eq 10 for every author
    values = {aid: career_factor(y or None, args.as_of_year)
              for aid, y in first_year.items()}
    spread = Counter(values.values())
    print(f"career_compensation: min {min(values.values())}, max {max(values.values())}, "
          f"{len(spread)} distinct values")
    for aid in list(values)[:5]:
        print(f"  {aid}: first year {first_year[aid] or None} -> {values[aid]}")

    if args.dry_run:
        print("\n[dry run] nothing written to the database")
        conn.close()
        return

    # ---- 3. write to author.career_compensation
    cols = [r[1] for r in conn.execute("PRAGMA table_info(author)")]
    if "career_compensation" not in cols:
        conn.execute("ALTER TABLE author ADD COLUMN career_compensation REAL")
        conn.commit()
        print("\nAdded column author.career_compensation")

    items = list(values.items())
    if args.limit:
        items = items[:args.limit]
    changed = 0
    for start in range(0, len(items), WRITE_BATCH):
        part = [(v, aid, v) for aid, v in items[start:start + WRITE_BATCH]]
        with conn:
            before = conn.total_changes
            conn.executemany(
                "UPDATE author SET career_compensation = ? "
                "WHERE author_id = ? AND career_compensation IS NOT ?", part)
            changed += conn.total_changes - before
        done = min(start + WRITE_BATCH, len(items))
        print(f"  overall: {done:,} / {len(items):,} ({done / len(items) * 100:.1f}%)",
              flush=True)

    print(f"\nDone. Authors with a career factor: {len(items):,} "
          f"({changed:,} rows written/changed)")
    conn.close()


if __name__ == "__main__":
    main()
