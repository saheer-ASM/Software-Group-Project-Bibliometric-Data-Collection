"""Lecturer-approved RQ1 diagnostics on one frozen reference cohort."""

import numpy as np
import pandas as pd
from scipy.stats import skew


def percentile_ranks(values):
    """Average tied ranks on the 0–100 empirical percentile scale."""
    series = pd.to_numeric(values, errors='coerce')
    series = series.replace([np.inf, -np.inf], np.nan)
    return series.rank(method='average', pct=True) * 100


CAREER_STAGES = ('Early', 'Mid-Early', 'Mid-Late', 'Senior')


def analyse(reference, baselines, *, synthetic=False, selected_ids=()):
    required = {'author_id', 'nm_index', 'c_score_raw',
                'middle_author_share', 'career_stage', 'reference_version',
                'evidence_reference'}
    missing = required - set(reference)
    if missing:
        return {'status': pd.DataFrame([dict(status='DATA_REQUIRED',
            issue=f'Reference score columns missing: {sorted(missing)}')])}
    if reference.author_id.isna().any() or reference.author_id.duplicated().any():
        raise ValueError('RQ1 reference requires unique non-NULL author_id values')
    versions = reference.reference_version.dropna().astype(str).str.strip().unique()
    if len(versions) != 1 or not versions[0]:
        raise ValueError('RQ1 reference requires one nonblank frozen reference_version')
    if (reference.evidence_reference.isna().any() or
            reference.evidence_reference.astype(str).str.strip().eq('').any()):
        raise ValueError('RQ1 reference rows require provenance evidence_reference')
    if not synthetic and len(reference) != 100000:
        return {'status': pd.DataFrame([dict(status='DATA_REQUIRED',
            issue='Lecturer requires exactly the approved 100000-author reference sample',
            reference_rows=len(reference), reference_version=versions[0])])}
    frame = reference.copy().reset_index(drop=True)
    absent_ids = set(selected_ids)-set(frame.author_id)
    if absent_ids:
        return {'rq01_cohort_match': pd.DataFrame([
            dict(author_id=value, status='EXCLUDED',
                 reason='SELECTED_AUTHOR_ABSENT_FROM_REFERENCE')
            for value in sorted(absent_ids)]),
            'status': pd.DataFrame([dict(status='DATA_REQUIRED',
                issue=f'{len(absent_ids)} selected authors absent from frozen reference')])}
    n = len(frame)
    numeric = frame[['nm_index', 'c_score_raw', 'middle_author_share']].apply(
        pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
    stage = frame.career_stage.astype('string').str.strip()
    valid = (numeric.nm_index.between(0, 100) & numeric.c_score_raw.notna()
             & numeric.middle_author_share.between(0, 1) & stage.isin(CAREER_STAGES))
    author_status = pd.DataFrame({'author_id': frame.author_id,
        'status': np.where(valid, 'READY', 'EXCLUDED'),
        'reason': np.where(valid, '', 'MISSING_OR_INVALID_NM_C_SCORE_SHARE_OR_CAREER_STAGE'),
        'reference_version': versions[0]})
    diagnostics = {'rq01_reference_author_status': author_status}
    if not valid.all():
        diagnostics['status'] = pd.DataFrame([dict(status='DATA_REQUIRED',
            issue='Complete reference values required; see rq01_reference_author_status',
            reference_rows=n, excluded=int((~valid).sum()))])
        return diagnostics
    nm_pct = percentile_ranks(numeric.nm_index)
    c_pct = percentile_ranks(numeric.c_score_raw)
    x = c_pct.to_numpy(dtype=float)
    y = nm_pct.to_numpy(dtype=float)
    if n < 3 or np.std(x) == 0:
        diagnostics['status'] = pd.DataFrame([dict(status='INSUFFICIENT_DATA',
            issue='OLS needs at least three authors and varying C-score percentiles')])
        return diagnostics
    design = np.column_stack([np.ones(n), x])
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    fitted = intercept + slope*x
    residual = y-fitted
    diagnostics['rq01_residual_coefficients'] = pd.DataFrame([dict(
        model='OLS: NM percentile ~ C-score percentile', n=n,
        intercept=float(intercept), c_score_percentile_coefficient=float(slope),
        residual_mean=float(residual.mean()),
        residual_sd=float(residual.std(ddof=1)),
        r_squared=float(1-(residual @ residual)/np.sum((y-y.mean())**2))
        if np.sum((y-y.mean())**2) else np.nan,
        reference_version=versions[0])])
    diagnostics['rq01_residuals'] = pd.DataFrame(dict(
        author_id=frame.author_id, nm_percentile=y, c_score_percentile=x,
        fitted_nm_percentile=fitted, residual=residual,
        middle_author_share=numeric.middle_author_share,
        career_stage=stage, reference_version=versions[0]))
    pairs, summaries = [], []
    for metric in baselines:
        if metric not in frame:
            summaries.append(dict(baseline=metric, status='DATA_REQUIRED',
                reason='Baseline absent from reference sample', reference_version=versions[0]))
            continue
        values = pd.to_numeric(frame[metric], errors='coerce').replace(
            [np.inf, -np.inf], np.nan)
        if values.isna().any():
            summaries.append(dict(baseline=metric, status='DATA_REQUIRED',
                reason=f'{int(values.isna().sum())} authors lack a finite baseline score',
                reference_version=versions[0]))
            continue
        baseline_pct = percentile_ranks(values).to_numpy(dtype=float)
        difference = y-baseline_pct
        mean = (y+baseline_pct)/2
        bias = float(difference.mean())
        sd = float(difference.std(ddof=1)) if n > 1 else np.nan
        low, high = bias-1.96*sd, bias+1.96*sd
        lower_emp, upper_emp = np.percentile(difference, [2.5, 97.5])
        summaries.append(dict(baseline=metric, status='OK', n=n, bias=bias,
            difference_sd=sd, loa_lower=low, loa_upper=high,
            difference_p2_5=float(lower_emp), difference_p97_5=float(upper_emp),
            difference_skewness=float(skew(difference, bias=False))
                if n > 2 and np.std(difference) > 0 else np.nan,
            skewness_assessment='REVIEW_REQUIRED: no approved numeric threshold',
            reference_version=versions[0]))
        pairs.append(pd.DataFrame(dict(author_id=frame.author_id, baseline=metric,
            nm_percentile=y, baseline_percentile=baseline_pct,
            pair_mean=mean, difference=difference,
            career_stage=stage, reference_version=versions[0])))
    diagnostics['rq01_bland_altman_summary'] = pd.DataFrame(summaries)
    diagnostics['rq01_bland_altman_pairs'] = (pd.concat(pairs, ignore_index=True)
        if pairs else pd.DataFrame(columns=['author_id','baseline','nm_percentile',
            'baseline_percentile','pair_mean','difference','career_stage','reference_version']))
    diagnostics['status'] = pd.DataFrame([dict(status='OK' if all(
        row['status'] == 'OK' for row in summaries) else 'DATA_REQUIRED',
        issue='' if all(row['status'] == 'OK' for row in summaries)
        else 'Some baselines are absent/incomplete in the frozen reference',
        reference_rows=n, reference_version=versions[0])])
    return diagnostics
