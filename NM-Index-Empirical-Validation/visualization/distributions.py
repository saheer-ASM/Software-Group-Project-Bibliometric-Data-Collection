"""Metric and NM distribution plots."""

import matplotlib.pyplot as plt
import pandas as pd

from .core import save


def histogram(frame, column, directory, name):
    values = pd.to_numeric(frame[column], errors='coerce').dropna()
    if values.empty:
        raise ValueError('No finite metric values')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(values, bins='auto', color='#0072B2', edgecolor='white')
    ax.set(xlabel=f'{column} (score/count units)', ylabel='Authors',
           title=f'{column} distribution (n={len(values)})')
    return save(fig, directory, name)
