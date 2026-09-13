from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent


def load_default_environment() -> None:
    """
    Load database variables without overriding values that are already
    present in the operating-system environment.

    Supported locations:
        1. project-root/.env
        2. Calculating_ISC/.env

    Keeping both locations supported makes the ISC module usable in the
    collaborative repository without requiring credentials in source code.
    """

    candidate_files = (
        PROJECT_ROOT / ".env",
        MODULE_DIR / ".env",
    )

    for env_file in candidate_files:
        if env_file.exists():
            load_dotenv(
                dotenv_path=env_file,
                override=False,
            )


load_default_environment()


def get_connection():
    """
    Create and return a PostgreSQL connection.
    """

    required_variables = [
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        searched_locations = (
            f"{PROJECT_ROOT / '.env'}, "
            f"{MODULE_DIR / '.env'}"
        )

        raise RuntimeError(
            "Missing database environment variables: "
            + ", ".join(missing_variables)
            + ". Checked: "
            + searched_locations
        )

    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "require"),
    )