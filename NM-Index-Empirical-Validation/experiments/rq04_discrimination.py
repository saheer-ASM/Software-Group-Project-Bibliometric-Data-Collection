"""RQ4 awardee discrimination with externally supplied award labels."""

import pandas as pd
import numpy as np
from scipy.stats import ttest_ind
from analysis.discrimination import roc_auc
from analysis.rq01_diagnostics import percentile_ranks
from .common import pending

AWARD_CATEGORIES = ('Nobel Prize', 'Lasker Award', 'Breakthrough Prize',
    'Breakthrough Prize in Life Sciences', 'Wolf Prize', 'Dirac Medal',
    'Knuth Prize', 'IEEE John von Neumann Medal', 'Turing Award',
    'Abel Prize', 'Fields Medal', 'Shaw Prize', 'Crafoord Prize')


def run(dataset, comparators, *, award_labels=None, award_events=None,
        reference_scores=None, award_inference_convention=None,
        award_inference_reference=None, data_source_kind=None, seed=2026, **_):
    if award_labels is None:
        return pending('Verified award-recipient labels from the design are required', 'DATA_REQUIRED')
    if award_labels.author_id.isna().any() or award_labels.author_id.duplicated().any():
        raise ValueError('award_labels requires unique non-NULL author_id values')
    if not award_labels.awardee.astype(str).str.lower().isin({'true', 'false', '0', '1'}).all():
        raise ValueError('awardee must be binary')
    labels = award_labels[['author_id', 'awardee']].copy()
    labels['awardee'] = labels.awardee.astype(str).str.lower().isin({'true', '1'}).astype(int)
    if not set(dataset.author_id.astype(str)) <= set(labels.author_id.astype(str)):
        return pending('Award labels missing for selected eligible authors', 'DATA_REQUIRED')
    if award_inference_convention is not None and (
            award_inference_convention != 'welch_two_sided_pooled_d'
            or not award_inference_reference or not str(award_inference_reference).strip()):
        raise ValueError('RQ4 inference needs an approved Welch/pooled-d decision reference')
    merged = dataset.merge(labels, on='author_id', validate='one_to_one')
    valid_reference = (reference_scores is not None and
        (data_source_kind == 'SYNTHETIC_TEST_DATA' or len(reference_scores) == 100000)
        and not reference_scores.author_id.isna().any()
        and not reference_scores.author_id.duplicated().any()
        and set(merged.author_id.astype(str)) <= set(reference_scores.author_id.astype(str)))
    rows, curves = [], {}
    for metric in ('nm_index', 'raw_total_cites', 'c_score_raw', 'h_index', 'g_index'):
        if metric not in merged:
            continue
        result, curve = roc_auc(merged, metric, 'awardee', seed=seed)
        if metric == 'nm_index' and result.get('status') == 'OK':
            threshold = merged.nm_index.dropna().quantile(.95)
            selected = merged.loc[merged.nm_index >= threshold]
            result.update(top5_threshold=float(threshold), top5_total=len(selected),
                          top5_awardees=int(selected.awardee.sum()),
                          top5_rule='score >= empirical 95th percentile; ties retained')
        result.update(awardee_mean_percentile=np.nan,
                      non_awardee_mean_percentile=np.nan, cohen_d=np.nan,
                      p_value=np.nan, p_value_bonferroni=np.nan,
                      comparison_status='DATA_REQUIRED: complete original reference scores required'
                          if not valid_reference else
                          'METHODOLOGY_PENDING: approved inference convention required',
                      award_category='ALL_CATEGORIES_UNVERIFIED')
        if valid_reference and metric in reference_scores:
            ref_values = pd.to_numeric(reference_scores[metric], errors='coerce')
            if ref_values.notna().all() and np.isfinite(ref_values).all():
                lookup = pd.Series(percentile_ranks(ref_values).to_numpy(),
                                   index=reference_scores.author_id.astype(str))
                selected_pct = merged.author_id.astype(str).map(lookup)
                positive = selected_pct.loc[merged.awardee.eq(1)].dropna().to_numpy(dtype=float)
                negative = selected_pct.loc[merged.awardee.eq(0)].dropna().to_numpy(dtype=float)
                result['awardee_mean_percentile'] = float(np.mean(positive)) if len(positive) else np.nan
                result['non_awardee_mean_percentile'] = float(np.mean(negative)) if len(negative) else np.nan
                if award_inference_convention and len(positive) >= 2 and len(negative) >= 2:
                    pooled_variance = ((len(positive)-1)*np.var(positive, ddof=1)
                        +(len(negative)-1)*np.var(negative, ddof=1))/(len(positive)+len(negative)-2)
                    if pooled_variance > 0:
                        result['cohen_d'] = float((np.mean(positive)-np.mean(negative))
                                                  /np.sqrt(pooled_variance))
                        result['p_value'] = float(ttest_ind(positive, negative,
                            equal_var=False, alternative='two-sided').pvalue)
                        result['comparison_status'] = 'OK'
                    else:
                        result['comparison_status'] = 'INSUFFICIENT_DATA: pooled variance zero'
                elif award_inference_convention:
                    result['comparison_status'] = 'INSUFFICIENT_DATA: need two per award group'
        rows.append(dict(metric=metric, **result))
        if not curve.empty:
            curves[f'roc_{metric}'] = curve
    valid_tests = sum(row['comparison_status'] == 'OK' for row in rows)
    for row in rows:
        if row['comparison_status'] == 'OK':
            row['p_value_bonferroni'] = min(1., row['p_value']*valid_tests)
    category_rows = []
    if award_events is not None:
        invalid = set(award_events.award_category.dropna())-set(AWARD_CATEGORIES)
        if invalid or award_events[['author_id', 'award_category']].isna().any().any():
            raise ValueError(f'Unknown or missing award category: {sorted(invalid)}')
        if (award_events.evidence_reference.isna().any()
                or award_events.evidence_reference.astype(str).str.strip().eq('').any()):
            raise ValueError('Each award event requires an evidence reference')
        if award_events[['author_id', 'award_category']].duplicated().any():
            raise ValueError('Duplicate author/award-category event')
        cohort_events = award_events.loc[award_events.author_id.isin(merged.author_id)]
        labelled_awardees = set(merged.loc[merged.awardee.eq(1), 'author_id'])
        if not set(cohort_events.author_id) <= labelled_awardees:
            raise ValueError('Award events must agree with binary awardee labels')
        selected_ids = set(merged.loc[merged.nm_index.ge(
            merged.nm_index.dropna().quantile(.95)), 'author_id'])
        for category in AWARD_CATEGORIES:
            recipients = set(award_events.loc[
                award_events.award_category.eq(category), 'author_id'])
            category_rows.append(dict(award_category=category,
                cohort_awardees=len(recipients & set(merged.author_id)),
                top5_awardees=len(recipients & selected_ids),
                status='OK'))
    else:
        category_rows = [dict(award_category=category, cohort_awardees=np.nan,
            top5_awardees=np.nan, status='INPUT_DATA_REQUIRED')
            for category in AWARD_CATEGORIES]
    unavailable_baselines = bool(rows) and all(
        row['comparison_status'] == 'OK' or row.get('status') == 'INSUFFICIENT_DATA'
        for row in rows)
    overall = ('INPUT_DATA_REQUIRED' if award_events is None else
               'OK' if valid_tests and valid_tests == len(rows) else
               'OK_WITH_UNAVAILABLE_BASELINES' if valid_tests and unavailable_baselines else
               'INPUT_DATA_REQUIRED' if not valid_reference else
               'METHODOLOGY_PENDING' if not award_inference_convention else
               'INSUFFICIENT_DATA')
    return {'award_analysis': pd.DataFrame(rows),
            'award_category_counts': pd.DataFrame(category_rows), **curves,
            'status': pd.DataFrame([dict(status=overall,
                issue=('Some baseline formulas or values unavailable' if
                    overall == 'OK_WITH_UNAVAILABLE_BASELINES' else
                    '' if overall == 'OK' else
                    'Some award/reference/inference inputs unavailable'))])}
