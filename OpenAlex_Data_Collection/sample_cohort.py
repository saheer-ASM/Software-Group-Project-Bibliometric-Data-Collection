"""Sample the validation cohort (default 100,000 authors) from the OpenAlex snapshot.

Streams the snapshot's authors files (gzip JSON Lines) twice, BelowNormal priority:
  pass 1  count eligible authors per stratum (field of the author's top topic)
  pass 2  reservoir-sample each stratum to its quota (seeded, reproducible)

Eligible: works_count >= --min-works and cited_by_count >= --min-cites.
Quota: proportional to the stratum's eligible population, at least --min-per-field
(capped at the population). Every laureate in --laureates (OpenAlex IDs) that is
present in the snapshot is always included, on top of the sample.

Career stage is not in OpenAlex author records (no first-publication year), so it
is checked after load_snapshot.py from the papers; re-sample a stratum if needed.

Writes cohort.csv (author_id, author_name, field, laureate) and cohort_strata.csv.

Usage:
  python sample_cohort.py --snapshot E:\\openalex --out cohort.csv ^
      --laureates ..\\Author_extraction\\cache\\laureate_checkpoint.jsonl
"""

import argparse
import csv
import ctypes
import glob
import gzip
import json
import os
import random
import sys
from collections import Counter


def low_priority():
    if os.name == 'nt':
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BelowNormal


def short(url):
    return url.rstrip('/').split('/')[-1] if url else None


def author_files(root):
    files = sorted(glob.glob(os.path.join(root, '**', 'authors', '**', '*.gz'), recursive=True))
    if not files:
        sys.exit(f'No authors/*.gz files under {root}')
    return files


def records(files):
    for path in files:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def stratum(rec):
    topics = rec.get('topics') or []
    if topics:
        field = (topics[0].get('field') or {}).get('display_name')
        if field:
            return field
    return 'Unknown'


def eligible(rec, min_works, min_cites):
    return (rec.get('works_count') or 0) >= min_works and (rec.get('cited_by_count') or 0) >= min_cites


def read_laureates(path):
    ids = set()
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    aid = json.loads(line).get('openalex_id')
                    if aid:
                        ids.add(aid)
    return ids


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--snapshot', required=True)
    p.add_argument('--out', default='cohort.csv')
    p.add_argument('--size', type=int, default=100_000)
    p.add_argument('--min-works', type=int, default=5)
    p.add_argument('--min-cites', type=int, default=10)
    p.add_argument('--min-per-field', type=int, default=200)
    p.add_argument('--laureates', default=None)
    p.add_argument('--seed', type=int, default=2026)
    a = p.parse_args()
    low_priority()
    files = author_files(a.snapshot)
    laureates = read_laureates(a.laureates)

    counts = Counter()
    for rec in records(files):                                   # pass 1
        if eligible(rec, a.min_works, a.min_cites):
            counts[stratum(rec)] += 1
    total = sum(counts.values())
    if not total:
        sys.exit('No eligible authors')
    quota = {s: min(n, max(a.min_per_field, round(a.size * n / total))) for s, n in counts.items()}
    scale = a.size / max(1, sum(quota.values()))                  # keep the total near --size
    quota = {s: min(counts[s], max(min(a.min_per_field, counts[s]), round(q * scale))) for s, q in quota.items()}

    rng = random.Random(a.seed)
    reservoir = {s: [] for s in quota}
    seen = Counter()
    kept_laureates = {}
    for rec in records(files):                                   # pass 2
        aid = short(rec.get('id'))
        row = (aid, rec.get('display_name') or '', stratum(rec))
        if aid in laureates:
            kept_laureates[aid] = row
            continue
        if not eligible(rec, a.min_works, a.min_cites):
            continue
        s = row[2]
        seen[s] += 1
        res = reservoir[s]
        if len(res) < quota[s]:
            res.append(row)
        else:
            j = rng.randrange(seen[s])
            if j < quota[s]:
                res[j] = row

    with open(a.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['author_id', 'author_name', 'field', 'laureate'])
        for aid, name, s in kept_laureates.values():
            w.writerow([aid, name, s, True])
        for res in reservoir.values():
            for aid, name, s in res:
                w.writerow([aid, name, s, False])
    strata = os.path.splitext(a.out)[0] + '_strata.csv'
    with open(strata, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['field', 'eligible', 'sampled'])
        for s in sorted(counts):
            w.writerow([s, counts[s], len(reservoir[s])])
    n = sum(len(r) for r in reservoir.values())
    print(f'{n:,} sampled + {len(kept_laureates):,} laureates from {total:,} eligible in '
          f'{len(counts)} fields -> {a.out}')


if __name__ == '__main__':
    main()
