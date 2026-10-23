"""Read-only, lecturer-approved RQ7 input transformations and benchmark contract.

This module does not calculate NM. It rejects unspecified graph allocations rather
than inventing citation relationships or publication/contribution metadata.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import StringIO

import pandas as pd


class MethodologyInputRequired(ValueError):
    """The lecturer specified a scenario but its exact graph data is unavailable."""


BENCHMARK_TABLES = ('field_year_means', 'field_caps', 'z_means',
                    'z_standard_deviations', 'percentile_reference')


@dataclass(frozen=True)
class FrozenBenchmarks:
    version: str
    original_author_count: int
    original_author_digest: str
    table_bytes: tuple[tuple[str, bytes], ...]
    sha256: str

    @classmethod
    def from_original(cls, author_ids, tables, *, version, synthetic=False):
        ids = tuple(map(str, author_ids))
        if not version or not str(version).strip() or not ids or len(set(ids)) != len(ids):
            raise ValueError('Frozen reference needs a version and unique original author IDs')
        if not synthetic and len(ids) != 100000:
            raise MethodologyInputRequired('Exactly the original 100000-author reference population required')
        absent = set(BENCHMARK_TABLES)-set(tables)
        if absent:
            raise MethodologyInputRequired(f'Original benchmark tables missing: {sorted(absent)}')
        contents = []
        for name in BENCHMARK_TABLES:
            frame = tables[name]
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                raise MethodologyInputRequired(f'Original {name} must be a nonempty table')
            contents.append((name, frame.to_csv(index=False).encode('utf-8')))
        author_digest = sha256('\n'.join(sorted(ids)).encode('utf-8')).hexdigest()
        digest = sha256(str(version).encode('utf-8')+author_digest.encode('ascii')+
                        b''.join(name.encode('ascii')+data for name, data in contents)).hexdigest()
        return cls(str(version), len(ids), author_digest, tuple(contents), digest)

    def snapshot(self, name):
        for key, data in self.table_bytes:
            if key == name:
                return pd.read_csv(StringIO(data.decode('utf-8')))
        raise KeyError(name)


def percentile_inflation(original, manipulated):
    """The lecturer's exact percentage-inflation rule with a zero guard."""
    values = pd.to_numeric(pd.Series([original, manipulated]), errors='coerce')
    if values.isna().any() or not values.between(0, 100).all():
        return dict(status='DATA_REQUIRED', reason='Missing/invalid percentile',
                    inflation_percent=float('nan'))
    if values.iloc[0] == 0:
        return dict(status='NOT_APPLICABLE', reason='Original percentile is zero',
                    inflation_percent=float('nan'))
    return dict(status='OK', reason='',
                inflation_percent=100*(values.iloc[1]-values.iloc[0])/values.iloc[0])


def add_self_citation_relationships(papers, edges, additions, *, target_author,
                                    relevant_core_authors, original_self_citation_count):
    """Add fully specified new citing papers/edges; never synthesize identities."""
    required = {'pub_id', 'authors'}
    if not required <= set(papers):
        raise ValueError(f'Paper fields missing: {sorted(required-set(papers))}')
    if not {'cited_pub_id', 'citing_pub_id'} <= set(edges):
        raise ValueError('Citation edges require cited_pub_id,citing_pub_id')
    if not {'pub_id', 'authors', 'cited_pub_id'} <= set(additions):
        raise MethodologyInputRequired('New citing papers need pub_id,authors,cited_pub_id')
    if not set(papers.columns) <= set(additions):
        raise MethodologyInputRequired('New citing papers need all original paper metadata')
    if 'citation_id' in edges and 'citation_id' not in additions:
        raise MethodologyInputRequired('New citation edges need unique citation_id values')
    expected = original_self_citation_count * .5
    if expected != int(expected):
        raise MethodologyInputRequired('Exact +50% count is fractional; rounding decision required')
    if len(additions) != expected:
        raise MethodologyInputRequired('Supplied citing relationships do not equal +50%')
    if ('citation_id' in edges and (additions.citation_id.isna().any()
            or additions.citation_id.duplicated().any()
            or additions.citation_id.isin(edges.citation_id).any())):
        raise ValueError('New citation IDs must be unique')
    if additions.pub_id.isna().any() or additions.pub_id.duplicated().any() or (
            additions.pub_id.isin(papers.pub_id)).any():
        raise ValueError('New citing-paper IDs must be unique and absent from original papers')
    cited = set(papers.pub_id)
    core = set(relevant_core_authors)
    if 'total_citation' not in papers:
        raise MethodologyInputRequired('Paper citation totals are required')
    observed_edges = edges.groupby('cited_pub_id').size()
    if any(observed_edges.get(row.pub_id, 0) != row.total_citation
           for row in papers.itertuples(index=False)):
        raise MethodologyInputRequired('Complete original citation edges must match paper totals')
    for row in additions.itertuples(index=False):
        authors = set(row.authors)
        if row.cited_pub_id not in cited or target_author not in authors or not core <= authors:
            raise MethodologyInputRequired('Each added edge needs a known cited paper and target/core authors')
    new_papers = pd.concat([papers.copy(deep=True),
        additions.reindex(columns=papers.columns)], ignore_index=True)
    new_counts = additions.groupby('cited_pub_id').size()
    for pub_id, added_count in new_counts.items():
        position = new_papers.index[new_papers.pub_id.eq(pub_id)][0]
        new_papers.at[position, 'total_citation'] += added_count
    new_edges = pd.concat([edges.copy(deep=True),
        additions.rename(columns={'pub_id': 'citing_pub_id'}).reindex(
            columns=edges.columns)], ignore_index=True)
    return new_papers, new_edges


