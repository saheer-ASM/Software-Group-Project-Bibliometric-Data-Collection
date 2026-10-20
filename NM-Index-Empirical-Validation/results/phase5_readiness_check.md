# Pre-Phase 5 readiness check

Audit date: 2026-10-04. **Overall status: NOT READY for full empirical
validation.** This audit performed source review and read-only data inspection;
it did not calculate any baseline, NM component, NM-index or statistical result.

| Check | Status | Evidence / remaining issue |
|---|---|---|
| Latest experiment design read | [x] | Entire `source_documents/Pasted markdown(7).md`; see `latest_experiment_design_summary.md`. |
| Latest NM manuscript read | [x] | Entire 39-page `(1)(3).pdf`; see `latest_nm_manuscript_summary.md`. The older PDF was not used as authority. |
| Source consistency checked | [x] | `source_consistency_audit.md` records unresolved cross-source and internal manuscript conflicts. |
| Baseline definitions checked | [x] | All 11 rows in `latest_baseline_audit.csv`; several definitions remain incomplete or conflicting. |
| NM vs baseline distinction checked | [x] | `nm_vs_baseline_mapping.md`; stored NM component values are not substituted for conventional metrics. |
| Total Cites distinction checked | [x] | Raw sum versus normalized/career-compensated `author_total_cites.total_cites_score` documented. |
| Database inputs verified | [x] | SELECT-only audit of 15 tables and 95 columns, including row/non-NULL/duplicate-key counts, in `validation_database_input_map.csv`. **Availability is not proof of complete portfolio data.** |
| Citation semantics verified | [ ] | Citation direction was established (`pub_id` cited, `cites_pub_id` citing), but 16 of 37 sampled stored totals disagree with edge counts; source completeness/provenance remains unresolved. |
| Author-publication relationship verified | [ ] | Application's stable-ID lookup through `author_contribution_weight` confirmed, but only 816 of 56,768 publications have a link row; complete portfolios and >10-author treatment are unverified. |
| Read-only database layer verified | [x] | Local SQL parser guard, enforced read-only transaction, server `transaction_read_only=on`, rollback/close and sanitized errors; no write probe was sent. |
| No production dependencies | [x] | Validation Python imports use standard/isolated packages and local `src`, `metrics`, `experiments`; production source was inspected read-only but never imported. |
| Unit tests passing | [ ] | 17 existing/new **non-metric** offline tests pass. Provisional Total Cites and h-index calculators have no executed unit tests because this audit explicitly prohibits metric calculations, including pilot runs. |
| No database writes | [x] | Live audit used `src.database.execute_select` and fixed SELECT queries only; every connection rolls back and closes. |
| No production files changed | [x] | Sibling project Git status was clean before and after audit; edits stayed in this validation directory. |

## Blocking decisions and data work

1. Confirm intended conventional hm/hf algorithms, s-index identity, m-index
   career-year convention and handling of the manuscript's five-paper `g=12`
   example. Supply full C-score, Fi-score and AR-index rules if all 11
   comparators remain required.
2. Establish whether `publication.total_citation` or the subset of `citation`
   edges is the authorized raw citation source, explaining observed mismatches.
3. Provide/verify complete author-publication portfolios. Current ten-slot
   records cover 816 publications and link 2,340 authors; 167 authors have no
   such link. The final 100,000-author stratified cohort and 334-field coverage
   are not present in the pilot.
4. Define missing-data and cohort eligibility policies; distinguish stored NM
   component *scores* from stored component *percentiles* for later analysis.
5. Once calculations are explicitly authorized, test provisional calculators
   with manually verifiable examples before any pilot run. Do not interpret
   manuscript example tables as verified ground truth where they contradict
   their own equations.

The validation project itself has no `.git` directory, so a standalone Git
status is unavailable. The original production repository remained clean.
No calculation runners, migrations, commits or pushes were executed.
