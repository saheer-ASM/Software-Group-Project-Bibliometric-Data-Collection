"""Shared finite-pair validation and explicit analysis statuses."""

import numpy as np
import pandas as pd

OK = 'OK'
INSUFFICIENT_DATA = 'INSUFFICIENT_DATA'
INVALID_INPUT = 'INVALID_INPUT'
METHODOLOGY_PENDING = 'METHODOLOGY_PENDING'
NOT_APPLICABLE = 'NOT_APPLICABLE'


def finite_pairs(frame, x, y, min_n=3):
    if x not in frame or y not in frame:
        return None, INVALID_INPUT
    pair = frame[[x, y]].apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
    if len(pair) < min_n:
        return pair, INSUFFICIENT_DATA
    if pair[x].nunique() < 2 or pair[y].nunique() < 2:
        return pair, INVALID_INPUT
    return pair, OK


def safe_numeric(frame, columns):
    if any(column not in frame for column in columns):
        return None
    return frame[list(columns)].apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
