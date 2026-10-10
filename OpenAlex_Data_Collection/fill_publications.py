"""Collect every publication of the authors marked 'need to update' in the
LOCAL SQLite database (database/openalex.db).

For every author whose pub_finished = 'need to update'
(e.g. the laureates added by add_laureate_authors.py):
    fetch ALL of their works from OpenAlex (cursor-paginated)
    publication not in the table          -> inserted, update_status = 'need to update'
    publication with 'no need to update'  -> changed to 'need to update'
    publication with 'updated'            -> left as is
    publication already 'need to update'  -> left as is
    (so fill_cited_publications.py later fetches the citing papers of every
    'need to update' one)
    set that author's pub_finished = 'done'

Co-authors ('no need') and finished authors ('done') are never touched.
Resumable: progress is the pub_finished column itself -- each author is
committed on its own, so an interrupted run just continues with the rest.

Usage:
    python fill_publications.py             # all 'need to update' authors
    python fill_publications.py --limit 3   # only the next 3 authors
    python fill_publications.py --dry-run   # fetch and print, write nothing
"""

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))

from db import DB_PATH, get_conn                        # noqa: E402

OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
OPENALEX_WORKS_URL = "https://api.openalex.org/works"

REQUEST_DELAY_SECONDS = 0.2
MAX_RETRIES = 4


# ------------------------------------------------------------------ OpenAlex
def rebuild_abstract(inv_index):
    """Convert OpenAlex's abstract_inverted_index back to readable text."""
    if not inv_index or not isinstance(inv_index, dict):
        return ""
    words = {}
    for word, positions in inv_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words.keys()))


def short_id(openalex_url):
    if not openalex_url:
        return None
    return openalex_url.rstrip("/").split("/")[-1]


class BudgetExhausted(RuntimeError):
    """OpenAlex's daily $ budget for this key is at $0. Retrying is pointless
    until midnight UTC, so this is raised immediately instead of being
    treated as a transient 429."""


def _is_budget_error(resp):
    try:
        payload = resp.json()
    except ValueError:
        return "insufficient budget" in resp.text.lower()
    if payload.get("dailyRemainingUsd") == 0:
        return True
    return "insufficient budget" in str(payload.get("message", "")).lower()


def _get(url, params):
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429 and _is_budget_error(resp):
            reset_secs = resp.headers.get("X-RateLimit-Reset")
            raise BudgetExhausted(
                f"OpenAlex daily budget exhausted for this key "
                f"(resets in {reset_secs}s / midnight UTC)")
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
    raise RuntimeError(f"gave up after {MAX_RETRIES} tries: {url}")


def fetch_all_works(author_id):
    """Every work by this author, cursor-paginated -- no 200-work cutoff."""
    works = []
    cursor = "*"
    while cursor:
        params = {
            "filter": f"authorships.author.id:{author_id}",
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


NEED = "need to update"
NO_NEED = "no need to update"
DONE = "done"


def work_to_row(work):
    return (
        short_id(work.get("id")),
        work.get("title") or "",
        rebuild_abstract(work.get("abstract_inverted_index")),
        work.get("publication_year"),
        work.get("cited_by_count", 0),
        NEED,
    )


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

    authors = conn.execute(
        "SELECT author_id, author_name FROM author WHERE pub_finished = ? ORDER BY rowid",
        (NEED,)).fetchall()
    if args.limit:
        authors = authors[:args.limit]
    print(f"{len(authors)} author(s) with pub_finished = '{NEED}' in {DB_PATH}")

    total_new = total_flipped = failures = 0
    for index, (author_id, author_name) in enumerate(authors, start=1):
        print(f"[{index}/{len(authors)}] {author_name} ({author_id})")
        try:
            works = fetch_all_works(author_id)
        except BudgetExhausted as exc:
            print(f"\nSTOPPED: {exc}\nRe-run later; finished authors are already saved.")
            break
        except Exception as exc:                        # leave author unfinished
            print(f"    [ERROR] {exc}")
            failures += 1
            continue

        rows = [work_to_row(w) for w in works if w.get("id")]
        new = flipped = 0
        if not args.dry_run:
            with conn:   # works + 'done' flag commit together
                before = conn.total_changes
                conn.executemany(
                    "INSERT OR IGNORE INTO publication (pub_id, pub_title, abstract, "
                    "year, total_citation, update_status) VALUES (?, ?, ?, ?, ?, ?)", rows)
                new = conn.total_changes - before
                before = conn.total_changes
                conn.executemany(
                    "UPDATE publication SET update_status = ? "
                    "WHERE pub_id = ? AND update_status = ?",
                    [(NEED, r[0], NO_NEED) for r in rows])
                flipped = conn.total_changes - before
                conn.execute("UPDATE author SET pub_finished = ? WHERE author_id = ?",
                             (DONE, author_id))
        total_new += new
        total_flipped += flipped
        print(f"    {len(works)} works fetched, {new} new, "
              f"{flipped} 'no need to update' -> '{NEED}'")

    print("\n--- summary ---")
    print(f"authors processed:     {len(authors)}")
    print(f"authors failed:        {failures}")
    print(f"new publications:      {total_new}")
    print(f"flipped to '{NEED}': {total_flipped}")
    if args.dry_run:
        print("[dry run] nothing written to the database")
    conn.close()


if __name__ == "__main__":
    main()
