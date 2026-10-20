"""Independent, in-memory NM calculation from complete citation relationships.

Implements the latest manuscript's Equations 1--27 for a single author. Every
field reference is read from an immutable original-population snapshot. This
module neither imports the production calculator nor opens a database.
"""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from math import isclose, isfinite, log10

import numpy as np
import pandas as pd
from scipy.stats import norm

from analysis.counterfactual import FrozenBenchmarks, MethodologyInputRequired


COMPONENTS = ('t', 's', 'u', 'hf', 'hm', 'g')


@dataclass(frozen=True)
class NMParameters:
    as_of_year: int
    epsilon_0: float = .90
    career_boost: float = 1.25
    career_decay: float = .0601
    weights: tuple[float, ...] = (1/6,) * 6

    def __post_init__(self):
        if (not isinstance(self.as_of_year, int) or not 1900 <= self.as_of_year <= 3000
                or not 0 <= self.epsilon_0 <= 1 or self.career_boost < 1
                or not 0 <= self.career_decay <= 1 or len(self.weights) != 6
                or any(not isfinite(x) or x < 0 for x in self.weights)
                or not isclose(sum(self.weights), 1, abs_tol=1e-9)):
            raise ValueError('Invalid explicit NM calculation parameters')


def _shares(paper):
    """Per-author fractions before multiplication by a paper's field weight."""
    authors = tuple(paper.authors)
    if not authors or len(set(authors)) != len(authors):
        raise MethodologyInputRequired('Complete unique ordered authors required')
    mode = paper.contribution_mode
    if mode == 'uniform':
        values = [1/len(authors)] * len(authors)  # Equation 1
    elif mode == 'relative':
        first_values = getattr(paper, 'first_positions', ())
        last_values = getattr(paper, 'last_positions', ())
        first = set(first_values) if isinstance(first_values, (tuple, list, set)) else set()
        last = set(last_values) if isinstance(last_values, (tuple, list, set)) else set()
        positions = set(range(1, len(authors)+1))
        if first & last or not (first | last) <= positions:
            raise MethodologyInputRequired('Invalid first/last author positions')
        effective = [sum(first)/len(first) if i in first else
                     sum(last)/len(last) if i in last else i
                     for i in range(1, len(authors)+1)]
        harmonic = [1/x for x in effective]
        values = [x/sum(harmonic) for x in harmonic]  # Equations 2--3
    elif mode == 'aci':
        supplied = getattr(paper, 'aci_shares', None)
        if not isinstance(supplied, dict) or set(supplied) != set(authors):
            raise MethodologyInputRequired('Complete ACI fractions required for every author')
        values = [supplied[a] for a in authors]  # Equation 4
    elif mode == 'credit':
        roles = getattr(paper, 'credit_roles', None)
        role_weights = getattr(paper, 'credit_role_weights', None)
        if not isinstance(roles, dict) or set(roles) != set(authors) or not isinstance(role_weights, dict):
            raise MethodologyInputRequired('Complete CRediT roles and field weights required')
        if any(role not in role_weights for author in authors for role in roles[author]):
            raise MethodologyInputRequired('Missing CRediT role weight')
        scores = [sum(role_weights[role] for role in roles[a]) for a in authors]
        if any(not isfinite(x) or x < 0 for x in scores) or sum(scores) <= 0:
            raise MethodologyInputRequired('Invalid CRediT scores')
        values = [x/sum(scores) for x in scores]  # Equation 5
    else:
        raise MethodologyInputRequired('Paper contribution mode must be uniform, relative, aci, or credit')
    if any(not isinstance(x, (int, float)) or not isfinite(x) or x < 0 for x in values) or not isclose(sum(values), 1, abs_tol=1e-8):
        raise MethodologyInputRequired('Author contribution fractions must be nonnegative and sum to one')
    return dict(zip(authors, values))


