"""RQ8 prospective t to t+5 outcomes; distinct from RQ5 explanatory analyses."""

import pandas as pd
from analysis.predictive import future_association
from .common import pending


def run(dataset, comparators, *, historical_scores=None, future_outcomes=None, score_year=None,
        data_source_kind=None, **_):
    if historical_scores is None or future_outcomes is None or score_year is None:
        return pending('RQ8 needs an explicit historical score snapshot at t and observed outcomes from t+1 through t+5', 'DATA_REQUIRED')
    snapshot = historical_scores.loc[historical_scores.score_year == score_year].copy()
    if data_source_kind in {'SELECT_ONLY_POSTGRESQL', 'SELECT_ONLY_POSTGRESQL_PILOT'} and len(snapshot) < 10000:
        return pending('RQ8 design requires 10000 complete longitudinal authors', 'DATA_REQUIRED')
    if snapshot.empty or snapshot.author_id.duplicated().any():
        return pending('No unique historical score records at the selected score year', 'INVALID_INPUT')
    if not {'outcome_start_year', 'outcome_end_year'} <= set(future_outcomes):
        return pending('Future outcome timing columns are required', 'INVALID_INPUT')
    if (future_outcomes.outcome_start_year != score_year+1).any() or (future_outcomes.outcome_end_year != score_year+5).any():
        return pending('Future outcome rows must be explicitly dated t+1 through t+5', 'INVALID_INPUT')
    merged = snapshot.merge(future_outcomes, on='author_id', validate='one_to_one')
    outcomes = ('future_citations', 'future_awards', 'h_index_growth')
    available = [metric for metric in ('nm_index', *comparators) if metric in merged]
    rows = [future_association(merged, metric, outcome, score_year=score_year,
                              outcome_start=score_year+1, outcome_end=score_year+5)
            for metric in available for outcome in outcomes]
    return {'predictive_validity': pd.DataFrame(rows)}
