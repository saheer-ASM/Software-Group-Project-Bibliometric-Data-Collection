# NM-index empirical validation: baseline metric specification

**Status:** Phase 5A latest-PDF review complete. Explicit formulas for raw Total Cites,
h-index and g-index remain implemented; conventional hf is now implemented
with a verified-coauthor-count gate and exercised on synthetic data only.
No real-author metrics were calculated. “Inputs exist” refers to columns verified in
the Phase 3 schema inspection, not to complete records for every author.

## Source and notation

- [Experiment Design](../source_documents/Pasted%20markdown%287%29.md), “Baseline
  Indices (12 Total)” table, lines 27–41, is the baseline list. Its RQ10 table,
  lines 291–309, names the six NM components. It supplies descriptions for most
  baselines and explicit formulas for Total Cites, h, g and m.
- [Latest NM manuscript](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf),
  PDF pages 2–3 (literature baseline descriptions), 5–13 (NM model equations),
  16–25 (comparison examples), is the model source. PDF page numbers below mean
  the reader's page numbers, not necessarily the printed page labels.
- `c_p` means the raw citation count of paper `p`; `P_a` is the set of distinct
  publications linked to author `a`; `c_(k)` is the k-th largest count in that
  set. These symbols only restate the source descriptions.
- Database availability is grounded in the [Phase 2 schema report](database_schema_report.csv),
  [Phase 3 mapping](phase3_mapping_report.md) and the latest
  [read-only input audit](validation_database_input_map.csv). The authorship
  table records only ten author slots per paper and covers just 816 of 56,768
  publication rows. It links 2,340 of 2,507 current authors; full career
  portfolios are not verified.

## Baselines

### 1. Total Cites

**Definition/formula:** “Sum of all citations” (design table, line 31); for an
author this is `Σ_(p∈P_a) c_p`. The latest manuscript comparison on PDF p. 21 calls
this an absolute raw citation sum, with no contribution or field normalization.

**Inputs:** `author.author_id`, `publication.pub_id` and `total_citation`, joined
through `author_contribution_weight.pub_id` and `author1id`–`author10id`.
**Exist now:** Yes, as columns. **Calculable now:** Only for observed linked
publications, after citation-source and cohort-completeness decisions. All
56,768 `publication.total_citation` values are non-NULL, but the sampled
`citation` edge counts disagree with stored totals for 16 of 37 IDs; the
two representations cannot be silently interchanged. Missing/unlinked
publications must remain unknown. `author_total_cites.total_cites_score` is
the NM component and is not raw Total Cites.

### 2. C-score, raw

**Definition:** “Citation score with position weights” (design line 32). The
manuscript, PDF p. 3, describes Ioannidis' composite as combining total
citations, h-index, hm-index and single/first/last author positions. Its PDF
p. 24 example describes **six indicators** (`NC`, `H`, `Hm`, `NS`, `NSF`,
`NSFL`), log transformation, standardization and a sum of standardized
values; the sample sum is about 2.471. It mentions citation normalization
and first/last author citation contributions. This is a worked example, **not
a complete general algorithm**: exact component construction, normalization
reference distributions, and standardization parameters are not specified.

**Inputs:** Publication citations; author lists and positions; field/year
benchmark citation data and a reference population for standardization.
**Exist now:** Raw citations and first ten authorship slots exist;
`field_classification` exists. A complete set of benchmark/reference
distribution inputs has not been verified. **Calculable now:** Not faithfully
from these documents and verified inputs alone. The legacy `author_metrics.c_index`
and the UI's C-score label are not verified equivalents. Do not replace the
formula with a sum of raw counts or the NM total-cites score.

### 3. C-score with self-citation adjustment

**Definition:** C-score with self-citation adjustment (design line 33). The
manuscript's real-world comparison table names it (PDF p. 26) but supplies no
distinct formula, exclusion convention, or instructions for adjusting each
of the six C-score components. Manuscript Equations 7–9 (PDF pp. 8–9) define
the *NM model's influential self-citation adjustment*; they do **not** state
that the Ioannidis self-citation-adjusted C-score uses this adjustment.

**Inputs:** All raw C-score inputs plus author-level self-citation attribution
and an explicit component-adjustment rule. **Exist now:** `citation`,
`influential_self_citations` and `author_paper_adjusted_citations` exist, but
equivalence to the baseline C-score self-citation data is unverified. Phase 3
found adjusted paper-author records for only 143 authors. **Calculable now:**
No validated implementation from these documents and verified inputs.

### 4. h-index

**Definition/formula:** Largest `h` such that at least `h` of the author's
papers have at least `h` citations: `h = max({0} ∪ {k ≤ |P_a| : c_(k) ≥ k})`
(design line 34; manuscript PDF p. 2).

**Inputs:** The same raw citation and author-publication links as Total Cites.
**Exist now:** Yes. **Calculable now:** Yes on observed, complete linked-paper
counts after approval. A missing citation count must not be silently treated
as zero. The empty or unverified portfolio policy must be recorded.

### 5. hm-index

