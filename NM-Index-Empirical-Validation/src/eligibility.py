"""Explicit, reusable author eligibility decisions."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EligibilityRules:
    min_publications: int = 5
    min_raw_cites: int = 10
    min_metric_coverage: float = 0.0
    require_nm: bool = True
    require_verified_portfolio: bool = True
    required_outcomes: tuple[str, ...] = ()
    required_time_span: tuple[int, int] | None = None
    require_active_period: bool = False
    require_complete_publication_metadata: bool = False


def evaluate(frame: pd.DataFrame, rules: EligibilityRules) -> pd.DataFrame:
    output = frame.copy()
    reasons = []
    for row in output.to_dict('records'):
        failures = []
        if row.get('linked_publications', 0) < rules.min_publications:
            failures.append('MIN_PUBLICATIONS')
        raw_cites = row.get('raw_total_cites')
        if pd.isna(raw_cites) or raw_cites < rules.min_raw_cites:
            failures.append('MIN_RAW_CITES')
        if rules.require_nm and not row.get('nm_index_available', False):
            failures.append('NM_UNAVAILABLE')
        component_complete = row.get('nm_component_complete')
        if rules.require_nm and (pd.isna(component_complete) or not bool(component_complete)):
            failures.append('NM_COMPONENTS_INCOMPLETE')
        if rules.require_verified_portfolio and not row.get('full_portfolio_verified', False):
            failures.append('PORTFOLIO_UNVERIFIED')
        if rules.require_active_period and row.get('active_2000_2024') is not True:
            failures.append('INACTIVE_2000_2024')
        if (rules.require_complete_publication_metadata
                and row.get('publication_metadata_complete') is not True):
            failures.append('INCOMPLETE_PUBLICATION_METADATA')
        if row.get('metric_coverage_percentage', 0) < rules.min_metric_coverage:
            failures.append('METRIC_COVERAGE')
        failures += [f'OUTCOME_UNAVAILABLE:{name}' for name in rules.required_outcomes
                     if pd.isna(row.get(name))]
        if rules.required_time_span:
            start, end = rules.required_time_span
            first, last = row.get('observed_first_year'), row.get('observed_last_year')
            if pd.isna(first) or pd.isna(last) or first > start or last < end:
                failures.append('TIME_SPAN')
        reasons.append(';'.join(failures) if failures else 'ELIGIBLE')
    output['eligibility_reason'] = reasons
    output['eligible_for_validation'] = output.eligibility_reason.eq('ELIGIBLE')
    return output
