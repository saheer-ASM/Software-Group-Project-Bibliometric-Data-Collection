"""Build one author row without fabricating unavailable baseline values."""

import pandas as pd

from nm_index.loader import load as load_nm
from .eligibility import EligibilityRules, evaluate
from .metric_registry import REGISTRY


BASELINE_COLUMNS = tuple(m.output_column for m in REGISTRY if m.metric_type == 'baseline')


def build(authors: pd.DataFrame, nm: pd.DataFrame, metric_series: dict,
          quality: pd.DataFrame, rules: EligibilityRules | None = None,
          components: pd.DataFrame | None = None) -> pd.DataFrame:
    if authors.author_id.isna().any() or authors.author_id.duplicated().any():
        raise ValueError('Author cohort must have unique non-NULL stable IDs')
    data = authors[['author_id']].copy().sort_values('author_id').reset_index(drop=True)
    data = data.merge(load_nm(nm), on='author_id', how='left', validate='one_to_one')
    if components is not None:
        data = data.merge(components, on='author_id', how='left', validate='one_to_one')
    data['nm_index_available'] = data.nm_index.notna()
    for name in BASELINE_COLUMNS:
        values = metric_series.get(name)
        if values is None:
            data[name] = pd.Series(pd.NA, index=data.index, dtype='Float64')
        else:
            if values.index.duplicated().any():
                raise ValueError(f'{name}: duplicate author IDs')
            data[name] = data.author_id.map(values)
    data['metric_coverage_count'] = data[list(BASELINE_COLUMNS)].notna().sum(axis=1)
    data['metric_coverage_percentage'] = data.metric_coverage_count / len(BASELINE_COLUMNS)
    if quality.author_id.duplicated().any():
        raise ValueError('Duplicate quality author IDs')
    optional = [c for c in ('observed_first_year', 'observed_last_year',
                           'active_2000_2024', 'publication_metadata_complete') if c in quality]
    data = data.merge(quality[['author_id', 'linked_publications', 'full_portfolio_verified', *optional]],
                      on='author_id', how='left', validate='one_to_one')
    data['linked_publications'] = data.linked_publications.fillna(0).astype(int)
    data['full_portfolio_verified'] = data.full_portfolio_verified.fillna(False).astype(bool)
    return evaluate(data, rules or EligibilityRules())
