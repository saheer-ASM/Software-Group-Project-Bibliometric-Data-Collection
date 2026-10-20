"""C-score variants: component/normalization/SC rules await approval."""

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Callable

import pandas as pd

from .strategy import calculate_with_strategy


@dataclass(frozen=True)
class CScoreStrategy:
    """Explicit, source-cited convention for six indicators and reference population."""

    reference: str
    build_indicators: Callable[[pd.DataFrame], pd.DataFrame]
    normalize_indicators: Callable[[pd.DataFrame], pd.DataFrame]
    aggregate: Callable[[pd.DataFrame], float]
    self_citation_adjust: Callable[[pd.DataFrame], pd.DataFrame] | None = None
    approval_reference: str = ''


def _specific(inputs, strategy, adjusted):
    if not strategy.reference.strip() or not strategy.approval_reference.strip():
        raise ValueError('C-score METHODOLOGY_PENDING: source and approval references required')
    if adjusted and strategy.self_citation_adjust is None:
        raise ValueError('C-score SC adjustment requires an explicit rule')
    values = {}
    for author, group in inputs.groupby('author_id', sort=True):
        prepared = strategy.self_citation_adjust(group.copy()) if adjusted else group.copy()
        indicators = strategy.build_indicators(prepared)
        if indicators.shape[1] != 6:
            raise ValueError('C-score requires six declared indicators')
        normalized = strategy.normalize_indicators(indicators)
        result = strategy.aggregate(normalized)
        if result is not None and not pd.isna(result) and (
                isinstance(result, bool) or not isinstance(result, Real)
                or not isfinite(float(result))):
            raise ValueError('C-score strategy returned an invalid value')
        values[author] = float(result) if result is not None and pd.notna(result) else pd.NA
    name = 'c_score_sc_adjusted' if adjusted else 'c_score_raw'
    return pd.Series(values, name=name, dtype='Float64').rename_axis('author_id')


def calculate_raw(inputs, strategy=None):
    if isinstance(strategy, CScoreStrategy):
        return _specific(inputs, strategy, False)
    return calculate_with_strategy('c_score_raw', inputs, strategy)


def calculate_self_citation_adjusted(inputs, strategy=None):
    if isinstance(strategy, CScoreStrategy):
        return _specific(inputs, strategy, True)
    return calculate_with_strategy('c_score_sc_adjusted', inputs, strategy)
