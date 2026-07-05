import os
import time
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

OPENALEX_WORKS = "https://api.openalex.org/works"


# ---------------- DB CONNECTION ----------------
def get_conn():
    """Create and return a connection to the PostgreSQL database"""
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
    """
    Load all publication IDs that already exist in the database
    This helps us avoid inserting duplicate publications
    """
    cur.execute("SELECT pub_id FROM publication")
    return set(r[0] for r in cur.fetchall())


def load_existing_citations(cur):
    """
    Load all citation pairs that already exist in the database
    This helps us avoid inserting duplicate citations
    Returns a set of tuples: {(pub_id, cites_pub_id), ...}
    """
    cur.execute("SELECT pub_id, cites_pub_id FROM citation")
    return {(r[0], r[1]) for r in cur.fetchall()}


# ---------------- ABSTRACT CLEANER ----------------
def rebuild_abstract(inv_index):
    """
    Convert OpenAlex's abstract_inverted_index format back to readable text
    Example: {"word": [0, 5], "another": [1]} becomes "word another word"
    """
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
    Returns the full work object containing metadata
    """
    try:
        url = f"{OPENALEX_WORKS}/{work_id}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] OpenAlex fetch failed for {work_id}: {e}")
        return None


# ---------------- FETCH CITING WORKS (INCOMING CITATIONS) ----------------
def fetch_citing_works(work_id):
    """
    Fetch works that cite this publication (incoming citations)
    Uses the /works endpoint with filter: cites:{work_id}
    
    Example: If work_id = W1234567890, this finds all papers that cite W1234567890
    """
    try:
        params = {
            "filter": f"cites:{work_id}",
            "per_page": 200  # Maximum results per page
        }
        r = requests.get(OPENALEX_WORKS, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"[ERROR] Failed to fetch citing works for {work_id}: {e}")
        return []


# ---------------- INSERT OR UPDATE PUBLICATION ----------------
def insert_or_update_publication(cur, pub_cache, pub_id, title, abstract, year, total_citation):
    """
    Insert a publication if it doesn't exist, or update it if it does
    Returns: 
        'inserted' if new publication was added
        'updated' if existing publication was updated
        'skipped' if failed
    """
    if pub_id in pub_cache:
        # ✅ Publication exists - UPDATE it
        cur.execute("""
            UPDATE publication 
            SET pub_title = %s, 
                abstract = %s, 
                year = %s, 
                total_citation = %s
            WHERE pub_id = %s
        """, (title, abstract, year, total_citation, pub_id))
        print(f"  [UPDATED] {pub_id} - citations: {total_citation}")
        return 'updated'
    else:
        # ✅ Publication doesn't exist - INSERT it
        cur.execute("""
            INSERT INTO publication (pub_id, pub_title, abstract, year, total_citation)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (pub_id) DO NOTHING
        """, (pub_id, title, abstract, year, total_citation))
        pub_cache.add(pub_id)
        print(f"  [NEW] {pub_id} - {title[:50] if title else 'No title'}...")
        return 'inserted'


# ---------------- INSERT CITATION ----------------
def insert_citation(cur, citation_cache, pub_id, cites_pub_id):
    """
    Create a citation link between two publications
    pub_id → cites_pub_id means cites_pub_id cites pub_id
    
    Example: insert_citation(cur, cache, 'W123', 'W111') 
    means W111 cites W123
    
    pub_id: The publication being cited (from your table)
    cites_pub_id: The publication that is citing pub_id
    """
    if not pub_id or not cites_pub_id:
        return False
    
    pair = (pub_id, cites_pub_id)
    if pair in citation_cache:
        return False

    try:
        cur.execute("""
            INSERT INTO citation (pub_id, cites_pub_id)
            VALUES (%s, %s)
            ON CONFLICT (pub_id, cites_pub_id) DO NOTHING
        """, (pub_id, cites_pub_id))
        
        citation_cache.add(pair)
        print(f"  [CITATION] {cites_pub_id} → {pub_id}")  # cites_pub_id cites pub_id
        return True
    except psycopg2.ForeignKeyViolation:
        print(f"  ⚠️  Foreign key violation: {cites_pub_id} doesn't exist in publication table")
        return False


# ---------------- CHECK IF PUBLICATION EXISTS ----------------
def publication_exists(cur, pub_id):
    """Check if a publication exists in the database"""
    cur.execute("SELECT 1 FROM publication WHERE pub_id = %s", (pub_id,))
    return cur.fetchone() is not None


# ---------------- MAIN PIPELINE ----------------
def main():
    # 1. Connect to database
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 60)
    print("CITED BY FETCHING PIPELINE (Incoming Citations)")
    print("(With Publication Updates - NO Table Clearing)")
    print("=" * 60)

    # 2. Load existing data into memory caches
    print("\nLoading existing data...")
    pub_cache = load_existing_publications(cur)
    citation_cache = load_existing_citations(cur)
    
    print(f"Publications in DB: {len(pub_cache)}")
    print(f"Citations already stored: {len(citation_cache)}")

    # 3. Get ALL publications from your database
    cur.execute("SELECT pub_id FROM publication ORDER BY pub_id")
    publications = cur.fetchall()
    
    print(f"\nProcessing {len(publications)} publications to find who cites them...")
    print("-" * 60)

    # Track statistics
    new_publications_count = 0
    updated_publications_count = 0
    citations_added_count = 0
    citations_skipped_count = 0
    publications_with_no_citations = 0

    # 4. Process each publication
    for idx, (pub_id,) in enumerate(publications, 1):
        print(f"\n[{idx}/{len(publications)}] 📄 Processing publication: {pub_id}")

        # 4a. Fetch works that CITE this publication
        citing_works = fetch_citing_works(pub_id)
        
        if not citing_works:
            print(f"  ℹ️  No citing works found for {pub_id}")
            publications_with_no_citations += 1
            continue

        print(f"  Found {len(citing_works)} works that cite {pub_id}")

        # 4b. Process each citing work
        for citing_work in citing_works:
            # This is the paper that cites YOUR publication
            citing_pub_id = (citing_work.get("id") or "").split("/")[-1]
            
            if not citing_pub_id:
                continue

            # Fetch details of the citing publication
            citing_work_details = fetch_work_details(citing_pub_id)
            
            if citing_work_details:
                # Extract metadata
                title = citing_work_details.get("display_name")
                year = citing_work_details.get("publication_year")
                abstract = rebuild_abstract(citing_work_details.get("abstract_inverted_index"))
                total_citation = citing_work_details.get("cited_by_count", 0)
                
                # Insert or Update the citing publication
                result = insert_or_update_publication(
                    cur, pub_cache, citing_pub_id, title, abstract, year, total_citation
                )
                
                if result == 'inserted':
                    new_publications_count += 1
                elif result == 'updated':
                    updated_publications_count += 1
                
                # Now create the citation link
                # pub_id is being cited by citing_pub_id
                added = insert_citation(cur, citation_cache, pub_id, citing_pub_id)
                if added:
                    citations_added_count += 1
                else:
                    citations_skipped_count += 1
            else:
                print(f"  ⚠️  Cannot add {citing_pub_id} - not found on OpenAlex")
                citations_skipped_count += 1

        # 4c. Commit every 10 publications to avoid large transactions
        if idx % 10 == 0:
            conn.commit()
            print(f"  💾 Checkpoint saved")

        # 4d. Be nice to OpenAlex API (rate limiting)
        time.sleep(0.5)

    # 5. Final commit
    conn.commit()
    
    # 6. Print summary
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETED")
    print("=" * 60)
    print(f"📊 Publications processed: {len(publications)}")
    print(f"📊 Publications with no citations: {publications_with_no_citations}")
    print(f"📚 New publications added: {new_publications_count}")
    print(f"📚 Existing publications updated: {updated_publications_count}")
    print(f"🔗 New citations added: {citations_added_count}")
    print(f"⏭️  Citations skipped (already exist or error): {citations_skipped_count}")
    print(f"📚 Total publications now: {len(pub_cache)}")
    print(f"🔗 Total citations now: {len(citation_cache)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()