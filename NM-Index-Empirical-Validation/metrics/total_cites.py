"""Conventional total: sum raw citation counts over distinct linked papers.

Phase 4 section 1 permits local calculation from publication citation data.
Does not use the NM methodology's weighted total_cites_score.
"""
import pandas as pd


def calculate(data):
    """Return one total per author in prepared CitationData; incomplete is NULL."""
    return pd.Series({author: sum(counts) if counts is not None else pd.NA
                      for author, counts in data.counts.items()},
                     name='raw_total_cites', dtype='Int64').rename_axis('author_id')
