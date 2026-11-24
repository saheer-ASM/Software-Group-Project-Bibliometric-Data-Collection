"""Yearly Nm-index scores for V6 (score evolution), V8 (t = 2019) and V9 (stability).

For each year y in --from..--to:
    1. make_snapshot_db.py   -> database/snapshots/snapshot_<y>.db  (papers and citations <= y)
    2. run the calculation steps on that snapshot with --as-of-year y
       (career factor, ISC, Eq 11-27; author weights are copied, they do not
       depend on time)
    3. read author_nm_index -> one row per (author_id, year, nm_index)

Writes --out (default ..\\NM-Index-Empirical-Validation\\inputs\\annual_scores.csv)
and, for --score-year, historical_scores.csv next to it. A year whose snapshot
already has author_nm_index is skipped (resumable); use --redo to recompute.

Usage (from the OpenAlex_Data_Collection folder):
    python run_yearly_snapshots.py --from 2015 --to 2024
"""

import argparse
import csv
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))
from db import DB_PATH                                   # noqa: E402

STEPS = [
    ["career_compensation_local/run_career_compensation.py", "--as-of-year", "{y}"],
    ["-m", "isc_local.run_isc"],
    ["-m", "total_cites_local.db_setup"],
    ["-m", "total_cites_local.run_total_cites", "--cohort", "done", "--as-of-year", "{y}"],
    ["-m", "eq12_13_14_local.run_equations_12_13_14", "--as-of-year", "{y}"],
    ["-m", "eq15_local.run_equation_15"],
    ["-m", "eq16_local.run_equation_16", "--cohort", "done"],
    ["-m", "eq17_local.run_equation_17", "--cohort", "done"],
    ["-m", "modified_hm_index_local.run_calculation", "--cohort", "done"],
    ["-m", "modified_g_index_local.run_calculation", "--cohort", "done"],
    ["-m", "final_nm_index_local.run_calculation", "--cohort", "done"],
]


def has_scores(path):
    if not os.path.exists(path):
        return False
    conn = sqlite3.connect(path)
    try:
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'author_nm_index'").fetchone()
                    and conn.execute("SELECT COUNT(*) FROM author_nm_index").fetchone()[0])
    finally:
        conn.close()


def scores(path, year):
    conn = sqlite3.connect(path)
    try:
        return [(a, year, v) for a, v in conn.execute(
            "SELECT author_id, nm_index FROM author_nm_index WHERE nm_index IS NOT NULL")]
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="first", type=int, default=2015)
    parser.add_argument("--to", dest="last", type=int, default=2024)
    parser.add_argument("--score-year", type=int, default=2019)
    parser.add_argument("--source", default=DB_PATH)
    parser.add_argument("--snapshot-dir", default=os.path.join(HERE, "database", "snapshots"))
    parser.add_argument("--out", default=os.path.join(HERE, "..", "NM-Index-Empirical-Validation",
                                                      "inputs", "annual_scores.csv"))
    parser.add_argument("--redo", action="store_true")
    args = parser.parse_args()
    os.makedirs(args.snapshot_dir, exist_ok=True)
    rows = []
    for year in range(args.first, args.last + 1):
        snap = os.path.join(args.snapshot_dir, f"snapshot_{year}.db")
        if args.redo and os.path.exists(snap):
            os.remove(snap)
        if not has_scores(snap):
            if os.path.exists(snap):
                os.remove(snap)          # incomplete earlier run: rebuild from scratch
            print(f"\n=== {year}: building snapshot", flush=True)
            subprocess.run([sys.executable, os.path.join(HERE, "make_snapshot_db.py"), "--year", str(year),
                            "--source", args.source, "--out", snap], check=True)
            env = dict(os.environ, OPENALEX_DB_PATH=snap)
            for step in STEPS:
                cmd = [sys.executable] + [part.format(y=year) for part in step]
                print(f"--- {year}: {' '.join(step[:2])}", flush=True)
                subprocess.run(cmd, cwd=HERE, env=env, check=True)
        rows += scores(snap, year)
        print(f"=== {year}: {sum(r[1] == year for r in rows):,} author scores", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["author_id", "year", "nm_index"])
        writer.writerows(rows)
    hist = os.path.join(os.path.dirname(os.path.abspath(args.out)), "historical_scores.csv")
    with open(hist, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["author_id", "score_year", "nm_index"])
        writer.writerows(r for r in rows if r[1] == args.score_year)
    print(f"\nannual scores -> {args.out}\nhistorical scores ({args.score_year}) -> {hist}")


if __name__ == "__main__":
    main()
