"""PNG plotting helpers with cache confined to this validation project."""

import os

from src.config import PROJECT_ROOT

_cache = PROJECT_ROOT/'.cache'/'matplotlib'
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(_cache))
