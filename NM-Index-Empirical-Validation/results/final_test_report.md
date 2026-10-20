# Final offline test report

**Scope:** isolated validation software, using synthetic test data only. No empirical conclusions are drawn from this run. Latest full mock run: `run_20261005T050206029193Z` (12 authors, 60 publications, 23 PNG figures, 40 top-level result artifacts and six generated reports). All generated CSVs, figures, reports and metadata are marked **SYNTHETIC TEST DATA — NOT EMPIRICAL RESULTS**.

| Check | Status | Evidence and limit |
|---|---|---|
| Unit and metric tests | PASS | Offline suite: 40 tests passed. Approved Total Cites, h-index and g-index have independently checked expected values, including edge cases. Eight undefined or decision-dependent baseline columns remain null with explicit status. |
| Integration and validation-dataset tests | PASS | Full synthetic repository-to-report pipeline completed; one row per author, IDs are stable, provenance, coverage and exclusion information exported. |
| Mock pipeline | PASS | `python run_validation.py --data-source mock --all` completed without PostgreSQL access. RQ01–RQ11 and sensitivity each produced a status; no pending method was silently replaced. |
| Statistical tests | PASS | Implemented statistical routines were exercised, including numeric/empty-input guards. This does not validate unresolved methods or real-data assumptions. |
| Visualization tests | PASS | 23 labelled PNGs were generated. A subgroup figure was opened and inspected for legibility and synthetic watermark. |
| Report generation | PASS | Executive summary, methodology, data quality, metric results, statistical results and limitations were generated in the run's `reports/` directory. |
| CLI tests | PASS | Dry-run, mock and individual experiment routes tested. Real-database route rejects missing readiness/citation/portfolio references before connection. |
| SQL safety and credential tests | PASS | Unit tests reject write SQL and redact connection errors. Static search found no reachable write-SQL path; `src/test_connection.py` contains a negative safety probe that the SELECT guard rejects before connection. No credentials were printed or copied into reports. |
| Production isolation | PASS | The production repository reported a clean `git status --short`; no production code or database was touched during this task. |
| Syntax and imports | PASS | All project Python files compiled and project modules imported in the offline verification. |
| Real database and empirical validation | SKIPPED | Deliberately not connected or run; population/readiness has not been established. |
| Method-dependent metrics and RQs | METHODOLOGY_PENDING | C-score raw/adjusted, hm, hf, m, Fi, s, AR and portions of RQ01, RQ03–RQ07, RQ09 and RQ11 await documented definitions/decisions. See run metadata and methodology documents for exact statuses. |
| Real-world external inputs | DATA_REQUIRED | Verified portfolio, approved outcomes/subgroup labels, historical snapshots and complete citation source must be supplied before corresponding real-data analyses. Synthetic fixtures only test interfaces. |

The mock `experiment_status` values are: RQ02, RQ08 and RQ10 `OK`; RQ06 `OK_WITH_EXPLICIT_CONVENTION`; RQ01, RQ03, RQ04, RQ05, RQ07, RQ09 and RQ11 `METHODOLOGY_PENDING`; supplementary sensitivity `INSUFFICIENT_DATA`. These are software-test statuses and do not imply publishable empirical results. Per-RQ input matching is exported separately from full methodological eligibility.

Source files were checked by SHA-256 and were not edited: experiment design `0ec5857ff77d449ac9fb6ea131ebb7ce9755ce411af14e309dce478316896b8a`; latest NM manuscript `3bffd57d10b334bf4e37d437bf6babe6a9ae333cada1e6102be9181539ebdb91`. No SQL, migration, production calculation runner, commit or push was executed.
