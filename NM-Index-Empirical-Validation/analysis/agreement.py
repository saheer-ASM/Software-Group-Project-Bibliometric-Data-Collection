"""RQ3 ICC: requires explicit model choice absent from source documents."""

import numpy as np
import pandas as pd

from .common import finite_pairs, OK


def _icc_a1(x):
    n, k = x.shape
    grand = x.mean()
    ms_rows = k * ((x.mean(axis=1)-grand)**2).sum()/(n-1)
    ms_cols = n * ((x.mean(axis=0)-grand)**2).sum()/(k-1)
    residual = x - x.mean(axis=1, keepdims=True) - x.mean(axis=0, keepdims=True) + grand
    ms_error = (residual**2).sum()/((n-1)*(k-1))
    denominator = ms_rows+(k-1)*ms_error+k*(ms_cols-ms_error)/n
    return (ms_rows-ms_error)/denominator if denominator > 0 else np.nan


def icc(frame, first, second, *, model=None, seed=2026, bootstrap=500):
    if model is None:
        return dict(metric_pair=f'{first}:{second}', status='METHODOLOGY_PENDING',
                    issue='Experiment design does not choose ICC model or score scale')
    if model != 'ICC(A,1) two-way random absolute agreement':
        return dict(metric_pair=f'{first}:{second}', status='INVALID_INPUT', issue='Unsupported ICC model')
    pair, status = finite_pairs(frame, first, second, min_n=3)
    if status != OK:
        return dict(metric_pair=f'{first}:{second}', status=status, n=len(pair) if pair is not None else 0)
    x = pair.to_numpy(dtype=float)
    n = len(x)
    value = _icc_a1(x)
    if not np.isfinite(value):
        return dict(metric_pair=f'{first}:{second}', status='INVALID_INPUT', n=n)
    rng = np.random.default_rng(seed)
    draws = np.array([_icc_a1(x[rng.integers(0, n, n)]) for _ in range(bootstrap)])
    draws = draws[np.isfinite(draws)]
    low, high = (np.quantile(draws, [.025, .975]) if len(draws) >= max(20, bootstrap//2)
                 else (np.nan, np.nan))
    return dict(metric_pair=f'{first}:{second}', status='OK', n=n, model=model,
                unit='single measurement', icc=value, ci_low=low, ci_high=high,
                ci_method='subject bootstrap, 95%',
                note='Raw score scales must be substantively comparable; no scaling was silently applied')
