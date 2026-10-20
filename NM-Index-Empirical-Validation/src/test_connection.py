"""Run with python -m src.test_connection. Only SELECT reaches PostgreSQL."""

from .config import load_config
from .database import DatabaseAccessError, UnsafeQueryError, execute_select


TABLES = (
    'author', 'publication', 'citation', 'author_contribution_weight',
    'field_classification', 'influential_self_citations',
    'author_paper_adjusted_citations', 'author_total_cites',
    'author_citations_per_paper', 'author_citation_rate',
    'author_paper_field_effective_citation', 'author_field_modified_hindex',
    'author_modified_hindex', 'modified_g_index_results', 'author_nm_index',
)


def main():
    # Rejected locally, never sent to PostgreSQL. No temporary objects are made.
    try:
        execute_select('CREATE TEMP TABLE nm_validation_safety_probe (id integer)')
    except UnsafeQueryError:
        print('SQL write guard: PASS (rejected before connection)')
    else:
        print('SQL write guard: FAIL')
        return 1
    try:
        config = load_config()
        database = execute_select('SELECT current_database() AS name;', config=config)[0]['name']
        user = execute_select('SELECT current_user AS name;', config=config)[0]['name']
        readonly = execute_select("SELECT current_setting('transaction_read_only') AS value;", config=config)[0]['value']
    except (ValueError, FileNotFoundError, DatabaseAccessError):
        print('Database connection: FAIL (check local configuration, access and connectivity)')
        print('Current database: NOT VERIFIED\nCurrent user: NOT VERIFIED')
        print('Transaction read-only: NOT VERIFIED\nRead-only protection: NOT VERIFIED')
        for table in TABLES:
            print(table + ': NOT TESTED')
        return 1
    print('Database connection: PASS')
    print('Current database: ' + database)
    print('Current user: ' + user)
    print('Transaction read-only: ' + readonly.upper())
    print('Read-only protection: ' + ('PASS' if readonly == 'on' else 'FAIL'))
    print('(Local write rejection plus server setting; no write statement sent.)')
    failed = readonly != 'on'
    for table in TABLES:
        try:
            # Identifiers come only from the fixed tuple above, never user input.
            execute_select('SELECT 1 AS accessible FROM public.' + table + ' LIMIT 1;', config=config)
            print(table + ': PASS')
        except DatabaseAccessError as error:
            print(table + (': NOT FOUND' if error.sqlstate == '42P01' else ': FAIL'))
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
