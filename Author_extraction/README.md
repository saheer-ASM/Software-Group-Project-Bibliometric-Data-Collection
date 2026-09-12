# Author_extraction

Builds the author sample the supervisor's sheet specifies, from **open data
only** — no paid Scopus/WoS licence, no API key.

| Cohort | This run | Full scale (sheet) | Source |
|---|---|---|---|
| Field-distributed authors | **1,000** | 95,000 | OpenAlex |
| Prize winners ("special case") | **50** | 5,000 | Wikidata → OpenAlex |

Scale up by editing `TARGET_GENERAL_AUTHORS` / `TARGET_LAUREATE_AUTHORS` in
`config.py` — no other file hardcodes a size.

## Why these sources

**OpenAlex** (`api.openalex.org`) is the open replacement for Microsoft Academic
Graph: ~250M works, ~90M authors, CC0-licensed, no key, no quota beyond a
courtesy rate limit. It is the only free source that carries *all four* things
the sheet needs at once:

- **field classification** — a `domain → field → subfield → topic` hierarchy
  whose 252 subfields are themselves derived from Scopus ASJC, so the project's
  existing 333-field list maps onto it directly;
- **career age** — earliest publication year per author, giving the `t` in
  `CF_com = C * (t + 1) ** -λ` (C = 1.25, λ = 0.0601) on the sheet;
- **impact** — `works_count`, `cited_by_count`, `h_index`, `i10_index`;
- **self-citation** — full `referenced_works` lists, so the ratio is *computed*
  rather than estimated.

Alternatives considered: Crossref has no author disambiguation or field
classification; Semantic Scholar needs an API key and has tighter quotas;
ORCID's public API has no citation data; Scopus/WoS are licensed.

**Wikidata** (`query.wikidata.org/sparql`) is the practical open register of
prize winners — every prize on the sheet is modelled as `award received` (P166),
and most laureates carry an ORCID (P496), which is an exact key into OpenAlex.
Nobelprize.org's own API only covers the Nobels, so it cannot serve the other
eleven prizes.

## Read this first: OpenAlex now meters the free tier

OpenAlex is still free and open, but as of this build the free tier is a **daily
budget, not just a rate limit**:

```
X-RateLimit-Limit      1000      requests per day
X-RateLimit-Limit-USD  0.1       $0.10 per day
X-RateLimit-Reset      ...       resets at midnight UTC
```

**The dollar budget binds before the request count.** Requests are *not* a flat
$0.0001 — a `per-page=200` query costs more than a single-result one. A real run
starting with 999 requests available ran out of money after **514 of them**. So
plan against the $0.10, not the 1,000, and prefer fewer-but-smaller pages when
you have a choice.

The full 1,000-author run needs roughly **6,000–10,000 requests**, so on the
free tier it takes about **a week of daily runs**, or a few dollars of prepaid
credit at <https://openalex.org/pricing> to finish in one sitting.

This is designed for, not worked around:

- every request is counted, and the remaining daily budget is printed at the end
  of each run;
- a budget-exhausted `429` is detected and **not** retried (it resets at
  midnight, so retrying only wastes time) — the run stops cleanly, reports how
  many hours until reset, and writes out everything collected so far;
- re-running the same command resumes from the checkpoint.

So the intended usage is simply: run it, let it stop, run it again tomorrow,
until it reports the full target.

## Working as a team

The OpenAlex daily allowance is **per API key**, so the fastest way to finish is
for everyone to use their own key and **share progress through git**.

Each person, once:

1. Create a free account at <https://openalex.org>, copy the key from
   <https://openalex.org/settings/api> (no payment method needed).
2. `cp .env.example .env` and paste the key in. `.env` is gitignored -- never
   commit it, and do not share one key between people: you would be sharing its
   $1/day budget too.

Then the loop is: `git pull` -> run -> `git add cache && git commit && git push`.

`cache/` is **committed on purpose**. The collected authors live in
`cache/general_checkpoint.jsonl`, and the budget is the bottleneck, so sharing
the checkpoint is how three people with three keys get three times the daily
progress instead of each re-collecting the same fields. Pull before you run so
you do not spend budget on fields someone else already did.

