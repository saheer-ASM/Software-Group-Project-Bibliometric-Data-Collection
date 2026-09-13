"""
Load the six per-author component metrics from PostgreSQL, compute the
final Nm-index (Eq. 24-27), and write the results back.

    python -m "final Nm index".run_calculation

Prereq: run schema.sql once against the target DB first.
"""

from datetime import datetime

import pandas as pd

from . import config
from .calculator import NmIndexCalculator
from .database import get_connection


# =============================================================
# SQL helpers
# =============================================================

def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


# =============================================================
# LOAD
# =============================================================

def load_authors(connection) -> pd.DataFrame:
    cfg = config.AUTHOR_TABLE
    query = f"""
        SELECT
            {quote_identifier(cfg['author_id'])}   AS author_id,
            {quote_identifier(cfg['author_name'])} AS author_name
        FROM {quote_identifier(cfg['table'])}
        WHERE {quote_identifier(cfg['author_id'])} IS NOT NULL
    """
    df = pd.read_sql(query, connection)
    print(f"  Loaded {len(df)} authors")
    return df


def load_metric(connection, metric_name: str) -> pd.DataFrame:
    """
    Return a DataFrame [author_id, <metric_name>] for one component
    metric. Rows with a NULL value are dropped (that author simply
    has no value for this metric). Duplicate author_ids are collapsed
    to their max value defensively -- every source table is expected
    to be unique on author_id already.
    """
    src = config.METRIC_SOURCES[metric_name]

    where = [f"{quote_identifier(src['value'])} IS NOT NULL"]

    if config.NM_FILTER_STATUS and src.get("status"):
        allowed = src["status_ok"]
        if allowed:
            rendered = ", ".join(
                "TRUE" if v is True else "FALSE" if v is False
                else f"'{v}'"
                for v in allowed
            )
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
        df = (
            df.sort_values(metric_name)
              .drop_duplicates(subset="author_id", keep="last")
        )

    print(f"  {metric_name:<22} {len(df):>6} authors with a value")
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

        for metric_name in (
            list(config.LOG_METRICS) + list(config.RANK_METRICS)
        ):
            metric_df = load_metric(connection, metric_name)
            merged = merged.merge(metric_df, on="author_id", how="left")

        return merged.merge(authors, on="author_id", how="left")
    finally:
        connection.close()


# =============================================================
# WRITE
# =============================================================

def write_results(results: pd.DataFrame) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    table = quote_identifier(config.NM_RESULT_TABLE)
    cols = config.NM_RESULT_COLUMNS

    metric_names = list(config.LOG_METRICS) + list(config.RANK_METRICS)

    insert_cols = (
        [cols["author_id"]]
        + [cols[m] for m in metric_names]
        + [cols["metrics_available"], cols["nm_index"], cols["calculated_at"]]
    )
    placeholders = ", ".join(["%s"] * len(insert_cols))
    update_assignments = ", ".join(
        f"{quote_identifier(c)} = EXCLUDED.{quote_identifier(c)}"
        for c in insert_cols
        if c != cols["author_id"]
    )

    upsert_sql = f"""
        INSERT INTO {table} (
            {", ".join(quote_identifier(c) for c in insert_cols)}
        )
        VALUES ({placeholders})
        ON CONFLICT ({quote_identifier(cols['author_id'])})
        DO UPDATE SET {update_assignments}
    """

    author_update_sql = None
    if config.NM_UPDATE_AUTHOR_TABLE:
        author_update_sql = f"""
            UPDATE {quote_identifier(config.AUTHOR_TABLE['table'])}
            SET {quote_identifier(config.AUTHOR_NM_COLUMN)} = %s
            WHERE {quote_identifier(config.AUTHOR_TABLE['author_id'])} = %s
        """

    print()
    print("=" * 60)
    print(f"WRITING RESULTS -> {config.NM_RESULT_TABLE}")
    print("=" * 60)

    try:
        connection.autocommit = False
        now = datetime.now()
        total = len(results)

        for i, (_, row) in enumerate(results.iterrows(), start=1):
            nm_value = (
                None if pd.isna(row["nm_index"]) else float(row["nm_index"])
            )

            values = [row["author_id"]]
            for metric in metric_names:
                v = row[f"per_{metric}"]
                values.append(None if pd.isna(v) else float(v))
            values.append(int(row["metrics_available"]))
            values.append(nm_value)
            values.append(now)

            cursor.execute(upsert_sql, values)

            if author_update_sql is not None:
                cursor.execute(author_update_sql, (nm_value, row["author_id"]))

            if i % 500 == 0 or i == total:
                print(f"  [{i}/{total}] {100 * i / total:6.2f}%")

        connection.commit()
        print(f"Committed {total} rows.")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


# =============================================================
# MAIN
# =============================================================

def main() -> None:
    print()
    print("=" * 60)
    print("FINAL Nm-INDEX CALCULATION")
    print("=" * 60)
    print(f"Started: {datetime.now()}")

    metrics = get_data_from_database()

    metric_names = list(config.LOG_METRICS) + list(config.RANK_METRICS)
    print()
    print("Component coverage (non-null / total authors):")
    for m in metric_names:
        have = metrics[m].notna().sum() if m in metrics else 0
        print(f"  {m:<22} {have:>6} / {len(metrics)}")

    calculator = NmIndexCalculator()
    results = calculator.calculate(metrics)

    scored = results["nm_index"].notna()
    print()
    print("-" * 60)
    print(f"Authors scored          : {scored.sum()} / {len(results)}")
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

    write_results(results)

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Completed: {datetime.now()}")


if __name__ == "__main__":
    main()
