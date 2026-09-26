"""Tunables for the author-extraction sample.

The supervisor's sheet specifies a full-scale target of 95,000 field-distributed
authors plus 5,000 prize winners.  This run is the scaled-down pilot:
1,000 general authors + 50 prize winners ("special case").  Change the two
TARGET_* numbers to scale back up -- nothing else in the code hardcodes a size.
"""

import os

from asjc_fields import ASJC_FIELDS

try:                                    # optional; the env var works without it
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------- cohort sizes
TARGET_GENERAL_AUTHORS = 250        # full scale: 95_000
TARGET_LAUREATE_AUTHORS = 50        # full scale: 5_000  ("special case")

# The two cohorts are collected separately, mirroring the sheet, which lists the
# 95k and the 5k as two distinct requirements.  A laureate that also turns up in
# the general sample is left in both; `run_extraction.py` reports the overlap.

# ------------------------------------------------------------------- API setup
# OpenAlex asks for a contact address to put you in the fast "polite pool".
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "tempmailcloud7@gmail.com")

# A FREE API key raises the daily allowance from $0.10 to $1.00 -- ten times the
# budget, no payment method required.  Sign up at openalex.org, then copy the key
# from openalex.org/settings/api and set OPENALEX_API_KEY in your environment.
# Costs within that allowance: list/filter calls $0.0001, search calls $0.001
# (ten times more -- the only `search=` left is the laureate name fallback, and
# every shortlisted laureate has an ORCID so it rarely fires), and singleton
# lookups (/authors/A123) are effectively free at 1 credit.
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
OPENALEX_BASE = "https://api.openalex.org"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = f"BibliometricAuthorExtraction/1.0 (mailto:{OPENALEX_MAILTO})"

REQUEST_DELAY_SECONDS = 0.12        # ~8 req/s; polite-pool limit is 10 req/s
MAX_RETRIES = 4
REQUEST_TIMEOUT = 60

# --------------------------------------------------------------- field sampling
FIELDS = ASJC_FIELDS                # 333 ASJC subject areas
RANDOM_SEED = 20260910              # makes the whole run reproducible

MIN_WORKS_COUNT = 5                 # skip near-empty author records
MAX_TOPIC_IDS_PER_FILTER = 45       # OpenAlex caps OR-lists at 50 values
CANDIDATE_POOL_MULTIPLIER = 12      # candidates sampled per author actually kept
MIN_CANDIDATE_POOL = 24

# -------------------------------------------------------------- career profile
# t = years since first publication, the `t` in the sheet's career compensation
# factor:
#
#     CF_com = C * (t + 1) ** -LAMBDA
#
# A gentle power-law decay: 1.2500 at t=0, 1.1031 at t=7, 1.0410 at t=20,
# 0.9472 at t=100.  Nearly half the lifetime decay is spent in the first seven
# years, which is why the `young` bucket ends there.
CAREER_FACTOR_C = 1.25
CAREER_FACTOR_LAMBDA = 0.0601

# Buckets give the required young / moderately matured / matured mix.  CF_com is
# smooth and monotonic, so it implies no breakpoints of its own -- these cuts
# are a sampling device and still need supervisor sign-off.
CAREER_BUCKETS = {
    "young": (0, 7),                # t <= 7
    "moderately_matured": (8, 20),
    "matured": (21, 200),
}
CAREER_BUCKET_ORDER = ["young", "moderately_matured", "matured"]

# ------------------------------------------------------------- self-citation
# Ratio = (references from this author's works that point at this author's own
# works) / (all references from this author's works).
SELF_CITATION_WORKS_CAP = 120       # works inspected per author

# Measured on a real pilot sample the citing-side ratio runs median 0.022,
# p90 0.036, max 0.067 -- so the 0.15 this started at, and even 0.10, flagged
# nobody at all.  0.05 sits above the p90 of that pilot, i.e. it marks the
# top decile rather than an absolute notion of "heavy".
#
# This is a judgement call, not a published constant.  The continuous
# `self_citation_ratio` is stored on every row, `distribution_summary` reports
# its median/p75/p90/max, and `--self-citation-threshold` reclassifies straight
# from the checkpoint -- so the cut can be re-picked with the supervisor without
# re-collecting anything.
HIGH_SELF_CITATION_MIN = 0.05       # >= this counts as a "high self-citer"
TARGET_HIGH_SELF_CITATION_SHARE = 0.30   # aim for ~30% high self-citers

# A uniform random author almost never self-cites heavily (most have a handful
# of papers).  High self-citation tracks productivity, so slots that need a high
# self-citer are drawn from a second, prolific-only pool.
PROLIFIC_MIN_WORKS = 40
MAX_HIGH_SELF_CITER_TRIES = 6       # per slot, before settling for whoever fits

# ------------------------------------------------------------------- prizes
# Wikidata Q-ids, each resolved and checked against wbsearchentities.  The query
# walks P279*/P361* from the root, so a root like the Wolf Prize also picks up
# its per-discipline sub-prizes.
PRIZES = {
    "Nobel Prize": ["Q38104", "Q44585", "Q80061"],   # physics, chemistry, medicine
    "Lasker Award": ["Q921415"],
    "Breakthrough Prize": ["Q1314470"],              # fundamental physics
    "Breakthrough Prize in Life Sciences": ["Q5019489"],
    "Wolf Prize": ["Q739936"],
    "Dirac Medal": ["Q20049851", "Q1227372"],        # ICTP + IOP
    "Knuth Prize": ["Q1165991"],
    "IEEE John von Neumann Medal": ["Q727274"],
    "Turing Award": ["Q185667"],
    "Abel Prize": ["Q188184"],
    "Fields Medal": ["Q28835"],
    "Shaw Prize": ["Q584250"],
    "Crafoord Prize": ["Q583069"],
}

# ------------------------------------------------------------------- outputs
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
FIELD_MAP_CACHE = os.path.join(CACHE_DIR, "field_topic_map.json")
GENERAL_CSV = os.path.join(OUTPUT_DIR, "general_authors.csv")
LAUREATE_CSV = os.path.join(OUTPUT_DIR, "laureate_authors.csv")
WORKBOOK = os.path.join(OUTPUT_DIR, "author_extraction.xlsx")
