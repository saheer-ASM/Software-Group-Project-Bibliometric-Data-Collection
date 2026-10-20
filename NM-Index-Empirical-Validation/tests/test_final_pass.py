"""Offline regression checks for the source-supported final pass."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from experiments.rq04_discrimination import run as award_run, AWARD_CATEGORIES
from experiments.rq05_unique_power import (_career_band, _domain_band, run as rq5_run,
    CAREER_BANDS, DOMAIN_BANDS, ISC_SCENARIOS, ORDERING_SCENARIOS)
from src.config import PROJECT_ROOT, ValidationConfig
from src.eligibility import EligibilityRules, evaluate
from src.pipeline import run_from_extracts
from src.repository import Extracts
from visualization.correlations import qq_plot
from visualization.discrimination import combined_roc


class FinalPassTests(unittest.TestCase):
    def test_design_bins_do_not_fill_source_gap(self):
        self.assertEqual(_domain_band(90), DOMAIN_BANDS[0])
        self.assertEqual(_domain_band(80), DOMAIN_BANDS[2])
        self.assertEqual(_domain_band(0), None)
        self.assertEqual(_career_band(10), CAREER_BANDS[1])
        self.assertIsNone(_career_band(12))
        self.assertEqual(_career_band(15.1), CAREER_BANDS[2])
        self.assertIsNone(_career_band(51))

    def test_rq5_tables_keep_all_explicit_rows(self):
        data = pd.DataFrame({'author_id': ['A1'], 'nm_index': [3.]})
        scenario = pd.DataFrame({'author_id': ['A1'], 'career_years': [4],
            'main_domain_percentage': [90], 'ordering_norm': [ORDERING_SCENARIOS[0]],
            'isc_scenario': [ISC_SCENARIOS[0]], 'high_relative_contribution': [True],
            'low_influential_self_citation': [True],
            'field_name': ['Computer networks and communication']})
        out = rq5_run(data, [], scenario_data=scenario)
        self.assertEqual(len(out['self_citation_analysis']), 6)
        self.assertEqual(len(out['author_ordering_analysis']), 6)
        self.assertEqual(len(out['domain_sensitivity']), 8)
        self.assertEqual(len(out['career_stage_analysis']), 9)
        self.assertEqual(out['career_stage_analysis'].iloc[0]['n'], 1)
        self.assertEqual(out['career_stage_analysis'].iloc[1]['status'], 'INPUT_DATA_REQUIRED')

    def test_award_combined_roc_only_uses_supplied_labels(self):
        dataset = pd.DataFrame({'author_id': [f'A{i}' for i in range(12)],
            'nm_index': list(range(12)), 'h_index': list(range(12)),
            'g_index': list(range(12)), 'raw_total_cites': list(range(12)),
            'c_score_raw': [float('nan')]*12})
        labels = pd.DataFrame({'author_id': dataset.author_id,
            'awardee': [False]*6+[True]*6})
        output = award_run(dataset, ['h_index', 'g_index', 'raw_total_cites'],
                           award_labels=labels, seed=4)
        self.assertEqual(len(output['award_category_counts']), 13)
        self.assertTrue(output['award_category_counts'].status.eq('INPUT_DATA_REQUIRED').all())
        events = pd.DataFrame({'author_id': ['A11'], 'award_category': [AWARD_CATEGORIES[0]],
                               'evidence_reference': ['synthetic test']})
        with_events = award_run(dataset, [], award_labels=labels, award_events=events, seed=4)
        self.assertEqual(with_events['award_category_counts'].iloc[0].top5_awardees, 1)
        self.assertEqual(output['award_analysis'].loc[
            output['award_analysis'].metric.eq('nm_index'), 'top5_awardees'].iloc[0], 1)
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as folder:
            path = combined_roc(output, output['award_analysis'], folder, 'roc.png')
            self.assertGreater(path.stat().st_size, 0)

    def test_eligibility_records_activity_and_metadata_reasons(self):
        frame = pd.DataFrame([{'author_id': 'A1', 'linked_publications': 5,
            'raw_total_cites': 15, 'nm_index_available': True,
            'nm_component_complete': True, 'full_portfolio_verified': True,
            'metric_coverage_percentage': .3,
            'active_2000_2024': False, 'publication_metadata_complete': False}])
        result = evaluate(frame, EligibilityRules(require_active_period=True,
            require_complete_publication_metadata=True))
        self.assertIn('INACTIVE_2000_2024', result.iloc[0].eligibility_reason)
        self.assertIn('INCOMPLETE_PUBLICATION_METADATA', result.iloc[0].eligibility_reason)

    def test_real_path_hf_requires_full_verified_per_paper_counts(self):
        author = 'A1'
        pubs = pd.DataFrame({'pub_id': [f'P{i}' for i in range(5)],
            'year': [2020]*5, 'total_citation': [50, 20, 30, 40, 25]})
        links = pd.DataFrame({'pub_id': pubs.pub_id, 'author1id': [author]*5})
        components = pd.DataFrame({'author_id': [author], **{
            name: [1.] for name in ('nm_raw_t','nm_raw_s','nm_raw_u',
                                    'nm_raw_hf','nm_raw_hm','nm_raw_g')}})
        nm = pd.DataFrame({'author_id': [author], 'nm_index': [4.],
            'metrics_available': [6], 'calculated_at': [None], **{
            name: [1.] for name in ('per_total_cites','per_citations_per_paper','per_citation_rate',
                                    'per_modified_hf_index','per_modified_hm_index',
                                    'per_modified_g_index')}})
        extracts = Extracts(pd.DataFrame({'author_id': [author]}), pubs,
            pd.DataFrame(columns=['pub_id','cites_pub_id']), links,
            pd.DataFrame(columns=['pub_id']), nm, components)
        verified = pd.DataFrame({'author_id': [author], 'portfolio_verified': [True],
                                 'evidence_reference': ['synthetic test']})
        counts = pd.DataFrame({'pub_id': pubs.pub_id,
            'coauthor_count': [3, 5, 4, 6, 4], 'verified_complete': [True]*5,
            'evidence_reference': ['synthetic test']*5})
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT/'results') as folder:
            settings = ValidationConfig(None, 5, 0, 9, Path(folder))
            kwargs = dict(experiment_names=['rq01'], settings=settings,
                output_directory=folder, generate_figures=False,
                source_kind='SUPPLIED_DATAFRAMES')
            without = run_from_extracts(extracts, extra_inputs={
                'portfolio_verification': verified}, **kwargs)
            self.assertTrue(pd.isna(pd.read_csv(without/'validation_dataset.csv').iloc[0].hf_index))
            with_counts = run_from_extracts(extracts, extra_inputs={
                'portfolio_verification': verified, 'coauthor_counts': counts}, **kwargs)
            self.assertEqual(pd.read_csv(with_counts/'validation_dataset.csv').iloc[0].hf_index, 4)
            counts.loc[0, 'verified_complete'] = False
            incomplete = run_from_extracts(extracts, extra_inputs={
                'portfolio_verification': verified, 'coauthor_counts': counts}, **kwargs)
            self.assertTrue(pd.isna(pd.read_csv(incomplete/'validation_dataset.csv').iloc[0].hf_index))

    def test_qq_plot_has_local_output(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as folder:
            path = qq_plot(pd.DataFrame({'nm_index': [1, 2, 3, 4]}),
                           'nm_index', folder, 'qq.png')
            self.assertGreater(path.stat().st_size, 0)


if __name__ == '__main__':
    unittest.main()