@lru_cache(maxsize=4)
def _reference_lookup(frozen):
    if not isinstance(frozen, FrozenBenchmarks):
        raise MethodologyInputRequired('Original immutable benchmark object required')
    year = frozen.snapshot('field_year_means')
    caps = frozen.snapshot('field_caps')
    zmeans = frozen.snapshot('z_means')
    zsds = frozen.snapshot('z_standard_deviations')
    values = frozen.snapshot('percentile_reference')
    expected = ((year, {'field', 'year', 'mean_adjusted_citations', 'field_mean_adjusted_citations'}),
                (caps, {'field', 'cap', 'hf_reference', 'hm_reference', 'g_reference'}),
                (zmeans, {'metric', 'mean', 'distribution'}),
                (zsds, {'metric', 'sd'}),
                (values, {'author_id', 'metric', 'value'}))
    for frame, columns in expected:
        if not columns <= set(frame):
            raise MethodologyInputRequired(f'Frozen reference missing {sorted(columns-set(frame))}')
    if year.duplicated(['field', 'year']).any() or caps.field.duplicated().any():
        raise MethodologyInputRequired('Frozen field benchmarks contain duplicate keys')
    for field, rows in year.groupby('field'):
        if pd.to_numeric(rows.field_mean_adjusted_citations, errors='coerce').nunique() != 1:
            raise MethodologyInputRequired(f'Frozen field-wide mean inconsistent across years: {field}')
    if zmeans.metric.duplicated().any() or zsds.metric.duplicated().any():
        raise MethodologyInputRequired('Frozen normalization contains duplicate metric keys')
    if values.duplicated(['author_id', 'metric']).any():
        raise MethodologyInputRequired('Frozen percentile reference contains duplicate authors per metric')
    reference_ids = set(values.loc[values.metric.eq('nm_index'), 'author_id'].astype(str))
    if sha256('\n'.join(sorted(reference_ids)).encode('utf-8')).hexdigest() != frozen.original_author_digest:
        raise MethodologyInputRequired('Percentile reference author IDs do not match frozen population')
    for metric in (*COMPONENTS, 'nm_index'):
        subset = values.loc[values.metric.eq(metric)]
        numeric = pd.to_numeric(subset.value, errors='coerce')
        if len(subset) != frozen.original_author_count or numeric.isna().any() or not np.isfinite(numeric).all():
            raise MethodologyInputRequired(f'Original full-population percentile distribution missing: {metric}')
        if set(subset.author_id.astype(str)) != reference_ids:
            raise MethodologyInputRequired('Frozen metric distributions have inconsistent author IDs')
    distributions = {metric: np.sort(pd.to_numeric(
        values.loc[values.metric.eq(metric), 'value']).to_numpy(dtype=float))
        for metric in (*COMPONENTS, 'nm_index')}
    return year.set_index(['field', 'year']), caps.set_index('field'), zmeans.set_index('metric'), zsds.set_index('metric'), distributions


def _percentile(value, reference, *, presorted=False):
    """Empirical percentage rank against the original distribution, average ties."""
    data = np.asarray(reference, dtype=float)
    if not np.isfinite(data).all() or not isfinite(value):
        raise MethodologyInputRequired('Finite, complete original percentile distribution required')
    if not presorted:
        data = np.sort(data)
    below = int(np.searchsorted(data, value, side='left'))
    tied = int(np.searchsorted(data, value, side='right'))-below
    return 100 * (below + (tied+1)/2 if tied else below) / len(data)


def _blom_percentile(value, sorted_reference):
    """Equation 24--26 Blom plotting position with average ranks for ties.

    A counterfactual value absent from the frozen reference takes its insertion
    rank, clipped to the original 1..N positions; the reference is not changed.
    """
    data = np.asarray(sorted_reference, dtype=float)
    if not len(data) or not np.isfinite(data).all() or not isfinite(value):
        raise MethodologyInputRequired('Finite frozen component distribution required')
    below = int(np.searchsorted(data, value, side='left'))
    tied = int(np.searchsorted(data, value, side='right'))-below
    rank = below+(tied+1)/2 if tied else min(max(below+1, 1), len(data))
    return 100*(rank-.375)/(len(data)+.25)


