"""Offline source-selection tests; no database connection or real experiment."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.config import PROJECT_ROOT, ValidationConfig
from src.database_first import resolve_real_inputs
from src.pipeline import _DATABASE_SOURCE_TOKEN, run_cohort, run_from_extracts
from src.repository import Extracts
from analysis.rq07_engine import run_author_graph
from tests.fixtures.synthetic import _rq07_graph_fixture


def verification(author='A1', *, approved=True, evidence='verified fixture'):
    return pd.DataFrame([dict(author_id=author, portfolio_verified=approved,
                              evidence_reference=evidence)])


def reference(author='A1'):
    return pd.DataFrame([dict(author_id=author, nm_index=25., c_score_raw=10.,
        middle_author_share=.2, career_stage='Early', reference_version='test-v1',
        evidence_reference='verified fixture')])


class SourceResolutionTests(unittest.TestCase):
    def test_database_wins_without_reading_fallback(self):
        database = verification(evidence='database attestation')
        selected, decisions = resolve_real_inputs(['A1'], ['rq02'],
            {'_fallback_paths': {'portfolio_verification': 'inputs/does_not_exist.csv'}},
            {'portfolio_verification': database})
        self.assertIs(selected['portfolio_verification'], database)
        self.assertEqual(decisions[0].source, 'DATABASE')

    def test_invalid_database_uses_verified_fallback(self):
        selected, decisions = resolve_real_inputs(['A1'], ['rq02'],
            {'portfolio_verification': verification()},
            {'portfolio_verification': verification(approved=False)})
        self.assertEqual(decisions[0].source, 'VERIFIED_FALLBACK')
        self.assertIn('Database candidate rejected', decisions[0].reason)
        self.assertEqual(decisions[0].authors_affected, 1)
        self.assertTrue(selected['portfolio_verification'].iloc[0].portfolio_verified)

    def test_missing_or_unverified_sources_remain_unavailable(self):
        selected, decisions = resolve_real_inputs(['A1'], ['rq01'],
            {'portfolio_verification': verification(approved=False),
             'reference_scores': reference().drop(columns='c_score_raw')})
        self.assertNotIn('portfolio_verification', selected)
        self.assertNotIn('reference_scores', selected)
        self.assertEqual([item.source for item in decisions], ['UNAVAILABLE', 'UNAVAILABLE'])
        self.assertTrue(all(item.records_affected == 0 for item in decisions))

    def test_reference_database_first_then_compatible_fallback(self):
        candidate = reference()
        selected, decisions = resolve_real_inputs(['A1'], ['rq01'],
            {'portfolio_verification': verification(), 'reference_scores': reference()},
            {'reference_scores': candidate}, synthetic=True)
        self.assertIs(selected['reference_scores'], candidate)
        self.assertEqual(decisions[1].source, 'DATABASE')
        selected, decisions = resolve_real_inputs(['A1'], ['rq01'],
            {'portfolio_verification': verification(), 'reference_scores': reference()},
            {'reference_scores': candidate.drop(columns='c_score_raw')}, synthetic=True)
        self.assertEqual(decisions[1].source, 'VERIFIED_FALLBACK')
        self.assertNotIn('c_score_raw', candidate.drop(columns='c_score_raw'))
        self.assertEqual(selected['reference_scores'].iloc[0].c_score_raw, 10.)

    def test_rq07_database_then_fallback_selection(self):
        bundle = _rq07_graph_fixture(['TEST_A'])
        supplied = dict(portfolio_verification=verification('TEST_A'),
            graph_inputs=bundle[0], frozen_benchmarks=bundle[1], nm_parameters=bundle[2])
        selected, decisions = resolve_real_inputs(['TEST_A'], ['rq07'], supplied,
            {'rq07_bundle': bundle}, synthetic=True)
        self.assertIs(selected['graph_inputs'], bundle[0])
        self.assertEqual(decisions[1].source, 'DATABASE')
        broken = ({}, bundle[1], bundle[2])
        selected, decisions = resolve_real_inputs(['TEST_A'], ['rq07'], supplied,
            {'rq07_bundle': broken}, synthetic=True)
        self.assertEqual(decisions[1].source, 'VERIFIED_FALLBACK')
        self.assertEqual(len(selected['graph_inputs']), 1)

    def test_rq07_bundle_field_weights_work_without_legacy_field_column(self):
        graphs, frozen, parameters = _rq07_graph_fixture(['TEST_A'])
        graph = graphs['TEST_A']
        graph.papers.drop(columns='field', inplace=True)
        graph.self_additions.drop(columns='field', inplace=True)
        scenario, _ = run_author_graph('TEST_A', graph, frozen, parameters)
        self.assertEqual(set(scenario.status), {'OK'})

    def test_existing_csv_path_is_loaded_only_as_fallback(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'inputs') as folder:
            path = Path(folder)/'portfolio_verification.csv'
            path.write_text('author_id,portfolio_verified,evidence_reference\nA1,true,verified source\n',
                            encoding='utf-8')
            selected, decisions = resolve_real_inputs(['A1'], ['rq02'],
                {'_fallback_paths': {'portfolio_verification': path}})
            self.assertEqual(decisions[0].source, 'VERIFIED_FALLBACK')
            self.assertTrue(selected['portfolio_verification'].iloc[0].portfolio_verified)


class PipelineProvenanceTests(unittest.TestCase):
    def _extracts(self):
        pubs = pd.DataFrame([dict(pub_id=f'P{i}', year=2020, total_citation=5,
                                  source='test') for i in range(5)])
        authorship = pd.DataFrame([dict(pub_id=pub_id, author1id='A1')
                                   for pub_id in pubs.pub_id])
        nm = pd.DataFrame([dict(author_id='A1', nm_index=25., metrics_available=6,
            calculated_at=None, **{name: 10. for name in (
                'per_total_cites','per_citations_per_paper','per_citation_rate',
                'per_modified_hf_index','per_modified_hm_index','per_modified_g_index')})])
        components = pd.DataFrame([dict(author_id='A1', **{name: 1. for name in (
            'nm_raw_t','nm_raw_s','nm_raw_u','nm_raw_hf','nm_raw_hm','nm_raw_g')})])
        return Extracts(pd.DataFrame([dict(author_id='A1', author_name='Author')]),
            pubs, pd.DataFrame(columns=['pub_id','cites_pub_id']), authorship,
            pd.DataFrame(columns=['pub_id']), nm, components)

    def test_real_run_records_fallback_and_unavailable_without_imputation(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'results') as folder:
            config = ValidationConfig(None, 5, 0, 2026, Path(folder))
            with patch('src.database.psycopg2.connect') as connection:
                output = run_from_extracts(self._extracts(), experiment_names=['rq01'],
                    settings=config, output_directory=folder, generate_figures=False,
                    extra_inputs={'portfolio_verification': verification()},
                    source_kind='SELECT_ONLY_POSTGRESQL_PILOT',
                    _source_token=_DATABASE_SOURCE_TOKEN)
                connection.assert_not_called()
            status = pd.read_csv(output/'input_source_status.csv')
            by_input = status.set_index('input_name')
            self.assertEqual(by_input.at['portfolio_verification', 'source'], 'VERIFIED_FALLBACK')
            self.assertEqual(by_input.at['reference_scores', 'source'], 'UNAVAILABLE')
            self.assertIn('1 stored NM rows', by_input.at['reference_scores', 'reason'])
            self.assertEqual(pd.read_csv(output/'rq01_status.csv').iloc[0].status, 'DATA_REQUIRED')
            dataset = pd.read_csv(output/'validation_dataset.csv')
            self.assertTrue(pd.isna(dataset.iloc[0].c_score_raw))
            meta = json.loads((output/'run_metadata.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['input_sources']['reference_scores']['source'], 'UNAVAILABLE')
            self.assertEqual(meta['input_sources']['portfolio_verification']['authors_affected'], 1)

    def test_cohort_without_fallback_records_unavailable_instead_of_fabricating_data(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'results') as folder:
            config = ValidationConfig(None, 5, 0, 2026, Path(folder))
            evidence = dict(database_ready_reference='test cohort readiness',
                            citation_source_reference='test citation evidence')
            with (patch('src.pipeline.load_config'),
                  patch('src.pipeline.load_validation_config', return_value=config),
                  patch('src.phase6_readiness.read_cohort', return_value=([], ['A1'])),
                  patch('src.repository.load_selected_author_ids', return_value=self._extracts()),
                  patch('src.database.psycopg2.connect') as connection):
                output = run_cohort(experiment_names=['rq07'], extra_inputs=evidence)
                connection.assert_not_called()
            statuses = pd.read_csv(output/'input_source_status.csv').set_index('input_name')
            self.assertEqual(statuses.at['portfolio_verification','source'], 'UNAVAILABLE')
            self.assertEqual(statuses.at['rq07_bundle','source'], 'UNAVAILABLE')
            self.assertEqual(pd.read_csv(output/'rq07_status.csv').iloc[0].status, 'DATA_REQUIRED')
            self.assertFalse(pd.read_csv(output/'validation_dataset.csv').iloc[0].eligible_for_validation)


if __name__ == '__main__':
    unittest.main()
