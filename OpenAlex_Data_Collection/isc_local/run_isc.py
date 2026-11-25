"""Equations 7, 8 and 9 (influential self-citation) on the LOCAL database
(database/openalex.db).

SQLite port of  Calculating_ISC/run_isc.py  (cloud PostgreSQL).
isc_calculator.py and models.py in this folder are UNMODIFIED copies of the cloud
files, so Eq 7 / 8 / 9 are the same code. normalize_author_weights and
normalize_fields below are copied verbatim from the cloud run_isc.py.

For every citation pair  q (citing) -> p (cited)  and every field f of p and every
target author a of p:
    Eq 7  ISC(a,p,q,f) = (self + eps*core) / (self + |J|*core + non_overlap)
    Eq 8  TC_adj       = (1 - ISC) * TC_raw        TC_raw = V_p(f)
Eq 9 = sum of TC_adj over EVERY q and f  ->  author_paper_adjusted_citations.

TC_raw is the field share V_p(f) of one citation (the paper's example: TC_raw = 1
for a one-field paper). The author weight W_p(a) is applied once, in Eq 11-15.

Every citing paper is used (no cap, no sampling), as in Eq 9:
    * q shares no author with p -> I and J are empty, so ISC = 0 exactly and
      TC_adj = TC_raw. Eq 7 is only run for citing papers that share authors,
      which keeps the run fast. Only those get influential_self_citations rows.
    * q's authors unknown (no row in author_contribution_weight; run
      collect_co_authors.py on the citing papers first) -> no self-citation can
      be shown, so ISC = 0. These pairs are counted in the summary.
    * a cited paper without author weights or fields is skipped and reported.

Tables created (same columns as the cloud ones; TEXT[] columns are stored as JSON):
    influential_self_citations      (Eq 7 + 8, one row per q, p, author, field)
    author_paper_adjusted_citations (Eq 9,     one row per p, author)

TARGET AUTHORS  (--targets)
    all   (default) every author of every cited paper -- exactly like the cloud script.
    done            only authors with pub_finished = 'done' (optional shortcut:
                    far fewer rows and much faster; NOT what the cloud script does).

Resumable: a cited paper that already has rows is skipped (use --redo to recompute).
Each batch of cited papers is committed on its own, together with its Eq 9 rows.

Usage (from the OpenAlex_Data_Collection folder):
    python -m isc_local.run_isc --dry-run --limit 3
    python -m isc_local.run_isc --limit 20
    python -m isc_local.run_isc
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from decimal import Decimal

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "database"))

from db import DB_PATH, get_conn                            # noqa: E402
from .isc_calculator import calculate_isc                   # noqa: E402
from .models import AuthorWeight, FieldData, ISCResult      # noqa: E402

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

CITED_BATCH = 100              # cited papers per transaction
SQL_IN_CHUNK = 500
SLOTS = range(1, 11)

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS influential_self_citations (
    isc_id                       INTEGER PRIMARY KEY,
    cited_pub_id                 TEXT NOT NULL,
    citing_pub_id                TEXT NOT NULL,
    target_author_id             TEXT NOT NULL,
    field_name                   TEXT NOT NULL,
    field_weight                 REAL NOT NULL,
    target_author_overall_weight REAL NOT NULL,
    self_author_ids              TEXT NOT NULL DEFAULT '[]',
    core_author_ids              TEXT NOT NULL DEFAULT '[]',
    non_overlap_author_ids       TEXT NOT NULL DEFAULT '[]',
    self_influence_sum           REAL NOT NULL DEFAULT 0,
    core_influence_sum           REAL NOT NULL DEFAULT 0,
    non_overlap_influence_sum    REAL NOT NULL DEFAULT 0,
    core_author_count            INTEGER NOT NULL DEFAULT 0,
    epsilon_zero                 REAL NOT NULL DEFAULT 1.0,
    epsilon_value                REAL NOT NULL DEFAULT 0,
    isc_numerator                REAL NOT NULL,
    isc_denominator              REAL NOT NULL,
    isc_value                    REAL NOT NULL,
    raw_citation                 REAL NOT NULL,
    adjusted_citation            REAL NOT NULL,
    calculated_at                TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_isc_pair_author_field
    ON influential_self_citations (cited_pub_id, citing_pub_id, target_author_id, field_name);

CREATE TABLE IF NOT EXISTS author_paper_adjusted_citations (
    cited_pub_id            TEXT NOT NULL,
    target_author_id        TEXT NOT NULL,
    citing_paper_count      INTEGER NOT NULL DEFAULT 0,
    field_row_count         INTEGER NOT NULL DEFAULT 0,
    total_raw_citation      REAL NOT NULL DEFAULT 0,
    total_adjusted_citation REAL NOT NULL DEFAULT 0,
    calculated_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cited_pub_id, target_author_id)
) WITHOUT ROWID;
"""


