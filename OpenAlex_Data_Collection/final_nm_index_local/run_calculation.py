"""Final Nm-index (Eq. 24-27) on the LOCAL database.

SQLite port of final_nm_index/run_calculation.py (+ schema.sql).
calculator.py and config.py in this folder are UNMODIFIED copies of the cloud files, so
Eq. 24-27 are the same code:

    Eq. 24  Tra_a(x)  transform each component metric
    Eq. 25  Nor_a(x)  normalise it
    Eq. 26  Per_a(x)  map to a 0-100 percentile
    Eq. 27  Nm_a      weighted average of the six percentiles (weights 1/6 each)

The six component metrics are read, unchanged, from the tables the earlier steps wrote:

    x1 T_a    author_total_cites.total_cites_score                (total_cites_local)
    x2 S_a    author_citations_per_paper.citations_per_paper_score (eq12_13_14_local)
    x3 U_a    author_citation_rate.citation_rate_score             (eq12_13_14_local)
    x4 Hf_a   author_modified_hindex.modified_hindex_final         (eq17_local)
    x5 Hm_a   author.modified_hm_index                             (modified_hm_index_local)
    x6 G_a    author.modified_g_index                              (modified_g_index_local)

Percentiles are relative to the author population loaded (every author in the local
author table that has a value for that metric) -- exactly as in the cloud script.

Results go to the table author_nm_index (created here, same columns as the cloud
schema.sql) and, because config.NM_UPDATE_AUTHOR_TABLE is False, NOT to author.nm_index.

Run from the OpenAlex_Data_Collection folder:
    python -m final_nm_index_local.run_calculation --dry-run
    python -m final_nm_index_local.run_calculation
"""

import argparse
import time
from datetime import datetime

import pandas as pd

