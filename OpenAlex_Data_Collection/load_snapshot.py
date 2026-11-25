"""Build openalex.db for a cohort from the OpenAlex snapshot (no API calls).

Replaces steps 2-4 of RUN_EQUATIONS.md (publications, citing papers, co-authors)
for large cohorts. Streams the snapshot's works files (gzip JSON Lines) twice:

  pass 1  works with a cohort author      -> publication (update_status 'updated',
          co_author 'done'), author_contribution_weight (first 10 authors),
          author (cohort: pub_finished 'done'; co-authors: 'no need'),
          institution + author_institution (cohort authors)
  pass 2  works whose referenced_works hit a pass-1 work -> publication
          ('no need to update', co_author 'done'), its authors, citation rows

Then continue with RUN_EQUATIONS.md step 4b (CRediT), 5 (field classification)
and 6 onward. Resumable per file: finished .gz files are recorded in
snapshot_progress and skipped on re-run.

Usage (from the OpenAlex_Data_Collection folder):
  python load_snapshot.py --snapshot E:\\openalex --cohort cohort.csv
  (writes to OPENALEX_DB_PATH or database\\openalex.db)
"""

import argparse
import csv
import glob
import gzip
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))
from db import DB_PATH, get_conn                        # noqa: E402

MAX_AUTHORS = 10
COLS = ", ".join(f"author{i}id" for i in range(1, MAX_AUTHORS + 1))
PROGRESS_SQL = "CREATE TABLE IF NOT EXISTS snapshot_progress (pass INTEGER, file TEXT, PRIMARY KEY (pass, file))"
INST_SQL = """
CREATE TABLE IF NOT EXISTS institution (institution_id TEXT PRIMARY KEY, institution_name TEXT,
                                        country_code TEXT, type TEXT);
CREATE TABLE IF NOT EXISTS author_institution (author_id TEXT NOT NULL, institution_id TEXT NOT NULL,
                                               PRIMARY KEY (author_id, institution_id)) WITHOUT ROWID;
"""


def short(url):
    return url.rstrip("/").split("/")[-1] if url else None


def abstract(inv):
    if not isinstance(inv, dict):
        return ""
    words = {p: w for w, ps in inv.items() for p in ps}
    return " ".join(words[i] for i in sorted(words))


def read_cohort(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["author_id"].strip() for r in csv.DictReader(f) if r["author_id"].strip()}


def works_files(root):
    files = sorted(glob.glob(os.path.join(root, "**", "works", "**", "*.gz"), recursive=True))
    if not files:
        sys.exit(f"No works/*.gz files under {root}")
    return files


def iter_works(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def authorships(work):
    out = []
    for a in work.get("authorships") or []:
        aid = short((a.get("author") or {}).get("id"))
        if aid and aid not in [x[0] for x in out]:
            out.append((aid, (a.get("author") or {}).get("display_name") or "Unknown", a.get("institutions") or []))
    return out


def save_work(conn, work, status, cohort):
    pid = short(work.get("id"))
    auth = authorships(work)
    conn.execute("INSERT OR IGNORE INTO publication (pub_id, pub_title, abstract, year, total_citation, "
                 "update_status, co_author) VALUES (?,?,?,?,?,?, 'done')",
                 (pid, work.get("title") or work.get("display_name"), abstract(work.get("abstract_inverted_index")),
                  work.get("publication_year"), work.get("cited_by_count"), status))
    ids = [a[0] for a in auth[:MAX_AUTHORS]] + [None] * (MAX_AUTHORS - min(len(auth), MAX_AUTHORS))
    conn.execute(f"INSERT OR IGNORE INTO author_contribution_weight (pub_id, {COLS}) VALUES "
                 f"(?{',?' * MAX_AUTHORS})", (pid, *ids))
    for aid, name, insts in auth:
        conn.execute("INSERT OR IGNORE INTO author (author_id, author_name, pub_finished) VALUES (?,?,?)",
                     (aid, name, "done" if aid in cohort else "no need"))
        if aid in cohort:
            for inst in insts:
                iid = short(inst.get("id"))
                if iid:
                    conn.execute("INSERT OR IGNORE INTO institution VALUES (?,?,?,?)",
                                 (iid, inst.get("display_name"), inst.get("country_code"), inst.get("type")))
                    conn.execute("INSERT OR IGNORE INTO author_institution VALUES (?,?)", (aid, iid))
    return pid


def run_pass(conn, files, number, handle):
    done = {r[0] for r in conn.execute("SELECT file FROM snapshot_progress WHERE pass = ?", (number,))}
    started = time.time()
    for k, path in enumerate(files, 1):
        if path in done:
            continue
        n = 0
        with conn:
            for work in iter_works(path):
                n += handle(work)
            conn.execute("INSERT INTO snapshot_progress VALUES (?,?)", (number, path))
        print(f"pass {number}: {k}/{len(files)} files, {n:,} kept from {os.path.basename(path)} "
              f"({(time.time() - started) / 60:.1f} min)", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--snapshot", required=True, help="folder containing data/jsonl/works/... .gz files")
    p.add_argument("--cohort", required=True, help="CSV with author_id (OpenAlex IDs, e.g. A5012345678)")
    a = p.parse_args()
    cohort = read_cohort(a.cohort)
    files = works_files(a.snapshot)
    conn = get_conn()
    conn.executescript(INST_SQL)
    conn.execute(PROGRESS_SQL)
    print(f"cohort {len(cohort):,} authors, {len(files):,} works files -> {DB_PATH}")

    def own(work):
        if any(aid in cohort for aid, _, _ in authorships(work)):
            save_work(conn, work, "updated", cohort)
            return 1
        return 0

    run_pass(conn, files, 1, own)
    own_ids = {r[0] for r in conn.execute("SELECT pub_id FROM publication WHERE update_status = 'updated'")}
    print(f"pass 1 done: {len(own_ids):,} cohort papers")

    def citing(work):
        hits = [short(r) for r in work.get("referenced_works") or [] if short(r) in own_ids]
        if not hits:
            return 0
        q = short(work.get("id"))
        if q not in own_ids:
            save_work(conn, work, "no need to update", cohort)
        conn.executemany("INSERT OR IGNORE INTO citation (pub_id, cites_pub_id) VALUES (?,?)",
                         [(h, q) for h in hits if h != q])
        return 1

    run_pass(conn, files, 2, citing)
    n_cit = conn.execute("SELECT COUNT(*) FROM citation").fetchone()[0]
    print(f"pass 2 done: {n_cit:,} citation links")
    conn.close()


if __name__ == "__main__":
    main()
