"""RQ3 ICC with explicit model selection."""

import pandas as pd
from analysis.agreement import icc


def run(dataset, comparators, *, icc_model=None, **_):
    return {'icc_analysis': pd.DataFrame([icc(dataset, 'nm_index', name, model=icc_model)
                                          for name in comparators])}
