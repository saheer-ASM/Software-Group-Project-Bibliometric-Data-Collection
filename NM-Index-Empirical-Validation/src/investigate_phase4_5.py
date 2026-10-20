"""Read-only Phase 4.5 data-quality inspection. No metric calculation."""

import csv
import json
from collections import Counter, defaultdict

from .config import PROJECT_ROOT
from .database import execute_select


RELATIONS = {
    'author_paper_adjusted_citations': ('target_author_id', 'cited_pub_id'),
    'equation_9_adjusted_citations': ('target_author_id', 'cited_pub_id'),
    'author_paper_field_effective_citation': ('author_id', 'pub_id'),
    'total_cites_equation_11_details': ('author_id', 'pub_id'),
    'total_cites_equation_11_details_with_score': ('author_id', 'pub_id'),
    'citations_per_paper_details': ('author_id', 'pub_id'),
    'citation_rate_details': ('author_id', 'pub_id'),
    'modified_g_index_paper_details': ('author_id', 'pub_id'),
    'influential_self_citations': ('target_author_id', 'cited_pub_id'),
    'eq15_effective_citations': ('author_id', 'pub_id'),
    'author_publications': ('author_id', 'publication_id'),
}

AUTHOR_TABLES = {
    'author': 'author_id', 'authors': 'author_id',
    'author_nm_index': 'author_id', 'author_total_cites': 'author_id',
    'author_citations_per_paper': 'author_id', 'author_citation_rate': 'author_id',
    'author_modified_hindex': 'author_id', 'author_field_modified_hindex': 'author_id',
    'modified_g_index_results': 'author_id', 'modified_g_index_field_results': 'author_id',
    'author_metrics': 'author_id', 'equation_11_total_cites': 'author_id',
    'equation_13_citations_per_paper': 'author_id',
    'equation_14_citation_rate': 'author_id',
}


def id_issues(values, authority):
    ids = [str(v) for v in values if v is not None]
    case = defaultdict(set)
    for value in ids:
        case[value.casefold()].add(value)
    return {
        'null_ids': len(values) - len(ids),
        'unique_ids': len(set(ids)),
        'duplicate_id_excess': len(ids) - len(set(ids)),
        'orphan_unique_ids': len(set(ids) - authority),
        'whitespace_rows': sum(value != value.strip() for value in ids),
        'case_variant_groups': sum(len(group) > 1 for group in case.values()),
        'format_prefixes': dict(Counter(value[:1] for value in ids)),
    }


