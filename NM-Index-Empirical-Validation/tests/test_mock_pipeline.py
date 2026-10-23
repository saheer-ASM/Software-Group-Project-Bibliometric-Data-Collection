"""End-to-end synthetic software tests; never use a live PostgreSQL connection."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from metrics.inputs import prepare_data
from metrics import total_cites, h_index, g_index
from src.config import PROJECT_ROOT, ValidationConfig
from src.mock_repository import LABEL, load_all
from src.models import Author, Publication, Citation, AuthorPublication, Contribution, NMIndexRecord
from src.pipeline import run_from_extracts
from tests.fixtures.synthetic import make_fixture, edge_case_records
from analysis.fairness import FairnessConvention, compare_percentiles
from experiments.rq10_pca import run as run_rq10


class MockPipelineTests(unittest.TestCase):
    def test_typed_records_enforce_stable_keys_and_bounds(self):
        self.assertEqual(Author('TEST_A1', 'Test').author_id, 'TEST_A1')
        self.assertEqual(Publication('TEST_P1', 2020, 0).total_citation, 0)
        self.assertEqual(Citation('TEST_P1', 'TEST_P2').cited_pub_id, 'TEST_P1')
        self.assertEqual(AuthorPublication('TEST_A1', 'TEST_P1', 1).position, 1)
        self.assertEqual(Contribution('TEST_A1', 'TEST_P1', .5).weight, .5)
        self.assertEqual(NMIndexRecord('TEST_A1', 50.0, 6).metrics_available, 6)
        with self.assertRaises(ValueError):
            Author('', 'Name is not an ID')
        with self.assertRaises(ValueError):
            Publication('TEST_P1', 2020, -1)
        with self.assertRaises(ValueError):
            NMIndexRecord('TEST_A1', 101.0, 6)

    def test_metric_values_independently_expected(self):
        single = prepare_data([{'author_id': 'TEST_A'}],
            [{'pub_id': 'P1', 'total_citation': 7}], [{'pub_id': 'P1', 'author1id': 'TEST_A'}])
        self.assertEqual(total_cites.calculate(single)['TEST_A'], 7)
        self.assertEqual(h_index.calculate(single)['TEST_A'], 1)
        self.assertEqual(g_index.calculate(single)['TEST_A'], 1)
        many = prepare_data([{'author_id': 'TEST_A'}],
            [{'pub_id': f'P{i}', 'total_citation': c} for i, c in enumerate((10, 4, 4, 0))],
            [{'pub_id': f'P{i}', 'author1id': 'TEST_A'} for i in range(4)])
        self.assertEqual(total_cites.calculate(many)['TEST_A'], 18)
        self.assertEqual(h_index.calculate(many)['TEST_A'], 3)
        self.assertEqual(g_index.calculate(many)['TEST_A'], 4)
        empty = prepare_data([{'author_id': 'TEST_A'}], [], [])
        self.assertTrue(pd.isna(total_cites.calculate(empty)['TEST_A']))
        missing = prepare_data([{'author_id': 'TEST_A'}],
            [{'pub_id': 'P1', 'total_citation': None}], [{'pub_id': 'P1', 'author1id': 'TEST_A'}])
        self.assertTrue(pd.isna(h_index.calculate(missing)['TEST_A']))
        edge = prepare_data(*edge_case_records())
        self.assertTrue(pd.isna(total_cites.calculate(edge)['TEST_EMPTY']))
        self.assertEqual(total_cites.calculate(edge)['TEST_ZERO'], 0)
        self.assertEqual(h_index.calculate(edge)['TEST_TIED'], 2)
        self.assertEqual(g_index.calculate(edge)['TEST_TIED'], 2)
        self.assertTrue(pd.isna(g_index.calculate(edge)['TEST_MISSING']))

    def test_complete_mock_run_is_local_labelled_and_has_reports_and_figures(self):
        extracts, extra = load_all()
        self.assertTrue(extracts.authors.author_id.str.startswith('TEST_').all())
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'results') as directory:
            settings = ValidationConfig(None, 5, 0, 2026, Path(directory))
            try:
                with patch('src.database.psycopg2.connect') as connection:
                    output = run_from_extracts(extracts, settings=settings,
                        output_directory=directory, extra_inputs=extra,
                        source_kind='SYNTHETIC_TEST_DATA', generate_figures=True)
                    connection.assert_not_called()
                dataset = pd.read_csv(output/'validation_dataset.csv')
                self.assertEqual(len(dataset), 12)
                self.assertEqual(dataset.author_id.nunique(), 12)
                self.assertTrue(dataset.eligible_for_validation.all())
                self.assertTrue(dataset.data_classification.eq(LABEL).all())
                self.assertTrue(dataset.c_score_raw.isna().all())
                self.assertTrue(dataset.hf_index.notna().all())
                self.assertEqual(dataset.data_provenance.unique().tolist(), ['SYNTHETIC_TEST_DATA'])
                self.assertTrue((output/'correlation_stats.csv').is_file())
                self.assertTrue((output/'pca_loadings.csv').is_file())
                self.assertTrue((output/'reports'/'statistical_results.md').is_file())
                self.assertIn(LABEL, (output/'reports'/'executive_summary.md').read_text(encoding='utf-8'))
                meta = json.loads((output/'run_metadata.json').read_text(encoding='utf-8'))
                self.assertEqual(meta['data_classification'], LABEL)
                self.assertEqual(meta['experiment_status']['rq03'], 'METHODOLOGY_PENDING')
                # Three approved scenarios recalculate; Table 9's combined row stays pending.
                self.assertEqual(meta['experiment_status']['rq07'], 'METHODOLOGY_PENDING')
                gaming = pd.read_csv(output/'gaming_resistance.csv')
                self.assertEqual(len(gaming), 48)
                self.assertTrue(gaming.loc[gaming.scenario.ne('combined'), 'status'].eq('OK').all())
                self.assertTrue(gaming.loc[gaming.scenario.eq('combined'), 'status']
                                .eq('METHODOLOGY_PENDING').all())
                self.assertEqual(gaming.author_id.nunique(), 12)
                self.assertEqual(gaming.benchmark_sha256.nunique(), 1)
                self.assertTrue((output/'output_manifest.csv').is_file())
                self.assertEqual(meta['frozen_benchmark']['original_author_count'], 12)
                self.assertEqual(meta['experiment_status']['rq09'], 'METHODOLOGY_PENDING')
                self.assertTrue(meta['figures'])
                self.assertTrue(all((PROJECT_ROOT/relative).is_file() for relative in meta['figures']))
                eligibility = pd.read_csv(output/'experiment_eligibility.csv')
                self.assertEqual(eligibility.loc[eligibility.experiment == 'rq03',
                    'experiment_specific_eligibility'].iloc[0], 'METHODOLOGY_PENDING')
                self.assertEqual(int(eligibility.loc[eligibility.experiment == 'rq11',
                    'experiment_input_matched_authors'].iloc[0]), 12)
            finally:
                if 'output' in locals():
                    figure_root = (PROJECT_ROOT/'figures').resolve()
                    figure_directory = (figure_root/output.name).resolve()
                    if figure_root in figure_directory.parents and figure_directory.is_dir():
                        shutil.rmtree(figure_directory)

    def test_mock_source_rejects_real_ids(self):
        extracts, extra = make_fixture()
        extracts.authors.loc[0, 'author_id'] = 'REAL_A1'
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'results') as directory:
            settings = ValidationConfig(None, 5, 0, 2026, Path(directory))
            with self.assertRaisesRegex(ValueError, 'TEST_ namespace'):
                run_from_extracts(extracts, settings=settings, output_directory=directory,
                                  extra_inputs=extra, source_kind='SYNTHETIC_TEST_DATA')

    def test_cli_mock_routes_without_database(self):
        import run_validation
        with patch('run_validation.run_from_extracts', return_value=PROJECT_ROOT/'results'/'fake') as execute:
            self.assertEqual(run_validation.main(['--data-source', 'mock', '--experiment', 'rq01']), 0)
            self.assertEqual(execute.call_args.kwargs['source_kind'], 'SYNTHETIC_TEST_DATA')
            self.assertEqual(execute.call_args.kwargs['experiment_names'], ['rq01'])

    def test_cli_database_route_is_only_a_mocked_call(self):
        import run_validation
        with patch('run_validation.run_database', return_value=PROJECT_ROOT/'results'/'fake') as execute:
            self.assertEqual(run_validation.main(['--data-source', 'database',
                                                  '--experiment', 'rq02']), 0)
            self.assertEqual(execute.call_args.kwargs['experiment_names'], ['rq02'])

    def test_database_route_fails_before_connection_without_readiness_evidence(self):
        from src.pipeline import run_database
        with patch('src.database.psycopg2.connect') as connection:
            with self.assertRaisesRegex(ValueError, 'DATA_REQUIRED'):
                run_database(experiment_names=['rq01'])
            connection.assert_not_called()

    def test_pilot_requires_evidence_before_connection(self):
        from src.pipeline import run_pilot
        with patch('src.database.psycopg2.connect') as connection:
            with self.assertRaisesRegex(ValueError, 'DATA_REQUIRED'):
                run_pilot(author_ids=['A1'], experiment_names=['rq02'])
            connection.assert_not_called()

    def test_pilot_id_file_and_cli_use_exact_stable_ids(self):
        import run_validation
        from src.external_inputs import load_pilot_author_ids
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'inputs') as directory:
            cohort = Path(directory)/'authors.csv'
            cohort.write_text('author_id\n0001\nA2\n', encoding='utf-8')
            self.assertEqual(load_pilot_author_ids(cohort).author_id.tolist(), ['0001', 'A2'])
            with patch('run_validation.run_pilot', return_value=PROJECT_ROOT/'results'/'fake') as execute:
                self.assertEqual(run_validation.main(['--data-source', 'pilot', '--experiment',
                    'rq02', '--pilot-author-ids', str(cohort), '--pilot-design-reference',
                    'approved small-cohort plan']), 0)
                self.assertEqual(execute.call_args.kwargs['author_ids'], ['0001', 'A2'])
                self.assertEqual(execute.call_args.kwargs['experiment_names'], ['rq02'])
            named_cohort = Path(directory)/'named_authors.csv'
            named_cohort.write_text('author_id,author_name\n0001,First Author\nA2,Second Author\n', encoding='utf-8')
            with patch('run_validation.run_pilot', return_value=PROJECT_ROOT/'results'/'fake') as execute:
                self.assertEqual(run_validation.main(['--data-source', 'pilot', '--experiment',
                    'rq02', '--pilot-author-ids', str(named_cohort), '--pilot-design-reference',
                    'approved selected cohort']), 0)
                self.assertEqual(execute.call_args.kwargs['author_ids'], ['0001', 'A2'])

    def test_selected_loader_uses_parameterized_subset_and_masks_other_coauthors(self):
        from src.repository import load_selected_author_ids
        from src.database import validate_select
        slots = {f'author{i}id': None for i in range(1, 11)}
        weights = {f'author{i}id_weight': None for i in range(1, 11)}
        slots.update(author1id='A1', author2id='OUTSIDE')
        weights.update(author1id_weight=1.0, author2id_weight=.5)
        records = dict(authors=[dict(author_id='A1', author_name='A')],
            publications=[dict(pub_id='P1', year=2020, total_citation=12, source='Journal')],
            citations=[], authorship=[dict(pub_id='P1', author_ordering_norm=1,
                                            **slots, **weights)], fields=[],
            nm=[dict(author_id='A1', nm_index=40, metrics_available=6,
                     calculated_at=None, per_total_cites=50,
                     per_citations_per_paper=50, per_citation_rate=50,
                     per_modified_hf_index=50, per_modified_hm_index=50,
                     per_modified_g_index=50)],
            component_t=[dict(author_id='A1', total_cites_score=12)],
            component_s=[dict(author_id='A1', citations_per_paper_score=12)],
            component_u=[dict(author_id='A1', citation_rate_score=12)],
            component_hf=[dict(author_id='A1', modified_hindex_final=1)],
            component_hm=[dict(author_id='A1', modified_hm_index=1)],
            component_g=[dict(author_id='A1', modified_g_index=1)])
        def batch(queries):
            self.assertEqual(set(queries), set(records))
            for sql, params in queries.values():
                validate_select(sql)
                self.assertEqual(set(params), {'A1'})
            return records
        with patch('src.repository.verify_schema') as schema:
            extracts = load_selected_author_ids(['A1'], batch=batch)
        schema.assert_called_once()
        self.assertEqual(extracts.authors.author_id.tolist(), ['A1'])
        self.assertEqual(extracts.publications.pub_id.tolist(), ['P1'])
        self.assertEqual(extracts.authorship.author1id.tolist(), ['A1'])
        self.assertTrue(pd.isna(extracts.authorship.author2id.iloc[0]))

    def test_pilot_pipeline_is_labelled_and_offline_when_adapter_is_mocked(self):
        from src.pipeline import run_pilot
        extracts, synthetic_extra = load_all()
        for frame, column in ((extracts.authors, 'author_id'),
                              (extracts.nm, 'author_id'),
                              (extracts.components, 'author_id'),
                              (extracts.publications, 'pub_id'),
                              (extracts.citations, 'pub_id'),
                              (extracts.citations, 'cites_pub_id'),
                              (extracts.authorship, 'pub_id'),
                              (extracts.fields, 'pub_id')):
            frame[column] = frame[column].map(
                lambda value: value.replace('TEST_', 'PILOT_') if isinstance(value, str) else value)
        for position in range(1, 11):
            column = f'author{position}id'
            if column in extracts.authorship:
                extracts.authorship[column] = extracts.authorship[column].map(
                    lambda value: value.replace('TEST_', 'PILOT_') if isinstance(value, str) else value)
        verification = synthetic_extra['portfolio_verification'].copy()
        verification.author_id = verification.author_id.str.replace('TEST_', 'PILOT_', regex=False)
        evidence = dict(pilot_design_reference='approved small-cohort test protocol',
                        database_ready_reference='verified test cohort',
                        citation_source_reference='approved test citation source',
                        portfolio_verification=verification,
                        pilot_author_ids=verification[['author_id']].copy())
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'results') as directory:
            settings = ValidationConfig(None, 5, 0, 2026, Path(directory))
            try:
                with patch('src.pipeline.load_config'), patch('src.pipeline.load_validation_config', return_value=settings), \
                     patch('src.repository.load_selected_author_ids', return_value=extracts) as loader, \
                     patch('src.database.psycopg2.connect') as connection:
                    output = run_pilot(author_ids=verification.author_id.tolist(),
                                       experiment_names=['rq02'], extra_inputs=evidence)
                    connection.assert_not_called()
                loader.assert_called_once()
                dataset = pd.read_csv(output/'validation_dataset.csv')
                self.assertEqual(len(dataset), 12)
                self.assertTrue(dataset.data_classification.str.startswith('PILOT DATA').all())
                self.assertEqual(dataset.data_provenance.unique().tolist(),
                                 ['SELECT_ONLY_POSTGRESQL_PILOT'])
                self.assertEqual(json.loads((output/'run_metadata.json').read_text())['database_isolation'],
                                 'REPEATABLE READ, READ ONLY')
            finally:
                if 'output' in locals():
                    figure_directory = (PROJECT_ROOT/'figures'/output.name).resolve()
                    if (PROJECT_ROOT/'figures').resolve() in figure_directory.parents and figure_directory.is_dir():
                        shutil.rmtree(figure_directory)

    def test_fairness_effects_are_persistable_and_directional(self):
        frame = pd.DataFrame(dict(gender=['Male', 'Male', 'Female', 'Female'],
                                  region=['A', 'B', 'A', 'B'],
                                  nm_index_percentile=[60, 80, 40, 50]))
        convention = FairnessConvention('pooled_sample_sd', 1,
                                        'TEST DATA ONLY: independently checked convention')
        groups, effects = compare_percentiles(frame, ['nm_index'], convention)
        self.assertEqual(len(groups), 4)
        gender = effects.loc[effects.effect == 'cohen_d_male_minus_female'].iloc[0]
        region = effects.loc[effects.effect == 'variance_of_region_mean_percentiles'].iloc[0]
        self.assertAlmostEqual(gender.value, 25 / (125 ** .5))
        self.assertAlmostEqual(region.value, 112.5)
        self.assertEqual(gender.status, 'OK')

    def test_pca_requires_an_explicit_convention(self):
        frame = pd.DataFrame({'author_id': ['TEST_A1']})
        self.assertEqual(run_rq10(frame, [])['status'].iloc[0].status, 'METHODOLOGY_PENDING')


if __name__ == '__main__':
    unittest.main()
