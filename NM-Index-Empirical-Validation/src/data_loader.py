"""Read-only source inspection. No existing calculation modules are imported."""

import re
from .database import execute_select
from .metric_mapping import SOURCES
from .test_connection import TABLES


NM_COLUMNS = ('author_id', 'nm_index', 'per_total_cites', 'per_citations_per_paper',
              'per_citation_rate', 'per_modified_hf_index', 'per_modified_hm_index',
              'per_modified_g_index', 'metrics_available', 'calculated_at')


def identifier(value):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', value):
        raise ValueError('Invalid inspection identifier')
    return '"' + value + '"'


def load_schema():
    return execute_select('''SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns WHERE table_schema = %s
        ORDER BY table_name, ordinal_position''', ('public',))


def inspect_sources():
    schema = load_schema()
    columns = {}
    for row in schema:
        columns.setdefault(row['table_name'], set()).add(row['column_name'])
    # Verify every visible column of the 15 requested tables without fetching records.
    verified = []
    for table in TABLES:
        if table not in columns:
            verified.append(dict(table=table, status='NOT VISIBLE', columns=0))
            continue
        projection = ', '.join(identifier(c) for c in sorted(columns[table]))
        execute_select('SELECT ' + projection + ' FROM public.' + identifier(table) + ' LIMIT 0')
        verified.append(dict(table=table, status='PASS', columns=len(columns[table])))

    requested = {'author': {'author_id', 'author_name'}, 'author_nm_index': set(NM_COLUMNS)}
    for source in SOURCES:
        requested.setdefault(source.table, set()).update((source.id_column, source.column))
        if source.status:
            requested[source.table].add(source.status)
        if source.grain == 'paper-author':
            requested[source.table].update(('cited_pub_id', 'citing_paper_count', 'field_row_count'))
    for table in ('author_total_cites', 'author_citations_per_paper', 'author_citation_rate', 'author_modified_hindex', 'modified_g_index_results'):
        requested.setdefault(table, set()).update(('calculated_at', 'career_factor'))
    requested['author_total_cites'].update(('as_of_year', 'first_publication_year', 'career_time_years'))
    data = {}
    for table, fields in requested.items():
        present = sorted(fields & columns.get(table, set()))
        if present:
            query = 'SELECT ' + ', '.join(identifier(c) for c in present) + ' FROM public.' + identifier(table)
            data[table] = execute_select(query)
    return schema, columns, verified, data
