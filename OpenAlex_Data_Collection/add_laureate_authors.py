"""Add the authors in Author_extraction/output/laureate_authors.csv to the
'author' table of the LOCAL SQLite database (database/openalex.db), after
cross-checking each one on OpenAlex.

For every laureate name:
  1. Look the author up on OpenAlex by openalex_id when the CSV row has one,
     otherwise (or if the id isn't found) by display name.
  2. Not found on OpenAlex         -> skipped and reported.
  3. author_id NOT in the table    -> new row inserted with
                                      pub_finished = "need to update".
  4. author_id already in the table:
       pub_finished == "done"      -> nothing to do ("no need to update").
       anything else               -> pub_finished set to "need to update".

Authors whose pub_finished is not "done" are the ones the publication
collection scripts still have to process.

--csv reads another author list instead (needs a display_name / author_name /
name column, or an openalex_id / author_id column). Each CSV gets its own
lookup checkpoint in cache/.

--replace makes this CSV the ONLY target cohort: every other 'done' author is
set to 'no need' (rows and their publications are kept, nothing is deleted),
so the --cohort done calculations only pick up the authors of this CSV.

Usage:
    python add_laureate_authors.py            # full run
    python add_laureate_authors.py --limit 5  # test on 5 authors
    python add_laureate_authors.py --dry-run  # search + report, write nothing
    python add_laureate_authors.py --csv ../Author_extraction/output/staff_merged.csv --replace
"""

import argparse
import csv
import json
import os
import sys
import time

import requests

# Reuses the OpenAlex search and id helper / env config.
import fill_sheet_from_general_authors as base

sys.path.insert(0, os.path.join(base.HERE, "database"))
from db import DB_PATH, get_conn                        # noqa: E402

HERE = base.HERE
INPUT_CSV = os.path.normpath(
    os.path.join(HERE, "..", "Author_extraction", "output", "laureate_authors.csv"))
CHECKPOINT = os.path.join(base.CACHE_DIR, "laureate_fill_checkpoint.jsonl")

NEEDS_UPDATE = "need to update"
DONE = "done"
NO_NEED = "no need"      # same value collect_co_authors.py uses for non-target authors
NAME_COLUMNS = ("display_name", "author_name", "name")
ID_COLUMNS = ("openalex_id", "author_id")


def checkpoint_path(input_csv):
    """The laureate CSV keeps its old checkpoint; any other CSV gets its own."""
    if os.path.normcase(os.path.abspath(input_csv)) == os.path.normcase(INPUT_CSV):
        return CHECKPOINT
    stem = os.path.splitext(os.path.basename(input_csv))[0]
    return os.path.join(base.CACHE_DIR, f"{stem}_fill_checkpoint.jsonl")


