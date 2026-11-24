"""RQ9 adjacent-year rank stability, separate from supplementary robustness."""

import pandas as pd
from analysis.temporal import rank_stability
from .common import pending


def run(dataset, comparators, *, annual_scores=None, first_year=None,
        rank_change_denominator='paired_cohort_size', **_):
    if annual_scores is None:
        return pending('RQ9 requires adjacent-year score snapshots', 'DATA_REQUIRED')
    years = sorted(pd.to_numeric(annual_scores.year, errors='coerce').dropna().astype(int).unique())
    # default: every pair of consecutive years (paper: temporal correlation matrix)
    starts = [first_year] if first_year is not None else [y for y in years if y + 1 in years]
    metrics = [m for m in ('nm_index', *comparators) if m in annual_scores]
    rows = []
    for start in starts:
        for metric in metrics:
            row = rank_stability(annual_scores, metric, first_year=start, second_year=start + 1,
                                 rank_change_denominator=rank_change_denominator)
            rows.append(dict(row, first_year=start, second_year=start + 1)
                        if isinstance(row, dict) else row)
    if not rows:
        return pending('RQ9 needs at least two consecutive years', 'DATA_REQUIRED')
    return {'temporal_stability': pd.DataFrame(rows)}
