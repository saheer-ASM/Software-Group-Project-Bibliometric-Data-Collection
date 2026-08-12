# database.py

import psycopg2
import os
from dotenv import load_dotenv


# Load variables from .env file
load_dotenv()


def get_connection():

    connection = psycopg2.connect(

        host=os.getenv("DB_HOST"),

        database=os.getenv("DB_NAME"),

        user=os.getenv("DB_USER"),

        password=os.getenv("DB_PASSWORD"),

        port=os.getenv("DB_PORT"),

        sslmode="require"
    )

    return connection