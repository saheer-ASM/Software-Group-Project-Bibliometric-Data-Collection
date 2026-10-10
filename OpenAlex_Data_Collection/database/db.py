"""Shared SQLite helpers. The whole database is ONE file: openalex.db.

No server, no username/password. Anyone who copies openalex.db into their own
`database/` folder (or points OPENALEX_DB_PATH at it) can open the same data.
"""

import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("OPENALEX_DB_PATH") or os.path.join(HERE, "openalex.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS author (
    author_id    TEXT PRIMARY KEY,
    author_name  TEXT,
    pub_finished TEXT
);

CREATE TABLE IF NOT EXISTS publication (
    pub_id         TEXT PRIMARY KEY,
    pub_title      TEXT,
    abstract       TEXT,
    year           INTEGER,
    total_citation INTEGER,
    -- 'need to update' | 'updated' | 'no need to update'
    update_status  TEXT NOT NULL DEFAULT 'need to update',
    -- 'done' once this paper's authors were collected, else NULL
    co_author      TEXT
);

-- pub_id = the cited paper, cites_pub_id = the paper that cites it
CREATE TABLE IF NOT EXISTS citation (
    pub_id       TEXT NOT NULL,
    cites_pub_id TEXT NOT NULL,
    PRIMARY KEY (pub_id, cites_pub_id)
) WITHOUT ROWID;

-- same shape as the Postgres table: first 10 authors of each paper
CREATE TABLE IF NOT EXISTS author_contribution_weight (
    pub_id TEXT PRIMARY KEY,
    author1id TEXT, author2id TEXT, author3id TEXT, author4id TEXT, author5id TEXT,
    author6id TEXT, author7id TEXT, author8id TEXT, author9id TEXT, author10id TEXT,
    author1id_weight REAL, author2id_weight REAL, author3id_weight REAL,
    author4id_weight REAL, author5id_weight REAL, author6id_weight REAL,
    author7id_weight REAL, author8id_weight REAL, author9id_weight REAL,
    author10id_weight REAL
);

CREATE INDEX IF NOT EXISTS idx_publication_status ON publication(update_status);
CREATE INDEX IF NOT EXISTS idx_citation_cites ON citation(cites_pub_id);
"""


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.executescript(SCHEMA)
    return conn
