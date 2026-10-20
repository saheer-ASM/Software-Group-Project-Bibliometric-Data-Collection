"""RQ9 adjacent-year rank stability, separate from supplementary robustness."""

import pandas as pd
from analysis.temporal import rank_stability
from .common import pending


def run(dataset, comparators, *, annual_scores=None, first_year=None,
        rank_change_denominator=None, **_):
    if annual_scores is None or first_year is None:
        return pending('RQ9 requires adjacent-year score snapshots', 'DATA_REQUIRED')
    return {'temporal_stability': pd.DataFrame([
        rank_stability(annual_scores, metric, first_year=first_year, second_year=first_year+1,
                       rank_change_denominator=rank_change_denominator)
        for metric in ('nm_index', *comparators)])}