# --------------------------------------------------- copied verbatim from cloud run_isc.py
def normalize_author_weights(weights, *, pub_id, tolerance):
    """Accepts weights totalling ~1 or ~100 and rescales them to total 1."""
    if not weights:
        raise RuntimeError(f"No author weights found for {pub_id}.")

    total = sum((item.weight for item in weights), ZERO)

    if total <= ZERO:
        raise RuntimeError(f"Author weights for {pub_id} total zero.")

    if abs(total - ONE) <= tolerance:
        scaled_weights = weights
    elif abs(total - HUNDRED) <= tolerance * HUNDRED:
        scaled_weights = [
            AuthorWeight(author_id=item.author_id, weight=item.weight / HUNDRED)
            for item in weights
        ]
    else:
        raise RuntimeError(
            f"Author weights for {pub_id} must total approximately 1 or 100. "
            f"Current total: {total}.")

    scaled_total = sum((item.weight for item in scaled_weights), ZERO)

    if scaled_total <= ZERO:
        raise RuntimeError(f"Normalized author weights for {pub_id} total zero.")

    normalization_factor = ONE / scaled_total

    return [
        AuthorWeight(author_id=item.author_id, weight=item.weight * normalization_factor)
        for item in scaled_weights
    ]


def normalize_fields(fields, *, pub_id, tolerance):
    """Accepts field weights totalling ~1 or ~100 and rescales them to total 1."""
    if not fields:
        raise RuntimeError(f"No field weights found for {pub_id}.")

    total = sum((field.field_weight for field in fields), ZERO)

    if total <= ZERO:
        raise RuntimeError(f"Field weights for {pub_id} total zero.")

    if abs(total - ONE) <= tolerance:
        scaled_fields = fields
    elif abs(total - HUNDRED) <= tolerance * HUNDRED:
        scaled_fields = [
            FieldData(field_name=field.field_name, field_weight=field.field_weight / HUNDRED)
            for field in fields
        ]
    else:
        raise RuntimeError(
            f"Field weights for {pub_id} must total approximately 1 or 100. "
            f"Current total: {total}.")

    scaled_total = sum((field.field_weight for field in scaled_fields), ZERO)

    if scaled_total <= ZERO:
        raise RuntimeError(f"Normalized field weights for {pub_id} total zero.")

    normalization_factor = ONE / scaled_total

    return [
        FieldData(field_name=field.field_name,
                  field_weight=field.field_weight * normalization_factor)
        for field in scaled_fields
    ]


# --------------------------------------------------- database access (SQLite)
def chunks(items, size):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_author_weights(conn, pub_ids):
    """{pub_id: [AuthorWeight]} -- same rules as the cloud
    fetch_publication_author_weights. A pub whose author has a NULL weight maps to
    an Exception so the pair is skipped, as in the cloud script."""
    cols = ", ".join(f"author{i}id, author{i}id_weight" for i in SLOTS)
    result = {}
    for part in chunks(pub_ids, SQL_IN_CHUNK):
        marks = ",".join("?" * len(part))
        for row in conn.execute(
                f"SELECT pub_id, {cols} FROM author_contribution_weight "
                f"WHERE pub_id IN ({marks})", part):
            pub_id, items, error = row[0], [], None
            for k in range(1, len(row), 2):
                author_id, weight = row[k], row[k + 1]
                if author_id is None:
                    continue
                author_id = author_id.strip()
                if not author_id:
                    continue
                if weight is None:
                    error = (f"Missing contribution weight for author {author_id} "
                             f"in publication {pub_id}.")
                    break
                items.append(AuthorWeight(author_id=author_id, weight=Decimal(str(weight))))
            result[pub_id] = RuntimeError(error) if error else items
    return result


