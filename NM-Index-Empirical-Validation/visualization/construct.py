"""PCA scree and loading figures."""

import matplotlib.pyplot as plt

from .core import save


def scree(explained_variance, directory, name):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(range(1, len(explained_variance)+1), explained_variance, marker='o')
    ax.set(xlabel='Principal component', ylabel='Explained variance proportion',
           title='PCA explained variance')
    return save(fig, directory, name)


def loadings(frame, directory, name):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.imshow(frame.drop(columns='component').to_numpy(dtype=float), cmap='coolwarm', vmin=-1, vmax=1)
    ax.set_xticks(range(len(frame.columns)-1), frame.columns[1:])
    ax.set_yticks(range(len(frame)), frame.component)
    ax.set_title('PCA loadings of six stored raw NM components')
    return save(fig, directory, name)
