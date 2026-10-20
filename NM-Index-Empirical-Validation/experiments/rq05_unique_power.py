"""RQ5 self-citation, author-ordering, domain and career-stage analyses."""

import pandas as pd
import numpy as np
from analysis.regression import fit
from .common import pending


def _summarize(frame, group, metrics):
    if group not in frame:
        return pd.DataFrame([dict(status='METHODOLOGY_PENDING', issue=f'Observed {group} labels absent')])
    rows = []
    for label, part in frame.groupby(group, dropna=True):
        for metric in metrics:
            values = pd.to_numeric(part[metric], errors='coerce').dropna()
            rows.append(dict(status='OK' if len(values) else 'INSUFFICIENT_DATA',
                             group=label, metric=metric, n=len(values),
                             mean=float(values.mean()) if len(values) else float('nan'),
                             median=float(values.median()) if len(values) else float('nan'),
                             sd=float(values.std(ddof=1)) if len(values)>1 else float('nan')))
    return pd.DataFrame(rows)


ISC_SCENARIOS = (
    'High single and unique author',
    'High other core author overlap with no non-overlap authors',
    'High single-author but with non overlapping authors',
    'High other overlapping core-authors but with non overlapping authors',
    'High single and other core author overlapping with non overlapping authors',
    'No overlapping authors',
)
ORDERING_SCENARIOS = (
    'Alphabetical/random ordering', 'Relative contribution ordering',
    'Explicit contribution with CRediT', 'Explicit contribution with ACI',
    'Gaming (higher prevalence of many low contribution papers)',
    'High sole author or high contribution practice',
)
DOMAIN_BANDS = ('Main domain ≥90%', '90%≥ Main domain >80%',
    '80%≥ Main domain >70%', '70%≥ Main domain >60%',
    '60%≥ Main domain >50%', '50%≥ Main domain >40%',
    '40%≥ Main domain >30%', '30%≥ Main domain >0%')
CAREER_BANDS = ('t≤5', '5<t≤10', '15<t≤20', '20<t≤25',
    '25<t≤30', '30<t≤35', '35<t≤40', '40<t≤45', '45<t≤50')


def _design_table(frame, group, labels, metrics):
    observed = _summarize(frame, group, metrics)
    lookup = {(row['group'], row['metric']): row for row in observed.to_dict('records')
              if 'group' in row}
    rows = []
    for label in labels:
        for metric in metrics:
            rows.append(lookup.get((label, metric), dict(group=label, metric=metric,
                status='INPUT_DATA_REQUIRED', n=0, mean=np.nan, median=np.nan, sd=np.nan)))
    return pd.DataFrame(rows)


def _domain_band(value):
    if pd.isna(value) or value <= 0 or value > 100:
        return None
    if value >= 90:
        return DOMAIN_BANDS[0]
    for upper, lower, label in zip((90, 80, 70, 60, 50, 40, 30),
                                    (80, 70, 60, 50, 40, 30, 0), DOMAIN_BANDS[1:]):
        if lower < value <= upper:
            return label
    return None


def _career_band(value):
    if pd.isna(value) or value < 0:
        return None
    for upper, label in zip((5, 10), CAREER_BANDS[:2]):
        if value <= upper:
            return label
    # The source table has no 10<t<=15 category; keep that gap unclassified.
    if value <= 15:
        return None
    for upper, label in zip((20, 25, 30, 35, 40, 45, 50), CAREER_BANDS[2:]):
        if value <= upper:
            return label
    return None


def run(dataset, comparators, *, scenario_data=None, predictors=None, covariates=(), **_):
    if scenario_data is None:
        return pending('RQ5 requires observed scenario, ordering, domain and career-stage inputs', 'DATA_REQUIRED')
    merged = dataset.merge(scenario_data, on='author_id', validate='one_to_one')
    required = {'career_years', 'main_domain_percentage', 'ordering_norm', 'isc_scenario',
                'high_relative_contribution', 'low_influential_self_citation', 'field_name'}
    if not required <= set(merged):
        return pending(f'RQ5 observed scenario data missing {sorted(required-set(merged))}', 'DATA_REQUIRED')
    years = pd.to_numeric(merged.career_years, errors='coerce')
    merged['career_stage'] = years.map(_career_band)
    merged['main_domain_band'] = pd.to_numeric(
        merged.main_domain_percentage, errors='coerce').map(_domain_band)
    recent = merged.loc[years.lt(15)].copy()
    mid = merged.loc[years.gt(15) & years.lt(30)].copy()
    late = merged.loc[years.gt(30) & merged.high_relative_contribution.eq(True)].copy()
    career = merged.loc[merged.low_influential_self_citation.eq(True)
                        & merged.high_relative_contribution.eq(True)
                        & merged.field_name.eq('Computer networks and communication')].copy()
    outputs = {
        'self_citation_analysis': _design_table(recent, 'isc_scenario', ISC_SCENARIOS, ('nm_index', *comparators)),
        'author_ordering_analysis': _design_table(mid, 'ordering_norm', ORDERING_SCENARIOS, ('nm_index', *comparators)),
        'domain_sensitivity': _design_table(late, 'main_domain_band', DOMAIN_BANDS, ('nm_index', *comparators)),
        'career_stage_analysis': _design_table(career, 'career_stage', CAREER_BANDS, ('nm_index', *comparators)),
        'rq05_unclassified': pd.DataFrame([
            dict(component='domain', authors=int(late.main_domain_band.isna().sum()),
                 reason='Main-domain percentage missing, zero, or outside (0,100]'),
            dict(component='career', authors=int(career.career_stage.isna().sum()),
                 reason='Career years missing/outside table or in unspecified 10<t<=15 gap'),
            dict(component='self_citation',
                 authors=int((~recent.isc_scenario.isin(ISC_SCENARIOS)).sum()),
                 reason='Observed label absent from six lecturer categories'),
            dict(component='ordering',
                 authors=int((~mid.ordering_norm.isin(ORDERING_SCENARIOS)).sum()),
                 reason='Observed label absent from six lecturer categories'),
        ]),
    }
    outputs['unique_power_regression'] = (fit(recent, 'nm_index', predictors, covariates)
        if predictors else pd.DataFrame([dict(status='METHODOLOGY_PENDING',
                            issue='Prespecified regression predictors/covariates required')]))
    outputs['status'] = pending('RQ5 observed category labels and regression predictors/covariates require supplied evidence and decisions')['status']
    return outputs
