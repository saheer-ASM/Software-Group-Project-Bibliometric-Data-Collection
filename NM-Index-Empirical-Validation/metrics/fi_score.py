"""Fi-score equation and threshold are absent from current sources."""

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Callable

import pandas as pd

from .strategy import calculate_with_strategy


@dataclass(frozen=True)
class FiStrategy:
    reference: str
    self_citation_treatment: Callable[[pd.DataFrame], pd.DataFrame]
    threshold: Callable[[pd.DataFrame], float]
    score: Callable[[pd.DataFrame, float], float]
    approval_reference: str = ''


def calculate(inputs, strategy=None):
    if isinstance(strategy, FiStrategy):
        if not strategy.reference.strip() or not strategy.approval_reference.strip():
            raise ValueError('Fi-score METHODOLOGY_PENDING: source and approval references required')
        values = {}
        for author, group in inputs.groupby('author_id', sort=True):
            adjusted = strategy.self_citation_treatment(group.copy())
            threshold = strategy.threshold(adjusted)
            if isinstance(threshold, bool) or not isinstance(threshold, Real) or not isfinite(float(threshold)):
                raise ValueError('Fi-score strategy returned an invalid threshold')
            score = strategy.score(adjusted, threshold)
            if isinstance(score, bool) or not isinstance(score, Real) or not isfinite(float(score)):
                raise ValueError('Fi-score strategy returned an invalid score')
            values[author] = float(score)
        return pd.Series(values, name='fi_score', dtype='Float64').rename_axis('author_id')
    return calculate_with_strategy('fi_score', inputs, strategy)
