"""Build the label input files for RQ4, RQ5, RQ8 and RQ11 from openalex.db.

Writes (into --out), in the formats of src/external_inputs.SCHEMAS:
  award_labels.csv      author_id, awardee            (RQ4; Wikidata laureate list)
  subgroup_labels.csv   author_id, gender, region, approved_for_analysis,
                        evidence_reference, gender_source   (RQ11)
  scenario_data.csv     RQ5 categories (rules: author decision 2026-11-24)
  future_outcomes.csv   RQ8 outcomes t+1..t+5 (citations, awards, h growth)
  historical_scores.csv RQ8 scores at t, from a pipeline run on the snapshot DB
                        (make_snapshot_db.py), if --historical-db is given

Gender (decision 2026-11-24): Wikidata P21 (via the OpenAlex author ID, P10283)
first, then the offline gender-guesser dictionary on the first name; anything
ambiguous stays 'unknown'. Region: continent of the author's most frequent
institution country (OpenAlex).

Usage (from NM-Index-Empirical-Validation):
  python -m src.build_labels --db ..\\OpenAlex_Data_Collection\\database\\openalex.db ^
      --cohort cohort.csv --laureates ..\\Author_extraction\\cache\\laureate_checkpoint.jsonl ^
      --out inputs --score-year 2019 [--historical-db snapshot_2019.db] [--no-wikidata]
"""

import argparse
import csv
import json
import sqlite3
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

AS_OF_DEFAULT = 2026
SLOTS = range(1, 11)

CONTINENT = {}
for _cont, _codes in {
    'Africa': 'DZ AO BJ BW BF BI CV CM CF TD KM CG CD CI DJ EG GQ ER SZ ET GA GM GH GN GW KE LS LR '
              'LY MG MW ML MR MU YT MA MZ NA NE NG RE RW SH ST SN SC SL SO ZA SS SD TZ TG TN UG EH ZM ZW',
    'Asia': 'AF AM AZ BH BD BT BN KH CN CY GE HK IN ID IR IQ IL JP JO KZ KW KG LA LB MO MY MV MN MM '
            'NP KP OM PK PS PH QA SA SG KR LK SY TW TJ TH TL TR TM AE UZ VN YE',
    'Europe': 'AX AL AD AT BY BE BA BG HR CZ DK EE FO FI FR DE GI GR GG HU IS IE IM IT JE XK LV LI LT '
              'LU MT MD MC ME NL MK NO PL PT RO RU SM RS SK SI ES SJ SE CH UA GB VA',
    'North America': 'AI AG AW BS BB BZ BM BQ VG CA KY CR CU CW DM DO SV GL GD GP GT HT HN JM MQ MX '
                     'MS NI PA PR BL KN LC MF PM VC SX TT TC US VI',
    'South America': 'AR BO BR CL CO EC FK GF GY PY PE SR UY VE',
    'Oceania': 'AS AU CK FJ PF GU KI MH FM NR NC NZ NU NF MP PW PG PN WS SB TK TO TV UM VU WF',
}.items():
    for _c in _codes.split():
        CONTINENT[_c] = _cont


