"""Make a copy of openalex.db as it was at the end of year t (RQ8 predictive validity).

Kept: publications with year <= t, citations whose citing AND cited papers are
kept, and the author / weight / field / contribution rows of kept papers.
publication.total_citation is reset to the kept citation count. Calculated
tables are not copied: run the normal pipeline on the snapshot with
--as-of-year t, then build historical_scores with src/build_labels.py
--historical-db <snapshot>.

Usage (from the OpenAlex_Data_Collection folder):
    python make_snapshot_db.py --year 2019 --out database\\snapshot_2019.db
    set OPENALEX_DB_PATH=database\\snapshot_2019.db   (then run the steps)
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))
from db import DB_PATH                                   # noqa: E402

COPY = {   # table -> WHERE clause on the source (alias s)
    "author": "1",
    "publication": "s.year IS NOT NULL AND s.year <= :t",
    "citation": ("s.pub_id IN (SELECT pub_id FROM main.publication) "
                 "AND s.cites_pub_id IN (SELECT pub_id FROM main.publication)"),
    "author_contribution_weight": "s.pub_id IN (SELECT pub_id FROM main.publication)",
    "field_classification": "s.pub_id IN (SELECT pub_id FROM main.publication)",
    "author_contribution_statement": "s.pub_id IN (SELECT pub_id FROM main.publication)",
    "institution": "1",
    "author_institution": "1",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--source", default=DB_PATH)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if os.path.abspath(args.out) == os.path.abspath(args.source):
        sys.exit("--out must differ from the source database")
    if os.path.exists(args.out):
        sys.exit(f"{args.out} already exists; delete it first")
    dst = sqlite3.connect(Path(args.out).resolve().as_uri(), uri=True)
    dst.execute("ATTACH DATABASE ? AS src", (Path(args.source).resolve().as_uri() + "?mode=ro",))
    tables = dict(dst.execute("SELECT name, sql FROM src.sqlite_master WHERE type = 'table'"))
    for table, where in COPY.items():
        if table not in tables:
            print(f"  (skip {table}: not in source)")
            continue
        dst.execute(tables[table])
        dst.execute(f"INSERT INTO main.{table} SELECT s.* FROM src.{table} AS s WHERE {where}",
                    {"t": args.year})
        dst.commit()
        n = dst.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0]
        print(f"  {table}: {n:,} rows")
    for idx_sql, in dst.execute("SELECT sql FROM src.sqlite_master WHERE type = 'index' "
                                "AND sql IS NOT NULL AND tbl_name IN (%s)"
                                % ",".join("?" * len(COPY)), list(COPY)).fetchall():
        dst.execute(idx_sql.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS", 1))
    dst.execute("UPDATE publication SET total_citation = (SELECT COUNT(DISTINCT c.cites_pub_id) "
                "FROM citation c WHERE c.pub_id = publication.pub_id AND c.cites_pub_id <> c.pub_id)")
    dst.commit()
    dst.execute("DETACH DATABASE src")
    dst.close()
    print(f"snapshot at end of {args.year} written to {args.out}")


if __name__ == "__main__":
    main()
