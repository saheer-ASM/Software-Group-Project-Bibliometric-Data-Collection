"""Execute lecturer-approved RQ7 graph scenarios on isolated in-memory copies."""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256

import numpy as np
import pandas as pd

from analysis.counterfactual import (MethodologyInputRequired,
    add_gift_authorship, add_self_citation_relationships,
    percentile_inflation, split_salami_papers)
from nm_index.counterfactual_calculator import NMParameters, _percentile, calculate_nm


SCENARIOS = ('self_citations_plus_50_percent',
             'salami_double_papers_half_citations',
             'gift_authorship_plus_30_percent')
SUPPORTED_BASELINES = ('raw_total_cites', 'h_index', 'hf_index', 'g_index')


@dataclass(frozen=True)
class AuthorGraphInput:
    papers: pd.DataFrame
    edges: pd.DataFrame
    career_start_year: int
    self_additions: pd.DataFrame | None = None
    original_self_citation_count: int | None = None
    relevant_core_authors: frozenset[str] | None = None
    salami_assignments: pd.DataFrame | None = None
    gift_assignments: pd.DataFrame | None = None
    source_sha256: str = ''


def _baseline_scores(author_id, papers):
    portfolio = papers.loc[papers.authors.map(lambda authors: author_id in authors)]
    counts = sorted((float(value) for value in portfolio.total_citation), reverse=True)
    fractional = sorted((float(row.total_citation)/len(row.authors)
                         for row in portfolio.itertuples(index=False)), reverse=True)
    h = max((k for k, value in enumerate(counts, 1) if value >= k), default=0)
    hf = max((k for k, value in enumerate(fractional, 1) if value >= k), default=0)
    total, g = 0., 0
    for k, value in enumerate(counts, 1):
        total += value
        if total >= k*k:
            g = k
    return {'raw_total_cites': sum(counts), 'h_index': h, 'hf_index': hf, 'g_index': g}


@lru_cache(maxsize=4)
def _baseline_reference(frozen):
    reference = frozen.snapshot('percentile_reference')
    lookup = {}
    for metric in SUPPORTED_BASELINES:
        subset = reference.loc[reference.metric.eq(metric)]
        digest = sha256('\n'.join(sorted(subset.author_id.dropna().astype(str))).encode('utf-8')).hexdigest()
        numeric = pd.to_numeric(subset.value, errors='coerce')
        lookup[metric] = (np.sort(numeric.to_numpy(dtype=float))
            if len(subset) == frozen.original_author_count and
               not subset.author_id.isna().any() and not subset.author_id.duplicated().any() and
               numeric.notna().all() and np.isfinite(numeric).all() and
               digest == frozen.original_author_digest else None)
    return lookup


def _baseline_rows(author_id, scenario, original_papers, changed_papers, frozen):
    reference = _baseline_reference(frozen)
    original = _baseline_scores(author_id, original_papers)
    changed = _baseline_scores(author_id, changed_papers)
    rows = []
    for metric in SUPPORTED_BASELINES:
        distribution = reference[metric]
        if distribution is None:
            rows.append(dict(author_id=author_id, scenario=scenario, metric=metric,
                             status='DATA_REQUIRED', reason='Original full baseline reference unavailable'))
            continue
        before = _percentile(original[metric], distribution, presorted=True)
        after = _percentile(changed[metric], distribution, presorted=True)
        inflation = percentile_inflation(before, after)
        rows.append(dict(author_id=author_id, scenario=scenario, metric=metric,
                         original_value=original[metric], manipulated_value=changed[metric],
                         original_percentile=before, manipulated_percentile=after,
                         inflation_percent=inflation['inflation_percent'],
                         status=inflation['status'], reason=inflation['reason']))
    for metric in ('hm_index', 'c_score_raw'):
        rows.append(dict(author_id=author_id, scenario=scenario, metric=metric,
                         status='METHODOLOGY_UNSPECIFIED',
                         reason='No source-approved complete baseline calculation'))
    return rows


def run_author_graph(author_id, graph, frozen, parameters):
    """Recalculate original and each feasible scenario; never mutate source frames."""
    if not isinstance(graph, AuthorGraphInput) or not isinstance(parameters, NMParameters):
        raise TypeError('AuthorGraphInput and NMParameters required')
    original_papers = graph.papers.copy(deep=True)
    original_edges = graph.edges.copy(deep=True)
    original = calculate_nm(author_id, original_papers, original_edges, frozen,
                            career_start_year=graph.career_start_year, parameters=parameters)
    target_ids = [row.pub_id for row in original_papers.itertuples(index=False)
                  if author_id in row.authors]
    scenario_rows, baseline_rows = [], []
    for scenario in SCENARIOS:
        try:
            if scenario == SCENARIOS[0]:
                if (graph.self_additions is None or graph.original_self_citation_count is None
                        or graph.relevant_core_authors is None):
                    raise MethodologyInputRequired('Explicit added citing papers, original self-citation count and core authors required')
                changed_papers, changed_edges = add_self_citation_relationships(
                    original_papers, original_edges, graph.self_additions,
                    target_author=author_id, relevant_core_authors=graph.relevant_core_authors,
                    original_self_citation_count=graph.original_self_citation_count)
            elif scenario == SCENARIOS[1]:
                if graph.salami_assignments is None:
                    raise MethodologyInputRequired('Explicit incoming and outgoing citation-half assignments required')
                changed_papers, changed_edges = split_salami_papers(
                    original_papers, original_edges, graph.salami_assignments,
                    target_pub_ids=target_ids)
            else:
                if graph.gift_assignments is None:
                    raise MethodologyInputRequired('Explicit existing coauthor papers and middle positions required')
                changed_papers = add_gift_authorship(
                    original_papers, graph.gift_assignments,
                    target_author=author_id, target_portfolio_ids=target_ids)
                changed_edges = original_edges.copy(deep=True)
            changed = calculate_nm(author_id, changed_papers, changed_edges, frozen,
                                   career_start_year=graph.career_start_year, parameters=parameters,
                                   counterfactual=True)
            inflation = percentile_inflation(original['nm_percentile'], changed['nm_percentile'])
            scenario_rows.append(dict(author_id=author_id, scenario=scenario,
                original_nm_index=original['nm_index'], manipulated_nm_index=changed['nm_index'],
                original_nm_percentile=original['nm_percentile'],
                manipulated_nm_percentile=changed['nm_percentile'],
                nm_inflation_percent=inflation['inflation_percent'],
                benchmark_version=frozen.version, benchmark_sha256=frozen.sha256,
                original_paper_count=len(target_ids),
                manipulated_paper_count=sum(author_id in authors for authors in changed_papers.authors),
                original_edge_count=len(original_edges), manipulated_edge_count=len(changed_edges),
                status=inflation['status'], exclusion_reason=inflation['reason']))
            baseline_rows.extend(_baseline_rows(author_id, scenario, original_papers,
                                                changed_papers, frozen))
        except MethodologyInputRequired as error:
            scenario_rows.append(dict(author_id=author_id, scenario=scenario,
                original_nm_index=original['nm_index'], original_nm_percentile=original['nm_percentile'],
                manipulated_nm_index=float('nan'), manipulated_nm_percentile=float('nan'),
                nm_inflation_percent=float('nan'), benchmark_version=frozen.version,
                benchmark_sha256=frozen.sha256, status='INPUT_DATA_REQUIRED',
                exclusion_reason=str(error)))
    return pd.DataFrame(scenario_rows), pd.DataFrame(baseline_rows)
