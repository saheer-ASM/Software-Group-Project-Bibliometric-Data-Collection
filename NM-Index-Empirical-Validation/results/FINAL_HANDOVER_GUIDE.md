# NM-index validation: member handover guide

This folder is the isolated, read-only empirical validation project. It uses
`995_authors.csv` at the project root as the fixed cohort. Do not edit or replace
those IDs. All generated results remain under this project; PostgreSQL is read
through `src/database.py` in verified read-only transactions. The production
application and calculation scripts are never invoked.

## Configure and verify locally

1. Copy `config/config.example.env` to `config/config.env` inside this project
   and fill in the member's populated PostgreSQL connection values. Keep
   `config/config.env` private; never put credentials in a report or commit.
   `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_SSLMODE`
   are the database variables; SSL mode must be `require`, `verify-ca`, or
   `verify-full`. The connection layer sets transaction read-only, rolls back,
   and closes every connection.
2. From this directory, install `requirements.txt` in a virtual environment.
3. Run offline checks before any real connection:

   ```powershell
   .\.venv\Scripts\python.exe -B -m unittest discover -s tests -q
   .\.venv\Scripts\python.exe -B run_validation.py --dry-run
   .\.venv\Scripts\python.exe -B run_validation.py --data-source mock --all
   ```

The mock run uses only `TEST_` authors and writes **SYNTHETIC TEST DATA — NOT
EMPIRICAL RESULTS**. It must not be interpreted as a real finding.

## Required populated data

The database adapter (`src/repository.py`) must resolve all 995 stable IDs in
`public.author`; selected authors must have stored NM rows, publication rows,
authorship links, publication years, raw citation counts, field classifications,
and six stored NM component sources. A separate, independently verified
`portfolio_verification.csv` must attest each author using
`author_id,portfolio_verified,evidence_reference`. A verified citation-source
reference is also required. The existing ten author slots do **not** prove
complete coauthor lists. Full graph-level data for RQ7 must therefore be
supplied in the canonical bundle below; a database table's presence alone is
not adequate evidence of full coverage.

The RQ7 bundle contains the original **100,000-author** reference population
and its unmanipulated field/year adjusted-citation means, field-wide means,
citation caps, field Hf/Hm/G denominators, Z means/SDs, and percentile
distributions. The loader freezes and hashes these tables before any scenario.
Every component and `nm_index` must have a complete, consistent reference
distribution. The bundle must not contain counterfactual values in reference
tables.

Place the bundle under this validation project, for example
`inputs/rq07_bundle/`:

```text
metadata.json
reference/field_year_means.csv
reference/field_caps.csv
reference/z_means.csv
reference/z_standard_deviations.csv
reference/percentile_reference.csv
graphs/<author_id>/papers.csv
graphs/<author_id>/citation_edges.csv
graphs/<author_id>/self_additions.csv
graphs/<author_id>/self_metadata.json
graphs/<author_id>/salami_assignments.csv
graphs/<author_id>/gift_assignments.csv
```

There must be one `graphs/<author_id>/` directory for **every** ID in
`995_authors.csv`. `papers.csv` requires `pub_id,authors,year,field_weights,
contribution_mode,total_citation`; `authors` is an ordered JSON array and
`field_weights` is a JSON object summing to one. `contribution_mode` is
`uniform`, `relative`, `aci`, or `credit`. Relative mode can provide JSON
`first_positions`/`last_positions` arrays; ACI requires `aci_shares` JSON for
every author; CRediT requires `credit_roles` and `credit_role_weights` JSON.
These fields must describe the complete paper, including every coauthor.
`citation_edges.csv` requires unique
`citation_id,cited_pub_id,citing_pub_id` rows, with complete citing-paper
authorship in `papers.csv`. Every author's cited-paper edge count must equal
its raw `total_citation` value.

`self_additions.csv` has the same paper columns plus `citation_id,cited_pub_id`
and represents **real new citing papers and relationships**. The loader does
not invent these identities. `self_metadata.json` requires
`career_start_year,original_self_citation_count,relevant_core_authors` (array).
The +50% count must be an exact integer until a rounding rule is approved.
`salami_assignments.csv` requires `citation_id,half` for every citation to a
split target paper; use `citing_half` wherever a split paper also cites another
paper. Half values must be 1 or 2, and each paper's received edges must divide
equally. `gift_assignments.csv` requires `pub_id,position` for existing
coauthor papers. The target is inserted in a valid middle position on exactly
30% of the original portfolio; that count must be an exact integer until a
rounding rule is approved. Its original career start remains fixed.

