"""Conventional hm is method-pending; NM modified hm is never substituted."""

from .strategy import MetricStrategy, calculate_with_strategy

HMStrategy = MetricStrategy


def calculate(inputs, strategy=None):
    return calculate_with_strategy('hm_index', inputs, strategy)
