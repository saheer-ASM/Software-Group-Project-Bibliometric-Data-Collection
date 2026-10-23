"""Offline regression checks for code fixes confirmed by the final 995-author review."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from experiments.rq02_paired_comparison import run as run_rq02
from src.config import PROJECT_ROOT, SQLiteConfig, ValidationConfig
from src.data_quality import check
from src.database import validate_select
from src.mock_repository import load_all
from src.pipeline import _database_engine, run_from_extracts
from src.repository import COMPLETENESS_FLAGS, REQUIRED_COLUMNS, _assemble, _queries


def _visible(*extra):
    return {(table, column) for table, columns in REQUIRED_COLUMNS.items()
            for column in columns} | set(extra)


class Final995ReviewTests(unittest.TestCase):
    def _run(self, extracts, extra, **kwargs):
        directory = tempfile.mkdtemp(dir=PROJECT_ROOT/'results')
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        output = run_from_extracts(extracts, settings=ValidationConfig(None, 5, 0, 2026, Path(directory)),
            output_directory=directory, extra_inputs=extra, source_kind='SYNTHETIC_TEST_DATA',
            generate_figures=False, experiment_names=('rq02',), **kwargs)
        self.addCleanup(shutil.rmtree, PROJECT_ROOT/'figures'/output.name, ignore_errors=True)
        return output

    def test_missing_year_excludes_authors_instead_of_aborting_run(self):
        extracts, extra = load_all()
        paper = extracts.authorship.iloc[0]
        affected = {paper.author1id, paper.author2id}
        extracts.publications.loc[extracts.publications.pub_id.eq(paper.pub_id), 'year'] = None
        output = self._run(extracts, extra)
        dataset = pd.read_csv(output/'validation_dataset.csv').set_index('author_id')
        for author in affected:
            self.assertIn('INCOMPLETE_PUBLICATION_METADATA', dataset.at[author, 'eligibility_reason'])
            self.assertFalse(dataset.at[author, 'eligible_for_validation'])
        self.assertTrue(dataset.drop(index=list(affected)).eligible_for_validation.all())
        quality = pd.read_csv(output/'data_quality_report.csv').set_index('check')
        self.assertEqual(quality.at['invalid_publication_years', 'count'], 1)
        meta = json.loads((output/'run_metadata.json').read_text(encoding='utf-8'))
        self.assertTrue(meta['publication_year_policy'].startswith('EXCLUDE_AUTHORS'))
        self.assertIsNone(meta['database_engine'])

    def test_paper_drop_flag_is_recorded_as_non_design_policy(self):
        extracts, extra = load_all()
        dropped = pd.DataFrame({'pub_id': ['TEST_X'], 'year': [None], 'total_citation': [0],
                                'cohort_author_ids': ['TEST_A'], 'reason': ['missing']})
        output = self._run(extracts, extra, excluded_publications=dropped)
        meta = json.loads((output/'run_metadata.json').read_text(encoding='utf-8'))
        self.assertTrue(meta['publication_year_policy'].startswith('DROP_PAPERS'))
        self.assertEqual(meta['excluded_publications'], 1)

    def test_completeness_flags_are_optional_safe_selects(self):
        absent = _queries(_visible() - {('publication', 'source')})
        present = _queries(_visible(*((table, column) for table, column, _ in COMPLETENESS_FLAGS.values())))
        for name, (_, column, alias) in COMPLETENESS_FLAGS.items():
            self.assertIn(f'NULL AS {alias} FROM', absent[name])
            self.assertIn(f'{column} AS {alias} FROM', present[name])
            validate_select(absent[name])
            validate_select(present[name])
        self.assertIn('NULL AS source', absent['publications'])

    def test_stored_flags_reach_quality_report_and_dataset_without_gating(self):
        extracts, extra = load_all()
        ids = extracts.components.author_id.tolist()
        extracts.components['nm_flag_t'] = [0] + [1]*(len(ids)-1)
        extracts.components['nm_flag_s'] = [True]*len(ids)
        quality = check(extracts)[0].set_index('check')
        self.assertEqual(quality.at['stored_nm_components_flagged_incomplete', 'count'], 1)
        self.assertEqual(quality.at['stored_nm_components_flagged_incomplete', 'status'], 'WARNING')
        output = self._run(extracts, extra)
        dataset = pd.read_csv(output/'validation_dataset.csv').set_index('author_id')
        self.assertFalse(dataset.at[ids[0], 'nm_stored_calculation_complete'])
        self.assertTrue(dataset.drop(index=ids[0]).nm_stored_calculation_complete.all())
        self.assertTrue(dataset.eligible_for_validation.all())

    def test_assemble_keeps_flags_and_absent_flags_stay_unknown(self):
        records = dict(authors=[dict(author_id='A1', author_name='x')], publications=[],
            citations=[], authorship=[], fields=[],
            nm=[dict(author_id='A1', nm_index=1., metrics_available=6, calculated_at=None,
                     per_total_cites=1., per_citations_per_paper=1., per_citation_rate=1.,
                     per_modified_hf_index=1., per_modified_hm_index=1., per_modified_g_index=1.)],
            component_t=[dict(author_id='A1', total_cites_score=1., nm_flag_t=0)],
            component_s=[dict(author_id='A1', citations_per_paper_score=1.)],
            component_u=[dict(author_id='A1', citation_rate_score=1.)],
            component_hf=[dict(author_id='A1', modified_hindex_final=1.)],
            component_hm=[dict(author_id='A1', modified_hm_index=1.)],
            component_g=[dict(author_id='A1', modified_g_index=1.)])
        extracts = _assemble(records)
        self.assertEqual(extracts.components.nm_flag_t.tolist(), [0])
        self.assertEqual(check(extracts)[0].set_index('check').at[
            'stored_nm_components_flagged_incomplete', 'count'], 1)
        unflagged, _ = load_all()
        self.assertEqual(check(unflagged)[0].set_index('check').at[
            'stored_nm_components_flagged_incomplete', 'count'], 0)

    def test_rq02_native_unit_differences_are_not_reported_as_complete(self):
        data = pd.DataFrame({'author_id': ['A', 'B', 'C'], 'nm_index': [50., 60., 70.],
                             'h_index': [5., 9., 8.]})
        output = run_rq02(data, ['h_index'])
        self.assertEqual(output['status'].iloc[0]['status'], 'METHODOLOGY_PENDING')
        stats = output['paired_difference_stats'].iloc[0]
        self.assertEqual(stats['score_scale'], 'native_units')
        self.assertEqual(stats['status'], 'OK')
        self.assertAlmostEqual(stats['mean_difference'], 52.666666666666664)

    def test_database_engine_is_recorded_separately_from_adapter_label(self):
        self.assertIsNone(_database_engine('SYNTHETIC_TEST_DATA'))
        with tempfile.NamedTemporaryFile(dir=PROJECT_ROOT/'results', suffix='.db', delete=False) as handle:
            path = Path(handle.name)
        self.addCleanup(path.unlink)
        with patch('src.pipeline.load_config', return_value=SQLiteConfig(path=path)):
            self.assertEqual(_database_engine('SELECT_ONLY_POSTGRESQL_COHORT'), 'sqlite')


if __name__ == '__main__':
    unittest.main()
