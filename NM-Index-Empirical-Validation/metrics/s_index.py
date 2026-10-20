"""s-index identity is unresolved in current sources."""

from .strategy import calculate_with_strategy


def calculate(inputs, strategy=None):
    return calculate_with_strategy('s_index', inputs, strategy)
