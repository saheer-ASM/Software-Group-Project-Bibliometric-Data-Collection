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


def load_existing_author_contributions(cur):
    """Load all existing author-publication links to avoid duplicates"""
    cur.execute("SELECT pub_id, author_id FROM author_contribution_weight")
    return {(r[0], r[1]) for r in cur.fetchall()}


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
    return cur.fetchall()


# ---------------- ABSTRACT CLEANER ----------------
def rebuild_abstract(inv_index):
    if not inv_index or not isinstance(inv_index, dict):
        return None

    words = {}
    for word, positions in inv_index.items():
        for p in positions:
            words[p] = word

    return " ".join(words[i] for i in sorted(words.keys()))


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
        print(f"[NEW AUTHOR] {name} ({author_id})")
        return author_id
    else:
        # Author already exists, still return the ID
        return author_id


# ---------------- INSERT AUTHOR CONTRIBUTION ----------------
def insert_author_contribution(cur, contribution_cache, pub_id, author_id):
    """
    Link an author to a publication in the author_contribution_weight table
    """
    if not pub_id or not author_id:
        return False
    
    pair = (pub_id, author_id)
    if pair in contribution_cache:
        return False

    cur.execute("""
        INSERT INTO author_contribution_weight (pub_id, author_id)
        VALUES (%s, %s)
        ON CONFLICT (pub_id, author_id) DO NOTHING
    """, (pub_id, author_id))

    contribution_cache.add(pair)
    print(f"[CONTRIBUTION] {pub_id} → {author_id}")
    return True


# ---------------- MAIN PIPELINE ----------------
def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 60)
    print("AUTHOR DISCOVERY PIPELINE (From Publications)")
    print("=" * 60)

    # Load existing data into caches
    print("\nLoading existing data...")
    author_cache = load_existing_authors(cur)
    pub_cache = load_existing_publications(cur)
    contribution_cache = load_existing_author_contributions(cur)

    print(f"Authors in DB: {len(author_cache)}")
    print(f"Publications in DB: {len(pub_cache)}")
    print(f"Contributions already stored: {len(contribution_cache)}")

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
    print("-" * 60)

    # Track statistics
    new_authors_count = 0
    contributions_added_count = 0
    skipped_publications = 0
    publications_with_no_authors = 0

    # Process each publication that needs authors
    for idx, (pub_id,) in enumerate(publications, 1):
        print(f"\n[{idx}/{len(publications)}] 📄 Processing publication: {pub_id}")

        # Fetch full work details from OpenAlex
        work = fetch_work_details(pub_id)
        
        if not work:
            print(f"  ⚠️  Skipping {pub_id} - couldn't fetch data")
            skipped_publications += 1
            continue

        # Get authorships
        authorships = work.get("authorships", [])
        
        if not authorships:
            print(f"  ℹ️  No authors found for {pub_id}")
            publications_with_no_authors += 1
            continue

        print(f"  Found {len(authorships)} author(s)")

        authors_added_for_this_pub = 0
        
        # Process each author
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue

            author_obj = authorship.get("author")
            if not author_obj or not isinstance(author_obj, dict):
                continue

            # Insert author if new
            author_id = insert_author(cur, author_cache, author_obj)
            
            if author_id:
                # Insert contribution link
                added = insert_author_contribution(cur, contribution_cache, pub_id, author_id)
                if added:
                    contributions_added_count += 1
                    authors_added_for_this_pub += 1

        print(f"  ✅ Added {authors_added_for_this_pub} author contributions for {pub_id}")

        # Commit every 10 publications to avoid large transactions
        if idx % 10 == 0:
            conn.commit()
            print(f"  💾 Checkpoint saved")

        # Be nice to OpenAlex API (rate limiting)
        time.sleep(0.5)

    # Final commit
    conn.commit()
    
    # Print summary
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETED")
    print("=" * 60)
    print(f"📊 Publications processed: {len(publications)}")
    print(f"📊 Publications with no authors: {publications_with_no_authors}")
    print(f"⏭️  Skipped publications (API errors): {skipped_publications}")
    print(f"👤 New authors added: {new_authors_count}")
    print(f"🔗 New contributions added: {contributions_added_count}")
    print(f"📚 Total authors now: {len(author_cache)}")
    print(f"📚 Total publications now: {len(pub_cache)}")
    print(f"🔗 Total contributions now: {len(contribution_cache)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()