**Definition:** “Multi-authored h-index (harmonic)” (design line 35). The
manuscript, PDF p. 2, says the original hm uses an effective paper rank
fractionally allocated by author count, and PDF p. 11 contrasts its `1/N_p`
rank treatment with NM's contribution-and-career rank. The PDF p. 23 example
also uses `h/N_p` loosely. The design's “harmonic” wording differs from the
manuscript's `1/N_p` rank description. **Neither source gives an unambiguous, complete
conventional hm threshold algorithm.** In particular, the PDF's NM modified
hm Equations 18–20 cannot be substituted for the conventional baseline.

**Inputs:** Ordered citation counts and number of coauthors for *every* linked
paper. **Exist now:** Raw counts and up to ten author slots exist; true author
counts beyond ten or complete authorship are not verified. **Calculable now:**
Not with an exact source-defined rule and verified complete authorship.

### 6. hf-index

**Latest-PDF definition/formula:** The manuscript p. 2 describes the original
hf as fractional allocation. Its Table 8 caption, p. 22, says the `h`-th
paper's fractional citations must be at least `h`, and Table 11, p. 25,
specifies **uniform `1/N_p`** authorship shares. Thus sort each paper's
`c_p/N_p` descending and take the greatest `h` with the `h`-th value ≥ `h`.
For the manuscript's five-paper example, fractional counts are
`[50/3,20/5,30/4,40/6,25/4]`; the result is **4**, matching Tables 8 and 11.
The design table's “contribution-weighted” wording does not supersede the
latest PDF. NM modified `Hf′` uses actual contribution and other adjustments;
it is not this baseline.

**Inputs:** Complete raw citations and independently verified full coauthor
count `N_p` for every paper. **Exist now:** Ten author slots and per-slot
weights exist but cannot prove that all coauthors are represented. **Calculable
now:** The calculator is implemented and tested with synthetic declared-complete
authorship; real-data output stays NULL until coauthor completeness is proven.

### 7. g-index

**Definition/formula:** Largest `g` such that the top `g` papers have at least
`g²` citations cumulatively: `g = max({0} ∪ {k ≤ |P_a| : Σ_(i=1)^k c_(i) ≥ k²})`
(design line 37; manuscript PDF p. 2). The two sources agree on this rule,
but the manuscript's pp. 23–25 five-paper example reports `g=12`, which is
incompatible with the displayed top-g-papers definition. **Methodology
decision required** if an extension beyond the paper count is intended.

**Inputs:** Same raw counts and author-publication links as h-index.
**Exist now:** Yes. **Calculable now:** Yes on observed, complete linked-paper
counts after approval. `modified_g_index_results.modified_g_index` and
`author.modified_g_index` contain modified NM values, not conventional g.
The documents do not specify an extension beyond the number of observed
papers; the formula above restricts `k` to those papers.

### 8. m-index

**Definition/formula:** `m = h / t`, where `t` is career years starting at the
first publication (design line 38; manuscript PDF p. 2). PDF p. 22 gives
`h/t = 5/10 = 0.50`. NM career compensation in Equation 10 is a different
quantity and must not replace this divisor.

**Inputs:** Conventional h-index, earliest publication year, and an as-of
date/year for the career length. **Exist now:** `publication.year` exists and
`author_total_cites.first_publication_year`, `as_of_year` and
`career_time_years` exist as stored NM calculation metadata. **Calculable now:**
Potentially, after an as-of date and duration convention are specified and
data completeness checked. The documents do not state whether `t` is elapsed
calendar years, inclusive publication years, or how to handle `t=0`, missing
years and future years. We must not silently adopt the NM career factor's
stored duration as the baseline m-index rule.

### 9. Fi-score

**Definition:** “Self-citation evaluation score” (design line 39). The
manuscript PDF p. 2 says it uses h-index and total citations and compares
against a data-driven threshold. It gives no equation or threshold derivation.

**Inputs:** h-index, total citations, self-citation measures and the specified
threshold/reference data. **Exist now:** Raw citation, authorship and
`influential_self_citations` tables exist, but the required Fi-score threshold
and precise self-citation inputs are not identified. **Calculable now:** No
faithful formula is specified.

### 10. s-index

**Definition:** “Self-citation index” (design line 40). The manuscript PDF p. 2
mentions it in relation to other self-citation metrics but does not define a
formula, unit or attribution rule. Its bibliography cites Brown (2009) as the
**b-index** paper, making the intended s-index reference ambiguous.

**Inputs:** Unknown until its formula is specified; likely citation and
self-citation links, but this is only an input candidate. **Exist now:**
`citation` and `influential_self_citations` exist; sufficiency cannot be
established. **Calculable now:** No exact rule is specified. It must not be
replaced by a raw count of self-citation rows.

### 11. AR-index

**Definition:** “Age-weighted citation rate” (design line 41); manuscript PDF
p. 2 says it takes citation age into account. Neither document states an
equation, the publication-age rule or a reference date.

**Inputs:** Raw citations, linked publications, publication years and a
defined as-of date. **Exist now:** Citation counts and `publication.year`
exist. **Calculable now:** No exact formula or zero/missing-age handling is
specified. Do not use the NM citation-rate score as a substitute.

