# Nm-Index Empirical Validation: Experiment Design Document

## Overview

This document specifies the empirical validation experiments for the Nm-Index paper, aligned with Section 3.2 of the manuscript. Students will execute these experiments using the implemented software system and Google Scholar/OpenAlex data.

---

## Data Source & Sample

| Parameter | Specification |
|-----------|---------------|
| **Data Source** | Google Scholar profiles (primary), OpenAlex for supplementary validation |
| **Sample Size** | 100,000 author profiles |
| **Fields** | All 334 fields in the system |
| **Sampling Strategy** | Stratified random sampling across fields, career stages, and geographic regions |
| **Career Stages** | Early (t≤5), Mid-Early (5<t≤15), Mid-Late (15<t≤30), Senior (t>30) |

### Author Selection Criteria
- At least 5 publications
- At least 10 total citations
- Active between 2000-2024
- Exclude authors with incomplete metadata (missing publication years, author positions)

---

## Baseline Indices (12 Total)

| Index | Formula/Description | Source |
|-------|---------------------|--------|
| **Total cites** | Sum of all citations | Standard |
| **C-score (raw)** | Citation score with position weights | Ioannidis (2016) |
| **C-score (SC adj.)** | C-score with self-citation adjustment | Ioannidis (2019) |
| **h-index** | Max h where h papers have ≥h citations | Hirsch (2005) |
| **hm-index** | Multi-authored h-index (harmonic) | Schreiber (2008) |
| **hf-index** | Fractional h-index (contribution-weighted) | Schreiber (2008) |
| **g-index** | Max g where top g papers have ≥g² total citations | Egghe (2006) |
| **m-index** | h-index / career years | Hirsch (2005) |
| **Fi-score** | Self-citation evaluation score | Fiorillo (2024) |
| **s-index** | Self-citation index | Brown (2009) |
| **AR-index** | Age-weighted citation rate | Jin (2007) |

---

## Research Questions & Experiments

### RQ1: Associative Power
**Question:** How strongly does the Nm-index correlate with established bibliometric indices?

#### Experiment 1.1: Cross-Index Correlation Analysis
- **Method:** Compute Pearson correlation between Nm-index and all 11 baselines
- **Sample:** Full 100,000 author dataset
- **Statistical Tests:** 
  - Pearson's r with 95% CI
  - p-values for significance testing

**Outputs:**
- QQ-plots for normality assessment
- Residual plots
- Bland-Altman plots (Figure: param_plots)

**Table 1: Correlation Matrix**
| Statistic | Nm-index | Total cites | C-score raw | C-score SC adj. | h-index | hm index | hf index | g index | m index | Fi-score | s-index | AR-index |
|-----------|----------|-------------|-------------|-----------------|---------|----------|----------|---------|---------|----------|---------|----------|
| Pearson r | 1.00 | | | | | | | | | | | |

---

### RQ2: Paired Difference Analysis
**Question:** Are there significant paired differences between Nm-index and other metrics?

#### Experiment 2.1: Paired t-test Analysis
- **Method:** Paired t-test between Nm-index and each baseline
- **Metrics:** 
  - Mean difference
  - Cohen's d effect size
  - 95% CI for difference

**Table 2: Paired Difference Statistics**
| Comparison | Mean Diff | SD | t-statistic | p-value | Cohen's d | 95% CI |
|------------|-----------|----|----|---------|-----------|--------|
| Nm vs. Total cites | | | | | | |
| Nm vs. C-score raw | | | | | | |
| Nm vs. h-index | | | | | | |
| ... | | | | | | |

---

### RQ3: Interchangeability
**Question:** Can Nm-index be used interchangeably with existing metrics?

#### Experiment 3.1: Intraclass Correlation Coefficient (ICC) Analysis
- **Method:** Compute ICC between Nm-index and each baseline
- **Interpretation:** ICC < 0.5 = poor, 0.5-0.75 = moderate, 0.75-0.9 = good, >0.9 = excellent

**Table 3: Interchangeability Statistics (from paper Table: real_author_stat_summary)**
| Statistic | Nm-index | Total cites | C-score raw | C-score SC adj. | h-index | hm index | hf index | g index | m index | Fi-score | s-index | AR-index |
|-----------|----------|-------------|-------------|-----------------|---------|----------|----------|---------|---------|----------|---------|----------|
| Mean | | | | | | | | | | | | |
| SD | | | | | | | | | | | | |
| ICC with Nm | 1.00 | | | | | | | | | | | |

---

