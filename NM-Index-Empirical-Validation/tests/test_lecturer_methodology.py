"""Synthetic checks for lecturer-approved percentile diagnostics."""

import tempfile
import unittest

import numpy as np
import pandas as pd

from analysis.rq01_diagnostics import analyse, percentile_ranks
from analysis.counterfactual import (FrozenBenchmarks, MethodologyInputRequired,
    percentile_inflation, add_self_citation_relationships,
    split_salami_papers, add_gift_authorship, BENCHMARK_TABLES)
from src.config import PROJECT_ROOT
from visualization.correlations import residual_plot, bland_altman_plot, difference_histogram
from experiments.rq07_gaming_sensitivity import run as run_rq07


class RQ1MethodologyTests(unittest.TestCase):
    def setUp(self):
        self.reference = pd.DataFrame({
            'author_id': [f'TEST_A{i}' for i in range(12)],
            'nm_index': [10, 30, 20, 40, 60, 50, 70, 90, 80, 100, 95, 85],
            'c_score_raw': list(range(1, 13)),
            'h_index': [2, 2, 4, 4, 5, 5, 6, 7, 8, 8, 9, 10],
            'middle_author_share': np.linspace(0, 1, 12),
            'career_stage': ['Early']*6+['Senior']*6,
            'reference_version': ['TEST_FROZEN_REFERENCE']*12,
            'evidence_reference': ['TEST DATA ONLY: invented reference']*12})

    def test_ols_percentiles_fitted_values_and_residual_definition(self):
        result = analyse(self.reference, ('c_score_raw','h_index'), synthetic=True)
        self.assertEqual(result['status'].iloc[0].status, 'OK')
        rows = result['rq01_residuals']
        coeff = result['rq01_residual_coefficients'].iloc[0]
        self.assertEqual(len(rows), 12)
        np.testing.assert_allclose(rows.nm_percentile-rows.fitted_nm_percentile,
                                   rows.residual)
        np.testing.assert_allclose(coeff.intercept + coeff.c_score_percentile_coefficient
                                   * rows.c_score_percentile, rows.fitted_nm_percentile)
        self.assertAlmostEqual(float(rows.residual.mean()), 0, places=10)
        self.assertEqual(set(rows.career_stage), {'Early','Senior'})

    def test_percentile_bland_altman_bias_loa_and_empirical_limits(self):
        result = analyse(self.reference, ('h_index',), synthetic=True)
        pairs = result['rq01_bland_altman_pairs']
        summary = result['rq01_bland_altman_summary'].iloc[0]
        np.testing.assert_allclose(pairs.difference,
            pairs.nm_percentile-pairs.baseline_percentile)
        np.testing.assert_allclose(pairs.pair_mean,
            (pairs.nm_percentile+pairs.baseline_percentile)/2)
        self.assertAlmostEqual(summary.bias, pairs.difference.mean())
        self.assertAlmostEqual(summary.loa_lower,
            summary.bias-1.96*pairs.difference.std(ddof=1))
        self.assertAlmostEqual(summary.loa_upper,
            summary.bias+1.96*pairs.difference.std(ddof=1))
        self.assertAlmostEqual(summary.difference_p2_5,
            np.percentile(pairs.difference, 2.5))
        self.assertAlmostEqual(summary.difference_p97_5,
            np.percentile(pairs.difference, 97.5))
        self.assertEqual(summary.skewness_assessment,
                         'REVIEW_REQUIRED: no approved numeric threshold')
        self.assertAlmostEqual(percentile_ranks(pd.Series([1, 1, 2])).iloc[0], 50)

    def test_reference_gate_and_explicit_exclusion(self):
        self.assertEqual(analyse(self.reference, ('h_index',))['status'].iloc[0].status,
                         'DATA_REQUIRED')
        incomplete = self.reference.copy()
        incomplete.loc[0, 'middle_author_share'] = None
        result = analyse(incomplete, ('h_index',), synthetic=True)
        self.assertEqual(result['status'].iloc[0].status, 'DATA_REQUIRED')
        self.assertEqual(result['rq01_reference_author_status'].status.eq('EXCLUDED').sum(), 1)
        self.assertNotIn('rq01_residuals', result)

    def test_residual_and_bland_altman_figures(self):
        result = analyse(self.reference, ('h_index',), synthetic=True)
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as folder:
            self.assertGreater(residual_plot(result['rq01_residuals'],
                'fitted_nm_percentile', folder, 'fitted.png').stat().st_size, 0)
            self.assertGreater(residual_plot(result['rq01_residuals'],
                'middle_author_share', folder, 'middle.png').stat().st_size, 0)
            self.assertGreater(bland_altman_plot(result['rq01_bland_altman_pairs'],
                result['rq01_bland_altman_summary'], folder, 'ba.png').stat().st_size, 0)
            self.assertGreater(difference_histogram(result['rq01_bland_altman_pairs'],
                result['rq01_bland_altman_summary'], folder, 'hist.png').stat().st_size, 0)