## NM-index: existing authoritative result and six components

**Final model definition:** The latest manuscript PDF pp. 12–13, Equations 24–27,
transforms each of six component scores, maps them to percentiles, then
combines the percentiles as `Nm_a = Σ_(i=1)^6 w_i Per_a(x_i)`, `Σw_i = 1`.
Equal weights `w_i = 1/6` are suggested, not imposed by the manuscript.
For `T_a`, `S_a`, `U_a`, Equation 24 uses `L(x)=log10(x+1)`; Equation 25
then uses either z normalization of `L(x)` under a lognormal assumption or
rank-based inverse normal transformation under a hooked power law. For
modified hf, hm and g, it uses fractional/midrank ranking, Blom plotting
position `P(x)=(r(x)-0.375)/(N+0.25)`, and inverse normal transformation.
Equation 26 maps the resulting values to 0–100 percentiles. The authoritative
**stored result** is `author_nm_index.nm_index`, joined by `author_id`. Its
six stored percentile columns, `metrics_available` and `calculated_at` must
be preserved; this validation project must not recalculate them. The
manuscript alone does not establish the exact policy used by existing code
for missing components or the concrete population used for stored percentiles.
The current read-only audit found 2,507 unique `author_nm_index.author_id`
rows, 2,321 non-NULL final scores and 186 NULL scores. There is no boolean
completeness column; `metrics_available` is the component count and
`calculated_at` is the timestamp. Duplicate author keys were not observed.

| Component | Model definition and source | Existing database source |
|---|---|---|
| `T_a`, total cites score | Eq. 11, PDF p. 10: career factor times sum across papers/fields of author-field contribution × ISC-adjusted paper citations / field-year mean adjusted citations. Raw baseline Total Cites has no such weighting. | `author_total_cites.total_cites_score`; NM percentile `author_nm_index.per_total_cites`. |
| `S_a`, citations per paper | Eqs. 12–13, PDF pp. 10–11: cap adjusted citations at field kth percentile, then career factor times weighted sum of capped citations divided by paper count and field mean. | `author_citations_per_paper.citations_per_paper_score`; percentile `per_citations_per_paper`. |
| `U_a`, citation rate | Eq. 14, PDF p. 11: career factor times weighted capped adjusted citations divided by years since publication and field-year mean. | `author_citation_rate.citation_rate_score`; percentile `per_citation_rate`. |
| `Hf′_a`, modified hf | Eqs. 15–17, PDF p. 11: derive effective adjusted field-paper citations using career and contribution weights, calculate a field-level modified h quantity, then field-weighted average. This is not the conventional hf baseline. | `author_modified_hindex.modified_hindex_final`; percentile `per_modified_hf_index`. |
| `Hm′_a`, modified hm | Eqs. 18–20, PDF pp. 11–12: effective paper rank accumulates career factor × author-field contribution; calculate field-level modified hm, then field-weighted average. This is not the conventional hm baseline. | `author.modified_hm_index`; percentile `per_modified_hm_index`. |
| `G′_a`, modified g | Eqs. 21–23, PDF p. 12: accumulate effective adjusted citations by sorted field-paper rank, apply a g² threshold, then field-weighted average. This is not conventional g. | `modified_g_index_results.modified_g_index`; percentile `per_modified_g_index`. `author.modified_g_index` is a separate mirror. |

The manuscript defines ISC adjustment in Equations 7–9 (PDF pp. 8–9) and
career compensation `CF_com = C(t+1)^(-λ)` in Equation 10 (PDF p. 9). Those
belong to the NM component model. They are not automatically applicable to
the conventional baseline indices. Some PDF equations are visibly compressed
or inconsistent in text extraction and example captions; exact NM code and
parameters are therefore not inferred from this transcription. Stored
`author_nm_index` values remain the only authorized NM-index values here.

## Implementation decision before pilot calculations

- Explicit baseline definitions: **Total Cites, h-index, g-index, conventional
  hf-index**. The first three use raw paper counts; hf also requires verified
  full coauthor counts. Their current database columns exist, but the author-publication
  link and citation-source coverage currently limit defensible full-career
  calculation. The manuscript's g example requires a methodology decision.
- Formula partly specified but calculation convention unresolved:
  **m-index** (career duration/as-of rules).
- Described but not fully specified for a faithful implementation:
  **C-score raw, C-score self-citation adjusted, hm-index, Fi-score,
  s-index, AR-index**. The sources have been read; these gaps are genuine,
  specific missing rules rather than an unavailable-document assumption.
- NM-index and six component scores: **read authoritative stored values only**.

The calculators and synthetic full pipeline were exercised in Phase 5A; no
real-author metric calculation or database write was performed. The registry
distinguishes formula availability from verified input availability. The older
Phase 3/4.5 database audits were SELECT-only.

The latest manuscript uses `Hf′≈0.545` and `Nm≈39.67` in its detailed
five-paper example (PDF pp. 20, 24–25); these replace the older manuscript's
example values. It also contains internal disagreements between equations,
captions and proofs. See [source consistency audit](source_consistency_audit.md)
for the unresolved cases; no example was used as a calculation oracle.