def main():
    publications = execute_select('SELECT pub_id, year, total_citation, source FROM public.publication')
    pub_ids = {row['pub_id'] for row in publications}
    authors = execute_select('SELECT author_id FROM public.author')
    author_ids = {row['author_id'] for row in authors}
    uuid_authors = execute_select('SELECT author_id FROM public.authors')
    uuid_author_ids = {str(row['author_id']) for row in uuid_authors}
    uuid_pubs = execute_select('SELECT publication_id FROM public.publications')
    uuid_pub_ids = {str(row['publication_id']) for row in uuid_pubs}

    wide = execute_select('SELECT pub_id, ' + ', '.join(f'author{i}id' for i in range(1, 11)) +
                          ' FROM public.author_contribution_weight')
    wide_pairs_all = [(str(row[f'author{i}id']), row['pub_id']) for row in wide
                      for i in range(1, 11) if row[f'author{i}id'] is not None]
    relationships = {'author_contribution_weight': set(wide_pairs_all)}
    stats = {'author_contribution_weight': {'rows': len(wide), 'relationship_rows': len(wide_pairs_all),
             'duplicate_pair_excess': len(wide_pairs_all) - len(relationships['author_contribution_weight']),
             'blank_author_slots': sum(row[f'author{i}id'] == '' for row in wide for i in range(1, 11))}}

    for table, (author_col, pub_col) in RELATIONS.items():
        records = execute_select(f'SELECT {author_col}, {pub_col} FROM public.{table}')
        pairs = [(str(row[author_col]), str(row[pub_col])) for row in records
                 if row[author_col] is not None and row[pub_col] is not None]
        relationships[table] = set(pairs)
        stats[table] = {'rows': len(records), 'relationship_rows': len(pairs),
                        'null_id_rows': len(records)-len(pairs),
                        'duplicate_pair_excess': len(pairs)-len(relationships[table])}

    for table, pairs in relationships.items():
        uuid = table == 'author_publications'
        a_ids, p_ids = (uuid_author_ids, uuid_pub_ids) if uuid else (author_ids, pub_ids)
        stats[table].update({
            'unique_authors': len({a for a, _ in pairs}),
            'unique_publications': len({p for _, p in pairs}),
            'orphan_author_pairs': sum(a not in a_ids for a, _ in pairs),
            'orphan_publication_pairs': sum(p not in p_ids for _, p in pairs),
            'overlap_with_wide_pairs': len(pairs & relationships['author_contribution_weight']),
            'additional_pairs': len(pairs - relationships['author_contribution_weight']),
            'additional_publications': len({p for _, p in pairs} - {p for _, p in relationships['author_contribution_weight']}),
        })
    union = set().union(*(pairs for name, pairs in relationships.items() if name != 'author_publications' and name != 'eq15_effective_citations'))
    union_authors = {a for a, _ in union}
    union_pubs = {p for _, p in union}

    citation_edges = execute_select('SELECT pub_id, cites_pub_id FROM public.citation')
    edge_counts = Counter(row['pub_id'] for row in citation_edges)
    citing_counts = Counter(row['cites_pub_id'] for row in citation_edges)
    citation_summary = {
        'rows': len(citation_edges), 'unique_edges': len({(r['pub_id'], r['cites_pub_id']) for r in citation_edges}),
        'unique_cited_pub_ids': len(edge_counts), 'unique_citing_pub_ids': len(citing_counts),
        'orphan_cited_edges': sum(r['pub_id'] not in pub_ids for r in citation_edges),
        'orphan_citing_edges': sum(r['cites_pub_id'] not in pub_ids for r in citation_edges),
        'stored_equals_edges': sum(row['total_citation'] == edge_counts[row['pub_id']] for row in publications),
        'stored_greater_edges': sum(row['total_citation'] > edge_counts[row['pub_id']] for row in publications),
        'stored_less_edges': sum(row['total_citation'] < edge_counts[row['pub_id']] for row in publications),
        'stored_positive_zero_edges': sum(row['total_citation'] > 0 and edge_counts[row['pub_id']] == 0 for row in publications),
        'stored_zero_positive_edges': sum(row['total_citation'] == 0 and edge_counts[row['pub_id']] > 0 for row in publications),
        'sum_stored_totals': sum(row['total_citation'] or 0 for row in publications),
        'sum_edge_counts_for_publications': sum(edge_counts[row['pub_id']] for row in publications),
    }
    samples = []
    for key in ('W1182682356', 'W1054753857'):
        row = next((r for r in publications if r['pub_id'] == key), None)
        if row:
            samples.append({'pub_id': key, 'stored': row['total_citation'],
                            'cited_edges': edge_counts[key], 'citing_edges': citing_counts[key],
                            'source': row['source']})
    for predicate in (
        lambda r: r['total_citation'] == edge_counts[r['pub_id']] and r['total_citation'] > 0,
        lambda r: r['total_citation'] > 0 and edge_counts[r['pub_id']] == 0,
        lambda r: r['total_citation'] == 0 and edge_counts[r['pub_id']] > 0,
        lambda r: r['total_citation'] < edge_counts[r['pub_id']],
    ):
        row = next((r for r in publications if predicate(r)), None)
        if row and row['pub_id'] not in {s['pub_id'] for s in samples}:
            samples.append({'pub_id': row['pub_id'], 'stored': row['total_citation'],
                            'cited_edges': edge_counts[row['pub_id']],
                            'citing_edges': citing_counts[row['pub_id']], 'source': row['source']})

    author_id_stats = {}
    for table, column in AUTHOR_TABLES.items():
        records = execute_select(f'SELECT {column} FROM public.{table}')
        authority = uuid_author_ids if table in ('authors', 'author_metrics') else author_ids
        author_id_stats[table] = {'rows': len(records), **id_issues([r[column] for r in records], authority)}
    for table, pairs in relationships.items():
        authority = uuid_author_ids if table == 'author_publications' else author_ids
        author_id_stats[table] = {'relationship_pairs': len(pairs), **id_issues([a for a, _ in pairs], authority)}

    nm = execute_select('SELECT author_id, nm_index, metrics_available, per_total_cites, '
        'per_citations_per_paper, per_citation_rate, per_modified_hf_index, '
        'per_modified_hm_index, per_modified_g_index FROM public.author_nm_index')
    components = ('per_total_cites', 'per_citations_per_paper', 'per_citation_rate',
                  'per_modified_hf_index', 'per_modified_hm_index', 'per_modified_g_index')
    nm_summary = {
        'rows': len(nm), 'authors_total': len(author_ids),
        'unique_nm_authors': len({r['author_id'] for r in nm}),
        'authors_missing_nm_row': len(author_ids - {r['author_id'] for r in nm}),
        'orphan_nm_authors': len({r['author_id'] for r in nm} - author_ids),
        'duplicate_nm_rows': len(nm) - len({r['author_id'] for r in nm}),
        'nonnull_nm_scores': sum(r['nm_index'] is not None for r in nm),
        'null_nm_scores': sum(r['nm_index'] is None for r in nm),
        'incomplete_components': sum(any(r[c] is None for c in components) for r in nm),
        'scored_incomplete_components': sum(r['nm_index'] is not None and any(r[c] is None for c in components) for r in nm),
        'metadata_count_mismatches': sum(r['metrics_available'] != sum(r[c] is not None for c in components) for r in nm),
        'component_count_distribution': dict(Counter(r['metrics_available'] for r in nm)),
    }

    out = {
        'author_count': len(authors), 'publication_count': len(publications),
        'publication_null_year': sum(r['year'] is None for r in publications),
        'publication_null_citations': sum(r['total_citation'] is None for r in publications),
        'uuid_author_count': len(uuid_authors), 'uuid_publication_count': len(uuid_pubs),
        'relationship_sources': stats,
        'union_candidate_pairs': len(union), 'union_candidate_authors': len(union_authors),
        'union_candidate_publications': len(union_pubs),
        'union_orphan_authors': len(union_authors-author_ids),
        'union_orphan_publications': len(union_pubs-pub_ids),
        'citation': citation_summary, 'citation_samples': samples,
        'author_id': author_id_stats, 'nm': nm_summary,
    }
    print(json.dumps(out, indent=2, default=str))
    destination = PROJECT_ROOT / 'results' / 'publication_coverage_diagnostics.csv'
    with destination.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=('source', 'source_rows', 'relationship_rows',
            'unique_pairs', 'duplicate_pair_excess', 'publications_with_author_relationship',
            'publications_without_author_relationship', 'authors_with_publications',
            'authors_without_publications', 'orphan_author_pairs', 'orphan_publication_pairs',
            'overlap_with_wide_pairs', 'additional_publications'))
        writer.writeheader()
        for table, pairs in relationships.items():
            s = stats[table]
            uuid = table == 'author_publications'
            writer.writerow(dict(source=table, source_rows=s['rows'], relationship_rows=s['relationship_rows'],
                unique_pairs=len(pairs), duplicate_pair_excess=s['duplicate_pair_excess'],
                publications_with_author_relationship=s['unique_publications'],
                publications_without_author_relationship=(len(uuid_pub_ids) if uuid else len(pub_ids)) - len({p for _, p in pairs} & (uuid_pub_ids if uuid else pub_ids)),
                authors_with_publications=len({a for a, _ in pairs} & (uuid_author_ids if uuid else author_ids)),
                authors_without_publications=(len(uuid_author_ids) if uuid else len(author_ids)) - len({a for a, _ in pairs} & (uuid_author_ids if uuid else author_ids)),
                orphan_author_pairs=s['orphan_author_pairs'], orphan_publication_pairs=s['orphan_publication_pairs'],
                overlap_with_wide_pairs=s['overlap_with_wide_pairs'], additional_publications=s['additional_publications']))
        writer.writerow(dict(source='union_string_id_candidates_excluding_eq15', source_rows='',
            relationship_rows='', unique_pairs=len(union), duplicate_pair_excess='',
            publications_with_author_relationship=len(union_pubs & pub_ids),
            publications_without_author_relationship=len(pub_ids-union_pubs),
            authors_with_publications=len(union_authors & author_ids),
            authors_without_publications=len(author_ids-union_authors),
            orphan_author_pairs='', orphan_publication_pairs='', overlap_with_wide_pairs='',
            additional_publications=len(union_pubs-{p for _, p in relationships['author_contribution_weight']})))


if __name__ == '__main__':
    main()
