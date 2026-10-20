"""m = h/career years, only with explicit approved duration convention."""

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class CareerConvention:
    career_start_definition: str
    as_of_date: date
    year_counting_rule: str
    zero_year_policy: str
    duration_years: Callable[[int, date], float]
    approval_reference: str = ''


def calculate(h_values: pd.Series, first_years: pd.Series, convention: CareerConvention | None = None):
    if convention is None:
        raise ValueError('m_index: METHODOLOGY_PENDING; explicit career convention required')
    if not all((convention.career_start_definition, convention.year_counting_rule,
                convention.zero_year_policy, convention.approval_reference)) or convention.as_of_date is None:
        raise ValueError('m_index: METHODOLOGY_PENDING; incomplete/unapproved career convention')
    values = {}
    for author, h in h_values.items():
        year = first_years.get(author)
        if pd.isna(h) or pd.isna(year):
            values[author] = pd.NA
            continue
        duration = convention.duration_years(int(year), convention.as_of_date)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not isfinite(duration) or duration < 0:
            raise ValueError('m_index: invalid career duration')
        if duration == 0:
            if convention.zero_year_policy == 'missing':
                values[author] = pd.NA
                continue
            raise ValueError('m_index: zero career duration requires an explicit supported policy')
        values[author] = float(h) / duration
    return pd.Series(values, name='m_index', dtype='Float64').rename_axis('author_id')