def fetch_fields(conn, pub_ids):
    """{pub_id: [FieldData]} -- same rules as the cloud fetch_publication_fields."""
    result = {}
    for part in chunks(pub_ids, SQL_IN_CHUNK):
        marks = ",".join("?" * len(part))
        for row in conn.execute(
                "SELECT pub_id, field1_name, field1_weight, field2_name, field2_weight, "
                f"field3_name, field3_weight FROM field_classification "
                f"WHERE pub_id IN ({marks})", part):
            by_name = {}
            for offset in (1, 3, 5):
                name, weight = row[offset], row[offset + 1]
                if not name or weight is None:
                    continue
                name = name.strip()
                if not name:
                    continue
                weight = Decimal(str(weight))
                if weight < 0:
                    raise RuntimeError(f"Negative field weight for {name} in {row[0]}.")
                if weight == 0:
                    continue
                by_name[name] = by_name.get(name, ZERO) + weight
            result[row[0]] = [FieldData(field_name=n, field_weight=w)
                              for n, w in by_name.items()]
    return result


def has_weight_row(conn, pub_ids):
    """Subset of pub_ids that have a row in author_contribution_weight."""
    found = set()
    for part in chunks(pub_ids, SQL_IN_CHUNK):
        marks = ",".join("?" * len(part))
        found.update(r[0] for r in conn.execute(
            f"SELECT pub_id FROM author_contribution_weight WHERE pub_id IN ({marks})", part))
    return found


def isc_row(r: ISCResult):
    return (r.cited_pub_id, r.citing_pub_id, r.target_author_id, r.field_name,
            float(r.field_weight), float(r.target_author_overall_weight),
            json.dumps(r.self_author_ids), json.dumps(r.core_author_ids),
            json.dumps(r.non_overlap_author_ids),
            float(r.self_influence_sum), float(r.core_influence_sum),
            float(r.non_overlap_influence_sum), r.core_author_count,
            float(r.epsilon_zero), float(r.epsilon_value),
            float(r.isc_numerator), float(r.isc_denominator), float(r.isc_value),
            float(r.raw_citation), float(r.adjusted_citation))


INSERT_ISC = (
    "INSERT OR REPLACE INTO influential_self_citations (cited_pub_id, citing_pub_id, "
    "target_author_id, field_name, field_weight, target_author_overall_weight, "
    "self_author_ids, core_author_ids, non_overlap_author_ids, self_influence_sum, "
    "core_influence_sum, non_overlap_influence_sum, core_author_count, epsilon_zero, "
    "epsilon_value, isc_numerator, isc_denominator, isc_value, raw_citation, "
    "adjusted_citation) VALUES (" + ",".join("?" * 20) + ")")


INSERT_APAC = (
    "INSERT INTO author_paper_adjusted_citations (cited_pub_id, target_author_id, "
    "citing_paper_count, field_row_count, total_raw_citation, total_adjusted_citation) "
    "VALUES (?,?,?,?,?,?)")


