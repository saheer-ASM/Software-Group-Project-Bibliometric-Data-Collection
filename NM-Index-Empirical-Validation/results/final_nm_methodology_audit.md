# Final NM-index methodology audit

## 1. Executive summary

**Final status: METHODOLOGY_ISSUES_REMAIN.** The current validation project does **not** implement the NM-index equations as an independent calculator. It reads the production-computed `author_nm_index.nm_index`, six stored percentile columns, and six separately stored raw component scores. Therefore a correct read of stored values cannot establish that the production calculation matches the manuscript. No production code or database was inspected or changed for this audit. A narrow validation fix now excludes a stored score from experiments when any of its six component percentiles is missing; it does not recalculate or alter the score.

This project cannot be certified as a PDF-faithful NM calculator. Implementing one would require complete source data and decisions where the manuscript is silent or inconsistent. The proposed 995-author experiment also has the independent Phase 6 blocker: only 8 of the selected 995 IDs were found in the connected database at that check. None of this is an empirical result.

## 2. Latest PDF used

The **only methodology authority** for this audit is [`source_documents/Nm Index novel model (1)(3).pdf`](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf), 39 pages, SHA-256 `3bffd57d10b334bf4e37d437bf6babe6a9ae333cada1e6102be9181539ebdb91`. All 39 pages were read. Equations 1–27 occur on PDF pages 5–13; synthetic examples and parameter defaults occur on pages 14–25; appendix discussion is on pages 30–36. Older PDFs and prior audit reports were not used as authorities. The PDF was not edited.

## 3. Equation-by-equation audit

The complete **27-row equation table**, with PDF meaning, actual validation file/function, mathematical implementation status, and fix outcome, is [`final_nm_methodology_audit.csv`](final_nm_methodology_audit.csv). `NOT_IMPLEMENTED` means the validation code has no formula for that equation; it does not assert that the stored production result is mathematically wrong. Equation 27 is `PARTIAL_MATCH` solely because the correct authoritative stored result and six stored percentile fields are read and the six-term availability gate is now enforced. The weighted sum itself is not computed or verified. There is **no equation-level MATCH** to claim for an unexecuted local NM calculator.

| Equations | PDF computation | Validation behavior |
|---|---|---|
| 1–6 | Author-field contribution by ordering or explicit roles | Reads ten-slot authorship and stored weights; does not derive or verify the models |
| 7–9 | ISC per citing edge; discounted credit; summation | Reads no cited/citing ISC inputs in the execution extract; no ISC computation |
| 10 | Career factor | No career-factor computation |
| 11–14 | T, cap, S, U | Loads stored raw components; no normalization or cap computation |
| 15–23 | Modified Hf, Hm, G | Loads stored raw components; no effective-credit, rank, threshold, or field-reference computation |
| 24–26 | Transforms, normalization, percentiles | Loads six stored `per_*` values; no reference-population percentile computation |
| 27 | Six-term weighted sum | Loads stored NM result; now excludes incomplete component rows from experiment eligibility; no weighted-sum verification |

## 4. Contribution methodology: Equations 1–6

The PDF defines A/R weight `V_f,p/N_p` (Eq. 1); RC effective author position for core first/last versus middle positions (Eq. 2), with harmonic share `V_f,p(1/EAP_i)/Σ_k(1/EAP_k)` (Eq. 3); ACI share `V_f,p B_i,p` (Eq. 4); CRediT share `V_f,p(Σ_j h_f,j e_i,j)/(Σ_kΣ_j h_f,j e_k,j)` (Eq. 5); and the mutually exclusive A/R, RC, EC-ACI, EC-CRediT combination (Eq. 6). The appendix requires field weights to sum to one, exactly one ordering mode, and one EC submode.

`src.repository.QUERIES['authorship']` reads `author_ordering_norm` and ten author slots with stored weights. The pipeline uses those links for baseline preparation and quality checks. There is no validation function that identifies the required norm/first/last core sets or derives Eqs. 1–6. Ten slots cannot prove the full author count. ACI declarations, CRediT roles, field-specific AHP role weights, and their exclusivity/provenance are not in the execution extract. Stored slot weights are **inputs for inspection**, not a mathematical match for Eq. 1–6.