`output/` is gitignored because it rebuilds from `cache/` with **zero** API
calls -- anyone can regenerate the spreadsheets at any time:

```bash
python run_extraction.py --general --laureates
```

If two people collect at once, `general_checkpoint.jsonl` can conflict. It is
append-only JSON Lines, so the fix is always "keep both sides": delete the
conflict markers, keep every line. Duplicate authors are harmless -- the loader
de-duplicates by `openalex_id`.

## Install & run

```bash
pip install -r requirements.txt
python run_extraction.py --all
```

```bash
python run_extraction.py --all --general-target 60 --laureate-target 12 --fresh
```

The second form is a fast smoke run. Other flags: `--general`, `--laureates`,
`--fresh` (ignore checkpoints).

Set `OPENALEX_MAILTO` in the environment to your own address — it is what puts
requests in OpenAlex's fast "polite pool".

To re-report an existing run under a different self-citation cut — no API calls,
it reclassifies straight from the checkpoint:

```bash
python run_extraction.py --all --self-citation-threshold 0.03
```

## What it produces

`output/author_extraction.xlsx` with sheets:

- `distribution_summary` — the sheet's own acceptance checks in one table
  (field coverage, career mix, self-citation mix, per-prize counts)
- `general_authors`, `laureate_authors` — one row per author
- `field_coverage`, `prize_coverage` — quota vs. actually collected, per stratum

plus the same two cohorts as CSV.

## How the sample is stratified

Three strata are satisfied at once (`quotas.py`):

1. **Field** — hard constraint. 1000 ÷ 333 = 3 per field, with the 1-author
   remainder given to a seeded-random field so it is not always the same one.
2. **Career age** — one cursor walks `young → moderately_matured → matured`
   across all fields, so the global mix comes out 334/333/333 even though each
   field only holds three authors. Buckets (`config.CAREER_BUCKETS`):
   `t ≤ 7`, `8–20`, `> 20` years since first publication, where

   ```
   t = max(0, current_year − first_publication_year)
   ```

   The `max(0, …)` guard matters: OpenAlex carries future-dated records
   (early-access and preprints), which would otherwise give a negative `t`.
3. **Self-citation** — a running balancer steers toward
   `TARGET_HIGH_SELF_CITATION_SHARE` (30%) high self-citers, where "high" is
   `self_citation_ratio ≥ HIGH_SELF_CITATION_MIN` (0.10). A uniform random author almost never
   self-cites heavily — most have a handful of papers — so each field is
   sampled **twice**: a base pool, and a prolific-only pool
   (`works_count ≥ PROLIFIC_MIN_WORKS`). Slots that need a high self-citer draw
   from the prolific pool and retry up to `MAX_HIGH_SELF_CITER_TRIES` times
   before settling for whoever fits the career bucket. The retry budget is
   adaptive: once ~30 authors are in and the true hit rate is visible, the
   search backs off rather than spending six extra profiled candidates per slot
   across all 1,000 slots for a trait this rare.

Self-citation ratio is citing-side: of every reference in the author's works
(newest 120), the share pointing at another of their own works. Measured on
real samples it sits around **0.02–0.05**, so the 0.10 cut marks a genuinely
heavy self-citer — but it is a judgement call, not a published constant. Every
row keeps the continuous ratio and `distribution_summary` reports its median /
p75 / p90 / max, so the threshold can be re-picked from the collected data
without re-running the extraction.

Authors for whom OpenAlex holds **no references at all** get
`self_citation_ratio = None` and `high_self_citer = None`. They are counted
separately ("measurable authors" in the summary) and excluded from the 30%
denominator rather than being silently treated as low self-citers.

Prize quota is split equally across the 13 prize groups in `config.PRIZES`
(50 ÷ 13 = 3 each, remainder spread over the first groups). A laureate holding
several prizes is only used once — first prize to claim them keeps them.

## Cost and restartability

