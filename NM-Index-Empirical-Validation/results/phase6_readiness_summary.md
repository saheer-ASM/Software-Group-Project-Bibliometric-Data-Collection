# Phase 6 — 995-author data readiness summary

Generated 2026-10-16T20:27:34.832663+00:00 from the unchanged master cohort `995_authors.csv` (SHA-256 `c704eeaa45602c445160d27ba07f07c9c123cf1145b9d8edc6b5855d80b651e9`). Exact IDs only; no substitutions or sampling.

**Overall status: DATA_NOT_READY.** Of 995 selected authors, 8 (0.8%) exist in `public.author`; 987 do not. 0 are READY, 8 INCOMPLETE, and 987 NOT_FOUND. Full publication portfolios and complete coauthor lists are not independently verified for any selected author.

| Requirement | Observed coverage and incomplete requirement |
|---|---|
| Selected authors | 995 unique nonblank IDs and names; 8 found, 987 absent |
| Publication links | 105 authorship rows, 105 distinct linked paper IDs for matched authors; 105 paper IDs resolve in `publication`; 0 orphan IDs; 0 matched authors have no links |
| Publication metadata | 0 linked papers lack year (0 authors); 0 lack stored citation count (0 authors); 0 lack fields (0 authors) |
| Citation relationships | 934 cited→citing rows on linked papers; 1 positive-count papers have zero edges; 6 papers have edge-count/stored-count mismatch; 0 duplicate edges; 0 edges point to absent citing publications |
| Authorship/coauthors | 0 papers lack ordering norm; 0 have missing populated-slot weights; 0 repeat an author within a row; 0 have multiple authorship rows; 0 fill all ten slots, so overflow cannot be excluded; 26 citing edges lack citing-paper authorship rows. Full author counts and portfolio completeness remain unverified. |
| Contribution data | 105 linked papers have non-null ordering norm; 105 have no missing weights among populated slots. Explicit ACI/CRediT provenance is not established by these columns. |
| Self-citation inputs | 763 distinct citing paper IDs; 748 have an authorship row; 7 selected authors have stored ISC rows; 2 matched authors have author-paper adjusted-citation rows for every observed linked paper. ISC absence may mean zero self-citations or missing processing; cannot infer which. |
| Field/year reference data | 6 papers lack at least one field/year mean; 0 lack a field mean; 0 lack a field cap; publication-year gaps affect 0 matched authors. |
| Stored NM-index | 8 matched authors have non-null `author_nm_index.nm_index`; 0 have a null row; 0 have no row; 0 have duplicate rows. `author.nm_index` is not the authoritative source. |
| Baselines | Raw Total Cites, h, g need complete linked publication counts; conventional hf additionally needs verified full coauthor counts. C-score raw/SC, hm, m, Fi, s, AR have unresolved methodology and/or inputs in source specification. No baseline was calculated. |

## Six NM component input checks

The table distinguishes presence of observed database inputs from verified full-cohort readiness. Stored component availability is separately reported below. A score present in a table does not prove its source records are complete.

| Component | Required inputs | Authors with required inputs | Authors missing inputs | Coverage | Status |
|---|---|---:|---|---|---|
| T_a — field/year-normalized total cites | linked papers; years; citation edges/ISC-adjusted author-paper counts; contribution; field/year means; career start | 0 verified (2 partial observed-data candidates) | 995 | 0% verified | INCOMPLETE |
| S_a — capped citations per paper | T inputs; field means; field citation percentile caps; paper count | 0 verified (2 partial observed-data candidates) | 995 | 0% verified | INCOMPLETE |
| U_a — citation rate | T inputs; field/year means; publication age; caps | 0 verified (2 partial observed-data candidates) | 995 | 0% verified | INCOMPLETE |
| Hf′_a — modified fractional h | complete authorship; contribution; adjusted counts; caps; career factor; field reference | 0 verified (2 partial observed-data candidates) | 995 | 0% verified | INCOMPLETE |
| Hm′_a — modified multi-author h | Hf′ inputs; complete author order and effective rank | 0 verified (2 partial observed-data candidates) | 995 | 0% verified | INCOMPLETE |
| G′_a — modified g | Hf′ inputs; ordered paper citations; field reference | 0 verified (2 partial observed-data candidates) | 995 | 0% verified | INCOMPLETE |

Stored non-null component values among matched authors: T_a — field/year-normalized total cites 8/8, S_a — capped citations per paper 8/8, U_a — citation rate 8/8, Hf′_a — modified fractional h 8/8, Hm′_a — modified multi-author h 8/8, G′_a — modified g 8/8.

All 995 author classifications and reasons are in `phase6_author_readiness.csv`. Name differences are reported in `phase6_author_coverage.csv`; the stable ID remains authoritative. Observed author-publication relationships are in `phase6_publication_coverage.csv`.
