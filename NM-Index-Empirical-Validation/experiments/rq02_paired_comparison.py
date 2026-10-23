"""RQ2 paired difference tests."""

from analysis.paired_tests import compare
from .common import pending


def run(dataset, comparators, **_):
    # Neither the design nor the manuscript fixes a common score scale (NM is 0-100,
    # baselines are counts), so native-unit differences stay descriptive, as for RQ3's ICC.
    stats = compare(dataset, 'nm_index', comparators)
    stats['score_scale'] = 'native_units'
    return {'paired_difference_stats': stats,
            'status': pending('Paired-test score scale is not specified (NM 0-100 vs baseline counts); '
                              'native-unit differences are descriptive only')['status']}
