"""Equations 1-3 and 6 (author contribution weights) on the LOCAL database
(database/openalex.db).

This is the SQLite port of  Author contribution/main.py  (which runs on the
cloud PostgreSQL). The maths is the SAME code: author_contribution_calculator.py
here is an unmodified copy of the cloud one. Only the database access changed.

For every row of `author_contribution_weight` (one publication, up to 10 author
ids) it
    1. looks up the author NAMES from `author`               (names that exist)
    2. looks up the field weights from `field_classification`
    3. detects the ordering norm   ('alphabetical' | 'relative')
         - 1 or 2 authors            -> relative
         - 3+ authors in A-Z order   -> alphabetical, else relative
    4. computes each author's weight, summed over the paper's fields
         alphabetical : field_weight / N                          (Eq 1)
         relative     : field_weight * (1/position) / sum(1/pos)  (Eq 2-3, harmonic)
    5. writes author_ordering_norm and author1id_weight .. author10id_weight

New column added to the local table (once): author_ordering_norm TEXT.

Resumable: rows that already have author_ordering_norm are skipped, and every
batch is committed on its own. Publications with no authors, or with no field
classification, are skipped (left empty) and reported.

Usage (from the OpenAlex_Data_Collection folder):
    python author_contribution_local/run_author_contribution.py
    python author_contribution_local/run_author_contribution.py --limit 5000
    python author_contribution_local/run_author_contribution.py --dry-run --limit 20
"""

import argparse
import os
import sys

# Windows' default console codepage can't print every Unicode author name.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "database"))

from db import DB_PATH, get_conn                          # noqa: E402
from author_contribution_calculator import AuthorContributionCalculator  # noqa: E402

DEFAULT_BATCH = 2000
SQL_IN_CHUNK = 500       # ids per "IN (...)" query

AUTHOR_COLS = [f"author{i}id" for i in range(1, 11)]
WEIGHT_COLS = [f"author{i}id_weight" for i in range(1, 11)]


def chunks(items, size):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_names(conn, author_ids):
    """{author_id: author_name} for the given ids."""
    names = {}
    for part in chunks(author_ids, SQL_IN_CHUNK):
        marks = ",".join("?" * len(part))
        for aid, name in conn.execute(
                f"SELECT author_id, author_name FROM author WHERE author_id IN ({marks})",
                part):
            names[aid] = name
    return names