from . import config
from .calculator import NmIndexCalculator
from .db_connection import get_connection

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS author_nm_index (
        author_id TEXT PRIMARY KEY,
        per_total_cites REAL,
        per_citations_per_paper REAL,
        per_citation_rate REAL,
        per_modified_hf_index REAL,
        per_modified_hm_index REAL,
        per_modified_g_index REAL,
        metrics_available INTEGER NOT NULL DEFAULT 0,
        nm_index REAL,
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

WRITE_BATCH = 100_000


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def load_authors(connection) -> pd.DataFrame:
    cfg = config.AUTHOR_TABLE
    query = f"""
        SELECT {quote_identifier(cfg['author_id'])} AS author_id
        FROM {quote_identifier(cfg['table'])}
        WHERE {quote_identifier(cfg['author_id'])} IS NOT NULL
    """
    df = pd.read_sql(query, connection)
    print(f"  Loaded {len(df):,} authors")
    return df


def load_metric(connection, metric_name: str) -> pd.DataFrame:
    """[author_id, <metric_name>] for one component metric; NULL values are dropped,
    duplicate author_ids collapse to their max value (same as the cloud loader)."""
    src = config.METRIC_SOURCES[metric_name]
    where = [f"{quote_identifier(src['value'])} IS NOT NULL"]
    if config.NM_FILTER_STATUS and src.get("status"):
        allowed = src["status_ok"]
        if allowed:
            rendered = ", ".join(
                "1" if v is True else "0" if v is False else f"'{v}'" for v in allowed)
            where.append(f"{quote_identifier(src['status'])} IN ({rendered})")
    query = f"""
        SELECT
            {quote_identifier(src['author_id'])} AS author_id,
            {quote_identifier(src['value'])}     AS {metric_name}
        FROM {quote_identifier(src['table'])}
        WHERE {' AND '.join(where)}
    """
    try:
        df = pd.read_sql(query, connection)
    except Exception as error:  # noqa: BLE001 - report and continue
        print(f"  [WARN] {metric_name}: could not load ({error!r}); "
              f"treating as unavailable for all authors")
        return pd.DataFrame(columns=["author_id", metric_name])
    if not df.empty:
        df = (df.sort_values(metric_name)
                .drop_duplicates(subset="author_id", keep="last"))
    print(f"  {metric_name:<22} {len(df):>10,} authors with a value")
    return df


def get_data_from_database() -> pd.DataFrame:
    connection = get_connection()
    try:
        print()
        print("=" * 60)
        print("LOADING COMPONENT METRICS")
        print("=" * 60)
        authors = load_authors(connection)
        merged = authors[["author_id"]].copy()
        for metric_name in list(config.LOG_METRICS) + list(config.RANK_METRICS):
            metric_df = load_metric(connection, metric_name)
            merged = merged.merge(metric_df, on="author_id", how="left")
        return merged
    finally:
        connection.close()


def write_results(results: pd.DataFrame) -> None:
    connection = get_connection()
    cols = config.NM_RESULT_COLUMNS
    metric_names = list(config.LOG_METRICS) + list(config.RANK_METRICS)
    insert_cols = (
        [cols["author_id"]]
        + [cols[m] for m in metric_names]
        + [cols["metrics_available"], cols["nm_index"], cols["calculated_at"]]
    )
    upsert_sql = (
        f"INSERT OR REPLACE INTO {quote_identifier(config.NM_RESULT_TABLE)} "
        f"({', '.join(quote_identifier(c) for c in insert_cols)}) "
        f"VALUES ({', '.join('?' * len(insert_cols))})"
    )

    print()
    print("=" * 60)
    print(f"WRITING RESULTS -> {config.NM_RESULT_TABLE}")
    print("=" * 60)
    try:
        with connection:
            for statement in SCHEMA:
                connection.execute(statement)
            if config.NM_UPDATE_AUTHOR_TABLE:
                columns = [r[1] for r in connection.execute("PRAGMA table_info(author)")]
                if config.AUTHOR_NM_COLUMN not in columns:
                    connection.execute(
                        f"ALTER TABLE author ADD COLUMN {config.AUTHOR_NM_COLUMN} REAL")

        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        total = len(results)
        per_columns = [f"per_{m}" for m in metric_names]
        for start in range(0, total, WRITE_BATCH):
            part = results.iloc[start:start + WRITE_BATCH]
            rows = []
            for record in part[["author_id"] + per_columns +
                               ["metrics_available", "nm_index"]].itertuples(index=False):
                values = [record[0]]
                values += [None if pd.isna(v) else float(v) for v in record[1:7]]
                values.append(int(record[7]))
                values.append(None if pd.isna(record[8]) else float(record[8]))
                values.append(now)
                rows.append(values)
            with connection:
                connection.executemany(upsert_sql, rows)
                if config.NM_UPDATE_AUTHOR_TABLE:
                    connection.executemany(
                        f"UPDATE author SET {config.AUTHOR_NM_COLUMN} = ? WHERE author_id = ?",
                        [(r[8], r[0]) for r in rows])
            done = min(start + WRITE_BATCH, total)
            print(f"  [{done:,}/{total:,}] {100 * done / total:6.2f}%", flush=True)
        print(f"Committed {total:,} rows.")
    finally:
        connection.close()


def parse_arguments():
    parser = argparse.ArgumentParser(description="Final Nm-index (Eq 24-27), local database.")
    parser.add_argument("--dry-run", action="store_true",
                        help="calculate and print a summary, write nothing")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    print()
    print("=" * 60)
    print("FINAL Nm-INDEX CALCULATION")
    print("=" * 60)
    print(f"Started: {datetime.now()}")
    started = time.time()

    metrics = get_data_from_database()
    metric_names = list(config.LOG_METRICS) + list(config.RANK_METRICS)

    print()
    print("Component coverage (non-null / total authors):")
    for m in metric_names:
        have = metrics[m].notna().sum() if m in metrics else 0
        print(f"  {m:<22} {have:>10,} / {len(metrics):,}")

    calculator = NmIndexCalculator()
    results = calculator.calculate(metrics)
    print(f"\n  calculated in {(time.time() - started) / 60:.1f} min")

    scored = results["nm_index"].notna()
    print()
    print("-" * 60)
    print(f"Authors scored          : {scored.sum():,} / {len(results):,}")
    if scored.any():
        print(f"Nm-index mean           : {results.loc[scored, 'nm_index'].mean():.4f}")
        print(f"Nm-index min / max      : "
              f"{results.loc[scored, 'nm_index'].min():.4f} / "
              f"{results.loc[scored, 'nm_index'].max():.4f}")
    print("metrics_available distribution:")
    print(results["metrics_available"].value_counts().sort_index().to_string())
    print()
    print("Top 10 authors by Nm-index:")
    top = results.sort_values("nm_index", ascending=False).head(10)
    for _, r in top.iterrows():
        print(f"  {r['author_id']}  Nm={r['nm_index']:.4f}  "
              f"(from {int(r['metrics_available'])} metrics)")

    if arguments.dry_run:
        print("\nDry run: nothing written to the database.")
        return

    write_results(results)
    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Completed: {datetime.now()}")


if __name__ == "__main__":
    main()
