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

def test_author_metrics(author_id):
    conn = get_conn()
    cur = conn.cursor()

    # 1. Fetch author details (using author_name)
    cur.execute("SELECT author_name, career_compensation FROM author WHERE author_id = %s;", (author_id,))
    author = cur.fetchone()
    
    if not author:
        print(f"❌ Author {author_id} not found.")
        return

    author_name, current_comp = author

    # 2. Get publications and earliest year
    # We check all 10 author columns defined in your schema
    cols = [f"author{i}Id" for i in range(1, 11)]
    where_clause = " OR ".join([f"{col} = %s" for col in cols])
    
    query = f"""
        SELECT p.pub_id, p.year
        FROM author_contribution_weight acw
        JOIN publication p ON acw.pub_id = p.pub_id
        WHERE {where_clause};
    """
    
    cur.execute(query, [author_id] * 10)
    pubs = cur.fetchall()
    
    years = [p[1] for p in pubs if p[1] is not None]
    first_pub_year = min(years) if years else None

    # 3. Calculate metrics
    t = (2026 - first_pub_year) if first_pub_year is not None else 0
    new_comp = 1.25 * ((t + 1) ** -0.0601)
    new_comp = round(new_comp, 4)

    # 4. Output results
    print(f"--- DEBUG METRICS ---")
    print(f"Author Name: {author_name}")
    print(f"Author ID:   {author_id}")
    print(f"Current DB Compensation: {current_comp}")
    print(f"Total Publications:      {len(pubs)}")
    print(f"Earliest Pub Year:       {first_pub_year}")
    print(f"Experience (t):          {t}")
    print(f"Calculated Compensation: {new_comp}")
    print("---------------------")

    cur.close()
    conn.close()

if __name__ == "__main__":
    # Replace with an actual ID from your database
    test_author_metrics('A5050585435')