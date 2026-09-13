# database.py

import os

import psycopg2
from dotenv import load_dotenv


# Load variables from the repo-root .env file
load_dotenv()


def get_connection():
    """
    Open a PostgreSQL connection using the same .env variables the
    rest of the project uses (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD,
    DB_PORT). SSL is required by the managed instance.
    """

    connection = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
        sslmode="require",
    )

    return connection
