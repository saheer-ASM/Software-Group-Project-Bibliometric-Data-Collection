"""Seeded synthetic benchmark: SOTA comparison, ablation and dose-response.

SYNTHETIC DATA -- for checking that the experiments are implemented and behave
plausibly before the 100,000-author data exist. Not empirical results.

Each seed ("cycle") generates a fresh author population with a known latent
quality q (citations per paper-year), two fields with different citation
densities, early- and late-career authors, "hyper-authors" (middle authors on
large, highly cited team papers) and "self-citers". Every metric value of every
seed is written with its running mean to cycles.csv; summary.csv gives mean and
95% CI (t-distribution over seeds).

Experiments
  sota_auc        AUC for identifying the top-20% q authors: Nm vs baselines
  sota_gaming     percentile inflation after manipulation (x = intensity)
  ablation        each Nm component switched off; metric matched to the component
                  no_isc          -> self-citation inflation (x = +50%)
                  no_contribution -> gift-authorship inflation (x = +30%)
                  no_career       -> seniority bias |Spearman(score, career years)|
                  no_field_norm   -> field bias |Spearman(score, dense field)|
                  no_cap          -> AUC
"""

import argparse
import math
import zlib
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, t as student_t

from analysis.counterfactual import FrozenBenchmarks
from metrics import standard
from nm_index.counterfactual_calculator import NMParameters, calculate_nm

AS_OF = 2025
DENSITY = {'DENSE': 3.0, 'SPARSE': 1.0}
COMPONENTS = ('t', 's', 'u', 'hf', 'hm', 'g')
BASELINES = ('raw_total_cites', 'c_score_raw', 'c_score_sc_adjusted', 'h_index', 'hm_index', 'hf_index',
             'g_index', 'm_index', 'fi_score', 's_index', 'ar_index')
# Fi-score and s-index measure self-citation, not merit: evaluated as detectors
DETECTORS = ('s_index', 'fi_score')
MERIT = tuple(b for b in BASELINES if b not in DETECTORS)
VARIANTS = {
    'full': {},
    'no_isc': dict(use_isc=False),
    'no_contribution': dict(use_contribution=False),
    'no_career': dict(career_boost=1.0, career_decay=0.0),
    'no_field_norm': dict(use_field_norm=False),
    'no_cap': dict(use_cap=False),
    'no_multifield': dict(use_multifield=False),
    **{f'no_{c}': dict(weights=tuple(0.0 if i == j else 0.2 for i in range(6)))
       for j, c in enumerate(('T', 'S', 'U', 'Hf', 'Hm', 'G'))},
}


# ------------------------------------------------------------------ population
SIZE = dict(max_papers=20, cite_scale=0.8, outliers=0.0, role_merit=False, merit_auc=False)


def make_population(rng, n_authors):
    authors = []
    for i in range(n_authors):
        a = f'A{i:03d}'
        kind = rng.choice(['normal', 'hyper', 'selfciter'], p=[0.7, 0.15, 0.15])
        field = rng.choice(['DENSE', 'SPARSE'])
        q = float(rng.lognormal(0.0, 0.5))
        start = int(rng.integers(1995, AS_OF - 1))
        n_papers = int(min(SIZE['max_papers'], max(2, rng.poisson(0.8 * (AS_OF - start)) + 1)))
        papers, edges = [], []
        for j in range(n_papers):
            pid = f'{a}_P{j}'
            year = int(rng.integers(start, AS_OF))
            if kind == 'hyper':
                team = int(rng.integers(15, 31))
                pos = int(rng.integers(2, team))           # middle author
                boost = 3.0
            else:
                team = int(rng.integers(1, 6))
                pos = int(rng.integers(1, team + 1))
                boost = 1.0
            others = [f'{pid}_co{k}' for k in range(team - 1)]
            auth = others[:pos - 1] + [a] + others[pos - 1:]
            other = 'SPARSE' if field == 'DENSE' else 'DENSE'
            fw = {field: 0.6, other: 0.4} if rng.random() < SIZE.get('multifield_share', 0.3) else {field: 1.0}
            papers.append(dict(pub_id=pid, authors=tuple(auth), year=year,
                               field_weights=fw, contribution_mode='relative'))
            age = max(1, AS_OF - year)
            if SIZE.get('role_merit'):
                h = [1.0 / k for k in range(1, len(auth) + 1)]
                share = h[pos - 1] / sum(h)
                team_q = share * q + (1 - share) * float(rng.lognormal(0.0, 0.5))
                rate = team_q
            else:
                rate = q
            dens = (sum(w * DENSITY[f] for f, w in fw.items()) if SIZE.get('mixed_density', True)
                    else DENSITY[field])
            n_cite = int(rng.poisson(rate * dens * min(age, 10) * SIZE['cite_scale'] * boost))
            if j == 0 and rng.random() < SIZE['outliers']:
                n_cite *= 20                                  # one extreme outlier paper
            n_self = int(rng.poisson(n_cite)) if kind == 'selfciter' else 0
            for k in range(n_cite + n_self):
                qid = f'{pid}_c{k}'
                cy = int(min(AS_OF, year + 1 + rng.integers(0, max(1, age))))
                cauth = ((a, f'{qid}_x') if k >= n_cite else (f'{qid}_x', f'{qid}_y', f'{qid}_z'))
                papers.append(dict(pub_id=qid, authors=cauth, year=cy, field_weights=fw,
                                   contribution_mode='relative'))
                edges.append(dict(citation_id=f'{pid}>{qid}', cited_pub_id=pid, citing_pub_id=qid))
        authors.append(dict(author_id=a, kind=kind, field=field, q=q, start=start,
                            papers=papers, edges=edges))
    return authors


