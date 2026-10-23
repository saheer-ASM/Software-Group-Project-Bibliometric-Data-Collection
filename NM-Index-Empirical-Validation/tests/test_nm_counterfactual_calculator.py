"""Offline equation and isolation checks using invented TEST-only graphs."""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from analysis.counterfactual import (BENCHMARK_TABLES, FrozenBenchmarks,
    MethodologyInputRequired, add_self_citation_relationships,
    split_salami_papers)
from nm_index.counterfactual_calculator import (NMParameters, _percentile,
    _blom_percentile, _shares, calculate_nm)
from analysis.rq07_engine import AuthorGraphInput, run_author_graph
from experiments.rq07_gaming_sensitivity import run as run_rq07
from src.config import PROJECT_ROOT
from src.rq07_bundle import load_bundle
from src.phase6_readiness import read_cohort
from src.pipeline import run_cohort


def fixture():
    papers = pd.DataFrame([
        dict(pub_id='P', authors=('TEST_A', 'TEST_B'), year=2020,
             field='F', field_weights={'F': 1.}, contribution_mode='uniform', total_citation=2),
        dict(pub_id='Q0', authors=('TEST_B', 'TEST_C'), year=2021,
             field='F', field_weights={'F': 1.}, contribution_mode='uniform', total_citation=0),
        dict(pub_id='Q1', authors=('TEST_A', 'TEST_C'), year=2021,
             field='F', field_weights={'F': 1.}, contribution_mode='uniform', total_citation=0),
    ])
    edges = pd.DataFrame([
        dict(citation_id='E0', cited_pub_id='P', citing_pub_id='Q0'),
        dict(citation_id='E1', cited_pub_id='P', citing_pub_id='Q1'),
    ])
    ids = ['TEST_A', 'TEST_B']
    reference = pd.DataFrame([
        dict(author_id=author, metric=metric, value=value)
        for metric in (*('t', 's', 'u', 'hf', 'hm', 'g'), 'nm_index')
        for author, value in zip(ids, (0., 100.))
    ])
    tables = {
        'field_year_means': pd.DataFrame([
            dict(field='F', year=year, mean_adjusted_citations=1.,
                 field_mean_adjusted_citations=1.) for year in (2020, 2021)]),
        'field_caps': pd.DataFrame([dict(field='F', cap=10., hf_reference=1.,
                                         hm_reference=1., g_reference=1.)]),
        'z_means': pd.DataFrame([dict(metric=m, mean=.5, distribution='lognormal')
                                 for m in ('t', 's', 'u')]),
        'z_standard_deviations': pd.DataFrame([dict(metric=m, sd=.5)
                                               for m in ('t', 's', 'u')]),
        'percentile_reference': reference,
    }
    assert set(tables) == set(BENCHMARK_TABLES)
    frozen = FrozenBenchmarks.from_original(ids, tables, version='SYNTHETIC_TEST_REFERENCE',
                                             synthetic=True)
    return papers, edges, frozen