`metadata.json` requires `version,as_of_year,epsilon_0,career_boost,
career_decay,component_weights`; the last field is a six-number JSON array
summing to one. Explicit values make the run reproducible. The latest NM
manuscript's synthetic defaults are `0.90`, `1.25`, `0.0601`, and six equal
weights; use only parameter choices approved for the real study.

Reference CSV columns are:

| File | Required columns |
|---|---|
| `field_year_means.csv` | `field,year,mean_adjusted_citations,field_mean_adjusted_citations` |
| `field_caps.csv` | `field,cap,hf_reference,hm_reference,g_reference` |
| `z_means.csv` | `metric,mean,distribution` (`lognormal` or `hooked_power_law`) |
| `z_standard_deviations.csv` | `metric,sd` |
| `percentile_reference.csv` | `author_id,metric,value` for `t,s,u,hf,hm,g,nm_index`; optional complete distributions for supported baselines |

## Other external research data

Use `--input KIND=CSV` for the existing validated input kinds listed in
`src/external_inputs.py`. RQ1 requires a complete 100,000-author
`reference_scores.csv` with verified C-score, middle-author share and career
stage. RQ4 requires independent award labels and, for the 13-category table,
award events. RQ5 requires observed scenario/order/domain/career fields. RQ6
and RQ9 need longitudinal scores. RQ8 needs separate historical scores and
future outcomes. RQ10 needs explicit PCA preprocessing and a decision
reference. RQ11 needs approved gender/region labels, percentile inputs and
fairness conventions. These are never inferred from names or missing data.

For RQ4's inferential comparison, supply a documented, approved convention
using `--award-inference-convention welch_two_sided_pooled_d` and
`--award-inference-reference "<approval record>"`. The implementation then
reports awardee/nonawardee mean reference percentiles, pooled-SD Cohen's d,
two-sided Welch p-values and Bonferroni-adjusted p-values. This convention
is exercised with **TEST DATA ONLY** in the mock fixture; it is not claimed
to have lecturer approval for the real experiment. A verified, complete
`award_events.csv` is required for the 13-category counts. Zero counts mean
no event in that supplied complete file; incomplete event exports must not
be passed as complete evidence.

## Run the fixed cohort later

After the member verifies the populated database and creates the bundle, a
full-cohort invocation has this shape (replace the evidence references and add
the relevant RQ inputs/options):

```powershell
.\.venv\Scripts\python.exe -B run_validation.py --data-source cohort --all `
  --rq07-bundle inputs/rq07_bundle `
  --database-ready-reference "approved populated database and cohort check" `
  --citation-source-reference "verified citation-source audit" `
  --input portfolio_verification=inputs/portfolio_verification.csv `
  --input reference_scores=inputs/reference_scores.csv
```

The command checks the immutable 995-ID CSV, portfolio evidence, complete
RQ7 bundle and original 100,000-author reference **before** database access.
It then uses the SELECT-only selected-author adapter. RQs lacking other
required external data or approved methodology remain explicitly unavailable;
do not interpret a pending status as a numerical result. Never use the mock
command for real data.

## Outputs and reproducibility

Each run writes `results/run_<UTC timestamp>/` with `validation_dataset.csv`,
RQ-specific CSVs, six Markdown reports, `run_metadata.json`, and
`output_manifest.csv` (file sizes and SHA-256 hashes). Figures are under
`figures/run_<same timestamp>/`; the manifest includes them. RQ7 exports
`gaming_resistance.csv`, `gaming_index_inflation.csv`, and
`rq07_nm_percentile_pairs.png` when valid pairs exist. The RQ7 rows record
original/manipulated NM values, percentiles, benchmark version/hash, graph
counts and explicit scenario status. Check one author per `validation_dataset`
row, all 995 IDs retained, eligibility/exclusion reasons, RQ statuses, missing
metric cells, every figure path, and all manifest hashes. Reproduce a run with
the same cohort hash, bundle/reference version, input CSVs, parameter file,
code hash, and seed in `run_metadata.json`.

If an author fails, inspect `experiment_eligibility.csv`,
`validation_dataset.csv`, `data_quality_report.csv`, and the RQ-specific status
rows. Do not silently remove them or substitute zero values. A missing graph,
edge, field reference, author position, or scenario assignment must be fixed
in the verified source/export, not guessed by this validation code.

The sensitivity experiment writes `parameter_sensitivity_scores.csv`: for
each eligible graph it recalculates NM under the design's four career
parameter pairs and four ISC epsilon values using the original frozen
reference. Rank-change, Gini and binary-ISC summaries still need exact
approved conventions. The score grid alone is not a complete sensitivity
interpretation.
