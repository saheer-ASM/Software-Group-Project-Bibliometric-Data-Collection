"""Offline safety tests: no real connections, SQL, or credentials."""

import unittest
from unittest.mock import MagicMock, patch

import psycopg2

from src.config import DatabaseConfig
from src.database import DatabaseAccessError, UnsafeQueryError, execute_select, execute_select_batch, validate_select
from src import inspect_schema


CONFIG = DatabaseConfig('example.invalid', 5432, 'dummy', 'dummy', 'secret', 'require')


class DatabaseTests(unittest.TestCase):
    def test_rejects_unsafe_queries_before_connecting(self):
        queries = [
            '', 'INSERT INTO author VALUES (1)', 'UPDATE author SET x = 1',
            'DELETE FROM author', 'DROP TABLE author', 'ALTER TABLE author ADD x int',
            'CREATE TEMP TABLE probe (id int)', 'TRUNCATE author',
            'SELECT 1; DELETE FROM author', 'SELECT 1 INTO TEMP probe',
            'SELECT * FROM author FOR UPDATE',
            'WITH removed AS (DELETE FROM author RETURNING *) SELECT * FROM removed',
            "SELECT set_config('transaction_read_only', 'off', false)",
            "SELECT nextval('sequence')", "SELECT public.current_database()",
            "SELECT pg_advisory_lock(1)", "SELECT pg_sleep(100)",
            'SELECT 1::public.custom_type', 'SHOW transaction_read_only',
            'COPY author TO STDOUT', 'COMMIT', 'EXPLAIN ANALYZE DELETE FROM author',
        ]
        with patch('src.database.psycopg2.connect') as connect:
            for query in queries:
                with self.subTest(query=query), self.assertRaises(UnsafeQueryError):
                    execute_select(query, config=CONFIG)
            connect.assert_not_called()

    def test_accepts_safe_selects_and_placeholders(self):
        for query in [
            'SELECT current_database();', 'SELECT current_user;',
            "SELECT current_setting('transaction_read_only')",
            'SELECT * FROM public.author LIMIT 1',
            'SELECT author_id FROM public.author WHERE author_id = %s',
            'SELECT author_id FROM public.author WHERE author_id = %(author_id)s',
            "SELECT 'DELETE FROM author; %s' AS example",
            'SELECT table_name FROM information_schema.columns WHERE table_name IN (%s, %s)',
            'WITH sample AS (SELECT 1 AS n) SELECT n FROM sample',
        ]:
            with self.subTest(query=query):
                validate_select(query)

    def connection(self, readonly='on'):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'read_only': readonly}
        cursor.fetchall.return_value = [{'value': 1}]
        return connection, cursor

    def test_enforces_readonly_binds_params_and_closes(self):
        connection, cursor = self.connection()
        with patch('src.database.psycopg2.connect', return_value=connection) as connect:
            query = 'SELECT author_id FROM public.author WHERE author_id = %s'
            params = ("'; DELETE FROM author; --",)
            self.assertEqual(execute_select(query, params, config=CONFIG), [{'value': 1}])
            self.assertIn('default_transaction_read_only=on', connect.call_args.kwargs['options'])
            connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
            cursor.execute.assert_any_call(query, params)
            connection.rollback.assert_called_once()
            connection.close.assert_called_once()
            connection.commit.assert_not_called()
            connection.cursor.return_value.__exit__.assert_called_once()

    def test_batch_uses_one_readonly_repeatable_read_snapshot(self):
        connection, cursor = self.connection()
        with patch('src.database.psycopg2.connect', return_value=connection):
            result = execute_select_batch({'authors':'SELECT author_id FROM public.author',
                                           'papers':'SELECT pub_id FROM public.publication'}, config=CONFIG)
        self.assertEqual(set(result), {'authors', 'papers'})
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False,
                                                        isolation_level='REPEATABLE READ')
        self.assertEqual(cursor.execute.call_count, 3)
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        connection.commit.assert_not_called()

    def test_batch_binds_parameters_without_interpolation(self):
        connection, cursor = self.connection()
        query = 'SELECT author_id FROM public.author WHERE author_id IN (%s, %s)'
        ids = ("'; DELETE FROM public.author; --", 'A2')
        with patch('src.database.psycopg2.connect', return_value=connection):
            execute_select_batch({'selected': (query, ids)}, config=CONFIG)
        cursor.execute.assert_any_call(query, ids)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()

    def test_refuses_unprotected_session(self):
        connection, cursor = self.connection('off')
        with patch('src.database.psycopg2.connect', return_value=connection):
            with self.assertRaises(DatabaseAccessError):
                execute_select('SELECT 1', config=CONFIG)
        self.assertEqual(cursor.execute.call_count, 1)
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()

    def test_query_failure_is_sanitized_and_closed(self):
        connection, cursor = self.connection()
        cursor.execute.side_effect = [None, psycopg2.OperationalError('password=secret')]
        with patch('src.database.psycopg2.connect', return_value=connection):
            with self.assertRaises(DatabaseAccessError) as caught:
                execute_select('SELECT 1', config=CONFIG)
        self.assertNotIn('secret', str(caught.exception))
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        connection.commit.assert_not_called()

    def test_connection_failure_is_sanitized(self):
        with patch('src.database.psycopg2.connect', side_effect=psycopg2.OperationalError('secret')):
            with self.assertRaises(DatabaseAccessError) as caught:
                execute_select('SELECT 1', config=CONFIG)
        self.assertNotIn('secret', str(caught.exception))

    def test_rollback_failure_still_closes(self):
        connection, cursor = self.connection()
        connection.rollback.side_effect = psycopg2.OperationalError('disconnected')
        with patch('src.database.psycopg2.connect', return_value=connection):
            execute_select('SELECT 1', config=CONFIG)
        connection.close.assert_called_once()

    def test_schema_query_is_valid_and_parameterized(self):
        def check(query, params, **kwargs):
            validate_select(query)
            self.assertEqual(params, ('public', *inspect_schema.TABLES))
            raise DatabaseAccessError()
        with patch('src.inspect_schema.load_config', return_value=CONFIG), patch('src.inspect_schema.execute_select', side_effect=check), patch('builtins.print'):
            self.assertEqual(inspect_schema.main(), 1)


if __name__ == '__main__':
    unittest.main()
