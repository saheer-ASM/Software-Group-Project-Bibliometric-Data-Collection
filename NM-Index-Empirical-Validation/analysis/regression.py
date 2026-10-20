"""RQ5 explanatory regression with explicit predictors and covariates."""

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


def fit(frame, outcome, predictors, covariates=()):
    columns = (outcome, *predictors, *covariates)
    if not predictors or any(c not in frame for c in columns):
        return pd.DataFrame([dict(status='INVALID_INPUT', issue='Explicit outcome/predictors required')])
    complete = frame[list(columns)].apply(pd.to_numeric, errors='coerce').replace(
        [np.inf, -np.inf], np.nan).dropna()
    n, k = len(complete), len(columns)-1
    if n <= k+2:
        return pd.DataFrame([dict(status='INSUFFICIENT_DATA', n=n)])
    x = np.column_stack([np.ones(n), complete[list(columns[1:])].to_numpy(dtype=float)])
    y = complete[outcome].to_numpy(dtype=float)
    if np.linalg.matrix_rank(x) < x.shape[1]:
        return pd.DataFrame([dict(status='INVALID_INPUT', n=n, issue='Singular design matrix')])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residual = y-x@beta
    dof = n-x.shape[1]
    variance = np.dot(residual, residual)/dof
    covariance = variance*np.linalg.inv(x.T@x)
    standard_error = np.sqrt(np.diag(covariance))
    if not np.isfinite(standard_error).all() or not (standard_error > 0).all():
        return pd.DataFrame([dict(status='INVALID_INPUT', n=n,
                                  issue='Zero residual variance or unstable standard error')])
    p = 2*student_t.sf(np.abs(beta/standard_error), dof)
    return pd.DataFrame([dict(status='OK', n=n, outcome=outcome, term=term,
                              coefficient=float(b), standard_error=float(se), p_value=float(pv))
                         for term, b, se, pv in zip(('intercept', *columns[1:]), beta, standard_error, p)])
