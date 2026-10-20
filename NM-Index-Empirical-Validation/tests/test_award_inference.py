"""Source-supported RQ4 output with an explicit TEST-only inference choice."""

import unittest

import numpy as np
import pandas as pd

from experiments.rq04_discrimination import AWARD_CATEGORIES, run


class AwardInferenceTests(unittest.TestCase):
    def setUp(self):
        ids = [f'TEST_A{i}' for i in range(12)]
        self.dataset = pd.DataFrame({'author_id': ids,
            'nm_index': [float(i*7+2) for i in range(12)],
            'raw_total_cites': [float(i*9+1) for i in range(12)],
            'h_index': [float(i+1) for i in range(12)],
            'g_index': [float(i+2) for i in range(12)]})
        self.labels = pd.DataFrame({'author_id': ids,
                                    'awardee': [int(i >= 8) for i in range(12)]})
        self.reference = self.dataset.copy()
        self.events = pd.DataFrame([dict(author_id='TEST_A11',
            award_category='Turing Award', evidence_reference='TEST DATA ONLY')])

    def test_percentile_means_effect_p_auc_and_category_structure(self):
        result = run(self.dataset, ['raw_total_cites', 'h_index', 'g_index'],
            award_labels=self.labels, award_events=self.events,
            reference_scores=self.reference, data_source_kind='SYNTHETIC_TEST_DATA',
            award_inference_convention='welch_two_sided_pooled_d',
            award_inference_reference='TEST DATA ONLY: approved for fixture')
        self.assertEqual(result['status'].iloc[0].status, 'OK')
        row = result['award_analysis'].set_index('metric').loc['nm_index']
        self.assertEqual(row['top5_awardees'], 1)
        self.assertGreater(row['awardee_mean_percentile'], row['non_awardee_mean_percentile'])
        self.assertTrue(np.isfinite(row['cohen_d']))
        self.assertTrue(0 <= row['p_value'] <= 1)
        self.assertTrue(0 <= row['p_value_bonferroni'] <= 1)
        self.assertTrue(0 <= row['auc'] <= 1)
        self.assertEqual(len(result['award_category_counts']), 13)
        self.assertEqual(set(result['award_category_counts'].award_category), set(AWARD_CATEGORIES))
        self.assertIn('roc_nm_index', result)

    def test_missing_author_label_never_silently_drops_author(self):
        result = run(self.dataset, [], award_labels=self.labels.iloc[:-1])
        self.assertEqual(result['status'].iloc[0].status, 'DATA_REQUIRED')

    def test_missing_award_events_remain_explicitly_unavailable(self):
        result = run(self.dataset, ['h_index'], award_labels=self.labels,
            reference_scores=self.reference, data_source_kind='SYNTHETIC_TEST_DATA',
            award_inference_convention='welch_two_sided_pooled_d',
            award_inference_reference='TEST DATA ONLY: approved for fixture')
        self.assertEqual(result['status'].iloc[0].status, 'INPUT_DATA_REQUIRED')
        self.assertEqual(set(result['award_category_counts'].status), {'INPUT_DATA_REQUIRED'})


if __name__ == '__main__':
    unittest.main()
