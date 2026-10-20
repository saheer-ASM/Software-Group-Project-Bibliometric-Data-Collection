"""Sample-size and scenario sensitivity plots."""

import matplotlib.pyplot as plt
import pandas as pd

from .core import save


def sensitivity(frame, x, y, directory, name):
    valid = frame[[x, y]].dropna()
    if valid.empty:
        raise ValueError('No valid sensitivity values')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(valid[x], valid[y], marker='o', color='#CC79A7')
    ax.set(xlabel=x, ylabel=y, title=f'Sample-size robustness (n={len(valid)} sizes)')
    return save(fig, directory, name)


def gaming_percentile_pairs(frame, directory, name):
    """Compare original and graph-recalculated NM percentiles by scenario."""
    required = {'scenario', 'status', 'original_nm_percentile', 'manipulated_nm_percentile'}
    if not required <= set(frame):
        raise ValueError('RQ7 percentile pair columns missing')
    valid = frame.loc[frame.status.eq('OK')].copy()
    valid['original_nm_percentile'] = pd.to_numeric(valid.original_nm_percentile, errors='coerce')
    valid['manipulated_nm_percentile'] = pd.to_numeric(valid.manipulated_nm_percentile, errors='coerce')
    valid = valid.dropna(subset=['original_nm_percentile', 'manipulated_nm_percentile'])
    if valid.empty:
        raise ValueError('No valid graph-recalculated RQ7 percentile pairs')
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0, 100], [0, 100], linestyle='--', color='#777777', linewidth=1)
    for scenario, part in valid.groupby('scenario'):
        ax.scatter(part.original_nm_percentile, part.manipulated_nm_percentile,
                   label=f'{scenario} (n={len(part)})', alpha=.8, s=28)
    ax.set(xlim=(0, 100), ylim=(0, 100), xlabel='Original NM percentile',
           ylabel='Counterfactual NM percentile', title='RQ7 graph-recalculated NM')
    ax.legend(fontsize=7)
    return save(fig, directory, name)
