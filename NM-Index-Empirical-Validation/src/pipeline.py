"""Future-run orchestration; imports no production modules and writes only local files."""

import hashlib
import importlib
import importlib.metadata
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis.descriptive import describe
from metrics.inputs import prepare_data
from metrics import total_cites, h_index, hf_index, g_index
from nm_index.loader import load as load_nm
from .config import PROJECT_ROOT, SQLiteConfig, load_config, load_validation_config
from .data_quality import check, to_markdown
from .database_first import inspect_mapped_extracts, resolve_real_inputs
from .eligibility import EligibilityRules
from .metric_registry import REGISTRY
from .provenance import metric_provenance
from .repository import Extracts, load_all, verify_schema
from .validation_dataset import build, BASELINE_COLUMNS


EXPERIMENT_MODULES = {
    'rq01': 'experiments.rq01_correlation',
    'rq02': 'experiments.rq02_paired_comparison',
    'rq03': 'experiments.rq03_agreement',
    'rq04': 'experiments.rq04_discrimination',
    'rq05': 'experiments.rq05_unique_power',
    'rq06': 'experiments.rq06_temporal_evolution',
    'rq07': 'experiments.rq07_gaming_sensitivity',
    'rq08': 'experiments.rq08_predictive_validity',
    'rq09': 'experiments.rq09_temporal_stability',
    'rq10': 'experiments.rq10_pca',
    'rq11': 'experiments.rq11_fairness',
    'sensitivity': 'experiments.sensitivity',
}

DOCUMENTS = ('Pasted markdown(7).md', 'Nm Index novel model (1)(3).pdf')
_DATABASE_SOURCE_TOKEN = object()
EXTERNAL_REQUIREMENTS = {
    'rq01': ('reference_scores',),
    'rq03': ('icc_model',), 'rq04': ('award_labels', 'award_events',
                                 'reference_scores', 'award_inference_convention',
                                 'award_inference_reference'),
    'rq05': ('scenario_data',), 'rq06': ('annual_scores', 'representative_author',
                                     'trajectory_normalization', 'trajectory_decision_reference'),
    'rq07': ('graph_inputs', 'frozen_benchmarks', 'nm_parameters'),
    'rq08': ('historical_scores', 'future_outcomes', 'score_year'),
    'rq09': ('annual_scores', 'first_year'),
    'rq10': ('pca_preprocessing', 'pca_decision_reference'),
    'rq11': ('subgroup_labels', 'percentile_scores', 'fairness_convention'),
}


def source_hashes():
    return {name: hashlib.sha256((PROJECT_ROOT/'source_documents'/name).read_bytes()).hexdigest()
            for name in DOCUMENTS}


def code_hash():
    digest = hashlib.sha256()
    for path in sorted(PROJECT_ROOT.rglob('*.py')):
        if any(part in {'.venv', 'venv', '__pycache__'} for part in path.parts):
            continue
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def dry_run(experiment_names=()):
    load_config()  # Parse only; no network connection.
    config = load_validation_config()
    hashes = source_hashes()
    names = tuple(experiment_names) or tuple(EXPERIMENT_MODULES)
    for name in names:
        if name not in EXPERIMENT_MODULES:
            raise ValueError(f'Unknown experiment: {name}')
        importlib.import_module(EXPERIMENT_MODULES[name])
    return dict(status='DRY_RUN_OK', database_access=False, database_writes=False,
                files_written=False, experiments=names, methodology_pending=[
                    m.metric_name for m in REGISTRY if m.implementation_status == 'METHODOLOGY_PENDING'],
                source_sha256=hashes, random_seed=config.random_seed)


def _run_directory(output_root):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = Path(output_root)/('run_'+stamp)
    destination.mkdir(parents=True, exist_ok=False)
    return destination


def _write_csv(frame, path, classification=None):
    if path.exists():
        raise FileExistsError(path)
    output = frame.copy()
    if classification:
        output.insert(0, 'data_classification', classification)
    output.to_csv(path, index=False)


def _database_isolation(source_kind):
    if not source_kind.startswith('SELECT_ONLY_POSTGRESQL'):
        return 'NOT_APPLICABLE'
    if isinstance(load_config(), SQLiteConfig):
        return 'SQLITE FILE mode=ro, query_only, single read transaction'
    return 'REPEATABLE READ, READ ONLY'


def _database_engine(source_kind):
    """The SELECT_ONLY_POSTGRESQL* source labels name the guarded adapter, not the engine."""
    if not source_kind.startswith('SELECT_ONLY_POSTGRESQL'):
        return None
    return 'sqlite' if isinstance(load_config(), SQLiteConfig) else 'postgresql'


