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
def load_existing_publications(cur):
    """Load all publication IDs that already exist in the database"""
    cur.execute("SELECT pub_id FROM publication")
    return set(r[0] for r in cur.fetchall())


# ---------------- ABSTRACT CLEANER ----------------
def rebuild_abstract(inv_index):
    """Convert OpenAlex's abstract_inverted_index back to readable text"""
    if not inv_index or not isinstance(inv_index, dict):
        return None

    words = {}
    for word, positions in inv_index.items():
        for p in positions:
            words[p] = word

    return " ".join(words[i] for i in sorted(words.keys()))


# ---------------- FETCH WORKS BY AUTHOR ----------------
def fetch_works_by_author(author_id):
    """Fetch all works for a specific author from OpenAlex"""
    try:
        params = {
            "filter": f"author.id:{author_id}",
            "per_page": 200
        }
        r = requests.get(OPENALEX_WORKS, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"[ERROR] OpenAlex fetch failed for author {author_id}: {e}")
        return []


# ---------------- INSERT OR UPDATE PUBLICATION ----------------
def insert_or_update_publication(cur, pub_cache, pub_id, title, abstract, year, total_citation):
    """
    Insert a publication if it doesn't exist, or update it if it does
    Returns True if inserted/updated, False if failed
    """
    if pub_id in pub_cache:
        # Publication exists - update it
        cur.execute("""
            UPDATE publication 
            SET pub_title = %s, 
                abstract = %s, 
                year = %s, 
                total_citation = %s
            WHERE pub_id = %s
        """, (title, abstract, year, total_citation, pub_id))
        return True
    else:
        # Publication doesn't exist - insert it
        cur.execute("""
            INSERT INTO publication (pub_id, pub_title, abstract, year, total_citation)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (pub_id) DO NOTHING
        """, (pub_id, title, abstract, year, total_citation))
        
        pub_cache.add(pub_id)
        return True


# ---------------- MAIN PIPELINE ----------------
def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 60)
    print("AUTHOR-BASED PUBLICATION FETCHER")
    print("(Updates/Inserts Publications from Authors)")
    print("=" * 60)

    # Load existing publications cache
    print("\nLoading existing publications...")
    pub_cache = load_existing_publications(cur)
    print(f"Publications in DB: {len(pub_cache)}")

    # Get ALL authors from the author table
    cur.execute("SELECT author_id FROM author ORDER BY author_id")
    authors = cur.fetchall()
    
    print(f"\nProcessing {len(authors)} authors...")
    print("-" * 60)

    # Track statistics
    new_publications_count = 0
    updated_publications_count = 0
    total_works_found = 0
    authors_with_no_works = 0
    skipped_authors = 0

    for idx, (author_id,) in enumerate(authors, 1):
        print(f"\n[{idx}/{len(authors)}] 🔍 Processing author: {author_id}")

        # Fetch works for this author
        works = fetch_works_by_author(author_id)
        
        if not works:
            print(f"  ℹ️  No works found for author {author_id}")
            authors_with_no_works += 1
            continue

        print(f"  Found {len(works)} works")
        total_works_found += len(works)

        # Track for this author
        author_new = 0
        author_updated = 0

        # Process each work
        for w in works:
            pub_id = (w.get("id") or "").split("/")[-1]
            if not pub_id:
                continue

            title = w.get("display_name")
            year = w.get("publication_year")
            abstract = rebuild_abstract(w.get("abstract_inverted_index"))
            total_citation = w.get("cited_by_count", 0)

            # Check if publication exists
            if pub_id in pub_cache:
                # Update existing publication
                cur.execute("""
                    UPDATE publication 
                    SET pub_title = %s, 
                        abstract = %s, 
                        year = %s, 
                        total_citation = %s
                    WHERE pub_id = %s
                """, (title, abstract, year, total_citation, pub_id))
                author_updated += 1
            else:
                # Insert new publication
                cur.execute("""
                    INSERT INTO publication (pub_id, pub_title, abstract, year, total_citation)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (pub_id) DO NOTHING
                """, (pub_id, title, abstract, year, total_citation))
                pub_cache.add(pub_id)
                author_new += 1

        new_publications_count += author_new
        updated_publications_count += author_updated
        print(f"  ✅ New: {author_new}, Updated: {author_updated}")

        # Commit every 5 authors
        if idx % 5 == 0:
            conn.commit()
            print(f"  💾 Checkpoint saved ({idx} authors processed)")

        # Rate limiting
        time.sleep(1)

    # Final commit
    conn.commit()
    cur.close()
    conn.close()
    
    # Print summary
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETED")
    print("=" * 60)
    print(f"👤 Authors processed: {len(authors)}")
    print(f"📊 Authors with works: {len(authors) - authors_with_no_works}")
    print(f"📊 Authors with no works: {authors_with_no_works}")
    print(f"📚 Total works found: {total_works_found}")
    print(f"📚 New publications added: {new_publications_count}")
    print(f"📚 Existing publications updated: {updated_publications_count}")
    print(f"📚 Total publications now: {len(pub_cache)}")


if __name__ == "__main__":
    main()