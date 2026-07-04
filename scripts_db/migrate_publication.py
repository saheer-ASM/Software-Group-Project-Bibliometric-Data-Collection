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
    cur.execute("SELECT author_id FROM author")
    return set(r[0] for r in cur.fetchall())


def load_existing_publications(cur):
    cur.execute("SELECT pub_id FROM publication")
    return set(r[0] for r in cur.fetchall())


# ---------------- ABSTRACT CLEANER ----------------
def rebuild_abstract(inv_index):
    if not inv_index or not isinstance(inv_index, dict):
        return None

    words = {}
    for word, positions in inv_index.items():
        for p in positions:
            words[p] = word

    return " ".join(words[i] for i in sorted(words.keys()))


# ---------------- FETCH OPENALEX ----------------
def fetch_works(author_id):
    try:
        params = {
            "filter": f"author.id:{author_id}",
            "per_page": 200
        }
        r = requests.get(OPENALEX_WORKS, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"[ERROR] OpenAlex fetch failed for {author_id}: {e}")
        return []


# ---------------- SAFE AUTHOR HANDLER ----------------
def ensure_author(cur, cache, author_obj):
    if not isinstance(author_obj, dict):
        return None

    author_id_full = author_obj.get("id")
    if not author_id_full:
        return None

    aid = author_id_full.split("/")[-1]
    name = author_obj.get("display_name") or "Unknown"

    if aid not in cache:
        cur.execute("""
            INSERT INTO author (author_id, author_name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (aid, name))

        cache.add(aid)
        print(f"[NEW AUTHOR] {name} ({aid})")

    return aid


# ---------------- INSERT PUBLICATION ----------------
def insert_publication(cur, pub_cache, pub_id, title, abstract, year):
    if pub_id in pub_cache:
        return False

    cur.execute("""
        INSERT INTO publication (pub_id, pub_title, abstract, year)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (pub_id, title, abstract, year))

    pub_cache.add(pub_id)
    return True


# ---------------- LINK TABLE ----------------
def link_author(cur, pub_id, author_id):
    if not author_id:
        return

    cur.execute("""
        INSERT INTO publication_author (pub_id, author_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (pub_id, author_id))


# ---------------- MAIN PIPELINE ----------------
def main():
    conn = get_conn()
    cur = conn.cursor()

    print("Loading cache...")

    author_cache = load_existing_authors(cur)
    pub_cache = load_existing_publications(cur)

    print(f"Authors: {len(author_cache)}")
    print(f"Publications: {len(pub_cache)}")

    # fetch authors from DB
    cur.execute("SELECT author_id FROM author LIMIT 5")
    authors = cur.fetchall()

    for (author_id,) in authors:
        print(f"\n🔍 Processing author {author_id}")

        works = fetch_works(author_id)
        print(f"Found {len(works)} works")

        for w in works:
            pub_id = (w.get("id") or "").split("/")[-1]
            if not pub_id:
                continue

            title = w.get("display_name")
            year = w.get("publication_year")
            abstract = rebuild_abstract(w.get("abstract_inverted_index"))

            # insert publication
            insert_publication(cur, pub_cache, pub_id, title, abstract, year)

            # process authors safely
            for a in w.get("authorships", []):
                if not isinstance(a, dict):
                    continue

                auth = a.get("author")
                if not auth or not isinstance(auth, dict):
                    continue

                aid = ensure_author(cur, author_cache, auth)
                link_author(cur, pub_id, aid)

            print(f"✔ Done {pub_id}")

        conn.commit()
        time.sleep(1)

    cur.close()
    conn.close()
    print("\n✅ PIPELINE COMPLETED SAFELY")


if __name__ == "__main__":
    main()