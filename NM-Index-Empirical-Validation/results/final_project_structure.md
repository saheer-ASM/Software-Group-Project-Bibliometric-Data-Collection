# Final project structure

This inventory describes the isolated validation project after the offline synthetic run. `config/config.env` is local and excluded from this inventory because it contains connection settings. No file from the production bibliometric project is part of this tree.

```text
NM-Index-Empirical-Validation/
├── README.md, requirements.txt, .gitignore
├── config/                 config.example.env; local ignored config.env
├── source_documents/       Pasted markdown(7).md; Nm Index novel model (1)(3).pdf
├── src/                    configuration, read-only adapter, data loader/model,
│                           quality, eligibility, pipeline, provenance, mock repository
├── nm_index/               stored NM-index loader, component mapping, provenance
├── metrics/                baseline calculators and pending-method strategy interfaces
├── analysis/               reusable statistical analysis functions
├── experiments/            RQ01–RQ11 and sensitivity orchestration
├── visualization/          figure generation and synthetic-data marking
├── tests/                  unit/integration/safety tests and synthetic fixtures
├── inputs/                 external-input schema documentation
├── reports/                report templates
├── results/                methodology/specification/audit documents,
│   ├── run_metadata.json   latest synthetic run metadata snapshot
│   └── run_20261005T050206029193Z/
│       ├── reports/         six generated reports
│       └── *.csv/json/md/txt  synthetic datasets, statuses, metadata
├── figures/
│   └── run_20261005T050206029193Z/  23 synthetic figures
├── logs/
└── run_validation.py       dry-run, mock, gated read-only database CLI
```

The database adapter is confined to `src/database.py` and the data loader. Metric and experiment modules operate on in-memory data. The latest run directory contains 40 top-level artifacts plus six reports, and the corresponding figure directory contains 23 PNG files. Run-specific metadata is authoritative; `results/run_metadata.json` is a convenience snapshot.

Historical Phase 0–5 audit and inspection scripts/reports remain as traceable records. The active experiment path uses `run_validation.py` and `src/pipeline.py`; no alternate production calculation runner was added.
