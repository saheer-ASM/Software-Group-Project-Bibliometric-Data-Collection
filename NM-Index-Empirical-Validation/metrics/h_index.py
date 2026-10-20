"""Conventional h-index, explicitly defined in Phase 4 section 3."""
import pandas as pd


def calculate(data):
    """Largest rank h with at least h citations; incomplete portfolios are NULL."""
    values = {}
    for author, counts in data.counts.items():
        values[author] = (sum(count >= rank for rank, count in
                             enumerate(sorted(counts, reverse=True), start=1))
                          if counts is not None else pd.NA)
    return pd.Series(values, name='h_index', dtype='Int64').rename_axis('author_id')