def split_salami_papers(papers, edges, split_assignments, *, target_pub_ids):
    """Split papers with source-specified edge allocation and identical metadata."""
    # Field metadata is the canonical `field_weights` column read by the NM calculator.
    required_paper = {'pub_id', 'authors', 'field_weights', 'year', 'total_citation'}
    required_edge = {'citation_id', 'cited_pub_id', 'citing_pub_id'}
    required_assignment = {'citation_id', 'half'}
    if (not required_paper <= set(papers) or not ({'field', 'field_weights'} & set(papers))
            or not required_edge <= set(edges)):
        raise MethodologyInputRequired('Complete paper metadata and citation IDs required')
    if not required_assignment <= set(split_assignments):
        raise MethodologyInputRequired('Each citation needs an explicit split half (1 or 2)')
    selected = set(target_pub_ids)
    if not selected or not selected <= set(papers.pub_id):
        raise ValueError('Unknown or empty target paper selection')
    affected = edges.loc[edges.cited_pub_id.isin(selected)]
    outgoing = edges.loc[edges.citing_pub_id.isin(selected)]
    assignment = split_assignments.set_index('citation_id')
    if (split_assignments.citation_id.duplicated().any()
            or not set(affected.citation_id) <= set(assignment.index)
            or not assignment.half.isin([1, 2]).all()):
        raise MethodologyInputRequired('Unique explicit half assignment needed for every citation')
    if len(outgoing):
        if 'citing_half' not in assignment or not set(outgoing.citation_id) <= set(assignment.index):
            raise MethodologyInputRequired('Outgoing citations from split papers need explicit citing_half assignments')
        if not assignment.loc[outgoing.citation_id, 'citing_half'].isin([1, 2]).all():
            raise MethodologyInputRequired('Every outgoing citation needs citing_half 1 or 2')
    new_papers = papers.loc[~papers.pub_id.isin(selected)].copy(deep=True)
    new_edges = edges.loc[~edges.cited_pub_id.isin(selected)].copy(deep=True)
    for row in papers.loc[papers.pub_id.isin(selected)].itertuples(index=False):
        old_edges = affected.loc[affected.cited_pub_id.eq(row.pub_id)].copy()
        if len(old_edges) != row.total_citation or len(old_edges) % 2:
            raise MethodologyInputRequired('Half-citation split needs complete even-count edge evidence')
        assigned = old_edges.citation_id.map(assignment.half)
        if len(old_edges) and assigned.value_counts().to_dict() != {
                1: len(old_edges)//2, 2: len(old_edges)//2}:
            raise MethodologyInputRequired('Citation halves must contain equal edge counts')
        for half in (1, 2):
            new_id = f'{row.pub_id}__SPLIT_{half}'
            if new_id in set(papers.pub_id):
                raise ValueError('Split paper ID collision')
            copy = papers.loc[papers.pub_id.eq(row.pub_id)].copy(deep=True)
            copy['pub_id'] = new_id
            copy['total_citation'] = row.total_citation/2
            new_papers = pd.concat([new_papers, copy], ignore_index=True)
            links = old_edges.loc[assigned.eq(half)].copy()
            links['cited_pub_id'] = new_id
            new_edges = pd.concat([new_edges, links], ignore_index=True)
    # A split paper can itself cite another paper. Preserve each relationship
    # only with a source-supplied choice of which new half made that citation.
    for old_id in selected:
        mask = new_edges.citing_pub_id.eq(old_id)
        if mask.any():
            halves = new_edges.loc[mask, 'citation_id'].map(assignment.citing_half)
            new_edges.loc[mask, 'citing_pub_id'] = [f'{old_id}__SPLIT_{int(half)}' for half in halves]
    return new_papers, new_edges


def add_gift_authorship(papers, assignments, *, target_author, target_portfolio_ids):
    """Add target in an explicitly supplied middle slot on coauthor papers."""
    if not {'pub_id', 'authors', 'year', 'field_weights', 'total_citation'} <= set(papers):
        raise MethodologyInputRequired('Gift scenario needs full paper metadata')
    if not {'pub_id', 'position'} <= set(assignments):
        raise MethodologyInputRequired('Gift papers and middle positions must be supplied')
    count = .3*len(set(target_portfolio_ids))
    if count != int(count):
        raise MethodologyInputRequired('30% of portfolio is fractional; rounding decision required')
    if len(assignments) != count or assignments.pub_id.duplicated().any():
        raise MethodologyInputRequired('Exactly 30% distinct additional papers required')
    original = papers.copy(deep=True)
    portfolio = original.loc[original.pub_id.isin(target_portfolio_ids)]
    known_coauthors = set().union(*(set(x) for x in portfolio.authors))-{target_author}
    for row in assignments.itertuples(index=False):
        matched = original.loc[original.pub_id.eq(row.pub_id)]
        if len(matched) != 1 or row.pub_id in target_portfolio_ids:
            raise MethodologyInputRequired('Gift paper must be a distinct existing paper')
        authors = list(matched.iloc[0].authors)
        if (target_author in authors or not known_coauthors.intersection(authors)
                or not isinstance(row.position, int)
                or row.position < 2 or row.position > len(authors)):
            raise MethodologyInputRequired('Gift paper needs an existing coauthor and explicit middle position')
        authors.insert(row.position-1, target_author)
        original.at[matched.index[0], 'authors'] = tuple(authors)
    return original
