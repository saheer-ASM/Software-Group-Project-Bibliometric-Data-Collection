"""Offline audit contracts; no metric computation or live database connection."""

import unittest
from unittest.mock import patch

from src.audit_database_inputs import INPUTS, query_for_table
from src.config import DatabaseConfig, load_config
from src.database import validate_select
from src.metric_registry import REGISTRY


class AuditContracts(unittest.TestCase):
    def test_registry_has_unique_target_and_eleven_distinct_baselines(self):
        names = [metric.metric_name for metric in REGISTRY]
        self.assertEqual(len(names), 12)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[0], 'nm_index')
        self.assertEqual(next(m for m in REGISTRY if m.metric_name == 'g_index').implementation_status,
                         'READY')
        self.assertEqual(next(m for m in REGISTRY if m.metric_name == 'raw_total_cites').implementation_status,
                         'READY')
        self.assertTrue(all('Full experiment design unavailable' not in m.definition_reference
                            for m in REGISTRY))

    def test_all_fixed_input_audit_queries_pass_select_guard(self):
        for table, columns in INPUTS.items():
            with self.subTest(table=table):
                query = query_for_table(table, columns)
                validate_select(query)
                self.assertTrue(query.startswith('SELECT '))
        with self.assertRaises(ValueError):
            query_for_table('author;DROP TABLE author', ('author_id',))

    def test_config_loader_is_local_and_does_not_connect(self):
        with patch('src.database.psycopg2.connect') as connect:
            with self.assertRaises(ValueError):
                load_config('../production/.env')
            connect.assert_not_called()
        config = DatabaseConfig('example.invalid', 5432, 'example', 'user', 'secret', 'require')
        self.assertNotIn('secret', repr(config))
        self.assertNotIn('example.invalid', repr(config))


if __name__ == '__main__':
    unittest.main()
