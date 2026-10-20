"""RQ2 paired difference tests."""

from analysis.paired_tests import compare


def run(dataset, comparators, **_):
    return {'paired_difference_stats': compare(dataset, 'nm_index', comparators)}
