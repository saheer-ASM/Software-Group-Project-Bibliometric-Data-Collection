# Latest NM manuscript: mathematical reference

Source: [`Nm Index novel model (1)(3).pdf`](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf), especially §2, PDF pp. 5–13, numerical demonstrations pp. 14–25, and appendix pp. 30–36. This is a reference for **stored** production NM scores and separate local simulations; the validation pipeline reads `author_nm_index.nm_index` and does not recompute it.

## Variables and contribution (Equations 1–6)

For paper `p`, field `f`, author position `i`: `N_p` is the complete author count; `Vᶠ_p ≥ 0` is the field allocation with `Σ_f Vᶠ_p = 1`; `α_p, β_p, γ_p` exclusively indicate alphabetical/random, relative or explicit ordering. Under explicit ordering, `δ_p, φ_p` exclusively indicate ACI or CRediT. Equation 1 assigns `Wᶠ_{p,A/R}=Vᶠ_p/N_p`. Equation 2 replaces positions for jointly designated first/last authors with the mean of the positions in that group; middle authors keep their position. Equation 3 assigns relative-ordering weight `Wᶠⁱ_{p,RC}=Vᶠ_p(1/EAP_i)/Σ_k(1/EAP_k)`. Equation 4 uses reported ACI share `Bⁱ_p`: `Wᶠⁱ_{p,EC,ACI}=Vᶠ_p Bⁱ_p`, with author shares summing to one. Equation 5 uses CRediT role indicators `eⁱ_j` and field-specific expert weights `hᶠ_j`: `Wᶠⁱ_{p,EC,CRediT}=Vᶠ_p Σ_j hᶠ_j eⁱ_j / Σ_k Σ_j hᶠ_j eᵏ_j`. Equation 6 selects the active model: `Wᶠⁱ_p=αW_A/R+βW_RC+γδW_ACI+γφW_CRediT`. The appendix pp. 30–31 proves per-field weights sum to `Vᶠ_p`; complete authorship, ordering labels, fields and CRediT/ACI declarations are therefore required. The database's ten author slots are not evidence that larger teams are complete.

## Influential self-citation and career time (Equations 7–10)

For a citation from citing paper `q` to cited paper `p` and target author `a`, `I` contains the target author's citing-paper positions, `J` the *other* authors overlapping the cited paper, and `M` the nonoverlapping citing authors. Let `S_I=Σ_{k∈I}Wᶠᵏ_q`, `S_J=Σ_{j∈J}Wᶠʲ_q`, `S_M=Σ_{m∈M}Wᶠᵐ_q`, `ε=ε₀|J|`, `0≤ε₀≤1`. Equation 7 is `ISC=(S_I+ε S_J)/(S_I+|J|S_J+S_M)`; a positive denominator and normalized weights are required. Appendix pp. 32–33 states `0≤ISC≤1`; no overlap yields zero, sole target-author citation yields one. Equation 8 discounts each raw citation by `1−ISC`. Equation 9 sums adjusted citation contributions over citing papers and fields for the cited author-paper. The example on pp. 14–16 uses `ε₀=0.90`; this is a manuscript example/default, not permission to change production records. The written Equation 7 and the drawn Figure 3 should be checked together because extracted typography is compressed.

Equation 10 gives `CF_com=C(t+1)^(-λ)`, with `C≥1`, `t≥0` elapsed years since the first publication, and `0≤λ≤1`. The proposed/example values are `C=1.25`, `λ=0.0601`, approaching one at `t≈40`; no compensation is `C=1, λ=0`. This is **not** the conventional baseline m-index denominator. The manuscript says the career factor is a decaying boost, although the appendix's claim that it is always `≥1` is false for sufficiently large `t` when `λ>0`; keep this mathematical conflict visible.

## Six raw component scores (Equations 11–23)

