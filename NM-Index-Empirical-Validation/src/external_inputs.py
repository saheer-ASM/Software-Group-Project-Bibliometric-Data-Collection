"""Read explicit local research input CSVs, never production project files."""

from pathlib import Path

import pandas as pd

from .config import PROJECT_ROOT


SCHEMAS = {
    'award_labels': {'author_id', 'awardee'},
    'reference_scores': {'author_id', 'nm_index', 'c_score_raw',
                         'middle_author_share', 'career_stage', 'reference_version',
                         'evidence_reference'},
    'award_events': {'author_id', 'award_category', 'evidence_reference'},
    'annual_scores': {'author_id', 'year', 'nm_index'},
    'future_outcomes': {'author_id', 'outcome_start_year', 'outcome_end_year',
                        'future_citations', 'future_awards', 'h_index_growth'},
    'historical_scores': {'author_id', 'score_year', 'nm_index'},
    'scenario_data': {'author_id'},
    'subgroup_labels': {'author_id', 'gender', 'region', 'approved_for_analysis', 'evidence_reference'},
    'percentile_scores': {'author_id'},
    'paper_inputs': {'author_id', 'total_citation', 'self_citation_count', 'coauthor_count'},
    'portfolio_verification': {'author_id', 'portfolio_verified', 'evidence_reference'},
    'coauthor_counts': {'pub_id', 'coauthor_count', 'verified_complete', 'evidence_reference'},
}


def load_csv(kind, path):
    if kind not in SCHEMAS:
        raise ValueError(f'Unsupported local input kind: {kind}')
    supplied = Path(path)
    target = (supplied if supplied.is_absolute() else PROJECT_ROOT/supplied).resolve()
    if PROJECT_ROOT not in target.parents:
        raise ValueError('Research input CSV must be inside the isolated validation project')
    frame = pd.read_csv(target, dtype={'author_id': 'string'})
    missing = SCHEMAS[kind]-set(frame.columns)
    if missing:
        raise ValueError(f'{kind} missing required columns: {sorted(missing)}')
    if frame.author_id.isna().any():
        raise ValueError(f'{kind} has NULL author IDs')
    if kind in {'award_labels','future_outcomes','scenario_data','subgroup_labels','percentile_scores',
                'reference_scores',
                'portfolio_verification'} and frame.author_id.duplicated().any():
        raise ValueError(f'{kind} needs one row per author')
    if kind == 'portfolio_verification':
        flags = frame.portfolio_verified.astype(str).str.strip().str.lower()
        if not flags.isin({'true', 'false'}).all():
            raise ValueError('portfolio_verified must be true or false')
        frame['portfolio_verified'] = flags.eq('true')
    if kind == 'coauthor_counts':
        if frame.pub_id.isna().any() or frame.pub_id.duplicated().any():
            raise ValueError('coauthor_counts requires unique non-NULL pub_id values')
        flags = frame.verified_complete.astype(str).str.strip().str.lower()
        if not flags.isin({'true', 'false'}).all():
            raise ValueError('verified_complete must be true or false')
        frame['verified_complete'] = flags.eq('true')
    if kind == 'subgroup_labels':
        flags = frame.approved_for_analysis.astype(str).str.strip().str.lower()
        if not flags.isin({'true', 'false'}).all():
            raise ValueError('approved_for_analysis must be true or false')
        frame['approved_for_analysis'] = flags.eq('true')
    if kind == 'historical_scores' and frame[['author_id','score_year']].duplicated().any():
        raise ValueError('historical_scores has duplicate author/score_year records')
    if kind == 'annual_scores' and frame[['author_id','year']].duplicated().any():
        raise ValueError('annual_scores has duplicate author/year records')
    return frame


def load_pilot_author_ids(path):
    """Read a local CSV of exact stable IDs; do not infer identities from names."""
    supplied = Path(path)
    target = (supplied if supplied.is_absolute() else PROJECT_ROOT/supplied).resolve()
    if PROJECT_ROOT not in target.parents or not target.is_file():
        raise ValueError('Pilot author list must be an existing CSV inside the validation project')
    frame = pd.read_csv(target, dtype={'author_id': 'string'})
    columns = list(frame.columns)
    if columns not in (['author_id'], ['author_id', 'author_name']) or frame.empty:
        raise ValueError('Pilot author list must have author_id and optional author_name columns and at least one row')
    if 'author_name' in frame and (frame.author_name.isna().any()
                                  or frame.author_name.astype(str).str.strip().eq('').any()):
        raise ValueError('Pilot author_name values must not be blank')
    ids = frame.author_id
    if (ids.isna().any() or ids.str.strip().ne(ids).any() or ids.str.strip().eq('').any()
            or ids.duplicated().any() or ids.str.startswith('TEST_').any()
            or len(ids) > 6000):
        raise ValueError('Pilot requires 1–6000 unique, nonempty, real stable author IDs')
    return frame