Profiling is two-phase: a career probe decides the bucket, and the works fetch
runs only on candidates still in the running. For any author with no more works
than `SELF_CITATION_WORKS_CAP` — the large majority — the probe pulls their
complete works list oldest-first, giving the exact first publication year *and*
everything the self-citation measurement needs, so the second phase costs
nothing. That roughly halves the run.

Budget per author kept is ~6–10 requests: most candidates are profiled and
rejected for being in the wrong career bucket. Everything checkpoints:

- `cache/openalex_topic_index.json` — the whole OpenAlex topic vocabulary
  (26 fields, 252 subfields, ~4.5k topics) in ~26 requests, downloaded once.
  Pages are flushed to `.partial.json` as they arrive, so a budget stop
  mid-download resumes from its cursor instead of starting over.
- `cache/field_topic_map.json` — ASJC → topic ids, matched **locally** against
  that index at zero API cost
- `cache/general_checkpoint.jsonl` — appended after every field
- `cache/wikidata_laureates.json`, `cache/laureate_checkpoint.jsonl`

Re-running picks up where it stopped — including the running self-citation
balance, which is replayed from the checkpointed rows so the 30% target stays on
track across days. Whole fields are the unit of checkpointing, so a field
interrupted mid-way is simply redone; nothing already banked is lost. Delete a
cache file (or pass `--fresh`) to redo that part.

### Why the field map is built this way

The first version resolved each ASJC name with its own `/subfields?search=` call
plus a topics call — ~2.1 requests per field. It spent an entire daily budget
resolving 243 of 333 fields and collected **zero authors**, because the map is a
prerequisite for any collection.

Worse, that search endpoint was *wrong*. It always fuzzy-matches and never says
"no", so it returned confident nonsense:

| ASJC name | what the search endpoint returned |
|---|---|
| Colloid and Surface Chemistry | Biomedical Engineering |
| Chemical Engineering | Environmental Chemistry |
| Multidisciplinary | Statistics, Probability and Uncertainty |

Authors sampled for "Colloid and Surface Chemistry" would have been biomedical
engineers. Now the vocabulary is downloaded in bulk and matched locally, exact
matches first, and every mapping is inspectable in the cache file before a
single author is collected.

It also fixes the 28 ASJC names the search endpoint failed on outright. Those are
mostly umbrella categories — "General Chemistry", "Chemistry (miscellaneous)" —
which have no subfield equivalent, because OpenAlex's 252 subfields *are* ASJC
with the umbrella and miscellaneous entries stripped out. They now fall back to
the field level, taking topics round-robin across that field's subfields so one
corner of a broad category does not stand in for the whole thing.

## Files

| File | Role |
|---|---|
| `config.py` | every tunable: targets, buckets, thresholds, prize Q-ids |
| `asjc_fields.py` | the 333 ASJC subject areas (generated from `data-collection-for-tunning/main.py`) |
| `openalex.py` | polite OpenAlex client with retry/backoff and cursor paging |
| `wikidata.py` | SPARQL laureate queries + prize-label → Q-id helper |
| `topic_index.py` | bulk download of OpenAlex's fields/subfields/topics, resumable |
| `field_mapping.py` | ASJC name → topic ids, matched locally against that index |
| `profiling.py` | career probe (cheap) and self-citation measurement (expensive) |
| `quotas.py` | the three-stratum quota arithmetic |
| `collect_general.py` | the 1,000-author cohort |
| `collect_laureates.py` | the 50-laureate cohort |
| `run_extraction.py` | CLI + Excel/CSV output |

## Career factor (CF_com)

The sheet's career compensation factor is

```
CF_com = C * (t + 1) ** -λ        C = 1.25, λ = 0.0601
```

It is **not** used for sampling — it is computed upstream and lives in
`author_paper_field_effective_citation.career_factor`. It is carried on every
output row as `career_factor_cf_com` purely so the extraction can be reconciled
against that upstream column.

It is a very gentle decay, and it is worth knowing how flat:

| t | 0 | 7 | 20 | 40 | 100 |
|---|---|---|---|---|---|
| CF_com | 1.2500 | 1.1031 | 1.0410 | 1.0000 | 0.9472 |

