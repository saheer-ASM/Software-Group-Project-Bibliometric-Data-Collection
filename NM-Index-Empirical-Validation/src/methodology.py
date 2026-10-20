"""Machine-readable unresolved source decisions; no implicit method choice."""

import json

from .config import PROJECT_ROOT
from .metric_registry import REGISTRY


EXPERIMENT_ISSUES = {
    'rq03': ('ICC form/model and score scale are not fixed', 'Choose ICC model and any approved scale transformation'),
    'rq04': ('Award labels are absent from current database', 'Supply verified awardee/non-awardee labels'),
    'rq05': ('Scenario definitions and covariate design are incomplete', 'Supply observed scenario variables and prespecified regression covariates'),
    'rq06': ('Annual NM and C-score histories are not present', 'Supply historical score snapshots and representative author'),
    'rq07': ('Stored production NM cannot be recomputed under counterfactuals here', 'Approve counterfactual NM procedure and complete self-citation/coauthor inputs'),
    'rq08': ('Historical t scores and t+1..t+5 outcomes are not present', 'Supply time-stamped score and outcome cohorts'),
    'rq09': ('Adjacent-year metric score snapshots are not present', 'Supply annual score snapshots'),
    'rq11': ('Approved gender/region labels are not present', 'Supply approved subgroup labels; no automatic inference'),
    'sensitivity': ('Alternate NM career/ISC parameters require an approved counterfactual NM calculation path',
                    'Approve a separate local parameter-sensitivity strategy; do not alter stored production scores'),
}


def records():
    rows = []
    for metric in REGISTRY:
        if metric.implementation_status == 'METHODOLOGY_PENDING':
            rows.append(dict(name=metric.metric_name, issue=metric.assumptions,
                source_references=metric.definition_reference,
                current_implementation_status=metric.implementation_status,
                required_decision='Provide an explicit documented strategy matching the source and required inputs',
                effect_if_unresolved='Metric remains NULL and is excluded from metric-specific analysis'))
        elif metric.metric_name == 'hf_index':
            rows.append(dict(name='hf_index',
                issue='Latest-PDF conventional c_p/N_p formula implemented; ten database slots do not prove complete coauthor count.',
                source_references=metric.definition_reference,
                current_implementation_status='READY_INPUT_GATED',
                required_decision='Independently verify N_p for every real paper before enabling real hf calculation',
                effect_if_unresolved='Synthetic fixture calculates hf; real/pilot hf remains NULL'))
    for name, (issue, decision) in EXPERIMENT_ISSUES.items():
        rows.append(dict(name=name, issue=issue,
            source_references='Pasted markdown(7).md, '+name.upper()+' section; latest NM manuscript §3.4',
            current_implementation_status='METHODOLOGY_PENDING',
            required_decision=decision,
            effect_if_unresolved='Experiment emits explicit pending status, not an empirical result'))
    rows.append(dict(name='g_index_example', issue='Five displayed papers produce g=5 under written definition; manuscript reports g=12',
        source_references='Pasted markdown(7).md line 37; latest NM manuscript pp. 2, 19, 23, 25',
        current_implementation_status='READY_WITH_EXAMPLE_CONFLICT',
        required_decision='Clarify zero-padding, omitted papers, or example correction',
        effect_if_unresolved='Written top-g-papers rule is implemented; manuscript example cannot be used as fixture'))
    return rows


def write_status():
    rows = records()
    folder = PROJECT_ROOT/'results'
    (folder/'methodology_status.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    lines = ['# Methodology status', '', 'Unresolved items are explicit; no convention is selected by this file.', '']
    for row in rows:
        lines += [f"## {row['name']} — {row['current_implementation_status']}", '',
                  f"- Issue: {row['issue']}", f"- Sources: {row['source_references']}",
                  f"- Required decision: {row['required_decision']}",
                  f"- If unresolved: {row['effect_if_unresolved']}", '']
    (folder/'methodology_status.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    write_status()