def connect(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    conn.execute('PRAGMA query_only = ON')
    return conn


def q(conn, sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def in_ids(column, ids):
    return f"{column} IN (SELECT value FROM json_each(?))", (json.dumps(list(ids)),)


def read_ids(path):
    with open(path, encoding='utf-8-sig', newline='') as handle:
        return [r['author_id'].strip() for r in csv.DictReader(handle) if r['author_id'].strip()]


def authorship(conn, ids):
    """One row per (author_id, pub_id, position, weight 0-1, year, ordering norm)."""
    cond, params = in_ids('a', ids)
    parts = []
    for i in SLOTS:
        parts.append(f"SELECT author{i}id AS a, pub_id, {i} AS position, "
                     f"author{i}id_weight AS w, author_ordering_norm AS norm "
                     f"FROM author_contribution_weight WHERE author{i}id IS NOT NULL")
    sql = (f"SELECT t.a AS author_id, t.pub_id, t.position, t.w, t.norm, p.year "
           f"FROM ({' UNION ALL '.join(parts)}) t JOIN publication p ON p.pub_id = t.pub_id "
           f"WHERE t.{cond}")
    frame = q(conn, sql, params)
    frame['w'] = pd.to_numeric(frame.w, errors='coerce') / 100.0   # weights stored as % of paper
    return frame


# ------------------------------------------------------------------ RQ4
def award_labels(ids, laureate_file):
    laureates = set()
    if laureate_file and Path(laureate_file).is_file():
        with open(laureate_file, encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    if rec.get('openalex_id'):
                        laureates.add(rec['openalex_id'])
    return pd.DataFrame(dict(author_id=ids, awardee=[a in laureates for a in ids]))


def award_years(laureate_file):
    out = {}
    if laureate_file and Path(laureate_file).is_file():
        with open(laureate_file, encoding='utf-8') as handle:
            for line in handle:
                if line.strip():
                    rec = json.loads(line)
                    y = rec.get('award_year')
                    years = y if isinstance(y, list) else [y]
                    out[rec.get('openalex_id')] = [int(v) for v in years if str(v).isdigit()]
    return out


# ------------------------------------------------------------------ RQ11
def wikidata_gender(ids, pause=1.0):
    """{openalex_id: ('female'|'male'|..., 'wikidata:Q..')} via SPARQL on P10283."""
    import requests
    out = {}
    url = 'https://query.wikidata.org/sparql'
    headers = {'User-Agent': 'nm-index-validation/1.0 (research script)'}
    for start in range(0, len(ids), 200):
        chunk = ids[start:start + 200]
        values = ' '.join(f'"{a}"' for a in chunk)
        query = ('SELECT ?oa ?item ?genderLabel WHERE { VALUES ?oa { ' + values + ' } '
                 '?item wdt:P10283 ?oa ; wdt:P21 ?gender . '
                 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }')
        try:
            resp = requests.get(url, params=dict(query=query, format='json'), headers=headers, timeout=60)
            for b in resp.json()['results']['bindings']:
                out[b['oa']['value']] = (b['genderLabel']['value'],
                                         'wikidata:' + b['item']['value'].rsplit('/', 1)[-1])
        except Exception as exc:                      # keep going; those stay unresolved
            print(f'  Wikidata batch {start} failed: {exc}')
        time.sleep(pause)
    return out


def name_gender(full_name, detector):
    parts = [p for p in str(full_name or '').replace('.', ' ').split() if len(p) > 1]
    if not parts:
        return None
    guess = detector.get_gender(parts[0].capitalize())
    return {'male': 'male', 'female': 'female'}.get(guess)   # mostly_*/andy/unknown -> None


def subgroup_labels(conn, ids, use_wikidata=True):
    cond, params = in_ids('author_id', ids)
    names = q(conn, f"SELECT author_id, author_name FROM author WHERE {cond}", params)
    names = dict(zip(names.author_id, names.author_name))
    cond2, params2 = in_ids('ai.author_id', ids)
    countries = q(conn, "SELECT ai.author_id, i.country_code FROM author_institution ai "
                        f"JOIN institution i ON i.institution_id = ai.institution_id WHERE {cond2}", params2)
    country = (countries.dropna().groupby('author_id').country_code
               .agg(lambda s: Counter(s).most_common(1)[0][0]))
    wiki = wikidata_gender(list(ids)) if use_wikidata else {}
    try:
        import gender_guesser.detector as gg
        detector = gg.Detector(case_sensitive=False)
    except ImportError:
        detector = None
        print('  gender-guesser not installed: name inference skipped (pip install gender-guesser)')
    rows = []
    for a in ids:
        if a in wiki:
            g, ref = wiki[a]
            src = 'wikidata_p21'
        else:
            g = name_gender(names.get(a), detector) if detector else None
            ref, src = (f'gender-guesser:{str(names.get(a) or "").split()[0] if names.get(a) else ""}',
                        'name_inference') if g else ('', 'none')
        cc = country.get(a)
        region = CONTINENT.get(str(cc).upper()) if cc else None
        rows.append(dict(author_id=a, gender=g or 'unknown', region=region or 'unknown',
                         approved_for_analysis=bool(g or region), gender_source=src,
                         evidence_reference=';'.join(x for x in (ref, f'openalex-country:{cc}' if cc else '') if x)
                         or 'none'))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ RQ5
PATTERN = {  # (self I, core J, non-overlap M) -> category
    (True, False, False): 'High single and unique author',
    (False, True, False): 'High other core author overlap with no non-overlap authors',
    (True, False, True): 'High single-author but with non overlapping authors',
    (False, True, True): 'High other overlapping core-authors but with non overlapping authors',
    (True, True, True): 'High single and other core author overlapping with non overlapping authors',
    (True, True, False): 'High single and unique author',
}
NORM_LABEL = {'alphabetical': 'Alphabetical/random ordering', 'relative': 'Relative contribution ordering',
              'explicit_credit': 'Explicit contribution with CRediT', 'explicit_aci': 'Explicit contribution with ACI'}


def scenario_data(conn, ids, links, as_of_year):
    # fields per paper
    pubs = links.pub_id.unique().tolist()
    cond, params = in_ids('pub_id', pubs)
    fld = q(conn, f"SELECT pub_id, field1_name, field1_weight, field2_name, field2_weight, "
                  f"field3_name, field3_weight FROM field_classification WHERE {cond}", params)
    long = pd.concat([fld[['pub_id', f'field{k}_name', f'field{k}_weight']]
                      .set_axis(['pub_id', 'field', 'v'], axis=1) for k in (1, 2, 3)]).dropna()
    long['v'] = pd.to_numeric(long.v, errors='coerce') / 100.0
    share = links.merge(long, on='pub_id').assign(x=lambda d: d.w * d.v)
    by_field = share.groupby(['author_id', 'field']).x.sum().reset_index()
    main = by_field.sort_values('x', ascending=False).drop_duplicates('author_id').set_index('author_id')
    totals = by_field.groupby('author_id').x.sum()

    # self-citation pattern and ISC loss
    cond, params = in_ids('target_author_id', ids)
    isc = q(conn, "SELECT DISTINCT cited_pub_id, citing_pub_id, target_author_id AS author_id, "
                  "self_author_ids, core_author_ids, non_overlap_author_ids "
                  f"FROM influential_self_citations WHERE {cond}", params)
    apac = q(conn, "SELECT target_author_id AS author_id, SUM(citing_paper_count) AS pairs, "
                   "SUM(total_raw_citation) AS raw, SUM(total_adjusted_citation) AS adj "
                   f"FROM author_paper_adjusted_citations WHERE {cond} GROUP BY target_author_id", params)
    apac = apac.set_index('author_id')
    for col in ('self_author_ids', 'core_author_ids', 'non_overlap_author_ids'):
        isc[col] = isc[col].map(lambda v: bool(json.loads(v)) if isinstance(v, str) else False)
    isc['pattern'] = list(zip(isc.self_author_ids, isc.core_author_ids, isc.non_overlap_author_ids))

    weights = links.groupby('author_id').w
    mean_w = weights.mean()
    median_w = mean_w.median()
    rows = []
    for a in ids:
        mine = links.loc[links.author_id == a]
        if mine.empty:
            continue
        first = pd.to_numeric(mine.year, errors='coerce').min()
        pairs = apac.pairs.get(a, 0) or 0
        own = isc.loc[isc.author_id == a]
        if pairs == 0 or len(own) / pairs < 0.05:
            isc_s = 'No overlapping authors'
        else:
            isc_s = PATTERN.get(Counter(own.pattern).most_common(1)[0][0], 'No overlapping authors')
        w = mine.w.dropna()
        if len(w) and (w < 0.10).mean() > 0.5:
            norm = 'Gaming (higher prevalence of many low contribution papers)'
        elif len(w) and (w >= 0.5).mean() > 0.5:
            norm = 'High sole author or high contribution practice'
        else:
            norm = NORM_LABEL.get(Counter(mine.norm.dropna()).most_common(1)[0][0]
                                  if mine.norm.notna().any() else None)
        raw, adj = apac.raw.get(a, np.nan), apac.adj.get(a, np.nan)
        rows.append(dict(
            author_id=a,
            career_years=(as_of_year - first) if pd.notna(first) else np.nan,
            main_domain_percentage=(100 * main.x.get(a) / totals.get(a)) if a in main.index and totals.get(a) else np.nan,
            field_name=main.field.get(a) if a in main.index else None,
            ordering_norm=norm, isc_scenario=isc_s,
            high_relative_contribution=bool(mean_w.get(a, np.nan) >= median_w),
            low_influential_self_citation=bool(raw > 0 and (1 - adj / raw) < 0.10)))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ RQ8
def h_of(values):
    v = sorted(values, reverse=True)
    return sum(c >= i for i, c in enumerate(v, 1))


def future_outcomes(conn, ids, links, t, years_by_author):
    pubs = links.pub_id.unique().tolist()
    cond, params = in_ids('c.pub_id', pubs)
    cites = q(conn, "SELECT c.pub_id, p.year AS citing_year FROM citation c "
                    f"JOIN publication p ON p.pub_id = c.cites_pub_id WHERE {cond} "
                    "AND c.pub_id <> c.cites_pub_id", params)
    cites['citing_year'] = pd.to_numeric(cites.citing_year, errors='coerce')
    upto_t = cites.loc[cites.citing_year <= t].groupby('pub_id').size()
    upto_t5 = cites.loc[cites.citing_year <= t + 5].groupby('pub_id').size()
    window = cites.loc[cites.citing_year.between(t + 1, t + 5)].groupby('pub_id').size()
    rows = []
    for a, mine in links.groupby('author_id'):
        if a not in set(ids):
            continue
        p_t = mine.loc[pd.to_numeric(mine.year, errors='coerce') <= t, 'pub_id']
        p_t5 = mine.loc[pd.to_numeric(mine.year, errors='coerce') <= t + 5, 'pub_id']
        rows.append(dict(
            author_id=a, outcome_start_year=t + 1, outcome_end_year=t + 5,
            future_citations=int(window.reindex(mine.pub_id).fillna(0).sum()),
            future_awards=sum(t + 1 <= y <= t + 5 for y in years_by_author.get(a, [])),
            h_index_growth=h_of(upto_t5.reindex(p_t5).fillna(0)) - h_of(upto_t.reindex(p_t).fillna(0))))
    return pd.DataFrame(rows)


def historical_scores(path, ids, t):
    conn = connect(path)
    cond, params = in_ids('author_id', ids)
    frame = q(conn, f"SELECT author_id, nm_index FROM author_nm_index WHERE {cond}", params).dropna()
    conn.close()
    return frame.assign(score_year=t)[['author_id', 'score_year', 'nm_index']]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', required=True)
    parser.add_argument('--cohort', required=True)
    parser.add_argument('--laureates', help='laureate_checkpoint.jsonl from Author_extraction')
    parser.add_argument('--out', required=True)
    parser.add_argument('--as-of-year', type=int, default=AS_OF_DEFAULT)
    parser.add_argument('--score-year', type=int, default=2019)
    parser.add_argument('--historical-db', help='snapshot DB after running the pipeline at --score-year')
    parser.add_argument('--no-wikidata', action='store_true')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    conn = connect(args.db)
    ids = read_ids(args.cohort)
    links = authorship(conn, ids)

    award_labels(ids, args.laureates).to_csv(out / 'award_labels.csv', index=False)
    sub = subgroup_labels(conn, ids, use_wikidata=not args.no_wikidata)
    sub.to_csv(out / 'subgroup_labels.csv', index=False)
    scenario_data(conn, ids, links, args.as_of_year).to_csv(out / 'scenario_data.csv', index=False)
    future_outcomes(conn, ids, links, args.score_year,
                    award_years(args.laureates)).to_csv(out / 'future_outcomes.csv', index=False)
    if args.historical_db:
        historical_scores(args.historical_db, ids, args.score_year).to_csv(
            out / 'historical_scores.csv', index=False)
    conn.close()
    print(f'labels written to {out}: gender known {int(sub.gender.ne("unknown").sum()):,} '
          f'({sub.gender_source.value_counts().to_dict()}), region known '
          f'{int(sub.region.ne("unknown").sum()):,} of {len(ids):,}')


if __name__ == '__main__':
    main()