def candidate_cited_papers(conn, targets):
    """Cited papers to process, sorted: those that have citing papers AND whose
    authors include a target author (or every cited paper for --targets all)."""
    if targets == "all":
        return [r[0] for r in conn.execute("SELECT DISTINCT pub_id FROM citation ORDER BY pub_id")]
    target_ids = {r[0] for r in conn.execute(
        "SELECT author_id FROM author WHERE pub_finished = 'done'")}
    cols = ", ".join(f"author{i}id" for i in SLOTS)
    papers = []
    for row in conn.execute(f"SELECT pub_id, {cols} FROM author_contribution_weight"):
        if any(a in target_ids for a in row[1:] if a):
            papers.append(row[0])
    papers.sort()
    # keep only papers that actually have citing papers
    out = []
    for part in chunks(papers, SQL_IN_CHUNK):
        marks = ",".join("?" * len(part))
        out.extend(r[0] for r in conn.execute(
            f"SELECT DISTINCT pub_id FROM citation WHERE pub_id IN ({marks})", part))
    out.sort()
    return out, target_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None,
                        help="process only the first N cited papers (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="calculate and print, write nothing to the database")
    parser.add_argument("--cited-pub-id", action="append", dest="cited_pub_ids",
                        help="process only this cited paper (repeatable)")
    parser.add_argument("--targets", choices=["done", "all"], default="done",
                        help="which authors of a cited paper are target authors")
    parser.add_argument("--redo", action="store_true",
                        help="recompute cited papers that already have rows")
    parser.add_argument("--epsilon-zero", type=Decimal, default=Decimal("1.0"))   # sweep winner
    parser.add_argument("--weight-tolerance", type=Decimal, default=Decimal("0.02"))
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        sys.exit("--limit must be greater than zero.")
    if args.weight_tolerance < ZERO:
        sys.exit("--weight-tolerance cannot be negative.")
    if not os.path.exists(DB_PATH):
        sys.exit(f"Local database not found: {DB_PATH}")

    conn = get_conn()
    if not args.dry_run:
        conn.executescript(TABLES_SQL)
        conn.commit()
    exists = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}

    print("Selecting cited papers ...", flush=True)
    if args.targets == "all":
        cited_papers = candidate_cited_papers(conn, "all")
        target_ids = None
    else:
        cited_papers, target_ids = candidate_cited_papers(conn, "done")
    if args.cited_pub_ids:
        wanted = set(args.cited_pub_ids)
        cited_papers = [p for p in cited_papers if p in wanted]

    already = set()
    if "author_paper_adjusted_citations" in exists and not args.redo:
        already = {r[0] for r in conn.execute(
            "SELECT DISTINCT cited_pub_id FROM author_paper_adjusted_citations")}
    total_candidates = len(cited_papers)
    todo = [p for p in cited_papers if p not in already]
    if args.limit:
        todo = todo[:args.limit]
    print(f"Targets: {args.targets}. Cited papers: {total_candidates:,} total, "
          f"{total_candidates - len([p for p in cited_papers if p not in already]):,} "
          f"already done, {len(todo):,} to process in this run\n", flush=True)

    batch_size = CITED_BATCH
    processed_pairs = skipped_papers = rows_saved = 0
    overlap_pairs = unknown_author_pairs = 0
    skip_reasons = {}
    started = time.time()

    for start in range(0, len(todo), batch_size):
        batch = todo[start:start + batch_size]
        marks = ",".join("?" * len(batch))

        # Eq 9 sums over ALL papers q that cite p (no cap, no sampling).
        pairs_by_cited = {}
        for cited, citing in conn.execute(
                f"SELECT DISTINCT pub_id, cites_pub_id FROM citation WHERE pub_id IN ({marks})",
                batch):
            if citing is not None and cited != citing:
                pairs_by_cited.setdefault(cited, []).append(citing)
        for cited in pairs_by_cited:
            pairs_by_cited[cited].sort()

        weights = fetch_author_weights(
            conn, set(batch) | {q for qs in pairs_by_cited.values() for q in qs})
        fields = fetch_fields(conn, batch)

        out_rows = []      # Eq 7/8 detail rows (only citing papers that share authors)
        apac_rows = []     # Eq 9 rows
        for cited in batch:
            citing_list = pairs_by_cited.get(cited, [])
            try:
                cited_w = weights.get(cited)
                if isinstance(cited_w, Exception):
                    raise cited_w
                if not cited_w:
                    raise RuntimeError(f"No author weights for cited paper {cited}.")
                if not fields.get(cited):
                    raise RuntimeError(f"No field classification for cited paper {cited}.")
                cited_author_weights = normalize_author_weights(
                    cited_w, pub_id=cited, tolerance=args.weight_tolerance)
                cited_fields = normalize_fields(
                    fields[cited], pub_id=cited, tolerance=args.weight_tolerance)
            except Exception as error:
                skipped_papers += 1
                reason = str(error).split(" for ")[0][:60]
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                if skipped_papers <= 5:
                    print(f"SKIPPED cited paper {cited}: {error}")
                continue

            cited_author_ids = [i.author_id for i in cited_author_weights]
            cited_id_set = set(cited_author_ids)
            targets = [t for t in cited_author_weights
                       if target_ids is None or t.author_id in target_ids]
            if not targets:
                continue
            field_total = sum((f.field_weight for f in cited_fields), ZERO)  # = 1
            raw_sum = {t.author_id: ZERO for t in targets}
            adj_sum = {t.author_id: ZERO for t in targets}

            for citing in citing_list:
                processed_pairs += 1
                citing_w = weights.get(citing)
                citing_author_weights = None
                if citing_w and not isinstance(citing_w, Exception):
                    try:
                        citing_author_weights = normalize_author_weights(
                            citing_w, pub_id=citing, tolerance=args.weight_tolerance)
                    except Exception:
                        citing_author_weights = None
                if citing_author_weights is None:
                    unknown_author_pairs += 1
                shares = (citing_author_weights is not None and any(
                    w.author_id in cited_id_set for w in citing_author_weights))

                if not shares:
                    # No shared author (or authors unknown): I and J are empty,
                    # so ISC = 0 exactly and TC_adj = TC_raw = V_p^f for every f.
                    for t in targets:
                        raw_sum[t.author_id] += field_total
                        adj_sum[t.author_id] += field_total
                    continue

                overlap_pairs += 1
                for field in cited_fields:
                    for t in targets:
                        result = calculate_isc(
                            cited_pub_id=cited, citing_pub_id=citing,
                            cited_author_ids=cited_author_ids,
                            citing_author_weights=citing_author_weights,
                            target_author_id=t.author_id,
                            target_author_overall_weight=t.weight,
                            field_name=field.field_name,
                            field_weight=field.field_weight,
                            epsilon_zero=args.epsilon_zero,
                            weight_tolerance=args.weight_tolerance)
                        raw_sum[t.author_id] += result.raw_citation
                        adj_sum[t.author_id] += result.adjusted_citation
                        out_rows.append(isc_row(result))
                        if args.dry_run and overlap_pairs <= 8:
                            print(f"q={citing} -> p={cited} | author={t.author_id} | "
                                  f"field={field.field_name} | ISC={result.isc_value:.6f} | "
                                  f"raw={result.raw_citation:.6f} | "
                                  f"adjusted={result.adjusted_citation:.6f}")

            for t in targets:
                apac_rows.append((cited, t.author_id, len(citing_list),
                                  len(citing_list) * len(cited_fields),
                                  float(raw_sum[t.author_id]), float(adj_sum[t.author_id])))

        if not args.dry_run:
            with conn:
                conn.execute(f"DELETE FROM influential_self_citations "
                             f"WHERE cited_pub_id IN ({marks})", batch)
                conn.execute(f"DELETE FROM author_paper_adjusted_citations "
                             f"WHERE cited_pub_id IN ({marks})", batch)
                conn.executemany(INSERT_ISC, out_rows)
                conn.executemany(INSERT_APAC, apac_rows)
        rows_saved += len(out_rows)

        done_cited = len(already) + min(start + batch_size, len(todo))
        elapsed = time.time() - started
        print(f"  cited papers: {done_cited:,} / {total_candidates:,} "
              f"({done_cited / max(total_candidates, 1) * 100:.2f}%) | "
              f"pairs {processed_pairs:,} (shared authors {overlap_pairs:,}, "
              f"authors unknown {unknown_author_pairs:,}) | "
              f"{elapsed / 60:.1f} min" + ("  [dry run]" if args.dry_run else ""),
              flush=True)

    print("\n--- summary ---")
    print(f"citation pairs counted:          {processed_pairs:,}")
    print(f"  with shared authors (Eq 7 run): {overlap_pairs:,}")
    print(f"  citing authors unknown (ISC=0): {unknown_author_pairs:,}")
    print(f"cited papers skipped:            {skipped_papers:,}  {skip_reasons or ''}")
    print(f"Eq 7/8 rows {'(would be) ' if args.dry_run else ''}written: {rows_saved:,}")
    if args.dry_run:
        print("[dry run] nothing written to the database")
    conn.close()


if __name__ == "__main__":
    main()
