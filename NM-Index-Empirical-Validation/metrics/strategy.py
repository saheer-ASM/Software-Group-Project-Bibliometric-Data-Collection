"""Explicit activation point for baselines whose source formula is incomplete."""

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Callable, Optional

import pandas as pd


METHODOLOGY_PENDING = 'METHODOLOGY_PENDING'


@dataclass(frozen=True)
class MetricStrategy:
    name: str
    reference: str
    required_inputs: tuple[str, ...]
    calculate_author: Callable[[pd.DataFrame], float]
    approval_reference: str = ''


def calculate_with_strategy(name: str, inputs: pd.DataFrame,
                            strategy: Optional[MetricStrategy] = None) -> pd.Series:
    if strategy is None:
        raise ValueError(f'{name}: METHODOLOGY_PENDING; an explicit, documented strategy is required')
    if strategy.name != name or not strategy.reference.strip() or not strategy.approval_reference.strip():
        raise ValueError(f'{name}: METHODOLOGY_PENDING; source and approval references required')
    missing = set(strategy.required_inputs) - set(inputs.columns)
    if missing:
        raise ValueError(f'{name}: required strategy inputs missing: {sorted(missing)}')
    if 'author_id' not in inputs:
        raise ValueError(f'{name}: author_id is required')
    values = {}
    for author, group in inputs.groupby('author_id', sort=True):
        result = strategy.calculate_author(group.copy())
        if result is None or pd.isna(result):
            values[author] = pd.NA
        elif isinstance(result, bool) or not isinstance(result, Real) or not isfinite(float(result)):
            raise ValueError(f'{name}: strategy returned an invalid value')
        else:
            values[author] = float(result)
    return pd.Series(values, name=name, dtype='Float64').rename_axis('author_id')
