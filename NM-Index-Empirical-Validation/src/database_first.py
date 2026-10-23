"""Select verified database inputs before compatible local fallbacks.

The mapped research schema does not currently certify complete portfolios,
store the approved raw C-score reference, or describe RQ7 counterfactual
choices.  Those gaps are explicit; they must not be filled from a plausible
but scientifically different column.  No connection is opened by this module.
"""

from dataclasses import dataclass
import pandas as pd
import numpy as np

from analysis.counterfactual import FrozenBenchmarks
from analysis.rq07_engine import AuthorGraphInput
from nm_index.counterfactual_calculator import NMParameters, _reference_lookup


SOURCES = ('portfolio_verification', 'reference_scores', 'rq07_bundle')
RQ_USES = {
    'reference_scores': {'rq01', 'rq04'},
    'rq07_bundle': {'rq07', 'sensitivity'},
}
DATABASE_GAPS = {
    'portfolio_verification': (
        'The mapped research schema has no author-level complete-portfolio '
        'attestation or source-coverage evidence; linked publications alone '
        'cannot establish an exhaustive career portfolio.'),
    'reference_scores': (
        'The mapped research schema has no verified raw C-score source or '
        'approved original 100000-author reference membership/version. '
        'Stored NM and publication data are only partial inputs.'),
    'rq07_bundle': (
        'The mapped research schema lacks verified complete citation/authorship '
        'graphs, all frozen reference denominators, and explicit counterfactual '
        'paper/edge assignments. Original rows cannot supply invented scenarios.'),
}


def inspect_mapped_extracts(extracts, ids, names):
    """Assess the already-fetched research rows; never infer missing evidence.

    This is the database-first attempt supported by today's fixed SQL mapping.
    It deliberately returns no complete candidate for any of the three
    contracts: the saved schema has no approved attestation, raw C-score, or
    counterfactual choices. The observed row counts make the rejection
    reviewable without another connection or a fabricated value.
    """
    ids = set(map(str, ids))
    names = set(names)
    found = set(extracts.authors.author_id.dropna().astype(str))
    reasons = {
        'portfolio_verification': (
            f'{len(found & ids)}/{len(ids)} selected authors and '
            f'{len(extracts.publications)} linked-paper rows were fetched; '
            + DATABASE_GAPS['portfolio_verification'])
    }
    if RQ_USES['reference_scores'] & names:
        reasons['reference_scores'] = (
            f'{len(extracts.nm)} stored NM rows were fetched for this extract; '
            + DATABASE_GAPS['reference_scores'])
    if RQ_USES['rq07_bundle'] & names:
        reasons['rq07_bundle'] = (
            f'{len(extracts.citations)} citation-edge rows were fetched for this extract; '
            + DATABASE_GAPS['rq07_bundle'])
    return {}, reasons


@dataclass(frozen=True)
class SourceDecision:
    input_name: str
    source: str
    reason: str
    affected_rqs: str
    authors_affected: int
    records_affected: int

    def as_record(self):
        return vars(self).copy()


def _portfolio_valid(frame, ids):
    if not isinstance(frame, pd.DataFrame):
        return False, 'portfolio verification is not a table'
    required = {'author_id', 'portfolio_verified', 'evidence_reference'}
    if not required <= set(frame):
        return False, 'portfolio verification lacks required columns'
    if frame.author_id.isna().any() or frame.author_id.astype(str).duplicated().any():
        return False, 'portfolio verification has null or duplicate author IDs'
    if not frame.portfolio_verified.map(lambda value: type(value) is bool).all():
        return False, 'portfolio verification must contain Boolean flags'
    valid = frame.loc[frame.portfolio_verified & frame.evidence_reference.notna()
        & frame.evidence_reference.astype(str).str.strip().ne(''), 'author_id'].astype(str)
    if not set(ids) <= set(valid):
        return False, 'not every selected author has a true flag and nonblank evidence'
    return True, ''


def _reference_valid(frame, ids, *, synthetic=False):
    if not isinstance(frame, pd.DataFrame):
        return False, 'reference scores are not a table'
    required = {'author_id', 'nm_index', 'c_score_raw', 'middle_author_share',
                'career_stage', 'reference_version', 'evidence_reference'}
    if not required <= set(frame):
        return False, 'reference scores lack required columns'
    if frame.author_id.isna().any() or frame.author_id.astype(str).duplicated().any():
        return False, 'reference scores have null or duplicate author IDs'
    if not synthetic and len(frame) != 100000:
        return False, 'approved original reference requires exactly 100000 authors'
    if not set(ids) <= set(frame.author_id.astype(str)):
        return False, 'selected authors are absent from the original reference'
    versions = frame.reference_version.dropna().astype(str).str.strip().unique()
    if len(versions) != 1 or not versions[0]:
        return False, 'reference scores need one nonblank frozen version'
    if frame.evidence_reference.isna().any() or frame.evidence_reference.astype(str).str.strip().eq('').any():
        return False, 'reference scores lack provenance evidence'
    numeric = frame[['nm_index', 'c_score_raw', 'middle_author_share']].apply(
        pd.to_numeric, errors='coerce')
    if (numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all()
            or not numeric.nm_index.between(0, 100).all()
            or not numeric.middle_author_share.between(0, 1).all()):
        return False, 'reference NM/C-score/share values are missing or invalid'
    stages = {'Early', 'Mid-Early', 'Mid-Late', 'Senior'}
    if not frame.career_stage.astype(str).str.strip().isin(stages).all():
        return False, 'reference career stages are missing or unapproved'
    return True, ''


