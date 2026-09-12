"""
Step 1 -- build one author-level dataset.

Produces exactly:

    author_id, T_a, S_a, U_a, Hf_a, Hm_a, G_a

one row per author, by reading the six already-computed component
scores straight out of PostgreSQL. Nothing here recalculates
citations, h-index, hm-index, g-index, etc. -- those are read as-is
from the tables mapped in config.py.

A metric that is NULL for a given author in the source table stays
NaN in the output (never filled with 0).
"""

import pandas as pd

from . import config


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _load_metric(connection, column_name: str) -> pd.DataFrame:
    """Load one [author_id, <column_name>] frame for one metric."""

    src = config.METRIC_SOURCES[column_name]

    # Alias must be quoted -- Postgres folds an unquoted alias like
    # "AS T_a" to lowercase ("t_a"), which would then fail to match
    # config.METRIC_COLUMNS ("T_a") after the round trip through pandas.
    query = f"""
        SELECT
            {_quote(src['author_id'])} AS author_id,
            {_quote(src['value'])}     AS {_quote(column_name)}
        FROM {_quote(src['table'])}
        WHERE {_quote(src['value'])} IS NOT NULL
    """

    df = pd.read_sql(query, connection)

    # Defensive de-dup: every source table is expected to already be
    # unique on author_id.
    if not df.empty:
        df = df.drop_duplicates(subset="author_id", keep="last")

    return df


def _load_authors(connection) -> pd.DataFrame:
    cfg = config.AUTHOR_TABLE
    query = f"""
        SELECT {_quote(cfg['author_id'])} AS author_id
        FROM {_quote(cfg['table'])}
        WHERE {_quote(cfg['author_id'])} IS NOT NULL
    """
    return pd.read_sql(query, connection)


def build_author_metric_dataset(connection) -> pd.DataFrame:
    """
    Step 1.

    Parameters
    ----------
    connection : an open DB-API connection (e.g. database.get_connection()).

    Returns
    -------
    DataFrame with columns:
        author_id, T_a, S_a, U_a, Hf_a, Hm_a, G_a
    one row per author known to the `author` table. A metric column
    is NaN for any author whose source row is NULL or missing.
    """

    dataset = _load_authors(connection)

    for column_name in config.METRIC_COLUMNS:
        metric_df = _load_metric(connection, column_name)
        dataset = dataset.merge(metric_df, on="author_id", how="left")

    return dataset[["author_id", *config.METRIC_COLUMNS]]
