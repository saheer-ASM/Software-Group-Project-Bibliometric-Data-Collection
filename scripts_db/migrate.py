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
    CREATE TABLE IF NOT EXISTS citation (
        pub_id          VARCHAR(100) NOT NULL,
        cited_pub_id    VARCHAR(100) NOT NULL,
        PRIMARY KEY (pub_id, cited_pub_id),
        FOREIGN KEY (pub_id) REFERENCES publication(pub_id) ON DELETE CASCADE,
        FOREIGN KEY (cited_pub_id) REFERENCES publication(pub_id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS field_classification (
        pub_id          VARCHAR(100) PRIMARY KEY,
        field1_name     VARCHAR(255),
        field1_weight   DECIMAL(5,2),
        field2_name     VARCHAR(255),
        field2_weight   DECIMAL(5,2),
        field3_name     VARCHAR(255),
        field3_weight   DECIMAL(5,2),
        FOREIGN KEY (pub_id) REFERENCES publication(pub_id) ON DELETE CASCADE
    );
    """,
   """
    CREATE TABLE IF NOT EXISTS author_contribution_weight (
        pub_id                                  VARCHAR(100) PRIMARY KEY,
        author1Id                               TEXT,
        author2Id                               TEXT,
        author3Id                               TEXT,
        author4Id                               TEXT,
        author5Id                               TEXT,
        author6Id                               TEXT,
        author7Id                               TEXT,
        author8Id                               TEXT,
        author9Id                               TEXT, 
        author10Id                               TEXT,
        author_ordering_nome                    TEXT,
        field1_author_contribution_weight       DECIMAL(6,4),
        field2_author_contribution_weight       DECIMAL(6,4),
        field3_author_contribution_weight       DECIMAL(6,4),
        overall_author_contribution_weight      DECIMAL(6,4),
        FOREIGN KEY (pub_id) REFERENCES publication(pub_id) ON DELETE CASCADE,
        FOREIGN KEY (author1Id) REFERENCES author(author_id),
        FOREIGN KEY (author2Id) REFERENCES author(author_id),
        FOREIGN KEY (author3Id) REFERENCES author(author_id),
        FOREIGN KEY (author4Id) REFERENCES author(author_id),
        FOREIGN KEY (author5Id) REFERENCES author(author_id),
        FOREIGN KEY (author6Id) REFERENCES author(author_id),
        FOREIGN KEY (author7Id) REFERENCES author(author_id),
        FOREIGN KEY (author8Id) REFERENCES author(author_id),
        FOREIGN KEY (author9Id) REFERENCES author(author_id),
        FOREIGN KEY (author10Id) REFERENCES author(author_id)
    
    );
    """,
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