def _component_percentile(metric, raw, zmeans, zsds, distributions):
    reference = distributions[metric]
    if metric in {'t', 's', 'u'}:
        if metric not in zmeans.index or metric not in zsds.index:
            raise MethodologyInputRequired(f'Frozen Z-normalization missing: {metric}')
        branch = zmeans.at[metric, 'distribution']
        if branch == 'lognormal':
            mean, sd = float(zmeans.at[metric, 'mean']), float(zsds.at[metric, 'sd'])
            if raw < 0 or not isfinite(mean) or not isfinite(sd) or sd <= 0:
                raise MethodologyInputRequired('Invalid lognormal raw score or original SD')
            return 100*norm.cdf((log10(raw+1)-mean)/sd)
        if branch != 'hooked_power_law':
            raise MethodologyInputRequired('Original distribution branch must be explicitly supplied')
    return _blom_percentile(raw, reference)


def calculate_nm(author_id, papers, edges, frozen, *, career_start_year, parameters,
                 counterfactual=False):
    """Return six fresh components, their frozen-reference percentiles and NM.

    Canonical paper rows require: pub_id, ordered authors, year, field_weights
    (dict summing to one), contribution_mode, total_citation, and mode-specific
    contribution inputs. Citation rows require unique citation_id, cited_pub_id,
    citing_pub_id; all citing papers must be present with full authorship.
    """
    if not isinstance(parameters, NMParameters):
        raise TypeError('NMParameters required')
    required_papers = {'pub_id', 'authors', 'year', 'field_weights', 'contribution_mode', 'total_citation'}
    required_edges = {'citation_id', 'cited_pub_id', 'citing_pub_id'}
    if not required_papers <= set(papers) or not required_edges <= set(edges):
        raise MethodologyInputRequired('Complete canonical paper and citation-edge columns required')
    if papers.pub_id.isna().any() or papers.pub_id.duplicated().any() or edges.citation_id.isna().any() or edges.citation_id.duplicated().any():
        raise MethodologyInputRequired('Unique non-null paper and citation IDs required')
    by_id = {row.pub_id: row for row in papers.itertuples(index=False)}
    shares = {}
    for row in by_id.values():
        shares[row.pub_id] = _shares(row)
        fields = row.field_weights
        if (not isinstance(fields, dict) or not fields or any(not isfinite(v) or v < 0 for v in fields.values())
                or not isclose(sum(fields.values()), 1, abs_tol=1e-8)):
            raise MethodologyInputRequired('Complete normalized paper field weights required')
        if (not isinstance(row.year, int) or row.year > parameters.as_of_year
                or not isinstance(row.total_citation, (int, float)) or not isfinite(row.total_citation)
                or row.total_citation < 0):
            raise MethodologyInputRequired('Valid publication year and citation total required')
    if not set(edges.cited_pub_id) <= set(by_id) or not set(edges.citing_pub_id) <= set(by_id):
        raise MethodologyInputRequired('Every cited and citing paper must have complete metadata')
    portfolio = [row for row in by_id.values() if author_id in row.authors]
    if (not portfolio or not isinstance(career_start_year, int)
            or (not counterfactual and career_start_year > min(row.year for row in portfolio))
            or career_start_year > parameters.as_of_year):
        raise MethodologyInputRequired('Original author career start and complete portfolio required')
    t = parameters.as_of_year-career_start_year
    career_factor = parameters.career_boost*(t+1)**(-parameters.career_decay)  # Equation 10
    year_ref, field_ref, zmeans, zsds, distributions = _reference_lookup(frozen)
    grouped = {pid: frame for pid, frame in edges.groupby('cited_pub_id')}
    field_rows = []
    for paper in portfolio:
        citing = grouped.get(paper.pub_id, edges.iloc[0:0])
        if len(citing) != paper.total_citation:
            raise MethodologyInputRequired(f'Citation edges do not equal raw count for {paper.pub_id}')
        age = parameters.as_of_year-paper.year
        if age <= 0:
            raise MethodologyInputRequired('Equation 14 publication age is zero; as-of convention required')
        for field, field_weight in paper.field_weights.items():
            if field_weight == 0:
                continue
            if (field, paper.year) not in year_ref.index or field not in field_ref.index:
                raise MethodologyInputRequired(f'Original field/year benchmark missing for {field}/{paper.year}')
            adjusted = 0.
            for edge in citing.itertuples(index=False):
                q = by_id[edge.citing_pub_id]
                if field not in q.field_weights or q.field_weights[field] <= 0:
                    raise MethodologyInputRequired('Citing-paper field contribution unavailable for ISC')
                q_weights = {a: w*q.field_weights[field] for a, w in shares[q.pub_id].items()}
                overlap = set(paper.authors) & set(q.authors)
                self_weight = q_weights.get(author_id, 0.)
                core = overlap-{author_id}
                core_weight = sum(q_weights[a] for a in core)
                other_weight = sum(w for a, w in q_weights.items() if a not in overlap)
                denominator = self_weight+len(core)*core_weight+other_weight
                if denominator <= 0:
                    raise MethodologyInputRequired('ISC denominator is zero')
                isc = (self_weight+parameters.epsilon_0*len(core)*core_weight)/denominator  # Equation 7
                if not 0 <= isc <= 1+1e-9:
                    raise MethodologyInputRequired('ISC is outside [0,1]')
                adjusted += 1-min(1., isc)  # Equations 8--9; one unit per edge
            mean_year = float(year_ref.at[(field, paper.year), 'mean_adjusted_citations'])
            mean_field = float(year_ref.at[(field, paper.year), 'field_mean_adjusted_citations'])
            cap = float(field_ref.at[field, 'cap'])
            if min(mean_year, mean_field) <= 0 or cap < 0:
                raise MethodologyInputRequired('Invalid original mean or cap')
            weight = field_weight*shares[paper.pub_id][author_id]
            capped = min(adjusted, cap)  # Equation 12
            field_rows.append(dict(field=field, field_weight=field_weight, weight=weight,
                                   adjusted=adjusted, capped=capped, mean_year=mean_year,
                                   mean_field=mean_field, age=age,
                                   effective=career_factor*weight*capped))
    n_papers = len(portfolio)
    raw = {
        't': career_factor*sum(r['weight']*r['adjusted']/r['mean_year'] for r in field_rows),
        's': career_factor*sum(r['weight']*r['capped']/r['mean_field'] for r in field_rows)/n_papers,
        'u': career_factor*sum(r['weight']*r['capped']/(r['age']*r['mean_year']) for r in field_rows),
    }  # Equations 11, 13, 14
    for metric in ('hf', 'hm', 'g'):
        weighted = 0.
        for field in {r['field'] for r in field_rows}:
            rows = sorted((r for r in field_rows if r['field'] == field),
                          key=lambda r: r['effective'], reverse=True)
            effective = [r['effective'] for r in rows]
            if metric == 'hf':
                field_score = max((k for k, value in enumerate(effective, 1) if value >= k), default=0)
            elif metric == 'hm':
                cumulative_rank, field_score = 0., 0.
                for row in rows:
                    cumulative_rank += career_factor*row['weight']  # Equation 18
                    if row['effective'] >= cumulative_rank:
                        field_score = cumulative_rank
            else:
                cumulative_cites, field_score = 0., 0
                for k, value in enumerate(effective, 1):
                    cumulative_cites += value  # Equation 21
                    if cumulative_cites >= k*k:
                        field_score = k
            denominator = float(field_ref.at[field, f'{metric}_reference'])
            if denominator <= 0:
                raise MethodologyInputRequired(f'Original {metric} field reference must be positive')
            weighted += sum(r['field_weight'] for r in rows)*field_score/denominator
        raw[metric] = weighted/n_papers  # Equations 17, 20, 23
    percentiles = {metric: _component_percentile(metric, raw[metric], zmeans, zsds, distributions)
                   for metric in COMPONENTS}
    score = sum(w*percentiles[metric] for w, metric in zip(parameters.weights, COMPONENTS))
    return {'author_id': author_id, 'career_factor': career_factor, 'raw_components': raw,
            'component_percentiles': percentiles, 'nm_index': score,
            'nm_percentile': _percentile(score, distributions['nm_index'], presorted=True),
            'benchmark_version': frozen.version, 'benchmark_sha256': frozen.sha256}