def frames(author):
    papers = pd.DataFrame(author['papers'])
    edges = pd.DataFrame(author['edges'], columns=['citation_id', 'cited_pub_id', 'citing_pub_id'])
    counts = edges.groupby('cited_pub_id').size()
    papers['total_citation'] = papers.pub_id.map(counts).fillna(0).astype(int)
    return papers, edges


# ------------------------------------------------------------------ frozen reference
def frozen_reference(pop, params):
    """Build field benchmarks and the percentile reference for this population and model variant."""
    ids = [a['author_id'] for a in pop]
    own = []
    for a in pop:
        p, _ = frames(a)
        mine = p.loc[p.authors.map(lambda x: a['author_id'] in x)]
        if SIZE.get('weighted_benchmark', False):
            # each paper counts in every field it belongs to, with its field weight
            own += [(f, int(r.year), r.total_citation, w) for r in mine.itertuples()
                    for f, w in r.field_weights.items()]
        else:
            own += [(a['field'], int(r.year), r.total_citation, 1.0) for r in mine.itertuples()]
    own = pd.DataFrame(own, columns=['field', 'year', 'c', 'w'])
    own['cw'] = own.c * own.w
    fy = (own.groupby(['field', 'year']).cw.sum() / own.groupby(['field', 'year']).w.sum()).clip(lower=0.5)
    fm = (own.groupby('field').cw.sum() / own.groupby('field').w.sum()).clip(lower=0.5)
    years = range(1990, AS_OF + 1)
    fym = pd.DataFrame([dict(field=f, year=y, mean_adjusted_citations=float(fy.get((f, y), fm[f])),
                             field_mean_adjusted_citations=float(fm[f])) for f in fm.index for y in years])
    caps = own.groupby('field').c.quantile(SIZE.get('cap_q', 0.999))

    def tables(refs, values):
        return {'field_year_means': fym,
                'field_caps': pd.DataFrame([dict(field=f, cap=float(caps[f]), hf_reference=refs[f]['hf'],
                                                 hm_reference=refs[f]['hm'], g_reference=refs[f]['g'])
                                            for f in fm.index]),
                'z_means': pd.DataFrame([dict(metric=m, mean=0.0, distribution='hooked_power_law')
                                         for m in ('t', 's', 'u')]),
                'z_standard_deviations': pd.DataFrame([dict(metric=m, sd=1.0) for m in ('t', 's', 'u')]),
                'percentile_reference': values}

    def build(refs, values):
        return FrozenBenchmarks.from_original(ids, tables(refs, values), version='synthetic', synthetic=True)

    dummy = pd.DataFrame([dict(author_id=i, metric=m, value=float(k)) for m in (*COMPONENTS, 'nm_index')
                          for k, i in enumerate(ids)])
    ones = {f: dict(hf=1.0, hm=1.0, g=1.0) for f in fm.index}
    raw = run_all(pop, build(ones, dummy), params)               # pass 1: field h/hm/g references
    refs = {f: {m: max(1e-6, float(np.mean([raw[a['author_id']]['raw_components'][m]
                                            for a in pop if a['field'] == f] or [1.0])))
                for m in ('hf', 'hm', 'g')} for f in fm.index}
    raw = run_all(pop, build(refs, dummy), params)               # pass 2: component distributions
    comp = pd.DataFrame([dict(author_id=i, metric=m, value=float(raw[i]['raw_components'][m]))
                         for i in ids for m in COMPONENTS])
    tmp = pd.concat([comp, dummy.loc[dummy.metric.eq('nm_index')]])
    scores = run_all(pop, build(refs, tmp), params)              # pass 3: Nm distribution
    nm = pd.DataFrame([dict(author_id=i, metric='nm_index', value=float(scores[i]['nm_index'])) for i in ids])
    final = build(refs, pd.concat([comp, nm]))
    return final, {i: scores[i]['nm_index'] for i in ids}


