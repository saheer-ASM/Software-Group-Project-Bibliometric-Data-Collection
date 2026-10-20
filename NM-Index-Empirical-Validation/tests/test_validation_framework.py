"""Offline source-grounded metrics, statistics and mocked integration tests."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from analysis.agreement import icc
from analysis.correlation import correlate
from analysis.discrimination import roc_auc
from analysis.fairness import subgroup
from analysis.gaming import simulate
from analysis.paired_tests import compare
from analysis.pca import analyze
from analysis.predictive import future_association
from analysis.robustness import sample_size
from analysis.temporal import rank_stability
from metrics.inputs import prepare_data
from metrics import total_cites, h_index, g_index
from metrics.m_index import calculate as calculate_m, CareerConvention
from metrics.hm_index import calculate as calculate_hm
from metrics.hf_index import calculate as calculate_hf
from metrics.fi_score import FiStrategy
from metrics.ar_index import ARStrategy
from metrics.strategy import MetricStrategy, calculate_with_strategy
from metrics.c_score import calculate_raw, calculate_self_citation_adjusted
from metrics.fi_score import calculate as calculate_fi
from metrics.s_index import calculate as calculate_s
from metrics.ar_index import calculate as calculate_ar
from nm_index.loader import COMPONENT_COLUMNS, load as load_nm
from src.config import PROJECT_ROOT, ValidationConfig
from src.database import execute_select_batch, UnsafeQueryError
from src.data_quality import check
from src.external_inputs import load_csv
from src.eligibility import EligibilityRules, evaluate
from src.pipeline import dry_run, run_from_extracts, EXPERIMENT_MODULES
from src.repository import Extracts, QUERIES, REQUIRED_COLUMNS, verify_schema
from src.validation_dataset import build
from experiments.rq08_predictive_validity import run as run_rq08
from visualization.distributions import histogram
from visualization.correlations import scatter, heatmap
from visualization.construct import scree


def authorship(pub, author='A1'):
    return {'pub_id': pub, 'author1id': author}


def nm_rows(authors):
    return pd.DataFrame([dict(author_id=author, nm_index=float(i+1), metrics_available=6,
                              calculated_at=None, **{c: float(i+1) for c in COMPONENT_COLUMNS})
                         for i, author in enumerate(authors)])


class MetricTests(unittest.TestCase):
    def test_explicit_raw_metrics_and_duplicate_link(self):
        data = prepare_data([{'author_id': 'A1'}],
            [{'pub_id': f'P{i}', 'total_citation': c} for i, c in enumerate([50, 20, 30, 40, 25])],
            [authorship(f'P{i}') for i in range(5)] + [authorship('P1')])
        self.assertEqual(total_cites.calculate(data)['A1'], 165)
        self.assertEqual(h_index.calculate(data)['A1'], 5)
        self.assertEqual(g_index.calculate(data)['A1'], 5)
        self.assertEqual(data.issues['duplicate_authorship_links'], 1)

    def test_empty_zero_ties_missing(self):
        zero = prepare_data([{'author_id':'A1'}, {'author_id':'A2'}],
            [{'pub_id':'P1','total_citation':0}, {'pub_id':'P2','total_citation':0}],
            [authorship('P1'), authorship('P2')])
        self.assertEqual(total_cites.calculate(zero)['A1'], 0)
        self.assertEqual(h_index.calculate(zero)['A1'], 0)
        self.assertEqual(g_index.calculate(zero)['A1'], 0)
        self.assertTrue(pd.isna(total_cites.calculate(zero)['A2']))
        tied = prepare_data([{'author_id':'A1'}],
            [{'pub_id':'P1','total_citation':3}, {'pub_id':'P2','total_citation':3}],
            [authorship('P1'), authorship('P2')])
        self.assertEqual(h_index.calculate(tied)['A1'], 2)
        self.assertEqual(g_index.calculate(tied)['A1'], 2)
        missing = prepare_data([{'author_id':'A1'}], [{'pub_id':'P1','total_citation':None}], [authorship('P1')])
        self.assertTrue(pd.isna(g_index.calculate(missing)['A1']))

    def test_pending_baselines_require_explicit_strategy(self):
        inputs = pd.DataFrame({'author_id':['A1'], 'total_citation':[5]})
        for fn in (calculate_hm, calculate_raw,
                   calculate_self_citation_adjusted, calculate_fi, calculate_s, calculate_ar):
            with self.subTest(fn=fn.__module__), self.assertRaisesRegex(ValueError, 'METHODOLOGY_PENDING'):
                fn(inputs)
        with self.assertRaisesRegex(ValueError, 'DATA_REQUIRED'):
            calculate_hf(inputs)
        with self.assertRaisesRegex(ValueError, 'METHODOLOGY_PENDING'):
            calculate_fi(inputs, FiStrategy('source', lambda x: x, lambda x: 1, lambda x, t: 1))
        with self.assertRaisesRegex(ValueError, 'METHODOLOGY_PENDING'):
            calculate_ar(inputs, ARStrategy('source', date(2025, 1, 1), lambda y, d: 1, lambda x: 1))
        with self.assertRaisesRegex(ValueError, 'invalid threshold'):
            calculate_fi(inputs, FiStrategy('source', lambda x: x, lambda x: float('inf'),
                                           lambda x, t: 1, 'approved test decision'))
        dated = inputs.assign(year=2020)
        with self.assertRaisesRegex(ValueError, 'invalid paper age'):
            calculate_ar(dated, ARStrategy('source', date(2025, 1, 1),
                                           lambda y, d: -1, lambda x: 1,
                                           'approved test decision'))
        with self.assertRaisesRegex(ValueError, 'invalid value'):
            calculate_with_strategy('s_index', inputs, MetricStrategy('s_index', 'approved source',
                ('total_citation',), lambda group: float('inf'), 'approved decision'))
        with self.assertRaisesRegex(ValueError, 'METHODOLOGY_PENDING'):
            calculate_m(pd.Series({'A1':2}), pd.Series({'A1':2020}))
        convention = CareerConvention('first observed publication', date(2025, 1, 1),
            'approved synthetic five-year example', 'missing', lambda first, as_of: as_of.year-first,
            'TEST DATA ONLY: synthetic method decision')
        self.assertAlmostEqual(calculate_m(pd.Series({'A1':2}), pd.Series({'A1':2020}), convention)['A1'], .4)

    def test_latest_pdf_conventional_hf_is_distinct_from_modified_component(self):
        # PDF pp. 19, 22-25: 50/3, 20/5, 30/4, 40/6, 25/4.
        papers = pd.DataFrame({'author_id': ['A1']*5,
            'pub_id': [f'P{i}' for i in range(5)],
            'total_citation': [50, 20, 30, 40, 25],
            'coauthor_count': [3, 5, 4, 6, 4]})
        self.assertEqual(calculate_hf(papers, verified_authorship=True)['A1'], 4)
        tied = pd.DataFrame({'author_id': ['A2', 'A2'], 'pub_id': ['T1', 'T2'],
                             'total_citation': [4, 4], 'coauthor_count': [2, 2]})
        self.assertEqual(calculate_hf(tied, verified_authorship=True)['A2'], 2)
        zero = pd.DataFrame({'author_id': ['A3'], 'pub_id': ['Z'],
                             'total_citation': [0], 'coauthor_count': [1]})
        self.assertEqual(calculate_hf(zero, verified_authorship=True)['A3'], 0)
        self.assertEqual(calculate_hf(pd.DataFrame(columns=papers.columns),
                                      verified_authorship=True).size, 0)
        missing = papers.copy()
        missing.loc[0, 'coauthor_count'] = None
        self.assertTrue(pd.isna(calculate_hf(missing, verified_authorship=True)['A1']))
        duplicate = pd.concat([papers, papers.iloc[[0]]], ignore_index=True)
        self.assertEqual(calculate_hf(duplicate, verified_authorship=True)['A1'], 4)
        duplicate.loc[5, 'coauthor_count'] = 7
        self.assertTrue(pd.isna(calculate_hf(duplicate, verified_authorship=True)['A1']))


class StatisticalTests(unittest.TestCase):
    def test_correlation_and_paired(self):
        frame = pd.DataFrame({'nm_index':[1,2,3,4,5], 'h_index':[2,4,6,8,10]})
        result = correlate(frame, 'nm_index', ['h_index']).iloc[0]
        self.assertEqual(result.status, 'OK')
        self.assertAlmostEqual(result.correlation, 1)
        pair = compare(frame, 'nm_index', ['h_index']).iloc[0]
        self.assertEqual(pair.n, 5)
        self.assertLess(pair.mean_difference, 0)
        self.assertEqual(icc(frame, 'nm_index', 'h_index')['status'], 'METHODOLOGY_PENDING')
        identical = pd.DataFrame({'a':[1,2,3,4], 'b':[1,2,3,4]})
        chosen = icc(identical, 'a', 'b', model='ICC(A,1) two-way random absolute agreement')
        self.assertEqual(chosen['status'], 'OK')
        self.assertAlmostEqual(chosen['icc'], 1)

    def test_roc_pca_robustness_fairness_and_temporal(self):
        frame = pd.DataFrame({'author_id':[f'A{i}' for i in range(10)],
            'score': list(range(10)), 'label':[0]*5+[1]*5,
            'group':['X']*5+['Y']*5})
        roc, curve = roc_auc(frame, 'score', 'label', bootstrap=20)
        self.assertEqual(roc['status'], 'OK')
        self.assertAlmostEqual(roc['auc'], 1)
        self.assertFalse(curve.empty)
        self.assertEqual(subgroup(frame, 'score', 'group').iloc[0].status, 'METHODOLOGY_PENDING')
        self.assertEqual(len(subgroup(frame, 'score', 'group', approved_labels=True)), 2)
        six = pd.DataFrame({f'C{i}': np.arange(10)+np.sin(np.arange(10)*(.1+i)) for i in range(6)})
        summary, loadings = analyze(six, list(six.columns))
        self.assertEqual(summary['status'], 'OK')
        self.assertEqual(loadings.shape, (6, 7))
        self.assertEqual(sample_size(frame.rename(columns={'score':'nm_index', 'label':'h_index'}),
                                     'nm_index', 'h_index', [5], seed=3).iloc[0].status, 'OK')
        annual = pd.DataFrame({'author_id':['A1','A2','A3']*2,
            'year':[2020]*3+[2021]*3, 'score':[1,2,3,2,1,3]})
        self.assertEqual(rank_stability(annual, 'score', first_year=2020, second_year=2021)['status'], 'METHODOLOGY_PENDING')
        self.assertTrue(pd.isna(rank_stability(annual, 'score', first_year=2020,
                                             second_year=2021)['proportion_over_ten_percent']))

    def test_future_window_and_simulation_guards(self):
        frame = pd.DataFrame({'score':[1,2,3,4], 'outcome':[2,4,6,8]})
        self.assertEqual(future_association(frame,'score','outcome',score_year=2020,
                          outcome_start=2021,outcome_end=2025)['status'], 'OK')
        self.assertEqual(future_association(frame,'score','outcome',score_year=2020,
                          outcome_start=2020,outcome_end=2025)['status'], 'INVALID_INPUT')
        with self.assertRaisesRegex(ValueError, 'Observed self-citation'):
            simulate([5], scenario='self_citations_plus_50_percent')


class IntegrationTests(unittest.TestCase):
    def test_eligibility_explains_citation_and_time_exclusions(self):
        frame = pd.DataFrame([dict(author_id='A1', linked_publications=5,
            raw_total_cites=9, nm_index_available=True, full_portfolio_verified=True,
            metric_coverage_percentage=.5, observed_first_year=2010,
            observed_last_year=2020)])
        result = evaluate(frame, EligibilityRules(required_time_span=(2000, 2024)))
        self.assertFalse(result.iloc[0].eligible_for_validation)
        self.assertIn('MIN_RAW_CITES', result.iloc[0].eligibility_reason)
        self.assertIn('TIME_SPAN', result.iloc[0].eligibility_reason)

    def test_external_input_stays_local_and_rq08_needs_historical_scores(self):
        with self.assertRaisesRegex(ValueError, 'inside the isolated validation project'):
            load_csv('award_labels', PROJECT_ROOT.parent/'outside.csv')
        response = run_rq08(pd.DataFrame({'author_id':['A1'], 'nm_index':[9]}), [],
                            future_outcomes=pd.DataFrame({'author_id':['A1'],
                              'outcome_start_year':[2021], 'outcome_end_year':[2025]}), score_year=2020)
        self.assertEqual(response['status'].iloc[0].status, 'DATA_REQUIRED')

    def test_png_exports_are_local_and_non_overwriting(self):
        frame = pd.DataFrame({'nm_index':[1,2,3], 'h_index':[2,3,4]})
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as folder:
            self.assertTrue(histogram(frame, 'nm_index', folder, 'distribution.png').is_file())
            self.assertTrue(scatter(frame, 'nm_index', 'h_index', folder, 'scatter.png').is_file())
            self.assertTrue(heatmap(frame.corr(), folder, 'heatmap.png').is_file())
            self.assertTrue(scree([.6,.4], folder, 'scree.png').is_file())
            with self.assertRaises(FileExistsError):
                histogram(frame, 'nm_index', folder, 'distribution.png')

    def test_repository_fixed_queries_and_schema_check(self):
        from src.database import validate_select
        for sql in QUERIES.values():
            validate_select(sql)
        rows = [{'table_name':table, 'column_name':column} for table, columns in REQUIRED_COLUMNS.items()
                for column in columns]
        self.assertTrue(verify_schema(rows))
        with self.assertRaisesRegex(ValueError, 'table=publication column=total_citation'):
            verify_schema([r for r in rows if not (r['table_name']=='publication' and r['column_name']=='total_citation')])

    def test_batch_rejects_write_before_connect(self):
        with patch('src.database.psycopg2.connect') as connect:
            with self.assertRaises(UnsafeQueryError):
                execute_select_batch({'unsafe': 'DELETE FROM public.author'})
            connect.assert_not_called()

    def test_stored_nm_identity_and_one_row_dataset(self):
        authors = pd.DataFrame({'author_id':['A1']})
        nm = nm_rows(['A1'])
        self.assertEqual(load_nm(nm).iloc[0].nm_index_source, 'STORED_PRODUCTION_RESULT')
        quality = pd.DataFrame({'author_id':['A1'], 'linked_publications':[5], 'full_portfolio_verified':[True]})
        dataset = build(authors, nm, {'h_index':pd.Series({'A1':3})}, quality)
        self.assertEqual(len(dataset), 1)
        self.assertEqual(dataset.iloc[0].nm_index, 1)
        self.assertTrue(pd.isna(dataset.iloc[0].c_score_raw))

    def test_stored_nm_requires_all_six_component_percentiles_for_eligibility(self):
        authors = pd.DataFrame({'author_id': ['A1']})
        nm = nm_rows(['A1'])
        quality = pd.DataFrame({'author_id': ['A1'], 'linked_publications': [5],
                                'full_portfolio_verified': [True]})
        raw = {'raw_total_cites': pd.Series({'A1': 20})}
        complete = build(authors, nm, raw, quality)
        self.assertTrue(bool(complete.iloc[0].eligible_for_validation))
        nm.loc[0, 'per_modified_g_index'] = None
        incomplete = build(authors, nm, raw, quality)
        self.assertEqual(incomplete.iloc[0].nm_index, complete.iloc[0].nm_index)
        self.assertFalse(bool(incomplete.iloc[0].eligible_for_validation))
        self.assertIn('NM_COMPONENTS_INCOMPLETE', incomplete.iloc[0].eligibility_reason)

    def test_mocked_pipeline_and_dry_run_never_connect(self):
        authors = pd.DataFrame({'author_id':['A1'], 'author_name':['Example']})
        pubs = pd.DataFrame({'pub_id':[f'P{i}' for i in range(5)], 'year':[2020]*5,
                             'total_citation':[5,4,3,2,1], 'source':[None]*5})
        wide = pd.DataFrame([authorship(f'P{i}') for i in range(5)])
        citation = pd.DataFrame(columns=['pub_id','cites_pub_id'])
        fields = pd.DataFrame(columns=['pub_id'])
        components = pd.DataFrame({'author_id':['A1'], **{name:[float(i+1)] for i,name in
            enumerate(('nm_raw_t','nm_raw_s','nm_raw_u','nm_raw_hf','nm_raw_hm','nm_raw_g'))}})
        extracts = Extracts(authors, pubs, citation, wide, fields, nm_rows(['A1']), components)
        with patch('src.database.psycopg2.connect') as connect:
            self.assertEqual(dry_run(['rq01'])['status'], 'DRY_RUN_OK')
            connect.assert_not_called()
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'results') as folder:
            config = ValidationConfig(None, 5, 0, 9, Path(folder))
            output = run_from_extracts(extracts, experiment_names=list(EXPERIMENT_MODULES),
                                       settings=config, output_directory=folder,
                                       generate_figures=False,
                                       extra_inputs={'pca_preprocessing': 'complete_case_z_standardization',
                                                     'pca_decision_reference': 'TEST DATA ONLY: synthetic PCA convention'})
            self.assertTrue((output/'validation_dataset.csv').is_file())
            self.assertTrue((output/'pca_status.csv').is_file())
            self.assertEqual(pd.read_csv(output/'validation_dataset.csv').iloc[0].raw_total_cites, 15)
            snapshot = pd.read_csv(output/'validation_dataset.csv')
            self.assertFalse(bool(snapshot.iloc[0].full_portfolio_verified))
            self.assertFalse(bool(snapshot.iloc[0].eligible_for_validation))
            self.assertIn('PORTFOLIO_UNVERIFIED', snapshot.iloc[0].eligibility_reason)

            verification = pd.DataFrame([dict(author_id='A1', portfolio_verified=True,
                                               evidence_reference='independent synthetic audit')])
            verified_output = run_from_extracts(extracts, experiment_names=['rq01'],
                settings=config, output_directory=folder, generate_figures=False,
                extra_inputs={'portfolio_verification': verification})
            verified = pd.read_csv(verified_output/'validation_dataset.csv')
            self.assertTrue(bool(verified.iloc[0].full_portfolio_verified))
            self.assertTrue(bool(verified.iloc[0].eligible_for_validation))
            self.assertTrue(pd.isna(verified.iloc[0].hf_index))


if __name__ == '__main__':
    unittest.main()