## 5. Self-citation methodology: Equations 7–9

Let `I` be the target author's citing-paper positions, `J` the other authors shared by citing and cited papers, and `M` the nonoverlapping citing authors. Eq. 7 gives `ISC = [Σ_I W_q,f + ε₀|J|Σ_J W_q,f] / [Σ_I W_q,f + |J|Σ_J W_q,f + Σ_M W_q,f]`, with `0≤ε₀≤1`; Eq. 8 discounts raw fractional edge credit by `1−ISC`; Eq. 9 sums adjusted credit over citing papers and fields. The PDF's synthetic default is `ε₀=0.90` (p. 14). The execution extractor reads `citation` edges but does not request the full cited/citing authorship, `influential_self_citations`, or `author_paper_adjusted_citations` as formula operands. There is no ISC implementation. The separate Phase 6 inventory inspected some of these tables but did not calculate ISC.

The PDF's worked citing paper with **11 authors** (p. 15) exceeds the current ten-slot authorship extract. Thus complete overlap and citing-author weights cannot be established for that case. A zero denominator or missing coauthor data policy is **NOT SPECIFIED IN LATEST PDF**. No epsilon or tolerance is configured for an NM calculation in this project.

## 6. Career factor: Equation 10

`CF_com = C(t+1)^(-λ)`, with `C≥1`, `0≤λ≤1`, and `t≥0` elapsed years since the first publication (p. 9). The proposed synthetic values are `C=1.25`, `λ=0.0601`; these are not validation runtime parameters. Neither `nm_index` nor the pipeline computes this factor. The exact as-of date, fractional-year convention, future-paper handling, and missing first-year policy are **NOT SPECIFIED IN LATEST PDF**. The appendix's assertion that `CF_com≥1` for all careers conflicts with Eq. 10 when `λ>0`, since the factor tends to zero as `t` grows; Eq. 10 governs the mathematical description.

## 7. T, S, U components: Equations 11–14

Eq. 11 multiplies the career factor by the sum of author-field weights times ISC-adjusted paper-author citations divided by the corresponding field/year adjusted citation mean. Eq. 12 caps adjusted paper-author citations at the field's `k`th-percentile threshold (example `k=99`). Eq. 13 divides the weighted capped sum by the author's paper count and field adjusted mean, then multiplies by career factor. Eq. 14 divides its weighted capped terms by elapsed publication time `y` and the field/year adjusted mean, then multiplies by career factor. The example uses `y=max(1, as_of_year−publication_year)` (p. 19); the general equation only says elapsed time. The value of `k`, zero benchmark/elapsed-time handling, and resolution between the percentile cap in Eq. 12 and p. 14's `Q1−1.5×IQR` / `Q3+1.5×IQR` trimming are **NOT SPECIFIED IN LATEST PDF** as a single consistent production rule.

The validation project reads `author_total_cites.total_cites_score`, `author_citations_per_paper.citations_per_paper_score`, and `author_citation_rate.citation_rate_score` into RQ10 data. It does **not** compute these equations. Conventional `metrics.total_cites` is a separate raw-citation baseline and must not be mistaken for Eq. 11.

## 8. Modified hf: Equations 15–17

Eq. 15 forms `TC_eff = CF_com × W_f,p,i × TC_adj,capped`, then sorts field papers by effective citations. Eq. 16 takes the largest `h` with the `h`th effective citation at least `h`, divided by the field's `Hf′_f` reference. Eq. 17 averages the field results using paper-field shares `V_f,p`. The validation project reads `author_modified_hindex.modified_hindex_final` as a stored component. Its conventional `metrics.hf_index` uses `c_p/N_p` for a **baseline** and is not this modified component. The source of the field reference `Hf′_f`, including zero-reference policy, is **NOT SPECIFIED IN LATEST PDF**.

## 9. Modified hm: Equations 18–20

