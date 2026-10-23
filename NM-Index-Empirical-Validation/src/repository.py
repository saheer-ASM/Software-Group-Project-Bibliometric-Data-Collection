"""Fixed SELECT-only extracts for the populated string-ID research schema."""

from dataclasses import dataclass

import pandas as pd

from .database import execute_select, execute_select_batch


QUERIES = {
    'authors': 'SELECT author_id, author_name FROM public.author ORDER BY author_id',
    'publications': 'SELECT pub_id, year, total_citation, source FROM public.publication ORDER BY pub_id',
    'citations': 'SELECT pub_id, cites_pub_id FROM public.citation ORDER BY pub_id, cites_pub_id',
    'authorship': ('SELECT pub_id, author_ordering_norm, ' +
                   ', '.join(f'author{i}id, author{i}id_weight' for i in range(1, 11)) +
                   ' FROM public.author_contribution_weight ORDER BY pub_id'),
    'fields': ('SELECT pub_id, field1_name, field1_weight, field2_name, field2_weight, '
               'field3_name, field3_weight FROM public.field_classification ORDER BY pub_id'),
    'nm': ('SELECT author_id, nm_index, metrics_available, calculated_at, '
           'per_total_cites, per_citations_per_paper, per_citation_rate, '
           'per_modified_hf_index, per_modified_hm_index, per_modified_g_index '
           'FROM public.author_nm_index ORDER BY author_id'),
    'component_t': 'SELECT author_id, total_cites_score FROM public.author_total_cites ORDER BY author_id',
    'component_s': 'SELECT author_id, citations_per_paper_score FROM public.author_citations_per_paper ORDER BY author_id',
    'component_u': 'SELECT author_id, citation_rate_score FROM public.author_citation_rate ORDER BY author_id',
    'component_hf': 'SELECT author_id, modified_hindex_final FROM public.author_modified_hindex ORDER BY author_id',
    'component_hm': 'SELECT author_id, modified_hm_index FROM public.author ORDER BY author_id',
    'component_g': 'SELECT author_id, modified_g_index FROM public.modified_g_index_results ORDER BY author_id',
}

REQUIRED_COLUMNS = {
    'author': ('author_id', 'author_name', 'modified_hm_index'),
    'publication': ('pub_id', 'year', 'total_citation', 'source'),
    'citation': ('pub_id', 'cites_pub_id'),
    'author_contribution_weight': ('pub_id', 'author_ordering_norm',
                                   *(f'author{i}id' for i in range(1, 11)),
                                   *(f'author{i}id_weight' for i in range(1, 11))),
    'field_classification': ('pub_id', 'field1_name', 'field1_weight', 'field2_name',
                             'field2_weight', 'field3_name', 'field3_weight'),
    'author_nm_index': ('author_id', 'nm_index', 'metrics_available', 'calculated_at',
                        'per_total_cites', 'per_citations_per_paper', 'per_citation_rate',
                        'per_modified_hf_index', 'per_modified_hm_index',
                        'per_modified_g_index'),
    'author_total_cites': ('author_id', 'total_cites_score'),
    'author_citations_per_paper': ('author_id', 'citations_per_paper_score'),
    'author_citation_rate': ('author_id', 'citation_rate_score'),
    'author_modified_hindex': ('author_id', 'modified_hindex_final'),
    'modified_g_index_results': ('author_id', 'modified_g_index'),
}

# Publication source text is descriptive only; a database without it reads NULL.
OPTIONAL_COLUMNS = {('publication', 'source')}

# Production's own completeness flag for each stored NM component that has one
# (Hf' has only a status label and Hm' none). Reported, never used for eligibility;
# a database without the column reads NULL.
COMPLETENESS_FLAGS = {
    'component_t': ('author_total_cites', 'calculation_complete', 'nm_flag_t'),
    'component_s': ('author_citations_per_paper', 'calculation_complete', 'nm_flag_s'),
    'component_u': ('author_citation_rate', 'calculation_complete', 'nm_flag_u'),
    'component_g': ('modified_g_index_results', 'calculation_complete', 'nm_flag_g'),
}

REQUIRED_BY = {
    'author': 'all_metrics;RQ10', 'publication': 'raw_total_cites;h_index;g_index',
    'citation': 'citation_quality_audit', 'author_contribution_weight': 'all_raw_baselines;eligibility',
    'field_classification': 'field_stratification', 'author_nm_index': 'nm_index;RQ01-RQ11',
    'author_total_cites': 'RQ10', 'author_citations_per_paper': 'RQ10',
    'author_citation_rate': 'RQ10', 'author_modified_hindex': 'RQ10',
    'modified_g_index_results': 'RQ10',
}


@dataclass
class Extracts:
    authors: pd.DataFrame
    publications: pd.DataFrame
    citations: pd.DataFrame
    authorship: pd.DataFrame
    fields: pd.DataFrame
    nm: pd.DataFrame
    components: pd.DataFrame | None = None


def verify_schema(schema_rows=None):
    """Fail with exact missing source fields before extracting any records.

    Returns the visible (table, column) pairs so optional columns can be projected.
    """
    if schema_rows is None:
        from .data_loader import load_schema
        schema_rows = load_schema()
    visible = {(r['table_name'], r['column_name']) for r in schema_rows}
    missing = [(table, col) for table, cols in REQUIRED_COLUMNS.items()
               for col in cols if (table, col) not in visible and (table, col) not in OPTIONAL_COLUMNS]
    if missing:
        raise ValueError('Missing database input(s): ' + '; '.join(
            f'table={table} column={column} required_by={REQUIRED_BY[table]}'
            for table, column in missing))
    return visible


