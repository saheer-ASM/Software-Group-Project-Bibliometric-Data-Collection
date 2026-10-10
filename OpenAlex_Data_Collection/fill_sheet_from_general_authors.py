"""Fill a Google Sheet tab with (author_id, author_name) for the 917 authors
in Author_extraction/output/general_authors.csv -- the same lookup method as
scripts_db/import_authors_from_csv.py (search OpenAlex by name), but writing
to a shared Google Sheet instead of PostgreSQL, and reading names from the
new extraction's CSV instead of the old authors.csv.

Only the general_authors.csv authors are touched. Nothing already in the old
PostgreSQL database, and nothing already in any other tab of the sheet, is
read or overwritten.

Usage:
    python fill_sheet_from_general_authors.py           # full run
    python fill_sheet_from_general_authors.py --limit 5  # test on 5 authors first
    python fill_sheet_from_general_authors.py --dry-run  # search OpenAlex, print
                                                          # results, write nothing
                                                          # to the sheet or checkpoint

Resumable: every (input name -> OpenAlex result) lookup is checkpointed to
cache/sheet_fill_checkpoint.jsonl as it happens, so an interrupted run can
simply be re-run -- already-looked-up names are not re-searched, and rows
already confirmed present in the sheet are not re-appended.

Requires: service_account.json (a Google service-account key) in this folder,
and that service account's email added as an Editor on the target sheet.
"""

import argparse
import csv
import json
import os
import sys
import time

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

# Windows' default console codepage (cp1252) can't print every Unicode name
# OpenAlex returns (Cyrillic, CJK, accented Latin, ...); fall back to
# replacing the unprintable character rather than crashing mid-run.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.normpath(
    os.path.join(HERE, "..", "Author_extraction", "output", "general_authors.csv"))
CACHE_DIR = os.path.join(HERE, "cache")
CHECKPOINT = os.path.join(CACHE_DIR, "sheet_fill_checkpoint.jsonl")

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
TAB_NAME = os.getenv("GOOGLE_SHEET_TAB", "general_authors")
SERVICE_ACCOUNT_FILE = os.path.join(
    HERE, os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"))

OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
OPENALEX_AUTHORS_URL = "https://api.openalex.org/authors"

REQUEST_DELAY_SECONDS = 0.5
MAX_RETRIES = 4
SHEET_BATCH_SIZE = 200   # rows per batched Sheets write

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ------------------------------------------------------------------ OpenAlex
def search_author(name):
    """GET /authors?search=name&per_page=1 -- same method as
    scripts_db/import_authors_from_csv.py. Returns the first match dict or
    None. Retries on 429/5xx; gives up (returns None) after MAX_RETRIES."""
    params = {"search": name, "per_page": 1}
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY

    delay = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(OPENALEX_AUTHORS_URL, params=params, timeout=15)
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                print(f"    [ERROR] {name!r}: {exc}")
                return None
            time.sleep(delay)
            delay *= 2
            continue

        if resp.status_code == 200:
            results = resp.json().get("results") or []
            return results[0] if results else None
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(delay)
            delay *= 2
            continue
        print(f"    [ERROR] {name!r}: HTTP {resp.status_code} {resp.text[:200]}")
        return None
    return None


def short_id(openalex_url):
    if not openalex_url:
        return None
    return openalex_url.rstrip("/").split("/")[-1]


# ------------------------------------------------------------------ checkpoint
def load_checkpoint():
    """{input_name: {"author_id":..., "author_name":..., "found": bool}}"""
    done = {}
    if not os.path.exists(CHECKPOINT):
        return done
    with open(CHECKPOINT, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[record["input_name"]] = record
    return done


def append_checkpoint(record):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CHECKPOINT, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ Google Sheet
def open_worksheet():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    try:
        worksheet = spreadsheet.worksheet(TAB_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=TAB_NAME, rows=1000, cols=2)
    return worksheet


def existing_author_ids(worksheet):
    """author_id values already present in the sheet, so a re-run never
    appends the same author twice."""
    values = worksheet.get_all_values()
    if not values:
        return set(), False
    header_present = values[0][:2] == ["author_id", "author_name"]
    body = values[1:] if header_present else values
    return {row[0] for row in body if row and row[0]}, header_present


# ------------------------------------------------------------------ main
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N authors (for a test run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="search OpenAlex and print results; write nothing "
                             "to the sheet or the checkpoint")
    args = parser.parse_args()

    if not SHEET_ID:
        sys.exit("GOOGLE_SHEET_ID is not set -- copy .env.example to .env and fill it in")
    if not args.dry_run and not os.path.exists(SERVICE_ACCOUNT_FILE):
        sys.exit(f"Service account key not found: {SERVICE_ACCOUNT_FILE}\n"
                 f"Download it from Google Cloud and save it at that path "
                 f"(see .env.example).")
    if not os.path.exists(INPUT_CSV):
        sys.exit(f"Input CSV not found: {INPUT_CSV}")

    with open(INPUT_CSV, encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    names = [r["display_name"].strip() for r in rows if r.get("display_name", "").strip()]
    if args.limit:
        names = names[:args.limit]

    print(f"{len(names)} author name(s) to look up from {INPUT_CSV}")

    checkpoint = load_checkpoint()
    worksheet = None
    sheet_ids = set()
    header_present = False
    if not args.dry_run:
        worksheet = open_worksheet()
        sheet_ids, header_present = existing_author_ids(worksheet)
        if not header_present:
            worksheet.insert_row(["author_id", "author_name"], index=1)

    to_append = []
    found = skipped_cached = not_found = already_in_sheet = 0

    for index, name in enumerate(names, start=1):
        record = checkpoint.get(name)
        if record is None:
            print(f"[{index}/{len(names)}] searching: {name}")
            match = search_author(name)
            record = {
                "input_name": name,
                "found": match is not None,
                "author_id": short_id(match["id"]) if match else None,
                "author_name": match.get("display_name") if match else None,
            }
            if not args.dry_run:
                append_checkpoint(record)
            time.sleep(REQUEST_DELAY_SECONDS)
        else:
            skipped_cached += 1

        if not record["found"]:
            not_found += 1
            print(f"    [NOT FOUND] {name}")
            continue

        found += 1
        if record["author_id"] in sheet_ids:
            already_in_sheet += 1
            continue

        to_append.append([record["author_id"], record["author_name"]])
        sheet_ids.add(record["author_id"])

    print("\n--- summary ---")
    print(f"total names:        {len(names)}")
    print(f"from checkpoint:     {skipped_cached}")
    print(f"found on OpenAlex:   {found}")
    print(f"not found:           {not_found}")
    print(f"already in sheet:    {already_in_sheet}")
    print(f"new rows to write:   {len(to_append)}")

    if args.dry_run:
        print("\n[dry run] nothing written to the sheet or checkpoint")
        return

    for start in range(0, len(to_append), SHEET_BATCH_SIZE):
        batch = to_append[start:start + SHEET_BATCH_SIZE]
        worksheet.append_rows(batch, value_input_option="RAW")
        print(f"  wrote rows {start + 1}-{start + len(batch)} to '{TAB_NAME}'")

    print("Done.")


if __name__ == "__main__":
    main()
