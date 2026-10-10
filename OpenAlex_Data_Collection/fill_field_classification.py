"""Field classification for the LOCAL database (database/openalex.db).

Same model and same logic as
    asjc fine tunned/my_custom_asjc_model/feildclassification.py
but it reads publications from, and writes `field_classification` to, the local
SQLite database instead of PostgreSQL.

For every publication with publication.field_classified = 'not done':
    text  = "title={<title>}, abstract={<abstract>}"
    run the local fine-tuned ASJC model (no API call)
    keep the top 3 fields, normalise their scores so the three sum to 100
    store them in field_classification (field1..3 name + weight)
    set publication.field_classified = 'done' (same transaction as the insert)

Resumable: 'done' publications are never reselected, and every chunk is
committed on its own, so an interrupted run just continues.

Usage:
    python fill_field_classification.py                 # every unclassified publication
    python fill_field_classification.py --limit 100     # only the next 100 (testing)
    python fill_field_classification.py --dry-run       # classify + print, write nothing
    python fill_field_classification.py --status "need to update"
                                                         # only publications with that update_status
"""

import argparse
import os
import sys

import torch
from transformers import pipeline, TextClassificationPipeline

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))

from db import DB_PATH, get_conn                        # noqa: E402

MODEL_PATH = os.getenv("ASJC_MODEL_PATH") or os.path.normpath(
    os.path.join(HERE, "..", "asjc fine tunned", "my_custom_asjc_model"))
CHUNK_SIZE = 64        # publications per DB read / commit
INFER_BATCH = 16       # texts per model forward pass

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS field_classification (
    pub_id        TEXT PRIMARY KEY,
    field1_name   TEXT, field1_weight REAL,
    field2_name   TEXT, field2_weight REAL,
    field3_name   TEXT, field3_weight REAL
)
"""


# ---------------- CUSTOM PIPELINE (same as the PostgreSQL script) ----------------
class ASJCMultiLabelPipeline(TextClassificationPipeline):
    """Returns every field with its sigmoid score, best first (no threshold)."""
    def postprocess(self, model_outputs, **kwargs):
        scores = torch.sigmoid(model_outputs["logits"]).tolist()
        results = [{"label": self.model.config.id2label[i], "score": float(score)}
                   for i, score in enumerate(scores[0])]
        return sorted(results, key=lambda x: x["score"], reverse=True)


def top3(predictions):
    """-> ([name1, name2, name3], [w1, w2, w3]) with weights summing to 100."""
    if predictions and isinstance(predictions[0], list):   # extra batch list
        predictions = predictions[0]
    best = predictions[:3]
    total = sum(p["score"] for p in best)
    names = [None, None, None]
    weights = [None, None, None]
    for i, p in enumerate(best):
        names[i] = p["label"]
        weights[i] = round(p["score"] / total * 100, 2) if total > 0 else 0.0
    return names, weights


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N publications in total (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="classify and print, write nothing to the database")
    parser.add_argument("--status", default=None,
                        help="only publications whose update_status equals this")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit(f"Local database not found: {DB_PATH}")
    if not os.path.exists(os.path.join(MODEL_PATH, "model.safetensors")):
        sys.exit(f"Model not found at {MODEL_PATH} (set ASJC_MODEL_PATH to override)")

    device = 0 if torch.cuda.is_available() else -1
    print(f"Loading model from {MODEL_PATH} on {'GPU' if device == 0 else 'CPU'} ...")
    pipe = pipeline(task="text-classification", model=MODEL_PATH, tokenizer=MODEL_PATH,
                    pipeline_class=ASJCMultiLabelPipeline, device=device)
    print("Model loaded.\n")

    conn = get_conn()
    columns = [r[1] for r in conn.execute("PRAGMA table_info(publication)")]
    if "field_classified" not in columns:
        sys.exit("publication.field_classified column is missing -- add it first "
                 "(ALTER TABLE publication ADD COLUMN field_classified TEXT "
                 "DEFAULT 'not done')")
    if not args.dry_run:
        conn.execute(TABLE_SQL)
        conn.commit()

    # COUNT(*) on an index / primary key: fast even on millions of rows
    total_pubs = conn.execute("SELECT COUNT(*) FROM publication").fetchone()[0]
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'field_classification'").fetchone()
    already_done = (conn.execute("SELECT COUNT(*) FROM field_classification").fetchone()[0]
                    if has_table else 0)
    print(f"Field classification so far: {already_done:,} done / {total_pubs:,} total "
          f"({already_done / total_pubs * 100:.2f}%), {total_pubs - already_done:,} left\n")

    where = "p.rowid > ? AND p.field_classified = 'not done'"
    params_extra = []
    if args.status:
        where += " AND p.update_status = ?"
        params_extra.append(args.status)
    sql = (f"SELECT p.rowid, p.pub_id, p.pub_title, p.abstract FROM publication p "
           f"WHERE {where} ORDER BY p.rowid LIMIT ?")

    done = 0
    last_rowid = 0
    while True:
        want = CHUNK_SIZE if not args.limit else min(CHUNK_SIZE, args.limit - done)
        if want <= 0:
            break
        rows = conn.execute(sql, [last_rowid, *params_extra, want]).fetchall()
        if not rows:
            break
        last_rowid = rows[-1][0]

        texts = [f"title={{{t or ''}}}, abstract={{{a or ''}}}" for _, _, t, a in rows]
        predictions = pipe(texts, truncation=True, max_length=512, batch_size=INFER_BATCH)

        out = []
        for (_, pub_id, _, _), preds in zip(rows, predictions):
            names, weights = top3(preds)
            out.append((pub_id, names[0], weights[0], names[1], weights[1],
                        names[2], weights[2]))
            if args.dry_run:
                print(f"{pub_id}: 1) {names[0]} ({weights[0]}%)  "
                      f"2) {names[1]} ({weights[1]}%)  3) {names[2]} ({weights[2]}%)")

        if not args.dry_run:
            with conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO field_classification (pub_id, field1_name, "
                    "field1_weight, field2_name, field2_weight, field3_name, field3_weight) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)", out)
                conn.executemany(
                    "UPDATE publication SET field_classified = 'done' WHERE pub_id = ?",
                    [(r[0],) for r in out])
        done += len(rows)
        overall = already_done + (0 if args.dry_run else done)
        print(f"  overall: {overall:,} / {total_pubs:,} "
              f"({overall / total_pubs * 100:.2f}%)" +
              ("  [dry run]" if args.dry_run else ""), flush=True)

    overall = already_done + (0 if args.dry_run else done)
    print(f"\nDone. Classified this run: {done:,}"
          + ("  [dry run - nothing written]" if args.dry_run else ""))
    print(f"Overall: {overall:,} done / {total_pubs:,} total "
          f"({overall / total_pubs * 100:.2f}%), {total_pubs - overall:,} left")
    conn.close()


if __name__ == "__main__":
    main()
