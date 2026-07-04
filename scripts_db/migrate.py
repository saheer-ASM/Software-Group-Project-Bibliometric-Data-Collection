import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    sslmode="require"        
)
cur = conn.cursor()

# Tracking table — remembers which migrations already ran
cur.execute("""
    CREATE TABLE IF NOT EXISTS migrations_log (
        filename   VARCHAR(255) PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT NOW()
    );
""")
conn.commit()

migrations_dir = "migrations"
sql_files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))

for filename in sql_files:
    cur.execute("SELECT filename FROM migrations_log WHERE filename = %s", (filename,))
    if cur.fetchone():
        print(f"  Skipping {filename} (already applied)")
        continue

    filepath = os.path.join(migrations_dir, filename)
    with open(filepath, "r") as f:
        sql = f.read()

    print(f"  Applying {filename}...")
    cur.execute(sql)
    cur.execute("INSERT INTO migrations_log (filename) VALUES (%s)", (filename,))
    conn.commit()
    print(f"  Done!")

cur.close()
conn.close()
print("\nAll migrations complete. Your tables are ready.")