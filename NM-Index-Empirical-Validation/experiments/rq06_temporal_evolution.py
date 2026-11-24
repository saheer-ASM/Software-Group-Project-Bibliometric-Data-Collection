"""RQ6 one-author observed annual score trajectory."""

import pandas as pd

from analysis.temporal import trajectory
from .common import pending


def median_authors(annual_scores, reference_scores=None):
    """Default (author decision 2026-11-24): per career stage, the author with the
    median Nm-index in the latest year."""
    latest = annual_scores.loc[annual_scores.year == annual_scores.year.max()]
    if reference_scores is not None and 'career_stage' in reference_scores:
        latest = latest.merge(reference_scores[['author_id', 'career_stage']], on='author_id')
    else:
        latest = latest.assign(career_stage='All')
    picks = {}
    for stage, group in latest.groupby('career_stage'):
        group = group.sort_values(['nm_index', 'author_id']).reset_index(drop=True)
        picks[stage] = group.author_id.iloc[(len(group) - 1) // 2]
    return picks


def run(dataset, comparators, *, annual_scores=None, representative_author=None,
        trajectory_normalization='within_author_max', trajectory_decision_reference=None,
        reference_scores=None, **_):
    if annual_scores is None:
        return pending('RQ6 requires annual score snapshots', 'DATA_REQUIRED')
    if not {'author_id', 'year', 'nm_index'} <= set(annual_scores):
        return pending('RQ6 annual snapshots need author_id, year, nm_index', 'DATA_REQUIRED')
    metrics = [c for c in ('publication_count', 'nm_index', *comparators) if c in annual_scores]
    authors = ({'selected': representative_author} if representative_author
               else median_authors(annual_scores, reference_scores))
    trajectory_decision_reference = (trajectory_decision_reference or
        'Author decision 2026-11-24: median author per career stage, within-author max')
    frames = [trajectory(annual_scores, author, metrics).assign(career_stage=stage)
              for stage, author in authors.items()]
    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if output.empty:
        return pending('RQ6 selected author has no annual score records', 'DATA_REQUIRED')
    comparators = [c for c in comparators if c in output]
    results = {'score_evolution': output}
    if trajectory_normalization is None or not trajectory_decision_reference:
        results['status'] = pending('RQ6 normalized-score convention and representative-author decision reference required')['status']
        return results
    if trajectory_normalization != 'within_author_max':
        results['status'] = pending('Unsupported trajectory normalization', 'INVALID_INPUT')['status']
        return results
    normalized = output[[c for c in ('author_id', 'career_stage', 'year', 'publication_count')
                         if c in output]].copy()
    for metric in ('nm_index', *comparators):
        values = pd.to_numeric(output[metric], errors='coerce')
        maximum = values.groupby(output.author_id).transform('max')
        normalized[metric] = (values / maximum).where(maximum > 0)
    normalized['normalization'] = trajectory_normalization
    normalized['decision_reference'] = trajectory_decision_reference
    results['score_evolution_normalized'] = normalized
    results['status'] = pending('Explicit within-author normalization used', 'OK_WITH_EXPLICIT_CONVENTION')['status']
    return results
