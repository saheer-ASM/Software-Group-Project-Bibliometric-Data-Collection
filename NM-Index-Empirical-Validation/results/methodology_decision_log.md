# Phase 4.5 methodology decision log

Current authorities: [experiment design](../source_documents/Pasted%20markdown%287%29.md), especially baseline table lines 30–41, and [latest NM manuscript](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf), especially PDF pp. 2–3 and 19–25. This log records conflicts without choosing an undocumented method. Stored NM components are separate from conventional baselines.

## hm-index — REQUIRES_USER_DECISION

- **Design:** “Multi-authored h-index (harmonic),” attributed to Schreiber (2008), line 35; no full equation.
- **Manuscript:** PDF p. 2 describes an effective paper rank using a “harmonic mean” and fractional allocation by coauthor count; p. 23 contrasts original uniform `1/Np` with NM's contribution-weighted rank. The worked comparison reports original hm=4 for five papers, while adjacent `h/Np≈1.14` prose does not define a reproducible algorithm.
- **Conflict/effect:** “Harmonic” is not an exact threshold algorithm, and the described cumulative `1/Np` rank is not enough to reconstruct the example. Different rank/citation conventions change hm and its correlation with NM.
- **Interpretations:** conventional cumulative `1/Np` effective rank; a harmonic-mean credit; or another Schreiber variant. No interpretation is selected.
- **Needed/recommendation:** supply the intended equation, tie/rank handling, and a verified worked example; confirm complete per-paper coauthor counts. Do not substitute modified NM `Hm′`.

## hf-index — REQUIRES_USER_DECISION

- **Design:** “Fractional h-index (contribution-weighted),” Schreiber (2008), line 36; no full equation.
- **Manuscript:** PDF pp. 2 and 22–23 describe conventional fractional allocation/equal author shares `1/Np`; Table 11 reports hf=4. NM `Hf′` separately uses actual contribution, field and career adjustments.
- **Conflict/effect:** contribution-weighted design wording conflicts with the manuscript's uniform-share comparator; neither specifies the complete citation/rank threshold rule. Applying stored contribution weights versus `1/Np` can change hf substantially.
- **Interpretations:** uniform fractional citations, uniform fractional paper ranks, or actual contribution fractions. No interpretation is selected.
- **Needed/recommendation:** provide exact conventional hf equation and select uniform or actual contribution input; verify full author lists and source of contribution shares. Do not use NM `author_modified_hindex` as hf.

## Conventional g-index example — REQUIRES_USER_DECISION

- **Design:** largest `g` whose top `g` papers have at least `g²` cumulative citations (line 37).
- **Manuscript:** PDF p. 2 agrees, but pp. 23 and 25 report g=12 for Table 4's five-paper profile.
- **Conflict/effect:** manual audit yields g=5 when `g` is limited to the five observed papers; zero-padding to 12 reproduces the reported value but is unstated. This affects both comparator implementation and any verification fixture.
- **Interpretations:** five-paper cap; zero-pad beyond paper count; omitted papers; example error. See [manual audit](g_index_example_audit.md).
- **Needed/recommendation:** authorial clarification of paper-set completeness and allowed g domain. Preserve the written definition in the specification pending a decision; do not assert the example is correct.

## s-index — REQUIRES_USER_DECISION

- **Design:** “Self-citation index,” attributed to Brown (2009), line 40; no equation.
- **Manuscript:** PDF p. 2 discusses self-citation metrics but gives no s-index equation or unit; its bibliography identifies Brown (2009) as a **b-index** paper, not an s-index method.
- **Conflict/effect:** metric identity/reference is ambiguous. There is no justified way to transform citation/self-citation rows into the intended s-index. The database's NM influential-self-citation adjustment is not a substitute.
- **Interpretations:** intended s-index with a missing citation, Brown b-index mislabeled, or a project-specific self-citation index. No interpretation is selected.
- **Needed/recommendation:** provide the correct reference and exact algorithm, including self-citation attribution and required input completeness. Status in baseline planning: **REQUIRES SOURCE/METHODOLOGY DECISION**.

## m-index career-year convention — INSUFFICIENT_SOURCE_INFORMATION

- **Design:** `m = h / career years` (line 38); no evaluation date or duration convention.
- **Manuscript:** PDF p. 2 divides h by years starting from first publication; PDF p. 22 uses `5/10 = 0.5` in a synthetic example. Its NM career factor is a separate formula.
- **Conflict/effect:** no contradiction in the broad formula, but the exact `t` is undefined for real records. Elapsed versus inclusive years, evaluation date, same-year authors, missing/future years, and whether stored NM `career_time_years` is comparable all affect values.
- **Interpretations:** calendar elapsed years, inclusive years, or a fixed as-of cohort year. No interpretation is selected.
- **Needed/recommendation:** establish an explicit validation as-of date/year, year-count rule, and zero/missing/future-year policy. Status: **REQUIRES EXPLICIT VALIDATION CONVENTION**; do not implement yet.

## Additional incomplete baseline definitions — INSUFFICIENT_SOURCE_INFORMATION

The design's Total Cites and h-index rules are explicit; g-index has the example conflict above. The design/manuscript do not give a complete general algorithm and reference distributions for **C-score raw**, a separate component adjustment rule for **C-score SC adjusted**, a threshold/formula for **Fi-score**, or a publication-age equation and as-of policy for **AR-index**. See [baseline metric specification](baseline_metric_specification.md). None may be silently filled from general knowledge or replaced with an NM component.
