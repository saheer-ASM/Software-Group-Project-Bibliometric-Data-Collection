"""SELECT-only PostgreSQL or read-only SQLite access; no connection is opened at import time."""

import json
import re
import sqlite3

import psycopg2
from psycopg2.extras import RealDictCursor
from pglast import parser

from .config import DatabaseConfig, SQLiteConfig, load_config


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


_SQLITE_TOKEN = re.compile(
    r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*[\s\S]*?\*/|=\s*ANY\s*\(\s*%s\s*\)|%s|\bpublic\."
)


def _sqlite_statement(query, params):
    """Rewrite a validated PostgreSQL SELECT for SQLite without interpolating values.

    The public schema is SQLite's main database, %s becomes ?, and = ANY(%s)
    becomes a JSON-array membership test so a long ID list binds one value.
    """
    values = list(params or ())
    bound = []

    def replace(match):
        token = match.group()
        if token[0] in '\'"-/':
            return token
        if token == 'public.':
            return ''
        if len(bound) >= len(values):
            raise UnsafeQueryError("Fewer parameters than placeholders.")
        value = values[len(bound)]
        if token == '%s':
            bound.append(value)
            return '?'
        bound.append(json.dumps(list(value)))
        return 'IN (SELECT value FROM json_each(?))'
    return _SQLITE_TOKEN.sub(replace, query), bound


def _attach_information_schema(connection):
    """Expose SQLite table columns in the information_schema.columns shape."""
    connection.execute("ATTACH DATABASE ':memory:' AS information_schema")
    connection.execute('CREATE TABLE information_schema.columns (table_schema TEXT, table_name TEXT, '
                       'column_name TEXT, data_type TEXT, is_nullable TEXT, ordinal_position INTEGER)')
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM main.sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'")]
    for table in tables:
        columns = connection.execute(
            'SELECT cid, name, type, "notnull" FROM pragma_table_info(?, \'main\')', (table,)).fetchall()
        connection.executemany('INSERT INTO information_schema.columns VALUES (?, ?, ?, ?, ?, ?)', [
            ('public', table, name, (kind or '').lower(), 'NO' if notnull else 'YES', cid + 1)
            for cid, name, kind, notnull in columns])


def _sqlite_batch(queries, settings):
    """Read SQLite extracts in one transaction on a mode=ro, query_only connection."""
    connection = None
    try:
        connection = sqlite3.connect(settings.path.as_uri() + '?mode=ro', uri=True,
                                     timeout=10, isolation_level=None)
        _attach_information_schema(connection)
        connection.execute('PRAGMA query_only = ON')
        if connection.execute('PRAGMA query_only').fetchone()[0] != 1:
            raise DatabaseAccessError('READ_ONLY_NOT_ENFORCED')
        connection.row_factory = sqlite3.Row
        connection.execute('BEGIN')
        output = {}
        for name, item in queries.items():
            query, params = item if isinstance(item, tuple) else (item, None)
            rows = connection.execute(*_sqlite_statement(query, params)).fetchall()
            output[name] = [dict(row) for row in rows]
        return output
    except sqlite3.Error as error:
        raise DatabaseAccessError(getattr(error, 'sqlite_errorname', None)) from None
    finally:
        if connection is not None:
            connection.close()


def execute_select(query, params=None, *, config=None):
    """Return dictionaries from a SELECT in a verified read-only transaction.

    Supply values separately as psycopg2 parameters. The raw connection is never
    returned. Every call rolls back and closes, including successful reads.
    """
    validate_select(query)
    settings = config if config is not None else load_config()
    if isinstance(settings, SQLiteConfig):
        return _sqlite_batch({'rows': (query, params)}, settings)['rows']
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
    if isinstance(settings, SQLiteConfig):
        return _sqlite_batch(queries, settings)
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