def load_checkpoint(checkpoint):
    done = {}
    if not os.path.exists(checkpoint):
        return done
    with open(checkpoint, encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[record["input_name"]] = record
    return done


def append_checkpoint(checkpoint, record):
    os.makedirs(base.CACHE_DIR, exist_ok=True)
    with open(checkpoint, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_entries(input_csv):
    """[(openalex_id or None, display_name or None)], de-duplicated. A row
    with an openalex_id is looked up by id; otherwise by display name."""
    with open(input_csv, encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        name_col = next((c for c in NAME_COLUMNS if c in fields), None)
        id_col = next((c for c in ID_COLUMNS if c in fields), None)
        if name_col is None and id_col is None:
            sys.exit(f"Need an id column ({', '.join(ID_COLUMNS)}) or a name "
                     f"column ({', '.join(NAME_COLUMNS)}) in {input_csv}; found: {fields}")
        entries = []
        for r in reader:
            oid = base.short_id((r.get(id_col) or "").strip()) if id_col else None
            name = (r.get(name_col) or "").strip() if name_col else None
            if oid or name:
                entries.append((oid or None, name or None))
    return list(dict.fromkeys(entries))


def fetch_author_by_id(openalex_id):
    """GET /authors/{id}; returns the author dict or None."""
    params = {}
    if base.OPENALEX_MAILTO:
        params["mailto"] = base.OPENALEX_MAILTO
    if base.OPENALEX_API_KEY:
        params["api_key"] = base.OPENALEX_API_KEY
    delay = 1.0
    for attempt in range(base.MAX_RETRIES):
        try:
            resp = requests.get(f"{base.OPENALEX_AUTHORS_URL}/{openalex_id}",
                                params=params, timeout=15)
        except requests.RequestException as exc:
            if attempt == base.MAX_RETRIES - 1:
                print(f"    [ERROR] {openalex_id}: {exc}")
                return None
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code != 404:
            print(f"    [ERROR] {openalex_id}: HTTP {resp.status_code}")
        return None
    return None


def load_authors(conn):
    """{author_id: pub_finished} for every author already in the table."""
    return {aid: (pf or "").strip()
            for aid, pf in conn.execute("SELECT author_id, pub_finished FROM author")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--csv", default=INPUT_CSV,
                        help="author list to read (default: laureate_authors.csv)")
    parser.add_argument("--replace", action="store_true",
                        help="set every 'done' author NOT in this CSV to 'no need'")
    args = parser.parse_args()
    input_csv = os.path.abspath(args.csv)
    checkpoint_file = checkpoint_path(input_csv)

    if not os.path.exists(DB_PATH):
        sys.exit(f"Local database not found: {DB_PATH}")
    if not os.path.exists(input_csv):
        sys.exit(f"Input CSV not found: {input_csv}")

    names = read_entries(input_csv)
    if args.limit:
        names = names[:args.limit]
    print(f"{len(names)} author(s) from {input_csv}")

    conn = get_conn()
    sheet = load_authors(conn)
    print(f"{len(sheet)} authors already in {DB_PATH}")
    checkpoint = load_checkpoint(checkpoint_file)

    to_append = []      # (author_id, author_name, pub_finished) new rows
    to_flag = []        # author_ids of existing rows to set to 'need to update'
    new = already_done = flagged = not_found = duplicates = 0
    seen_ids = set()

    for index, (oid, dname) in enumerate(names, start=1):
        name = oid or dname           # checkpoint key
        record = checkpoint.get(name)
        if record is None:
            print(f"[{index}/{len(names)}] looking up: {name}")
            match = fetch_author_by_id(oid) if oid else None
            if match is None and dname:   # no id, or id not found -> by name
                match = base.search_author(dname)
            record = {
                "input_name": name,
                "found": match is not None,
                "author_id": base.short_id(match["id"]) if match else None,
                "author_name": match.get("display_name") if match else None,
            }
            if match:
                print(f"    -> {record['author_id']}  {record['author_name']}  "
                      f"(works: {match.get('works_count')})")
            if not args.dry_run:
                append_checkpoint(checkpoint_file, record)
            time.sleep(base.REQUEST_DELAY_SECONDS)

        if not record["found"]:
            not_found += 1
            print(f"    [NOT FOUND] {name}")
            continue

        author_id = record["author_id"]
        if author_id in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(author_id)

        if author_id not in sheet:
            to_append.append((author_id, record["author_name"], NEEDS_UPDATE))
            new += 1
        elif sheet[author_id].lower() == DONE:
            already_done += 1          # in table, publications up to date
        else:
            if sheet[author_id] != NEEDS_UPDATE:
                to_flag.append(author_id)
            flagged += 1

    print("\n--- summary ---")
    print(f"names checked:                 {len(names)}")
    print(f"not found on OpenAlex:         {not_found}")
    print(f"duplicate of earlier row:      {duplicates}")
    print(f"new authors (need to update):  {new}")
    print(f"in table, publications done:   {already_done}")
    print(f"in table, need to update:      {flagged}  ({len(to_flag)} rows changed)")
    assert len(names) == not_found + duplicates + new + already_done + flagged

    # --replace: the old cohort leaves the 'done' set (rows and papers are kept)
    to_demote = []
    if args.replace:
        to_demote = [aid for aid, pf in sheet.items()
                     if pf.lower() == DONE and aid not in seen_ids]
        print(f"old 'done' authors -> '{NO_NEED}': {len(to_demote)}  (--replace)")

    if args.dry_run:
        print("\n[dry run] nothing written to the database or checkpoint")
        return

    with conn:   # one transaction: all-or-nothing
        conn.executemany("UPDATE author SET pub_finished = ? WHERE author_id = ?",
                         [(NO_NEED, aid) for aid in to_demote])
        conn.executemany("UPDATE author SET pub_finished = ? WHERE author_id = ?",
                         [(NEEDS_UPDATE, aid) for aid in to_flag])
        conn.executemany("INSERT OR IGNORE INTO author "
                         "(author_id, author_name, pub_finished) VALUES (?, ?, ?)",
                         to_append)
    print(f"  set {len(to_demote)} old row(s) to '{NO_NEED}', "
          f"{len(to_flag)} existing row(s) to '{NEEDS_UPDATE}', "
          f"inserted {len(to_append)} new row(s)")
    conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
