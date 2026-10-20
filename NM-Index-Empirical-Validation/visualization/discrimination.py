"""Award-label ROC curve."""

import matplotlib.pyplot as plt

from .core import save


def roc(curve, directory, name):
    if curve.empty:
        raise ValueError('No ROC points')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(curve.fpr, curve.tpr, color='#0072B2')
    ax.plot([0, 1], [0, 1], linestyle='--', color='gray')
    ax.set(xlabel='False positive rate', ylabel='True positive rate',
           title='Award-label ROC (supplied labels only)', xlim=(0, 1), ylim=(0, 1))
    return save(fig, directory, name)


def combined_roc(curves, award_analysis, directory, name):
    """Plot only observed ROC curves; AUC labels come from the analysis table."""
    order = ('nm_index', 'h_index', 'g_index', 'c_score_raw', 'raw_total_cites')
    colors = ('#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00')
    fig, ax = plt.subplots(figsize=(10, 6))
    count = 0
    for metric, color in zip(order, colors):
        curve = curves.get('roc_'+metric)
        result = award_analysis.loc[award_analysis.metric.eq(metric)]
        if curve is None or curve.empty or result.empty or result.iloc[0].status != 'OK':
            continue
        auc = result.iloc[0].auc
        ax.plot(curve.fpr, curve.tpr, color=color, label=f'{metric} (AUC={auc:.3f})')
        count += 1
    if not count:
        plt.close(fig)
        raise ValueError('No verified ROC results to plot')
    ax.plot([0, 1], [0, 1], linestyle='--', color='#666666', label='Chance')
    ax.set(xlabel='False positive rate', ylabel='True positive rate',
           title='Award prediction (verified supplied labels)', xlim=(0, 1), ylim=(0, 1))
    ax.legend(loc='lower right')
    return save(fig, directory, name)
