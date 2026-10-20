"""Reproducible local sample-size and parameter sensitivity summaries."""

import numpy as np
import pandas as pd

from .correlation import correlate


def sample_size(frame, target, comparator, sizes, *, seed=2026):
    if 'author_id' not in frame:
        raise ValueError('Stable author IDs are required for reproducible sampling')
    rng = np.random.default_rng(seed)
    ids = np.array(sorted(frame.author_id.dropna().unique()))
    order = rng.permutation(ids)
    rows = []
    for size in sizes:
        if size > len(ids) or size < 4:
            rows.append(dict(sample_size=size, status='INSUFFICIENT_DATA', available=len(ids)))
            continue
        sample = frame[frame.author_id.isin(order[:size])]
        row = correlate(sample, target, [comparator]).iloc[0].to_dict()
        rows.append(dict(sample_size=size, **row))
    return pd.DataFrame(rows)


def compare_scenarios(original, alternative, *, scenario, parameter):
    if not np.isfinite([original, alternative]).all():
        return dict(status='INVALID_INPUT', scenario=scenario, parameter=parameter)
    return dict(status='OK', scenario=scenario, parameter=parameter,
                original_result=original, alternative_result=alternative,
                difference=alternative-original,
                relative_change=(alternative-original)/original if original else np.nan)
