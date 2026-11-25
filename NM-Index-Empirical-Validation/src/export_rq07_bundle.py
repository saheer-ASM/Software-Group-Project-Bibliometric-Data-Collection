"""Build the RQ7 (gaming) bundle from the local openalex.db, read-only.

Writes the layout that src/rq07_bundle.load_bundle reads:

  <out>/metadata.json
  <out>/reference/{field_year_means,field_caps,z_means,z_standard_deviations,
                   percentile_reference}.csv          (frozen, whole reference set)
  <out>/graphs/<author>/papers.csv, citation_edges.csv, self_additions.csv,
                   salami_assignments.csv, gift_assignments.csv, self_metadata.json

Gaming scenarios (paper, Table gaming_resistance), all deterministic:
  +50% self-citation : round-half-up(0.5 * own self-citations) NEW papers by the author and
                       a core coauthor, each citing one of the author's papers
                       (most-cited first, round robin). At least 1.
  salami (2x papers, 0.5x cites): each citation of a split paper is put in half
                       1 or 2, alternating per paper (odd: half 1 gets the extra);
                       citations made BY a split paper stay with half 1.
  gift (+30% coauthors): round-half-up(0.3 * own papers) papers by the author's coauthors
                       (author not on them), most-cited first; the author is
                       inserted as a middle author (position len//2 + 1).

Usage (from NM-Index-Empirical-Validation):
  python -m src.export_rq07_bundle --db path\\to\\openalex.db --cohort cohort.csv \\
      --out inputs\\rq07_bundle --as-of-year 2026
"""

import argparse
import csv
import json
import math
import sqlite3
from pathlib import Path

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'OpenAlex_Data_Collection'
                       / 'author_contribution_local'))
from explicit_contribution import (CREDIT_ROLES, EQUAL_ROLE_WEIGHT, aci_shares,  # noqa: E402
                                   core_positions, credit_shares, normalise_role)

SLOTS = [f'author{i}id' for i in range(1, 11)]
COMPONENT_SOURCES = {
    't': ('author_total_cites', 'total_cites_score'),
    's': ('author_citations_per_paper', 'citations_per_paper_score'),
    'u': ('author_citation_rate', 'citation_rate_score'),
    'hf': ('author_modified_hindex', 'modified_hindex_final'),
    'hm': ('author', 'modified_hm_index'),
    'g': ('modified_g_index_results', 'modified_g_index'),
}


