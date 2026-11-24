"""Comparison (baseline) indices with standard published definitions.

Definitions chosen by the author (decision 2026-11-24):
  hm  Schreiber (2008): papers sorted by citations; r_eff(r) = sum_{i<=r} 1/N_i;
      hm = max r_eff(r) with c_r >= r_eff(r).
  hf  fractional h: papers ranked by c_p/N_p; largest h with c_h/N_h >= h.
  m   Hirsch (2005): m = h / (as_of - first_year + 1).
  AR  Jin et al. (2007): AR = sqrt( sum over the h-core of c_j / a_j ),
      a_j = as_of - year_j + 1.
  s   Kacem et al. (2020): h-index of the per-paper self-citation counts
      (citing papers that include the author).
  C   Ioannidis et al. (2016): six indicators NC, H, Hm, NCS (single-author
      papers), NCSF (single+first), NCSFL (single+first+last); each
      log(1+x) / max over the cohort of log(1+x); C = sum of the six.
  Fi  Fiorillo (2024): Fi = h^2 / total citations * 100 (all citations,
      self-citations included); values above 32 flag self-distorted profiles.
  C-SC Ioannidis et al. (2019): the same, with every self-citation (citing paper
      sharing ANY author with the cited paper) removed first.

N_i is the number of authors stored for the paper (up to 10 database slots, so
papers with more than 10 authors are counted as 10 -- a known limitation).
Self-citation counts come from the pipeline's influential_self_citations table;
without it, s-index and C-SC are left missing (never assumed zero).
"""

from math import log1p, sqrt

import numpy as np
import pandas as pd

REFERENCE = ('Schreiber 2008; Hirsch 2005; Jin et al. 2007; Kacem et al. 2020; '
             'Ioannidis et al. 2016, 2019')
APPROVAL = 'Author decision 2026-11-24: standard published definitions'
REQUIRED = {'author_id', 'pub_id', 'total_citation', 'year', 'position', 'n_authors'}


def _h(values):
    ordered = sorted(values, reverse=True)
    return sum(v >= rank for rank, v in enumerate(ordered, start=1))


def _hm(cites, n_authors):
    order = np.argsort(-np.asarray(cites, dtype=float), kind='stable')
    r_eff, best = 0.0, 0.0
    for i in order:
        r_eff += 1.0 / n_authors[i]
        if cites[i] >= r_eff:
            best = r_eff
        else:
            break
    return best


def _author_values(group, as_of):
    c = group.total_citation.astype(float).tolist()
    n = group.n_authors.astype(float).tolist()
    h = _h(c)
    years = group.year.astype(float)
    first = years.min()
    top = group.sort_values('total_citation', ascending=False).head(h)
    ages = (as_of - top.year.astype(float) + 1).clip(lower=1)
    single = group.n_authors.eq(1)
    first_pos = group.position.eq(1)
    last_pos = group.position.eq(group.n_authors) & group.n_authors.gt(1)
    return dict(
        h_index=h,
        hm_index=_hm(c, n),
        hf_index=_h([ci / ni for ci, ni in zip(c, n)]),
        m_index=(h / (as_of - first + 1)) if pd.notna(first) and as_of - first + 1 > 0 else np.nan,
        ar_index=sqrt(float((top.total_citation.astype(float) / ages).sum())) if h else 0.0,
        nc=float(sum(c)),
        ncs=float(group.loc[single, 'total_citation'].sum()),
        ncsf=float(group.loc[single | first_pos, 'total_citation'].sum()),
        ncsfl=float(group.loc[single | first_pos | last_pos, 'total_citation'].sum()),
    )


def _composite(table):
    """Ioannidis: sum of log(1+x)/max log(1+x) over the six indicators."""
    cols = ['nc', 'h_index', 'hm_index', 'ncs', 'ncsf', 'ncsfl']
    logs = table[cols].astype(float).apply(np.log1p)
    maxima = logs.max().replace(0, np.nan)
    return (logs / maxima).fillna(0).sum(axis=1).where(table[cols].notna().all(axis=1))


def compute(papers: pd.DataFrame, *, as_of_year: int, self_citations: pd.DataFrame | None = None):
    """papers: one row per (author_id, pub_id) with REQUIRED columns.
    self_citations: optional (pub_id, author_id, self_cites, any_overlap_cites).
    Returns {metric_name: Series indexed by author_id}."""
    missing = REQUIRED - set(papers)
    if missing:
        raise ValueError(f'standard metrics: missing columns {sorted(missing)}')
    data = papers.drop_duplicates(['author_id', 'pub_id']).copy()
    data['total_citation'] = pd.to_numeric(data.total_citation, errors='coerce')
    data['n_authors'] = pd.to_numeric(data.n_authors, errors='coerce').clip(lower=1)
    data['year'] = pd.to_numeric(data.year, errors='coerce')
    bad = data.groupby('author_id')[['total_citation', 'n_authors']].apply(
        lambda g: g.isna().any().any())
    rows = {author: _author_values(group, as_of_year)
            for author, group in data.groupby('author_id', sort=True) if not bad.get(author, True)}
    table = pd.DataFrame.from_dict(rows, orient='index')
    out = {}
    if table.empty:
        return out
    table.index.name = 'author_id'
    table['fi_score'] = np.where(table.nc > 0, table.h_index.astype(float) ** 2 / table.nc * 100, np.nan)
    for name in ('hm_index', 'hf_index', 'm_index', 'ar_index', 'fi_score'):
        out[name] = table[name].astype('Float64').rename(name)
    out['c_score_raw'] = _composite(table).astype('Float64').rename('c_score_raw')

    if self_citations is not None and not self_citations.empty:
        sc = self_citations.copy()
        for col in ('self_cites', 'any_overlap_cites'):
            sc[col] = pd.to_numeric(sc[col], errors='coerce').fillna(0)
        merged = data.merge(sc, on=['author_id', 'pub_id'], how='left')
        merged[['self_cites', 'any_overlap_cites']] = merged[['self_cites', 'any_overlap_cites']].fillna(0)
        out['s_index'] = merged.groupby('author_id').self_cites.apply(
            lambda s: _h(s.tolist())).reindex(table.index).astype('Float64').rename('s_index')
        adjusted = merged.assign(total_citation=(merged.total_citation - merged.any_overlap_cites).clip(lower=0))
        rows = {author: _author_values(group, as_of_year)
                for author, group in adjusted.groupby('author_id', sort=True) if author in table.index}
        sc_table = pd.DataFrame.from_dict(rows, orient='index')
        out['c_score_sc_adjusted'] = _composite(sc_table).astype('Float64').rename('c_score_sc_adjusted')
    for series in out.values():
        series.index.name = 'author_id'
    return out
