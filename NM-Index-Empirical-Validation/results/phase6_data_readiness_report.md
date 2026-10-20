# Phase 6 — data readiness report

**Decision: DATA_NOT_READY.** The authoritative 995-ID CSV cannot currently be matched to the connected PostgreSQL database: only 8 IDs exist in `public.author`. No experiment or metric calculation should start with this cohort/database pairing.

## 1. Study cohort

Source: `995_authors.csv` at the validation-project root, SHA-256 `c704eeaa45602c445160d27ba07f07c9c123cf1145b9d8edc6b5855d80b651e9`. Exactly 995 data rows, 995 unique nonblank `author_id` values, no blank names. File was not modified. This is the only cohort used.

## 2. Author coverage

8/995 found; 987/995 missing. Found IDs: A5002072930, A5004065644, A5010244939, A5044182686, A5050585435, A5050803432, A5054657936, A5080607818. 2 found IDs have a name difference after case-insensitive whitespace normalization. IDs, not names, govern matching. See `phase6_author_coverage.csv` for every selected row.

## 3. Publication coverage

For the matched IDs only: 105 matching authorship rows and 105 distinct publication IDs; 105 resolve to publication records, 0 do not. 0 paper IDs have multiple authorship records; 0 have multiple publication records; 0 have duplicate author IDs within an authorship row. Counts by author and orphan/duplicate flags are in `phase6_publication_coverage.csv`. These observed records do not prove the full portfolio is present.

## 4. Citation coverage

934 citation rows refer to the observed cited papers. 763 distinct citing paper IDs occur, of which 763 resolve to publication records; 0 edges have no citing publication. 0 repeated cited/citing pairs occur. 1 papers have positive `publication.total_citation` but no matching `citation` rows; 6 observed papers have raw edge count different from stored total. A difference may reflect distinct source/ingest semantics; it must be resolved before using edge-derived citation counts. 0 observed papers lack stored citation counts. No Total Cites were recalculated.

## 5. Authorship and contribution coverage

The `author_contribution_weight` relation contains author1–author10 only. There is no independently verified full author-count field in this extract. 0 observed papers fill all ten slots, and even fewer populated slots do not prove completeness. 0 papers have an empty authorship row, 0 repeat an author ID, 0 lack `author_ordering_norm`, 0 lack weights in populated slots. Selected-author positions are visible in the matched slots. Explicit ACI/CRediT source and category provenance remain unverified. No contribution weights were calculated.

## 6. Self-citation inputs

The database exposes cited/citing paper IDs and authorship slots. Of 763 distinct citing IDs, 748 have authorship rows; 26 edges lack a citing-paper authorship row. 7 selected authors have rows in `influential_self_citations`; 2 matched authors have an `author_paper_adjusted_citations` row for every observed paper. Absence of ISC rows is not automatically evidence of zero self-citations. The source pipeline's cited-paper sampling and ten-slot limit require provenance review. No ISC was calculated.

## 7. Field/year coverage

Of 105 observed paper IDs, 0 lack a publication year (0 matched authors affected) and 0 lack a field (0 authors affected). 6 have at least one field without a matching field/year adjusted mean; 0 lack a field mean; 0 lack a field percentile cap. These are input-presence checks, not field normalization.

## 8. Stored NM-index and component input coverage

Authoritative result: `author_nm_index.nm_index`. 8 matched authors have a non-null value, 0 have a null-valued row, 0 have no row, and 0 have duplicate rows. The six latest-manuscript components and strict observed-input candidates are tabulated in `phase6_readiness_summary.md`. None has verified complete portfolio/coauthor coverage for all 995 selected authors. Stored scores do not substitute for input verification.

## 9. Baseline input availability

The latest experiment design requires 11 baselines. The latest manuscript is authoritative for NM methodology and the baseline notes below retain unresolved definitions instead of inventing them.

| Baseline | Available inputs | Missing inputs / verification | Methodology status |
|---|---|---|---|
| Total Cites | Linked paper IDs and stored raw citation counts for matched authors | 987 authors absent; complete portfolios and citation semantics unverified | Formula defined; no metric run |
| C-score raw | Some raw counts, positions, fields | Complete author positions, reference distributions, standardization inputs | General algorithm unresolved in sources |
| C-score SC adjusted | Some citation edges, ISC/adjusted rows | Complete self-citation attribution and C-score adjustment rule | Unresolved; NM ISC is not this baseline |
| h-index | Linked paper counts and raw citations | Verified complete publication portfolios | Formula defined; no metric run |
| hm-index | Counts and up to ten author slots | Verified full coauthor counts and threshold rule | Ambiguous between source descriptions |
| hf-index | Counts and up to ten author slots | Independently verified full coauthor count per paper | Formula defined by latest PDF; input gated |
| g-index | Linked paper counts and raw citations | Verified complete portfolios; resolve worked-example contradiction before comparison | Formula defined for observed papers; no metric run |
| m-index | h inputs and publication years | Complete portfolios, as-of date and career-duration convention | Incomplete duration convention |
| Fi-score | Some counts and ISC rows | Threshold/reference data and exact equation | Formula unresolved |
| s-index | Some citation and ISC rows | Exact input attribution and equation | Formula unresolved |
| AR-index | Some counts and years | As-of/age convention and exact equation | Formula unresolved |


## 10. Missing data and authors requiring attention

987 selected IDs are absent; exact IDs are in `phase6_author_readiness.csv`. 8 matched authors require source-data and independent portfolio/coauthor verification. Specific missing-year, count, field, contribution, adjusted-citation, NM, and component flags are in their per-author reason fields. 0 meet full readiness; nobody was silently excluded.

## 11. Decision and exact next step

**DATA_NOT_READY.** First reconcile the immutable master CSV against the intended PostgreSQL instance or correct upstream author-ID mapping, without changing the cohort or production database. Then rerun this read-only inventory and independently verify full publication portfolios and coauthor counts. Resolve citation-source semantics and unresolved baseline methodology before any experimental execution.

## Scope and safety

This audit queried only the selected cohort, their linked papers, their citing-paper references, and field benchmark metadata, using the validation project's `execute_select_batch`. Each batch enforced `transaction_read_only=on`, used a repeatable-read snapshot, rolled back and closed. Batches are separate snapshots; concurrent database changes could affect cross-batch comparisons. The only SQL statements supplied to the interface were SELECTs. No database writes, migrations, calculation scripts, statistical experiments, figure generation, commits or pushes were performed. The production project was not edited.
