# Database-first selection with verified fallback — implementation report

## Outcome and boundary

The real-run input path now **attempts the mapped database extract first**, validates any complete database candidate, then lazily loads a verified local fallback. Each required source is recorded as `DATABASE`, `VERIFIED_FALLBACK`, or `UNAVAILABLE` in `results/run_<timestamp>/input_source_status.csv` and `run_metadata.json`, with the reason, affected RQ(s), selected-author count, and source-record count. An unavailable required source gives the affected RQ an explicit `DATA_REQUIRED` status. Missing scores remain missing; no zero or guessed value is substituted. The existing CSV and RQ7 bundle interfaces remain compatible.

**A database-only 995-author run is not yet scientifically executable from the saved schema.** The fixed SQL mapping cannot establish complete-career portfolio attestations, an approved raw C-score reference, or all RQ7 graph/reference/scenario inputs. `src/database_first.py` therefore rejects the incomplete mapped source rather than pretending that these contracts have been replaced. The resolution engine has a validated database-candidate seam, exercised offline, for a later adapter built from *documented* populated-schema fields. It is not a claim that the current production route can supply all three complete inputs today.

## Files changed

| File | Change |
|---|---|
| `src/database_first.py` (new) | Source assessment, complete-input validators, database-first/fallback selection, and provenance decisions. No connection code. |
| `src/pipeline.py` | Resolve real-run inputs after the read-only extract; defer previously premature portfolio/RQ7 fallback gates; record input lineage; mark blocked RQs `DATA_REQUIRED`. |
| `run_validation.py` | Preserve `--input` and `--rq07-bundle` syntax while loading these three fallbacks only if the mapped database source is unusable. |
| `analysis/counterfactual.py` | Accept the documented `field_weights` paper column in salami/gift scenario guards while retaining legacy `field` support. No scenario formula changed. |
| `tests/test_database_first.py` (new) | Offline priority, rejection, fallback, no-imputation, provenance, RQ7, and existing CSV-path tests. |
| `README.md` | Current source-selection behavior and remaining limits. |
| `results/database_first_implementation_report.md` (new) | This report. |

No production files, database tables, records, migrations, NM formulas, or approved RQ calculations were changed.

## Database fields used and source decisions

The existing SELECT-only extract continues to use `public.author.author_id`; `public.publication.pub_id`, `year`, and `total_citation`; `public.citation.pub_id` (cited) and `cites_pub_id` (citing); `public.author_contribution_weight.pub_id`, `author1id`–`author10id`, their weights and `author_ordering_norm`; `public.field_classification` field names/weights; `public.author_nm_index.nm_index` and its six percentiles; and the six established raw NM component sources. The new source selector assesses the fetched author, paper, NM, and citation row counts. It does not introduce an unverified SQL column or query a different production schema.

| Existing input | Current mapped database contribution | Complete database replacement now? | Verified fallback |
|---|---|---|---|
| `portfolio_verification.csv` | Observed author IDs and linked publications can be checked. | **No.** Neither `portfolio_verified` nor source-coverage evidence is mapped. Completeness cannot be inferred from observed rows. | The file is loaded when supplied and accepted only when every selected author has a true Boolean and nonblank evidence. |
| `reference_scores.csv` | NM, paper counts, years, authorship slots and some baseline inputs are mapped. | **No.** Raw C-score and the approved original 100,000-author reference membership/version are unmapped; complete middle-author shares and career stages also need verification. `author_metrics.c_index` is not raw C-score. | The file needs the original 100,000 IDs, required finite values, approved career labels, one version, and evidence. |
| `inputs/rq07_bundle/` | Original publication/citation/field/authorship rows and some benchmark candidates are mapped. | **No.** Full edge/authorship coverage, all frozen denominators, and explicit counterfactual additions/assignments are not established. Earlier saved citation data had edge/count disagreement. | The bundle loader and structural validator retain the original graph-level path. It is selected only when the mapped source is incomplete. |