`TC_adj(p,a)` is author-specific adjusted paper citation credit. `μ_adj(f,y)` and `μ_adj(f)` are field/year and field adjusted-citation means, and `R_adj(k,f)` is the field `k`th percentile cap. Means/divisors must be positive; the manuscript does not specify a zero-denominator policy. The main text illustrates `k=99` and Figure 1/§3.1.3 also mention `Q1−1.5×IQR` and `Q3+1.5×IQR` trimming. These are **different outlier treatments**; no silent choice is valid.

| Eq. | Raw component definition | Authoritative stored source for validation |
|---|---|---|
| 11 | `T_a=CF_com Σ_p Σ_f Wᶠⁱ_p TC_adj(p,a)/μ_adj(f,y_p)`; no outlier cap. | `author_total_cites.total_cites_score` |
| 12–13 | `cap=min(TC_adj,R_adj(k,f))`; `S_a=CF_com Σ_p Σ_f Wᶠⁱ_p cap/(P μ_adj(f))`. | `author_citations_per_paper.citations_per_paper_score` |
| 14 | `U_a=CF_com Σ_p Σ_f Wᶠⁱ_p cap/(age_p μ_adj(f,y_p))`. Example p. 19 uses `age_p=max(1,as_of_year−publication_year)`; main equation only says elapsed time, so that floor is not silently generalized. | `author_citation_rate.citation_rate_score` |
| 15–17 | `TC_eff=CF_com Wᶠⁱ_p cap`; sort by effective citations, find largest `h` with `TC_eff(h)≥h`, divide by field reference `Hf′_f`, then weighted-average fields by `Vᶠ_p`. | `author_modified_hindex.modified_hindex_final` |
| 18–20 | Effective rank through sorted paper `k` is `r_eff(k)=Σ_{p′≤k}CF_com Wᶠⁱ_{p′}`; largest qualifying rank has `TC_eff(k)≥r_eff(k)`, divided by field reference `Hm′_f`, then field weighted average. | `author.modified_hm_index` |
| 21–23 | `A_eff(k)=Σ_{p′≤k}TC_eff(p′)`; largest `k` satisfying `A_eff(k)≥k²`, divided by field reference `G′_f`, then field weighted average. | `modified_g_index_results.modified_g_index` |

The manuscript's worked five-paper example gives inconsistent intermediate values in pp. 20–24 and labels a conventional `g=12` despite the written top-`g` paper rule. Stored NM components are loaded as provenance, never used as conventional baseline hf/hm/g or raw Total Cites.

## Transformation and final score (Equations 24–27)

Equation 24 applies `L(x)=log10(x+1)` to `T,S,U` and Blom plotting position `P(x)=(midrank(x)−0.375)/(N+0.25)` to modified hf/hm/g. Equation 25 uses either `z=(L−mean(L))/sd(L)` for a lognormal citation component or `Φ⁻¹(P(L))` for a hooked-power-law citation component; modified indices use `Φ⁻¹(P(x))`. Equation 26 maps citation-component z-scores to `100Φ(z)` and modified-index ranks to `100P(x)`. Equation 27 combines six percentiles: `Nm_a=Σ_{j=1}^6 w_j Per_a(x_j)`, `Σ_j w_j=1`; equal `w_j=1/6` is proposed, not an immutable rule. The population/reference distribution, distribution-family selection and missing-component weighting used for **stored** NM values are not proven by the PDF alone. `author_nm_index.nm_index`, its six `per_*` values, `metrics_available`, and timestamp remain the authoritative outputs. RQ10 uses the six **raw** scores above; it does not use these percentiles by accident.

## Boundaries for validation software

Equations 1–27 describe the NM model, but this project is not authorized to reproduce the production calculation. Exact local calculations currently supported by the source and required for baseline comparison are the conventional raw Total Cites, h and written g rules; see [baseline audit](baseline_implementation_audit.md). The design specifies self-citation/gaming *experiments*, yet it does not give all counterfactual input and recomputation conventions. Their interface and `METHODOLOGY_PENDING` status are retained. All substantive open decisions must be prespecified before real data execution.
