"""TEST DATA ONLY — deterministic, invented records for offline software testing."""

import pandas as pd

from analysis.counterfactual import FrozenBenchmarks
from analysis.rq07_engine import AuthorGraphInput
from analysis.fairness import FairnessConvention
from nm_index.counterfactual_calculator import NMParameters
from nm_index.loader import COMPONENT_COLUMNS
from src.repository import Extracts


LABEL = 'SYNTHETIC TEST DATA — NOT EMPIRICAL RESULTS'


def _rq07_graph_fixture(ids):
    """Complete, isolated TEST-only graphs and a frozen mock reference."""
    graph_inputs = {}
    for i, author in enumerate(ids):
        core, other = f'TEST_CORE_{i}', f'TEST_OTHER_{i}'
        papers, edges, additions, halves = [], [], [], []
        def paper(pid, authors, year, count):
            return dict(pub_id=pid, authors=tuple(authors), year=year, field='TEST_FIELD',
                        field_weights={'TEST_FIELD': 1.}, contribution_mode='uniform',
                        total_citation=count)
        for j in range(10):
            pid = f'TEST_RQ7_P{i}_{j}'
            papers.append(paper(pid, (author, core), 2020, 2))
            for half in (1, 2):
                qid, eid = f'TEST_RQ7_Q{i}_{j}_{half}', f'TEST_RQ7_E{i}_{j}_{half}'
                papers.append(paper(qid, (core, other), 2021, 0))
                edges.append(dict(citation_id=eid, cited_pub_id=pid, citing_pub_id=qid))
                halves.append(dict(citation_id=eid, half=half))
            new_id = f'TEST_RQ7_NEW{i}_{j}'
            additions.append(dict(**paper(new_id, (author, core, other), 2021, 0),
                                  citation_id=f'TEST_RQ7_NEWEDGE{i}_{j}', cited_pub_id=pid))
        for j in range(3):
            gid = f'TEST_RQ7_G{i}_{j}'
            papers.append(paper(gid, (core, other, f'TEST_D_{i}'), 2019, 2))
            for k in (1, 2):
                rid = f'TEST_RQ7_R{i}_{j}_{k}'
                papers.append(paper(rid, (f'TEST_X_{i}',), 2021, 0))
                edges.append(dict(citation_id=f'TEST_RQ7_GE{i}_{j}_{k}',
                                  cited_pub_id=gid, citing_pub_id=rid))
        graph_inputs[author] = AuthorGraphInput(
            papers=pd.DataFrame(papers), edges=pd.DataFrame(edges),
            career_start_year=2020, self_additions=pd.DataFrame(additions),
            original_self_citation_count=20,
            relevant_core_authors=frozenset({core}),
            salami_assignments=pd.DataFrame(halves),
            gift_assignments=pd.DataFrame([
                dict(pub_id=f'TEST_RQ7_G{i}_{j}', position=2) for j in range(3)]))
    reference = pd.DataFrame([
        dict(author_id=author, metric=metric, value=float((i+1)*8))
        for metric in ('t', 's', 'u', 'hf', 'hm', 'g', 'nm_index',
                       'raw_total_cites', 'h_index', 'hf_index', 'g_index')
        for i, author in enumerate(ids)])
    tables = {
        'field_year_means': pd.DataFrame([
            dict(field='TEST_FIELD', year=year, mean_adjusted_citations=2.,
                 field_mean_adjusted_citations=2.) for year in (2019, 2020, 2021)]),
        'field_caps': pd.DataFrame([dict(field='TEST_FIELD', cap=20.,
            hf_reference=1., hm_reference=1., g_reference=1.)]),
        'z_means': pd.DataFrame([dict(metric=metric, mean=.5,
                                    distribution='lognormal') for metric in ('t','s','u')]),
        'z_standard_deviations': pd.DataFrame([dict(metric=metric, sd=.5)
                                              for metric in ('t','s','u')]),
        'percentile_reference': reference,
    }
    frozen = FrozenBenchmarks.from_original(ids, tables,
        version='SYNTHETIC_TEST_REFERENCE_ONLY', synthetic=True)
    return graph_inputs, frozen, NMParameters(as_of_year=2025)