def _rq07_valid(bundle, ids, *, synthetic=False):
    if not isinstance(bundle, tuple) or len(bundle) != 3:
        return False, 'RQ7 graph/reference/parameter triplet is missing'
    graphs, frozen, parameters = bundle
    if not isinstance(graphs, dict) or set(graphs) != set(ids):
        return False, 'RQ7 graphs do not cover every selected author'
    if not isinstance(frozen, FrozenBenchmarks) or not isinstance(parameters, NMParameters):
        return False, 'RQ7 frozen benchmarks or NM parameters are unverified types'
    if not synthetic and frozen.original_author_count != 100000:
        return False, 'RQ7 requires the original 100000-author reference'
    try:
        _reference_lookup(frozen)
    except (ValueError, KeyError, TypeError) as error:
        return False, f'RQ7 frozen reference invalid: {error}'
    for author, graph in graphs.items():
        if not isinstance(graph, AuthorGraphInput) or not isinstance(graph.papers, pd.DataFrame) or not isinstance(graph.edges, pd.DataFrame):
            return False, f'RQ7 graph malformed for {author}'
        if not {'pub_id','authors','year','field_weights','contribution_mode','total_citation'} <= set(graph.papers):
            return False, f'RQ7 papers incomplete for {author}'
        if not {'citation_id','cited_pub_id','citing_pub_id'} <= set(graph.edges):
            return False, f'RQ7 citation edges incomplete for {author}'
        if graph.papers.empty or graph.papers.pub_id.isna().any() or graph.papers.pub_id.duplicated().any():
            return False, f'RQ7 paper IDs invalid for {author}'
        if graph.edges.citation_id.isna().any() or graph.edges.citation_id.duplicated().any():
            return False, f'RQ7 citation IDs invalid for {author}'
        paper_ids = set(graph.papers.pub_id)
        if not set(graph.edges.cited_pub_id) <= paper_ids or not set(graph.edges.citing_pub_id) <= paper_ids:
            return False, f'RQ7 cited or citing metadata absent for {author}'
        counts = graph.edges.groupby('cited_pub_id').size()
        if any(counts.get(row.pub_id, 0) != row.total_citation for row in graph.papers.itertuples(index=False)):
            return False, f'RQ7 edge counts disagree with stored paper totals for {author}'
        if graph.self_additions is None or graph.original_self_citation_count is None or graph.relevant_core_authors is None or graph.salami_assignments is None or graph.gift_assignments is None:
            return False, f'RQ7 scenario inputs incomplete for {author}'
        if (not isinstance(graph.original_self_citation_count, int)
                or isinstance(graph.original_self_citation_count, bool)
                or graph.original_self_citation_count < 0):
            return False, f'RQ7 original self-citation count invalid for {author}'
        if not graph.papers.authors.map(lambda value: isinstance(value, (tuple, list)) and bool(value)
                                        and len(value) == len(set(value))).all():
            return False, f'RQ7 complete ordered author rosters invalid for {author}'
        if not graph.papers.field_weights.map(lambda value: isinstance(value, dict) and bool(value)).all():
            return False, f'RQ7 field weights invalid for {author}'
        portfolio = graph.papers.loc[graph.papers.authors.map(lambda authors: author in authors)]
        if portfolio.empty:
            return False, f'RQ7 original portfolio absent for {author}'
        additions = graph.self_additions
        if not isinstance(additions, pd.DataFrame) or not (
                {'pub_id','authors','year','field_weights','contribution_mode',
                 'total_citation','citation_id','cited_pub_id'} <= set(additions)):
            return False, f'RQ7 self-addition records incomplete for {author}'
        expected_additions = graph.original_self_citation_count * .5
        if expected_additions != int(expected_additions) or len(additions) != expected_additions:
            return False, f'RQ7 exact self-citation scenario count invalid for {author}'
        salami = graph.salami_assignments
        affected = graph.edges.loc[graph.edges.cited_pub_id.isin(portfolio.pub_id)]
        if (not isinstance(salami, pd.DataFrame) or not {'citation_id','half'} <= set(salami)
                or salami.citation_id.isna().any() or salami.citation_id.duplicated().any()
                or not set(affected.citation_id) <= set(salami.citation_id)
                or not salami.half.isin([1, 2]).all()):
            return False, f'RQ7 salami assignments incomplete for {author}'
        gift = graph.gift_assignments
        expected_gift = .3 * len(portfolio)
        if (not isinstance(gift, pd.DataFrame) or not {'pub_id','position'} <= set(gift)
                or expected_gift != int(expected_gift) or len(gift) != expected_gift
                or gift.pub_id.isna().any() or gift.pub_id.duplicated().any()):
            return False, f'RQ7 exact gift-authorship assignments invalid for {author}'
    return True, ''


