"""RQ1 heatmap, scatter and paired difference plots."""

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from .core import save


def heatmap(matrix, directory, name):
    fig, ax = plt.subplots(figsize=(10, 6))
    values = np.ma.masked_invalid(matrix.to_numpy(dtype=float))
    cmap = plt.colormaps['coolwarm'].with_extremes(bad='#dddddd')
    im = ax.imshow(values, vmin=-1, vmax=1, cmap=cmap)
    ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=45, ha='right')
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    ax.set_title('Pairwise Pearson correlations (gray = unavailable)')
    fig.colorbar(im, ax=ax, label='Pearson r')
    return save(fig, directory, name)


def scatter(frame, first, second, directory, name):
    pair = frame[[first, second]].dropna()
    if pair.empty:
        raise ValueError('No paired values')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(pair[first], pair[second], alpha=.45, color='#0072B2', s=15)
    ax.set(xlabel=first, ylabel=second, title=f'{first} vs {second} (n={len(pair)})')
    return save(fig, directory, name)


def paired_difference(frame, first, second, directory, name):
    pair = frame[[first, second]].dropna()
    if pair.empty:
        raise ValueError('No paired values')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter((pair[first]+pair[second])/2, pair[first]-pair[second],
               alpha=.45, color='#D55E00', s=15)
    ax.axhline(0, color='black', linewidth=.8)
    ax.set(xlabel='Pair mean (raw units)', ylabel=f'{first} − {second} (raw units)',
           title=f'Paired difference (n={len(pair)}; scale interpretation pending)')
    return save(fig, directory, name)


def qq_plot(frame, metric, directory, name):
    values = np.asarray(frame[metric].dropna(), dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 3:
        raise ValueError('QQ plot requires at least three finite values')
    fig, ax = plt.subplots(figsize=(6, 4))
    stats.probplot(values, dist='norm', plot=ax)
    ax.set(xlabel='Theoretical normal quantile', ylabel=f'{metric} observed quantile',
           title=f'Normal QQ diagnostic: {metric} (n={len(values)})')
    return save(fig, directory, name)


def residual_plot(frame, x, directory, name):
    if frame.empty or x not in frame:
        raise ValueError('No residual data')
    fig, ax = plt.subplots(figsize=(6, 4))
    stages = sorted(frame.career_stage.dropna().unique())
    colors = ('#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00')
    for stage, color in zip(stages, colors):
        selected = frame.loc[frame.career_stage.eq(stage)]
        ax.scatter(selected[x], selected.residual, label=stage,
                   alpha=.55, color=color, s=16)
    ax.axhline(0, color='#333333', linewidth=.8)
    ax.set(xlabel='Fitted NM percentile' if x == 'fitted_nm_percentile'
           else 'Share of middle-author papers',
           ylabel='Observed NM percentile − fitted NM percentile',
           title='OLS residuals: NM percentile on C-score percentile')
    ax.legend(title='Career stage')
    return save(fig, directory, name)


def bland_altman_plot(pairs, summary, directory, name):
    if pairs.empty or summary.empty or summary.iloc[0].status != 'OK':
        raise ValueError('No approved Bland–Altman result')
    row = summary.iloc[0]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(pairs.pair_mean, pairs.difference, alpha=.45,
               color='#0072B2', s=15)
    ax.axhline(row.bias, color='#D55E00', label=f'Bias {row.bias:.2f}')
    ax.axhline(row.loa_lower, color='#009E73', linestyle='--',
               label=f'Lower LOA {row.loa_lower:.2f}')
    ax.axhline(row.loa_upper, color='#CC79A7', linestyle='--',
               label=f'Upper LOA {row.loa_upper:.2f}')
    ax.set(xlabel='Mean of NM and baseline percentiles',
           ylabel='NM percentile − baseline percentile',
           title=f'Bland–Altman: NM vs {row.baseline} (n={len(pairs)})')
    ax.legend()
    return save(fig, directory, name)


def difference_histogram(pairs, summary, directory, name):
    if pairs.empty or summary.empty or summary.iloc[0].status != 'OK':
        raise ValueError('No Bland–Altman differences')
    row = summary.iloc[0]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(pairs.difference, bins='auto', color='#0072B2', edgecolor='white')
    ax.axvline(row.bias, color='#D55E00', label='Bias')
    ax.set(xlabel='NM percentile − baseline percentile', ylabel='Authors',
           title=f'Difference distribution: {row.baseline}')
    ax.legend()
    return save(fig, directory, name)