Eq. 18 accumulates `CF_com × W_f,p,i` in the effective-citation sort order. Eq. 19 takes the largest effective rank whose corresponding effective citation reaches that rank, divided by the field's `Hm′_f` reference. Eq. 20 applies the same paper-field-share weighted average. The validation project reads `author.modified_hm_index`; it has no function calculating Eqs. 18–20. Conventional `metrics.hm_index` is methodology-pending and is not a substitute. The field-reference construction/zero policy is **NOT SPECIFIED IN LATEST PDF**.

## 10. Modified g: Equations 21–23

Eq. 21 accumulates sorted effective citations by field. Eq. 22 selects the largest `k` with cumulative effective citations at least `k²`, divided by the field's `G′_f` reference. Eq. 23 takes the paper-field-share weighted average. The validation project reads `modified_g_index_results.modified_g_index`; `metrics.g_index` is the conventional baseline, not Eq. 22. The field-reference construction/zero policy is **NOT SPECIFIED IN LATEST PDF**. The PDF example on pp. 20–21 checks `k` beyond available field papers in places, while Eq. 21 defines cumulative sums only through observed sorted papers. The example's conventional `g=12` for five papers (pp. 23–25) also conflicts with its written top-`g`-papers description (p. 2). Neither inconsistency authorizes inventing paper-padding or changing Eq. 22.

## 11. Final NM-index: Equations 24–27

Eq. 24 uses `log10(x+1)` for `T,S,U` and the Blom position `(r−0.375)/(N+0.25)` with fractional/midranks for tied modified indices. Eq. 25 uses log-Z normalization when citation metrics follow a log-normal distribution or inverse-normal ranking of the logged value for a hooked power law; modified indices use the inverse normal of the Blom position. Eq. 26 maps to 0–100 percentiles (`100×Φ(Nor)` for citation metrics; `100×P(x)` for modified indices). Eq. 27 is `NM_a=Σ_{i=1}^6 w_i Per_a(x_i)` with `Σw_i=1`; equal `1/6` weights are suggested and used in the synthetic example, not set in validation runtime code.

`nm_index.loader.load` maps the six stored percentile columns and final stored score; `src.repository` reads six raw stored component sources separately. The code **does not** choose reference populations/distribution families, transform, rank, assign weights, or aggregate. The latest PDF does **not** specify a rule for missing component percentiles, weight renormalization, or zero-filling. None was added. Eq. 27 explicitly requires six terms, so `src.eligibility.evaluate` now marks a row `NM_COMPONENTS_INCOMPLETE` if any of six `per_*` fields is absent, even when a stored `nm_index` is non-null. This keeps that stored value visible for audit without admitting it to experimental analysis. It does not prove the stored value follows Eq. 27. The full 100,000-profile reference population used by the example is not available in this validation extract.

## 12. Parameter audit

