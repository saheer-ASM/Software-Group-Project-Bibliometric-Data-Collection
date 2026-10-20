"""RQ8 prospective outcome association with explicit future window and no leakage."""

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, norm


def future_association(frame, predictor, outcome, *, score_year, outcome_start, outcome_end):
    if outcome_start <= score_year or outcome_end < outcome_start:
        return dict(status='INVALID_INPUT', issue='Outcome window must follow score year')
    if predictor not in frame or outcome not in frame:
        return dict(status='INVALID_INPUT', issue='Prospective score/outcome missing')
    pair = frame[[predictor, outcome]].apply(pd.to_numeric, errors='coerce').replace(
        [np.inf, -np.inf], np.nan).dropna()
    if len(pair) < 4 or pair[predictor].nunique() < 2 or pair[outcome].nunique() < 2:
        return dict(status='INSUFFICIENT_DATA', n=len(pair))
    r, p = pearsonr(pair[predictor], pair[outcome])
    if abs(r) < 1:
        z = np.arctanh(r)
        half = norm.ppf(.975)/np.sqrt(len(pair)-3)
        interval = (float(np.tanh(z-half)), float(np.tanh(z+half)))
    else:
        interval = (float(r), float(r))
    return dict(status='OK', n=len(pair), predictor=predictor, outcome=outcome,
                score_year=score_year, outcome_start=outcome_start, outcome_end=outcome_end,
                correlation=float(r), p_value=float(p), ci_low=interval[0], ci_high=interval[1])
