"""RQ6 trajectories and RQ9 adjacent-year rank stability."""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def trajectory(frame, author_id, metrics):
    required = {'author_id', 'year', *metrics}
    if not required <= set(frame):
        raise ValueError(f'Temporal frame missing: {sorted(required-set(frame))}')
    result = frame.loc[frame.author_id == author_id, ['author_id', 'year', *metrics]].copy()
    if result.year.duplicated().any():
        raise ValueError('One author has duplicate annual records')
    return result.sort_values('year')


def rank_stability(frame, metric, *, first_year, second_year, rank_change_denominator=None):
    required = {'author_id', 'year', metric}
    if not required <= set(frame) or second_year != first_year+1:
        return dict(status='INVALID_INPUT', issue='Adjacent years and annual author scores required')
    first = frame.loc[frame.year == first_year, ['author_id', metric]]
    second = frame.loc[frame.year == second_year, ['author_id', metric]]
    if first.author_id.duplicated().any() or second.author_id.duplicated().any():
        return dict(status='INVALID_INPUT', issue='Duplicate author/year score')
    pairs = first.merge(second, on='author_id', suffixes=('_t', '_t1')).dropna()
    a, b = f'{metric}_t', f'{metric}_t1'
    if len(pairs) < 3 or pairs[a].nunique() < 2 or pairs[b].nunique() < 2:
        return dict(status='INSUFFICIENT_DATA', n=len(pairs))
    first_rank = pairs[a].rank(ascending=False, method='average')
    second_rank = pairs[b].rank(ascending=False, method='average')
    change = (first_rank-second_rank).abs()
    rho, p = spearmanr(first_rank, second_rank)
    if rank_change_denominator is None:
        threshold_status = 'METHODOLOGY_PENDING'
        proportion = np.nan
    elif rank_change_denominator == 'paired_cohort_size':
        threshold_status = 'OK_WITH_EXPLICIT_CONVENTION'
        proportion = float((change > .1*len(pairs)).mean())
    else:
        return dict(status='INVALID_INPUT', issue='Unsupported rank-change denominator')
    return dict(status=threshold_status, n=len(pairs), metric=metric, first_year=first_year,
                second_year=second_year, mean_absolute_rank_change=float(change.mean()),
                spearman_rho=float(rho), p_value=float(p),
                proportion_over_ten_percent=proportion,
                threshold_rule=rank_change_denominator or 'METHODOLOGY_PENDING')
