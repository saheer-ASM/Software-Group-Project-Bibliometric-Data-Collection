import psycopg2
import os
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

try:
    # Connect
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )
    print("✓ Connection successful!")
    
    cur = conn.cursor()
    
    # Check what tables exist
    print("\n📋 Tables in database:")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables = cur.fetchall()
    for table in tables:
        print(f"  - {table[0]}")
    
    # Check row counts
    print("\n📊 Row counts:")
    cur.execute("SELECT COUNT(*) FROM author;")
    print(f"  author: {cur.fetchone()[0]} rows")
    
    cur.execute("SELECT COUNT(*) FROM publication;")
    print(f"  publication: {cur.fetchone()[0]} rows")
    
    cur.execute("SELECT COUNT(*) FROM self_citation;")
    print(f"  self_citation: {cur.fetchone()[0]} rows")
    
    # Sample data
    print("\n📝 Sample data (first 3 authors):")
    cur.execute("SELECT * FROM author LIMIT 3;")
    for row in cur.fetchall():
        print(f"  {row}")
    
    cur.close()
    conn.close()
    print("\n✓ All checks passed! Database is working.")
    
except Exception as e:
    print(f"✗ Error: {e}")
    print("\nTroubleshooting:")
    print("  1. Check if PostgreSQL server is running")
    print("  2. Verify credentials in .env are correct")
    print("  3. Check if firewall allows connection to 13.48.93.138:5432")
