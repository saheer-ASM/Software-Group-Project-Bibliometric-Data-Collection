"""Shared publication-scale figure export."""

import os
from pathlib import Path

from src.config import PROJECT_ROOT

# Keep Matplotlib's writable font cache within the isolated validation project.
_cache = PROJECT_ROOT/'.cache'/'matplotlib'
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(_cache))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'serif'


def save(fig, directory, name):
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    if '/' in name or '\\' in name or not name.endswith('.png'):
        raise ValueError('Figure name must be a simple PNG filename')
    path = folder/name
    if path.exists():
        raise FileExistsError(f'Figure already exists: {path}')
    classification_file = PROJECT_ROOT/'results'/folder.name/'DATA_CLASSIFICATION.txt'
    if folder.parent.resolve() == (PROJECT_ROOT/'figures').resolve() and classification_file.is_file():
        classification = classification_file.read_text(encoding='utf-8').strip()
        fig.text(.5, .01, classification, ha='center', va='bottom', fontsize=8,
                 color='#a00000' if classification.startswith('SYNTHETIC') else '#555555')
        fig.tight_layout(rect=(0, .04, 1, 1))
    else:
        fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return path