def run_all(pop, frozen, params):
    out = {}
    for a in pop:
        p, e = frames(a)
        out[a['author_id']] = calculate_nm(a['author_id'], p, e, frozen,
                                           career_start_year=a['start'], parameters=params, counterfactual=True)
    return out


# ------------------------------------------------------------------ baselines
def baseline_scores(pop):
    rows = []
    for a in pop:
        p, _ = frames(a)
        mine = p.loc[p.authors.map(lambda x: a['author_id'] in x)].copy()
        mine['author_id'] = a['author_id']
        mine['position'] = mine.authors.map(lambda x: x.index(a['author_id']) + 1)
        mine['n_authors'] = mine.authors.map(len)
        rows.append(mine)
    papers = pd.concat(rows)
    # self-citations per (paper, author): citing paper includes the author (s-index) or
    # shares any author with the cited paper (Ioannidis 2019 C-score adjustment)
    sc = []
    for a in pop:
        p, e = frames(a)
        by_id = dict(zip(p.pub_id, p.authors))
        for cited, grp in e.groupby('cited_pub_id'):
            if a['author_id'] not in by_id[cited]:
                continue
            citing = [by_id[q] for q in grp.citing_pub_id]
            sc.append(dict(pub_id=cited, author_id=a['author_id'],
                           self_cites=sum(a['author_id'] in c for c in citing),
                           any_overlap_cites=sum(bool(set(c) & set(by_id[cited])) for c in citing)))
    std = standard.compute(papers[['author_id', 'pub_id', 'total_citation', 'year', 'position', 'n_authors']],
                           as_of_year=AS_OF, self_citations=pd.DataFrame(sc))
    tot = papers.groupby('author_id').total_citation.sum()
    h = papers.groupby('author_id').total_citation.apply(lambda c: standard._h(c.tolist()))
    g = papers.groupby('author_id').total_citation.apply(g_index)
    out = pd.DataFrame(dict(raw_total_cites=tot, h_index=h, g_index=g))
    for k in ('hf_index', 'hm_index', 'c_score_raw', 'c_score_sc_adjusted', 'm_index', 'fi_score',
              's_index', 'ar_index'):
        out[k] = std[k] if k in std else np.nan
    return out.astype(float)


def g_index(c):
    c = sorted(c, reverse=True)
    g, s = 0, 0
    for k, v in enumerate(c, 1):
        s += v
        if s >= k * k:
            g = k
    return g


