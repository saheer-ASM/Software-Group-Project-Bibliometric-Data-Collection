"""One-off cleanup: fix_sheet_from_general_authors.py's name-search can match
the wrong OpenAlex author for a common name. This script finds every row in
the `author` tab whose author_id disagrees with the one Author_extraction
already verified (general_authors.csv), and fixes it:

    for each mismatched row:
        if pub_finished == "done":
            fetch the WRONG id's work list      (to know what to remove)
            fetch the CORRECT id's work list     (to know what to keep)
            remove any publication row that's only valid under the wrong id
            clear pub_finished so it gets reprocessed under the right id
        correct the author_id in place

Nothing is touched for rows that already have the right id.

Usage:
    python fix_author_id_mismatches.py --dry-run   # report only, change nothing
    python fix_author_id_mismatches.py              # apply the fix
"""

import argparse
import csv
import os
import sys
import time

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.normpath(
    os.path.join(HERE, "..", "Author_extraction", "output", "general_authors.csv"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
AUTHOR_TAB = os.getenv("GOOGLE_SHEET_TAB", "author")
PUBLICATION_TAB = os.getenv("GOOGLE_SHEET_PUBLICATION_TAB", "publication")
SERVICE_ACCOUNT_FILE = os.path.join(
    HERE, os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"))

OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def short_id(url):
    return url.rstrip("/").split("/")[-1] if url else None


class BudgetExhausted(RuntimeError):
    """OpenAlex's daily $ budget for this key is at $0. Retrying is pointless
    until midnight UTC."""


def _is_budget_error(resp):
    try:
        payload = resp.json()
    except ValueError:
        return "insufficient budget" in resp.text.lower()
    if payload.get("dailyRemainingUsd") == 0:
        return True
    return "insufficient budget" in str(payload.get("message", "")).lower()


def fetch_work_ids(author_id):
    """Every work id by this author, cursor-paginated."""
    ids = []
    cursor = "*"
    while cursor:
        params = {
            "filter": f"authorships.author.id:{author_id}",
            "per_page": 200,
            "cursor": cursor,
            "select": "id",
        }
        if OPENALEX_MAILTO:
            params["mailto"] = OPENALEX_MAILTO
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY
        resp = requests.get(OPENALEX_WORKS_URL, params=params, timeout=30)
        if resp.status_code == 429 and _is_budget_error(resp):
            reset_secs = resp.headers.get("X-RateLimit-Reset")
            raise BudgetExhausted(
                f"OpenAlex daily budget exhausted (resets in {reset_secs}s)")
        resp.raise_for_status()
        page = resp.json()
        ids.extend(short_id(w["id"]) for w in page.get("results", []))
        cursor = page.get("meta", {}).get("next_cursor")
        time.sleep(0.2)
    return set(ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    correct = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            correct[r["display_name"].strip()] = r["openalex_id"]

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    ws_author = spreadsheet.worksheet(AUTHOR_TAB)
    ws_pub = spreadsheet.worksheet(PUBLICATION_TAB)

    author_values = ws_author.get_all_values()
    header = author_values[0]
    pub_finished_col = header.index("pub_finished") + 1

    mismatches = []  # (row_number, name, wrong_id, correct_id, was_done)
    for i, row in enumerate(author_values[1:], start=2):
        if len(row) < 2:
            continue
        sheet_id, name = row[0], row[1]
        was_done = len(row) >= pub_finished_col and row[pub_finished_col - 1].strip().lower() == "done"
        correct_id = correct.get(name.strip())
        if correct_id and correct_id != sheet_id:
            mismatches.append((i, name, sheet_id, correct_id, was_done))

    print(f"{len(mismatches)} mismatched row(s) found "
          f"({sum(1 for m in mismatches if m[4])} already marked done)")

    pub_values = ws_pub.get_all_values()
    pub_header = pub_values[0]
    pub_rows = pub_values[1:]
    pub_id_to_rownum = {}
    for i, row in enumerate(pub_rows, start=2):
        if row and row[0]:
            pub_id_to_rownum[row[0]] = i

    rows_to_delete = set()  # publication-tab row numbers
    # Rows safe to correct: any "pending" mismatch (no fetch needed at all),
    # plus any "was done" mismatch we actually finished fetching before a
    # possible budget stop. A "was done" row not yet reached is left
    # completely untouched, so a re-run recomputes and retries it cleanly.
    safe_to_correct = [m for m in mismatches if not m[4]]

    budget_ran_out = False
    for row_number, name, wrong_id, correct_id, was_done in mismatches:
        if not was_done:
            continue
        print(f"\n{name!r}: wrong={wrong_id} correct={correct_id}")
        try:
            print("  fetching wrong id's work list...")
            wrong_works = fetch_work_ids(wrong_id)
            print(f"    {len(wrong_works)} work(s) under the wrong id")
            print("  fetching correct id's work list...")
            correct_works = fetch_work_ids(correct_id)
            print(f"    {len(correct_works)} work(s) under the correct id")
        except BudgetExhausted as exc:
            print(f"\n!! {exc}")
            print("   stopping cleanly -- re-run this script after the reset "
                  "to finish the remaining mismatches")
            budget_ran_out = True
            break

        wrong_only = wrong_works - correct_works
        removed_here = 0
        for pub_id in wrong_only:
            rownum = pub_id_to_rownum.get(pub_id)
            if rownum:
                rows_to_delete.add(rownum)
                removed_here += 1
        print(f"  -> {removed_here} publication row(s) marked for removal "
              f"(the other {len(wrong_works) - removed_here} overlap with the "
              f"correct author or were never added)")
        safe_to_correct.append((row_number, name, wrong_id, correct_id, was_done))

    mismatches = safe_to_correct  # only the ones actually safe to commit
    print(f"\ntotal publication rows to delete: {len(rows_to_delete)}")
    print(f"total author_id corrections to apply: {len(mismatches)}"
          + (" (partial -- budget ran out)" if budget_ran_out else ""))

    if args.dry_run:
        print("\n[dry run] nothing written")
        return

    # Local safety backup BEFORE any destructive write -- belt and suspenders
    # on top of Sheets' own version history, in case anything goes wrong.
    os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)
    backup_path = os.path.join(
        HERE, "cache", f"publication_backup_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    with open(backup_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(pub_header)
        writer.writerows(pub_rows)
    print(f"local backup written: {backup_path} ({len(pub_rows)} rows)")

    # Delete the flagged rows as ONE atomic batchUpdate call (deleteDimension
    # requests, highest row-index first so earlier entries in the same call
    # aren't shifted by later ones) -- never clear()+update(), which is two
    # separate, non-atomic API calls and is what wiped the tab last time when
    # the second call failed after the first had already succeeded.
    if rows_to_delete:
        sheet_gid = ws_pub.id
        requests_list = [
            {"deleteDimension": {"range": {
                "sheetId": sheet_gid, "dimension": "ROWS",
                "startIndex": rownum - 1, "endIndex": rownum}}}
            for rownum in sorted(rows_to_delete, reverse=True)
        ]
        spreadsheet.batch_update({"requests": requests_list})
        print(f"deleted {len(rows_to_delete)} contaminated publication row(s) "
              f"(single atomic call)")
    else:
        print("no publication rows needed removing")

    # Correct the author_id and clear pub_finished for anyone that was done,
    # as ONE batched cell update instead of one update_cell() call each.
    if mismatches:
        batch = []
        for row_number, name, wrong_id, correct_id, was_done in mismatches:
            batch.append({"range": gspread.utils.rowcol_to_a1(row_number, 1),
                         "values": [[correct_id]]})
            if was_done:
                batch.append({"range": gspread.utils.rowcol_to_a1(row_number, pub_finished_col),
                             "values": [[""]]})
        ws_author.batch_update(batch, value_input_option="RAW")
    print(f"corrected {len(mismatches)} author_id value(s) "
          f"and cleared pub_finished on the previously-done ones")


if __name__ == "__main__":
    main()
