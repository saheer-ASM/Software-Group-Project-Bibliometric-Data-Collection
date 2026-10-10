"""Collect the authors (co-authors) of every publication into the local SQLite
database  database/openalex.db.  Same logic as scripts_db/co_authors_migrations.py
(the old Postgres version), but faster: 100 publications per OpenAlex request.

For each publication whose `co_author` column is NULL:

    fetch its `authorships` from OpenAlex
    insert every author not already in `author`         (pub_finished = 'no need')
    write ONE row to `author_contribution_weight`       (first 10 author ids)
    mark publication.co_author = 'done'                 <- one transaction per request

`co_author` stays NULL for any publication OpenAlex did not return, so it is
retried on the next run. Resumable by construction.

Uses its own API key: OPENALEX_API_KEY_CO_AUTHOR (in .env).

Runs in batches (default 5000 publications) and asks permission before the
next batch.

Usage:
    python collect_co_authors.py                   # all publications, 5000 per batch
    python collect_co_authors.py --own-only        # skip citing papers (no need to update)
    python collect_co_authors.py --limit 5 --dry-run
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))

from db import DB_PATH, get_conn                        # noqa: E402
from fill_publications import (                   # noqa: E402
    BudgetExhausted, OPENALEX_MAILTO, OPENALEX_WORKS_URL, REQUEST_DELAY_SECONDS,
    _get, short_id,
)

API_KEY = os.getenv("OPENALEX_API_KEY_CO_AUTHOR", "")
IDS_PER_REQUEST = 100          # OpenAlex allows up to 100 OR-ed ids per filter
DEFAULT_BATCH_SIZE = 5000
MAX_AUTHORS = 10
NO_NEED_PUBS = "no need"       # pub_finished value for co-authors: never collect their papers

ID_COLS = [f"author{i}id" for i in range(1, MAX_AUTHORS + 1)]
UPSERT_SQL = (
    "INSERT INTO author_contribution_weight (pub_id, " + ", ".join(ID_COLS) + ") "
    "VALUES (" + ",".join("?" * (1 + MAX_AUTHORS)) + ") "
    "ON CONFLICT(pub_id) DO UPDATE SET "
    + ", ".join(f"{c}=excluded.{c}" for c in ID_COLS)      # weights are left untouched
)


def fetch_authorships(pub_ids):
    """{pub_id: [(author_id, author_name), ...]} for the works OpenAlex returned."""
    params = {
        "filter": "openalex_id:" + "|".join(pub_ids),
        "per_page": IDS_PER_REQUEST,
        "select": "id,authorships",
        "api_key": API_KEY,
    }
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO
    page = _get(OPENALEX_WORKS_URL, params)
    found = {}
    for work in page.get("results", []):
        authors = []
        for authorship in work.get("authorships") or []:
            author = (authorship or {}).get("author") or {}
            aid = short_id(author.get("id"))
            if aid:
                authors.append((aid, author.get("display_name") or "Unknown"))
        found[short_id(work.get("id"))] = authors
    return found


def save_chunk(conn, found):
    """Write one request's results atomically. Returns (pubs_done, new_authors)."""
    new_authors = 0
    with conn:
        for pub_id, authors in found.items():
            for aid, name in authors:
                new_authors += conn.execute(
                    "INSERT OR IGNORE INTO author (author_id, author_name, pub_finished) "
                    "VALUES (?,?,?)", (aid, name, NO_NEED_PUBS)).rowcount
            ids = [a[0] for a in authors[:MAX_AUTHORS]]
            ids += [None] * (MAX_AUTHORS - len(ids))
            conn.execute(UPSERT_SQL, (pub_id, *ids))
            conn.execute("UPDATE publication SET co_author = 'done' WHERE pub_id = ?",
                         (pub_id,))
    return len(found), new_authors


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="publications per batch; asks permission between batches")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N publications in total (testing)")
    parser.add_argument("--own-only", action="store_true",
                        help="skip citing papers (update_status = 'no need to update')")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and print, write nothing to the database")
    args = parser.parse_args()

    if not API_KEY:
        sys.exit("OPENALEX_API_KEY_CO_AUTHOR is not set -- check .env")
    if not os.path.exists(DB_PATH):
        sys.exit(f"{DB_PATH} not found")
    conn = get_conn()

    sql = "SELECT pub_id FROM publication WHERE co_author IS NULL"
    if args.own_only:
        sql += " AND update_status != 'no need to update'"
    todo = [r[0] for r in conn.execute(sql + " ORDER BY rowid")]
    if args.limit:
        todo = todo[:args.limit]
    total = len(todo)
    print(f"database: {DB_PATH}")
    print(f"{total} publication(s) without co-authors this run; batches of {args.batch_size}\n")

    stats = {"done": 0, "new_authors": 0, "missing": 0}
    batch_start = 0
    try:
        for start in range(0, total, IDS_PER_REQUEST):
            chunk = todo[start:start + IDS_PER_REQUEST]
            try:
                found = fetch_authorships(chunk)
            except BudgetExhausted as exc:
                print(f"\n!! {exc}\n   re-run after the reset; progress is saved")
                break
            except Exception as exc:
                print(f"[{start}/{total}] request failed ({exc}) -- left NULL, continuing")
                continue

            missing = len(chunk) - len(found)
            if args.dry_run:
                done, new_authors = len(found), sum(len(a) for a in found.values())
            else:
                done, new_authors = save_chunk(conn, found)
            stats["done"] += done
            stats["new_authors"] += new_authors
            stats["missing"] += missing
            index = start + len(chunk)
            print(f"[{index}/{total}] {done} done, {new_authors} new authors, "
                  f"{missing} not returned")
            time.sleep(REQUEST_DELAY_SECONDS)

            if index - batch_start >= args.batch_size and index < total:
                print(f"\n=== batch finished: {index}/{total} publications "
                      f"({stats['done']} done, {stats['new_authors']} new authors) ===")
                try:
                    answer = input(f"Continue with the next {args.batch_size}? [y/N] ")
                except EOFError:
                    answer = "n"
                if answer.strip().lower() not in ("y", "yes"):
                    print("stopping; re-run to resume")
                    break
                batch_start = index
    except KeyboardInterrupt:
        print("\ninterrupted -- finished chunks are already saved")
    finally:
        conn.close()

    print("\n--- summary ---")
    print(f"publications marked done this run: {stats['done']}")
    print(f"not returned by OpenAlex (left NULL): {stats['missing']}")
    print(f"new authors added: {stats['new_authors']}")
    if args.dry_run:
        print("[dry run] nothing written to the database")


if __name__ == "__main__":
    main()