def make_fixture():
    """Return synthetic database-shaped extracts and independently labelled inputs."""
    ids = [f'TEST_A{i:02d}' for i in range(12)]
    graph_inputs, frozen_benchmarks, nm_parameters = _rq07_graph_fixture(ids)
    authors = pd.DataFrame([dict(author_id=author, author_name=f'Synthetic Author {i}')
                            for i, author in enumerate(ids)])
    publications, authorship, citations, fields, paper_inputs = [], [], [], [], []
    for i, author in enumerate(ids):
        for j in range(5):
            pub = f'TEST_P{i:02d}_{j}'
            count = 0 if j == 0 and i % 3 == 0 else (i + 2) * (j + 1) + (20 if i == 11 and j == 4 else 0)
            year = 2010 + j + (i % 5)
            coauthor = ids[(i + 1) % len(ids)]
            publications.append(dict(pub_id=pub, year=year, total_citation=count, source='TEST DATA ONLY'))
            authorship.append(dict(pub_id=pub, author1id=author, author1id_weight=0.65,
                                   author2id=coauthor, author2id_weight=0.35))
            fields.append(dict(pub_id=pub, field_id=f'TEST_FIELD_{i % 3}'))
            paper_inputs.append(dict(author_id=author, total_citation=count,
                                     self_citation_count=min(count, j % 3), coauthor_count=2))
            if count:
                citations.append(dict(pub_id=pub, cites_pub_id=f'TEST_CITING_{i}_{j}'))
    nm_rows = []
    components = []
    for i, author in enumerate(ids):
        nm_rows.append(dict(author_id=author, nm_index=12.0 + i * 5.3 + (i % 3),
                            metrics_available=6, calculated_at=None,
                            **{name: float(10 + (i * (k + 3) + i * i * (k % 3 + 1)) % 81)
                               for k, name in enumerate(COMPONENT_COLUMNS)}))
        components.append(dict(author_id=author, **{
            name: float((i + 1) ** (1 + (k % 3) / 3) + (i * (k + 1)) % 7 + k)
            for k, name in enumerate(('nm_raw_t', 'nm_raw_s', 'nm_raw_u',
                                      'nm_raw_hf', 'nm_raw_hm', 'nm_raw_g'))}))
    extracts = Extracts(authors, pd.DataFrame(publications), pd.DataFrame(citations),
                        pd.DataFrame(authorship), pd.DataFrame(fields),
                        pd.DataFrame(nm_rows), pd.DataFrame(components))
    verification = pd.DataFrame([dict(author_id=author, portfolio_verified=True,
                                      evidence_reference='TEST DATA ONLY: fixture has five declared papers')
                                 for author in ids])
    awards = pd.DataFrame([dict(author_id=author, awardee=int(i >= 8)) for i, author in enumerate(ids)])
    annual = pd.DataFrame([dict(author_id=author, year=year, nm_index=10 + i * 4 + (year - 2020) * (i % 3 + 1),
                                h_index=2 + i // 3 + year - 2020,
                                hf_index=1 + i // 4 + year - 2020,
                                raw_total_cites=20 + i * 10 + (year - 2020) * 5,
                                g_index=3 + i // 2 + year - 2020,
                                publication_count=5 + year - 2020)
                           for i, author in enumerate(ids) for year in (2020, 2021)])
    history = annual.loc[annual.year == 2020, ['author_id', 'nm_index', 'h_index',
                                                'raw_total_cites', 'g_index']].copy()
    history['score_year'] = 2020
    future = pd.DataFrame([dict(author_id=author, outcome_start_year=2021, outcome_end_year=2025,
                                future_citations=15 + i * 4, future_awards=int(i >= 8),
                                h_index_growth=1 + i % 5)
                           for i, author in enumerate(ids)])
    scenario = pd.DataFrame([dict(author_id=author, career_years=4 + i * 4,
                                  main_domain_percentage=38 + i * 5,
                                  isc_scenario=['No overlapping authors', 'High single and unique author'][i % 2],
                                  ordering_norm=['Alphabetical/random ordering', 'Relative contribution ordering'][i % 2],
                                  isc_share=(i % 4) / 10,
                                  high_relative_contribution=bool(i % 2),
                                  low_influential_self_citation=bool(i % 3),
                                  field_name='Computer networks and communication')
                             for i, author in enumerate(ids)])
    subgroup = pd.DataFrame([dict(author_id=author, gender='Male' if i % 2 else 'Female',
                                  region=['North America', 'Europe', 'Asia', 'Other'][i % 4],
                                  approved_for_analysis=True,
                                  evidence_reference='TEST DATA ONLY: invented fixture labels')
                             for i, author in enumerate(ids)])
    percentiles = pd.DataFrame([dict(author_id=author,
        nm_index_percentile=15 + i * 5, h_index_percentile=12 + i * 4,
        raw_total_cites_percentile=10 + i * 5, g_index_percentile=11 + i * 5)
        for i, author in enumerate(ids)])
    reference_scores = pd.DataFrame([dict(author_id=author,
        nm_index=nm_rows[i]['nm_index'], c_score_raw=float(i*3+2),
        raw_total_cites=float(sum(p['total_citation'] for p in publications
                                  if p['pub_id'].startswith(f'TEST_P{i:02d}_'))),
        h_index=float(min(5, i//2+1)), hf_index=float(min(5, i//3+1)),
        g_index=float(min(5, i//2+1)),
        middle_author_share=i/11, career_stage=('Early' if i < 3 else
            'Mid-Early' if i < 6 else 'Mid-Late' if i < 9 else 'Senior'),
        reference_version='TEST_ONLY_FROZEN_REFERENCE',
        evidence_reference='TEST DATA ONLY: invented complete reference')
        for i, author in enumerate(ids)])
    award_events = pd.DataFrame([dict(author_id=author,
        award_category='Turing Award', evidence_reference='TEST DATA ONLY: invented award')
        for author in awards.loc[awards.awardee.astype(bool), 'author_id']])
    extra = dict(portfolio_verification=verification, award_labels=awards,
                 award_events=award_events,
                 award_inference_convention='welch_two_sided_pooled_d',
                 award_inference_reference='TEST DATA ONLY: software exercise',
                 graph_inputs=graph_inputs, frozen_benchmarks=frozen_benchmarks,
                 nm_parameters=nm_parameters,
                 reference_scores=reference_scores,
                 annual_scores=annual, representative_author=ids[0], first_year=2020,
                 trajectory_normalization='within_author_max',
                 trajectory_decision_reference='TEST DATA ONLY: synthetic normalization choice',
                 historical_scores=history, future_outcomes=future, score_year=2020,
                 scenario_data=scenario, predictors=('isc_share',),
                 paper_inputs=pd.DataFrame(paper_inputs), subgroup_labels=subgroup,
                 gaming_fractional_policy='preserve_fractional_counts',
                 gaming_decision_reference='TEST DATA ONLY: fractional citation convention',
                 percentile_scores=percentiles,
                 fairness_convention=FairnessConvention('pooled_sample_sd', 1,
                     'TEST DATA ONLY: synthetic convention for software exercise'),
                 pca_preprocessing='complete_case_z_standardization',
                 pca_decision_reference='TEST DATA ONLY: synthetic PCA software exercise',
                 group_column='gender')
    return extracts, extra


def edge_case_records():
    """TEST DATA ONLY: separate missing, zero, tie and orphan-link fixtures."""
    authors = [{'author_id': f'TEST_{name}'} for name in ('EMPTY', 'ZERO', 'TIED', 'MISSING')]
    publications = [
        {'pub_id': 'TEST_ZERO_P', 'year': 2020, 'total_citation': 0},
        {'pub_id': 'TEST_TIE_P1', 'year': 2021, 'total_citation': 4},
        {'pub_id': 'TEST_TIE_P2', 'year': 2021, 'total_citation': 4},
        {'pub_id': 'TEST_MISSING_P', 'year': None, 'total_citation': None},
    ]
    authorship = [
        {'pub_id': 'TEST_ZERO_P', 'author1id': 'TEST_ZERO'},
        {'pub_id': 'TEST_TIE_P1', 'author1id': 'TEST_TIED'},
        {'pub_id': 'TEST_TIE_P2', 'author1id': 'TEST_TIED'},
        {'pub_id': 'TEST_MISSING_P', 'author1id': 'TEST_MISSING'},
    ]
    return authors, publications, authorship
