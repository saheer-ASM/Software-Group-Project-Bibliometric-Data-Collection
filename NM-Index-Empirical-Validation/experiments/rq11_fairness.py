"""RQ11 uses supplied approved subgroup labels; never infers demographics."""

from analysis.fairness import compare_percentiles, FairnessConvention
from .common import pending


METRICS = ('nm_index', 'h_index', 'c_score_raw', 'raw_total_cites', 'g_index', 'm_index')


def run(dataset, comparators, *, subgroup_labels=None, percentile_scores=None,
        fairness_convention=None, **_):
    if subgroup_labels is None:
        return pending('RQ11 requires externally supplied, approved gender/region labels; no name inference', 'DATA_REQUIRED')
    required = {'author_id', 'gender', 'region', 'approved_for_analysis', 'evidence_reference'}
    if not required <= set(subgroup_labels):
        return pending(f'RQ11 label input missing {sorted(required-set(subgroup_labels))}', 'DATA_REQUIRED')
    if not subgroup_labels.approved_for_analysis.map(lambda value: type(value) is bool).all() or not subgroup_labels.approved_for_analysis.all():
        return pending('RQ11 subgroup labels need explicit approval', 'DATA_REQUIRED')
    if subgroup_labels.evidence_reference.isna().any() or subgroup_labels.evidence_reference.astype(str).str.strip().eq('').any():
        return pending('RQ11 subgroup-label provenance is missing', 'DATA_REQUIRED')
    if percentile_scores is None:
        return pending('RQ11 needs externally supplied reference-population percentiles', 'DATA_REQUIRED')
    if not isinstance(fairness_convention, FairnessConvention):
        return pending('RQ11 Cohen d and regional variance conventions need explicit approval')
    merged = (dataset[['author_id']].merge(subgroup_labels, on='author_id', validate='one_to_one')
              .merge(percentile_scores, on='author_id', validate='one_to_one'))
    groups, effects = compare_percentiles(merged, METRICS, fairness_convention)
    state = 'METHODOLOGY_PENDING' if (effects.status != 'OK').any() else 'OK'
    return {'fairness_analysis': groups, 'fairness_effects': effects,
            'status': pending('RQ11 comparator percentiles incomplete' if state != 'OK' else
                              'Approved supplied percentiles and conventions used', state)['status']}
