"""RQ2 paired t tests on identical author IDs only."""

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from .common import OK


def compare(frame, target, comparators):
    rows = []
    for name in comparators:
        pair = (frame[[target, name]].apply(pd.to_numeric, errors='coerce')
                .replace([np.inf, -np.inf], np.nan).dropna()) if target in frame and name in frame else None
        status = OK if pair is not None and len(pair) >= 2 else 'INSUFFICIENT_DATA' if pair is not None else 'INVALID_INPUT'
        row = dict(target=target, comparator=name, n=len(pair) if pair is not None else 0, status=status,
                   mean_difference=np.nan, median_difference=np.nan, sd_difference=np.nan,
                   t_statistic=np.nan, p_value=np.nan, cohen_d=np.nan, ci_low=np.nan, ci_high=np.nan)
        if status == OK:
            delta = pair[target] - pair[name]
            sd = float(delta.std(ddof=1))
            if sd == 0:
                row['status'] = 'INVALID_INPUT'
            else:
                n = len(delta)
                mean = float(delta.mean())
                se = sd / np.sqrt(n)
                t = mean / se
                half = student_t.ppf(.975, n-1)*se
                row.update(mean_difference=mean, median_difference=float(delta.median()),
                           sd_difference=sd, t_statistic=t,
                           p_value=float(2*student_t.sf(abs(t), n-1)), cohen_d=mean/sd,
                           ci_low=mean-half, ci_high=mean+half)
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out['p_bonferroni'] = (out.p_value * max(out.p_value.notna().sum(), 1)).clip(upper=1)
    return out
