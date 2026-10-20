"""Names of six stored component percentiles; never recompute them here."""

from .loader import COMPONENT_COLUMNS

LABELS = dict(zip(COMPONENT_COLUMNS,
                  ('T_a', 'S_a', 'U_a', "Hf'_a", "Hm'_a", "G'_a")))
