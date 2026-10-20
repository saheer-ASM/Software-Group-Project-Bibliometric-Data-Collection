# Pre-Phase 5 state before audit

Recorded 2026-10-04 before audit corrections. The validation directory is **not
itself a Git repository** (`git status` reports “not a git repository”). The
sibling production repository was clean on branch
`update/author-checkpoint-20261001` at the start of this audit.

## Structure and files present

- Root: `README.md`, `requirements.txt`, `.gitignore`.
- `config/`: `config.example.env` and ignored local `config.env`.
- `src/`: `__init__.py`, `config.py`, `database.py`, `data_loader.py`,
  `inspect_schema.py`, `metric_mapping.py`, `metric_registry.py`,
  `test_connection.py`.
- `experiments/`: `__init__.py`, `inspect_author_coverage.py`.
- `metrics/`: `__init__.py`, `inputs.py`, `total_cites.py`, `h_index.py`.
- `tests/`: `test_database.py`, `test_inspection.py`.
- `source_documents/`: `Pasted markdown(7).md` and
  `Nm Index novel model (1).pdf`. The *named latest* manuscript
  `Nm Index novel model (1)(3).pdf` is absent at this point.
- `results/`: `.gitkeep`, `author_metric_coverage.csv`,
  `baseline_metric_specification.md`, `database_schema_report.csv`,
  `metric_availability.csv`, `metric_column_candidates.csv`,
  `metric_data_quality.csv`, `phase3_inspection_summary.json`,
  `phase3_mapping_report.md`, `phase3_schema_columns.csv`,
  `phase3_table_verification.csv`, `validation_dataset_preview.csv`.
- `figures/` and `logs/`: `.gitkeep` only; `.venv/` is local and ignored.

## Implementation status before audit

Phase 1–3 scaffolding, SELECT-only access and stored-value inspection exist.
`metrics/inputs.py`, `total_cites.py` and `h_index.py` are provisional Phase 4
scaffolding and have **not** been run as a pilot. The metric registry was also
created before the source documents arrived. There is no final baseline
dataset or Phase 5 experiment.

Current metric status from the prior specification: stored NM-index available
as an existing result; conventional Total Cites, h and g have explicit
definitions in the *previously available* documents, but only Total Cites and
h have provisional code. m has unresolved career-year conventions. Raw and
self-citation-adjusted C-score, conventional hm/hf, Fi, s and AR lack complete
rules in the previously available documents. **All statuses must be revisited
against the latest named manuscript before any Phase 5 work.**

## Known issues at audit start

1. The exact latest PDF filename in the audit request is missing locally, so
   manuscript-dependent comparison cannot yet be finalized.
2. README still calls the project a Phase 2 scaffold and says the design is not
   included; that is outdated.
3. The provisional registry still marks g as definition insufficient despite
   an explicit g formula in the experiment design and earlier manuscript.
4. The Phase 3 report and code-generated summary say the full design document
   is absent; those statements are stale now that the document is present.
5. Citation semantics and the authoritative author-publication relationship
   have not yet been checked against live row-level evidence. Current
   provisional code assumes the ten-slot contribution table is sufficient.
6. No unit tests exist yet for the provisional Total Cites/h calculators or
   portfolio preparation; existing tests cover Phase 2/3 safety and mapping.
7. The provisional code and source specification were prepared before this
   audit; they must not be used for calculations until the latest source and
   database audits are complete.
