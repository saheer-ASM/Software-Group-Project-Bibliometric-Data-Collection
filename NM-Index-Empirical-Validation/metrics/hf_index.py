"""Conventional fractional-citation hf, distinct from NM modified Hf′.

Latest manuscript PDF pp. 22-25: rank papers by c_p/N_p and take the largest
h for which the h-th fractional citation count is at least h. Complete
coauthor counts must be verified independently of the ten database slots.
"""

import pandas as pd

from .inputs import citation_count


REQUIRED = {'author_id', 'pub_id', 'total_citation', 'coauthor_count'}


def calculate(papers: pd.DataFrame, *, verified_authorship: bool = False) -> pd.Series:
    if not verified_authorship:
        raise ValueError('hf_index: DATA_REQUIRED; complete coauthor counts must be verified')
    missing = REQUIRED - set(papers.columns)
    if missing:
        raise ValueError(f'hf_index: missing input columns: {sorted(missing)}')
    if papers.author_id.isna().any() or papers.pub_id.isna().any():
        raise ValueError('hf_index: author_id and pub_id must be non-NULL')
    values = {}
    for author, group in papers.groupby('author_id', sort=True):
        duplicate = group.duplicated(['pub_id'], keep=False)
        if duplicate.any() and group.loc[duplicate].groupby('pub_id')[
                ['total_citation', 'coauthor_count']].nunique(dropna=False).gt(1).any().any():
            values[author] = pd.NA
            continue
        unique = group.drop_duplicates('pub_id')
        fractional = []
        for row in unique.itertuples(index=False):
            citations = citation_count(row.total_citation)
            coauthors = citation_count(row.coauthor_count)
            if citations is None or coauthors is None or coauthors < 1:
                fractional = None
                break
            fractional.append(citations / coauthors)
        if fractional is None:
            values[author] = pd.NA
        else:
            values[author] = sum(c >= rank for rank, c in
                                 enumerate(sorted(fractional, reverse=True), start=1))
    return pd.Series(values, name='hf_index', dtype='Int64').rename_axis('author_id')
