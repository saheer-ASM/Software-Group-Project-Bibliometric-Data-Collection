"""Legacy aggregate-count diagnostics; not the approved graph-level RQ7 method.

The RQ7 runner does not call these scalar transformations after the lecturer's
counterfactual decision. Keep only for existing isolated diagnostic tests.
"""

import numpy as np


SCENARIOS = ('self_citations_plus_50_percent', 'salami_double_papers_half_citations',
             'gift_authorship_plus_30_percent', 'combined')


def simulate(counts, *, scenario, self_citation_counts=None, coauthor_counts=None):
    values = np.asarray(counts, dtype=float)
    if scenario not in SCENARIOS or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError('Invalid local scenario or citation values')
    if scenario in (SCENARIOS[0], SCENARIOS[3]):
        if self_citation_counts is None:
            raise ValueError('Observed self-citation counts required; do not invent them')
        self_counts = np.asarray(self_citation_counts, dtype=float)
        if self_counts.shape != values.shape or np.any(self_counts < 0) or np.any(self_counts > values):
            raise ValueError('Self-citation shape/count invalid')
        values = values + .5*self_counts
    if scenario in (SCENARIOS[1], SCENARIOS[3]):
        values = np.repeat(values/2, 2)
    if scenario in (SCENARIOS[2], SCENARIOS[3]):
        if coauthor_counts is None:
            raise ValueError('Observed complete coauthor counts required')
        counts_authors = np.asarray(coauthor_counts, dtype=float)
        if counts_authors.shape != np.asarray(counts).shape or not np.all(np.isfinite(counts_authors)) or np.any(counts_authors < 1):
            raise ValueError('Coauthor shape invalid')
        if scenario == SCENARIOS[3]:
            counts_authors = np.repeat(counts_authors, 2)
        return values, np.ceil(counts_authors*1.3).astype(int)
    return values, None


def compare_values(original, scenario):
    if original is None or scenario is None or not np.isfinite([original, scenario]).all():
        return dict(status='NOT_APPLICABLE')
    return dict(status='OK', original=original, scenario=scenario, difference=scenario-original,
                percentage_change=100*(scenario-original)/original if original else np.nan)
