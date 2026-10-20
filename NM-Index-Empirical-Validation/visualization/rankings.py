"""Rank comparison plots."""

import matplotlib.pyplot as plt

from .core import save


def compare(frame, first, second, directory, name):
    pair = frame[[first, second]].dropna()
    if pair.empty:
        raise ValueError('No paired values')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(pair[first].rank(ascending=False), pair[second].rank(ascending=False),
               color='#009E73', alpha=.5, s=15)
    ax.set(xlabel=f'{first} rank', ylabel=f'{second} rank',
           title=f'Author rank comparison (n={len(pair)})')
    return save(fig, directory, name)
