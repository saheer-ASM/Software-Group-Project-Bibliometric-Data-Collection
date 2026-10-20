"""RQ10 construct validity on the six stored raw NM component scores."""

import pandas as pd
from analysis.pca import analyze
from .common import pending

RAW_COMPONENT_COLUMNS = ('nm_raw_t', 'nm_raw_s', 'nm_raw_u',
                         'nm_raw_hf', 'nm_raw_hm', 'nm_raw_g')


def run(dataset, comparators, *, pca_preprocessing=None, pca_decision_reference=None, **_):
    if pca_preprocessing is None or not pca_decision_reference:
        return pending('RQ10 PCA preprocessing and eligible cohort must be explicitly prespecified')
    if pca_preprocessing != 'complete_case_z_standardization':
        return pending('Unsupported PCA preprocessing choice', 'INVALID_INPUT')
    summary, loadings = analyze(dataset, RAW_COMPONENT_COLUMNS)
    summary['decision_reference'] = pca_decision_reference
    return {'pca_status': pd.DataFrame([summary]), 'pca_loadings': loadings}
