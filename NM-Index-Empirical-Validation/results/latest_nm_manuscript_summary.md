# Latest NM manuscript — source summary

Source: [Nm Index novel model (1)(3).pdf](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf),
39 PDF pages, read in full on 2026-10-04. This document supersedes the older
`Nm Index novel model (1).pdf` as a source for this audit. Page numbers below
are PDF page numbers. Formula notation below is transcription, not an
implementation or recalculation of NM-index.

## Definition and required inputs

Nm-index is a 0–100 weighted combination of six component percentiles
(Equations 24–27, pp. 12–13). Its model needs each author's complete
publication/citation history, cited and citing paper authors, paper years,
field assignments and field weights, author order/norm or explicit
contribution, field/year citation reference distributions, a career start,
and a reference population for ranking. The manuscript plans 100,000 Google
Scholar profiles in 334 fields with OpenAlex supplementation (p. 13).

The six component *scores* are `T_a` (weighted field/year normalized total
cites), `S_a` (weighted capped field normalized citations per paper), `U_a`
(weighted capped field/year normalized citation rate), `Hf′_a`, `Hm′_a`,
`G′_a` (modified field-weighted variants). They are different from the
conventional Total Cites, hf, hm and g **baselines**.

## Method equations

| Topic | Latest manuscript rule | Location |
|---|---|---|
| Alphabetical/random | Author-field share `V_f,p / N_p`. | Eq. 1, p. 5 |
| Relative contribution | Core first/last author positions share an effective author position (EAP); `H_i=1/EAP_i`; author-field share `V_f,p H_i / Σ_k H_k`. | Eqs. 2–3, pp. 6–7 |
| Explicit ACI | Author-field share `V_f,p B_i,p`, where ACI shares sum to one in the appendix proof. | Eq. 4, p. 7; Lemma 3, p. 31 |
| Explicit CRediT | Field weight times an author's weighted CRediT roles divided by weighted roles across all authors. Domain-expert AHP role weights are proposed. | Eq. 5, p. 7 |
| Overall contribution | Mutually exclusive A/R, RC or EC mode, with ACI or CRediT within EC. Sum their active weighted terms. | Eq. 6, p. 7; Appendix Lemmas 1–5, pp. 31–32 |
| Influential self-citation | ISC is a ratio of target-author plus `ε₀·|J|` times overlapping core-author citing-paper contributions, to target-author plus `|J|` times core-author plus non-overlapping citing-paper contributions. `ε₀∈[0,1]`; adjusted edge credit is `(1−ISC) × raw edge credit`, summed over citing papers/fields. | Eqs. 7–9, pp. 8–9; Fig. 3, p. 9 |
| Career factor | `CF_com=C(t+1)^(-λ)`, `C≥1`, `0≤λ≤1`, t since first publication. Proposed example `C=1.25`, `λ=0.0601`. | Eq. 10, p. 9; Fig. 4, p. 10 |
| `T_a` | Career factor times sum of author-field weighted, ISC-adjusted citations divided by field/year mean adjusted citations. | Eq. 11, p. 10 |
| `S_a` | Cap adjusted citations at a field kth percentile (example k=99), then divide weighted sum by paper count and field mean, and multiply by career factor. | Eqs. 12–13, pp. 10–11 |
| `U_a` | Career factor times weighted capped adjusted citations divided by time since publication and field/year mean. | Eq. 14, p. 11 |
| `Hf′_a` | Effective citations `CF_com × W_f,p,i × capped adjusted citations`; rank papers in each field, apply a Hirsch-like threshold, divide by field reference value, then field-weighted average. | Eqs. 15–17, p. 11 |
| `Hm′_a` | Effective rank is cumulative `CF_com × W_f,p,i`; threshold against effective citations, normalize by field reference, then field-weighted average. | Eqs. 18–20, pp. 11–12 |
| `G′_a` | Accumulate effective citations over ranked field papers, apply a `k²` threshold, normalize by field reference, then field-weighted average. | Eqs. 21–23, p. 12 |
| Percentiles and final Nm | `L(x)=log10(x+1)` for `T,S,U`; use log-z or rank inverse normal according to distribution. Tied modified indices use fractional/midranks and Blom position `(r−0.375)/(N+0.25)`. Map to 0–100 percentiles; `Nm=Σ_i w_i Per_i`, `Σ_i w_i=1`; equal `1/6` suggested and used in example. | Eqs. 24–27, pp. 12–13 |

The synthetic defaults (p. 14) are `ε₀=0.90`, `C=1.25`, `λ=0.0601`, equal
six weights and IQR trimming at `Q1−1.5×IQR` / `Q3+1.5×IQR`. Eq. 12 instead
uses a field kth-percentile cap. This **outlier-rule inconsistency** is not
resolved by the manuscript and requires a methodology decision if components
are ever recomputed. This audit only reads existing stored components.

## Baseline comparators and numerical examples

The manuscript's p. 13 list repeats the design's 11 baselines. Its p. 2 gives
explicit conventional h, g and m descriptions, but only broad hm/hf/Fi/s/AR
descriptions. The C-score discussion on pp. 3, 16–17 and 24–25 gives an
illustrative four-role credit fraction `(I_single + I_single/first +
I_single/first/last + I_any)/4` and a six-indicator standardized C-score
example. These do **not** specify all reference distributions and rules needed
for a general Ioannidis C-score implementation, nor the baseline's SC
adjustment. The ISC equations are explicitly NM's own method.

The p. 19–25 fictitious profile has five papers, raw citations 165, career
time 10, and no self-citations. The latest manuscript reports component scores
`T≈1.683`, `S≈0.374`, `U≈0.629`, `Hf′≈0.545`, `Hm′≈0.113`, `G′≈0.365` and
example percentiles 55, 30, 45, 48, 25, 35, giving **Nm≈39.67** (p. 24–25).
These are synthetic examples, not values calculated from the current database.

## Validation plan and limitations within the manuscript

Section 3.1 (pp. 13–14) mirrors the design's 100,000/334-field cohort,
stratification and eligibility. It lists Pearson/95% CI, paired t/Cohen's d,
ICC, ROC/AUC, PCA, demographic stratification and Bonferroni correction.
Section 3.4 (pp. 25–29) sketches the real-world experiments, including
gaming, future success, rank stability and fairness. Several tables contain
`[TBD]` and figures are `[FIGURE PLACEHOLDER]`. Discussion and conclusion on
p. 30 are placeholders. Statements in the abstract and introduction that
large-scale validation already demonstrated outcomes are therefore **claims
without displayed completed results in this supplied manuscript**.

The appendix on pp. 30–36 gives normalization/boundedness lemmas and proofs.
It is not a source of missing conventional-baseline formulas. Some appendix
claims differ from the displayed main equations or are mathematically
problematic: it assumes `CF_com≥1` although Eq. 10 tends to zero for positive
`λ`; it sometimes treats a fractional single-author share as summing to one
per target author; and its proof text uses a plotting position `r/(N+1)`
where Eq. 24 gives the Blom position. These are flagged, not corrected.

Specific numerical inconsistencies: pp. 23 and 25 report conventional
`g=12` for a **five-paper** profile despite the p. 2/top-g-papers definition;
p. 21 checks `k=5` for a four-paper CS field and `k=2` for one-paper BE;
some Table 5–10 captions disagree with nearby prose and detailed calculations
(e.g. modified hf 0.84 versus detailed 0.545). These examples must not be
used as verification fixtures. The correct NM result for this project remains
the stored `author_nm_index.nm_index`; this audit does not recompute it.
