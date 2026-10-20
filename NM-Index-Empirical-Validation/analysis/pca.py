"""RQ10 PCA on six stored component percentiles with complete-case policy."""

import numpy as np
import pandas as pd


def analyze(frame, columns):
    if len(columns) != 6 or any(c not in frame for c in columns):
        return dict(status='INVALID_INPUT', issue='Exactly six stored components required'), pd.DataFrame()
    complete = frame[list(columns)].apply(pd.to_numeric, errors='coerce').replace(
        [np.inf, -np.inf], np.nan).dropna()
    n = len(complete)
    if n < 7:
        return dict(status='INSUFFICIENT_DATA', n=n), pd.DataFrame()
    x = complete.to_numpy(dtype=float)
    sd = x.std(axis=0, ddof=1)
    if np.any(sd <= 0):
        return dict(status='INVALID_INPUT', n=n, issue='Constant component'), pd.DataFrame()
    x = (x-x.mean(axis=0))/sd
    _, singular, vectors = np.linalg.svd(x, full_matrices=False)
    eigenvalues = singular**2/(n-1)
    explained = eigenvalues/eigenvalues.sum()
    loadings = vectors.T * np.sqrt(eigenvalues)
    result = pd.DataFrame(loadings, index=columns, columns=[f'PC{i}' for i in range(1, 7)]).reset_index(names='component')
    rank = int(np.linalg.matrix_rank(x))
    return dict(status='OK', n=n, preprocessing='complete_case_z_standardization',
                effective_rank=rank,
                note='Rank deficient input; zero-variance trailing PCs reflect redundancy' if rank < 6 else '',
                explained_variance=explained.tolist(), cumulative_variance=np.cumsum(explained).tolist()), result