The generic `database_candidates` seam in `run_from_extracts()` accepts already retrieved, verified in-memory candidates for these three contracts. Both candidates and fallback values pass the same checks. The current real adapter supplies no *complete* candidate from the known schema, so source rows will ordinarily say `VERIFIED_FALLBACK` or `UNAVAILABLE` until the member documents additional populated-database sources. A future adapter must use `src/database.py`'s guarded `SELECT` interface and a repeatable-read, read-only snapshot, then pass only complete, provenance-backed objects. A database candidate may not be built by treating a normalized NM component as conventional Total Cites or C-score.

## RQ-by-RQ impact

| RQ | Source-selection effect |
|---|---|
| RQ1 | Reference source is selected and validated before residual/percentile diagnostics; missing reference gives `DATA_REQUIRED`. |
| RQ2–RQ3 | Portfolio gate applies; existing comparator and agreement logic is unchanged. |
| RQ4 | Reference source is selected before percentile-based award contrasts; award labels/events remain separate inputs. |
| RQ5 | Portfolio gate applies; scenario labels remain separate inputs. |
| RQ6 | Portfolio gate applies; annual score snapshots remain separate inputs. |
| RQ7 | Graph, frozen benchmark, and NM parameters are selected as one coherent source. The existing full counterfactual calculator and baseline recalculation remain in use; no scalar citation-count shortcut is introduced. Missing data is `DATA_REQUIRED`. |
| RQ8 | Portfolio gate applies; historical scores and future outcomes remain separate inputs. |
| RQ9 | Portfolio gate applies; annual scores remain separate inputs. |
| RQ10 | Portfolio gate applies; the six stored raw NM component sources are unchanged. |
| RQ11 | Portfolio gate applies; approved subgroup labels and percentiles remain separate inputs. |

The `sensitivity` experiment shares RQ7's graph/reference source selection. Other pending baseline formulas and methodological decisions are unchanged.

## Fallback and provenance behavior

For each required contract the selector checks a complete database candidate, then the corresponding fallback path or already supplied in-memory object. Invalid candidates do not silently win. A validated database candidate prevents fallback loading. A rejected database candidate records its rejection reason; a verified fallback records why the database path could not be used. If both fail, the status is `UNAVAILABLE` and the affected RQ is blocked. `input_source_status.csv` contains `input_name`, `source`, `reason`, `affected_rqs`, `authors_affected`, and `records_affected`; the same decisions appear under `input_sources` in `run_metadata.json`. The source file formats are implementation contracts, not methodological necessities. `VERIFIED_FALLBACK` means the file passed the implemented content/structure/provenance-field checks; software cannot independently authenticate a free-text evidence reference.

## Verification

- All **84 offline unit tests passed** after the final functional changes. Tests include database priority, verified fallback, unavailable sources, no silent imputation, source metadata, RQ7 database/fallback selection, and the existing local CSV path.
- Syntax parsing passed for **98 Python files** without creating bytecode.
- `run_validation.py --dry-run --all` returned `DRY_RUN_OK` and reported no database access or writes.
- `run_validation.py --data-source mock --all` completed with synthetic test data and wrote `results/run_20261021T150822021650Z/`. Its outputs are not empirical findings.
- No real connection or 995-author run was made.

## Remaining blockers

1. An authoritative, author-level complete-portfolio evidence source must be mapped or supplied. The generic `database_ready_reference` text is not itself proof for every author.
2. A verified raw C-score source, the approved original 100,000-author ID set, complete middle-author positions, career-stage mapping, and reference provenance are needed for database-only RQ1/RQ4.
3. RQ7 needs complete original cited/citing paper graphs, exact contribution modes, edge/count agreement, universal field Hf/Hm references, original normalization/distribution data, and prespecified counterfactual additions/edge-half/gift-position choices. Those choices are not facts in the unmanipulated database.
4. `run_validation.py` still requires documented database-readiness and citation-source references before a real connection. Other RQs still have their own external labels or longitudinal data requirements. Thus `995_authors.csv + database` alone currently produces explicit unavailable states instead of a complete RQ1–RQ11 empirical result.

No commit or push was made.
