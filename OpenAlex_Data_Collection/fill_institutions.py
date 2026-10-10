"""Fill the institution tables in the LOCAL database (database/openalex.db)
from OpenAlex's `last_known_institutions`, for authors whose publications are
finished (author.pub_finished = 'done') only.

Tables (created if missing):
    institution        (institution_id PK, institution_name, country_code, type)
    author_institution (author_id, institution_id, PK on the pair)

Plus one flag column on `author`:
    author.institution_done  'not done' (default) | 'done'
so an author with no institution on OpenAlex is not fetched again on every run.

Authors are fetched from OpenAlex in batches of up to 50 per request.
Each batch is committed on its own: stop with Ctrl+C and re-run any time.

Usage:
    python fill_institutions.py              # every pub-finished author not yet done
    python fill_institutions.py --limit 100  # only the next 100 authors (testing)
    python fill_institutions.py --dry-run    # fetch and print, write nothing
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))

from db import DB_PATH, get_conn                        # noqa: E402
from fill_publications import (                         # noqa: E402
    BudgetExhausted, OPENALEX_API_KEY, OPENALEX_MAILTO, REQUEST_DELAY_SECONDS,
    _get, short_id,
)

OPENALEX_AUTHORS_URL = "https://api.openalex.org/authors"
BATCH_SIZE = 50          # OpenAlex allows up to 50 ids per OR filter

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS institution (
    institution_id   TEXT PRIMARY KEY,
    institution_name TEXT,
    country_code     TEXT,
    type             TEXT
);
CREATE TABLE IF NOT EXISTS author_institution (
    author_id      TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    PRIMARY KEY (author_id, institution_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_author_institution_inst
    ON author_institution(institution_id);
"""


def fetch_authors(author_ids):
    """{author_id: [institution dicts]} for the authors OpenAlex returned."""
    params = {
        "filter": "openalex:" + "|".join(author_ids),
        "per_page": BATCH_SIZE,
        "select": "id,last_known_institutions",
    }
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    page = _get(OPENALEX_AUTHORS_URL, params)
    return {short_id(a["id"]): a.get("last_known_institutions") or []
            for a in page.get("results", [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the next N authors (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and print, write nothing to the database")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit(f"Local database not found: {DB_PATH}")
    conn = get_conn()

    if not args.dry_run:
        conn.executescript(TABLES_SQL)
        columns = [r[1] for r in conn.execute("PRAGMA table_info(author)")]
        if "institution_done" not in columns:
            # DEFAULT is applied instantly to every existing row (no rewrite).
            conn.execute("ALTER TABLE author ADD COLUMN institution_done "
                         "TEXT DEFAULT 'not done'")
            conn.commit()
            print("Added column author.institution_done (default 'not done')")

    columns = [r[1] for r in conn.execute("PRAGMA table_info(author)")]
    pending_sql = "SELECT author_id FROM author WHERE pub_finished = 'done'"
    if "institution_done" in columns:
        pending_sql += " AND COALESCE(institution_done, 'not done') != 'done'"
    pending = [r[0] for r in conn.execute(pending_sql + " ORDER BY rowid")]
    total_done_authors = conn.execute(
        "SELECT COUNT(*) FROM author WHERE pub_finished = 'done'").fetchone()[0]
    if args.limit:
        pending = pending[:args.limit]
    print(f"{total_done_authors:,} authors have pub_finished = 'done'; "
          f"{len(pending):,} to process in this run\n")

    processed = missing = links = 0
    new_institutions = set()
    try:
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            found = fetch_authors(batch)
            time.sleep(REQUEST_DELAY_SECONDS)

            inst_rows, link_rows, done_ids = {}, [], []
            for author_id in batch:
                if author_id not in found:
                    missing += 1                  # leave 'not done', retry next run
                    continue
                done_ids.append(author_id)
                for inst in found[author_id]:
                    inst_id = short_id(inst.get("id"))
                    if not inst_id:
                        continue
                    inst_rows[inst_id] = (inst_id, inst.get("display_name"),
                                          inst.get("country_code"), inst.get("type"))
                    link_rows.append((author_id, inst_id))

            if args.dry_run:
                for author_id in done_ids[:5]:
                    names = [r[1] for (a, i), r in
                             ((l, inst_rows[l[1]]) for l in link_rows) if a == author_id]
                    print(f"  {author_id}: {names or '(no institution)'}")
            else:
                with conn:
                    conn.executemany(
                        "INSERT INTO institution (institution_id, institution_name, "
                        "country_code, type) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(institution_id) DO UPDATE SET "
                        "institution_name = excluded.institution_name, "
                        "country_code = excluded.country_code, type = excluded.type",
                        list(inst_rows.values()))
                    conn.executemany(
                        "INSERT OR IGNORE INTO author_institution "
                        "(author_id, institution_id) VALUES (?, ?)", link_rows)
                    conn.executemany(
                        "UPDATE author SET institution_done = 'done' WHERE author_id = ?",
                        [(a,) for a in done_ids])

            processed += len(done_ids)
            links += len(link_rows)
            new_institutions.update(inst_rows)
            print(f"  authors done: {processed:,} / {len(pending):,} "
                  f"| links: {links:,} | institutions seen: {len(new_institutions):,}"
                  + ("  [dry run]" if args.dry_run else ""), flush=True)
    except BudgetExhausted as exc:
        print(f"\nSTOPPED: {exc}\nRe-run later; finished batches are already saved.")

    print("\n--- summary ---")
    print(f"authors processed:          {processed:,}")
    print(f"not returned by OpenAlex:   {missing:,}  (left 'not done')")
    print(f"author-institution links:   {links:,}")
    print(f"distinct institutions seen: {len(new_institutions):,}")
    if args.dry_run:
        print("[dry run] nothing written to the database")
    conn.close()


if __name__ == "__main__":
    main()