def auc(score, label):
    s = pd.Series(score).rank()
    pos = label.astype(bool)
    n1, n0 = pos.sum(), (~pos).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    return float((s[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def pct(value, dist):
    dist = np.sort(np.asarray(dist, float))
    return 100.0 * (np.searchsorted(dist, value, 'left') + np.searchsorted(dist, value, 'right')) / (2 * len(dist))


# ------------------------------------------------------------------ manipulations
def add_self_citations(author, share, rng):
    """Self-citations from the author's EXISTING later papers (new citation edges only,
    no new papers, so per-paper sub-scores are not diluted). Same-field pairs only;
    the number is limited by the available (earlier, later) paper pairs."""
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = sorted((p for p in a['papers'] if author['author_id'] in p['authors']), key=lambda p: p['year'])
    have = {(e['cited_pub_id'], e['citing_pub_id']) for e in a['edges']}
    pairs = [(c, q) for i, c in enumerate(own) for q in own[i + 1:]
             if q['year'] > c['year'] and set(c['field_weights']) <= set(q['field_weights'])
             and (c['pub_id'], q['pub_id']) not in have]
    rng.shuffle(pairs)
    for c, q in pairs[:max(1, round(share * len(author['edges'])))]:
        a['edges'].append(dict(citation_id=f"{c['pub_id']}>{q['pub_id']}", cited_pub_id=c['pub_id'],
                               citing_pub_id=q['pub_id']))
    return a


def add_core_citations(author, share, rng):
    """Core-author self-citations: new papers by a co-author of the cited paper (not the author)."""
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = [p for p in a['papers'] if author['author_id'] in p['authors']]
    with_co = [p for p in own if len(p['authors']) > 1] or own
    organic = len(a['edges'])
    for k in range(max(1, round(share * organic))):
        target = with_co[k % len(with_co)]
        co = next((x for x in target['authors'] if x != author['author_id']), f'{target["pub_id"]}_co')
        qid = f"{target['pub_id']}_cc{k}"
        a['papers'].append(dict(pub_id=qid, authors=(co, f'{qid}_x'), year=AS_OF,
                                field_weights=target['field_weights'], contribution_mode='relative'))
        a['edges'].append(dict(citation_id=f"{target['pub_id']}>{qid}", cited_pub_id=target['pub_id'],
                               citing_pub_id=qid))
    return a


def add_outlier_paper(author, factor, rng):
    """One of the author's papers suddenly receives (factor - 1) x its citations + 20 more."""
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = [p for p in a['papers'] if author['author_id'] in p['authors']]
    target = own[0]
    n = sum(e['cited_pub_id'] == target['pub_id'] for e in a['edges'])
    for k in range(int((factor - 1) * n) + 20):
        qid = f"{target['pub_id']}_out{k}"
        a['papers'].append(dict(pub_id=qid, authors=(f'{qid}_x', f'{qid}_y'), year=AS_OF,
                                field_weights=target['field_weights'], contribution_mode='relative'))
        a['edges'].append(dict(citation_id=f"{target['pub_id']}>{qid}", cited_pub_id=target['pub_id'],
                               citing_pub_id=qid))
    return a


def add_h_targeted(author, share, rng):
    """Self-citations aimed at papers just below the h threshold (boosting h)."""
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = [p for p in a['papers'] if author['author_id'] in p['authors']]
    counts = {p['pub_id']: sum(e['cited_pub_id'] == p['pub_id'] for e in a['edges']) for p in own}
    h = standard._h(list(counts.values()))
    below = sorted((p for p in own if counts[p['pub_id']] <= h), key=lambda p: -counts[p['pub_id']])
    for k, target in enumerate(below[:max(1, round(share * len(own)))]):
        need = h + 1 - counts[target['pub_id']]
        for j in range(max(1, need)):
            qid = f"{target['pub_id']}_ht{k}_{j}"
            a['papers'].append(dict(pub_id=qid, authors=(author['author_id'], f'{qid}_x'), year=AS_OF,
                                    field_weights=target['field_weights'], contribution_mode='relative'))
            a['edges'].append(dict(citation_id=f"{target['pub_id']}>{qid}", cited_pub_id=target['pub_id'],
                                   citing_pub_id=qid))
    return a


def _add_external(author, share, rng, with_coauthor):
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = [p for p in a['papers'] if author['author_id'] in p['authors'] and len(p['authors']) > 1]
    if not own:
        return a
    for k in range(max(1, round(share * len(author['edges'])))):
        target = own[k % len(own)]
        qid = f"{target['pub_id']}_{'fu' if with_coauthor else 'in'}{k}"
        co = next(x for x in target['authors'] if x != author['author_id'])
        auth = ((co,) if with_coauthor else (f'{qid}_w',)) + (f'{qid}_x', f'{qid}_y', f'{qid}_z')
        a['papers'].append(dict(pub_id=qid, authors=auth, year=AS_OF,
                                field_weights=target['field_weights'], contribution_mode='relative'))
        a['edges'].append(dict(citation_id=f"{target['pub_id']}>{qid}", cited_pub_id=target['pub_id'],
                               citing_pub_id=qid))
    return a


def add_followup_citations(author, share, rng):
    """Legitimate follow-up work: a co-author of the cited paper plus 3 independent authors."""
    return _add_external(author, share, rng, True)


def add_independent_citations(author, share, rng):
    """Same number of citations from 4 fully independent authors (reference)."""
    return _add_external(author, share, rng, False)


def add_salami(author, share, rng):
    """Salami slicing: split a share of the author's papers into two half-cited papers."""
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = [p for p in a['papers'] if author['author_id'] in p['authors']]
    for target in own[:max(1, round(share * len(own)))]:
        mine = [e for e in a['edges'] if e['cited_pub_id'] == target['pub_id']]
        twin = dict(target, pub_id=target['pub_id'] + '_half2')
        a['papers'].append(twin)
        for k, e in enumerate(mine):
            if k % 2:                              # every second citation moves to the twin
                a['edges'].remove(e)
                a['edges'].append(dict(e, citation_id=e['citation_id'] + '_h2', cited_pub_id=twin['pub_id']))
    return a


def add_combined(author, share, rng):
    """Gift -> salami -> self-citation, each at the given share."""
    return add_self_citations(add_salami(add_gift_papers(author, share, rng), share, rng), share, rng)


def add_gift_papers(author, share, rng):
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = [p for p in a['papers'] if author['author_id'] in p['authors']]
    mean_c = max(1, round(len(a['edges']) / max(1, len(own))))
    n_gift = int(share) if share >= 1 else max(1, round(share * len(own)))
    rng = np.random.default_rng(zlib.crc32(author['author_id'].encode()))   # same draw at every x (reproducible)
    for k in range(n_gift):
        pid = f"{author['author_id']}_gift{k}"
        team = [f'{pid}_co{i}' for i in range(9)]
        auth = tuple(team[:4] + [author['author_id']] + team[4:])        # middle of 10
        year = int(rng.integers(author['start'], AS_OF))
        a['papers'].append(dict(pub_id=pid, authors=auth, year=year, field_weights={author['field']: 1.0},
                                contribution_mode='relative'))
        for c in range(mean_c * 2):                                        # gift papers are well cited
            qid = f'{pid}_c{c}'
            a['papers'].append(dict(pub_id=qid, authors=(f'{qid}_x', f'{qid}_y'), year=AS_OF,
                                    field_weights={author['field']: 1.0}, contribution_mode='relative'))
            a['edges'].append(dict(citation_id=f'{pid}>{qid}', cited_pub_id=pid, citing_pub_id=qid))
    return a


def sym_change(before, after):
    """Symmetric % change 200(a-b)/(|a|+|b|): defined at 0, bounded to [-200, 200]."""
    if pd.isna(before) or pd.isna(after):
        return np.nan
    denom = abs(after) + abs(before)
    return 0.0 if denom == 0 else 200.0 * (after - before) / denom


def inflation(pop, frozen, params, base, nm_dist, targets, manipulate, share, rng):
    rows = []
    for a in targets:
        p, e = frames(a)
        r0 = calculate_nm(a['author_id'], p, e, frozen, career_start_year=a['start'],
                          parameters=params, counterfactual=True)
        before = r0['nm_index']
        m = manipulate(a, share, rng)
        p2, e2 = frames(m)
        r1 = calculate_nm(a['author_id'], p2, e2, frozen, career_start_year=a['start'],
                          parameters=params, counterfactual=True)
        after = r1['nm_index']
        pb, pa = pct(before, nm_dist), pct(after, nm_dist)
        row = dict(nm_index=100 * (pa - pb) / max(pb, 1.0))
        # value outcome (no percentile ceiling): mean % change of the six raw components
        row['nm_index|value'] = float(np.mean([sym_change(r0['raw_components'][c], r1['raw_components'][c])
                                               for c in COMPONENTS]))
        row['nm_index|score'] = sym_change(before, after)   # weighted Nm score: reflects sub-score weights
        # recompute baselines on the whole population with this author manipulated, so
        # population-scaled indices (C-score: log(1+x)/max) keep the population maxima
        bb = base.loc[a['author_id']]
        ba = baseline_scores([m if x is a else x for x in pop]).loc[a['author_id']]
        for k in MERIT:
            b0, b1 = pct(bb[k], base[k]), pct(ba[k], base[k])
            row[k] = 100 * (b1 - b0) / max(b0, 1.0)
            row[k + '|value'] = sym_change(bb[k], ba[k])
        rows.append(row)
    return pd.DataFrame(rows).mean(skipna=True)


# ------------------------------------------------------------------ one cycle
def one_seed(seed, n_authors, which='all'):
    rng = np.random.default_rng(seed)
    pop = make_population(rng, n_authors)
    q = pd.Series({a['author_id']: a['q'] for a in pop})
    label = q >= q.quantile(0.8)
    years = pd.Series({a['author_id']: AS_OF - a['start'] for a in pop})
    dense = pd.Series({a['author_id']: float(a['field'] == 'DENSE') for a in pop})
    base = baseline_scores(pop)
    normal = [a for a in pop if a['kind'] == 'normal'][:SIZE.get('targets', 6)]
    results = []

    variant_scores = {}
    names = list(VARIANTS) if which in ('all', 'ablation') else ['full']
    for name in names:
        kw = VARIANTS[name]
        params = NMParameters(as_of_year=AS_OF, **kw)
        frozen, nm = frozen_reference(pop, params)
        nm = pd.Series(nm)
        variant_scores[name] = (params, frozen, nm)
        if which == 'sota':
            continue
        if SIZE.get('merit_auc'):      # off: synthetic merit AUC is generator-dependent (decision 2026-11-25)
            results.append(('ablation_auc', name, 0, auc(nm, label)))
        results.append(('ablation_seniority_bias', name, 0, abs(spearmanr(nm, years[nm.index]).statistic)))
        # signed: |rho| has a noise floor of ~0.2 at these sizes (decision 2026-11-25)
        results.append(('ablation_field_bias', name, 0, spearmanr(nm, dense[nm.index]).statistic))
        if name in ('full', 'no_isc'):
            inf = inflation(pop, frozen, params, base, nm.values, normal, add_self_citations, 0.5, rng)
            results.append(('ablation_selfcite_inflation', name, 0.5, inf['nm_index']))
            results.append(('ablation_selfcite_value_change', name, 0.5, inf['nm_index|value']))
        if name.startswith('no_') and name[3:] in ('T', 'S', 'U', 'Hf', 'Hm', 'G') or name == 'full':
            for exp, fn_, x in (('ablation_subscore_salami_score_change', add_salami, 1.0),
                                ('ablation_subscore_outlier_score_change', add_outlier_paper, 20)):
                inf = inflation(pop, frozen, params, base, nm.values, normal, fn_, x, rng)
                results.append((exp, name, x, inf['nm_index|score']))
        if name in ('full', 'no_cap'):
            inf = inflation(pop, frozen, params, base, nm.values, normal, add_outlier_paper, 20, rng)
            results.append(('ablation_outlier_value_change', name, 20, inf['nm_index|value']))
        if name in ('full', 'no_contribution'):
            inf = inflation(pop, frozen, params, base, nm.values, normal, add_gift_papers, 0.3, rng)
            results.append(('ablation_gift_inflation', name, 0.3, inf['nm_index']))
            results.append(('ablation_gift_value_change', name, 0.3, inf['nm_index|value']))

    params, frozen, nm = variant_scores['full']
    if which == 'ablation':
        return pd.DataFrame(results, columns=['experiment', 'method', 'x', 'value']).assign(seed=seed)
    if SIZE.get('merit_auc'):          # merit discrimination only on real award labels (V4)
        results.append(('sota_auc', 'nm_index', 0, auc(nm, label)))
        for k in MERIT:
            results.append(('sota_auc', k, 0, auc(base[k].reindex(nm.index), label)))
    # detectors: AUC for flagging authors after +100% self-citations (higher score = suspicious)
    manip = [add_h_targeted(a, 1.0, rng) for a in normal]
    b0 = base.loc[[a['author_id'] for a in normal]]
    b1 = pd.concat([baseline_scores([m if x is a else x for x in pop]).loc[[a['author_id']]]
                    for a, m in zip(normal, manip)])
    lab = pd.Series([0] * len(b0) + [1] * len(b1))
    for k in DETECTORS:
        results.append(('sota_detection_auc', k, 1.0, auc(pd.concat([b0[k], b1[k]], ignore_index=True), lab)))
    # false penalty: share of legitimate follow-up citation credit kept, relative to the
    # same number of independent citations (1 = kept in full, 0 = all removed)
    for x in (0.25, 0.5, 0.75, 1.0, 1.5):
        fu = inflation(pop, frozen, params, base, nm.values, normal, add_followup_citations, x, rng)
        ind = inflation(pop, frozen, params, base, nm.values, normal, add_independent_citations, x, rng)
        for k in ('nm_index', *MERIT):
            num, den = fu.get(k + '|value'), ind.get(k + '|value')
            if den is not None and pd.notna(den) and abs(den) > 1e-6:
                results.append(('sota_legit_credit_retained', k, x, num / den))
    # 5-point sweeps per gaming scenario (final campaign: full SOTA sweep)
    for exp, fn, xs in (('sota_selfcite_inflation', add_self_citations, (0.25, 0.5, 0.75, 1.0, 1.5)),
                        ('sota_salami_inflation', add_salami, (0.2, 0.4, 0.6, 0.8, 1.0)),
                        ('sota_gift_inflation', add_gift_papers, (0.1, 0.2, 0.3, 0.4, 0.5)),
                        ('sota_combined_inflation', add_combined, (0.1, 0.2, 0.3, 0.4, 0.5))):
        for x in xs:
            inf = inflation(pop, frozen, params, base, nm.values, normal, fn, x, rng)
            for k, v in inf.items():
                kind = 'value_change' if k.endswith('|value') else 'percentile_inflation'
                results.append((f'{exp}_{kind}', k.split('|')[0], x, v))
    return pd.DataFrame(results, columns=['experiment', 'method', 'x', 'value']).assign(seed=seed)


def summarise(cycles):
    def ci(v):
        v = v.dropna()
        n = len(v)
        if n < 2:
            return pd.Series(dict(n=n, mean=v.mean(), ci95_low=np.nan, ci95_high=np.nan))
        half = student_t.ppf(0.975, n - 1) * v.std(ddof=1) / math.sqrt(n)
        return pd.Series(dict(n=n, mean=v.mean(), ci95_low=v.mean() - half, ci95_high=v.mean() + half))
    return cycles.groupby(['experiment', 'method', 'x']).value.apply(ci).unstack().reset_index()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seeds', type=int, default=30)
    parser.add_argument('--experiment', choices=['all', 'sota', 'ablation'], default='all')
    parser.add_argument('--time-budget', type=float, default=None, help='stop starting new seeds after N seconds')
    parser.add_argument('--authors', type=int, default=60)
    parser.add_argument('--max-papers', type=int, default=20)
    parser.add_argument('--cite-scale', type=float, default=0.8)
    parser.add_argument('--targets', type=int, default=6, help='authors manipulated per seed')
    parser.add_argument('--outliers', type=float, default=0.0, help='share of authors with one 20x-cited paper')
    parser.add_argument('--role-merit', action='store_true', help='citations depend on each author contribution share')
    parser.add_argument('--career', default='2.0,0.15', help='C,lambda for the full model')
    parser.add_argument('--out', default='results/synthetic_benchmark')
    args = parser.parse_args()
    SIZE.update(max_papers=args.max_papers, cite_scale=args.cite_scale, targets=args.targets, outliers=args.outliers, role_merit=args.role_merit)
    c, lam = map(float, args.career.split(','))
    for k in VARIANTS:
        if k != 'no_career':
            VARIANTS[k] = dict(VARIANTS[k], career_boost=c, career_decay=lam)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    all_rows = []
    for seed in range(args.seeds):
        if args.time_budget and seed > 0 and time.time() - started > args.time_budget:
            break
        all_rows.append(one_seed(seed, args.authors, args.experiment))
        cycles = pd.concat(all_rows, ignore_index=True)
        cycles = cycles.sort_values(['experiment', 'method', 'x', 'seed'])
        cycles['running_mean'] = cycles.groupby(['experiment', 'method', 'x']).value.transform(
            lambda v: v.expanding().mean())
        cycles.to_csv(out / 'cycles.csv', index=False)           # saved after every cycle
        summarise(cycles).to_csv(out / 'summary.csv', index=False)
        print(f'seed {seed} done, {time.time() - started:.1f} s', flush=True)
    print(f'{len(all_rows)} seed(s) -> {out}')


if __name__ == '__main__':
    main()
