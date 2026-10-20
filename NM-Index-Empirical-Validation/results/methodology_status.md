# Methodology status

Unresolved items are explicit; no convention is selected by this file.

## c_score_raw — METHODOLOGY_PENDING

- Issue: Six indicators named; full construction, attribution and reference normalization absent.
- Sources: Nm Index novel model (1)(3).pdf pp. 3, 16-17, 24-25
- Required decision: Provide an explicit documented strategy matching the source and required inputs
- If unresolved: Metric remains NULL and is excluded from metric-specific analysis

## c_score_sc_adjusted — METHODOLOGY_PENDING

- Issue: Conventional C-score SC-adjustment equation absent; NM ISC is separate.
- Sources: Nm Index novel model (1)(3).pdf pp. 13, 26-29
- Required decision: Provide an explicit documented strategy matching the source and required inputs
- If unresolved: Metric remains NULL and is excluded from metric-specific analysis

## hm_index — METHODOLOGY_PENDING

- Issue: Original 1/Np rank mentioned; full threshold rule and worked values internally inconsistent.
- Sources: Nm Index novel model (1)(3).pdf pp. 2, 11, 23-25
- Required decision: Provide an explicit documented strategy matching the source and required inputs
- If unresolved: Metric remains NULL and is excluded from metric-specific analysis

## hf_index — READY_INPUT_GATED

- Issue: Latest-PDF conventional c_p/N_p formula implemented; ten database slots do not prove complete coauthor count.
- Sources: Nm Index novel model (1)(3).pdf pp. 2, 22-25
- Required decision: Independently verify N_p for every real paper before enabling real hf calculation
- If unresolved: Synthetic fixture calculates hf; real/pilot hf remains NULL

## m_index — METHODOLOGY_PENDING

- Issue: Explicit career-duration convention required.
- Sources: Pasted markdown(7).md, baseline table lines 30-41; Nm Index novel model (1)(3).pdf pp. 2, 22
- Required decision: Provide an explicit documented strategy matching the source and required inputs
- If unresolved: Metric remains NULL and is excluded from metric-specific analysis

## fi_score — METHODOLOGY_PENDING

- Issue: Equation and threshold absent.
- Sources: Pasted markdown(7).md, baseline table lines 30-41; Nm Index novel model (1)(3).pdf p. 2
- Required decision: Provide an explicit documented strategy matching the source and required inputs
- If unresolved: Metric remains NULL and is excluded from metric-specific analysis

## s_index — METHODOLOGY_PENDING

- Issue: Brown b-index reference conflicts with s-index label.
- Sources: Pasted markdown(7).md, baseline table lines 30-41; Nm Index novel model (1)(3).pdf p. 2
- Required decision: Provide an explicit documented strategy matching the source and required inputs
- If unresolved: Metric remains NULL and is excluded from metric-specific analysis

## ar_index — METHODOLOGY_PENDING

- Issue: Age-weighting formula absent.
- Sources: Pasted markdown(7).md, baseline table lines 30-41; Nm Index novel model (1)(3).pdf p. 2
- Required decision: Provide an explicit documented strategy matching the source and required inputs
- If unresolved: Metric remains NULL and is excluded from metric-specific analysis

## rq03 — METHODOLOGY_PENDING

- Issue: ICC form/model and score scale are not fixed
- Sources: Pasted markdown(7).md, RQ03 section; latest NM manuscript §3.4
- Required decision: Choose ICC model and any approved scale transformation
- If unresolved: Experiment emits explicit pending status, not an empirical result

## rq04 — METHODOLOGY_PENDING

- Issue: Award labels are absent from current database
- Sources: Pasted markdown(7).md, RQ04 section; latest NM manuscript §3.4
- Required decision: Supply verified awardee/non-awardee labels
- If unresolved: Experiment emits explicit pending status, not an empirical result

## rq05 — METHODOLOGY_PENDING

- Issue: Scenario definitions and covariate design are incomplete
- Sources: Pasted markdown(7).md, RQ05 section; latest NM manuscript §3.4
- Required decision: Supply observed scenario variables and prespecified regression covariates
- If unresolved: Experiment emits explicit pending status, not an empirical result

## rq06 — METHODOLOGY_PENDING

- Issue: Annual NM and C-score histories are not present
- Sources: Pasted markdown(7).md, RQ06 section; latest NM manuscript §3.4
- Required decision: Supply historical score snapshots and representative author
- If unresolved: Experiment emits explicit pending status, not an empirical result

## rq07 — METHODOLOGY_PENDING

- Issue: Stored production NM cannot be recomputed under counterfactuals here
- Sources: Pasted markdown(7).md, RQ07 section; latest NM manuscript §3.4
- Required decision: Approve counterfactual NM procedure and complete self-citation/coauthor inputs
- If unresolved: Experiment emits explicit pending status, not an empirical result

## rq08 — METHODOLOGY_PENDING

- Issue: Historical t scores and t+1..t+5 outcomes are not present
- Sources: Pasted markdown(7).md, RQ08 section; latest NM manuscript §3.4
- Required decision: Supply time-stamped score and outcome cohorts
- If unresolved: Experiment emits explicit pending status, not an empirical result

## rq09 — METHODOLOGY_PENDING

- Issue: Adjacent-year metric score snapshots are not present
- Sources: Pasted markdown(7).md, RQ09 section; latest NM manuscript §3.4
- Required decision: Supply annual score snapshots
- If unresolved: Experiment emits explicit pending status, not an empirical result

## rq11 — METHODOLOGY_PENDING

- Issue: Approved gender/region labels are not present
- Sources: Pasted markdown(7).md, RQ11 section; latest NM manuscript §3.4
- Required decision: Supply approved subgroup labels; no automatic inference
- If unresolved: Experiment emits explicit pending status, not an empirical result

## sensitivity — METHODOLOGY_PENDING

- Issue: Alternate NM career/ISC parameters require an approved counterfactual NM calculation path
- Sources: Pasted markdown(7).md, SENSITIVITY section; latest NM manuscript §3.4
- Required decision: Approve a separate local parameter-sensitivity strategy; do not alter stored production scores
- If unresolved: Experiment emits explicit pending status, not an empirical result

## g_index_example — READY_WITH_EXAMPLE_CONFLICT

- Issue: Five displayed papers produce g=5 under written definition; manuscript reports g=12
- Sources: Pasted markdown(7).md line 37; latest NM manuscript pp. 2, 19, 23, 25
- Required decision: Clarify zero-padding, omitted papers, or example correction
- If unresolved: Written top-g-papers rule is implemented; manuscript example cannot be used as fixture
