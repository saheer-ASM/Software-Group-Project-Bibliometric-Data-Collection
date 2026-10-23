# Running the equations (NM-index)

How to collect the data from OpenAlex and calculate Equations 1–27 (the NM-index), step by
step, in the right order.

- All scripts are in **`OpenAlex_Data_Collection`**. They write to one SQLite file,
  **`OpenAlex_Data_Collection\database\openalex.db`** (about 76 GB). Keep the file where it is.
- The website only reads this file. After a step finishes, refresh the website to see the new
  values. To run the website, see [RUN_PRODUCTION.md](RUN_PRODUCTION.md).
- The folders `Calculating_ISC`, `Calculating_Total_Cites`, `Equations_12_13_14`,
  `eq16_field_hindex`, `eq17_modified_hindex`, `modified_hf_index`, `modified_hm_index`,
  `Modified_G_Index`, `final_nm_index`, `career-compentation`, `Author contribution` and
  `scripts_db` are the old cloud (PostgreSQL) versions. This guide does not use them.

**Contents:** [1. Setup](#1-setup) · [2. The order](#2-the-order) · [3. Rules](#3-rules) ·
[4. The steps](#4-the-steps) · [5. Add authors later, re-run, or start again](#5-add-authors-later-re-run-or-start-again) ·
[6. Current status](#6-current-status-23-october-2026)

---

## 1. Setup

### Every time you open PowerShell

```powershell
cd D:\SoftwareProject\OpenAlex_Data_Collection
..\.venv\Scripts\Activate.ps1
function dbq($sql) { python -c "import sqlite3, sys; c = sqlite3.connect('file:database/openalex.db?mode=ro', uri=True); [print(row) for row in c.execute(sys.argv[1])]" ($sql -replace '\s+', ' ') }
```

- **Every command in this guide runs from this folder.**
- The prompt now starts with `(.venv)`. If Windows says that running scripts is disabled, run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.
- `dbq` runs one SQL query **read-only**, so it can never change the database. Every step below
  ends with a `dbq` check. Try it: `dbq "SELECT pub_finished, COUNT(*) FROM author GROUP BY 1"`

### Once

1. Install the Python packages:

   ```powershell
   pip install -r requirements.txt numpy pandas scipy torch transformers
   ```

   `requirements.txt` lists only the data-collection packages. The equations also need numpy,
   pandas and scipy, and step 5 needs torch and transformers.

2. Check `OpenAlex_Data_Collection\.env` (copy `.env.example` to `.env` if it is missing):

   | Setting | Used in | Meaning |
   |---|---|---|
   | `OPENALEX_MAILTO` | steps 1–4 | an e-mail address; puts requests in OpenAlex's faster "polite pool" |
   | `OPENALEX_API_KEY` | steps 1–3 | OpenAlex API key; raises the daily budget |
   | `OPENALEX_API_KEY_CO_AUTHOR` | step 4 | a second key, used only by step 4 |

### How the scripts keep track of their progress

Each step marks its progress in the database, so **any step can be stopped (Ctrl+C) and started
again**: it continues where it stopped.

| Column | Values |
|---|---|
| `author.pub_finished` | `need to update`: added, publications not collected yet → `done`: a **target author**, the NM-index is calculated for these. `no need`: a co-author, kept as data only |
| `publication.update_status` | `need to update`: citing papers not collected yet → `updated`. `no need to update`: a citing paper |
| `publication.co_author` | empty → `done` when the paper's authors are collected |
| `publication.field_classified` | `not done` → `done` when the paper has research fields |

### Good habits

- Try a step with **`--dry-run`** first where it exists: it calculates and prints, but writes
  nothing. Many steps also accept **`--limit N`** to test on a few rows.
- Run **one writing script at a time**. A second writer waits, or stops with `database is locked`.
- If the website is running in Docker, some pages may show errors while a script writes (Docker
  cannot see the script's file locks). Run long scripts when nobody uses the site, or stop it.
- Before big changes (section 5), copy the database to another drive if you have about 80 GB
  free: `Copy-Item database\openalex.db E:\backup\openalex.db`

---

## 2. The order

| Step | What it does | Equations | Command | Needs step |
|---|---|---|---|---|
| 1 | Add an author list | – | `python add_laureate_authors.py --csv <list.csv>` | – |
| 2 | Collect the authors' publications | – | `python fill_publications.py` | 1 |
| 3 | Collect the papers that cite them | – | `python fill_cited_publications.py` | 2 |
| 4 | Collect the authors of every paper | – | `python collect_co_authors.py` | 3 |
| 5 | Classify every paper into research fields | – | `python fill_field_classification.py` | 3 |
| 6 | Author contribution weights | 1–3, 6 | `python author_contribution_local\run_author_contribution.py` | 4, 5 |
| 7 | Career factor | 10 | `python career_compensation_local\run_career_compensation.py --as-of-year 2026` | 4 |
| 8 | Influential self-citations, adjusted citations | 7–9 | `python -m isc_local.run_isc` | 6 |
| 9 | Total cites T_a | 11 | `python -m total_cites_local.run_total_cites --cohort done --as-of-year 2026` | 8 |
| 10 | Citation cap, citations per paper S_a, citation rate U_a | 12–14 | `python -m eq12_13_14_local.run_equations_12_13_14 --as-of-year 2026` | 7, 9 |
| 11 | Effective citations | 15 | `python -m eq15_local.run_equation_15` | 10 |
| 12 | Field-level hf-index | 16 | `python -m eq16_local.run_equation_16 --cohort done` | 11 |
| 13 | Modified hf-index Hf_a | 17 | `python -m eq17_local.run_equation_17 --cohort done` | 12 |
| 14 | Modified hm-index Hm_a | 18–20 | `python -m modified_hm_index_local.run_calculation --cohort done` | 11 |
| 15 | Modified g-index G_a | 20–22 | `python -m modified_g_index_local.run_calculation --cohort done` | 11 |
| 16 | **Final NM-index** | 24–27 | `python -m final_nm_index_local.run_calculation --cohort done` | 9, 10, 13, 14, 15 |

- Step 7 can run any time after step 4, as long as it is before step 10.
- Steps 12–13, 14 and 15 each need only step 11, so they can run in any order.
- Optional, not used by the NM-index: `python fill_institutions.py` saves the institution
  (name, country) of each target author.
- The equation numbers are the ones written at the top of each script (Equation 20 appears in
  both the hm-index and the g-index script).

```
1 Add authors
  └─► 2 Publications
        └─► 3 Citing papers
              ├─► 4 Co-authors ─────────────────────────┐
              └─► 5 Fields                              │
                    └─► 6 Contribution weights (Eq 1–3, 6)    ◄── needs 4 and 5
                          └─► 8 Self-citations (Eq 7–9)
                                └─► 9 Total cites (Eq 11)
  7 Career factor (Eq 10)  ◄── needs 4  └─► 10 Eq 12–14      ◄── also needs 7
                                              └─► 11 Eq 15
                                                    ├─► 12 Eq 16 ─► 13 Eq 17 ────┐
                                                    ├─► 14 hm-index (Eq 18–20) ──┼─► 16 NM-index (Eq 24–27)
                                                    └─► 15 g-index (Eq 20–22) ───┘    ◄── also uses 9 and 10
```

### Run everything, in order

```powershell
# --- data (only needed when you add authors: see step 1) ---
python add_laureate_authors.py --csv ..\Author_extraction\output\<your_list>.csv
python fill_publications.py
python fill_cited_publications.py
python collect_co_authors.py
python fill_field_classification.py

# --- equations ---
python author_contribution_local\run_author_contribution.py
python career_compensation_local\run_career_compensation.py --as-of-year 2026
python -m isc_local.run_isc
python -m total_cites_local.db_setup
python -m total_cites_local.run_total_cites --cohort done --as-of-year 2026
python -m eq12_13_14_local.run_equations_12_13_14 --as-of-year 2026
python -m eq15_local.run_equation_15
python -m eq16_local.run_equation_16 --cohort done
python -m eq17_local.run_equation_17 --cohort done
python -m modified_hm_index_local.run_calculation --cohort done
python -m modified_g_index_local.run_calculation --cohort done
python -m final_nm_index_local.run_calculation --cohort done
```

---

## 3. Rules

1. **Use `--cohort done`** wherever a step has it. The NM-index is calculated for the *target
   authors* (`pub_finished = 'done'`, 995 authors now). The default, `all`, would also take the
   5.2 million co-authors, run far longer, and change the percentiles of step 16.
2. **Never use `--replace` in step 1.** It removes the other author lists from the cohort.
3. **Use the same `--as-of-year` in steps 7, 9 and 10** (2026 for the current results). Without
   it, steps 9 and 10 use the current year and step 7 uses 2026, so from 2027 on they would
   disagree.
4. **Run one writing script at a time.**
5. **Try `--dry-run` first** where a step has it.

---

## 4. The steps

### Step 1 — Add an author list

**Script** `add_laureate_authors.py` · **Needs** nothing · **Writes** `author` (new authors get
`pub_finished = 'need to update'`)

Adds the authors from a CSV file. Each author is first looked up on OpenAlex (by OpenAlex id if
the CSV has one, otherwise by name). Not found → skipped and reported. New → added as
`need to update`. Already there and `done` → nothing to do. Already there, not `done` → set to
`need to update`. The CSV needs a column `display_name`, `author_name` or `name`, or a column
`openalex_id` or `author_id`.

**⚠️ Never use `--replace`.** It makes the new list the *only* cohort: every other `done` author
is set to `no need`, so all later steps calculate only the new list. We always **add** new
authors to the ones already there (917 + 50 + 28 = 995 now).

```powershell
python add_laureate_authors.py --csv ..\Author_extraction\output\my_new_list.csv --dry-run   # look up + report only
python add_laureate_authors.py --csv ..\Author_extraction\output\my_new_list.csv
```

Without `--csv` it reads `..\Author_extraction\output\laureate_authors.csv`. Options:
`--csv <file>`, `--limit N` (first N names), `--dry-run`. Every lookup is saved in
`cache\<name of the csv>_fill_checkpoint.jsonl`, so a re-run does not search the same names again.

Check: `dbq "SELECT pub_finished, COUNT(*) FROM author GROUP BY 1"` (new authors show as
`need to update` until step 2 runs).

### Step 2 — Collect the authors' publications

**Script** `fill_publications.py` · **Needs** step 1 · **Writes** `publication`, and sets each
finished author to `done`

For every author with `pub_finished = 'need to update'`, it downloads **all** their works. A new
paper is added as `need to update` (so step 3 collects the papers that cite it). A paper that was
only a citing paper so far becomes `need to update`. Papers already `updated` stay as they are.
Then the author is set to `done`: from now on they are a target author. Co-authors and authors
already `done` are never touched.

```powershell
python fill_publications.py --dry-run    # fetch and print, write nothing
python fill_publications.py --limit 3    # only the next 3 authors
python fill_publications.py              # every waiting author
```

If OpenAlex's daily budget for your key runs out, it stops with
`STOPPED: OpenAlex daily budget exhausted ...`. Finished authors are saved; run it again after
midnight UTC.

Check (0 when finished): `dbq "SELECT COUNT(*) FROM author WHERE pub_finished = 'need to update'"`

### Step 3 — Collect the papers that cite them

**Script** `fill_cited_publications.py` · **Needs** step 2 · **Writes** `citation`, new citing
papers in `publication` (as `no need to update`), and sets each finished paper to `updated`

For every publication with `update_status = 'need to update'`, it downloads **all** the papers
that cite it (one level only). In `citation`, `pub_id` is the cited paper and `cites_pub_id` the
paper that cites it.

```powershell
python fill_cited_publications.py --limit 5 --dry-run   # test on 5 papers, write nothing
python fill_cited_publications.py                       # every waiting paper
```

It works in batches of 5,000 papers. Before each new batch it asks
`Continue with the next 5000? [y/N]`: type **`y`** and Enter to go on (just Enter stops; run it
again later to continue). Options: `--batch-size N` (default 5000), `--limit N`, `--dry-run`.

Check (`need to update` = still waiting): `dbq "SELECT update_status, COUNT(*) FROM publication GROUP BY 1"`

### Step 4 — Collect the authors of every paper

**Script** `collect_co_authors.py` · **Needs** step 3 · **Writes** `author` (new co-authors, as
`no need`), `author_contribution_weight` (one row per paper with its first 10 author ids), and
sets `publication.co_author = 'done'`

For every publication whose `co_author` is empty, it downloads the paper's authors (100 papers
per request). It uses its own key, `OPENALEX_API_KEY_CO_AUTHOR`.

```powershell
python collect_co_authors.py --limit 5 --dry-run   # test, write nothing
python collect_co_authors.py                       # every paper without authors
```

Like step 3, type **`y`** at `Continue with the next 5000? [y/N]`. Options: `--batch-size N`,
`--limit N`, `--dry-run`, and `--own-only` (skip the citing papers). **Don't use `--own-only`
for the NM-index**: step 8 needs the authors of the citing papers to find self-citations.
A paper that OpenAlex does not return keeps an empty `co_author`; the next run tries it again.

Check (`None` = no author data yet): `dbq "SELECT co_author, COUNT(*) FROM publication GROUP BY 1"`

### Step 5 — Classify every paper into research fields

**Script** `fill_field_classification.py` · **Needs** step 3 · **Writes** `field_classification`
(up to 3 fields per paper, with weights), and sets `publication.field_classified = 'done'`

For every publication with `field_classified = 'not done'`, it runs the project's fine-tuned ASJC
model on the text `title={…}, abstract={…}`, keeps the 3 best fields, and scales their scores to
add up to 100. The model is `..\asjc fine tunned\my_custom_asjc_model` (`model.safetensors`,
420 MB; set `ASJC_MODEL_PATH` to use another folder). It uses the graphics card (GPU)
automatically if PyTorch can see one, otherwise the CPU, which is much slower for many papers.

```powershell
python fill_field_classification.py --limit 20 --dry-run   # classify 20 and print, write nothing
python fill_field_classification.py                        # every unclassified paper
```

Options: `--limit N`, `--dry-run`, `--status "need to update"` (only papers with that
`update_status`). Every 64 papers are saved together.

Check (no `not done` row = finished): `dbq "SELECT field_classified, COUNT(*) FROM publication GROUP BY 1"`

### Step 6 — Author contribution weights (Equations 1–3 and 6)

**Script** `author_contribution_local\run_author_contribution.py` · **Needs** steps 4 and 5 ·
**Writes** `author_contribution_weight.author_ordering_norm` and `author1id_weight` …
`author10id_weight`

For every paper (up to 10 authors):

1. **Ordering norm**: 1–2 authors → `relative`; 3 or more in A–Z order of their names →
   `alphabetical`, otherwise `relative`.
2. **Weight per author and field**: alphabetical `field_weight / N` (Eq 1); relative
   `field_weight × (1/position) / Σ(1/position)` (Eq 2–3, harmonic).
3. The author's weight is the **sum over the paper's fields** (Eq 6).

Papers without authors or without fields are skipped and counted in the summary. Run it **as a
file path** (not with `python -m`):

```powershell
python author_contribution_local\run_author_contribution.py --dry-run --limit 20
python author_contribution_local\run_author_contribution.py
```

Options: `--limit N`, `--batch-size N` (default 2000), `--dry-run`, `--recompute` (recalculate
papers that already have weights; only after a formula change). Papers that already have an
ordering norm are skipped.

Check (`None` = not calculated): `dbq "SELECT author_ordering_norm, COUNT(*) FROM author_contribution_weight GROUP BY 1"`

### Step 7 — Career factor (Equation 10)

**Script** `career_compensation_local\run_career_compensation.py` · **Needs** step 4 · **Writes**
`author.career_compensation`

```
CF = 1.25 × (t + 1) ^ (−0.0601)              rounded to 4 decimals
t  = as-of year − first publication year     (0 if the year is unknown)
```

The first publication year is the earliest year among the author's papers in
`author_contribution_weight`. The website shows this value as the career compensation. Steps 10
and 11 need it. Run it **as a file path**, with the same year as steps 9 and 10:

```powershell
python career_compensation_local\run_career_compensation.py --dry-run --as-of-year 2026
python career_compensation_local\run_career_compensation.py --as-of-year 2026
```

Options: `--as-of-year YEAR` (default 2026), `--limit N`, `--dry-run`. Safe to run again at any
time; it only rewrites values that change.

Check (995 when complete): `dbq "SELECT COUNT(*) FROM author WHERE pub_finished = 'done' AND career_compensation IS NOT NULL"`

### Step 8 — Influential self-citations and adjusted citations (Equations 7–9)

**Script** `isc_local\run_isc.py` · **Needs** steps 3–6 · **Writes**
`influential_self_citations` (Eq 7–8), `author_paper_adjusted_citations` (Eq 9)

For every citation (paper q cites paper p), every field f of p and every target author a of p:

```
Eq 7   ISC(a,p,q,f) = (self + ε·core) / (self + |J|·core + non_overlap)
Eq 8   TC_adj       = (1 − ISC) × TC_raw          TC_raw = W_p(a) × V_p(f)
Eq 9   sum of TC_adj over every q and f   →   author_paper_adjusted_citations
```

The citing paper must have a row in `author_contribution_weight`. At most 200 citing papers per
cited paper are used, chosen at random with a fixed seed (42), so a re-run gives the same result.
Pairs whose papers have no weights or fields are skipped.

The default **`--targets done`** calculates only for the target authors; the current results
were made this way. (The text at the top of the script says the default is `all`; the real
default is `done`.) `--targets all` takes every author of every cited paper and is far slower.
Run it **as a module**:

```powershell
python -m isc_local.run_isc --dry-run --limit 3   # 3 cited papers, print, write nothing
python -m isc_local.run_isc
```

| Option | Meaning |
|---|---|
| `--targets done` / `all` | whose self-citations are calculated (default `done`) |
| `--limit N` | only the first N cited papers |
| `--dry-run` | calculate and print, write nothing |
| `--cited-pub-id W…` | only this cited paper (can be given several times) |
| `--redo` | recalculate cited papers that already have rows (their old rows are deleted first) |
| `--max-citing N` | citing papers per cited paper (default 200; `0` = all) |
| `--seed N` | seed for the random choice (default 42) |
| `--epsilon-zero X` | ε₀ of Equation 7 (default 0.90) |
| `--weight-tolerance X` | allowed rounding error in the author weights (default 0.02) |

A cited paper that already has rows is skipped, so a new run only does new papers.

Check: `dbq "SELECT COUNT(*), COUNT(DISTINCT target_author_id) FROM author_paper_adjusted_citations"`

### Step 9 — Total cites T_a (Equation 11)

**Script** `total_cites_local\run_total_cites.py` (+ `db_setup.py`) · **Needs** step 8 ·
**Writes** `field_year_adjusted_citation_average`, `total_cites_equation_11_details`,
`author_total_cites`

It runs two parts: (1) the benchmark, the average adjusted citations per field and publication
year (groups with fewer than 10 papers are smoothed); (2) Equation 11, each author's total cites
T_a with the career factor (C = 1.25, λ = 0.0601). The website's **C-score** is
`author_total_cites.total_cites_score`.

```powershell
python -m total_cites_local.db_setup                                         # create the tables: once, and after a reset
python -m total_cites_local.run_total_cites --cohort done --as-of-year 2026
```

This step has **no `--dry-run`**; it rebuilds the benchmark every time.

| Option | Meaning |
|---|---|
| `--cohort done` / `all` | target authors only, or every author (default `all`; **use `done`**) |
| `--as-of-year YEAR` | year used for the career time (default: the current year) |
| `--author-id A…` | only this author (can be given several times) |
| `--career-boost X` / `--career-decay X` | C and λ of Equation 10 (defaults 1.25 / 0.0601) |
| `--benchmark-population updated` / `all` | papers used for the field-year averages: `updated` (default) = papers whose citing papers were collected; `all` = every paper |
| `--min-group-size N` | smaller field-year groups are smoothed (default 10) |

Check (995 / 995 when complete): `dbq "SELECT COUNT(*), SUM(calculation_complete) FROM author_total_cites"`

### Step 10 — Citation cap, citations per paper and citation rate (Equations 12–14)

**Script** `eq12_13_14_local\run_equations_12_13_14.py` · **Needs** steps 9 and 7 · **Writes**
`field_citation_percentile_caps`, `field_adjusted_citation_average`,
`citations_per_paper_details`, `author_citations_per_paper`, `citation_rate_details`,
`author_citation_rate`

- **Eq 12, outlier cap**: per field, the cap R_k,f is the k-th percentile (k = 99) of the
  adjusted citations; larger values are cut down to the cap.
- **Eq 13, citations per paper S_a**: each paper's capped citations compared with its field's
  average, summed per author → `author_citations_per_paper.citations_per_paper_score`.
- **Eq 14, citation rate U_a**: the same, using the years since publication and the
  field-and-year average → `author_citation_rate.citation_rate_score`.

It calculates for the authors that step 9 calculated, so there is no `--cohort` option.

```powershell
python -m eq12_13_14_local.run_equations_12_13_14 --dry-run --as-of-year 2026
python -m eq12_13_14_local.run_equations_12_13_14 --as-of-year 2026
```

Options: `--percentile-k K` (default 99), `--as-of-year YEAR` (default: the current year),
`--dry-run`, `--skip-table-setup`. If it says `No rows found in total_cites_equation_11_details`,
run step 9 first.

Check: `dbq "SELECT COUNT(*), SUM(calculation_complete) FROM author_citations_per_paper"` and
`dbq "SELECT COUNT(*), SUM(calculation_complete) FROM author_citation_rate"`

### Step 11 — Effective citations (Equation 15)

**Script** `eq15_local\run_equation_15.py` · **Needs** steps 10 and 7 · **Writes**
`author_paper_field_effective_citation`

```
TCadj_eff(f, p, i) = CF_com × W_p^(f,i) × TCadj_cap
```

CF_com is the career factor (step 7), W the author's weight in that paper and field, and
TCadj_cap the capped adjusted citations (step 10). A row is `READY` when all three exist,
otherwise `MISSING_VALUE`. Steps 12, 14 and 15 all start from this table.

```powershell
python -m eq15_local.run_equation_15 --dry-run
python -m eq15_local.run_equation_15
```

Options: `--dry-run`, `--skip-table-setup`.

Check: `dbq "SELECT calculation_status, COUNT(*) FROM author_paper_field_effective_citation GROUP BY 1"`

### Step 12 — Field-level hf-index (Equation 16)

**Script** `eq16_local\run_equation_16.py` · **Needs** step 11 · **Writes**
`author_field_modified_hindex`

```
raw_h(a,f)  = the largest h such that the author's h-th best paper in field f has at least h effective citations
Hf_f        = average raw_h of all authors with at least one paper in field f
Hf_{f,a}    = raw_h(a,f) / Hf_f          (status ZERO_FIELD_NORMALIZATION if Hf_f = 0)
```

```powershell
python -m eq16_local.run_equation_16 --dry-run --cohort done
python -m eq16_local.run_equation_16 --cohort done
```

Options: `--cohort done` / `all` (default `all`; **use `done`**; with `done` the old rows are
deleted first so two populations never mix), `--dry-run`, `--skip-table-setup`.

Check: `dbq "SELECT calculation_status, COUNT(*) FROM author_field_modified_hindex GROUP BY 1"`

### Step 13 — Modified hf-index Hf_a (Equation 17)

**Script** `eq17_local\run_equation_17.py` · **Needs** step 12 · **Writes**
`author_modified_hindex` (result: `modified_hindex_final`)

```
field_weight_sum(a,f) = sum, over the author's papers, of the paper's weight in field f (weight / 100)
Hf_a = Σ_f field_weight_sum(a,f) × Hf_{f,a}  /  Σ_f field_weight_sum(a,f)
```

Only fields that got a value in step 12 count; an author with none gets `NO_ELIGIBLE_FIELDS`.

```powershell
python -m eq17_local.run_equation_17 --dry-run --cohort done
python -m eq17_local.run_equation_17 --cohort done
```

Options: `--cohort done` / `all` (**use `done`**), `--dry-run`, `--skip-table-setup`.

Check: `dbq "SELECT calculation_status, COUNT(*) FROM author_modified_hindex GROUP BY 1"`

### Step 14 — Modified hm-index Hm_a (Equations 18–20)

**Script** `modified_hm_index_local\run_calculation.py` · **Needs** step 11 · **Writes** the
column `author.modified_hm_index`

Starts from the `READY` rows of step 11, citations capped at **150**, rows with a zero weight or
career factor left out:

```
Eq 15   tc_eff   = career_factor × author_field_weight × capped_citation
Eq 18   r_eff    = running total of (career_factor × author_field_weight), one author's papers in one field, best tc_eff first
Eq 19   k_valid  = number of leading papers with tc_eff ≥ r_eff;  max_r_eff = r_eff at k_valid
        Hm_f     = average max_r_eff of all authors in field f;   Hm_{f,a} = max_r_eff / Hm_f
Eq 20   Hm_a     = Σ (field_weight × Hm_{f,a}) / Σ field_weight     (0 if nothing to divide by)
```

```powershell
python -m modified_hm_index_local.run_calculation --dry-run --cohort done
python -m modified_hm_index_local.run_calculation --cohort done
```

Options: `--cohort done` / `all` (**use `done`**), `--dry-run`.

Check (995 when complete): `dbq "SELECT COUNT(*) FROM author WHERE pub_finished = 'done' AND modified_hm_index IS NOT NULL"`

### Step 15 — Modified g-index G_a (Equations 20–22)

**Script** `modified_g_index_local\run_calculation.py` · **Needs** step 11 · **Writes** the
column `author.modified_g_index` and the table `modified_g_index_results`

Same starting rows as step 14 (`READY` rows, citations capped at **150**):

```
Eq 15   tc_eff   = career_factor × author_field_weight × capped_citation
Eq 20   A_eff(k) = running total of tc_eff over one author's papers in one field, best first
Eq 21   g_raw    = the largest k with A_eff(k) ≥ k²  (0 if none);  G_f = average g_raw in field f;  G_{f,a} = g_raw / G_f
Eq 22   G_a      = Σ (field_weight × G_{f,a}) / Σ field_weight     (0 if nothing to divide by)
```

The run creates its tables itself (`python -m modified_g_index_local.db_setup` is optional).

```powershell
python -m modified_g_index_local.run_calculation --dry-run --cohort done
python -m modified_g_index_local.run_calculation --cohort done
```

Options: `--cohort done` / `all` (**use `done`**), `--dry-run`.

Check: `dbq "SELECT COUNT(*) FROM modified_g_index_results"`

### Step 16 — Final NM-index (Equations 24–27)

**Script** `final_nm_index_local\run_calculation.py` · **Needs** steps 9, 10, 13, 14 and 15 ·
**Writes** `author_nm_index`

| | Metric | Read from | Step |
|---|---|---|---|
| x1 | T_a, total cites | `author_total_cites.total_cites_score` | 9 |
| x2 | S_a, citations per paper | `author_citations_per_paper.citations_per_paper_score` | 10 |
| x3 | U_a, citation rate | `author_citation_rate.citation_rate_score` | 10 |
| x4 | Hf_a, modified hf-index | `author_modified_hindex.modified_hindex_final` | 13 |
| x5 | Hm_a, modified hm-index | `author.modified_hm_index` | 14 |
| x6 | G_a, modified g-index | `author.modified_g_index` | 15 |

```
Eq 24   Tra_a(x)  transform each metric
Eq 25   Nor_a(x)  normalise it
Eq 26   Per_a(x)  turn it into a percentile from 0 to 100
Eq 27   Nm_a      the average of the six percentiles (weight 1/6 each)
```

**The percentiles compare the authors of the cohort with each other**, so the cohort decides the
result: `--cohort done` = the target authors (**use this**, the current 995 results); `all` =
every author in the `author` table (the default); `eligible` = authors with at least 5 papers
and more than 0 total cites. With `done` or `eligible`, the previous results are deleted first.
The website reads its NM-index from this table.

```powershell
python -m final_nm_index_local.run_calculation --dry-run --cohort done   # prints the top 10, writes nothing
python -m final_nm_index_local.run_calculation --cohort done
```

Check: `dbq "SELECT COUNT(*), ROUND(AVG(nm_index), 2), ROUND(MIN(nm_index), 2), ROUND(MAX(nm_index), 2) FROM author_nm_index"`

---

## 5. Add authors later, re-run, or start again

### A. Add a new author list (most common)

Run steps 1 → 16 in order, with `--cohort done` wherever it exists, and **without `--replace`**
in step 1. Steps 2–6 and 8 only do new work (finished authors, papers and citations are
skipped). Steps 7 and 9–16 recalculate the whole cohort, which is needed because step 16
compares all target authors with each other.

**One extra check after step 8.** Step 8 skips a cited paper that already has rows. If a new
author wrote a paper together with an author who was calculated before, that shared paper was
skipped, so the new author has no self-citation rows for it. List such papers (takes about half
a minute):

```powershell
$sql = @'
SELECT p.cited_pub_id, a.author_id
FROM (SELECT DISTINCT cited_pub_id FROM author_paper_adjusted_citations) AS p
JOIN author_contribution_weight AS acw ON acw.pub_id = p.cited_pub_id
JOIN author AS a ON a.pub_finished = 'done'
 AND a.author_id IN (acw.author1id, acw.author2id, acw.author3id, acw.author4id, acw.author5id,
                     acw.author6id, acw.author7id, acw.author8id, acw.author9id, acw.author10id)
WHERE NOT EXISTS (SELECT 1 FROM author_paper_adjusted_citations AS x
                  WHERE x.cited_pub_id = p.cited_pub_id AND x.target_author_id = a.author_id)
'@
dbq $sql
```

Nothing printed = nothing missing (true on 23 Oct 2026). Otherwise recalculate each listed
paper, then continue with step 9:

```powershell
python -m isc_local.run_isc --redo --cited-pub-id W1234567890 --cited-pub-id W2345678901
```

### B. Start all calculations again from zero

Use this after a formula changed, or if the results look mixed up. The collected data is
**never** touched (`author`, `publication`, `citation`, `author_contribution_weight`,
`field_classification`, `institution`, `author_institution`).

```powershell
python reset_calculated_tables.py          # dry run: only lists what would be dropped
python reset_calculated_tables.py --yes    # really drops the calculated tables
python -m total_cites_local.db_setup       # step 9 needs its tables back
```

It drops the tables of steps 8–16 and the columns `author.modified_hm_index` and
`author.modified_g_index`. Then run steps 8 → 16 again. If the contribution formula changed,
also run step 6 with `--recompute` (its weights are not dropped) and step 7 again.
`--yes --vacuum` also shrinks the database file, but needs a lot of free disk space and time.

**From the reset until step 16 has finished, the website's author pages and comparisons show
errors**, because the tables they read are gone (the dashboard counts keep working). Do this
when nobody needs the site.

### C. Change a setting

Re-run from the first step that uses the setting, and every step after it:

| Setting | Re-run from |
|---|---|
| as-of year (`--as-of-year`) | step 7, then 9 → 16 (same year in 7, 9 and 10) |
| percentile cap (`--percentile-k`) | step 10 → 16 |
| ISC options (`--max-citing`, `--epsilon-zero`, `--targets`) | step 8 with `--redo`, then 9 → 16 |
| final cohort (`--cohort`) | step 16 |

---

## 6. Current status (23 October 2026)

| | |
|---|---|
| Target authors (`pub_finished = 'done'`) | 995: 917 general + 50 laureates + 28 staff (added 16 Oct 2026) |
| Result tables of steps 9–16 | all calculated for these 995 authors |
| Publications still waiting for their citing papers (step 3) | 146 |
| Publications without co-author data (step 4) | 12,007 (OpenAlex returned nothing; step 4 retries them) |
| Publications with a field classification (step 5) | all 3,066,501 |
