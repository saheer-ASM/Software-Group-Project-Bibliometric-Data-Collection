"""SELECT-only PostgreSQL access; no connection is opened at import time."""

import json
import re

import psycopg2
from psycopg2.extras import RealDictCursor
from pglast import parser

from .config import DatabaseConfig, load_config


class UnsafeQueryError(ValueError):
    """The statement is outside the permitted SELECT subset."""


class DatabaseAccessError(RuntimeError):
    """Sanitized database error; connection details and SQL are not exposed."""

    def __init__(self, sqlstate=None):
        self.sqlstate = sqlstate
        super().__init__("Database access failed (SQLSTATE: " + (sqlstate or "unavailable") + ").")


# SELECT can call write-capable functions. Phase 2 permits only these built-ins.
SAFE_FUNCTIONS = {"current_database", "current_setting", "count", "min", "max", "sum", "avg"}
FORBIDDEN_NODES = {"IntoClause", "LockingClause", "TypeCast", "CollateClause"}


def _parameterized_for_parse(query):
    """Translate psycopg placeholders for parsing without interpolating values."""
    pattern = re.compile(
        r"'([^']|'')*'|\"([^\"]|\"\")*\"|--[^\n]*|/\*[\s\S]*?\*/|%\([A-Za-z_][A-Za-z0-9_]*\)s|%s"
    )
    index = 0
    def replace(match):
        nonlocal index
        token = match.group()
        if token.startswith('%'):
            index += 1
            return '$' + str(index)
        return token
    if '$' in query or '\\' in query or re.search(r"\b[Ee]'", query):
        raise UnsafeQueryError("Dollar quoting, escape strings and backslashes are not supported.")
    return pattern.sub(replace, query)


def validate_select(query):
    """Parse SQL and reject writes, multiple statements, and unsafe SELECT forms."""
    if not isinstance(query, str) or not query.strip():
        raise UnsafeQueryError("Only a single SELECT statement is permitted.")
    try:
        parsed = json.loads(parser.parse_sql_json(_parameterized_for_parse(query)))
    except UnsafeQueryError:
        raise
    except Exception:
        raise UnsafeQueryError("Invalid or unsupported SELECT statement.") from None
    statements = parsed.get('stmts', [])
    if len(statements) != 1 or 'SelectStmt' not in statements[0].get('stmt', {}):
        raise UnsafeQueryError("Only a single SELECT statement is permitted.")

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if (key.endswith('Stmt') and key != 'SelectStmt') or key in FORBIDDEN_NODES or (key in {'intoClause', 'lockingClause'} and value):
                    raise UnsafeQueryError("Writes, SELECT INTO, row locks and custom expressions are not permitted.")
                if key == 'FuncCall':
                    names = [part.get('String', {}).get('sval', '') for part in value.get('funcname', [])]
                    if not names or names[-1] not in SAFE_FUNCTIONS or (len(names) > 1 and names[:-1] != ['pg_catalog']):
                        raise UnsafeQueryError("This function is not allowed in the Phase 2 SELECT interface.")
                if key == 'A_Expr':
                    names = [part.get('String', {}).get('sval', '') for part in value.get('name', [])]
                    if len(names) != 1 or names[0] not in {'=', '<>', '<', '>', '<=', '>='}:
                        raise UnsafeQueryError("Only simple comparison operators are supported.")
                if key == 'RangeVar':
                    if value.get('catalogname') or value.get('schemaname') not in (None, 'public', 'information_schema', 'pg_catalog'):
                        raise UnsafeQueryError("Only research and metadata schemas are permitted.")
                visit(value)
    visit(statements)


def execute_select(query, params=None, *, config=None):
    """Return dictionaries from a SELECT in a verified read-only transaction.

    Supply values separately as psycopg2 parameters. The raw connection is never
    returned. Every call rolls back and closes, including successful reads.
    """
    validate_select(query)
    settings = config if config is not None else load_config()
    if not isinstance(settings, DatabaseConfig):
        raise TypeError("config must be a DatabaseConfig instance.")
    connection = None
    try:
        connection = psycopg2.connect(
            host=settings.host, port=settings.port, dbname=settings.name,
            user=settings.user, password=settings.password, sslmode=settings.sslmode,
            connect_timeout=10, application_name='nm_empirical_validation_readonly',
            options='-c default_transaction_read_only=on -c statement_timeout=15000 '
                    '-c lock_timeout=3000 -c search_path=pg_catalog,public',
        )
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT pg_catalog.current_setting('transaction_read_only') AS read_only")
            if cursor.fetchone()['read_only'] != 'on':
                raise DatabaseAccessError('READ_ONLY_NOT_ENFORCED')
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except psycopg2.Error as error:
        raise DatabaseAccessError(error.pgcode) from None
    finally:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
            finally:
                connection.close()


def execute_select_batch(queries, *, config=None):
    """Read fixed extracts from one repeatable-read, read-only PostgreSQL snapshot."""
    if not isinstance(queries, dict) or not queries:
        raise ValueError('A nonempty mapping of SELECT queries is required.')
    for item in queries.values():
        query = item[0] if isinstance(item, tuple) else item
        validate_select(query)
    settings = config if config is not None else load_config()
    if not isinstance(settings, DatabaseConfig):
        raise TypeError('config must be a DatabaseConfig instance.')
    connection = None
    try:
        connection = psycopg2.connect(
            host=settings.host, port=settings.port, dbname=settings.name,
            user=settings.user, password=settings.password, sslmode=settings.sslmode,
            connect_timeout=10, application_name='nm_empirical_validation_readonly',
            options='-c default_transaction_read_only=on -c statement_timeout=15000 '
                    '-c lock_timeout=3000 -c search_path=pg_catalog,public',
        )
        connection.set_session(readonly=True, autocommit=False, isolation_level='REPEATABLE READ')
        output = {}
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT pg_catalog.current_setting('transaction_read_only') AS read_only")
            if cursor.fetchone()['read_only'] != 'on':
                raise DatabaseAccessError('READ_ONLY_NOT_ENFORCED')
            for name, item in queries.items():
                if isinstance(item, tuple):
                    query, params = item
                    cursor.execute(query, params)
                else:
                    cursor.execute(item)
                output[name] = [dict(row) for row in cursor.fetchall()]
        return output
    except psycopg2.Error as error:
        raise DatabaseAccessError(error.pgcode) from None
    finally:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
            finally:
                connection.close()
