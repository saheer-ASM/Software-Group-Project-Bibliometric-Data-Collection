"""Source-table parameter grids run against unchanged synthetic graph/reference data."""

import unittest

import pandas as pd

from experiments.sensitivity import CAREER_GRID, ISC_GRID, run
from nm_index.counterfactual_calculator import calculate_nm
from tests.fixtures.synthetic import make_fixture


class ParameterSensitivityTests(unittest.TestCase):
    def test_source_grids_recalculate_original_graph_without_mutation(self):
        _, inputs = make_fixture()
        author_id, graph = next(iter(inputs['graph_inputs'].items()))
        original_papers = graph.papers.copy(deep=True)
        original_edges = graph.edges.copy(deep=True)
        benchmark_hash = inputs['frozen_benchmarks'].sha256
        dataset = pd.DataFrame({'author_id': [author_id]})
        output = run(dataset, [], graph_inputs=inputs['graph_inputs'],
            frozen_benchmarks=inputs['frozen_benchmarks'],
            nm_parameters=inputs['nm_parameters'])
        rows = output['parameter_sensitivity_scores']
        self.assertEqual(len(rows), len(CAREER_GRID) + len(ISC_GRID))
        self.assertEqual(set(rows.status), {'OK'})
        self.assertEqual(set(rows.benchmark_sha256), {benchmark_hash})
        baseline = calculate_nm(author_id, graph.papers, graph.edges,
            inputs['frozen_benchmarks'], career_start_year=graph.career_start_year,
            parameters=inputs['nm_parameters'])
        base_rows = rows.loc[((rows.grid == 'career') &
            (rows.career_boost == 1.25) & (rows.career_decay == .0601)) |
            ((rows.grid == 'isc') & (rows.epsilon_0 == .90))]
        self.assertEqual(len(base_rows), 2)
        self.assertTrue((base_rows.nm_index == baseline['nm_index']).all())
        pd.testing.assert_frame_equal(graph.papers, original_papers)
        pd.testing.assert_frame_equal(graph.edges, original_edges)
        self.assertEqual(inputs['frozen_benchmarks'].sha256, benchmark_hash)
        self.assertEqual(output['parameter_sensitivity_status'].iloc[0].status,
                         'SCORES_READY_SUMMARIES_PENDING')


if __name__ == '__main__':
    unittest.main()