def run_from_extracts(extracts: Extracts, *, experiment_names=(), settings=None,
                      output_directory=None, allow_incomplete=False, extra_inputs=None,
                      generate_figures=True, metric_strategies=None,
                      source_kind='SUPPLIED_DATAFRAMES', _source_token=None,
                      excluded_publications=None):
                      database_candidates=None):
    """Mockable integration seam. Never connects to a database itself."""
    settings = settings or load_validation_config()
    names = tuple(experiment_names) or tuple(EXPERIMENT_MODULES)
    unknown = set(names)-set(EXPERIMENT_MODULES)
    if unknown:
        raise ValueError(f'Unknown experiments: {sorted(unknown)}')
    root = Path(output_directory or settings.output_directory).resolve()
    results_root = (PROJECT_ROOT/'results').resolve()
    if root != results_root and results_root not in root.parents:
        raise ValueError('Calculated outputs must remain inside results/')
    classification = ('SYNTHETIC TEST DATA — NOT EMPIRICAL RESULTS'
                      if source_kind == 'SYNTHETIC_TEST_DATA' else
                      'PILOT DATA — NOT FULL EMPIRICAL VALIDATION'
                      if source_kind in {'SUPPLIED_DATAFRAMES', 'SELECT_ONLY_POSTGRESQL_PILOT'} else
                      'REAL EMPIRICAL DATA — INTERPRET ONLY AFTER READINESS REVIEW')
    if source_kind not in {'SYNTHETIC_TEST_DATA', 'SUPPLIED_DATAFRAMES',
                           'SELECT_ONLY_POSTGRESQL', 'SELECT_ONLY_POSTGRESQL_PILOT',
                           'SELECT_ONLY_POSTGRESQL_COHORT'}:
        raise ValueError('Unknown data source classification')
    if source_kind.startswith('SELECT_ONLY_POSTGRESQL') and _source_token is not _DATABASE_SOURCE_TOKEN:
        raise ValueError('Database classification is reserved for the guarded database adapter')
    ids = extracts.authors.author_id.astype(str)
    if source_kind == 'SYNTHETIC_TEST_DATA' and not ids.str.startswith('TEST_').all():
        raise ValueError('Mock source contains an ID outside the TEST_ namespace')
    if source_kind != 'SYNTHETIC_TEST_DATA' and ids.str.startswith('TEST_').any():
        raise ValueError('TEST_ authors cannot enter non-synthetic validation results')
    source_decisions = []
    if source_kind.startswith('SELECT_ONLY_POSTGRESQL'):
        mapped_candidates, database_reasons = inspect_mapped_extracts(extracts, ids, names)
        extra_inputs, source_decisions = resolve_real_inputs(
            ids, names, extra_inputs,
            database_candidates if database_candidates is not None else mapped_candidates,
            database_reasons=database_reasons)
    destination = _run_directory(root)
    (destination/'DATA_CLASSIFICATION.txt').write_text(classification+'\n', encoding='utf-8')
    quality_report, links = check(extracts)
    _write_csv(quality_report, destination/'data_quality_report.csv', classification)
    (destination/'data_quality_report.md').write_text(
        f'# {classification}\n\n'+to_markdown(quality_report), encoding='utf-8')
    if excluded_publications is not None:
        _write_csv(excluded_publications, destination/'excluded_publications.csv', classification)
    # Missing/invalid years are not a run blocker: the design excludes the affected
    # *authors* ("incomplete metadata"), which require_complete_publication_metadata does below.
    blocker_names = {'duplicate_author_ids', 'duplicate_publication_ids',
                     'orphan_link_authors', 'orphan_link_publications',
                     'authors_without_linked_publications',
                     'publications_without_author_relationship',
                     'missing_or_non_numeric_citation_counts', 'negative_citation_counts',
                     'duplicate_nm_records', 'orphan_nm_records'}
    blockers = quality_report.loc[quality_report['check'].isin(blocker_names) & quality_report['count'].gt(0), 'check'].tolist()
    if blockers and not allow_incomplete:
        raise ValueError('Incomplete/invalid snapshot; quality report saved. Blockers: '+', '.join(blockers))

    prepared = prepare_data(extracts.authors.to_dict('records'),
                            extracts.publications.to_dict('records'),
                            extracts.authorship.to_dict('records'))
    # Snapshot link coverage cannot prove an author's complete career portfolio.
    # Accept only an explicit, independently sourced author-level attestation.
    verification = (extra_inputs or {}).get('portfolio_verification')
    if verification is not None:
        required = {'author_id', 'portfolio_verified', 'evidence_reference'}
        if not required <= set(verification):
            raise ValueError(f'Portfolio verification missing: {sorted(required-set(verification))}')
        if verification.author_id.isna().any() or verification.author_id.duplicated().any():
            raise ValueError('Portfolio verification requires unique non-NULL author IDs')
        if not verification.portfolio_verified.map(lambda value: type(value) is bool).all():
            raise ValueError('portfolio_verified must contain Boolean values')
        approved = verification.loc[
            verification.portfolio_verified & verification.evidence_reference.notna()
            & verification.evidence_reference.astype(str).str.strip().ne(''), 'author_id']
        prepared.quality['full_portfolio_verified'] = prepared.quality.author_id.isin(approved)
    linked_years = (links.drop_duplicates(['author_id','pub_id'])
                    .merge(extracts.publications[['pub_id','year']], on='pub_id', how='left'))
    year_bounds = linked_years.groupby('author_id').year.agg(['min','max']).rename(
        columns={'min':'observed_first_year', 'max':'observed_last_year'})
    prepared.quality = prepared.quality.merge(year_bounds, on='author_id', how='left')
    linked_years['year_numeric'] = pd.to_numeric(linked_years.year, errors='coerce')
    activity = linked_years.groupby('author_id').year_numeric.apply(
        lambda values: values.between(2000, 2024, inclusive='both').any())
    complete_years = linked_years.groupby('author_id').year_numeric.apply(
        lambda values: values.notna().all() and values.between(1000, 9999).all())
    complete_positions = links.groupby('author_id').position.apply(
        lambda values: values.notna().all() and values.between(1, 10).all())
    prepared.quality['active_2000_2024'] = prepared.quality.author_id.map(activity).fillna(False).astype(bool)
    prepared.quality['publication_metadata_complete'] = (
        prepared.quality.author_id.map(complete_years).fillna(False).astype(bool)
        & prepared.quality.author_id.map(complete_positions).fillna(False).astype(bool))
    metrics = {'raw_total_cites': total_cites.calculate(prepared),
               'h_index': h_index.calculate(prepared),
               'g_index': g_index.calculate(prepared)}
    if source_kind == 'SYNTHETIC_TEST_DATA':
        # The bundled fixture declares complete author lists. Database slots
        # do not prove full coauthor coverage, so no real hf is inferred.
        synthetic_papers = (links.drop_duplicates(['author_id', 'pub_id'])
            .merge(extracts.publications[['pub_id', 'total_citation']],
                   on='pub_id', how='left', validate='many_to_one'))
        synthetic_papers['coauthor_count'] = synthetic_papers.pub_id.map(
            links.drop_duplicates(['author_id', 'pub_id']).groupby('pub_id').size())
        metrics['hf_index'] = hf_index.calculate(synthetic_papers, verified_authorship=True)
    else:
        verified_counts = (extra_inputs or {}).get('coauthor_counts')
        if verified_counts is not None:
            required = {'pub_id', 'coauthor_count', 'verified_complete', 'evidence_reference'}
            if not required <= set(verified_counts):
                raise ValueError(f'coauthor_counts missing: {sorted(required-set(verified_counts))}')
            if verified_counts.pub_id.isna().any() or verified_counts.pub_id.duplicated().any():
                raise ValueError('coauthor_counts requires unique non-NULL pub_id values')
            supplied = verified_counts.copy()
            supplied['coauthor_count'] = pd.to_numeric(supplied.coauthor_count, errors='coerce')
            valid = (supplied.verified_complete.map(lambda value: type(value) is bool)
                     & supplied.verified_complete
                     & supplied.evidence_reference.notna()
                     & supplied.evidence_reference.astype(str).str.strip().ne('')
                     & supplied.coauthor_count.ge(1)
                     & supplied.coauthor_count.mod(1).eq(0))
            supplied.loc[~valid, 'coauthor_count'] = float('nan')
            papers = (links.drop_duplicates(['author_id', 'pub_id'])
                .merge(extracts.publications[['pub_id', 'total_citation']],
                       on='pub_id', how='left', validate='many_to_one')
                .merge(supplied[['pub_id', 'coauthor_count']], on='pub_id',
                       how='left', validate='many_to_one'))
            metrics['hf_index'] = hf_index.calculate(papers, verified_authorship=True)
    if metric_strategies:
        metrics.update(_apply_metric_strategies(extracts, links, metrics, metric_strategies))
    rules = EligibilityRules(min_publications=settings.min_publications,
                             min_raw_cites=settings.min_raw_cites,
                             min_metric_coverage=settings.min_metric_coverage,
                             require_verified_portfolio=True,
                             require_active_period=True,
                             require_complete_publication_metadata=True)
    dataset = build(extracts.authors, extracts.nm, metrics, prepared.quality, rules,
                    components=extracts.components)
    dataset['data_provenance'] = source_kind
    _write_csv(dataset, destination/'validation_dataset.csv', classification)
    _write_csv(metric_provenance(metric_strategies or {}), destination/'metric_provenance.csv', classification)
    descriptive = describe(dataset.loc[dataset.eligible_for_validation], ['nm_index', *BASELINE_COLUMNS])
    _write_csv(descriptive, destination/'descriptive_statistics.csv', classification)
    comparators = [name for name in BASELINE_COLUMNS if dataset.loc[dataset.eligible_for_validation, name].notna().any()]
    experiment_outputs = {}
    eligible = dataset.loc[dataset.eligible_for_validation].copy()
    for name in names:
        unavailable = [item for item in source_decisions if item.source == 'UNAVAILABLE'
                       and name in item.affected_rqs.split(';')]
        if unavailable:
            from experiments.common import pending
            output = pending('Required input unavailable: '+ '; '.join(
                f'{item.input_name}: {item.reason}' for item in unavailable), 'DATA_REQUIRED')
        elif eligible.empty and source_kind.startswith('SELECT_ONLY_POSTGRESQL'):
            from experiments.common import pending
            output = pending('No authors meet the verified input and eligibility gates', 'DATA_REQUIRED')
        else:
            module = importlib.import_module(EXPERIMENT_MODULES[name])
            output = module.run(eligible, comparators, seed=settings.random_seed,
                                data_source_kind=source_kind, **(extra_inputs or {}))
        experiment_outputs[name] = output
        for title, frame in output.items():
            filename = f'{name}_status.csv' if title == 'status' else f'{title}.csv'
            _write_csv(frame, destination/filename, classification)
    eligibility_rows = []
    for name in names:
        absent = [key for key in EXTERNAL_REQUIREMENTS.get(name, ())
                  if (extra_inputs or {}).get(key) is None]
        method_keys = {'icc_model', 'fairness_convention', 'pca_preprocessing',
                       'pca_decision_reference', 'trajectory_normalization',
                       'trajectory_decision_reference', 'gaming_fractional_policy',
                       'gaming_decision_reference', 'award_inference_convention',
                       'award_inference_reference'}
        absent_status = ('METHODOLOGY_PENDING' if absent and set(absent) <= method_keys
                         else 'DATA_REQUIRED' if absent else 'SUPPLIED')
        experiment_status = _experiment_status(experiment_outputs[name])
        matched = set(dataset.loc[dataset.eligible_for_validation, 'author_id'])
        for key in EXTERNAL_REQUIREMENTS.get(name, ()):
            source = (extra_inputs or {}).get(key)
            if isinstance(source, pd.DataFrame) and 'author_id' in source:
                matched.intersection_update(source.author_id.dropna())
        for reason, count in dataset.eligibility_reason.value_counts(dropna=False).items():
            eligibility_rows.append(dict(experiment=name, eligibility_reason=reason,
                                         authors=int(count),
                                         cohort_eligible_authors=int(dataset.eligible_for_validation.sum()),
                                         cohort_excluded_authors=int((~dataset.eligible_for_validation).sum()),
                                         required_input_status=absent_status,
                                         missing_inputs=';'.join(absent),
                                         experiment_status=experiment_status,
                                         experiment_input_matched_authors=len(matched) if not absent else 0,
                                         experiment_specific_eligibility=('INPUT_MATCHED_NOT_FULLY_VALIDATED'
                                             if not absent else absent_status)))
    _write_csv(pd.DataFrame(eligibility_rows), destination/'experiment_eligibility.csv', classification)
    if source_decisions:
        _write_csv(pd.DataFrame([item.as_record() for item in source_decisions]),
                   destination/'input_source_status.csv', classification)
    figures = []
    if generate_figures:
        figures = _write_figures(destination, eligible, experiment_outputs)
    _write_reports(destination, quality_report, descriptive, experiment_outputs, dataset, classification)
    metadata = dict(data_classification=classification, run_at_utc=datetime.now(timezone.utc).isoformat(),
                    source_sha256=source_hashes(), author_rows=len(dataset),
                    code_sha256=code_hash(), python_version=sys.version.split()[0],
                    eligible_authors=int(dataset.eligible_for_validation.sum()),
                    excluded_publications=(None if excluded_publications is None
                                           else int(len(excluded_publications))),
                    publication_year_policy=('DROP_PAPERS_WITHOUT_VALID_YEAR (not the design rule; '
                                             'requires lecturer approval)'
                                             if excluded_publications is not None else
                                             'EXCLUDE_AUTHORS_WITH_MISSING_YEARS (design selection criterion)'),
                    metric_coverage={name:int(dataset[name].notna().sum()) for name in BASELINE_COLUMNS},
                    experiments=names,
                    experiment_status={name:_experiment_status(output) for name, output in experiment_outputs.items()},
                    eligibility_rules=asdict(rules), random_seed=settings.random_seed,
                    validation_config={key:str(value) if isinstance(value, (Path,)) else value
                                       for key, value in asdict(settings).items()},
                    figures=[str(path.relative_to(PROJECT_ROOT)) for path in figures],
                    frozen_benchmark=(dict(version=(extra_inputs or {})['frozen_benchmarks'].version,
                        sha256=(extra_inputs or {})['frozen_benchmarks'].sha256,
                        original_author_count=(extra_inputs or {})['frozen_benchmarks'].original_author_count)
                        if (extra_inputs or {}).get('frozen_benchmarks') is not None else None),
                    rq07_graph_author_count=len((extra_inputs or {}).get('graph_inputs') or {}),
                    rq07_graph_input_sha256={author:graph.source_sha256 for author, graph in
                        ((extra_inputs or {}).get('graph_inputs') or {}).items() if graph.source_sha256},
                    cohort_sha256=(hashlib.sha256((PROJECT_ROOT/'995_authors.csv').read_bytes()).hexdigest()
                        if source_kind == 'SELECT_ONLY_POSTGRESQL_COHORT' else None),
                    source=source_kind,
                    database_isolation=_database_isolation(source_kind),
                    database_engine=_database_engine(source_kind),
                    packages={name:importlib.metadata.version(name) for name in
                              ('python-dotenv', 'pandas', 'matplotlib', 'psycopg2-binary',
                               'pglast', 'pypdf', 'numpy', 'scipy')},
                    methodology_pending=[m.metric_name for m in REGISTRY
                                         if m.implementation_status == 'METHODOLOGY_PENDING'
                                         and m.metric_name not in (metric_strategies or {})],
                    activated_strategies={name:dict(source_reference=getattr(strategy, 'reference', ''),
                                                     approval_reference=strategy.approval_reference)
                                          for name, strategy in (metric_strategies or {}).items()},
                    data_readiness_references={key:(extra_inputs or {}).get(key)
                        for key in ('database_ready_reference', 'citation_source_reference',
                                    'pilot_design_reference')
                        if (extra_inputs or {}).get(key)},
                    input_digests={key:dict(rows=len(value), columns=list(value.columns),
                        sha256=hashlib.sha256(value.sort_values(
                            'author_id' if 'author_id' in value else 'pub_id',
                            kind='stable').to_csv(index=False).encode('utf-8')).hexdigest())
                        for key, value in (extra_inputs or {}).items() if isinstance(value, pd.DataFrame)})
    (destination/'run_metadata.json').write_text(json.dumps(metadata, indent=2, default=str), encoding='utf-8')
    manifest = []
    for path in sorted((*destination.rglob('*'), *figures)):
        if path.is_file():
            manifest.append(dict(relative_path=path.relative_to(PROJECT_ROOT).as_posix(),
                                 size_bytes=path.stat().st_size,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    _write_csv(pd.DataFrame(manifest), destination/'output_manifest.csv', classification)
    return destination


def _apply_metric_strategies(extracts, links, metrics, strategies):
    """Activate only explicitly supplied, source-cited baseline strategies."""
    from metrics import c_score, hm_index, m_index, fi_score, s_index, ar_index
    functions = {
        'c_score_raw': c_score.calculate_raw,
        'c_score_sc_adjusted': c_score.calculate_self_citation_adjusted,
        'hm_index': hm_index.calculate,
        'fi_score': fi_score.calculate, 's_index': s_index.calculate,
        'ar_index': ar_index.calculate,
    }
    unknown = set(strategies)-set(functions)-{'m_index'}
    if unknown:
        raise ValueError(f'Unknown or already source-defined strategy: {sorted(unknown)}')
    paper = (links.drop_duplicates(['author_id','pub_id'])
             .merge(extracts.publications, on='pub_id', how='left', validate='many_to_one'))
    if extracts.fields is not None and not extracts.fields.empty:
        if extracts.fields.pub_id.duplicated().any():
            raise ValueError('Duplicate field_classification pub_id')
        paper = paper.merge(extracts.fields, on='pub_id', how='left', validate='many_to_one')
    paper['coauthor_count'] = paper.pub_id.map(links.drop_duplicates(['author_id','pub_id']).groupby('pub_id').size())
    results = {}
    for name, strategy in strategies.items():
        if not getattr(strategy, 'approval_reference', '').strip():
            raise ValueError(f'{name}: METHODOLOGY_PENDING; approved strategy reference required')
        if name == 'm_index':
            years = paper.groupby('author_id').year.min()
            results[name] = m_index.calculate(metrics['h_index'], years, strategy)
        else:
            results[name] = functions[name](paper, strategy)
    return results


def _write_figures(destination, eligible, outputs):
    """Export only figures supported by observed finite results."""
    from visualization.distributions import histogram
    from visualization.correlations import (scatter, paired_difference, heatmap, qq_plot,
        residual_plot, bland_altman_plot, difference_histogram)
    from visualization.rankings import compare as ranking_comparison
    from visualization.construct import scree, loadings as pca_loadings
    from visualization.discrimination import roc as roc_plot, combined_roc
    from visualization.temporal import trajectory as trajectory_plot
    from visualization.robustness import (sensitivity as sensitivity_plot,
        gaming_percentile_pairs)
    from visualization.fairness import subgroup_means

    folder = PROJECT_ROOT/'figures'/destination.name
    created = []
    if eligible.empty:
        return created
    available = ['nm_index', *[name for name in BASELINE_COLUMNS
                               if name in eligible and eligible[name].notna().any()]]
    for metric in available:
        if metric in eligible and eligible[metric].notna().any():
            created.append(histogram(eligible, metric, folder, f'distribution_{metric}.png'))
    if 'rq01' in outputs:
        for metric in available:
            if pd.to_numeric(eligible[metric], errors='coerce').notna().sum() >= 3:
                created.append(qq_plot(eligible, metric, folder, f'qq_{metric}.png'))
        residuals = outputs['rq01'].get('rq01_residuals')
        if residuals is not None and not residuals.empty:
            created.append(residual_plot(residuals, 'fitted_nm_percentile', folder,
                                         'rq01_residual_vs_fitted.png'))
            created.append(residual_plot(residuals, 'middle_author_share', folder,
                                         'rq01_residual_vs_middle_share.png'))
        ba_pairs = outputs['rq01'].get('rq01_bland_altman_pairs')
        ba_summary = outputs['rq01'].get('rq01_bland_altman_summary')
        if ba_pairs is not None and ba_summary is not None:
            for row in ba_summary.to_dict('records'):
                if row['status'] != 'OK':
                    continue
                metric = row['baseline']
                comparison = ba_pairs.loc[ba_pairs.baseline.eq(metric)]
                summary = ba_summary.loc[ba_summary.baseline.eq(metric)]
                created.append(bland_altman_plot(comparison, summary, folder,
                    f'rq01_bland_altman_{metric}.png'))
                created.append(difference_histogram(comparison, summary, folder,
                    f'rq01_difference_hist_{metric}.png'))
    for metric in available[1:]:
        pair = eligible[['nm_index', metric]].dropna()
        if len(pair) >= 2:
            created.append(scatter(pair, 'nm_index', metric, folder, f'scatter_nm_{metric}.png'))
            created.append(paired_difference(pair, 'nm_index', metric, folder, f'paired_nm_{metric}.png'))
            created.append(ranking_comparison(pair, 'nm_index', metric, folder, f'ranks_nm_{metric}.png'))
    correlations = eligible[available].corr()
    if correlations.notna().to_numpy().any():
        created.append(heatmap(correlations, folder, 'correlation_heatmap.png'))
    pca_result = outputs.get('rq10', {}).get('pca_status')
    pca_table = outputs.get('rq10', {}).get('pca_loadings')
    if pca_result is not None and not pca_result.empty and pca_result.iloc[0].get('status') == 'OK':
        created.append(scree(pca_result.iloc[0]['explained_variance'], folder, 'pca_scree.png'))
        created.append(pca_loadings(pca_table, folder, 'pca_loadings.png'))
    for title, curve in outputs.get('rq04', {}).items():
        if title.startswith('roc_') and not curve.empty:
            created.append(roc_plot(curve, folder, title+'.png'))
    award = outputs.get('rq04', {}).get('award_analysis')
    if award is not None and 'status' in award and award.status.eq('OK').any():
        created.append(combined_roc(outputs['rq04'], award, folder, 'award_roc_combined.png'))
    evolution = outputs.get('rq06', {}).get('score_evolution_normalized')
    if evolution is not None and not evolution.empty:
        metrics = [c for c in evolution if c not in
                   ('author_id', 'year', 'publication_count', 'normalization', 'decision_reference')]
        created.append(trajectory_plot(evolution, metrics, folder, 'score_evolution.png'))
    fairness = outputs.get('rq11', {}).get('fairness_analysis')
    if fairness is not None and 'group' in fairness and (fairness.status == 'OK').any():
        for dimension in ('gender', 'region'):
            selected = fairness.loc[(fairness.metric == 'nm_index') &
                                    (fairness.dimension == dimension) & (fairness.status == 'OK')]
            if not selected.empty:
                created.append(subgroup_means(fairness, folder,
                    f'fairness_nm_{dimension}.png', dimension=dimension))
    sensitivity = outputs.get('sensitivity', {}).get('sensitivity_results')
    if sensitivity is not None and {'sample_size', 'correlation'} <= set(sensitivity):
        valid = sensitivity.loc[sensitivity.status == 'OK']
        if not valid.empty:
            created.append(sensitivity_plot(valid, 'sample_size', 'correlation',
                                            folder, 'sample_size_robustness.png'))
    gaming = outputs.get('rq07', {}).get('gaming_resistance')
    if gaming is not None and {'status', 'original_nm_percentile',
                               'manipulated_nm_percentile'} <= set(gaming) and gaming.status.eq('OK').any():
        created.append(gaming_percentile_pairs(gaming, folder,
                                               'rq07_nm_percentile_pairs.png'))
    return created


def _experiment_status(output):
    if 'status' in output and not output['status'].empty:
        return str(output['status'].iloc[0].get('status', 'UNKNOWN'))
    states = [str(row) for frame in output.values() if 'status' in frame
              for row in frame['status'].dropna().unique()]
    if not states:
        return 'NO_STATISTICAL_RESULT'
    return 'OK' if 'OK' in states else states[0]


def _write_reports(destination, quality, descriptive, outputs, dataset, classification):
    reports = destination/'reports'
    reports.mkdir()
    pending = [m.metric_name for m in REGISTRY if m.implementation_status == 'METHODOLOGY_PENDING']
    status_lines = [f'- **{name}: {_experiment_status(result)}** — '
                    + ', '.join(f'{title} ({len(frame)} rows)' for title, frame in result.items())
                    for name, result in outputs.items()]
    coverage_lines = [f'- `{name}`: {int(dataset[name].notna().sum())}/{len(dataset)} authors'
                      for name in BASELINE_COLUMNS]
    pending_lines = [name for name, result in outputs.items()
                     if _experiment_status(result) in {'METHODOLOGY_PENDING', 'DATA_REQUIRED',
                                                        'INSUFFICIENT_DATA', 'INVALID_INPUT'}]
    def state(name):
        if name not in outputs:
            return 'NOT_EXECUTED'
        code = _experiment_status(outputs[name])
        if code == 'DATA_REQUIRED':
            return 'UNAVAILABLE_INPUT'
        if code == 'METHODOLOGY_PENDING':
            return 'METHODOLOGY_PENDING'
        if code in {'INSUFFICIENT_DATA', 'INVALID_INPUT'}:
            return 'UNAVAILABLE_INPUT'
        return 'IMPLEMENTED_RESULT' if code in {'OK', 'OK_WITH_EXPLICIT_CONVENTION'} else code
    inventory = ['| Experiment | Report state | Detail |', '|---|---|---|']
    for name in EXPERIMENT_MODULES:
        detail = _experiment_status(outputs[name]) if name in outputs else 'Experiment not selected for this run'
        inventory.append(f'| {name} | {state(name)} | {detail} |')
    texts = {
        'executive_summary.md': '# Run summary\n\n'
            +f'Data classification: **{classification}**. Authors: {len(dataset)}; cohort eligible: '
            +f'{int(dataset.eligible_for_validation.sum())}. '
            +'These outputs are software checks and descriptive results; no empirical conclusion follows from coverage alone.\n',
        'methodology.md': '# Methodology\n\n'
            +'Source versions and hashes are recorded in `run_metadata.json`. NM is loaded from `author_nm_index`; '
            +'raw Total Cites, h and written g are local conventional baselines. Other baselines require source-cited '
            +'approved strategies. Each result CSV declares data classification; missing experiments are status-coded. '
            +'Eligibility uses separate portfolio evidence. See `experiment_eligibility.csv` for cohort counts and input gates.\n',
        'data_quality.md': to_markdown(quality),
        'metric_results.md': '# Metric coverage\n\n'+'\n'.join(coverage_lines)
            +'\n\nDescriptive statistics are in `descriptive_statistics.csv`. Missing baselines are not zero-filled.\n',
        'statistical_results.md': '# Experiment status and outputs\n\n'+'\n'.join(status_lines)
            +'\n\n## Execution and evidence state\n\n'+'\n'.join(inventory)
            +'\n\nNo status marked pending, data-required or insufficient should be interpreted as a final finding. '
            +'The numerical details and sample sizes are in the named CSVs.\n',
        'limitations.md': '# Limitations\n\nMethodology-pending baselines: '+', '.join(pending)
            +'. Experiments requiring further methods or inputs: '+(', '.join(pending_lines) or 'none')
            +'. Cohort/source completeness, citation provenance, missing-data policy, historical data, '
            +'award and subgroup-label provenance remain separate gates for any real study.\n',
    }
    for name, content in texts.items():
        (reports/name).write_text(f'# {classification}\n\n'+content, encoding='utf-8')


def run_database(*, experiment_names=(), allow_incomplete=False, extra_inputs=None):
    evidence = extra_inputs or {}
    if not evidence.get('database_ready_reference') or not evidence.get('citation_source_reference'):
        raise ValueError('DATA_REQUIRED: documented database/cohort and citation-source readiness references are required before connecting')
    load_config()
    verify_schema()
    extracts = load_all()
    if len(extracts.authors) < 100000:
        raise ValueError('DATA_REQUIRED: design calls for 100000 verified author profiles; no metrics calculated')
    return run_from_extracts(extracts, experiment_names=experiment_names,
                             allow_incomplete=allow_incomplete, extra_inputs=extra_inputs,
                             source_kind='SELECT_ONLY_POSTGRESQL', _source_token=_DATABASE_SOURCE_TOKEN)


def run_pilot(*, author_ids, experiment_names=(), extra_inputs=None):
    """Run a prespecified small cohort; never silently treat it as the 100k study."""
    evidence = extra_inputs or {}
    required = ('pilot_design_reference', 'database_ready_reference',
                'citation_source_reference')
    if any(evidence.get(key) is None or (isinstance(evidence.get(key), str)
           and not evidence[key].strip()) for key in required):
        raise ValueError('DATA_REQUIRED: pilot design, cohort readiness, citation source, and portfolio evidence are required before connecting')
    ids = tuple(author_ids)
    if not ids or len(ids) > 6000 or len(set(ids)) != len(ids):
        raise ValueError('Pilot author IDs must be a unique nonempty list of at most 6000')
    load_config()
    from .repository import load_selected_author_ids
    extracts = load_selected_author_ids(ids)
    return run_from_extracts(extracts, experiment_names=experiment_names,
                             extra_inputs=evidence, source_kind='SELECT_ONLY_POSTGRESQL_PILOT',
                             _source_token=_DATABASE_SOURCE_TOKEN)


def run_cohort(*, experiment_names=(), extra_inputs=None, exclude_missing_years=False):
    """Use the immutable 995-ID cohort against a later populated read-only DB."""
    from .phase6_readiness import read_cohort
    from .repository import load_selected_author_ids
    _, ids = read_cohort()
    evidence = extra_inputs or {}
    if not evidence.get('database_ready_reference') or not evidence.get('citation_source_reference'):
        raise ValueError('DATA_REQUIRED: populated database and citation-source evidence needed before connection')
    names = tuple(experiment_names) or tuple(EXPERIMENT_MODULES)
    graphs, frozen, parameters = (evidence.get('graph_inputs'),
                                  evidence.get('frozen_benchmarks'),
                                  evidence.get('nm_parameters'))
    # Without any RQ7 bundle, RQ7 itself reports DATA_REQUIRED; a supplied bundle must be complete.
    if 'rq07' in names and (graphs, frozen, parameters) != (None, None, None):
        if graphs is None or frozen is None or parameters is None or set(graphs) != set(ids):
            raise ValueError('DATA_REQUIRED: complete per-author RQ7 graphs and frozen original reference required')
        if frozen.original_author_count != 100000:
            raise ValueError('DATA_REQUIRED: real RQ7 requires the original 100000-author reference')
    load_config()
    extracts = load_selected_author_ids(ids)
    excluded = None
    if exclude_missing_years:
        extracts, excluded = _exclude_missing_year_publications(extracts)
    return run_from_extracts(extracts, experiment_names=names,
                             extra_inputs=evidence, source_kind='SELECT_ONLY_POSTGRESQL_COHORT',
                             _source_token=_DATABASE_SOURCE_TOKEN, excluded_publications=excluded)


def _exclude_missing_year_publications(extracts):
    """Drop papers without a valid year and return every dropped pub_id with its cohort authors."""
    year = pd.to_numeric(extracts.publications.year, errors='coerce')
    invalid = year.isna() | ~year.between(1000, 9999)
    excluded = extracts.publications.loc[invalid, ['pub_id', 'year', 'total_citation']].copy()
    dropped = set(excluded.pub_id)
    slots = extracts.authorship.loc[extracts.authorship.pub_id.isin(dropped)]
    authors = slots.set_index('pub_id')[[f'author{i}id' for i in range(1, 11)]].apply(
        lambda row: ';'.join(sorted(set(row.dropna().astype(str)))), axis=1)
    excluded['cohort_author_ids'] = excluded.pub_id.map(authors.groupby(level=0).first())
    excluded['reason'] = 'missing_or_invalid_publication_year'

    def keep(frame):
        return frame.loc[~frame.pub_id.isin(dropped)].reset_index(drop=True)
    return replace(extracts, publications=keep(extracts.publications), citations=keep(extracts.citations),
                   authorship=keep(extracts.authorship), fields=keep(extracts.fields)), excluded
