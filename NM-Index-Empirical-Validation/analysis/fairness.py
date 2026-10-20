"""RQ11 subgroup analysis on externally supplied, approved labels only."""

import numpy as np
import pandas as pd
from scipy.stats import t as student_t
from dataclasses import dataclass


@dataclass(frozen=True)
class FairnessConvention:
    """Explicit, externally approved operational choices absent from the design."""

    cohen_d_denominator: str
    regional_variance_ddof: int
    source_reference: str

    def __post_init__(self):
        if self.cohen_d_denominator != 'pooled_sample_sd' or self.regional_variance_ddof not in (0, 1):
            raise ValueError('Unsupported fairness effect convention')
        if not self.source_reference.strip():
            raise ValueError('Fairness convention requires a decision reference')


def compare_percentiles(frame, metric_columns, convention):
    """Gender and regional analyses on supplied percentiles, never inferred labels."""
    if not isinstance(convention, FairnessConvention):
        raise ValueError('METHODOLOGY_PENDING: explicit FairnessConvention required')
    if not {'gender', 'region'} <= set(frame):
        return (pd.DataFrame(), pd.DataFrame([dict(status='DATA_REQUIRED',
            issue='Approved gender and region labels required')]))
    group_rows, effects = [], []
    for metric in metric_columns:
        column = f'{metric}_percentile'
        if column not in frame or frame[column].isna().all():
            effects.append(dict(metric=metric, status='METHODOLOGY_PENDING',
                                issue='Supplied reference-population percentile unavailable'))
            continue
        values = pd.to_numeric(frame[column], errors='coerce').replace([np.inf, -np.inf], np.nan)
        if values.dropna().lt(0).any() or values.dropna().gt(100).any():
            effects.append(dict(metric=metric, status='INVALID_INPUT',
                                issue='Percentiles must be in [0,100]'))
            continue
        source = frame[['gender', 'region']].copy()
        source['value'] = values
        for dimension in ('gender', 'region'):
            for label, part in source.dropna(subset=[dimension, 'value']).groupby(dimension, sort=True):
                arr = part.value.to_numpy(dtype=float)
                n = len(arr)
                sd = float(np.std(arr, ddof=1)) if n > 1 else np.nan
                half = float(student_t.ppf(.975, n-1)*sd/np.sqrt(n)) if n > 1 else np.nan
                group_rows.append(dict(status='OK', dimension=dimension, group=label,
                    metric=metric, n=n, mean=float(arr.mean()), median=float(np.median(arr)),
                    sd=sd, ci_low=float(arr.mean()-half), ci_high=float(arr.mean()+half),
                    unit='percentile points', convention_reference=convention.source_reference))
        gender = source.dropna(subset=['gender', 'value'])
        male = gender.loc[gender.gender == 'Male', 'value'].to_numpy(dtype=float)
        female = gender.loc[gender.gender == 'Female', 'value'].to_numpy(dtype=float)
        if len(male) >= 2 and len(female) >= 2:
            pooled_var = ((len(male)-1)*np.var(male, ddof=1)
                          +(len(female)-1)*np.var(female, ddof=1))/(len(male)+len(female)-2)
            d = float((male.mean()-female.mean())/np.sqrt(pooled_var)) if pooled_var > 0 else np.nan
            effects.append(dict(status='OK' if np.isfinite(d) else 'INVALID_INPUT',
                metric=metric, dimension='gender', effect='cohen_d_male_minus_female',
                n=len(male)+len(female), value=d, convention_reference=convention.source_reference))
        else:
            effects.append(dict(status='INSUFFICIENT_DATA', metric=metric,
                dimension='gender', effect='cohen_d_male_minus_female',
                n=len(male)+len(female), convention_reference=convention.source_reference))
        regions = source.dropna(subset=['region', 'value']).groupby('region').value.mean()
        if len(regions) >= 2:
            effects.append(dict(status='OK', metric=metric, dimension='region',
                effect='variance_of_region_mean_percentiles', n=int(source.value.notna().sum()),
                group_count=len(regions), value=float(regions.var(ddof=convention.regional_variance_ddof)),
                convention_reference=convention.source_reference))
        else:
            effects.append(dict(status='INSUFFICIENT_DATA', metric=metric,
                dimension='region', effect='variance_of_region_mean_percentiles',
                n=int(source.value.notna().sum()), convention_reference=convention.source_reference))
    return pd.DataFrame(group_rows), pd.DataFrame(effects)


def subgroup(frame, metric, group_column, *, approved_labels=False):
    if not approved_labels:
        return pd.DataFrame([dict(status='METHODOLOGY_PENDING', issue='No demographic inference; approved labels required')])
    if metric not in frame or group_column not in frame:
        return pd.DataFrame([dict(status='INVALID_INPUT', issue='Metric or group labels absent')])
    clean = frame[[metric, group_column]].copy()
    clean[metric] = pd.to_numeric(clean[metric], errors='coerce')
    clean = clean.replace([np.inf, -np.inf], np.nan).dropna()
    rows = []
    for label, group in clean.groupby(group_column, sort=True):
        n = len(group)
        mean = float(group[metric].mean())
        sd = float(group[metric].std(ddof=1)) if n > 1 else np.nan
        half = student_t.ppf(.975, n-1)*sd/np.sqrt(n) if n > 1 else np.nan
        rows.append(dict(status='OK', group=label, metric=metric, n=n,
                         mean=mean, median=float(group[metric].median()), sd=sd,
                         ci_low=mean-half, ci_high=mean+half))
    if len(rows) < 2:
        return pd.DataFrame([dict(status='INSUFFICIENT_DATA', issue='At least two nonempty groups required')])
    result = pd.DataFrame(rows)
    result.attrs['variance_of_group_means'] = float(result['mean'].var(ddof=1))
    if len(rows) == 2:
        first, second = rows
        denominator = first['n']+second['n']-2
        pooled = np.sqrt(((first['n']-1)*first['sd']**2+(second['n']-1)*second['sd']**2)/denominator) if denominator > 0 else np.nan
        result.attrs['cohen_d_first_minus_second'] = (first['mean']-second['mean'])/pooled if pooled > 0 else np.nan
    return result
