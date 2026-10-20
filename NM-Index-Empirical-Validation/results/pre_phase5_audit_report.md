# Pre-Phase 5 audit findings and corrections

Read the current experiment design and the **39-page** latest manuscript
`Nm Index novel model (1)(3).pdf` in full. The older manuscript was excluded
from the current source review. No metric or statistical calculation was run.

## Issues found and fixed within this validation project

| Issue found | Correction |
|---|---|
| README described a Phase 2 scaffold and claimed the design was absent. | README now names the latest source pair, current phases, pilot limits and audit reports. |
| Baseline specification cited the older 32-page manuscript and its obsolete example values/page locations. | Specification now points to the latest 39-page manuscript and its `Hf′≈0.545`, `Nm≈39.67` detailed example, with conflict notes. |
| Provisional metric registry marked conventional g as definition-insufficient despite an explicit design/manuscript rule; it also said the full design was unavailable. | Registry now records the explicit g definition separately from unimplemented status and the contradictory example, and cites the current sources for all comparators. |
| Existing Phase 3 report generator claimed the design document was absent. | Future Phase 3 report generation points to the current specification; old Phase 3 outputs remain historical snapshots. |
| Phase 3 mapping notes told readers to confirm a design no longer absent. | Wording now directs readers to the current specification without implying any stored conventional baseline was found. |
| No reproducible input/citation semantics audit existed. | Added a SELECT-only fixed-column audit module, a 95-column table map and deterministic citation sample. |
| No audit-specific tests covered registry source status, SQL audit queries and local config. | Added three offline contract tests; all safe tests pass. |
| The environment used to read the latest PDF depended on an undeclared reader. | Added `pypdf` to the isolated validation requirements. |

## Material findings intentionally deferred

- The current database has 2,507 authors, 56,768 publication rows and 52,370
  citation-edge rows. Only 816 publications have an author-contribution row;
  those rows link 2,340 authors, leaving 167 authors without that lookup.
  This blocks full-career baselines from the current wide table alone.
- `publication.total_citation` is present and non-NULL on every publication,
  but the count of `citation` rows where a paper is cited disagrees for 16 of
  37 sampled IDs. Citation provenance and coverage need a source decision.
- The latest manuscript's five-paper example reports conventional `g=12`
  although both source definitions say top `g` papers. Its internal outlier
  rule and several component example values also conflict.
- The experiment design calls hm “harmonic” and hf “contribution-weighted”;
  the manuscript describes the original comparator using `1/Np` shares.
  The manuscript's Brown citation describes b-index while the design lists
  s-index. These require explicit methodology decisions.
- C-score construction and its self-citation version, Fi, s and AR do not
  receive complete operational formulas. m needs an as-of/career duration
  policy. The current pilot lacks the final target's 100,000 profiles,
  334-field stratification and verified award, gender/region and longitudinal
  data.
- Provisional `metrics/inputs.py`, `total_cites.py` and `h_index.py` were
  audited but left unexecuted. Their behavior for no links and unresolved
  counts is conservative, yet their source portfolios may be incomplete.
  Calculator unit tests and any pilot metrics are deferred by the explicit
  no-calculation rule.
- The Phase 2 access layer still permits only validated SELECT statements,
  verifies `transaction_read_only=on`, and rolls back/closes connections.
  Separate SELECT calls are separate snapshots, so concurrent ingestion can
  create timing differences in cross-table audit counts.

## Artifacts

- `latest_experiment_design_summary.md`, `latest_nm_manuscript_summary.md`,
  `source_consistency_audit.md` — current source evidence and conflicts.
- `latest_baseline_audit.csv` — all 11 baseline statuses.
- `nm_vs_baseline_mapping.md` — component/baseline/source distinctions.
- `validation_database_input_map.csv`, `citation_semantics_sample.csv` —
  SELECT-only coverage and citation checks.
- `assumption_register.md`, `phase5_readiness_check.md` — decisions and
  readiness gates.

## Safety and verification

17 offline, non-metric unit tests passed. The live input audit used only
`src.database.execute_select` SELECT queries under server read-only
transactions; no write SQL, migration or production calculation runner was
executed. Source documents were read only. The production repository status
was clean before and after the audit. The validation directory has no Git
repository. No commit or push occurred. **Phase 5 was not started.**