class NMEquationTests(unittest.TestCase):
    def test_uniform_relative_aci_and_credit_contribution(self):
        papers, _, _ = fixture()
        row = papers.iloc[0]
        self.assertEqual(_shares(row)['TEST_A'], .5)
        relative = pd.Series({'authors': ('TEST_A', 'TEST_B', 'TEST_C'),
                              'contribution_mode': 'relative',
                              'first_positions': (1,), 'last_positions': (3,)})
        shares = _shares(relative)
        self.assertGreater(shares['TEST_A'], shares['TEST_B'])
        self.assertAlmostEqual(sum(shares.values()), 1)
        aci = pd.Series({'authors': ('TEST_A', 'TEST_B'), 'contribution_mode': 'aci',
                         'aci_shares': {'TEST_A': .7, 'TEST_B': .3}})
        self.assertAlmostEqual(_shares(aci)['TEST_A'], .7)
        credit = pd.Series({'authors': ('TEST_A', 'TEST_B'), 'contribution_mode': 'credit',
                            'credit_roles': {'TEST_A': ('writing', 'analysis'),
                                             'TEST_B': ('writing',)},
                            'credit_role_weights': {'writing': 1., 'analysis': 2.}})
        self.assertAlmostEqual(_shares(credit)['TEST_A'], .75)

    def test_original_graph_recalculates_six_components_and_freezes_reference(self):
        papers, edges, frozen = fixture()
        before = papers.copy(deep=True), edges.copy(deep=True)
        parameters = NMParameters(as_of_year=2025)
        original = calculate_nm('TEST_A', papers, edges, frozen,
                                career_start_year=2020, parameters=parameters)
        self.assertEqual(set(original['raw_components']), {'t','s','u','hf','hm','g'})
        self.assertEqual(set(original['component_percentiles']), {'t','s','u','hf','hm','g'})
        self.assertGreater(original['raw_components']['t'], 0)
        self.assertAlmostEqual(original['raw_components']['t'],
                               original['career_factor'] * .5 * (.55 + .5))
        self.assertTrue(0 <= original['nm_index'] <= 100)
        self.assertEqual(_percentile(1, pd.Series([1,1,2])), 50)
        self.assertAlmostEqual(_blom_percentile(1, pd.Series([1,1,2])),
                               100*(1.5-.375)/(3+.25))
        additions = pd.DataFrame([dict(pub_id='Q2', authors=('TEST_A','TEST_B'),
            year=2021, field='F', field_weights={'F': 1.}, contribution_mode='uniform',
            total_citation=0, citation_id='E2', cited_pub_id='P')])
        changed_papers, changed_edges = add_self_citation_relationships(
            papers, edges, additions, target_author='TEST_A',
            relevant_core_authors={'TEST_B'}, original_self_citation_count=2)
        changed = calculate_nm('TEST_A', changed_papers, changed_edges, frozen,
                               career_start_year=2020, parameters=parameters)
        self.assertEqual(len(changed_edges), len(edges)+1)
        self.assertNotEqual(original['raw_components'], changed['raw_components'])
        self.assertEqual(original['benchmark_sha256'], changed['benchmark_sha256'])
        pd.testing.assert_frame_equal(papers, before[0])
        pd.testing.assert_frame_equal(edges, before[1])
        assignments = pd.DataFrame({'citation_id': ['E0','E1'], 'half': [1,2]})
        split_papers, split_edges = split_salami_papers(papers, edges, assignments,
                                                         target_pub_ids=['P'])
        split = calculate_nm('TEST_A', split_papers, split_edges, frozen,
                             career_start_year=2020, parameters=parameters)
        self.assertEqual(len(split_papers), len(papers)+1)
        self.assertEqual(split['benchmark_sha256'], original['benchmark_sha256'])
        self.assertNotEqual(split['raw_components'], original['raw_components'])

    def test_missing_graph_evidence_is_rejected(self):
        papers, edges, frozen = fixture()
        with self.assertRaises(MethodologyInputRequired):
            calculate_nm('TEST_A', papers, edges.iloc[:1], frozen,
                         career_start_year=2020, parameters=NMParameters(as_of_year=2025))
        bad = papers.copy(deep=True)
        bad.at[0, 'field_weights'] = {'F': .5}
        with self.assertRaises(MethodologyInputRequired):
            calculate_nm('TEST_A', bad, edges, frozen,
                         career_start_year=2020, parameters=NMParameters(as_of_year=2025))

    def test_salami_outgoing_relationship_requires_and_uses_explicit_half(self):
        papers, edges, _ = fixture()
        with self.assertRaises(MethodologyInputRequired):
            split_salami_papers(papers, edges,
                pd.DataFrame({'citation_id': ['E1'], 'half': [1]}),
                target_pub_ids=['Q1'])
        result_papers, result_edges = split_salami_papers(papers, edges,
            pd.DataFrame({'citation_id': ['E1'], 'half': [1], 'citing_half': [2]}),
            target_pub_ids=['Q1'])
        self.assertNotIn('Q1', set(result_papers.pub_id))
        self.assertEqual(result_edges.loc[result_edges.citation_id.eq('E1'),
                                          'citing_pub_id'].iloc[0], 'Q1__SPLIT_2')

    def test_rq07_runner_recalculates_only_fully_evidenced_scenarios(self):
        papers, edges, frozen = fixture()
        original_papers, original_edges = papers.copy(deep=True), edges.copy(deep=True)
        additions = pd.DataFrame([dict(pub_id='Q2', authors=('TEST_A','TEST_B'),
            year=2021, field='F', field_weights={'F': 1.}, contribution_mode='uniform',
            total_citation=0, citation_id='E2', cited_pub_id='P')])
        assignments = pd.DataFrame({'citation_id': ['E0','E1'],
                                    'half': [1,2], 'citing_half': [None,1]})
        graph = AuthorGraphInput(papers=papers, edges=edges, career_start_year=2020,
            self_additions=additions, original_self_citation_count=2,
            relevant_core_authors=frozenset({'TEST_B'}), salami_assignments=assignments)
        result = run_rq07(pd.DataFrame({'author_id':['TEST_A']}), [],
            graph_inputs={'TEST_A': graph}, frozen_benchmarks=frozen,
            nm_parameters=NMParameters(as_of_year=2025))
        output = result['gaming_resistance'].set_index('scenario')
        self.assertEqual(output.loc['self_citations_plus_50_percent', 'status'], 'OK')
        self.assertEqual(output.loc['salami_double_papers_half_citations', 'status'], 'OK')
        self.assertEqual(output.loc['gift_authorship_plus_30_percent', 'status'],
                         'INPUT_DATA_REQUIRED')
        self.assertNotEqual(output.loc['self_citations_plus_50_percent', 'original_nm_index'],
                            output.loc['self_citations_plus_50_percent', 'manipulated_nm_index'])
        self.assertEqual(output.benchmark_sha256.nunique(), 1)
        pd.testing.assert_frame_equal(papers, original_papers)
        pd.testing.assert_frame_equal(edges, original_edges)

    def test_gift_authorship_recomputes_contribution_and_nm(self):
        _, _, frozen = fixture()
        papers = pd.DataFrame([
            dict(pub_id=f'P{i}', authors=('TEST_A','TEST_B'), year=2020,
                 field='F', field_weights={'F': 1.}, contribution_mode='uniform',
                 total_citation=0) for i in range(10)] +
            [dict(pub_id=f'G{i}', authors=('TEST_B','TEST_C','TEST_D'), year=2021,
                  field='F', field_weights={'F': 1.}, contribution_mode='uniform',
                  total_citation=1) for i in range(3)] +
            [dict(pub_id=f'Q{i}', authors=('TEST_X',), year=2021,
                  field='F', field_weights={'F': 1.}, contribution_mode='uniform',
                  total_citation=0) for i in range(3)])
        edges = pd.DataFrame([dict(citation_id=f'E{i}', cited_pub_id=f'G{i}',
                                   citing_pub_id=f'Q{i}') for i in range(3)])
        before = papers.copy(deep=True)
        assignments = pd.DataFrame({'pub_id':[f'G{i}' for i in range(3)],
                                    'position':[2]*3})
        graph = AuthorGraphInput(papers=papers, edges=edges, career_start_year=2020,
                                 gift_assignments=assignments)
        scenarios, _ = run_author_graph('TEST_A', graph, frozen, NMParameters(as_of_year=2025))
        gift = scenarios.set_index('scenario').loc['gift_authorship_plus_30_percent']
        self.assertEqual(gift['status'], 'OK')
        self.assertEqual(gift['original_paper_count'], 10)
        self.assertEqual(gift['manipulated_paper_count'], 13)
        self.assertNotEqual(gift['original_nm_index'], gift['manipulated_nm_index'])
        pd.testing.assert_frame_equal(papers, before)

    def test_canonical_bundle_schema_without_legacy_field_runs_salami_and_gift(self):
        # The handover papers.csv contract carries field_weights only, never `field`.
        papers, edges, frozen = fixture()
        papers = papers.drop(columns='field')
        assignments = pd.DataFrame({'citation_id': ['E0', 'E1'],
                                    'half': [1, 2], 'citing_half': [None, 1]})
        graph = AuthorGraphInput(papers=papers, edges=edges, career_start_year=2020,
                                 salami_assignments=assignments)
        scenarios, _ = run_author_graph('TEST_A', graph, frozen, NMParameters(as_of_year=2025))
        self.assertEqual(scenarios.set_index('scenario').loc[
            'salami_double_papers_half_citations', 'status'], 'OK')
        gift_papers = pd.DataFrame([
            dict(pub_id=f'P{i}', authors=('TEST_A','TEST_B'), year=2020,
                 field_weights={'F': 1.}, contribution_mode='uniform',
                 total_citation=0) for i in range(10)] +
            [dict(pub_id=f'G{i}', authors=('TEST_B','TEST_C'), year=2021,
                  field_weights={'F': 1.}, contribution_mode='uniform',
                  total_citation=0) for i in range(3)])
        graph = AuthorGraphInput(papers=gift_papers, edges=edges.iloc[:0],
            career_start_year=2020, gift_assignments=pd.DataFrame(
                {'pub_id': [f'G{i}' for i in range(3)], 'position': [2]*3}))
        scenarios, _ = run_author_graph('TEST_A', graph, frozen, NMParameters(as_of_year=2025))
        self.assertEqual(scenarios.set_index('scenario').loc[
            'gift_authorship_plus_30_percent', 'status'], 'OK')

    def test_combined_manipulation_is_explicitly_pending_not_composed(self):
        papers, edges, frozen = fixture()
        graph = AuthorGraphInput(papers=papers, edges=edges, career_start_year=2020)
        scenarios, baselines = run_author_graph('TEST_A', graph, frozen,
                                                NMParameters(as_of_year=2025))
        combined = scenarios.set_index('scenario').loc['combined']
        self.assertEqual(combined['status'], 'METHODOLOGY_PENDING')
        self.assertTrue(pd.isna(combined['manipulated_nm_percentile']))
        self.assertFalse(pd.isna(combined['original_nm_percentile']))
        self.assertTrue(baselines.loc[baselines.scenario.eq('combined'), 'status']
                        .eq('METHODOLOGY_PENDING').all())
        self.assertEqual(set(baselines.loc[baselines.scenario.eq('combined'), 'metric']),
                         {'raw_total_cites', 'h_index', 'hf_index', 'g_index',
                          'hm_index', 'c_score_raw'})
        result = run_rq07(pd.DataFrame({'author_id': ['TEST_A', 'TEST_B']}), [],
            graph_inputs={'TEST_A': graph}, frozen_benchmarks=frozen,
            nm_parameters=NMParameters(as_of_year=2025))
        output = result['gaming_resistance']
        self.assertEqual(output.groupby('author_id').size().to_dict(), {'TEST_A': 4, 'TEST_B': 4})
        self.assertTrue(output.loc[output.scenario.eq('combined'), 'status']
                        .eq('METHODOLOGY_PENDING').all())
        self.assertEqual(result['status'].iloc[0]['status'], 'INPUT_DATA_REQUIRED')
        self.assertIn('combined', result['status'].iloc[0]['issue'])

    def test_local_bundle_loader_uses_fixed_ids_and_no_database(self):
        papers, edges, frozen = fixture()
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temporary:
            root = Path(temporary)
            (root/'reference').mkdir()
            graph_root = root/'graphs'/'TEST_A'
            graph_root.mkdir(parents=True)
            for name in BENCHMARK_TABLES:
                frozen.snapshot(name).to_csv(root/'reference'/f'{name}.csv', index=False)
            metadata = dict(version=frozen.version, as_of_year=2025, epsilon_0=.90,
                            career_boost=1.25, career_decay=.0601,
                            component_weights=[1/6]*6)
            (root/'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
            paper_csv = papers.copy()
            for column in ('authors', 'field_weights'):
                paper_csv[column] = paper_csv[column].map(json.dumps)
            paper_csv.to_csv(graph_root/'papers.csv', index=False)
            edges.to_csv(graph_root/'citation_edges.csv', index=False)
            additions = paper_csv.iloc[:0].copy()
            additions['citation_id'] = pd.Series(dtype='string')
            additions['cited_pub_id'] = pd.Series(dtype='string')
            additions.to_csv(graph_root/'self_additions.csv', index=False)
            pd.DataFrame({'citation_id':['E0','E1'], 'half':[1,2],
                          'citing_half':[None,1]}).to_csv(
                              graph_root/'salami_assignments.csv', index=False)
            pd.DataFrame({'pub_id':pd.Series(dtype='string'),
                          'position':pd.Series(dtype='int64')}).to_csv(
                              graph_root/'gift_assignments.csv', index=False)
            (graph_root/'self_metadata.json').write_text(json.dumps(dict(
                career_start_year=2020, original_self_citation_count=2,
                relevant_core_authors=['TEST_B'])), encoding='utf-8')
            graphs, reference, parameters = load_bundle(root, ['TEST_A'], synthetic=True)
            self.assertEqual(set(graphs), {'TEST_A'})
            self.assertEqual(reference.sha256, frozen.sha256)
            self.assertEqual(parameters.as_of_year, 2025)
            with self.assertRaises(ValueError):
                load_bundle(root, ['TEST_MISSING'], synthetic=True)

    def test_real_cohort_entrypoint_validates_exact_fixed_ids_before_db(self):
        _, ids = read_cohort()
        self.assertEqual(len(ids), 995)
        self.assertEqual(len(set(ids)), 995)
        with patch('src.database.psycopg2.connect') as connection:
            with self.assertRaisesRegex(ValueError, 'DATA_REQUIRED'):
                run_cohort(experiment_names=('rq07',), extra_inputs={})
            connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
