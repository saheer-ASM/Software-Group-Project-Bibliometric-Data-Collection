"""Diagnostics for the three failing gate items (synthetic data, small seeds).

1. Which sub-score carries the residual field / seniority bias (bias of each component).
2. Sub-score ablations on matched metrics: S -> salami change, U -> seniority bias,
   Hf/Hm/G -> outlier-paper change, T -> outlier-paper change.
3. Fi-score detection under h-targeted self-citations (Fiorillo's case) vs spread ones.
"""
import ctypes
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from experiments import synthetic_benchmark as sb
from nm_index.counterfactual_calculator import NMParameters, calculate_nm

if os.name == 'nt':
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)


def add_h_targeted(author, share, rng):
    """Self-citations aimed at papers just below the h threshold (boosting h)."""
    a = dict(author, papers=list(author['papers']), edges=list(author['edges']))
    own = [p for p in a['papers'] if author['author_id'] in p['authors']]
    counts = {p['pub_id']: sum(e['cited_pub_id'] == p['pub_id'] for e in a['edges']) for p in own}
    h = sb.standard._h(list(counts.values()))
    below = sorted((p for p in own if counts[p['pub_id']] <= h), key=lambda p: -counts[p['pub_id']])
    for k, target in enumerate(below[:max(1, round(share * len(own)))]):
        need = h + 1 - counts[target['pub_id']]
        for j in range(max(1, need)):
            qid = f"{target['pub_id']}_ht{k}_{j}"
            a['papers'].append(dict(pub_id=qid, authors=(author['author_id'], f'{qid}_x'), year=sb.AS_OF,
                                    field_weights=target['field_weights'], contribution_mode='relative'))
            a['edges'].append(dict(citation_id=f"{target['pub_id']}>{qid}", cited_pub_id=target['pub_id'],
                                   citing_pub_id=qid))
    return a


def main(seeds=2, n=16):
    sb.SIZE.update(max_papers=8, cite_scale=0.5)
    comp_bias, matched, det = [], [], []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        pop = sb.make_population(rng, n)
        years = pd.Series({a['author_id']: sb.AS_OF - a['start'] for a in pop})
        dense = pd.Series({a['author_id']: float(a['field'] == 'DENSE') for a in pop})
        params = NMParameters(as_of_year=sb.AS_OF)
        frozen, nm = sb.frozen_reference(pop, params)
        res = sb.run_all(pop, frozen, params)
        # 1. bias of each component percentile
        for c in sb.COMPONENTS:
            v = pd.Series({i: r['component_percentiles'][c] for i, r in res.items()})
            comp_bias.append(dict(seed=seed, component=c,
                                  field_bias=abs(spearmanr(v, dense[v.index]).statistic),
                                  seniority_bias=abs(spearmanr(v, years[v.index]).statistic)))
        # 2. matched metrics for sub-score ablations
        normal = [a for a in pop if a['kind'] == 'normal'][:3]
        base = sb.baseline_scores(pop)
        for name in ('full', 'no_T', 'no_S', 'no_U', 'no_Hf', 'no_Hm', 'no_G'):
            p = NMParameters(as_of_year=sb.AS_OF, **sb.VARIANTS[name])
            fz, nmv = sb.frozen_reference(pop, p)
            nmv = pd.Series(nmv)
            sal = sb.inflation(pop, fz, p, base, nmv.values, normal, sb.add_salami, 1.0, rng)['nm_index|value']
            out = sb.inflation(pop, fz, p, base, nmv.values, normal, sb.add_outlier_paper, 20, rng)['nm_index|value']
            matched.append(dict(seed=seed, variant=name, salami_change=sal, outlier_change=out,
                                seniority_bias=abs(spearmanr(nmv, years[nmv.index]).statistic)))
        # 3. Fi detection: spread vs h-targeted self-citations, both score directions
        for scen, fn in (('spread', sb.add_self_citations), ('h_targeted', add_h_targeted)):
            man = [fn(a, 1.0, rng) for a in normal]
            b0 = base.loc[[a['author_id'] for a in normal]]
            b1 = pd.concat([sb.baseline_scores([m if x is a else x for x in pop]).loc[[a['author_id']]]
                            for a, m in zip(normal, man)])
            lab = pd.Series([0] * len(b0) + [1] * len(b1))
            fi = pd.concat([b0.fi_score, b1.fi_score], ignore_index=True)
            det.append(dict(seed=seed, scenario=scen, fi_high=sb.auc(fi, lab), fi_low=sb.auc(-fi, lab),
                            s_index=sb.auc(pd.concat([b0.s_index, b1.s_index], ignore_index=True), lab)))
    print('1. bias per component (mean over seeds)')
    print(pd.DataFrame(comp_bias).groupby('component')[['field_bias', 'seniority_bias']].mean().round(2))
    print('\n2. sub-score ablations on matched metrics')
    print(pd.DataFrame(matched).groupby('variant')[['salami_change', 'outlier_change', 'seniority_bias']].mean().round(2))
    print('\n3. detector AUC')
    print(pd.DataFrame(det).groupby('scenario')[['fi_high', 'fi_low', 's_index']].mean().round(2))


if __name__ == '__main__':
    main(*(int(x) for x in sys.argv[1:]))