def connect(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    conn.execute('PRAGMA query_only = ON')
    return conn


def read_ids(path):
    with open(path, encoding='utf-8-sig', newline='') as handle:
        return [row['author_id'].strip() for row in csv.DictReader(handle) if row['author_id'].strip()]


def query(conn, sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def in_list(conn, sql_head, column, ids, extra=''):
    """SELECT ... WHERE column IN (json list) -- one bound value."""
    return query(conn, f"{sql_head} WHERE {column} IN (SELECT value FROM json_each(?)) {extra}",
                 (json.dumps(list(ids)),))


# ------------------------------------------------------------------ papers
def paper_rows(conn, pub_ids):
    if not pub_ids:
        return pd.DataFrame()
    acw = in_list(conn, f"SELECT pub_id, author_ordering_norm, {', '.join(SLOTS)} "
                        "FROM author_contribution_weight", 'pub_id', pub_ids)
    pub = in_list(conn, "SELECT pub_id, year, total_citation FROM publication", 'pub_id', pub_ids)
    fld = in_list(conn, "SELECT pub_id, field1_name, field1_weight, field2_name, field2_weight, "
                        "field3_name, field3_weight FROM field_classification", 'pub_id', pub_ids)
    frame = pub.merge(acw, on='pub_id', how='inner').merge(fld, on='pub_id', how='inner')
    stmts = {}
    has_stmt = conn.execute("SELECT 1 FROM sqlite_master WHERE name = "
                            "'author_contribution_statement'").fetchone()
    if has_stmt:
        st = in_list(conn, "SELECT pub_id, position, aci_share, credit_roles, equal_contrib "
                           "FROM author_contribution_statement", 'pub_id', pub_ids)
        for r in st.itertuples(index=False):
            stmts.setdefault(r.pub_id, {})[int(r.position)] = dict(
                aci_share=r.aci_share, credit_roles=r.credit_roles, equal_contrib=r.equal_contrib)
    out = []
    for r in frame.itertuples(index=False):
        authors = [a for a in (getattr(r, s) for s in SLOTS) if a]
        authors = list(dict.fromkeys(authors))
        weights = {}
        for k in (1, 2, 3):
            name, w = getattr(r, f'field{k}_name'), getattr(r, f'field{k}_weight')
            if name and w is not None and w > 0:
                weights[name] = weights.get(name, 0) + float(w)
        total = sum(weights.values())
        if not authors or total <= 0 or pd.isna(r.year):
            continue
        row = dict(pub_id=r.pub_id, authors=authors, year=int(r.year),
                   field_weights={k: v / total for k, v in weights.items()},
                   contribution_mode='uniform' if r.author_ordering_norm == 'alphabetical' else 'relative',
                   total_citation=int(r.total_citation or 0))
        # same model choice as the production weights (Eq 2, 4-6)
        st = stmts.get(r.pub_id, {})
        n = len(authors)
        aci = aci_shares(st, n)
        credit = None if aci else credit_shares(st, n)
        if r.author_ordering_norm == 'explicit_aci' and aci:
            row.update(contribution_mode='aci', aci_shares=dict(zip(authors, aci)))
        elif r.author_ordering_norm == 'explicit_credit' and credit:
            roles = {a: sorted({normalise_role(x) for x in json.loads(st[i + 1]['credit_roles'])} - {None})
                     for i, a in enumerate(authors)}
            row.update(contribution_mode='credit', credit_roles=roles,
                       credit_role_weights={role: EQUAL_ROLE_WEIGHT for role in CREDIT_ROLES})
        elif row['contribution_mode'] == 'relative':
            first, last = core_positions(st, n)
            row.update(first_positions=first or [], last_positions=last or [])
        out.append(row)
    return pd.DataFrame(out)


def write_papers(path, frame, extra_cols=()):
    frame = frame.copy()
    optional = [c for c in ('first_positions', 'last_positions', 'aci_shares',
                            'credit_roles', 'credit_role_weights') if c in frame]
    for col in ('authors', 'field_weights', *optional):
        frame[col] = frame[col].map(lambda v: json.dumps(v) if isinstance(v, (list, dict)) else None)
    cols = ['pub_id', 'authors', 'year', 'field_weights', 'contribution_mode',
            'total_citation', *optional, *extra_cols]
    frame.reindex(columns=cols).to_csv(path, index=False)


# ------------------------------------------------------------------ per author
def round_half_up(value):
    return max(1, int(value + 0.5))      # author decision 2026-11-24


def author_graph(conn, author, out_root, as_of_year, latest_year=None):
    own_ids = sorted({r[0] for r in conn.execute(
        'SELECT pub_id FROM author_contribution_weight WHERE '
        + ' OR '.join(f'{s} = ?' for s in SLOTS), [author] * 10)})
    own_meta = paper_rows(conn, own_ids)
    if own_meta.empty:
        return None
    coauthors = sorted({a for authors in own_meta.authors for a in authors} - {author})

    # gift candidates: coauthors' papers without the author, most-cited first
    gift_ids = []
    if coauthors:
        candidate_ids = {r[0] for r in conn.execute(
            'SELECT DISTINCT pub_id FROM author_contribution_weight WHERE '
            + ' OR '.join(f'{s} IN (SELECT value FROM json_each(?))' for s in SLOTS),
            [json.dumps(coauthors)] * 10)} - set(own_ids)
        cand = paper_rows(conn, sorted(candidate_ids))
        if not cand.empty:
            cand = cand.loc[cand.authors.map(lambda a: author not in a)]
            cand = cand.sort_values(['total_citation', 'pub_id'], ascending=[False, True])
            gift_ids = cand.pub_id.head(round_half_up(0.3 * len(own_meta))).tolist()

    cited_set = sorted(set(own_meta.pub_id) | set(gift_ids))
    edges = in_list(conn, "SELECT DISTINCT pub_id AS cited_pub_id, cites_pub_id AS citing_pub_id "
                          "FROM citation", 'pub_id', cited_set)
    edges = edges.loc[edges.cited_pub_id != edges.citing_pub_id]
    papers = paper_rows(conn, sorted(set(cited_set) | set(edges.citing_pub_id)))
    known = set(papers.pub_id)
    edges = edges.loc[edges.cited_pub_id.isin(known) & edges.citing_pub_id.isin(known)].copy()
    edges = edges.sort_values(['cited_pub_id', 'citing_pub_id']).reset_index(drop=True)
    edges['citation_id'] = edges.cited_pub_id + '>' + edges.citing_pub_id
    # citation count = observed citing edges (same basis as the ISC pipeline; the
    # stored OpenAlex count may include citing papers that were never collected)
    counts = edges.groupby('cited_pub_id').size()
    papers['total_citation'] = papers.pub_id.map(counts).fillna(0).astype(int)
    by_id = papers.set_index('pub_id')
    own = papers.loc[papers.pub_id.isin(own_ids)].sort_values(['total_citation', 'pub_id'],
                                                               ascending=[False, True])
    gift_ids = [g for g in gift_ids if g in known]

    self_edges = edges.loc[edges.cited_pub_id.isin(own.pub_id)
                           & edges.citing_pub_id.map(lambda q: author in by_id.at[q, 'authors'])]
    original_self = int(len(self_edges))
    core = coauthors[0] if coauthors else None

    # +50% self-citation additions (round half up, at least 1)
    targets = own.pub_id.tolist()
    additions = []
    for k in range(round_half_up(0.5 * original_self)):
        cited = targets[k % len(targets)]
        new_id = f'SELF_ADD_{author}_{k}'
        fields = by_id.at[cited, 'field_weights']
        main_field = max(fields, key=fields.get)
        # date it in the latest year that has a field/year benchmark (<= as-of)
        year = (latest_year or {}).get(main_field, as_of_year)
        additions.append(dict(pub_id=new_id, authors=[author] + ([core] if core else []),
                              year=year, field_weights=by_id.at[cited, 'field_weights'],
                              contribution_mode='relative', total_citation=0,
                              citation_id=f'{cited}>{new_id}', cited_pub_id=cited))
    # salami halves for every citation of a paper that can be split (own + gift):
    # alternate within each paper, so half 1 = ceil, half 2 = floor
    split = edges.loc[edges.cited_pub_id.isin(cited_set)].copy()
    split['half'] = split.groupby('cited_pub_id').cumcount() % 2 + 1
    salami = split[['citation_id', 'half']].copy()
    # citations MADE by a split paper: the first half keeps them
    outgoing = edges.loc[edges.citing_pub_id.isin(cited_set), 'citation_id']
    salami = salami.merge(pd.DataFrame(dict(citation_id=outgoing, citing_half=1)),
                          on='citation_id', how='outer')
    salami['half'] = salami.half.fillna(1).astype(int)
    salami['citing_half'] = salami.citing_half.fillna(1).astype(int)
    gift_rows = [dict(pub_id=g, position=len(by_id.at[g, 'authors']) // 2 + 1) for g in gift_ids]

    folder = out_root / 'graphs' / author
    folder.mkdir(parents=True, exist_ok=True)
    write_papers(folder / 'papers.csv', papers)
    edges[['citation_id', 'cited_pub_id', 'citing_pub_id']].to_csv(folder / 'citation_edges.csv', index=False)
    additions = pd.DataFrame(additions)
    for col in ('first_positions', 'last_positions', 'aci_shares', 'credit_roles',
                'credit_role_weights'):
        if col in papers and col not in additions:
            additions[col] = [[] if col.endswith('positions') else None] * len(additions)
    write_papers(folder / 'self_additions.csv', additions, ('citation_id', 'cited_pub_id'))
    salami.to_csv(folder / 'salami_assignments.csv', index=False)
    pd.DataFrame(gift_rows, columns=['pub_id', 'position']).to_csv(folder / 'gift_assignments.csv', index=False)
    (folder / 'self_metadata.json').write_text(json.dumps(dict(
        career_start_year=int(own.year.min()), original_self_citation_count=original_self,
        relevant_core_authors=[core] if core else [])), encoding='utf-8')
    return author


# ------------------------------------------------------------------ frozen reference
def hm_field_reference(conn, ids):
    rows = in_list(conn, "SELECT author_id, field_name, career_factor * author_field_weight AS contrib, "
                         "effective_citation FROM author_paper_field_effective_citation",
                   'author_id', ids, "AND calculation_status = 'READY'")
    values = {}
    for (author, field), g in rows.groupby(['author_id', 'field_name']):
        g = g.sort_values('effective_citation', ascending=False)
        r_eff, best = 0.0, 0.0
        for c, e in zip(g.contrib, g.effective_citation):
            r_eff += c
            if e >= r_eff:
                best = r_eff
        values.setdefault(field, []).append(best)
    return {f: float(np.mean(v)) for f, v in values.items()}


def write_reference(conn, ids, out_root):
    ref = out_root / 'reference'
    ref.mkdir(parents=True, exist_ok=True)
    fy = query(conn, "SELECT field_name AS field, publication_year AS year, "
                     "citation_avg_field_and_year AS mean_adjusted_citations "
                     "FROM field_year_adjusted_citation_average")
    fa = query(conn, "SELECT field_name AS field, citation_avg_field AS field_mean_adjusted_citations "
                     "FROM field_adjusted_citation_average")
    fy.merge(fa, on='field', how='inner').dropna().to_csv(ref / 'field_year_means.csv', index=False)
    caps = query(conn, "SELECT field_name AS field, cap_threshold AS cap FROM field_citation_percentile_caps")
    hf = query(conn, "SELECT field_name AS field, AVG(field_normalization) AS hf_reference "
                     "FROM author_field_modified_hindex GROUP BY field_name")
    g = query(conn, "SELECT field_name AS field, g_field_reference AS g_reference FROM g_index_field_reference")
    hm = pd.DataFrame(sorted(hm_field_reference(conn, ids).items()), columns=['field', 'hm_reference'])
    (caps.merge(hf, on='field').merge(hm, on='field').merge(g, on='field').dropna()
         .to_csv(ref / 'field_caps.csv', index=False))
    long = []
    for metric, (table, column) in COMPONENT_SOURCES.items():
        frame = in_list(conn, f"SELECT author_id, {column} AS value FROM {table}", 'author_id', ids)
        long.append(frame.assign(metric=metric))
    nm = in_list(conn, "SELECT author_id, nm_index AS value FROM author_nm_index", 'author_id', ids)
    long.append(nm.assign(metric='nm_index'))
    values = pd.concat(long, ignore_index=True).dropna()
    complete = set.intersection(*(set(values.loc[values.metric.eq(m), 'author_id'])
                                  for m in (*COMPONENT_SOURCES, 'nm_index')))
    values = values.loc[values.author_id.isin(complete)]
    values[['author_id', 'metric', 'value']].to_csv(ref / 'percentile_reference.csv', index=False)
    z = []
    for metric in ('t', 's', 'u'):
        logs = np.log10(values.loc[values.metric.eq(metric), 'value'].clip(lower=0) + 1)
        z.append(dict(metric=metric, mean=float(logs.mean()), sd=float(logs.std(ddof=1)),
                      distribution='hooked_power_law'))
    pd.DataFrame(z)[['metric', 'mean', 'distribution']].to_csv(ref / 'z_means.csv', index=False)
    pd.DataFrame(z)[['metric', 'sd']].to_csv(ref / 'z_standard_deviations.csv', index=False)
    return sorted(complete)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', required=True)
    parser.add_argument('--cohort', required=True, help='CSV with author_id (the selected authors)')
    parser.add_argument('--reference', help='CSV with author_id of the frozen reference set '
                                            '(default: the cohort)')
    parser.add_argument('--out', required=True)
    parser.add_argument('--as-of-year', type=int, default=2026)
    parser.add_argument('--version', default='openalex-local')
    args = parser.parse_args()
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    conn = connect(args.db)
    cohort = read_ids(args.cohort)
    reference_ids = read_ids(args.reference) if args.reference else cohort
    complete = write_reference(conn, reference_ids, out_root)
    fy = query(conn, 'SELECT field_name, MAX(publication_year) AS y FROM field_year_adjusted_citation_average '
                     'WHERE publication_year <= ? GROUP BY field_name', (args.as_of_year,))
    latest_year = dict(zip(fy.field_name, fy.y.astype(int)))
    done = [a for a in cohort if a in set(complete)
            and author_graph(conn, a, out_root, args.as_of_year, latest_year)]
    (out_root / 'metadata.json').write_text(json.dumps(dict(
        version=args.version, as_of_year=args.as_of_year, epsilon_0=1.0,
        career_boost=2.0, career_decay=0.15, component_weights=[1 / 6] * 6), indent=2),
        encoding='utf-8')
    pd.DataFrame(dict(author_id=done)).to_csv(out_root / 'exported_authors.csv', index=False)
    print(f'reference authors: {len(complete):,}; graphs written: {len(done):,} -> {out_root}')


if __name__ == '__main__':
    main()
