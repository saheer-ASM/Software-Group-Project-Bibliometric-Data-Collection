"""RQ6 one-author observed annual score trajectory."""

import pandas as pd

from analysis.temporal import trajectory
from .common import pending


def run(dataset, comparators, *, annual_scores=None, representative_author=None,
        trajectory_normalization=None, trajectory_decision_reference=None, **_):
    if annual_scores is None or representative_author is None:
        return pending('RQ6 requires annual score snapshots and an explicitly chosen representative author', 'DATA_REQUIRED')
    required = {'author_id', 'year', 'publication_count', 'nm_index', *comparators}
    if not required <= set(annual_scores):
        return pending(f'RQ6 annual snapshots missing {sorted(required-set(annual_scores))}', 'DATA_REQUIRED')
    output = trajectory(annual_scores, representative_author,
                        ['publication_count', 'nm_index', *comparators])
    if output.empty:
        return pending('RQ6 selected author has no annual score records', 'DATA_REQUIRED')
    results = {'score_evolution': output}
    if trajectory_normalization is None or not trajectory_decision_reference:
        results['status'] = pending('RQ6 normalized-score convention and representative-author decision reference required')['status']
        return results
    if trajectory_normalization != 'within_author_max':
        results['status'] = pending('Unsupported trajectory normalization', 'INVALID_INPUT')['status']
        return results
    normalized = output[['author_id', 'year', 'publication_count']].copy()
    for metric in ('nm_index', *comparators):
        values = pd.to_numeric(output[metric], errors='coerce')
        maximum = values.max()
        normalized[metric] = values / maximum if maximum > 0 else pd.NA
    normalized['normalization'] = trajectory_normalization
    normalized['decision_reference'] = trajectory_decision_reference
    results['score_evolution_normalized'] = normalized
    results['status'] = pending('Explicit within-author normalization used', 'OK_WITH_EXPLICIT_CONVENTION')['status']
    return results
