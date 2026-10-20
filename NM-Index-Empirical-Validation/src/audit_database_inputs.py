"""Read-only input audit; exports metadata counts and a citation-link sample.

Run only from this validation project. No metric calculations are performed.
Every query uses the Phase 2 SELECT-only access layer.
"""

import csv

from .config import PROJECT_ROOT
from .data_loader import identifier, load_schema
from .database import execute_select


# Fixed audited columns, never derived from untrusted input or supplied values.
INPUTS = {
    'author': ('author_id', 'author_name', 'modified_hm_index', 'modified_g_index', 'nm_index'),
    'publication': ('pub_id', 'year', 'total_citation', 'source'),
    'citation': ('pub_id', 'cites_pub_id'),
    'author_contribution_weight': ('pub_id', 'author_ordering_norm',
                                   *(f'author{i}id' for i in range(1, 11)),
                                   *(f'author{i}id_weight' for i in range(1, 11))),
    'field_classification': ('pub_id', 'field1_name', 'field1_weight',
                             'field2_name', 'field2_weight', 'field3_name', 'field3_weight'),
    'influential_self_citations': ('isc_id', 'cited_pub_id', 'citing_pub_id',
                                   'target_author_id', 'isc_value', 'raw_citation',
                                   'adjusted_citation', 'calculated_at'),
    'author_paper_adjusted_citations': ('cited_pub_id', 'target_author_id',
                                        'citing_paper_count', 'total_raw_citation',
                                        'total_adjusted_citation', 'calculated_at'),
    'author_total_cites': ('author_id', 'first_publication_year', 'as_of_year',
                           'career_time_years', 'total_cites_score',
                           'calculation_complete', 'calculated_at'),
    'author_citations_per_paper': ('author_id', 'publication_count',
                                   'citations_per_paper_score', 'calculation_complete'),
    'author_citation_rate': ('author_id', 'as_of_year', 'citation_rate_score',
                             'calculation_complete'),
    'author_paper_field_effective_citation': ('author_id', 'pub_id', 'field_name',
                                              'effective_citation', 'calculation_status'),
    'author_field_modified_hindex': ('author_id', 'field_name', 'raw_h_value',
                                      'modified_hindex_field', 'calculation_status'),
    'author_modified_hindex': ('author_id', 'modified_hindex_final', 'calculation_status'),
    'modified_g_index_results': ('author_id', 'modified_g_index', 'calculation_complete'),
    'author_nm_index': ('author_id', 'nm_index', 'per_total_cites',
                        'per_citations_per_paper', 'per_citation_rate',
                        'per_modified_hf_index', 'per_modified_hm_index',
                        'per_modified_g_index', 'metrics_available', 'calculated_at'),
}

GRAIN = {
    'author': 'author', 'publication': 'publication', 'citation': 'citation edge',
    'author_contribution_weight': 'publication with up to 10 author slots',
    'field_classification': 'publication with up to 3 field slots',
    'influential_self_citations': 'citation edge × target author × field',
    'author_paper_adjusted_citations': 'cited publication × target author',
    'author_paper_field_effective_citation': 'author × publication × field',
    'author_field_modified_hindex': 'author × field',
}

KEYS = {
    'author': ('author_id',), 'publication': ('pub_id',),
    'citation': ('pub_id', 'cites_pub_id'),
    'author_contribution_weight': ('pub_id',), 'field_classification': ('pub_id',),
    'influential_self_citations': ('isc_id',),
    'author_paper_adjusted_citations': ('cited_pub_id', 'target_author_id'),
    'author_paper_field_effective_citation': ('author_id', 'pub_id', 'field_name'),
    'author_field_modified_hindex': ('author_id', 'field_name'),
}


def query_for_table(table, columns):
    """Return audited SELECT with row, non-null and distinct-key counts."""
    if table not in INPUTS or not set(columns) <= set(INPUTS[table]):
        raise ValueError('Unapproved input table or column')
    select = ['COUNT(*) AS row_count']
    select += [f'COUNT({identifier(c)}) AS {identifier(c + "_nonnull")}' for c in columns]
    keys = KEYS.get(table, ('author_id',))
    key = identifier(keys[0]) if len(keys) == 1 else '(' + ', '.join(identifier(k) for k in keys) + ')'
    select += [f'COUNT(DISTINCT {key}) AS distinct_keys']
    return 'SELECT ' + ', '.join(select) + ' FROM public.' + identifier(table)


