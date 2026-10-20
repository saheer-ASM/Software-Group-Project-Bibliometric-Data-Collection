import unittest
from unittest.mock import patch

from experiments.inspect_author_coverage import describe, build_preview
from src.data_loader import inspect_sources
from src.database import validate_select
from src.metric_mapping import SOURCES, required_mapping


class InspectionTests(unittest.TestCase):
    def test_coverage_excludes_null_nonfinite_orphan_and_counts_zero(self):
        rows = [{'author_id': 'a', 'nm_index': 0}, {'author_id': 'a', 'nm_index': 10},
                {'author_id': 'b', 'nm_index': None}, {'author_id': 'c', 'nm_index': float('nan')},
                {'author_id': 'outside', 'nm_index': 50}]
        stats, ids = describe(SOURCES[0], rows, {'a', 'b', 'c'})
        self.assertEqual(ids, {'a'})
        self.assertEqual(stats['null_count'], 1)
        self.assertEqual(stats['nonfinite_count'], 1)
        self.assertEqual(stats['duplicate_author_ids'], 1)
        self.assertEqual(stats['orphan_author_ids'], 1)
        self.assertEqual(stats['median'], 10)

    def test_paper_author_repeats_are_not_duplicate_composite_keys(self):
        source = next(s for s in SOURCES if s.output == 'paper_adjusted_citations')
        stats, ids = describe(source, [dict(target_author_id='a', cited_pub_id=p, total_adjusted_citation=1) for p in ['p1', 'p2']], {'a'})
        self.assertEqual(stats['duplicate_author_ids'], 1)
        self.assertEqual(stats['duplicate_composite_keys'], 0)
        self.assertEqual(len(ids), 1)

    def test_preview_is_bounded_and_omits_absent_baselines(self):
        data = {'author': [dict(author_id=str(i), author_name='name') for i in range(30)],
                'author_nm_index': [dict(author_id=str(i), nm_index=i) for i in range(30)]}
        preview, fields = build_preview(data, {'NM-index': set(map(str, range(30)))}, set(map(str, range(30))))
        self.assertEqual(len(preview), 20)
        self.assertEqual(fields, ['author_id', 'author_name', 'nm_index'])

    def test_duplicate_values_are_not_silently_chosen(self):
        data = {'author': [dict(author_id='a', author_name='name')],
                'author_nm_index': [dict(author_id='a', nm_index=1), dict(author_id='a', nm_index=2)]}
        preview, _ = build_preview(data, {'NM-index': {'a'}}, {'a'})
        self.assertEqual(preview, [])

    def test_modified_components_do_not_become_conventional_baselines(self):
        rows = required_mapping({'NM-index': 2, 'Modified hm (NM component)': 2})
        self.assertEqual(len(rows), 12)
        self.assertEqual([r['metric'] for r in rows if r['available'] == 'YES'], ['NM-index'])

    def test_loader_uses_valid_selects_without_connection_bypass(self):
        schema = [dict(table_name='author', column_name=c, data_type='text', is_nullable='NO') for c in ['author_id', 'author_name']]
        def select(query, params=None):
            validate_select(query)
            if 'information_schema' in query:
                self.assertEqual(params, ('public',))
                return schema
            return []
        with patch('src.data_loader.execute_select', side_effect=select):
            _, _, tables, _ = inspect_sources()
        self.assertEqual(len(tables), 15)


if __name__ == '__main__':
    unittest.main()