class RQ7MethodologyTests(unittest.TestCase):
    def test_frozen_benchmarks_do_not_change_with_source_or_snapshot_edits(self):
        tables = {name: pd.DataFrame({'value': [1., 2.]}) for name in BENCHMARK_TABLES}
        frozen = FrozenBenchmarks.from_original(['TEST_A','TEST_B'], tables,
            version='TEST_ORIGINAL_V1', synthetic=True)
        digest = frozen.sha256
        tables['field_year_means'].loc[0, 'value'] = 99
        copy = frozen.snapshot('field_year_means')
        self.assertEqual(copy.iloc[0]['value'], 1)
        copy.loc[0, 'value'] = 100
        self.assertEqual(frozen.snapshot('field_year_means').iloc[0]['value'], 1)
        self.assertEqual(frozen.sha256, digest)
        with self.assertRaises(MethodologyInputRequired):
            FrozenBenchmarks.from_original(['A'], tables, version='REAL_V1')

    def test_percentile_inflation_and_zero_guard(self):
        self.assertEqual(percentile_inflation(40, 50)['inflation_percent'], 25)
        zero = percentile_inflation(0, 50)
        self.assertEqual(zero['status'], 'NOT_APPLICABLE')
        self.assertTrue(np.isnan(zero['inflation_percent']))

    def test_self_citation_uses_actual_new_paper_and_edge(self):
        papers = pd.DataFrame([dict(pub_id='P0', authors=('A','C'),
            year=2020, field='F', total_citation=2)])
        edges = pd.DataFrame([dict(citation_id=f'E{i}', cited_pub_id='P0',
                                   citing_pub_id=f'OLD{i}') for i in range(2)])
        additions = pd.DataFrame([dict(pub_id='Q1', authors=('A','C','X'),
            year=2021, field='F', total_citation=0, citation_id='E2',
            cited_pub_id='P0')])
        result_papers, result_edges = add_self_citation_relationships(
            papers, edges, additions, target_author='A',
            relevant_core_authors={'C'}, original_self_citation_count=2)
        self.assertEqual(len(result_papers), 2)
        self.assertEqual(len(result_edges), 3)
        self.assertEqual(result_edges.iloc[-1].citing_pub_id, 'Q1')
        self.assertEqual(result_papers.loc[result_papers.pub_id.eq('P0'),
                          'total_citation'].iloc[0], 3)
        self.assertEqual(len(papers), 1)
        with self.assertRaises(MethodologyInputRequired):
            add_self_citation_relationships(papers, edges, additions,
                target_author='A', relevant_core_authors={'C'},
                original_self_citation_count=3)

    def test_salami_preserves_authors_field_year_and_balances_real_edges(self):
        papers = pd.DataFrame([dict(pub_id='P0', authors=('A','B'),
            year=2020, field_weights={'F': 1.}, total_citation=4)])
        edges = pd.DataFrame([dict(citation_id=f'E{i}', cited_pub_id='P0',
                                   citing_pub_id=f'Q{i}') for i in range(4)])
        assignments = pd.DataFrame({'citation_id': [f'E{i}' for i in range(4)],
                                    'half': [1, 1, 2, 2]})
        output, links = split_salami_papers(papers, edges, assignments,
                                            target_pub_ids=['P0'])
        self.assertEqual(output.total_citation.tolist(), [2., 2.])
        self.assertTrue(all(x == ('A','B') for x in output.authors))
        self.assertEqual(output.field_weights.tolist(), [{'F': 1.}, {'F': 1.}])
        self.assertEqual(set(output.year), {2020})
        self.assertEqual(links.cited_pub_id.value_counts().tolist(), [2, 2])
        self.assertEqual(papers.iloc[0].total_citation, 4)

    def test_gift_authorship_uses_existing_coauthor_papers(self):
        papers = pd.DataFrame([dict(pub_id=f'P{i}', authors=('A','B'),
            year=2020, field_weights={'F': 1.}, total_citation=2) for i in range(10)] +
            [dict(pub_id=f'G{i}', authors=('B','C','D'), year=2019,
                  field_weights={'F': 1.}, total_citation=5) for i in range(3)])
        assignments = pd.DataFrame({'pub_id': ['G0','G1','G2'],
                                    'position': [2,2,2]})
        output = add_gift_authorship(papers, assignments,
            target_author='A', target_portfolio_ids=[f'P{i}' for i in range(10)])
        self.assertEqual(output.loc[output.pub_id.eq('G0'), 'authors'].iloc[0],
                         ('B','A','C','D'))
        self.assertEqual(output.loc[output.pub_id.eq('G0'), 'total_citation'].iloc[0], 5)
        self.assertEqual(papers.loc[papers.pub_id.eq('G0'), 'authors'].iloc[0],
                         ('B','C','D'))
        with self.assertRaises(MethodologyInputRequired):
            add_gift_authorship(papers, assignments,
                target_author='A', target_portfolio_ids=[f'P{i}' for i in range(5)])

    def test_aggregate_counts_never_claim_full_nm_recalculation(self):
        authors = pd.DataFrame({'author_id': ['TEST_A'], 'nm_index': [55.]})
        aggregate = pd.DataFrame({'author_id': ['TEST_A'],
            'total_citation': [10], 'self_citation_count': [2],
            'coauthor_count': [3]})
        result = run_rq07(authors, [], paper_inputs=aggregate)
        self.assertEqual(len(result['gaming_resistance']), 4)
        self.assertTrue(result['gaming_resistance'].manipulated_nm_percentile.isna().all())
        self.assertTrue(result['gaming_resistance'].status.eq('METHODOLOGY_INPUT_REQUIRED').all())


if __name__ == '__main__':
    unittest.main()
