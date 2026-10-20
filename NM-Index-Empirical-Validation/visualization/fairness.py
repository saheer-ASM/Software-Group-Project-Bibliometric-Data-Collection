"""Approved-label subgroup mean comparison."""

import matplotlib.pyplot as plt

from .core import save


def subgroup_means(frame, directory, name, *, metric='nm_index', dimension='gender'):
    valid = frame.loc[frame.status == 'OK']
    if 'metric' in valid:
        valid = valid.loc[valid.metric == metric]
    if 'dimension' in valid:
        valid = valid.loc[valid.dimension == dimension]
    if valid.empty:
        raise ValueError('No approved subgroup results')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(valid.group, valid['mean'], color='#56B4E9')
    ax.set(xlabel='Supplied subgroup', ylabel='Mean percentile',
           title=f'{metric} by {dimension} (supplied labels; n={int(valid.n.sum())})')
    return save(fig, directory, name)
