"""
Import authors from a CSV file, search OpenAlex for each author, and upsert into the `author` table.

Usage:
  python import_authors_from_csv.py --csv authors.csv --delay 1

CSV format:
- A header row with a column named `name` or `author` is preferred.
- If no header, the first column will be used as the author name.

Requirements:
- requests
- python-dotenv
- psycopg2

The script reads DB credentials from the `.env` file in the same folder (`scripts_db/.env`).
"""

import os
import csv
import time
import argparse
import requests
import psycopg2
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load .env from this folder (scripts_db)
load_dotenv()

OPENALEX_SEARCH_URL = "https://api.openalex.org/authors"


def get_openalex_author(name, timeout=10):
    """Search OpenAlex for an author by name and return the first match dict or None."""
    params = {
        'search': name,
        'per_page': 1
    }
    headers = {
        'User-Agent': 'SoftwareProject/1.0 (mailto:you@example.com)'
    }
    try:
        r = requests.get(OPENALEX_SEARCH_URL, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        results = data.get('results') or data.get('data') or []
        if results:
            # OpenAlex returns 'results' for search endpoints
            return results[0]
        return None
    except Exception as e:
        print(f"Error querying OpenAlex for '{name}': {e}")
        return None


def upsert_author(cur, author_id, author_name):
    sql = """
    INSERT INTO author (author_id, author_name)
    VALUES (%s, %s)
    ON CONFLICT (author_id) DO UPDATE
      SET author_name = EXCLUDED.author_name;
    """
    cur.execute(sql, (author_id, author_name))


def main():
    csv_path = "authors.csv"    # Your specific file name
    delay = 1.0
    limit = 0

    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return

    # Connect to DB using env vars
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT') or 5432),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            sslmode='require'
        )
        cur = conn.cursor()
        print('✓ Connected to database')
    except Exception as e:
        print(f"✗ Could not connect to DB: {e}")
        return

    processed = 0
    skipped = 0

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Peek header
        try:
            header = next(reader)
            has_header = any(h.lower() in ('name', 'author') for h in header)
            if has_header:
                # Use DictReader for convenience
                f.seek(0)
                dreader = csv.DictReader(f)
                rows = dreader
            else:
                # First row was data; treat first column as name
                f.seek(0)
                rows = (row for row in csv.reader(f))
        except StopIteration:
            print('CSV is empty')
            return

        for row in rows:
            if isinstance(row, dict):
                name = row.get('name') or row.get('author') or next(iter(row.values()))
            else:
                # row is a list
                name = row[0] if row else ''

            if not name or name.strip() == '':
                skipped += 1
                continue

            name = name.strip()
            print(f"Searching OpenAlex for: {name}")
            result = get_openalex_author(name)
            if not result:
                print(f"  No result for: {name}")
                skipped += 1
            else:
                openalex_id = result.get('id').split('/')[-1] # e.g., 'https://openalex.org/A12345' get only A12345
                
                display_name = result.get('display_name') or name
                print(f"  Found: {display_name} -> {openalex_id}")
                try:
                    upsert_author(cur, openalex_id, display_name)
                    conn.commit()
                    processed += 1
                except Exception as e:
                    print(f"  DB error for {openalex_id}: {e}")

            if limit and processed >= limit:
                print('Reached processing limit')
                break

            time.sleep(delay)

    cur.close()
    conn.close()
    print(f"Done. Processed: {processed}, Skipped: {skipped}")


if __name__ == '__main__':
    main()
