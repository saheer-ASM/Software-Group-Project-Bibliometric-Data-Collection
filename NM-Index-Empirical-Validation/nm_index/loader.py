"""One-row-per-author stored NM loader; does not implement NM mathematics."""

import pandas as pd

COMPONENT_COLUMNS = ('per_total_cites', 'per_citations_per_paper', 'per_citation_rate',
                     'per_modified_hf_index', 'per_modified_hm_index', 'per_modified_g_index')


def load(frame: pd.DataFrame) -> pd.DataFrame:
    needed = {'author_id', 'nm_index', 'metrics_available', *COMPONENT_COLUMNS}
    missing = needed - set(frame.columns)
    if missing:
        raise ValueError(f'author_nm_index missing columns: {sorted(missing)}')
    if frame.author_id.isna().any() or frame.author_id.duplicated().any():
        raise ValueError('author_nm_index has NULL or duplicate author IDs')
    result = frame.copy().sort_values('author_id').reset_index(drop=True)
    result['nm_index_available'] = result.nm_index.notna()
    result['nm_component_count'] = result[list(COMPONENT_COLUMNS)].notna().sum(axis=1)
    result['nm_component_complete'] = result.nm_component_count.eq(6)
    result['nm_index_source'] = 'STORED_PRODUCTION_RESULT'
    return result
