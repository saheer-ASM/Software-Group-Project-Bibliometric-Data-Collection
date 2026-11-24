"""RQ10 PCA on six stored component percentiles with complete-case policy."""

import numpy as np
import pandas as pd


def varimax(loadings, iterations=100, tol=1e-8):
    """Kaiser (1958) varimax with row normalisation, by pairwise planar rotations
    (no saddle-point stall when the unrotated loadings are symmetric)."""
    a = np.array(loadings, dtype=float)
    h = np.sqrt((a**2).sum(axis=1, keepdims=True))
    h[h == 0] = 1
    a = a / h
    p, k = a.shape
    for _ in range(iterations):
        changed = False
        for i in range(k - 1):
            for j in range(i + 1, k):
                x, y = a[:, i], a[:, j]
                u, v = x**2 - y**2, 2 * x * y
                num = 2 * (p * (u * v).sum() - u.sum() * v.sum())
                den = p * (u**2 - v**2).sum() - (u.sum()**2 - v.sum()**2)
                phi = np.arctan2(num, den) / 4
                if abs(phi) > tol:
                    c, s_ = np.cos(phi), np.sin(phi)
                    a[:, i], a[:, j] = c * x + s_ * y, -s_ * x + c * y
                    changed = True
        if not changed:
            break
    return a * h


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
    # Kaiser criterion (eigenvalue > 1), then varimax rotation of the kept PCs
    kept = max(1, int((eigenvalues > 1).sum()))
    rotated = varimax(loadings[:, :kept]) if kept > 1 else loadings[:, :kept]
    for j in range(kept):
        result[f'RC{j + 1}'] = rotated[:, j]
    return dict(status='OK', n=n, preprocessing='complete_case_z_standardization',
                effective_rank=rank, components_kept=kept, rotation='varimax',
                note='Rank deficient input; zero-variance trailing PCs reflect redundancy' if rank < 6 else '',
                explained_variance=explained.tolist(), cumulative_variance=np.cumsum(explained).tolist()), result