def write_csv(name, rows, columns):
    output = PROJECT_ROOT / 'results' / name
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def meaning_and_suitability(table, column):
    if table == 'author':
        if column == 'author_id':
            return 'Stable author cohort identifier', 'COHORT KEY'
        if column == 'author_name':
            return 'Display name; not a reliable join key', 'DISPLAY ONLY'
        return 'Stored NM component or stale author NM mirror', 'NM ONLY — do not use as baseline'
    if table == 'publication':
        meanings = {'pub_id': 'Stable publication identifier',
                    'year': 'Publication year; 8 current NULLs',
                    'total_citation': 'Stored per-publication citation total; provenance versus edge rows differs',
                    'source': 'Publication source text'}
        return meanings[column], ('BASELINE CANDIDATE — check link and citation provenance'
                                  if column in {'pub_id', 'year', 'total_citation'} else 'CONTEXT ONLY')
    if table == 'citation':
        return ('Cited publication ID' if column == 'pub_id' else 'Citing publication ID'), 'CITATION-EDGE CROSS-CHECK; incomplete versus stored totals'
    if table == 'author_contribution_weight':
        if column == 'pub_id':
            return 'Publication key for wide authorship record', 'BASELINE LINK CANDIDATE; only 816 linked publications'
        if column == 'author_ordering_norm':
            return 'Authorship order/contribution norm', 'NM INPUT; baseline formula dependent'
        if column.endswith('_weight'):
            return 'Stored contribution weight for matching author slot', 'NM INPUT; not uniform baseline share'
        return 'Stable author ID in one of ten position slots', 'BASELINE LINK CANDIDATE; >10 authors not represented'
    if table == 'field_classification':
        return ('Publication key' if column == 'pub_id' else
                'Assigned field name or fractional field weight'), 'NM/STRATIFICATION INPUT; only classified publications'
    if table == 'influential_self_citations':
        meanings = {'isc_id': 'Identifier for an NM influential self-citation record',
                    'cited_pub_id': 'Cited publication in an NM self-influence event',
                    'citing_pub_id': 'Citing publication in an NM self-influence event',
                    'target_author_id': 'Author receiving the adjusted citation credit',
                    'isc_value': 'NM influential self-citation discount factor',
                    'raw_citation': 'Fractional/raw NM citation credit before influence discount',
                    'adjusted_citation': 'NM citation credit after influence discount',
                    'calculated_at': 'NM ISC calculation timestamp'}
        return meanings[column], 'NM INPUT ONLY; not conventional self-citation baseline'
    if table == 'author_paper_adjusted_citations':
        meanings = {'cited_pub_id': 'Cited publication of paper-author NM aggregate',
                    'target_author_id': 'Target author of paper-author NM aggregate',
                    'citing_paper_count': 'Number of citing papers included in aggregate',
                    'total_raw_citation': 'Weighted/fractional raw NM credit',
                    'total_adjusted_citation': 'Weighted/fractional ISC-adjusted NM credit',
                    'calculated_at': 'NM aggregation timestamp'}
        return meanings[column], 'NM INPUT ONLY; weighted/fractional, not raw integer count'
    if table == 'author_nm_index':
        if column == 'author_id':
            meaning = 'Stable author key of authoritative NM result'
        elif column == 'nm_index':
            meaning = 'Authoritative stored final NM-index score'
        elif column.startswith('per_'):
            meaning = 'Stored NM component percentile for ' + column[4:]
        elif column == 'metrics_available':
            meaning = 'Count of available NM component percentiles'
        else:
            meaning = 'Final NM calculation timestamp'
        return meaning, 'AUTHORITATIVE NM READ ONLY'
    component = {
        'author_total_cites': 'T_a normalized/career-adjusted total-cites component',
        'author_citations_per_paper': 'S_a normalized citations-per-paper component',
        'author_citation_rate': 'U_a normalized citation-rate component',
        'author_paper_field_effective_citation': 'Paper/author/field effective citation input for modified NM indices',
        'author_field_modified_hindex': 'Field-specific modified NM h input',
        'author_modified_hindex': 'Stored modified NM hf component',
        'modified_g_index_results': 'Stored modified NM g component',
    }[table]
    if column == 'author_id':
        return 'Stable author key for ' + component, 'NM ONLY — not conventional baseline'
    if column in {'calculated_at'}:
        return 'Calculation timestamp for ' + component, 'NM ONLY — not conventional baseline'
    if column in {'calculation_complete', 'calculation_status'}:
        return 'Completion/status flag for ' + component, 'NM ONLY — not conventional baseline'
    return component + ': ' + column.replace('_', ' '), 'NM ONLY — not conventional baseline'


