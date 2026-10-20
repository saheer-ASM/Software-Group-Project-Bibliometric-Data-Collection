"""RQ1 pairwise Pearson analysis with Fisher intervals and Bonferroni values."""

import math
import numpy as np
import pandas as pd
from scipy.stats import norm, pearsonr

from .common import finite_pairs, OK


def correlate(frame, target, comparators):
    rows = []
    for name in comparators:
        pair, status = finite_pairs(frame, target, name, min_n=4)
        row = dict(target=target, comparator=name, n=len(pair) if pair is not None else 0, status=status,
                   correlation=np.nan, p_value=np.nan, ci_low=np.nan, ci_high=np.nan)
        if status == OK:
            r, p = pearsonr(pair[target], pair[name])
            row.update(correlation=float(r), p_value=float(p))
            if abs(r) < 1:
                z = math.atanh(r)
                half = norm.ppf(.975) / math.sqrt(len(pair)-3)
                row.update(ci_low=math.tanh(z-half), ci_high=math.tanh(z+half))
            else:
                row.update(ci_low=float(r), ci_high=float(r))
        rows.append(row)
    out = pd.DataFrame(rows)
    valid = out.p_value.notna().sum() if not out.empty else 0
    if not out.empty:
        out['p_bonferroni'] = (out.p_value * max(valid, 1)).clip(upper=1)
    return out
