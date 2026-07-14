import os
import time
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

OPENALEX_WORKS = "https://api.openalex.org/works"


# ---------------- DB CONNECTION ----------------
def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT") or 5432),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )


# ---------------- CACHE ----------------
def load_existing_authors(cur):
    """Load all existing author IDs from database"""
    cur.execute("SELECT author_id FROM author")
    return set(r[0] for r in cur.fetchall())


def load_existing_publications(cur):
    """Load all existing publication IDs from database"""
    cur.execute("SELECT pub_id FROM publication")
    return set(r[0] for r in cur.fetchall())


def get_publications_without_authors(cur):
    """
    Get only publications that don't have any authors linked yet
    """
    cur.execute("""
        SELECT p.pub_id 
        FROM publication p
        LEFT JOIN author_contribution_weight acw ON p.pub_id = acw.pub_id
        WHERE acw.pub_id IS NULL
        ORDER BY p.pub_id
    """)
    return [r[0] for r in cur.fetchall()]


# ---------------- FETCH WORK DETAILS ----------------
def fetch_work_details(work_id):
    """
    Fetch a specific publication's details from OpenAlex API
    Returns the full work object with author information
    """
    try:
        url = f"{OPENALEX_WORKS}/{work_id}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] OpenAlex fetch failed for {work_id}: {e}")
        return None


# ---------------- INSERT AUTHOR ----------------
def insert_author(cur, author_cache, author_obj):
    """
    Insert a new author into the database if they don't already exist
    Returns the author_id if successful, None otherwise
    """
    if not isinstance(author_obj, dict):
        return None

    author_id_full = author_obj.get("id")
    if not author_id_full:
        return None

    author_id = author_id_full.split("/")[-1]
    name = author_obj.get("display_name") or "Unknown"

    if author_id not in author_cache:
        cur.execute("""
            INSERT INTO author (author_id, author_name)
            VALUES (%s, %s)
            ON CONFLICT (author_id) DO NOTHING
        """, (author_id, name))
        
        author_cache.add(author_id)
        print(f"    [NEW AUTHOR] {name} ({author_id})")
        return author_id
    else:
        # Author already exists, still return the ID
        return author_id


# ---------------- INSERT AUTHOR CONTRIBUTION FOR MULTIPLE AUTHORS ----------------
def insert_author_contributions(cur, pub_id, authors_data):
    """
    Insert all authors for a publication in ONE row
    
    Args:
        pub_id: Publication ID
        authors_data: List of tuples [(author_id, author_name), ...]
    
    Returns:
        True if successful, False otherwise
    """
    if not pub_id or not authors_data:
        return False

    # Prepare author IDs (up to 10)
    author1Id = authors_data[0][0] if len(authors_data) > 0 else None
    author2Id = authors_data[1][0] if len(authors_data) > 1 else None
    author3Id = authors_data[2][0] if len(authors_data) > 2 else None
    author4Id = authors_data[3][0] if len(authors_data) > 3 else None
    author5Id = authors_data[4][0] if len(authors_data) > 4 else None
    author6Id = authors_data[5][0] if len(authors_data) > 5 else None
    author7Id = authors_data[6][0] if len(authors_data) > 6 else None
    author8Id = authors_data[7][0] if len(authors_data) > 7 else None
    author9Id = authors_data[8][0] if len(authors_data) > 8 else None
    author10Id = authors_data[9][0] if len(authors_data) > 9 else None

    # Create author_ordering_nome (comma-separated author names)
    author_names = [name for _, name in authors_data[:10]]
    author_ordering_nome = ", ".join(author_names)

    # Insert the row
    sql = """
    INSERT INTO author_contribution_weight 
    (pub_id, author1Id, author2Id, author3Id, author4Id, author5Id, author6Id, author7Id, author8Id, author9Id, author10Id, author_ordering_nome)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (pub_id) DO UPDATE SET
        author1Id = EXCLUDED.author1Id,
        author2Id = EXCLUDED.author2Id,
        author3Id = EXCLUDED.author3Id,
        author4Id = EXCLUDED.author4Id,
        author5Id = EXCLUDED.author5Id,
        author6Id = EXCLUDED.author6Id,
        author7Id = EXCLUDED.author7Id,
        author8Id = EXCLUDED.author8Id,
        author9Id = EXCLUDED.author9Id,
        author10Id = EXCLUDED.author10Id,
        author_ordering_nome = EXCLUDED.author_ordering_nome
    """

    cur.execute(sql, (
        pub_id,
        author1Id, author2Id, author3Id, author4Id, author5Id, author6Id, author7Id, author8Id, author9Id, author10Id,
        author_ordering_nome
    ))

    print(f"    ✅ Inserted {len(authors_data)} author(s) for publication {pub_id}")
    print(f"       Authors: {author_ordering_nome}")
    return True


# ---------------- MAIN PIPELINE ----------------
def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 70)
    print("AUTHOR DISCOVERY PIPELINE (From OpenAlex Publications)")
    print("=" * 70)

    # Load existing data into caches
    print("\nLoading existing data...")
    author_cache = load_existing_authors(cur)
    pub_cache = load_existing_publications(cur)

    print(f"Authors in DB: {len(author_cache)}")
    print(f"Publications in DB: {len(pub_cache)}")

    # Get ONLY publications that don't have authors linked yet
    publications = get_publications_without_authors(cur)
    
    if not publications:
        print("\n✅ All publications already have authors linked!")
        print("   No processing needed.")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(publications)} publication(s) without authors")
    print("Processing only these publications...")
    print("-" * 70)

    # Track statistics
    new_authors_count = 0
    publications_processed = 0
    skipped_publications = 0
    publications_with_no_authors = 0

    # Process each publication that needs authors
    for idx, pub_id in enumerate(publications, 1):
        print(f"\n[{idx}/{len(publications)}] 📄 Publication: {pub_id}")

        # Fetch full work details from OpenAlex
        work = fetch_work_details(pub_id)
        
        if not work:
            print(f"  ⚠️  Skipping - couldn't fetch data from OpenAlex")
            skipped_publications += 1
            continue

        # Get authorships
        authorships = work.get("authorships", [])
        
        if not authorships:
            print(f"  ℹ️  No authors found for this publication")
            publications_with_no_authors += 1
            continue

        print(f"  Found {len(authorships)} author(s)")

        # Collect all authors for this publication
        authors_data = []  # List of (author_id, author_name) tuples
        
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue

            author_obj = authorship.get("author")
            if not author_obj or not isinstance(author_obj, dict):
                continue

            # Insert author into author table if new
            author_id = insert_author(cur, author_cache, author_obj)
            
            if author_id:
                author_name = author_obj.get("display_name", "Unknown")
                authors_data.append((author_id, author_name))
                new_authors_count += 1

        # Insert all authors for this publication in ONE row
        if authors_data:
            added = insert_author_contributions(cur, pub_id, authors_data)
            if added:
                publications_processed += 1

        # Commit every 10 publications to avoid large transactions
        if idx % 10 == 0:
            conn.commit()
            print(f"  💾 Checkpoint saved")

        # Be nice to OpenAlex API (rate limiting)
        time.sleep(0.5)

    # Final commit
    conn.commit()
    
    # Print summary
    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETED")
    print("=" * 70)
    print(f"📊 Publications processed successfully: {publications_processed}")
    print(f"📊 Publications with no authors: {publications_with_no_authors}")
    print(f"⏭️  Skipped publications (API errors): {skipped_publications}")
    print(f"👤 New authors added: {new_authors_count}")
    print(f"📚 Total authors now: {len(author_cache)}")
    print(f"📚 Total publications now: {len(pub_cache)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()