"""Export visible metadata only; no author/publication records are exported."""

import csv

from .config import PROJECT_ROOT, load_config
from .database import DatabaseAccessError, execute_select
from .test_connection import TABLES


def main():
    query = '''SELECT table_name AS "Table", column_name AS "Column",
                      data_type AS "Data Type", is_nullable AS "Nullable"
               FROM information_schema.columns
               WHERE table_schema IN (%s) AND table_name IN (TABLE_PLACEHOLDERS)
               ORDER BY table_name, ordinal_position'''
    query = query.replace('TABLE_PLACEHOLDERS', ', '.join(['%s'] * len(TABLES)))
    try:
        rows = execute_select(query, ('public', *TABLES), config=load_config())
    except (ValueError, FileNotFoundError, DatabaseAccessError):
        print('Schema inspection: FAIL (check local configuration, access and connectivity)')
        print('No schema report written.')
        return 1
    output = PROJECT_ROOT / 'results' / 'database_schema_report.csv'
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['Table', 'Column', 'Data Type', 'Nullable'])
        writer.writeheader()
        writer.writerows(rows)
    visible = {row['Table'] for row in rows}
    print(f'Schema report: {len(rows)} columns across {len(visible)} tables')
    for table in TABLES:
        print(f'{table}: {sum(row["Table"] == table for row in rows)} visible columns')
    print('Absent metadata may mean a missing table or insufficient privileges.')
    print('Saved: ' + str(output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
