"""Conventional top-g-papers rule from design line 37 and manuscript p. 2."""

import pandas as pd


def calculate(data):
    values = {}
    for author, counts in data.counts.items():
        if counts is None:
            values[author] = pd.NA
            continue
        running = 0
        best = 0
        for rank, citations in enumerate(sorted(counts, reverse=True), 1):
            running += citations
            if running >= rank * rank:
                best = rank
        values[author] = best
    return pd.Series(values, name='g_index', dtype='Int64').rename_axis('author_id')
