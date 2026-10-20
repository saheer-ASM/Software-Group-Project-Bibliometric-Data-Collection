"""RQ7 gate: do not mistake aggregate citation arithmetic for NM recalculation."""

import numpy as np
import pandas as pd

from analysis.gaming import SCENARIOS
from analysis.counterfactual import FrozenBenchmarks
from analysis.rq07_engine import SCENARIOS as GRAPH_SCENARIOS, run_author_graph
from nm_index.counterfactual_calculator import NMParameters
from .common import pending


BASELINES = ('raw_total_cites', 'h_index', 'hm_index', 'hf_index', 'g_index', 'c_score_raw')
PARAMETERS = {
    SCENARIOS[0]: '+50% self-citation relationships',
    SCENARIOS[1]: '2 papers per original; half citation edges each',
    SCENARIOS[2]: '30% additional existing coauthor papers; target as middle author',
    SCENARIOS[3]: 'all three manipulations',
}


def run(dataset, comparators, *, paper_inputs=None, frozen_benchmarks=None,
        graph_inputs=None, nm_parameters=None, **_):
    """Report missing inputs until a verified full NM engine is available.

    Historical paper_inputs contains aggregate citation/self/coauthor counts.
    It cannot represent new citing-paper edges, contribution assignments, or
    the frozen 100000-author benchmark required by the lecturer's decision.
    """
    if dataset.empty:
        return pending('No eligible author records for RQ7', 'DATA_REQUIRED')
    if frozen_benchmarks is not None and not isinstance(frozen_benchmarks, FrozenBenchmarks):
        raise ValueError('RQ7 frozen_benchmarks must come from original reference data')
    if graph_inputs is not None:
        if not isinstance(graph_inputs, dict) or not isinstance(nm_parameters, NMParameters):
            raise ValueError('RQ7 graph inputs require per-author mappings and NMParameters')
        if frozen_benchmarks is None:
            return pending('Original immutable 100000-author benchmark required', 'DATA_REQUIRED')
        rows, index_rows = [], []
        for author in dataset.author_id:
            graph = graph_inputs.get(author)
            if graph is None:
                rows.extend(dict(author_id=author, scenario=scenario,
                    status='INPUT_DATA_REQUIRED',
                    exclusion_reason='Complete original graph absent for selected author',
                    benchmark_version=frozen_benchmarks.version,
                    benchmark_sha256=frozen_benchmarks.sha256)
                    for scenario in GRAPH_SCENARIOS)
                continue
            scenario_frame, baseline_frame = run_author_graph(
                author, graph, frozen_benchmarks, nm_parameters)
            rows.extend(scenario_frame.to_dict('records'))
            index_rows.extend(baseline_frame.to_dict('records'))
        frame = pd.DataFrame(rows)
        states = set(frame.status) if len(frame) else set()
        status = 'OK' if states == {'OK'} else 'INPUT_DATA_REQUIRED' if 'INPUT_DATA_REQUIRED' in states else 'NOT_APPLICABLE'
        return {'gaming_resistance': frame,
                'gaming_index_inflation': pd.DataFrame(index_rows),
                'status': pd.DataFrame([dict(status=status,
                    issue='' if status == 'OK' else 'At least one selected author/scenario lacks complete graph evidence')])}
    supplied = set(paper_inputs.author_id) if paper_inputs is not None else set()
    rows, index_rows = [], []
    for author in dataset.author_id:
        reason = ('Paper-level input absent' if author not in supplied else
                  'Aggregate paper counts lack citing-paper graph, full authorship and frozen benchmarks')
        for scenario in SCENARIOS:
            rows.append(dict(author_id=author, scenario=scenario,
                scenario_parameters=PARAMETERS[scenario],
                original_nm_percentile=np.nan, manipulated_nm_percentile=np.nan,
                nm_inflation_percent=np.nan,
                benchmark_version=frozen_benchmarks.version if frozen_benchmarks else '',
                benchmark_sha256=frozen_benchmarks.sha256 if frozen_benchmarks else '',
                authors_used=0,
                status='METHODOLOGY_INPUT_REQUIRED', exclusion_reason=reason,
                missing_data_reason='Complete original citation graph, author/contribution/field data, '
                    'frozen 100000-author benchmarks and validated local NM calculator required'))
            for metric in ('nm_index', *BASELINES):
                pending_method = metric in {'hm_index', 'c_score_raw'}
                index_rows.append(dict(author_id=author, scenario=scenario, metric=metric,
                    original_percentile=np.nan, manipulated_percentile=np.nan,
                    inflation_percent=np.nan,
                    status='METHODOLOGY_UNSPECIFIED' if pending_method else 'DATA_REQUIRED',
                    reason='Baseline formula not approved' if pending_method else reason))
    return {'gaming_resistance': pd.DataFrame(rows),
            'gaming_index_inflation': pd.DataFrame(index_rows),
            'status': pending('Full graph-level NM counterfactual calculator and frozen 100000-author reference required')['status']}
