"""Prepare citation portfolios without treating missing records as zero.

The available author_contribution_weight relation has ten author slots. These
portfolios describe observed links, not independently verified complete careers.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd


@dataclass
class CitationData:
    counts: dict
    quality: pd.DataFrame
    issues: dict


def citation_count(value):
    """Return a nonnegative integer, or None for null/invalid citation counts."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.to_integral_value():
            return None
        return int(number)
    except (InvalidOperation, ValueError, TypeError):
        return None


def prepare_data(authors, publications, authorship):
    """Accept record lists and produce exactly one portfolio per unique author.

    Repeated author/publication links count once. Conflicting citation counts
    for a publication invalidate that publication; identical copies collapse.
    Any unresolved linked paper makes both baselines unavailable for its author.
    No linked publications means unknown, rather than an asserted zero output.
    """
    ids = [row['author_id'] for row in authors]
    if any(not isinstance(key, str) or not key.strip() for key in ids):
        raise ValueError('The author cohort contains a missing or invalid author_id.')
    cohort = sorted(set(ids))
    papers = {}
    duplicate_papers = 0
    conflicting_papers = set()
    for row in publications:
        key = row['pub_id']
        count = citation_count(row.get('total_citation'))
        if key in papers:
            duplicate_papers += 1
            if papers[key] != count:
                conflicting_papers.add(key)
        else:
            papers[key] = count
    for key in conflicting_papers:
        papers[key] = None
    links = {key: set() for key in cohort}
    duplicate_links = orphan_links = null_publication_links = 0
    for row in authorship:
        for slot in range(1, 11):
            key = row.get(f'author{slot}id')
            if key is None or key == '':
                continue
            if key not in links:
                orphan_links += 1
                continue
            paper = row.get('pub_id')
            if paper is None:
                null_publication_links += 1
            if paper in links[key]:
                duplicate_links += 1
            links[key].add(paper)
    counts, quality = {}, []
    for key in cohort:
        linked = links[key]
        missing = sum(p not in papers or p is None for p in linked)
        invalid = sum(p in papers and papers[p] is None for p in linked)
        status = ('NO_LINKED_PUBLICATIONS' if not linked else
                  'INCOMPLETE_CITATION_DATA' if missing or invalid else 'OBSERVED_LINKS_COMPLETE')
        counts[key] = (tuple(papers[p] for p in sorted(linked))
                       if status == 'OBSERVED_LINKS_COMPLETE' else None)
        quality.append(dict(author_id=key, linked_publications=len(linked),
                            missing_publications=missing, invalid_citation_publications=invalid,
                            baseline_data_status=status, full_portfolio_verified=False))
    issues = dict(duplicate_author_id_rows=len(ids) - len(cohort),
                  duplicate_publication_rows=duplicate_papers,
                  conflicting_publication_ids=len(conflicting_papers),
                  duplicate_authorship_links=duplicate_links,
                  orphan_author_slots=orphan_links,
                  null_publication_links=null_publication_links)
    columns = ['author_id', 'linked_publications', 'missing_publications',
               'invalid_citation_publications', 'baseline_data_status', 'full_portfolio_verified']
    return CitationData(counts, pd.DataFrame(quality, columns=columns), issues)


def unavailable(data, name):
    """Keep the full cohort when a definition is unavailable."""
    return pd.Series(pd.NA, index=pd.Index(data.counts, name='author_id'),
                     name=name, dtype='Float64')