### RQ4: Discriminative Power
**Question:** Can the Nm-index distinguish recognized scholars (award recipients) from the general population?

#### Experiment 4.1: Award Recipient Analysis
- **Method:** Compare top 5% Nm-index scores with award recipient counts
- **Visualization:** ROC curves, AUC values

**Award Categories (13 awards as specified in paper):**
| Award | Field | Approx. Recipients |
|-------|-------|-------------------|
| Nobel Prize | Physics, Chemistry, Medicine, Economics | ~500 |
| Lasker Award | Biomedical | ~100 |
| Breakthrough Prize | Physics, Mathematics, Life Sciences | ~100 |
| Breakthrough Prize in Life Sciences | Life Sciences | ~50 |
| Wolf Prize | Multiple | ~100 |
| Dirac Medal | Theoretical Physics | ~50 |
| Knuth Prize | Computer Science (Theory) | ~30 |
| IEEE John von Neumann Medal | Computer Science/Engineering | ~50 |
| Turing Award | Computer Science | ~75 |
| Abel Prize | Mathematics | ~25 |
| Fields Medal | Mathematics | ~65 |
| Shaw Prize | Astronomy, Life Sciences, Mathematics | ~50 |
| Crafoord Prize | Sciences not covered by Nobel | ~50 |

**Table 4: Award Recipient Index Comparison**
| Index | Awardee Mean Percentile | Non-Awardee Mean | Cohen's d | AUC-ROC | p-value |
|-------|------------------------|-----------------|-----------|---------|---------|
| Nm | | | | | |
| Total cites | | | | | |
| C-score raw | | | | | |
| h-index | | | | | |
| g-index | | | | | |

**Figure: ROC Curves for Award Prediction**
- X-axis: False Positive Rate (0-1)
- Y-axis: True Positive Rate (0-1)
- Multiple curves: Nm, h, g, C-score, Total cites
- AUC values in legend

---

### RQ5: Unique Predictive Power
**Question:** Does Nm-index capture variance not explained by existing metrics through its novel components?

#### Experiment 5.1: Effect of Influential Self-Citations
- **Sample:** Relatively new profiles (t<15) with any author ordering norm in any field
- **Method:** Multiple linear regression with Nm-index as dependent variable

**Table 5: Self-Citation Scenario Analysis (from paper Table: self_citation_stat_summary)**
| Self-Citation Scenario | Nm-index | Total cites | C-score raw | C-score SC adj. | h-index | hm index | hf index | g index | m index | Fi-score | s-index | AR-index |
|------------------------|----------|-------------|-------------|-----------------|---------|----------|----------|---------|---------|----------|---------|----------|
| High single and unique author | | | | | | | | | | | | |
| High other core author overlap with no non-overlap authors | | | | | | | | | | | | |
| High single-author but with non overlapping authors | | | | | | | | | | | | |
| High other overlapping core-authors but with non overlapping authors | | | | | | | | | | | | |
| High single and other core author overlapping with non overlapping authors | | | | | | | | | | | | |
| No overlapping authors | | | | | | | | | | | | |

#### Experiment 5.2: Effect of Author Contribution and Ordering Norms
- **Sample:** Mid-career profiles (30>t>15) in appropriate domain for each case
- **Method:** Compare metrics across ordering norm categories

**Table 6: Author Ordering Scenario Analysis (from paper Table: contribution_stat_summary)**
| Author Ordering Scenario | Nm-index | Total cites | C-score raw | C-score SC adj. | h-index | hm index | hf index | g index | m index | Fi-score | s-index | AR-index |
|--------------------------|----------|-------------|-------------|-----------------|---------|----------|----------|---------|---------|----------|---------|----------|
| Alphabetical/random ordering | | | | | | | | | | | | |
| Relative contribution ordering | | | | | | | | | | | | |
| Explicit contribution with CRediT | | | | | | | | | | | | |
| Explicit contribution with ACI | | | | | | | | | | | | |
| Gaming (higher prevalence of many low contribution papers) | | | | | | | | | | | | |
| High sole author or high contribution practice | | | | | | | | | | | | |

#### Experiment 5.3: Evaluation of Domain Sensitivity
- **Sample:** Late-career (t>30) research profiles with high relative contribution ordering norm
- **Method:** Stratify by main domain distribution percentage