Across a whole 100-year career the factor moves only 1.250 → 0.947, and **48.5%
of that entire decay is spent in the first seven years** — half of it by `t = 8`.
Past `t ≈ 20` it is nearly flat, so CF_com barely distinguishes a 25-year career
from a 60-year one.

Two consequences worth noting:

- The `young` cutoff at `t ≤ 7` lands almost exactly on the half-decay point,
  which is a better justification for it than the funder convention it was
  originally picked from. The `8–20` split remains an arbitrary choice.
- CF_com is smooth and monotonic, so it implies **no** natural breakpoints. It
  cannot tell you where "moderately matured" ends; that stays a judgement call
  for the supervisor.

## The 5,000-laureate full-scale target is not reachable

The Wikidata laureate lists are cached in full (`cache/wikidata_laureates.json`,
fetched once, unmetered). Across all thirteen prizes on the sheet there are
**2,116 people in total**, 681 of them with an ORCID:

| prize | laureates | with ORCID |
|---|---:|---:|
| Nobel Prize (physics/chemistry/medicine) | 658 | 163 |
| Lasker Award | 412 | 96 |
| Wolf Prize | 377 | 126 |
| Dirac Medal | 122 | 61 |
| Shaw Prize | 107 | 55 |
| Breakthrough Prize in Life Sciences | 82 | 70 |
| Crafoord Prize | 78 | 28 |
| Turing Award | 79 | 15 |
| Fields Medal | 68 | 18 |
| Breakthrough Prize (fundamental physics) | 51 | 29 |
| IEEE John von Neumann Medal | 31 | 7 |
| Abel Prize | 29 | 5 |
| Knuth Prize | 22 | 8 |
| **total** | **2,116** | **681** |

The **50-author pilot is comfortably satisfiable** — 4 per prize, and the
smallest prize still has 22 holders.

The sheet's full-scale 5,000 with "equal distribution of each prize winner" is
not: that needs 385 per prize, and five of the thirteen prizes have fewer than
70 people in existence. Even taking *every* laureate of *all* thirteen prizes
gives 2,116. Reaching 5,000 would mean adding more prizes, or dropping the
equal-distribution requirement. Worth raising before the full run.

## The one result to check with the supervisor

The career and field strata come out exactly on target. The **self-citation
stratum does not**, and that is a property of the data rather than a bug:
measured citing-side self-citation runs median ≈ 0.022, p90 ≈ 0.036, max ≈ 0.067
on a real pilot. There is no population of authors sitting at 0.15+ to sample.

So "high self-citer" can only ever mean *relatively* high. What each cut yields
on a pilot of 18:

| threshold | high self-citers |
|---|---|
| 0.10 | 0 of 17 measurable |
| 0.05 (current default) | 1 of 17 |
| 0.03 | 4 of 17 |
| 0.02 | 9 of 17 |

Pick the cut with the supervisor, then re-report with
`--self-citation-threshold` — the collected data does not need to change.

## Notes / open points

- The sheet says "334 fields"; the project's existing list has **333** entries.
  Same list is reused here so both collectors stratify identically — worth
  confirming which one the 334th is.
- `data-collection-for-tunning/main.py` has a **Cyrillic І (U+0406)** at the
  start of "Issues, Ethics and Legal Aspects". It is corrected in
  `asjc_fields.py` (with an assertion to catch any recurrence), but the original
  is still wrong and would silently never match anything.
- The two cohorts are collected **separately**, mirroring the sheet's 95k + 5k.
  An author can legitimately appear in both; `distribution_summary` reports the
  overlap count rather than silently dropping it.
- Adding a prize: `WikidataClient().resolve_prize_label("…")` gives candidate
  Q-ids to paste into `config.PRIZES`. The SPARQL walks `P279*`/`P361*` from
  each root, so a root like the Wolf Prize picks up its per-discipline
  sub-prizes automatically.
- Only ~32% of laureates carry an ORCID. Those are matched into OpenAlex
  exactly and are tried first; the rest fall back to a verified name match
  (`match_method` on every row records which was used, so name matches can be
  spot-checked).
- Nothing here writes to PostgreSQL. Output is CSV/XLSX so it can be reviewed
  before any load into the `author` table.
