"""Annual score trajectories."""

import matplotlib.pyplot as plt

from .core import save


def trajectory(frame, columns, directory, name):
    if frame.empty:
        raise ValueError('No annual scores')
    fig, ax = plt.subplots(figsize=(10, 6))
    for col in columns:
        ax.plot(frame.year, frame[col], marker='o', label=col)
    ax.set(xlabel='Year (publication count recorded in CSV)', ylabel='Normalized score (0–1)',
           title=f'Observed annual trajectory (n={len(frame)} years; explicit convention)')
    ax.legend()
    return save(fig, directory, name)
