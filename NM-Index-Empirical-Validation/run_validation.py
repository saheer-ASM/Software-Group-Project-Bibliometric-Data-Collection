"""CLI for dry-run or an explicitly requested future validation run."""

import argparse
import json

from src.pipeline import (EXPERIMENT_MODULES, dry_run, run_cohort, run_database,
                          run_from_extracts, run_pilot)
from src.external_inputs import SCHEMAS, load_csv, load_pilot_author_ids


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only NM empirical validation')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--experiment', choices=EXPERIMENT_MODULES)
    selection.add_argument('--all', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='check local configuration/modules/documents without DB access')
    parser.add_argument('--data-source', choices=('database', 'cohort', 'pilot', 'mock'), default='database',
                        help='mock uses TEST DATA ONLY and never opens PostgreSQL')
    parser.add_argument('--pilot-author-ids', help='pilot only: local CSV containing one author_id column')
    parser.add_argument('--rq07-bundle', help='cohort only: complete local graph and frozen-reference bundle')
    parser.add_argument('--exclude-missing-year-publications', action='store_true',
                        help='cohort only: drop papers without a valid year, listed in excluded_publications.csv. '
                             'Deviates from the design, which excludes such authors (the default); '
                             'use only with lecturer approval')
    parser.add_argument('--pilot-design-reference',
                        help='pilot only: documented approval of selected cohort and reduced sample scope')
    parser.add_argument('--input', action='append', default=[], metavar='KIND=CSV',
                        help='local research CSV, e.g. award_labels=inputs/award_labels.csv; repeatable')
    parser.add_argument('--icc-model', choices=['ICC(A,1) two-way random absolute agreement'])
    parser.add_argument('--score-year', type=int)
    parser.add_argument('--first-year', type=int)
    parser.add_argument('--rank-change-denominator', choices=['paired_cohort_size'])
    parser.add_argument('--pca-preprocessing', choices=['complete_case_z_standardization'])
    parser.add_argument('--pca-decision-reference')
    parser.add_argument('--representative-author')
    parser.add_argument('--trajectory-normalization', choices=['within_author_max'])
    parser.add_argument('--trajectory-decision-reference')
    parser.add_argument('--gaming-fractional-policy', choices=['preserve_fractional_counts'])
    parser.add_argument('--gaming-decision-reference')
    parser.add_argument('--group-column')
    parser.add_argument('--fairness-cohen-d', choices=['pooled_sample_sd'])
    parser.add_argument('--fairness-variance-ddof', type=int, choices=[0, 1])
    parser.add_argument('--fairness-decision-reference')
    parser.add_argument('--database-ready-reference',
                        help='documented approval of complete cohort/data population; required before DB connection')
    parser.add_argument('--citation-source-reference',
                        help='documented approval of raw citation source; required before DB connection')
    parser.add_argument('--award-inference-convention', choices=['welch_two_sided_pooled_d'],
                        help='RQ4 only: explicitly approved independent-group test and effect convention')
    parser.add_argument('--award-inference-reference',
                        help='RQ4 only: lecturer/research-team approval reference for inference convention')
    parser.add_argument('--predictors', help='comma-separated prespecified RQ5 predictors')
    parser.add_argument('--covariates', help='comma-separated prespecified RQ5 covariates')
    args = parser.parse_args(argv)
    names = [args.experiment] if args.experiment else list(EXPERIMENT_MODULES) if args.all or args.data_source == 'mock' else []
    if args.dry_run:
        print(json.dumps(dry_run(names), indent=2))
        return 0
    if not args.experiment and not args.all and args.data_source != 'mock':
        parser.error('Choose --dry-run, --experiment NAME, or --all')
    if args.data_source != 'pilot' and (args.pilot_author_ids or args.pilot_design_reference):
        parser.error('--pilot-author-ids and --pilot-design-reference require --data-source pilot')
    if args.rq07_bundle and args.data_source != 'cohort':
        parser.error('--rq07-bundle requires --data-source cohort')
    if args.exclude_missing_year_publications and args.data_source != 'cohort':
        parser.error('--exclude-missing-year-publications requires --data-source cohort')
    if args.data_source == 'mock':
        if args.input:
            parser.error('Mock runs use only bundled synthetic inputs; --input is not accepted')
        from src.mock_repository import LABEL, load_all
        extracts, synthetic_inputs = load_all()
        destination = run_from_extracts(extracts, experiment_names=names,
            extra_inputs=synthetic_inputs, source_kind='SYNTHETIC_TEST_DATA')
        print(f'{LABEL}\nLocal mock run saved to {destination}')
        return 0
    extra = dict(icc_model=args.icc_model, score_year=args.score_year,
                 database_ready_reference=args.database_ready_reference,
                 citation_source_reference=args.citation_source_reference,
                 award_inference_convention=args.award_inference_convention,
                 award_inference_reference=args.award_inference_reference,
                 pilot_design_reference=args.pilot_design_reference,
                 first_year=args.first_year, rank_change_denominator=args.rank_change_denominator,
                 pca_preprocessing=args.pca_preprocessing,
                 pca_decision_reference=args.pca_decision_reference,
                 representative_author=args.representative_author,
                 trajectory_normalization=args.trajectory_normalization,
                 trajectory_decision_reference=args.trajectory_decision_reference,
                 gaming_fractional_policy=args.gaming_fractional_policy,
                 gaming_decision_reference=args.gaming_decision_reference,
                 group_column=args.group_column,
                 predictors=tuple(x.strip() for x in args.predictors.split(',') if x.strip()) if args.predictors else None,
                 covariates=tuple(x.strip() for x in args.covariates.split(',') if x.strip()) if args.covariates else ())
    choices = (args.fairness_cohen_d, args.fairness_variance_ddof,
               args.fairness_decision_reference)
    if any(value is not None for value in choices):
        if any(value is None for value in choices):
            parser.error('Fairness convention requires all three --fairness-* options')
        from analysis.fairness import FairnessConvention
        extra['fairness_convention'] = FairnessConvention(*choices)
    for item in args.input:
        if '=' not in item:
            parser.error('--input must be KIND=CSV')
        kind, path = item.split('=', 1)
        if kind not in SCHEMAS or kind in extra or kind in extra.get('_fallback_paths', {}):
            parser.error(f'Unsupported or duplicate --input kind: {kind}')
        if kind in {'portfolio_verification', 'reference_scores'}:
            extra.setdefault('_fallback_paths', {})[kind] = path
        else:
            extra[kind] = load_csv(kind, path)
    if args.data_source == 'cohort':
        from src.phase6_readiness import read_cohort
        _, ids = read_cohort()
        if args.rq07_bundle:
            extra['graph_inputs'], extra['frozen_benchmarks'], extra['nm_parameters'] = load_bundle(
                args.rq07_bundle, ids)
        destination = run_cohort(experiment_names=names, extra_inputs=extra,
                                 exclude_missing_years=args.exclude_missing_year_publications)
            extra['rq07_bundle_path'] = args.rq07_bundle
        destination = run_cohort(experiment_names=names, extra_inputs=extra)
    elif args.data_source == 'pilot':
        if not args.pilot_author_ids:
            parser.error('--data-source pilot requires --pilot-author-ids')
        extra['pilot_author_ids'] = load_pilot_author_ids(args.pilot_author_ids)
        ids = extra['pilot_author_ids'].author_id.tolist()
        destination = run_pilot(author_ids=ids, experiment_names=names, extra_inputs=extra)
    else:
        destination = run_database(experiment_names=names, extra_inputs=extra)
    print(f'Local validation run saved to {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
