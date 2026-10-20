"""Local provenance records for every baseline and the stored target."""

import pandas as pd

from .metric_registry import REGISTRY


def metric_provenance(activated=None):
    activated = activated or {}
    return pd.DataFrame([dict(metric=m.metric_name, source=m.source,
                              source_table=('author_nm_index' if m.metric_name == 'nm_index' else
                                            'publication' if m.implementation_status in {'READY', 'READY_INPUT_GATED'} else 'UNRESOLVED'),
                              source_column=('nm_index' if m.metric_name == 'nm_index' else
                                             'total_citation' if m.implementation_status in {'READY', 'READY_INPUT_GATED'} else 'UNRESOLVED'),
                              input_tables=';'.join(sorted({x.split('.')[0] for x in m.required_inputs if '.' in x})),
                              calculation_module=m.calculation_module,
                              definition_reference=m.definition_reference,
                              strategy_reference=getattr(activated.get(m.metric_name), 'reference', ''),
                              approval_reference=getattr(activated.get(m.metric_name), 'approval_reference', ''),
                              assumptions=m.assumptions,
                              status=('APPROVED_STRATEGY_SUPPLIED' if m.metric_name in activated else m.implementation_status))
                         for m in REGISTRY])
