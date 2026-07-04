import os
import psycopg2
from dotenv import load_dotenv

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
# CREATE TABLES SQL
# =========================================
TABLES = [

"""
CREATE TABLE IF NOT EXISTS author (
    author_id   VARCHAR(100) PRIMARY KEY,
    author_name VARCHAR(255) NOT NULL
);
""",

"""
CREATE TABLE IF NOT EXISTS publication (
    pub_id          VARCHAR(100) PRIMARY KEY,
    pub_title       TEXT,
    abstract        TEXT,
    year            INT,
    total_citation  INT DEFAULT 0
);
""",

"""
CREATE TABLE IF NOT EXISTS publication_author (
    pub_id     VARCHAR(100) NOT NULL,
    author_id  VARCHAR(100) NOT NULL,

    PRIMARY KEY (pub_id, author_id),

    FOREIGN KEY (pub_id)
        REFERENCES publication(pub_id)
        ON DELETE CASCADE,

    FOREIGN KEY (author_id)
        REFERENCES author(author_id)
        ON DELETE CASCADE
);
""",

"""
CREATE TABLE IF NOT EXISTS self_citation (
    pub_id          VARCHAR(100) NOT NULL,
    cited_pub_id    VARCHAR(100) NOT NULL,

    PRIMARY KEY (pub_id, cited_pub_id),

    FOREIGN KEY (pub_id)
        REFERENCES publication(pub_id)
        ON DELETE CASCADE,

    FOREIGN KEY (cited_pub_id)
        REFERENCES publication(pub_id)
        ON DELETE CASCADE
);
"""
]


# =========================================
# MAIN EXECUTION
# =========================================
def main():
    conn = get_conn()
    cur = conn.cursor()

    print("Creating tables...")

    for sql in TABLES:
        cur.execute(sql)
        print("✔ Table executed")

    conn.commit()
    cur.close()
    conn.close()

    print("\n✅ All tables created successfully!")


if __name__ == "__main__":
    main()