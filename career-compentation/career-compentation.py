import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT") or 5432),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )

def main():
    conn = get_conn()
    cur = conn.cursor()

    print("Fetching statistics and calculating compensation...")
    
    # 1. Get stats for ALL authors in one query
    query = """
        SELECT aid, COUNT(pub_id) as total_pubs, MIN(year) as first_pub_year
        FROM (
            SELECT author1id as aid, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author2id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author3id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author4id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author5id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author6id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author7id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author8id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author9id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
            UNION ALL SELECT author10id, pub_id, year FROM author_contribution_weight JOIN publication USING(pub_id)
        ) AS flattened
        WHERE aid IS NOT NULL
        GROUP BY aid;
    """
    cur.execute(query)
    stats = cur.fetchall() 

    update_query = "UPDATE author SET career_compensation = %s WHERE author_id = %s;"
    batch = []
    
    print(f"{'Author ID':<15} | {'Pubs':<5} | {'1st Year':<10} | {'New Comp'}")
    print("-" * 55)

    for i, (author_id, total_pubs, first_pub_year) in enumerate(stats, 1):
        # 2. Calculation
        t = (2026 - first_pub_year) if first_pub_year else 0
        new_comp = round(1.25 * ((t + 1) ** -0.0601), 4)
        
        batch.append((new_comp, author_id))
        print(f"{author_id:<15} | {total_pubs:<5} | {str(first_pub_year):<10} | {new_comp}")

        # 3. Save to database in batches of 10
        if len(batch) >= 10:
            cur.executemany(update_query, batch)
            conn.commit()
            print(f"    💾 Saved batch of 10...")
            batch = []

    # 4. Save any remaining authors
    if batch:
        cur.executemany(update_query, batch)
        conn.commit()
        print(f"    💾 Saved final batch.")

    print(f"\n✅ Successfully updated {len(stats)} authors.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()