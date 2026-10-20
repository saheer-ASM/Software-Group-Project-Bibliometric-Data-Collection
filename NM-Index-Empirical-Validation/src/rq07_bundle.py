"""Load complete RQ7 graph/reference CSVs supplied inside this project.

No database connection or calculation is performed here. The bundle is an
explicit interface for a later, independently verified data export.
"""

import json
import re
from hashlib import sha256
from pathlib import Path

import pandas as pd

from analysis.counterfactual import BENCHMARK_TABLES, FrozenBenchmarks
from analysis.rq07_engine import AuthorGraphInput
from nm_index.counterfactual_calculator import NMParameters, _reference_lookup
from .config import PROJECT_ROOT


PAPER_COLUMNS = {'pub_id', 'authors', 'year', 'field_weights',
                 'contribution_mode', 'total_citation'}
JSON_COLUMNS = ('authors', 'field_weights', 'first_positions', 'last_positions',
                'aci_shares', 'credit_roles', 'credit_role_weights')


def _inside(base, path):
    path = path.resolve()
    if path != base and base not in path.parents:
        raise ValueError('RQ7 bundle path must stay inside the validation project')
    return path


def _csv(path, required):
    if not path.is_file():
        raise ValueError(f'RQ7 bundle input missing: {path.name}')
    frame = pd.read_csv(path, dtype={'author_id': 'string', 'pub_id': 'string',
                                     'cited_pub_id': 'string', 'citing_pub_id': 'string',
                                     'citation_id': 'string'})
    if not required <= set(frame):
        raise ValueError(f'{path.name} missing columns: {sorted(required-set(frame))}')
    return frame


def _paper_frame(path, *, additions=False):
    required = PAPER_COLUMNS | ({'citation_id', 'cited_pub_id'} if additions else set())
    frame = _csv(path, required)
    for column in JSON_COLUMNS:
        if column not in frame:
            continue
        def decode(value):
            if pd.isna(value):
                return None
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                raise ValueError(f'{path.name}: invalid JSON in {column}') from None
        frame[column] = frame[column].map(decode)
    if frame.empty and not additions:
        raise ValueError(f'{path.name}: empty graph')
    if not frame.empty:
        if not frame.authors.map(lambda x: isinstance(x, list) and bool(x)).all():
            raise ValueError(f'{path.name}: authors must be nonempty ordered JSON arrays')
        frame['authors'] = frame.authors.map(tuple)
        if not frame.field_weights.map(lambda x: isinstance(x, dict) and bool(x)).all():
            raise ValueError(f'{path.name}: field_weights must be nonempty JSON objects')
        for column in ('first_positions', 'last_positions'):
            if column in frame:
                frame[column] = frame[column].map(
                    lambda value: tuple(value) if isinstance(value, list) else None)
    return frame


def load_bundle(path, cohort_ids, *, synthetic=False):
    """Return per-author graphs, frozen reference and explicit NM parameters."""
    root = _inside(PROJECT_ROOT.resolve(),
                   (PROJECT_ROOT/path if not Path(path).is_absolute() else Path(path)))
    if not root.is_dir():
        raise ValueError('RQ7 bundle directory does not exist')
    ids = tuple(map(str, cohort_ids))
    if not ids or len(set(ids)) != len(ids) or any(not re.fullmatch(r'[A-Za-z0-9_-]+', value) for value in ids):
        raise ValueError('RQ7 cohort IDs must be unique safe stable identifiers')
    metadata_path = root/'metadata.json'
    if not metadata_path.is_file():
        raise ValueError('RQ7 bundle metadata.json missing')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    required_meta = {'version', 'as_of_year', 'epsilon_0', 'career_boost',
                     'career_decay', 'component_weights'}
    if not required_meta <= metadata.keys():
        raise ValueError(f'RQ7 metadata missing {sorted(required_meta-set(metadata))}')
    parameters = NMParameters(as_of_year=int(metadata['as_of_year']),
        epsilon_0=float(metadata['epsilon_0']),
        career_boost=float(metadata['career_boost']),
        career_decay=float(metadata['career_decay']),
        weights=tuple(map(float, metadata['component_weights'])))
    tables = {name: _csv(root/'reference'/f'{name}.csv', set())
              for name in BENCHMARK_TABLES}
    reference = tables['percentile_reference']
    if not {'author_id', 'metric', 'value'} <= set(reference):
        raise ValueError('percentile_reference requires author_id,metric,value')
    reference_ids = reference.loc[reference.metric.eq('nm_index'), 'author_id'].dropna().astype(str)
    if reference_ids.duplicated().any() or not set(ids) <= set(reference_ids):
        raise ValueError('Original reference must contain every selected author exactly once')
    frozen = FrozenBenchmarks.from_original(reference_ids, tables,
        version=metadata['version'], synthetic=synthetic)
    _reference_lookup(frozen)  # Structural/author-set check; no metric calculation.
    graphs = {}
    for author in ids:
        graph_root = _inside(root, root/'graphs'/author)
        papers = _paper_frame(graph_root/'papers.csv')
        edges = _csv(graph_root/'citation_edges.csv',
                     {'citation_id', 'cited_pub_id', 'citing_pub_id'})
        additions = _paper_frame(graph_root/'self_additions.csv', additions=True)
        salami = _csv(graph_root/'salami_assignments.csv', {'citation_id', 'half'})
        gift = _csv(graph_root/'gift_assignments.csv', {'pub_id', 'position'})
        self_path = graph_root/'self_metadata.json'
        if not self_path.is_file():
            raise ValueError(f'{author}: self_metadata.json missing')
        self_info = json.loads(self_path.read_text(encoding='utf-8'))
        if not {'career_start_year', 'original_self_citation_count', 'relevant_core_authors'} <= self_info.keys():
            raise ValueError(f'{author}: career/self-citation metadata incomplete')
        graphs[author] = AuthorGraphInput(
            papers=papers, edges=edges,
            career_start_year=int(self_info['career_start_year']),
            self_additions=additions,
            original_self_citation_count=int(self_info['original_self_citation_count']),
            relevant_core_authors=frozenset(self_info['relevant_core_authors']),
            salami_assignments=salami, gift_assignments=gift,
            source_sha256=sha256(b''.join((graph_root/name).read_bytes() for name in (
                'papers.csv', 'citation_edges.csv', 'self_additions.csv',
                'self_metadata.json', 'salami_assignments.csv',
                'gift_assignments.csv'))).hexdigest())
    return graphs, frozen, parameters