**Table 7: Domain Distribution Analysis (from paper Table: career_stat_summary)**
| Domain Distribution Percentage | Nm-index | Total cites | C-score raw | C-score SC adj. | h-index | hm index | hf index | g index | m index | Fi-score | s-index | AR-index |
|--------------------------------|----------|-------------|-------------|-----------------|---------|----------|----------|---------|---------|----------|---------|----------|
| Main domain ≥90% | | | | | | | | | | | | |
| 90%≥ Main domain >80% | | | | | | | | | | | | |
| 80%≥ Main domain >70% | | | | | | | | | | | | |
| 70%≥ Main domain >60% | | | | | | | | | | | | |
| 60%≥ Main domain >50% | | | | | | | | | | | | |
| 50%≥ Main domain >40% | | | | | | | | | | | | |
| 40%≥ Main domain >30% | | | | | | | | | | | | |
| 30%≥ Main domain >0% | | | | | | | | | | | | |

#### Experiment 5.4: Evaluation of Effect of Career Stage
- **Sample:** Low influential self-citing profiles in Computer networks and communication field with papers high in relative contribution ordering
- **Method:** Stratify by career stage (t)

**Table 8: Career Stage Analysis (from paper Table: career_stat_summary)**
| Career Stage (t) | Nm-index | Total cites | C-score raw | C-score SC adj. | h-index | hm index | hf index | g index | m index | Fi-score | s-index | AR-index |
|------------------|----------|-------------|-------------|-----------------|---------|----------|----------|---------|---------|----------|---------|----------|
| t≤5 | | | | | | | | | | | | |
| 5<t≤10 | | | | | | | | | | | | |
| 15<t≤20 | | | | | | | | | | | | |
| 20<t≤25 | | | | | | | | | | | | |
| 25<t≤30 | | | | | | | | | | | | |
| 30<t≤35 | | | | | | | | | | | | |
| 35<t≤40 | | | | | | | | | | | | |
| 40<t≤45 | | | | | | | | | | | | |
| 45<t≤50 | | | | | | | | | | | | |

---

### RQ6: Score Evolution
**Question:** How does Nm-index evolve over an individual's career compared to other indices?

#### Experiment 6.1: Longitudinal Analysis
- **Method:** Track one representative individual and plot index evolution with number of papers
- **Visualization:** Line plots showing Total citation, H-index, C-score, and Nm-Score variation over time

**Figure: Score Evolution (from paper Figure: score_evolution)**
- X-axis: Number of papers / Time
- Y-axis: Index value (normalized)
- Multiple lines: Nm-index, h-index, C-score, Total cites

---

### RQ7: Gaming Resistance
**Question:** How resistant is Nm-index to common manipulation strategies compared to existing indices?

#### Experiment 7.1: Gaming Simulation
- **Method:** Simulate three manipulation strategies on author profiles:
  1. **Excessive self-citation**: Artificially inflate self-citations by 50%
  2. **Salami slicing**: Double paper count with half citations each
  3. **Gift authorship**: Add 30% more co-authors to papers
- **Metric:** Percentage inflation in index value under each strategy

**Table 9: Gaming Resistance Analysis (from paper Table: gaming_resistance)**
| Gaming Strategy | Nm-index | h-index | C-score | hm index | hf index | g index |
|-----------------|----------|---------|---------|----------|----------|---------|
| Excessive self-citation (+50%) | | | | | | |
| Salami slicing (2x papers, 0.5x cites) | | | | | | |
| Gift authorship (+30% co-authors) | | | | | | |
| Combined manipulation | | | | | | |

**Interpretation:** Lower inflation = better gaming resistance. Nm-index should show lowest inflation due to ISC adjustment and contribution weighting.

---

### RQ8: Predictive Validity
**Question:** Can Nm-index predict future scholarly success better than existing indices?

#### Experiment 8.1: Future Success Prediction
- **Sample:** 10,000 authors with complete longitudinal data (2015-2024)
- **Method:** Compute indices at time t, correlate with outcomes at t+5
- **Outcomes:**
  1. Citations received in [t+1, t+5]
  2. Awards received by t+5
  3. h-index growth

**Table 10: Predictive Validity (from paper Table: predictive_validity)**
| Future Outcome | Nm-index | h-index | C-score | hm index | g index | m index |
|----------------|----------|---------|---------|----------|---------|---------|
| Future citations (t+5) | | | | | | |
| Future awards | | | | | | |
| h-index growth | | | | | | |

**Interpretation:** Higher correlation = better predictive validity for hiring/funding decisions.

---

### RQ9: Temporal Stability
**Question:** How stable are Nm-index rankings over time compared to other indices?

