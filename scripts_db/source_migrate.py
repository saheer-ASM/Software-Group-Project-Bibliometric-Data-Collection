import os
import psycopg2
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =========================================
# DB CONNECTION
# =========================================
def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT") or 5432),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )

# =========================================
# MAIN EXECUTION
# =========================================
def main():
    print("========================================")
    print(" UPDATING PUBLICATION SOURCES FROM OPENALEX")
    print("========================================")
    
    conn = get_conn()
    cur = conn.cursor()

    # Step 0: Ensure the source column exists
    cur.execute("ALTER TABLE publication ADD COLUMN IF NOT EXISTS source TEXT;")
    conn.commit()

    # Step 1: Fetch publications where source is NULL
    print("Fetching publications without a source...")
    cur.execute("SELECT pub_id FROM publication WHERE source IS NULL;")
    pubs = cur.fetchall()

    if not pubs:
        print("✅ All publications already have a source.")
        cur.close()
        conn.close()
        return

    print(f"Found {len(pubs)} publications to update.")

    for (pub_id,) in pubs:
        try:
            # Query OpenAlex API
            url = f"https://api.openalex.org/works/{pub_id}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extracting publisher name from primary_location -> source -> host_organization_name
                # Fallback to display_name if host_organization_name is missing
                publisher = (
                    data.get("primary_location", {})
                    .get("source", {})
                    .get("host_organization_name")
                )
                
                if publisher:
                    cur.execute("UPDATE publication SET source = %s WHERE pub_id = %s;", (publisher, pub_id))
                    conn.commit()
                    print(f"  [UPDATED] {pub_id} -> {publisher}")
                else:
                    print(f"  [SKIPPED] No publisher found for {pub_id}")
            else:
                print(f"  [ERROR] API request failed for {pub_id}: {response.status_code}")
            
            # Polite delay to respect OpenAlex API guidelines
            time.sleep(0.5)

        except Exception as e:
            print(f"  [ERROR] {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print("\n✅ Update process complete.")

if __name__ == "__main__":
    main()