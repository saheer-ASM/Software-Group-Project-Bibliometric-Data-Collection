"""RQ1 associative power: Pearson with 95% CI and multiplicity correction."""

from analysis.correlation import correlate
from analysis.rq01_diagnostics import analyse
import pandas as pd
from .common import pending


def run(dataset, comparators, *, reference_scores=None,
        data_source_kind=None, **_):
    columns = ['nm_index', *comparators]
    matrix = dataset[columns].apply(pd.to_numeric, errors='coerce').corr(method='pearson')
    matrix.insert(0, 'metric', matrix.index)
    output = {'correlation_matrix': matrix.reset_index(drop=True),
              'correlation_stats': correlate(dataset, 'nm_index', comparators)}
    if reference_scores is None:
        output['status'] = pending(
            'Versioned full 100000-author percentile reference with C-score, middle-author share and career stage required',
            'DATA_REQUIRED')['status']
        return output
    output.update(analyse(reference_scores, comparators,
                          synthetic=data_source_kind == 'SYNTHETIC_TEST_DATA',
                          selected_ids=dataset.author_id))
    return output
