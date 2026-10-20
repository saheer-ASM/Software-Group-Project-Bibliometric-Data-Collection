"""Supplementary robustness and source-grid NM parameter recalculations."""

from dataclasses import replace

import pandas as pd

from analysis.robustness import sample_size
from nm_index.counterfactual_calculator import NMParameters, calculate_nm


CAREER_GRID = ((1.00, 0.00), (1.25, .0601), (1.50, .10), (2.00, .15))
ISC_GRID = (.50, .75, .90, 1.00)


def run(dataset, comparators, *, seed=2026, graph_inputs=None,
        frozen_benchmarks=None, nm_parameters=None, **_):
    rows = []
    for metric in ('h_index', 'c_score_raw'):
        if metric in comparators:
            rows.append(sample_size(dataset, 'nm_index', metric,
                                    (25000, 50000, 75000, 100000), seed=seed))
    results = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame([
        dict(status='METHODOLOGY_PENDING', issue='No supported h/C comparator available')])
    parameter_rows = []
    if graph_inputs is not None and frozen_benchmarks is not None and nm_parameters is not None:
        if not isinstance(nm_parameters, NMParameters):
            raise TypeError('Parameter sensitivity requires NMParameters')
        for author_id in dataset.author_id:
            graph = graph_inputs.get(author_id)
            if graph is None:
                parameter_rows.append(dict(author_id=author_id, status='INPUT_DATA_REQUIRED',
                    issue='Complete graph missing for selected author'))
                continue
            for boost, decay in CAREER_GRID:
                parameters = replace(nm_parameters, career_boost=boost, career_decay=decay)
                score = calculate_nm(author_id, graph.papers, graph.edges,
                    frozen_benchmarks, career_start_year=graph.career_start_year,
                    parameters=parameters)
                parameter_rows.append(dict(author_id=author_id, grid='career',
                    career_boost=boost, career_decay=decay, epsilon_0=parameters.epsilon_0,
                    nm_index=score['nm_index'], nm_percentile=score['nm_percentile'],
                    benchmark_sha256=score['benchmark_sha256'], status='OK'))
            for epsilon in ISC_GRID:
                parameters = replace(nm_parameters, epsilon_0=epsilon)
                score = calculate_nm(author_id, graph.papers, graph.edges,
                    frozen_benchmarks, career_start_year=graph.career_start_year,
                    parameters=parameters)
                parameter_rows.append(dict(author_id=author_id, grid='isc',
                    career_boost=parameters.career_boost, career_decay=parameters.career_decay,
                    epsilon_0=epsilon, nm_index=score['nm_index'],
                    nm_percentile=score['nm_percentile'],
                    benchmark_sha256=score['benchmark_sha256'], status='OK'))
    status = ('SCORES_READY_SUMMARIES_PENDING' if parameter_rows and
        all(row['status'] == 'OK' for row in parameter_rows) else 'DATA_REQUIRED')
    issue = ('Rank-delta tie/direction rules, Gini target, and binary-ISC comparison convention are not defined in the source tables'
             if status == 'SCORES_READY_SUMMARIES_PENDING' else
             'Complete graph inputs and frozen reference required for parameter recalculation')
    return {'sensitivity_results': results,
            'parameter_sensitivity_scores': pd.DataFrame(parameter_rows),
            'parameter_sensitivity_status': pd.DataFrame([dict(status=status, issue=issue)]),
            'status': pd.DataFrame([dict(status=status, issue=issue)])}
