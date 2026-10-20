"""Local, non-destructive extract validation and coverage diagnostics."""

import pandas as pd


def authorship_pairs(frame):
    rows = []
    for row in frame.to_dict('records'):
        for position in range(1, 11):
            author = row.get(f'author{position}id')
            if pd.notna(author) and author != '':
                rows.append({'author_id': author, 'pub_id': row.get('pub_id'),
                             'position': position, 'contribution_weight': row.get(f'author{position}id_weight')})
    return pd.DataFrame(rows, columns=['author_id', 'pub_id', 'position', 'contribution_weight'])


def check(extracts):
    a, p, n = extracts.authors, extracts.publications, extracts.nm
    links = authorship_pairs(extracts.authorship)
    issues = []

    def add(name, count, severity, detail):
        issues.append(dict(check=name, count=int(count), status=severity if count else 'VALID', detail=detail))

    add('duplicate_author_ids', a.author_id.duplicated().sum(), 'ERROR', 'Duplicate authoritative author key')
    add('duplicate_publication_ids', p.pub_id.duplicated().sum(), 'ERROR', 'Duplicate authoritative paper key')
    add('duplicate_author_publication_pairs', links[['author_id', 'pub_id']].duplicated().sum(),
        'WARNING', 'Deduplicate stable-ID pairs; duplicate slots are not additional papers')
    add('orphan_link_authors', (~links.author_id.isin(a.author_id)).sum(), 'ERROR', 'Linked author absent from author')
    add('orphan_link_publications', (~links.pub_id.isin(p.pub_id)).sum(), 'ERROR', 'Linked paper absent from publication')
    add('authors_without_linked_publications', (~a.author_id.isin(links.author_id)).sum(),
        'INCOMPLETE', 'Absence of a link is unknown portfolio coverage')
    add('publications_without_author_relationship', (~p.pub_id.isin(links.pub_id)).sum(),
        'INCOMPLETE', 'No stable-ID authorship in current source')
    citation = pd.to_numeric(p.total_citation, errors='coerce')
    add('missing_or_non_numeric_citation_counts', citation.isna().sum(), 'ERROR', 'Required raw count absent')
    add('negative_citation_counts', (citation < 0).sum(), 'ERROR', 'Raw count must be nonnegative')
    year = pd.to_numeric(p.year, errors='coerce')
    add('invalid_publication_years', (year.isna() | (year < 1000) | (year > 9999)).sum(),
        'INCOMPLETE', 'Missing or out-of-range year')
    add('missing_contribution_weights', links.contribution_weight.isna().sum(), 'INCOMPLETE',
        'Relevant only to an approved contribution-weighted strategy')
    add('missing_nm_rows', (~a.author_id.isin(n.author_id)).sum(), 'INCOMPLETE', 'No authoritative NM row')
    add('null_nm_scores', n.nm_index.isna().sum(), 'INCOMPLETE', 'Stored NM row with unavailable score')
    add('duplicate_nm_records', n.author_id.duplicated().sum(), 'ERROR', 'Duplicate NM author key')
    add('orphan_nm_records', (~n.author_id.isin(a.author_id)).sum(), 'ERROR', 'NM author absent from author')
    edges = extracts.citations.groupby('pub_id').size()
    comparison = p[['pub_id', 'total_citation']].copy()
    comparison['edges'] = comparison.pub_id.map(edges).fillna(0)
    add('inconsistent_citation_sources',
        (pd.to_numeric(comparison.total_citation, errors='coerce') != comparison.edges).sum(),
        'WARNING', 'Stored raw paper total differs from observed incoming edges; provenance unresolved')
    return pd.DataFrame(issues, columns=['check', 'count', 'status', 'detail']), links


def to_markdown(report):
    lines = ['# Data-quality report', '', 'Counts describe the extracted snapshot, not a verified complete career dataset.',
             '', '| Check | Count | Status | Detail |', '|---|---:|---|---|']
    for row in report.to_dict('records'):
        lines.append(f"| {row['check']} | {row['count']} | {row['status']} | {row['detail']} |")
    return '\n'.join(lines) + '\n'