| Parameter | Latest PDF | Current validation value/use | Match status |
|---|---|---|---|
| `ε₀` | `[0,1]`; synthetic default `0.90` (pp. 8, 14) | No NM calculation parameter or use | NOT_IMPLEMENTED |
| `α,β,γ; δ,ϕ` | Mutually exclusive ordering and EC modes (pp. 5–7, 31) | Stored `author_ordering_norm` read; modes not derived | NOT_IMPLEMENTED |
| `V_f,p` | Nonnegative field shares summing to one per paper (pp. 5, 31) | Up to three stored field slots read; no Eq. 1–6 validation | PARTIAL_MATCH as data access only |
| ACI `B_i,p` | Declared author shares summing to one (pp. 7, 31) | No dedicated ACI declaration extract | NOT_IMPLEMENTED |
| CRediT `h_f,j` | Field-specific AHP role weights; 14 roles (p. 7) | No role/weight extract or value | NOT_IMPLEMENTED |
| `C,λ` | `C≥1`, `0≤λ≤1`; proposed `1.25`, `0.0601` (pp. 9, 14) | No NM runtime values; stored career metadata is not recomputation | NOT_IMPLEMENTED |
| `t,y` | Career time since first publication; paper age elapsed to now (pp. 9, 11) | Years available; no NM duration function | NOT_IMPLEMENTED; exact conventions NOT SPECIFIED IN LATEST PDF |
| `k`, field cap | Field `k`th percentile; `k=99` is example (p. 10) | No NM cap parameter or calculation | NOT_IMPLEMENTED; final k NOT SPECIFIED IN LATEST PDF |
| IQR limits | `Q1±1.5×IQR` as written on p. 14 | No NM trimming | NOT_IMPLEMENTED; conflicts with Eq. 12 cap rule |
| Field/year means and field index references | Denominators in Eqs. 11–14 and 16/19/22 | Not loaded for formula execution | NOT_IMPLEMENTED; index-reference derivation NOT SPECIFIED IN LATEST PDF |
| Rank/percentile `N` | Blom `(r−0.375)/(N+0.25)`; example `N=100000` (pp. 12–13, 24) | Six stored percentiles read; no ranking or full reference population | NOT_IMPLEMENTED |
| Six `w_i` | Nonnegative sum to one; equal `1/6` suggested (p. 13) | No local NM aggregation or weight value | NOT_IMPLEMENTED |
| Zero/missing-data tolerance | No general fallback or imputation stated | No NM fallback added; incomplete components now excluded | NOT SPECIFIED IN LATEST PDF |
| `MIN_PUBLICATIONS=5`, `MIN_RAW_CITES=10` | Study selection criteria (p. 13) | Validation eligibility defaults; **not NM formula parameters** | MATCH as default selection thresholds |

## 13. Database input audit

`src.repository.QUERIES` requests author IDs, publication IDs/years/raw citation counts, citation edges, up to ten author positions/stored weights and ordering norm, up to three field shares, final NM and six percentiles, and six stored raw component scores. These are appropriate for **reading existing results and conventional baselines**. The execution extract does **not** request complete coauthor rosters, ACI/CRediT declarations, all cited/citing field-author weights, per-edge ISC records, author-paper adjusted citations, field/year adjusted means, cap thresholds, field index-reference values, or a full reference population. The inspection-only `src.audit_database_inputs` and Phase 6 code mention additional tables, but they are not called by `run_validation.py` for NM computation. Some inputs are not known to exist in a usable complete form. No database connection or SQL was executed for this methodology audit.

## 14. Problems found

1. **Independent formula verification is impossible in the current architecture.** All 27 equations are either absent locally or represented only by stored output access. The validation project cannot certify whether the production-computed NM values match the latest PDF.
2. A non-null stored NM result could previously pass eligibility despite a missing one of six stored component percentiles. This did not follow the six-term availability requirement of Eq. 27.
3. Complete input and reference data are unavailable or unverified, including coauthor counts beyond ten slots and the full reference population. The latest PDF leaves several operational conventions unstated and contains an outlier-rule conflict and worked-example contradictions noted above.

## 15. Fixes made

Only `src/eligibility.py` and its targeted offline test were changed. Eligibility now emits `NM_COMPONENTS_INCOMPLETE` and excludes a row with any missing stored component percentile. No NM equation, stored score, baseline formula, experiment methodology, database query, or production file was changed. It would be scientifically misleading to add a new full NM calculator by guessing the missing inputs, reference values, and rules.

## 16. Tests performed

After the fix, `python -B -m unittest discover -s tests -v` passed **47/47** tests, including the new complete-versus-incomplete six-percentile regression test. AST syntax parsing passed for **85** Python files. `python -B run_validation.py --dry-run` returned `DRY_RUN_OK`, `database_access=false`, and `files_written=false`. The suite covered mocked database access, synthetic metrics, analysis, visualization, and reporting. All testing was synthetic/offline. No real-author metrics or RQs were run.

## 17. Final status

**METHODOLOGY_ISSUES_REMAIN.** The stored-NM validation route is safer after the eligibility guard, but the code cannot be called a verified implementation of the latest PDF's NM equations. Before handing off a 995-author real experiment, obtain a reconciled cohort/database, verify the production algorithm against Eqs. 1–27 or build an independently specified calculator with complete inputs, and resolve the manuscript's open conventions. Then rerun the methodology audit and offline checks. This report makes no claim that empirical validation is complete.