def _fallback(name, supplied, ids):
    paths = supplied.get('_fallback_paths') or {}
    if name == 'rq07_bundle':
        if all(supplied.get(key) is not None for key in ('graph_inputs','frozen_benchmarks','nm_parameters')):
            return (supplied['graph_inputs'], supplied['frozen_benchmarks'], supplied['nm_parameters']), ''
        path = supplied.get('rq07_bundle_path')
        if path is None:
            return None, 'no RQ7 fallback bundle supplied'
        from .rq07_bundle import load_bundle
        try:
            return load_bundle(path, ids), ''
        except (ValueError, OSError, KeyError, TypeError) as error:
            return None, f'RQ7 fallback invalid: {error}'
    if name in supplied and supplied[name] is not None:
        return supplied[name], ''
    if name not in paths:
        return None, f'no {name} fallback supplied'
    from .external_inputs import load_csv
    try:
        return load_csv(name, paths[name]), ''
    except (ValueError, OSError, KeyError, TypeError) as error:
        return None, f'{name} fallback invalid: {error}'


def resolve_real_inputs(ids, names, supplied=None, database_candidates=None, *,
                        database_reasons=None, synthetic=False):
    """Return selected inputs and explicit lineage without querying the database.

    A database adapter may pass only values retrieved from a validated read-only
    snapshot as ``database_candidates``. Missing mapped sources fail closed.
    Both source types pass identical structural/content checks.
    """
    ids = tuple(map(str, ids))
    names = set(names)
    supplied = dict(supplied or {})
    candidates = database_candidates or {}
    database_reasons = database_reasons or {}
    needed = ['portfolio_verification']
    if RQ_USES['reference_scores'] & names:
        needed.append('reference_scores')
    if RQ_USES['rq07_bundle'] & names:
        needed.append('rq07_bundle')
    chosen = {key: value for key, value in supplied.items()
              if key not in {'portfolio_verification','reference_scores','graph_inputs',
                             'frozen_benchmarks','nm_parameters','_fallback_paths','rq07_bundle_path'}}
    decisions = []
    for name in needed:
        affected = ';'.join(sorted(names if name == 'portfolio_verification' else RQ_USES[name] & names))
        validator = (_portfolio_valid if name == 'portfolio_verification' else
                     _reference_valid if name == 'reference_scores' else _rq07_valid)
        database_value = candidates.get(name)
        db_reason = database_reasons.get(name, DATABASE_GAPS[name])
        if database_value is not None:
            good, failure = (validator(database_value, ids) if name == 'portfolio_verification'
                else validator(database_value, ids, synthetic=synthetic))
            if good:
                value, origin, reason = database_value, 'DATABASE', 'Verified database source selected'
            else:
                db_reason = f'Database candidate rejected: {failure}'
                value = None
        else:
            value = None
        if value is None:
            fallback_value, fallback_reason = _fallback(name, supplied, ids)
            if fallback_value is not None:
                good, failure = (validator(fallback_value, ids) if name == 'portfolio_verification'
                    else validator(fallback_value, ids, synthetic=synthetic))
                if good:
                    value, origin = fallback_value, 'VERIFIED_FALLBACK'
                    reason = f'{db_reason} Verified fallback selected.'
                else:
                    fallback_reason = f'Fallback rejected: {failure}'
            if value is None:
                origin = 'UNAVAILABLE'
                reason = f'{db_reason} {fallback_reason}'
        if value is not None:
            if name == 'rq07_bundle':
                chosen['graph_inputs'], chosen['frozen_benchmarks'], chosen['nm_parameters'] = value
                authors = len(ids)
                records = sum(len(graph.papers)+len(graph.edges) for graph in value[0].values())
            else:
                chosen[name] = value
                authors = len(ids)
                records = len(value)
        else:
            authors = len(ids)
            records = 0
        decisions.append(SourceDecision(name, origin, reason, affected, authors, records))
    return chosen, decisions