def fetch_fields(conn, pub_ids):
    """{pub_id: {field_name: weight}} -- same rules as the cloud get_field_weights."""
    result = {}
    for part in chunks(pub_ids, SQL_IN_CHUNK):
        marks = ",".join("?" * len(part))
        for row in conn.execute(
                "SELECT pub_id, field1_name, field1_weight, field2_name, field2_weight, "
                f"field3_name, field3_weight FROM field_classification "
                f"WHERE pub_id IN ({marks})", part):
            fields = {}
            for name, weight in ((row[1], row[2]), (row[3], row[4]), (row[5], row[6])):
                if name and weight is not None:
                    fields[name] = float(weight)
            result[row[0]] = fields
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N publications in total (testing)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--dry-run", action="store_true",
                        help="calculate and print, write nothing to the database")
    parser.add_argument("--recompute", action="store_true",
                        help="recalculate rows that already have weights (use this once after "
                             "the duplicate-name fix)")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit(f"Local database not found: {DB_PATH}")
    conn = get_conn()

    cols = [r[1] for r in conn.execute("PRAGMA table_info(author_contribution_weight)")]
    if "author_ordering_norm" not in cols:
        if args.dry_run:
            print("(dry run) column author_ordering_norm would be added")
        else:
            conn.execute("ALTER TABLE author_contribution_weight "
                         "ADD COLUMN author_ordering_norm TEXT")
            conn.commit()
            print("Added column author_contribution_weight.author_ordering_norm")
            cols.append("author_ordering_norm")
    has_norm = "author_ordering_norm" in cols

    total = conn.execute("SELECT COUNT(*) FROM author_contribution_weight").fetchone()[0]
    done_before = (conn.execute("SELECT COUNT(*) FROM author_contribution_weight "
                                "WHERE author_ordering_norm IS NOT NULL").fetchone()[0]
                   if has_norm and not args.recompute else 0)
    print(f"Author contribution weights so far: {done_before:,} done / {total:,} total "
          f"({done_before / total * 100:.2f}%), {total - done_before:,} left\n")

    calculator = AuthorContributionCalculator()
    select_sql = (f"SELECT rowid, pub_id, {', '.join(AUTHOR_COLS)} "
                  f"FROM author_contribution_weight WHERE rowid > ? "
                  + ("AND author_ordering_norm IS NULL "
                     if has_norm and not args.recompute else "")
                  + "ORDER BY rowid LIMIT ?")
    update_sql = ("UPDATE author_contribution_weight SET author_ordering_norm = ?, "
                  + ", ".join(f"{c} = ?" for c in WEIGHT_COLS) + " WHERE pub_id = ?")

    processed = no_authors = no_fields = 0
    seen = 0
    last_rowid = 0
    norms = {"alphabetical": 0, "relative": 0}

    while True:
        want = args.batch_size if not args.limit else min(args.batch_size,
                                                          args.limit - seen)
        if want <= 0:
            break
        rows = conn.execute(select_sql, (last_rowid, want)).fetchall()
        if not rows:
            break
        last_rowid = rows[-1][0]
        seen += len(rows)

        all_ids = {a for r in rows for a in r[2:] if a is not None}
        names = fetch_names(conn, all_ids)
        fields_by_pub = fetch_fields(conn, [r[1] for r in rows])

        updates = []
        for row in rows:
            pub_id = row[1]
            author_ids = [a for a in row[2:] if a is not None]
            if not author_ids:
                no_authors += 1
                continue

            fields = fields_by_pub.get(pub_id) or {}
            if not fields:
                no_fields += 1
                continue

            # DUPLICATE-NAME FIX. The cloud script keys every weight by author NAME, so two
            # authors with the same name were merged and their weights added (totals > 100,
            # which breaks Lemma 5/6 of the paper). Here the weights are taken BY POSITION
            # from the unchanged calculator methods, so every author id keeps its own share.
            # The ordering norm is detected exactly as before (from the names that exist).
            author_names = [names[a] for a in author_ids if names.get(a)]
            ordering = calculator.detect_ordering_norm(author_names, pub_id)
            n_authors = len(author_ids)
            by_position = [0.0] * n_authors
            for field, field_weight in fields.items():
                if ordering == "alphabetical":
                    per_position = calculator.calculate_alphabetical_weights(
                        pub_id, field, field_weight, n_authors)
                else:
                    per_position = calculator.calculate_relative_weights(
                        pub_id, field, field_weight, n_authors)
                for position, value in per_position.items():
                    by_position[position - 1] += value

            result = {"ordering_norm": ordering}
            weights = by_position + [None] * (10 - n_authors)
            updates.append((ordering, *weights, pub_id))
            norms[ordering] += 1

            if args.dry_run and processed + len(updates) <= 5:
                print(f"{pub_id}: {ordering}, fields={fields}")
                for a, w in zip(author_ids, weights):
                    print(f"    {a}  {names.get(a)!r:40} {w}")

        if not args.dry_run and updates:
            with conn:
                conn.executemany(update_sql, updates)
        processed += len(updates)

        overall = done_before + (0 if args.dry_run else processed)
        print(f"  overall: {overall:,} / {total:,} ({overall / total * 100:.2f}%)"
              + ("  [dry run]" if args.dry_run else ""), flush=True)

    overall = done_before + (0 if args.dry_run else processed)
    print("\n--- summary ---")
    print(f"publications calculated this run: {processed:,} "
          f"(alphabetical {norms['alphabetical']:,}, relative {norms['relative']:,})")
    print(f"skipped, no authors:              {no_authors:,}")
    print(f"skipped, no field classification: {no_fields:,}")
    print(f"Overall: {overall:,} done / {total:,} total "
          f"({overall / total * 100:.2f}%), {total - overall:,} left")
    if args.dry_run:
        print("[dry run] nothing written to the database")
    conn.close()


if __name__ == "__main__":
    main()