#### Experiment 9.1: Year-over-Year Stability
- **Method:** Compute rankings at consecutive years, measure stability
- **Metrics:**
  - Mean absolute rank change per year
  - Spearman ρ between year t and t+1 rankings
  - Percentage of authors with >10% rank change

**Table 11: Temporal Stability (from paper Table: stability_stats)**
| Metric | Nm-index | h-index | C-score | hm index | g index | m index |
|--------|----------|---------|---------|----------|---------|---------|
| Mean |Δrank| per year | | | | | | |
| Spearman ρ (t vs t+1) | | | | | | |
| % authors |Δrank| > 10% | | | | | | |

**Interpretation:** Moderate stability is ideal (too stable = insensitive to real changes; too volatile = unreliable).

---

### RQ10: Construct Validity
**Question:** Do the six Nm-index sub-scores capture distinct, non-redundant dimensions of scholarly impact?

#### Experiment 10.1: Principal Component Analysis
- **Method:** PCA on the six sub-scores (T_a, S_a, U_a, Hf', Hm', G')
- **Expected:** 2-3 principal components explaining >80% variance
- **Interpretation:** Distinct loadings confirm sub-scores measure different aspects

**Table 12: PCA Factor Loadings (from paper Table: pca_loadings)**
| Sub-score | PC1 (Impact) | PC2 (Efficiency) | PC3 (Breadth) |
|-----------|--------------|------------------|---------------|
| T_a (Total cites) | | | |
| S_a (Cites per paper) | | | |
| U_a (Citation rate) | | | |
| Hf'_a (Modified hf) | | | |
| Hm'_a (Modified hm) | | | |
| G'_a (Modified g) | | | |
| Variance explained (%) | | | |

**Interpretation:** If all sub-scores load on single PC, they are redundant. Distinct loadings justify including all 6.

---

### RQ11: Fairness Analysis
**Question:** Does Nm-index reduce known demographic biases in citation-based metrics?

#### Experiment 11.1: Gender Fairness
- **Method:** Infer gender via name-based classification (e.g., genderize.io API)
- **Metric:** Cohen's d between male and female mean percentiles

#### Experiment 11.2: Geographic Fairness
- **Method:** Stratify by institutional region (North America, Europe, Asia, Other)
- **Metric:** Variance of mean percentiles across regions

**Table 13: Fairness Analysis (from paper Table: fairness_analysis)**
| Group | Nm-index | h-index | C-score | Total cites | g index | m index |
|-------|----------|---------|---------|-------------|---------|---------|
| **By Gender** | | | | | | |
| Male | | | | | | |
| Female | | | | | | |
| Cohen's d (M-F) | | | | | | |
| **By Region** | | | | | | |
| North America | | | | | | |
| Europe | | | | | | |
| Asia | | | | | | |
| Other | | | | | | |
| Variance across regions | | | | | | |

**Interpretation:** Lower Cohen's d and lower regional variance = fairer index.

---

## Supplementary Experiments

### Sensitivity Analysis

**Table 9: Parameter Sensitivity (Career Compensation)**
| C | λ | Mean Rank Δ (Early) | Mean Rank Δ (Senior) | Gini Change |
|---|---|---------------------|---------------------|-------------|
| 1.00 | 0.00 | | | |
| 1.25 | 0.0601 | (baseline) | (baseline) | (baseline) |
| 1.50 | 0.10 | | | |
| 2.00 | 0.15 | | | |

**Table 10: Parameter Sensitivity (ISC ε₀)**
| ε₀ | Mean ISC | Correlation with Binary | Mean Rank Δ |
|----|----------|------------------------|-------------|
| 0.50 | | | |
| 0.75 | | | |
| 0.90 | (baseline) | | |
| 1.00 | | | |

### Robustness Checks

**Table 11: Sample Size Robustness**
| Sample Size | Nm-h ρ | 95% CI | Nm-C ρ | 95% CI |
|-------------|--------|--------|--------|--------|
| 25,000 | | | | |
| 50,000 | | | | |
| 75,000 | | | | |
| 100,000 (Full) | | | | |

---

## Implementation Notes for Students

### Data Collection

```python
# Example: Fetch author data from OpenAlex (supplementary)
import requests

def get_author_data(author_id):
    url = f"https://api.openalex.org/authors/{author_id}"
    response = requests.get(url)
    return response.json()

# Example: Fetch works for an author
def get_author_works(author_id, per_page=200):
    url = f"https://api.openalex.org/works?filter=author.id:{author_id}&per_page={per_page}"
    response = requests.get(url)
    return response.json()

# For Google Scholar: Use scholarly library or scraping with rate limiting
# Note: Respect robots.txt and rate limits
```

### Required Output Files

1. `correlation_matrix.csv` — Full 12×12 correlation matrix
2. `paired_difference_stats.csv` — Paired t-test results
3. `icc_analysis.csv` — Interchangeability coefficients
4. `award_analysis.csv` — Award recipient analysis results
5. `self_citation_analysis.csv` — ISC scenario results
6. `author_ordering_analysis.csv` — Ordering norm comparison
7. `domain_sensitivity.csv` — Domain distribution analysis
8. `career_stage_analysis.csv` — Career stage stratification
9. `score_evolution.csv` — Longitudinal data
10. `gaming_resistance.csv` — Gaming simulation results
11. `predictive_validity.csv` — Future outcome correlations
12. `temporal_stability.csv` — Year-over-year stability metrics
13. `pca_loadings.csv` — Factor analysis results
14. `fairness_analysis.csv` — Demographic fairness metrics
15. `sensitivity_results.csv` — Parameter sensitivity tables

### Figure Specifications

| Figure | Format | Dimensions | DPI |
|--------|--------|------------|-----|
| All figures | PDF/PNG | 6" × 4" (single) or 10" × 6" (double) | 300 |
| Color scheme | Colorblind-safe palette (e.g., viridis, ColorBrewer) | | |
| Font | Serif (Times/Computer Modern) for consistency with LaTeX | | |

---

## Statistical Reporting Standards

- Report exact p-values (not just < 0.05)
- Include 95% confidence intervals for all estimates
- Use effect sizes (Cohen's d, η²) alongside significance tests
- Apply Bonferroni correction for multiple comparisons
- Report sample sizes for all subgroups

---

## Timeline

| Week | Task |
|------|------|
| 1-2 | Data collection (100,000 Google Scholar profiles) |
| 3 | Compute all baseline indices |
| 4 | Compute Nm-index components (6 sub-scores) |
| 5 | Run RQ1-RQ3 experiments (Associative, Paired diff, ICC) |
| 6 | Run RQ4 experiments (Discriminative power with 13 awards) |
| 7 | Run RQ5 experiments (Unique predictive power: 4 sub-experiments) |
| 8 | Run RQ6 (Score evolution), RQ7 (Gaming resistance) |
| 9 | Run RQ8 (Predictive validity), RQ9 (Temporal stability) |
| 10 | Run RQ10 (Construct validity/PCA), RQ11 (Fairness analysis) |
| 11 | Sensitivity analysis, generate all figures |
| 12 | Write results section, integrate into paper |

---

## Expected Results Section Structure (aligned with paper)

```
3. Results

3.1 Experiment Setup
    - Data and code availability (Harvard Dataverse)

3.2 Numerical Demonstration (Synthetic Data)
    - 3.2.1 Demonstration of influential self-citations
    - 3.2.2 Demonstration of author contribution and ordering norms
    - 3.2.3 Demonstration of career stage
    - 3.2.4 Evaluation of all sub-scores with domain sensitivity
    - 3.2.5 Comparison Tables
    - 3.2.6 Final Nm-Index Calculation

3.3 Evaluation for Real-World Dataset (100,000 profiles)
    - 3.3.1 Associative power (RQ1)
    - 3.3.2 Paired difference between metrics (RQ2)
    - 3.3.3 Interchangeability (RQ3)
    - 3.3.4 Discriminative power (RQ4) — 13 awards, ROC/AUC
    - 3.3.5 Unique predictive power (RQ5)
        - Effect of influential self-citations
        - Effect of author contribution and ordering norms
        - Domain sensitivity
        - Effect of career stage
    - 3.3.6 Evaluation of score evolution (RQ6)
    - 3.3.7 Gaming resistance (RQ7)
    - 3.3.8 Predictive validity (RQ8)
    - 3.3.9 Temporal stability (RQ9)
    - 3.3.10 Construct validity (RQ10)
    - 3.3.11 Fairness analysis (RQ11)

3.4 Evaluation of Longitudinal Study

3.5 Evaluation of Formulated Hypotheses

4. Discussion
    - 4.1 Study overview
    - 4.2 Pros and Cons
    - 4.3 Evaluation of longitudinal study
    - 4.4 Review of sequential analysis in light of earlier works
    - 4.5 Evaluation of formulated hypotheses
    - 4.6 Review of hypotheses in light of earlier works
    - 4.7 Prescriptive input for administrative leaders

5. Conclusion
```