def _queries(visible):
    queries = dict(QUERIES)
    if ('publication', 'source') not in visible:
        queries['publications'] = queries['publications'].replace(', source FROM', ', NULL AS source FROM')
    for name, (table, column, alias) in COMPLETENESS_FLAGS.items():
        source = column if (table, column) in visible else 'NULL'
        queries[name] = queries[name].replace(' FROM public.', f', {source} AS {alias} FROM public.', 1)
    return queries


def load_all(*, query=execute_select):
    queries = _queries(verify_schema())
    records = (execute_select_batch(queries) if query is execute_select else
               {name: query(sql) for name, sql in queries.items()})
    return _assemble(records)


def load_selected_author_ids(author_ids, *, batch=execute_select_batch):
    """Extract only the requested cohort and its linked papers in one read-only snapshot.

    Non-cohort author slots are masked in the returned in-memory authorship frame;
    their identities are never counted as orphaned cohort authors. This subset is
    suitable for the three current whole-paper baselines, not an approved
    coauthor-sensitive baseline calculation.
    """
    ids = tuple(author_ids)
    if not ids or len(ids) > 6000 or len(set(ids)) != len(ids) or any(
            not isinstance(value, str) or not value.strip() or value.startswith('TEST_')
            for value in ids):
        raise ValueError('Pilot requires 1–6000 unique, nonempty, real stable author IDs')
    base = _queries(verify_schema())
    placeholders = ', '.join(['%s'] * len(ids))
    selected = f'author_id IN ({placeholders})'
    linked = ' OR '.join(f'author{i}id IN ({placeholders})' for i in range(1, 11))
    paper_select = f'SELECT pub_id FROM public.author_contribution_weight WHERE {linked}'
    paper_where = f'pub_id IN ({paper_select})'
    author_params = ids
    paper_params = ids * 10
    queries = {
        'authors': (base['authors'].replace(' ORDER BY author_id', f' WHERE {selected} ORDER BY author_id'), author_params),
        'publications': (base['publications'].replace(' ORDER BY pub_id', f' WHERE {paper_where} ORDER BY pub_id'), paper_params),
        'citations': (base['citations'].replace(' ORDER BY pub_id, cites_pub_id', f' WHERE {paper_where} ORDER BY pub_id, cites_pub_id'), paper_params),
        'authorship': (base['authorship'].replace(' ORDER BY pub_id', f' WHERE {paper_where} ORDER BY pub_id'), paper_params),
        'fields': (base['fields'].replace(' ORDER BY pub_id', f' WHERE {paper_where} ORDER BY pub_id'), paper_params),
        'nm': (base['nm'].replace(' ORDER BY author_id', f' WHERE {selected} ORDER BY author_id'), author_params),
    }
    for name in ('component_t', 'component_s', 'component_u', 'component_hf',
                 'component_hm', 'component_g'):
        queries[name] = (base[name].replace(' ORDER BY author_id',
                                               f' WHERE {selected} ORDER BY author_id'), author_params)
    records = batch(queries)
    extracts = _assemble(records)
    if set(extracts.authors.author_id.astype(str)) != set(ids):
        raise ValueError('DATA_REQUIRED: at least one selected author ID is absent from the database')
    for position in range(1, 11):
        column = f'author{position}id'
        other = ~extracts.authorship[column].isin(ids)
        extracts.authorship.loc[other, column] = None
        extracts.authorship.loc[other, f'author{position}id_weight'] = None
    return extracts


def _assemble(records):
    frames = {name: pd.DataFrame(rows) for name, rows in records.items()}
    for name, frame in frames.items():
        if frame.empty:
            # Retain a stable schema for empty future or mocked extracts.
            columns = {'authors': ('author_id', 'author_name'),
                'publications': REQUIRED_COLUMNS['publication'],
                'citations': REQUIRED_COLUMNS['citation'],
                'authorship': REQUIRED_COLUMNS['author_contribution_weight'],
                'fields': REQUIRED_COLUMNS['field_classification'],
                'nm': REQUIRED_COLUMNS['author_nm_index'],
                'component_t': ('author_id', 'total_cites_score'),
                'component_s': ('author_id', 'citations_per_paper_score'),
                'component_u': ('author_id', 'citation_rate_score'),
                'component_hf': ('author_id', 'modified_hindex_final'),
                'component_hm': ('author_id', 'modified_hm_index'),
                'component_g': ('author_id', 'modified_g_index')}[name]
            frames[name] = pd.DataFrame(columns=columns)
    component_columns = {'component_t': ('total_cites_score', 'nm_raw_t'),
        'component_s': ('citations_per_paper_score', 'nm_raw_s'),
        'component_u': ('citation_rate_score', 'nm_raw_u'),
        'component_hf': ('modified_hindex_final', 'nm_raw_hf'),
        'component_hm': ('modified_hm_index', 'nm_raw_hm'),
        'component_g': ('modified_g_index', 'nm_raw_g')}
    components = frames['authors'][['author_id']].copy()
    for name, (original, renamed) in component_columns.items():
        source = frames.pop(name)
        if source.author_id.duplicated().any():
            raise ValueError(f'Duplicate stored NM component author_id in {name}')
        flags = [column for column in source if column.startswith('nm_flag_')]
        components = components.merge(source[['author_id', original, *flags]].rename(columns={original: renamed}),
                                      on='author_id', how='left', validate='one_to_one')
    frames['components'] = components
    return Extracts(**frames)
