"""Local SQLite connection for the Eq 11 modules (replaces Calculating_ISC.db_connection,
which opens the cloud PostgreSQL database)."""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "database"))

from db import DB_PATH, get_conn   # noqa: E402


def get_connection():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Local database not found: {DB_PATH}")
    conn = get_conn()
    # PostgreSQL POWER(), so the SQL stays the same as the cloud script
    conn.create_function("POWER", 2, lambda a, b: math.pow(a, b))
    return conn
