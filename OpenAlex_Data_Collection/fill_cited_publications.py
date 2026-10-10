"""Collect the papers that CITE each publication (one level only) into the local
SQLite database  database/openalex.db  (see database/db.py).

`publication.update_status`:

    need to update      -> its citing papers have not been collected yet
    updated             -> its citing papers are done
    no need to update   -> was added AS a citing paper; never expanded further

For each `need to update` publication, in order:

    fetch ALL papers that cite it from OpenAlex (cursor-paginated, no 200 cap)
    insert citing papers not already in `publication`  (no need to update)
    insert (pub_id, cites_pub_id) into `citation`
    mark the original row `updated`          <- all in ONE transaction

`citation`: pub_id = the cited paper (P1), cites_pub_id = the paper citing it (P2).

Runs in batches (default 5000 publications) and asks permission before the
next batch. Resumable: progress lives in `update_status`.

Usage:
    python fill_cited_publications.py                  # batches of 5000, asks between batches
    python fill_cited_publications.py --batch-size 100
    python fill_cited_publications.py --limit 5 --dry-run   # fetch 5, write nothing
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))

from db import DB_PATH, get_conn                        # noqa: E402
from fill_publications import (                   # noqa: E402
    BudgetExhausted, OPENALEX_API_KEY, OPENALEX_MAILTO, OPENALEX_WORKS_URL,
    REQUEST_DELAY_SECONDS, _get, rebuild_abstract, short_id,
)

NEED = "need to update"
DONE = "updated"
NO_NEED = "no need to update"

DEFAULT_BATCH_SIZE = 5000


# ------------------------------------------------------------------ OpenAlex
def fetch_citing_works(pub_id):
    """Every work that cites pub_id, cursor-paginated -- no 200 cutoff."""
    works = []
    cursor = "*"
    while cursor:
        params = {
            "filter": f"cites:{pub_id}",
            "per_page": 200,
            "cursor": cursor,
            "select": "id,title,abstract_inverted_index,publication_year,cited_by_count",
        }
        if OPENALEX_MAILTO:
            params["mailto"] = OPENALEX_MAILTO
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY
        page = _get(OPENALEX_WORKS_URL, params)
        works.extend(page.get("results", []))
        cursor = page.get("meta", {}).get("next_cursor")
        time.sleep(REQUEST_DELAY_SECONDS)
    return works


def work_to_row(work):
    return (
        short_id(work.get("id")),
        work.get("title") or "",
        rebuild_abstract(work.get("abstract_inverted_index")),
        work.get("publication_year"),
        work.get("cited_by_count", 0),
        NO_NEED,
    )


# ------------------------------------------------------------------ main
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="publications per batch; asks permission between batches")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N publications in total (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and print, write nothing to the database")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit(f"{DB_PATH} not found -- run `python database/create_database.py` first")
    conn = get_conn()

    todo = [r[0] for r in conn.execute(
        "SELECT pub_id FROM publication WHERE update_status = ? ORDER BY rowid", (NEED,))]
    if args.limit:
        todo = todo[:args.limit]
    total = len(todo)
    print(f"database: {DB_PATH}")
    print(f"{total} publication(s) marked '{NEED}' this run; batches of {args.batch_size}\n")

    stats = {"processed": 0, "new_pubs": 0, "new_links": 0, "failed": []}
    batch_start = 0
    try:
        for index, pub_id in enumerate(todo, start=1):
            try:
                citing = fetch_citing_works(pub_id)
            except BudgetExhausted as exc:
                print(f"\n!! {exc}\n   re-run after the reset; progress is saved")
                break
            except Exception as exc:
                print(f"[{index}/{total}] {pub_id} [ERROR] {exc} -- left as '{NEED}'")
                stats["failed"].append(pub_id)
                continue

            new_pubs = new_links = 0
            if not args.dry_run:
                with conn:   # one transaction per publication: all-or-nothing
                    for work in citing:
                        row = work_to_row(work)
                        cid = row[0]
                        if not cid or cid == pub_id:
                            continue
                        new_pubs += conn.execute(
                            "INSERT OR IGNORE INTO publication (pub_id, pub_title, abstract, "
                            "year, total_citation, update_status) VALUES (?,?,?,?,?,?)",
                            row).rowcount
                        new_links += conn.execute(
                            "INSERT OR IGNORE INTO citation VALUES (?,?)",
                            (pub_id, cid)).rowcount
                    conn.execute("UPDATE publication SET update_status = ? WHERE pub_id = ?",
                                 (DONE, pub_id))
            stats["processed"] += 1
            stats["new_pubs"] += new_pubs
            stats["new_links"] += new_links
            print(f"[{index}/{total}] {pub_id}: {len(citing)} citing, "
                  f"{new_pubs} new pubs, {new_links} new links")

            if index - batch_start >= args.batch_size and index < total:
                print(f"\n=== batch finished: {index}/{total} publications done "
                      f"(new pubs {stats['new_pubs']}, new links {stats['new_links']}) ===")
                try:
                    answer = input(f"Continue with the next {args.batch_size}? [y/N] ")
                except EOFError:
                    answer = "n"
                if answer.strip().lower() not in ("y", "yes"):
                    print("stopping; re-run to resume from the next 'need to update' row")
                    break
                batch_start = index
    except KeyboardInterrupt:
        print("\ninterrupted -- finished publications are already saved")
    finally:
        conn.close()

    print("\n--- summary ---")
    print(f"publications processed this run: {stats['processed']}")
    print(f"failed (still '{NEED}'): {len(stats['failed'])}")
    print(f"new publication rows: {stats['new_pubs']}")
    print(f"new citation links:   {stats['new_links']}")
    if args.dry_run:
        print("[dry run] nothing written to the database")


if __name__ == "__main__":
    main()
