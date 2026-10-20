# Limited-author pilot protocol

**Purpose:** test the research workflow on a prespecified small set of real authors. This is a **pilot**, not the 100,000-profile study described by the experiment design. The reduced sample, its selection rule and the advisor's approval must be recorded before interpretation. Do not report pilot estimates as final NM-index validation.

## Prepare the cohort

1. Put a CSV inside this validation project with an `author_id` column and, optionally, an `author_name` column. The supplied root-level `995_authors.csv` can be passed directly; IDs remain the only selection key. The pilot command accepts at most 6,000 distinct stable IDs because each selected ID is bound repeatedly in the authorship query. Names are not accepted as IDs. Keep the approved list immutable and record how authors were chosen, the number selected and any field/career/region balance. Do not use synthetic `TEST_` IDs.
2. Verify each author's **complete publication portfolio** independently, including stable author–paper links, publication years, author positions and relevant coauthor data. Check the design's at-least-five-publications, at-least-ten-citations and active-2000–2024 criteria; the current global eligibility code checks the first two but does not establish the activity or metadata-completeness rule by itself. Create `inputs/portfolio_verification.csv` with `author_id,portfolio_verified,evidence_reference`; every selected ID must have `true` and a nonempty evidence reference. A database link count alone is not proof of completeness.
3. Document the citation source, snapshot date and meaning of `publication.total_citation`. The last recorded database audit found broad disagreement between that count and observed citation edges. Resolve that provenance before interpreting computed baselines.
4. Record three nonempty references for the command below: approved small-cohort design, selected-cohort/data readiness, and citation-source decision. The CLI checks that these are supplied; the researcher must verify that they correspond to real documents and evidence.
5. Run the offline tests and dry-run first. Do not change the production database, code or NM scores.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
.\.venv\Scripts\python.exe -B run_validation.py --dry-run
```

## Run a single pilot experiment

Run this from the validation-project directory **after** the cohort and evidence above are ready. Substitute actual local references and file paths; do not place credentials on the command line. The validation project's `config/config.env` supplies its existing read-only connection configuration.

```powershell
.\.venv\Scripts\python.exe -B run_validation.py --data-source pilot --experiment rq01 `
  --pilot-author-ids inputs/pilot_author_ids.csv `
  --pilot-design-reference "approved small-cohort protocol reference" `
  --database-ready-reference "verified selected-cohort audit reference" `
  --citation-source-reference "approved citation-source decision reference" `
  --input portfolio_verification=inputs/portfolio_verification.csv
```

Use `--all` in place of `--experiment rq01` only when you want the full **status-bearing** pilot run. Methods requiring awards, annual/historical scores, approved subgroup labels or other external data also need their relevant `--input` CSVs and method-decision flags; otherwise they report `DATA_REQUIRED` or `METHODOLOGY_PENDING`. RQ08's design requires at least 10,000 complete longitudinal authors and will not claim a result from a smaller real pilot. Seven conventional baseline formulas remain unresolved and their columns remain null by default. The latest PDF specifies conventional hf, but the real pilot also leaves hf null until complete per-paper coauthor counts are independently verified and supplied through an approved input path. A small pilot cannot establish the planned stratified population estimates or statistical power.

The pilot loader uses parameterized SELECTs for selected authors and their linked papers within one read-only repeatable-read snapshot. It does not change any production records. It masks nonselected coauthor slots in memory so noncohort authors do not enter the dataset; this means coauthor-dependent methods require a separate completeness review. Files are saved only to a timestamped `results/run_.../` and `figures/run_.../`, labelled **PILOT DATA — NOT FULL EMPIRICAL VALIDATION**. Review `data_quality_report.csv`, `validation_dataset.csv`, `experiment_eligibility.csv`, each experiment status and `run_metadata.json` before interpreting the three currently executable real-pilot baselines.

**Current state:** no real author-list CSV or portfolio-evidence CSV was supplied in this request. No pilot database connection or calculation was made while preparing this workflow.
