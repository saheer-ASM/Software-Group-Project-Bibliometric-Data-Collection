"""RQ4 award-label ROC/AUC; no labels are inferred or fabricated."""

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu


def roc_auc(frame, score, label, *, seed=2026, bootstrap=500):
    if score not in frame or label not in frame:
        return dict(status='INVALID_INPUT', issue='Score or externally supplied award label missing'), pd.DataFrame()
    pair = frame[[score, label]].replace([np.inf, -np.inf], np.nan).dropna()
    if not pair[label].isin([0, 1, False, True]).all():
        return dict(status='INVALID_INPUT', issue='Award labels must be binary'), pd.DataFrame()
    y = pair[label].astype(int).to_numpy()
    x = pd.to_numeric(pair[score], errors='coerce').to_numpy(dtype=float)
    valid = np.isfinite(x)
    y, x = y[valid], x[valid]
    if len(x) < 4 or len(set(y)) < 2:
        return dict(status='INSUFFICIENT_DATA', n=len(x)), pd.DataFrame()
    positives, negatives = x[y == 1], x[y == 0]
    auc = float(mannwhitneyu(positives, negatives, alternative='two-sided').statistic /
                (len(positives)*len(negatives)))
    thresholds = np.r_[np.inf, np.sort(np.unique(x))[::-1]]
    curve = pd.DataFrame([dict(threshold=t, tpr=float((positives >= t).mean()),
                               fpr=float((negatives >= t).mean())) for t in thresholds])
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(bootstrap):
        a = rng.choice(positives, len(positives), replace=True)
        b = rng.choice(negatives, len(negatives), replace=True)
        draws.append(mannwhitneyu(a, b).statistic/(len(a)*len(b)))
    return dict(status='OK', n=len(x), positives=len(positives), negatives=len(negatives),
                auc=auc, ci_low=float(np.quantile(draws, .025)),
                ci_high=float(np.quantile(draws, .975))), curve
