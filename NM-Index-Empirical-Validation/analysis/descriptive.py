"""Finite-value descriptive statistics and explicit missing counts."""

import numpy as np
import pandas as pd
from scipy.stats import skew


def describe(frame, columns):
    rows = []
    for name in columns:
        if name not in frame:
            rows.append(dict(metric=name, status='INVALID_INPUT', count=0, missing=len(frame)))
            continue
        values = pd.to_numeric(frame[name], errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
        n = len(values)
        rows.append(dict(metric=name, status='OK' if n else 'INSUFFICIENT_DATA', count=n,
            missing=len(frame)-n, mean=values.mean() if n else np.nan,
            median=values.median() if n else np.nan, std=values.std(ddof=1) if n > 1 else np.nan,
            minimum=values.min() if n else np.nan, maximum=values.max() if n else np.nan,
            p25=values.quantile(.25) if n else np.nan, p75=values.quantile(.75) if n else np.nan,
            p95=values.quantile(.95) if n else np.nan,
            skewness=skew(values, bias=False) if n > 2 and values.nunique() > 1 else np.nan))
    return pd.DataFrame(rows)
