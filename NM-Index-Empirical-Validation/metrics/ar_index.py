"""AR age weighting and reference date are absent from current sources."""

from dataclasses import dataclass
from datetime import date
from math import isfinite
from numbers import Real
from typing import Callable

import pandas as pd

from .strategy import calculate_with_strategy


@dataclass(frozen=True)
class ARStrategy:
    reference: str
    as_of_date: date
    paper_age: Callable[[int, date], float]
    aggregate: Callable[[pd.DataFrame], float]
    approval_reference: str = ''


def calculate(inputs, strategy=None):
    if isinstance(strategy, ARStrategy):
        if not strategy.reference.strip() or not strategy.approval_reference.strip() or strategy.as_of_date is None:
            raise ValueError('AR METHODOLOGY_PENDING: source, approval and reference date required')
        values = {}
        for author, group in inputs.groupby('author_id', sort=True):
            paper = group.copy()
            paper['paper_age'] = paper.year.map(lambda year: strategy.paper_age(year, strategy.as_of_date))
            if paper.paper_age.map(lambda value: isinstance(value, bool) or not isinstance(value, Real)
                    or not isfinite(float(value)) or value < 0).any():
                raise ValueError('AR strategy returned an invalid paper age')
            score = strategy.aggregate(paper)
            if isinstance(score, bool) or not isinstance(score, Real) or not isfinite(float(score)):
                raise ValueError('AR strategy returned an invalid score')
            values[author] = float(score)
        return pd.Series(values, name='ar_index', dtype='Float64').rename_axis('author_id')
    return calculate_with_strategy('ar_index', inputs, strategy)