def main():
    schema = {(row['table_name'], row['column_name']): row
              for row in load_schema()}
    output = []
    for table, requested in INPUTS.items():
        present = [column for column in requested if (table, column) in schema]
        # Fail rather than silently report partial input availability.
        if len(present) != len(requested):
            raise RuntimeError('An audited table is missing expected visible columns: ' + table)
        result = execute_select(query_for_table(table, present))[0]
        grain = GRAIN.get(table, 'author (stored NM component/result)')
        duplicates = result['row_count'] - result['distinct_keys']
        for column in present:
            nullable = result['row_count'] - result[column + '_nonnull']
            meaning, suitability = meaning_and_suitability(table, column)
            output.append(dict(table=table, column=column, data_meaning=meaning,
                               row_granularity=grain, table_rows=result['row_count'],
                               nonnull_rows=result[column + '_nonnull'], null_rows=nullable,
                               key_columns=';'.join(KEYS.get(table, ('author_id',))),
                               duplicate_key_excess_rows=duplicates,
                               suitability=suitability))
    fields = ('table', 'column', 'data_meaning', 'row_granularity', 'table_rows',
              'nonnull_rows', 'null_rows', 'key_columns', 'duplicate_key_excess_rows',
              'suitability')
    write_csv('validation_database_input_map.csv', output, fields)

    # Compare deterministic citation-edge and publication samples in both
    # candidate directions. This is a representation check, not a metric.
    linked = execute_select('SELECT pub_id FROM public.citation GROUP BY pub_id ORDER BY pub_id LIMIT 20')
    papers = execute_select('SELECT pub_id FROM public.publication ORDER BY pub_id LIMIT 20')
    ids = sorted({r['pub_id'] for r in linked + papers})
    if ids:
        placeholders = ', '.join(['%s'] * len(ids))
        base = 'SELECT pub_id, total_citation FROM public.publication WHERE pub_id IN (' + placeholders + ')'
        pub = {r['pub_id']: r for r in execute_select(base, ids)}
        cited = execute_select('SELECT pub_id, COUNT(*) AS n FROM public.citation WHERE pub_id IN (' +
                               placeholders + ') GROUP BY pub_id', ids)
        citing = execute_select('SELECT cites_pub_id, COUNT(*) AS n FROM public.citation WHERE cites_pub_id IN (' +
                                placeholders + ') GROUP BY cites_pub_id', ids)
        cited_counts = {r['pub_id']: r['n'] for r in cited}
        citing_counts = {r['cites_pub_id']: r['n'] for r in citing}
        sample = [dict(pub_id=key, publication_total_citation=pub.get(key, {}).get('total_citation'),
                       rows_where_cited_pub_id= cited_counts.get(key, 0),
                       rows_where_citing_pub_id=citing_counts.get(key, 0)) for key in ids]
    else:
        sample = []
    write_csv('citation_semantics_sample.csv', sample,
              ('pub_id', 'publication_total_citation', 'rows_where_cited_pub_id',
               'rows_where_citing_pub_id'))
    print('Audited', len(INPUTS), 'tables and', len(output), 'columns; citation sample:', len(sample))
    print('No metric calculation or database write was performed.')


if __name__ == '__main__':
    main()
