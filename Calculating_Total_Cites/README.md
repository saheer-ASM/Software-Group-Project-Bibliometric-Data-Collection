Calculating Total Cites — Equation 11

This module calculates the Total Cites component exactly in the sequence usedby the uploaded Nm-index paper:

Equation 9 supplies TC_adj(p,i).

The field/year benchmark supplies TC-bar_adj(f,y).

Author and field weights supply W_p^(f,i).

Equation 10 supplies CF_com.

Equation 11 calculates T_a.

Equation 11

[T_a = CF_{com}\sum_p\sum_f W_p^{f,i}\frac{TC_{p,i}^{adj}}{\overline{TC}_{f,y}^{adj}}]

Files

db_setup.py — creates the benchmark, detail, and final result tables.

refresh_field_year_average.py — refreshes TC-bar_adj(f,y).

calculate_total_cites.py — performs Equation 11.

run_total_cites.py — command-line runner.

Run order

From the repository root:

py -m Calculating_Total_Cites.db_setup
py -m Calculating_Total_Cites.refresh_field_year_average
py -m Calculating_Total_Cites.run_total_cites

Calculate one author only:

py -m Calculating_Total_Cites.run_total_cites `
  --author-id A5050585435

Use a fixed evaluation year:

py -m Calculating_Total_Cites.run_total_cites `
  --as-of-year 2026

Output tables

public.total_cites_equation_11_details

Stores each paper-field term:

author_field_weight = W_p^(f,i)

adjusted_citation = TC_adj(p,i)

field_year_average = TC-bar_adj(f,y)

normalized_citation_ratio

paper_field_contribution

calculation_status

public.author_total_cites

Stores the final author-level result:

career_factor = Equation 10

normalized_contribution_sum = the double summation in Equation 11

total_cites_score = T_a

calculation_complete = whether all inputs were complete and noprovisional benchmark was used

The view public.equation_11_total_cites exposes the final results.

Inspect results

SELECT *
FROM public.author_total_cites
ORDER BY total_cites_score DESC NULLS LAST;

SELECT *
FROM public.total_cites_equation_11_details
WHERE author_id = 'A5050585435'
ORDER BY publication_year, pub_id, field_name;